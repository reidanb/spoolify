"""
Data retrieval functions (return data, no printing).
These are reused by both CLI and API layers.
"""

import re
from datetime import date

_MONTH_RE = re.compile(r'^\d{4}-(?:0[1-9]|1[0-2])$')


def _validate_month_param(value):
    """Validates that value matches YYYY-MM format. Raises ValueError if not."""
    if value is None:
        return None
    if not _MONTH_RE.match(value):
        raise ValueError(f"Invalid month format: expected YYYY-MM")
    return value


def _next_month(month_value):
    year, month = month_value.split("-")
    next_month = int(month) + 1
    next_year = int(year)
    if next_month > 12:
        next_month = 1
        next_year += 1
    return f"{next_year:04d}-{next_month:02d}"


def _build_ts_filter(start_month=None, end_month=None, include_ts_not_null=True):
    start_month = _validate_month_param(start_month)
    end_month = _validate_month_param(end_month)

    clauses = []
    params = []

    if include_ts_not_null:
        clauses.append("ts IS NOT NULL")

    if start_month:
        clauses.append("ts >= ?")
        params.append(start_month + "-01T00:00:00")

    if end_month:
        clauses.append("ts < ?")
        params.append(_next_month(end_month) + "-01T00:00:00")

    where_clause = ""
    if clauses:
        where_clause = "WHERE " + " AND ".join(clauses)

    return where_clause, params


def get_top_artists(conn, limit=10):
    """Returns top artists by listening time."""
    cur = conn.cursor()
    cur.execute('''
        SELECT artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE artist_name IS NOT NULL
        GROUP BY artist_name
        ORDER BY minutes DESC
        LIMIT ?
    ''', (limit,))
    return cur.fetchall()


def get_top_tracks(conn, limit=10):
    """Returns top tracks by listening time."""
    cur = conn.cursor()
    cur.execute('''
        SELECT track_name, artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE track_name IS NOT NULL AND artist_name IS NOT NULL
        GROUP BY track_name, artist_name
        ORDER BY minutes DESC
        LIMIT ?
    ''', (limit,))
    return cur.fetchall()


def get_monthly_stats(conn):
    """Returns monthly listening stats."""
    cur = conn.cursor()
    cur.execute('''
        SELECT substr(ts, 1, 7) AS month, COUNT(*) AS plays, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY month
        ORDER BY month
    ''')
    return cur.fetchall()


def get_yearly_stats(conn):
    """Returns yearly listening stats."""
    cur = conn.cursor()
    cur.execute('''
        SELECT substr(ts, 1, 4) AS year, COUNT(*) AS plays, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY year
        ORDER BY year
    ''')
    return cur.fetchall()


def get_hourly_stats(conn):
    """Returns hour-of-day listening stats."""
    cur = conn.cursor()
    cur.execute('''
        SELECT CAST(strftime('%H', ts) AS INTEGER) AS hour, COUNT(*) AS plays, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY hour
        ORDER BY hour
    ''')
    return cur.fetchall()


