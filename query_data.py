"""
Data retrieval functions (return data, no printing).
These are reused by both CLI and API layers.
"""

import re

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
    from queries import get_listening_profile
    return get_listening_profile(conn)


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