def get_overall_stats(conn):
    """Returns overall listening statistics."""
    cur = conn.cursor()
    cur.execute('SELECT SUM(ms_played) FROM plays')
    total_ms = cur.fetchone()[0] or 0
    total_minutes = int(total_ms // 60000)
    total_minutes_exact = total_ms / 60000.0
    total_hours = total_minutes / 60
    
    cur.execute('SELECT COUNT(*) FROM plays')
    total_plays = cur.fetchone()[0]
    
    return {
        "total_minutes": total_minutes,
        "total_minutes_exact": total_minutes_exact,
        "total_hours": round(total_hours, 1),
        "total_plays": total_plays
    }


def get_listening_profile_data(conn):
    """Returns listening profile (time-of-day breakdown)."""
    cur = conn.cursor()
    buckets = [
        (0, 6, "night"),
        (6, 12, "morning"),
        (12, 18, "afternoon"),
        (18, 24, "evening"),
    ]
    bucket_labels = [b[2] for b in buckets]
    bucket_minutes = {label: 0 for label in bucket_labels}
    cur.execute('''
        SELECT CAST(strftime('%H', ts) AS INTEGER) AS hour, SUM(ms_played) / 60000.0 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY hour
    ''')
    hour_data = cur.fetchall()
    total_minutes = sum(minutes for _, minutes in hour_data)
    for hour, minutes in hour_data:
        for start, end, label in buckets:
            if start <= hour < end:
                bucket_minutes[label] += minutes
                break
    bucket_pct = {
        label: (bucket_minutes[label] / total_minutes * 100) if total_minutes > 0 else 0
        for label in bucket_labels
    }
    primary_label = max(bucket_labels, key=lambda l: bucket_pct[l])
    primary_pct = bucket_pct[primary_label]
    if primary_pct > 40:
        confidence = "high"
    elif primary_pct >= 30:
        confidence = "moderate"
    else:
        confidence = "low"
    peak_hour = max(hour_data, key=lambda x: x[1])[0] if hour_data else None
    sorted_pct = sorted(bucket_pct.values(), reverse=True)
    skew = f"{primary_label}-heavy" if sorted_pct[0] - sorted_pct[1] >= 15 else "balanced"
    return {
        "bucket_minutes": bucket_minutes,
        "bucket_pct": bucket_pct,
        "primary_profile": primary_label,
        "primary_pct": primary_pct,
        "confidence": confidence,
        "peak_hour": peak_hour,
        "skew": skew,
        "very_low_night": bucket_pct["night"] < 10,
        "total_minutes": total_minutes,
        "total_minutes_exact": total_minutes,
    }


def get_unique_artist_count(conn):
    """Returns count of unique artists."""
    cur = conn.cursor()
    cur.execute('SELECT COUNT(DISTINCT artist_name) FROM plays WHERE artist_name IS NOT NULL')
    return cur.fetchone()[0] or 0


def get_unique_track_count(conn):
    """Returns count of unique tracks."""
    cur = conn.cursor()
    cur.execute('''
        SELECT COUNT(DISTINCT COALESCE(NULLIF(track_uri, ''), track_name || '||' || COALESCE(artist_name, '')))
        FROM plays
        WHERE track_name IS NOT NULL
    ''')
    return cur.fetchone()[0] or 0


def get_date_range(conn):
    """Returns earliest and latest timestamps in database."""
    cur = conn.cursor()
    cur.execute('SELECT MIN(ts), MAX(ts) FROM plays WHERE ts IS NOT NULL')
    min_ts, max_ts = cur.fetchone()
    return {"start": min_ts, "end": max_ts}


def get_peak_month(conn):
    """Returns month with most listening minutes."""
    cur = conn.cursor()
    cur.execute('''
        SELECT substr(ts, 1, 7) AS month, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY month
        ORDER BY minutes DESC
        LIMIT 1
    ''')
    row = cur.fetchone()
    return row[0] if row else None


# Date-range filtered versions
def get_overall_stats_filtered(conn, start_month=None, end_month=None):
    """Returns overall listening statistics for a date range."""
    where_clause, params = _build_ts_filter(start_month, end_month, include_ts_not_null=False)
    cur = conn.cursor()
    cur.execute(f'SELECT SUM(ms_played) FROM plays {where_clause}', params)
    total_ms = cur.fetchone()[0] or 0
    total_minutes = int(total_ms // 60000)
    total_minutes_exact = total_ms / 60000.0
    total_hours = total_minutes / 60
    
    cur.execute(f'SELECT COUNT(*) FROM plays {where_clause}', params)
    total_plays = cur.fetchone()[0]
    
    return {
        "total_minutes": total_minutes,
        "total_minutes_exact": total_minutes_exact,
        "total_hours": round(total_hours, 1),
        "total_plays": total_plays
    }


def get_unique_artist_count_filtered(conn, start_month=None, end_month=None):
    """Returns count of unique artists for a date range."""
    where_clause, params = _build_ts_filter(start_month, end_month)
    where_clause = f"{where_clause} AND artist_name IS NOT NULL" if where_clause else "WHERE artist_name IS NOT NULL"
    cur = conn.cursor()
    cur.execute(f'SELECT COUNT(DISTINCT artist_name) FROM plays {where_clause}', params)
    return cur.fetchone()[0] or 0


def get_unique_track_count_filtered(conn, start_month=None, end_month=None):
    """Returns count of unique tracks for a date range."""
    where_clause, params = _build_ts_filter(start_month, end_month)
    where_clause = f"{where_clause} AND track_name IS NOT NULL" if where_clause else "WHERE track_name IS NOT NULL"
    cur = conn.cursor()
    cur.execute(f'''
        SELECT COUNT(DISTINCT COALESCE(NULLIF(track_uri, ''), track_name || '||' || COALESCE(artist_name, '')))
        FROM plays {where_clause}
    ''', params)
    return cur.fetchone()[0] or 0


def get_monthly_stats_filtered(conn, start_month=None, end_month=None):
    """Returns monthly listening stats for a date range."""
    where_clause, params = _build_ts_filter(start_month, end_month)
    cur = conn.cursor()
    cur.execute(f'''
        SELECT substr(ts, 1, 7) AS month, COUNT(*) AS plays, SUM(ms_played) / 60000 AS minutes
        FROM plays
        {where_clause}
        GROUP BY month
        ORDER BY month
    ''', params)
    return cur.fetchall()


def get_yearly_stats_filtered(conn, start_month=None, end_month=None):
    """Returns yearly listening stats for a date range."""
    where_clause, params = _build_ts_filter(start_month, end_month)
    cur = conn.cursor()
    cur.execute(f'''
        SELECT substr(ts, 1, 4) AS year, COUNT(*) AS plays, SUM(ms_played) / 60000 AS minutes
        FROM plays
        {where_clause}
        GROUP BY year
        ORDER BY year
    ''', params)
    return cur.fetchall()


def get_hourly_stats_filtered(conn, start_month=None, end_month=None):
    """Returns hour-of-day listening stats for a date range."""
    where_clause, params = _build_ts_filter(start_month, end_month)
    cur = conn.cursor()
    cur.execute(f'''
        SELECT CAST(strftime('%H', ts) AS INTEGER) AS hour, COUNT(*) AS plays, SUM(ms_played) / 60000 AS minutes
        FROM plays
        {where_clause}
        GROUP BY hour
        ORDER BY hour
    ''', params)
    return cur.fetchall()


def get_top_artists_filtered(conn, limit=10, start_month=None, end_month=None):
    """Returns top artists by listening time for a date range."""
    where_clause, params = _build_ts_filter(start_month, end_month)
    where_clause = f"{where_clause} AND artist_name IS NOT NULL" if where_clause else "WHERE artist_name IS NOT NULL"
    cur = conn.cursor()
    cur.execute(f'''
        SELECT artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        {where_clause}
        GROUP BY artist_name
        ORDER BY minutes DESC
        LIMIT ?
    ''', (*params, limit))
    return cur.fetchall()


def get_top_tracks_filtered(conn, limit=10, start_month=None, end_month=None):
    """Returns top tracks by listening time for a date range."""
    where_clause, params = _build_ts_filter(start_month, end_month)
    where_clause = (
        f"{where_clause} AND track_name IS NOT NULL AND artist_name IS NOT NULL"
        if where_clause else
        "WHERE track_name IS NOT NULL AND artist_name IS NOT NULL"
    )
    cur = conn.cursor()
    cur.execute(f'''
        SELECT track_name, artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        {where_clause}
        GROUP BY track_name, artist_name
        ORDER BY minutes DESC
        LIMIT ?
    ''', (*params, limit))
    return cur.fetchall()


def get_date_range_filtered(conn, start_month=None, end_month=None):
    """Returns earliest and latest timestamps for a date range."""
    where_clause, params = _build_ts_filter(start_month, end_month)
    cur = conn.cursor()
    cur.execute(f'SELECT MIN(ts), MAX(ts) FROM plays {where_clause}', params)
    min_ts, max_ts = cur.fetchone()
    return {"start": min_ts, "end": max_ts}


def get_peak_month_filtered(conn, start_month=None, end_month=None):
    """Returns month with most listening minutes for a date range."""
    where_clause, params = _build_ts_filter(start_month, end_month)
    cur = conn.cursor()
    cur.execute(f'''
        SELECT substr(ts, 1, 7) AS month, SUM(ms_played) / 60000 AS minutes
        FROM plays
        {where_clause}
        GROUP BY month
        ORDER BY minutes DESC
        LIMIT 1
    ''', params)
    row = cur.fetchone()
    return row[0] if row else None


# ==============================================================================
# Wrapped helpers
# ==============================================================================

def _heatmap(cur, year_str):
    cur.execute('''
        SELECT DATE(ts) AS day, SUM(ms_played)/60000 AS minutes, COUNT(*) AS plays
        FROM plays WHERE ts IS NOT NULL AND substr(ts,1,4)=?
        GROUP BY day ORDER BY day
    ''', (year_str,))
    return [{"date": d, "minutes": int(m), "plays": p} for d, m, p in cur.fetchall()]


def _streaks(heatmap_rows, year_int):
    dates = sorted(set(r["date"] for r in heatmap_rows))
    if not dates:
        return {"longest": 0, "active_days": 0}
    longest = cur_len = 1
    for i in range(1, len(dates)):
        gap = (date.fromisoformat(dates[i]) - date.fromisoformat(dates[i-1])).days
        cur_len = cur_len + 1 if gap == 1 else 1
        if cur_len > longest:
            longest = cur_len
    return {"longest": longest, "active_days": len(dates)}


def _most_active_day(heatmap_rows):
    if not heatmap_rows:
        return None
    return max(heatmap_rows, key=lambda r: r["minutes"])


def _monthly_trend(cur, year_str):
    cur.execute('''
        SELECT CAST(substr(ts,6,2) AS INTEGER) AS month,
               SUM(ms_played)/60000 AS minutes, COUNT(*) AS plays
        FROM plays WHERE ts IS NOT NULL AND substr(ts,1,4)=?
        GROUP BY month ORDER BY month
    ''', (year_str,))
    return [{"month": m, "minutes": int(min_), "plays": p} for m, min_, p in cur.fetchall()]


def _weekday_data(cur, year_str):
    cur.execute('''
        SELECT CAST(strftime('%w', ts) AS INTEGER) AS dow,
               SUM(ms_played)/60000 AS minutes, COUNT(*) AS plays
        FROM plays WHERE ts IS NOT NULL AND substr(ts,1,4)=?
        GROUP BY dow
    ''', (year_str,))
    labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    result = {d: {"minutes": 0, "plays": 0} for d in labels}
    for dow, m, p in cur.fetchall():
        result[labels[dow]] = {"minutes": int(m), "plays": p}
    return result


def _hourly_minutes(cur, year_str):
    cur.execute('''
        SELECT CAST(strftime('%H', ts) AS INTEGER) AS hour,
               SUM(ms_played)/60000 AS minutes
        FROM plays WHERE ts IS NOT NULL AND substr(ts,1,4)=?
        GROUP BY hour
    ''', (year_str,))
    result = [0] * 24
    for h, m in cur.fetchall():
        result[h] = int(m)
    return result


def _skip_stats(cur, year_str):
    cur.execute('''
        SELECT COUNT(*), COALESCE(SUM(skipped),0)
        FROM plays WHERE substr(ts,1,4)=?
    ''', (year_str,))
    total, n_skipped = cur.fetchone()
    skip_rate = round(n_skipped / total * 100, 1) if total > 0 else 0.0
    cur.execute('''
        SELECT track_name, artist_name, COUNT(*) AS n
        FROM plays WHERE skipped=1 AND substr(ts,1,4)=? AND track_name IS NOT NULL
        GROUP BY track_name, artist_name ORDER BY n DESC LIMIT 5
    ''', (year_str,))
    most_skipped = [{"track": t, "artist": a, "skips": n} for t, a, n in cur.fetchall()]
    return {"skip_rate": skip_rate, "most_skipped_tracks": most_skipped}


def _top_albums(cur, year_str):
    cur.execute('''
        SELECT album_name, artist_name, SUM(ms_played)/60000 AS minutes, COUNT(*) AS plays
        FROM plays WHERE album_name IS NOT NULL AND substr(ts,1,4)=?
        GROUP BY album_name, artist_name ORDER BY minutes DESC LIMIT 5
    ''', (year_str,))
    return [{"album": a, "artist": ar, "minutes": int(m), "plays": p}
            for a, ar, m, p in cur.fetchall()]


def _diversity(cur, year_str):
    cur.execute('''
        SELECT COUNT(DISTINCT artist_name), COUNT(DISTINCT track_name), COUNT(DISTINCT album_name)
        FROM plays WHERE substr(ts,1,4)=? AND track_name IS NOT NULL
    ''', (year_str,))
    artists, tracks, albums = cur.fetchone()
    return {"unique_artists": artists or 0, "unique_tracks": tracks or 0, "unique_albums": albums or 0}


def _platform_stats(cur, year_str):
    cur.execute('''
        SELECT platform, COUNT(*) AS plays
        FROM plays WHERE platform IS NOT NULL AND platform!='' AND substr(ts,1,4)=?
        GROUP BY platform ORDER BY plays DESC LIMIT 6
    ''', (year_str,))
    rows = cur.fetchall()
    total = sum(r[1] for r in rows)
    return [{"platform": p, "plays": c,
             "pct": round(c / total * 100, 1) if total > 0 else 0}
            for p, c in rows]


def _milestones(cur, year_str):
    cur.execute('''
        SELECT ts, track_name, artist_name FROM plays
        WHERE substr(ts,1,4)=? AND track_name IS NOT NULL ORDER BY ts ASC LIMIT 1
    ''', (year_str,))
    first = cur.fetchone()
    cur.execute('''
        SELECT ts, track_name, artist_name FROM plays
        WHERE substr(ts,1,4)=? AND track_name IS NOT NULL ORDER BY ts DESC LIMIT 1
    ''', (year_str,))
    last = cur.fetchone()
    cur.execute('''
        SELECT DATE(ts) AS day, track_name, artist_name, COUNT(*) AS cnt
        FROM plays WHERE substr(ts,1,4)=? AND track_name IS NOT NULL
        GROUP BY day, track_name, artist_name ORDER BY cnt DESC LIMIT 1
    ''', (year_str,))
    top_repeat = cur.fetchone()
    return {
        "first_track": {"ts": first[0], "track": first[1], "artist": first[2]} if first else None,
        "last_track": {"ts": last[0], "track": last[1], "artist": last[2]} if last else None,
        "top_daily_repeat": {"date": top_repeat[0], "track": top_repeat[1],
                             "artist": top_repeat[2], "count": top_repeat[3]}
                             if top_repeat else None,
    }


# ==============================================================================
# Analytics functions (used by both CLI and API)
# ==============================================================================

def get_wrapped(conn, year=None):
    """Returns a deterministic yearly summary for the most recent complete year (or a specific year)."""
    cur = conn.cursor()
    cur.execute('''
        SELECT substr(ts, 1, 4) AS year, COUNT(*) AS plays, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY year
        ORDER BY year
    ''')
    years = cur.fetchall()
    if not years:
        return {"error": "No data available"}
    year_data = {int(y): {"plays": p, "minutes": int(m)} for y, p, m in years}
    sorted_years = sorted(year_data)
    if len(sorted_years) >= 2:
        last, prev = sorted_years[-1], sorted_years[-2]
        if year_data[last]["minutes"] < 0.5 * year_data[prev]["minutes"]:
            sorted_years = sorted_years[:-1]
    if not sorted_years:
        return {"error": "No complete year available"}
    if year is None:
        target_year = sorted_years[-1]
    else:
        if int(year) not in sorted_years:
            return {"error": f"Year {year} not found"}
        target_year = int(year)
    stats = year_data[target_year]
    cur.execute('''
        SELECT artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE artist_name IS NOT NULL AND substr(ts, 1, 4) = ?
        GROUP BY artist_name
        ORDER BY minutes DESC
        LIMIT 5
    ''', (str(target_year),))
    top_artists = cur.fetchall()
    cur.execute('''
        SELECT track_name, artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE track_name IS NOT NULL AND artist_name IS NOT NULL AND substr(ts, 1, 4) = ?
        GROUP BY track_name, artist_name
        ORDER BY minutes DESC
        LIMIT 5
    ''', (str(target_year),))
    top_tracks = cur.fetchall()
    cur.execute('''
        SELECT substr(ts, 6, 2) AS month, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL AND substr(ts, 1, 4) = ?
        GROUP BY month
        ORDER BY minutes DESC
        LIMIT 1
    ''', (str(target_year),))
    peak_month = cur.fetchone()
    cur.execute('''
        SELECT CAST(strftime('%H', ts) AS INTEGER) AS hour, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL AND substr(ts, 1, 4) = ?
        GROUP BY hour
        ORDER BY minutes DESC
        LIMIT 1
    ''', (str(target_year),))
    peak_hour = cur.fetchone()
    cur.execute('''
        SELECT CAST(strftime('%H', ts) AS INTEGER) AS hour, SUM(ms_played) / 60000.0 AS minutes
        FROM plays
        WHERE ts IS NOT NULL AND substr(ts, 1, 4) = ?
        GROUP BY hour
    ''', (str(target_year),))
    hour_data = cur.fetchall()
    buckets = [(0, 6, "night"), (6, 12, "morning"), (12, 18, "afternoon"), (18, 24, "evening")]
    bucket_labels = [b[2] for b in buckets]
    bucket_minutes = {label: 0 for label in bucket_labels}
    total_minutes = sum(minutes for _, minutes in hour_data)
    for hour, minutes in hour_data:
        for start, end, label in buckets:
            if start <= hour < end:
                bucket_minutes[label] += minutes
                break
    bucket_pct = {
        label: (bucket_minutes[label] / total_minutes * 100) if total_minutes > 0 else 0
        for label in bucket_labels
    }
    primary_label = max(bucket_labels, key=lambda l: bucket_pct[l]) if total_minutes > 0 else None
    year_str = str(target_year)
    heatmap_rows = _heatmap(cur, year_str)
    streak_info = _streaks(heatmap_rows, target_year)
    most_active = _most_active_day(heatmap_rows)
    monthly = _monthly_trend(cur, year_str)
    weekdays = _weekday_data(cur, year_str)
    hourly = _hourly_minutes(cur, year_str)
    skip_data = _skip_stats(cur, year_str)
    albums = _top_albums(cur, year_str)
    div_stats = _diversity(cur, year_str)
    platforms = _platform_stats(cur, year_str)
    milestones = _milestones(cur, year_str)
    return {
        "year": target_year,
        "available_years": sorted_years,
        "total_minutes": stats["minutes"],
        "total_plays": stats["plays"],
        "top_artists": [{"artist": a, "minutes": int(m)} for a, m in top_artists],
        "top_tracks": [{"track": t, "artist": a, "minutes": int(m)} for t, a, m in top_tracks],
        "top_albums": albums,
        "peak_month": peak_month[0] if peak_month else None,
        "peak_hour": peak_hour[0] if peak_hour else None,
        "hourly_minutes": hourly,
        "profile": {"bucket_pct": bucket_pct, "primary": primary_label},
        "monthly_trend": monthly,
        "heatmap": heatmap_rows,
        "weekdays": weekdays,
        "streaks": streak_info,
        "most_active_day": most_active,
        "skip_stats": skip_data,
        "diversity": div_stats,
        "platforms": platforms,
        "milestones": milestones,
    }


def get_yearly_trend(conn):
    """
    Returns yearly trend analysis:
      - yearly_changes, peak_year, lowest_year, trend, insights, trend_segments, flags, data_confidence
    """
    cur = conn.cursor()
    cur.execute('''
        SELECT substr(ts, 1, 4) AS year, COUNT(*) AS plays, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY year
        ORDER BY year
    ''')
    rows = cur.fetchall()
    if not rows:
        return {
            "yearly_changes": {},
            "peak_year": None,
            "lowest_year": None,
            "trend": "stable",
            "insights": ["No data available"],
        }
    year_data = {int(year): {"plays": plays, "minutes": int(minutes)} for year, plays, minutes in rows}
    max_minutes = max(y["minutes"] for y in year_data.values())
    sorted_years = sorted(year_data)
    partial_year = None
    if len(sorted_years) >= 2:
        last, prev = sorted_years[-1], sorted_years[-2]
        if year_data[last]["minutes"] < 0.5 * year_data[prev]["minutes"]:
            partial_year = last
            year_data[last]["partial"] = True
    filtered = {
        y: d for y, d in year_data.items()
        if d["minutes"] >= max_minutes * 0.05 and not d.get("partial")
    }
    if len(filtered) < 2:
        peak_year = max(year_data, key=lambda y: year_data[y]["minutes"])
        lowest_year = min(year_data, key=lambda y: year_data[y]["minutes"])
        return {
            "yearly_changes": {
                y: {**d, **({"partial": True} if d.get("partial") else {})}
                for y, d in year_data.items()
            },
            "peak_year": peak_year,
            "lowest_year": lowest_year,
            "trend": "stable",
            "insights": ["Not enough data for trend analysis"],
            "trend_segments": {},
            "flags": [],
            "data_confidence": "medium" if partial_year else "high",
        }
    all_years = sorted(year_data)
    yearly_changes = {}
    low_signal_flags = {}
    for idx, y in enumerate(all_years):
        minutes = year_data[y]["minutes"]
        if idx == 0:
            entry = {"change_pct": None, "change_minutes": None, "baseline": True}
            if year_data[y].get("partial"):
                entry["partial"] = True
            yearly_changes[y] = entry
        else:
            prev_y = all_years[idx - 1]
            prev_min = year_data[prev_y]["minutes"]
            low_signal = prev_min < 500
            change = minutes - prev_min
            pct = None if low_signal else (change / prev_min * 100 if prev_min else None)
            entry = {
                "change_pct": None if low_signal else (round(pct, 1) if pct is not None else None),
                "change_minutes": change,
            }
            if year_data[y].get("partial"):
                entry["partial"] = True
            if low_signal:
                entry["low_signal_baseline"] = True
                low_signal_flags[y] = True
            yearly_changes[y] = entry
    years = [
        y for y in sorted(filtered)
        if not (yearly_changes[y].get("low_signal_baseline") or yearly_changes[y].get("baseline"))
    ]
    stable_years = [
        y for y in sorted(filtered)
        if not (
            yearly_changes[y].get("low_signal_baseline")
            or yearly_changes[y].get("baseline")
            or yearly_changes[y].get("partial")
        )
    ]
    peak_year = max(filtered, key=lambda y: filtered[y]["minutes"])
    lowest_year = min(filtered, key=lambda y: filtered[y]["minutes"])
    peak_idx = stable_years.index(peak_year) if peak_year in stable_years else 0
    decline_start, decline_end = None, None
    for i in range(peak_idx + 1, len(stable_years)):
        y = stable_years[i]
        prev_y = stable_years[i - 1]
        chg = filtered[y]["minutes"] - filtered[prev_y]["minutes"]
        if chg < 0 and decline_start is None:
            decline_start = prev_y
            decline_end = y
        elif chg < 0:
            decline_end = y
        elif chg >= 0 and decline_start is not None:
            break
    recovery_start = None
    if decline_end:
        for i in range(stable_years.index(decline_end) + 1, len(stable_years)):
            y = stable_years[i]
            prev_y = stable_years[i - 1]
            chg = filtered[y]["minutes"] - filtered[prev_y]["minutes"]
            if chg > 0:
                recovery_start = y
                break
    trend_segments = {}
    if peak_idx > 0 and len(stable_years) > 0:
        trend_segments["growth"] = f"{stable_years[0]}–{peak_year}"
    if decline_start and decline_end:
        trend_segments["decline"] = f"{decline_start}–{decline_end}"
    if recovery_start:
        trend_segments["recovery"] = f"{recovery_start}–{stable_years[-1]}"
    changes = [
        filtered[years[i]]["minutes"] - filtered[years[i - 1]]["minutes"]
        for i in range(1, len(years))
    ]
    if all(c > 0 for c in changes):
        trend = "increasing"
    elif all(c < 0 for c in changes):
        trend = "decreasing"
    elif all(abs(c) < max_minutes * 0.05 for c in changes):
        trend = "stable"
    else:
        trend = "volatile"
    flags = []
    data_confidence = "high"
    possible_platform_switch = False
    for i in range(1, len(years)):
        y = years[i]
        prev_y = years[i - 1]
        prev_min = filtered[prev_y]["minutes"]
        chg = filtered[y]["minutes"] - prev_min
        if chg < 0 and abs(chg) > 0.5 * prev_min and recovery_start:
            possible_platform_switch = True
            break
    if possible_platform_switch:
        flags.append("possible_platform_switch")
        data_confidence = "medium"
    elif len(years) < 3:
        data_confidence = "medium"
    insights = []
    if peak_year is not None:
        insights.append(f"Listening peaked in {peak_year}")
    if decline_start and decline_end:
        insights.append(f"Sharp decline between {decline_start}–{decline_end}")
    if recovery_start:
        insights.append(f"Strong recovery from {recovery_start} onwards")
    if lowest_year is not None and lowest_year != peak_year:
        insights.append(f"Lowest listening in {lowest_year}")
    return {
        "yearly_changes": {
            y: {**yearly_changes.get(y, {}), **({"partial": True} if year_data[y].get("partial") else {})}
            for y in all_years
        },
        "peak_year": peak_year,
        "lowest_year": lowest_year,
        "trend": trend,
        "insights": insights,
        "trend_segments": trend_segments,
        "flags": flags,
        "data_confidence": data_confidence,
    }
