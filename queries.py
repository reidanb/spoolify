import json

def get_wrapped(conn, year=None):
    """
    Returns a deterministic yearly summary for the most recent complete year (or a specific year if provided).
    Composes from existing stats, profile, and trend logic. No new analytics.
    """
    # Get yearly stats
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
    # Exclude partial years (last year with much lower minutes than previous)
    year_data = {int(y): {"plays": p, "minutes": int(m)} for y, p, m in years}
    sorted_years = sorted(year_data)
    if len(sorted_years) >= 2:
        last, prev = sorted_years[-1], sorted_years[-2]
        if year_data[last]["minutes"] < 0.5 * year_data[prev]["minutes"]:
            sorted_years = sorted_years[:-1]
    if not sorted_years:
        return {"error": "No complete year available"}
    # Pick year
    if year is None:
        target_year = sorted_years[-1]
    else:
        if int(year) not in sorted_years:
            return {"error": f"Year {year} not found"}
        target_year = int(year)
    # Get stats for target year
    stats = year_data[target_year]
    # Top artists
    cur.execute('''
        SELECT artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE artist_name IS NOT NULL AND substr(ts, 1, 4) = ?
        GROUP BY artist_name
        ORDER BY minutes DESC
        LIMIT 5
    ''', (str(target_year),))
    top_artists = cur.fetchall()
    # Top tracks
    cur.execute('''
        SELECT track_name, artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE track_name IS NOT NULL AND artist_name IS NOT NULL AND substr(ts, 1, 4) = ?
        GROUP BY track_name, artist_name
        ORDER BY minutes DESC
        LIMIT 5
    ''', (str(target_year),))
    top_tracks = cur.fetchall()
    # Peak month
    cur.execute('''
        SELECT substr(ts, 6, 2) AS month, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL AND substr(ts, 1, 4) = ?
        GROUP BY month
        ORDER BY minutes DESC
        LIMIT 1
    ''', (str(target_year),))
    peak_month = cur.fetchone()
    # Peak hour
    cur.execute('''
        SELECT CAST(strftime('%H', ts) AS INTEGER) AS hour, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL AND substr(ts, 1, 4) = ?
        GROUP BY hour
        ORDER BY minutes DESC
        LIMIT 1
    ''', (str(target_year),))
    peak_hour = cur.fetchone()
    # Compose profile for year
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
    bucket_pct = {label: (bucket_minutes[label] / total_minutes * 100) if total_minutes > 0 else 0 for label in bucket_labels}
    primary_label = max(bucket_labels, key=lambda l: bucket_pct[l]) if total_minutes > 0 else None
    # Compose output
    return {
        "year": target_year,
        "total_minutes": stats["minutes"],
        "total_plays": stats["plays"],
        "top_artists": [{"artist": a, "minutes": int(m)} for a, m in top_artists],
        "top_tracks": [{"track": t, "artist": a, "minutes": int(m)} for t, a, m in top_tracks],
        "peak_month": peak_month[0] if peak_month else None,
        "peak_hour": peak_hour[0] if peak_hour else None,
        "profile": {
            "bucket_pct": bucket_pct,
            "primary": primary_label
        }
    }
def get_yearly_trend(conn):
    """
    Returns a dict with:
      - yearly_changes: {year: {change_pct, change_minutes}}
      - peak_year, lowest_year
      - trend: increasing/decreasing/volatile/stable
      - insights: [str]
    Uses minutes as primary metric. Deterministic, no printing.
    """
    cur = conn.cursor()
    cur.execute('''
        SELECT substr(ts, 1, 4) AS year, COUNT(*) AS plays, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY year
        ORDER BY year
    ''')
    rows = cur.fetchall()  # [(year, plays, minutes), ...]
    # Filter out years with very low minutes (e.g. <5% of max year)
    if not rows:
        return {
            "yearly_changes": {},
            "peak_year": None,
            "lowest_year": None,
            "trend": "stable",
            "insights": ["No data available"]
        }
    year_data = {int(year): {"plays": plays, "minutes": int(minutes)} for year, plays, minutes in rows}
    max_minutes = max(y["minutes"] for y in year_data.values())
    # Detect partial (incomplete) year: last year with much lower minutes than previous
    sorted_years = sorted(year_data)
    partial_year = None
    if len(sorted_years) >= 2:
        last, prev = sorted_years[-1], sorted_years[-2]
        last_min, prev_min = year_data[last]["minutes"], year_data[prev]["minutes"]
        if last_min < 0.5 * prev_min:
            partial_year = last
            year_data[last]["partial"] = True
    # Remove years with <5% of max minutes (likely partial years)
    filtered = {y: d for y, d in year_data.items() if d["minutes"] >= max_minutes * 0.05 and not d.get("partial")}
    if len(filtered) < 2:
        peak_year = max(year_data, key=lambda y: year_data[y]["minutes"])
        lowest_year = min(year_data, key=lambda y: year_data[y]["minutes"])
        return {
            "yearly_changes": {y: {**d, **({"partial": True} if d.get("partial") else {})} for y, d in year_data.items()},
            "peak_year": peak_year,
            "lowest_year": lowest_year,
            "trend": "stable",
            "insights": ["Not enough data for trend analysis"],
            "trend_segments": {},
            "flags": [],
            "data_confidence": "medium" if partial_year else "high"
        }
    # Calculate year-over-year changes (all years, including partial)
    all_years = sorted(year_data)
    yearly_changes = {}
    prev_minutes = None
    low_signal_flags = {}
    for idx, y in enumerate(all_years):
        minutes = year_data[y]["minutes"]
        if idx == 0:
            # Baseline year
            entry = {"change_pct": None, "change_minutes": None, "baseline": True}
            if year_data[y].get("partial"):
                entry["partial"] = True
            yearly_changes[y] = entry
        else:
            prev_y = all_years[idx-1]
            prev_min = year_data[prev_y]["minutes"]
            # Low-signal baseline detection
            low_signal = prev_min < 500
            change = minutes - prev_min
            pct = None if low_signal else (change / prev_min * 100 if prev_min else None)
            entry = {"change_pct": None if low_signal else round(pct, 1) if pct is not None else None,
                     "change_minutes": change}
            if year_data[y].get("partial"):
                entry["partial"] = True
            if low_signal:
                entry["low_signal_baseline"] = True
                low_signal_flags[y] = True
            yearly_changes[y] = entry
    # Only use non-partial, non-low-signal years for trend/insight/segment analysis
    years = [y for y in sorted(filtered) if not (yearly_changes[y].get("low_signal_baseline") or yearly_changes[y].get("baseline"))]
    # Find first stable year (not low-signal, not baseline, not partial)
    stable_years = [y for y in sorted(filtered) if not (yearly_changes[y].get("low_signal_baseline") or yearly_changes[y].get("baseline") or yearly_changes[y].get("partial"))]
    # Find peak year (highest minutes, non-partial)
    peak_year = max(filtered, key=lambda y: filtered[y]["minutes"])
    lowest_year = min(filtered, key=lambda y: filtered[y]["minutes"])
    # Decline/recovery detection (deterministic)
    # 1. Find peak
    peak_idx = stable_years.index(peak_year) if peak_year in stable_years else 0
    # 2. Decline: first year after peak with negative change
    decline_start, decline_end = None, None
    for i in range(peak_idx+1, len(stable_years)):
        y = stable_years[i]
        prev_y = stable_years[i-1]
        chg = filtered[y]["minutes"] - filtered[prev_y]["minutes"]
        if chg < 0 and decline_start is None:
            decline_start = prev_y
            decline_end = y
        elif chg < 0:
            decline_end = y
        elif chg >= 0 and decline_start is not None:
            break
    # 3. Recovery: first year after decline with sustained positive change
    recovery_start = None
    if decline_end:
        for i in range(stable_years.index(decline_end)+1, len(stable_years)):
            y = stable_years[i]
            prev_y = stable_years[i-1]
            chg = filtered[y]["minutes"] - filtered[prev_y]["minutes"]
            if chg > 0:
                recovery_start = y
                break
    # Trend segments (exclude partial and noisy baseline)
    trend_segments = {}
    if peak_idx > 0 and len(stable_years) > 0:
        trend_segments["growth"] = f"{stable_years[0]}–{peak_year}"
    if decline_start and decline_end:
        trend_segments["decline"] = f"{decline_start}–{decline_end}"
    if recovery_start:
        trend_segments["recovery"] = f"{recovery_start}–{stable_years[-1]}"
    # Trend classification (non-partial years only)
    changes = [filtered[years[i]]["minutes"] - filtered[years[i-1]]["minutes"] for i in range(1, len(years))]
    if all(c > 0 for c in changes):
        trend = "increasing"
    elif all(c < 0 for c in changes):
        trend = "decreasing"
    elif all(abs(c) < max_minutes * 0.05 for c in changes):
        trend = "stable"
    else:
        trend = "volatile"
    # Platform switch detection (deterministic)
    flags = []
    data_confidence = "high"
    possible_platform_switch = False
    drop_year = None
    for i in range(1, len(years)):
        y = years[i]
        prev_y = years[i-1]
        prev_min = filtered[prev_y]["minutes"]
        chg = filtered[y]["minutes"] - prev_min
        if chg < 0 and abs(chg) > 0.5 * prev_min:
            # Only if recovery occurs later
            if recovery_start:
                possible_platform_switch = True
                drop_year = y
                break
    if possible_platform_switch:
        flags.append("possible_platform_switch")
        data_confidence = "medium"
    elif len(years) < 3:
        data_confidence = "medium"
    # Insights (precise, decoupled from flags)
    insights = []
    if peak_year is not None:
        insights.append(f"Listening peaked in {peak_year}")
    if decline_start and decline_end:
        insights.append(f"Sharp decline between {decline_start}–{decline_end}")
    if recovery_start:
        insights.append(f"Strong recovery from {recovery_start} onwards")
    if lowest_year is not None and lowest_year != peak_year:
        insights.append(f"Lowest listening in {lowest_year}")
    # Add possible platform switch as a flag, not in insight
    # Return
    return {
        "yearly_changes": {y: {**yearly_changes.get(y, {}), **({"partial": True} if year_data[y].get("partial") else {})} for y in all_years},
        "peak_year": peak_year,
        "lowest_year": lowest_year,
        "trend": trend,
        "insights": insights,
        "trend_segments": trend_segments,
        "flags": flags,
        "data_confidence": data_confidence,
    }
def get_listening_profile(conn):
    """
    Returns a dict with listening behaviour profile:
      - time-of-day buckets (night/morning/afternoon/evening)
      - % of total listening time per bucket
      - primary profile (highest % bucket)
      - confidence (high/moderate/low)
      - peak hour
      - skewed/balanced
      - very low night usage flag (<10%)
    """
    cur = conn.cursor()
    # Define buckets: (start_hour, end_hour, label)
    buckets = [
        (0, 6, "night"),      # 00:00–05:59
        (6, 12, "morning"),   # 06:00–11:59
        (12, 18, "afternoon"),# 12:00–17:59
        (18, 24, "evening"),  # 18:00–23:59
    ]
    bucket_labels = [b[2] for b in buckets]
    bucket_minutes = {label: 0 for label in bucket_labels}
    # Get minutes per hour
    cur.execute('''
        SELECT CAST(strftime('%H', ts) AS INTEGER) AS hour, SUM(ms_played) / 60000.0 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY hour
    ''')
    hour_data = cur.fetchall()  # [(hour, minutes), ...]
    total_minutes = sum(minutes for _, minutes in hour_data)
    # Assign to buckets
    for hour, minutes in hour_data:
        for start, end, label in buckets:
            if start <= hour < end:
                bucket_minutes[label] += minutes
                break
    # Calculate percentages
    bucket_pct = {label: (bucket_minutes[label] / total_minutes * 100) if total_minutes > 0 else 0 for label in bucket_labels}
    # Primary profile
    primary_label = max(bucket_labels, key=lambda l: bucket_pct[l])
    primary_pct = bucket_pct[primary_label]
    # Confidence
    if primary_pct > 40:
        confidence = "high"
    elif primary_pct >= 30:
        confidence = "moderate"
    else:
        confidence = "low"
    # Peak hour
    peak_hour = max(hour_data, key=lambda x: x[1])[0] if hour_data else None
    # Skewed or balanced
    sorted_pct = sorted(bucket_pct.values(), reverse=True)
    if sorted_pct[0] - sorted_pct[1] >= 15:
        skew = f"{primary_label}-heavy"
    else:
        skew = "balanced"
    # Very low night usage flag
    very_low_night = bucket_pct["night"] < 10

    return {
        "bucket_minutes": bucket_minutes,
        "bucket_pct": bucket_pct,
        "primary_profile": primary_label,
        "primary_pct": primary_pct,
        "confidence": confidence,
        "peak_hour": peak_hour,
        "skew": skew,
        "very_low_night": very_low_night,
        "total_minutes": total_minutes,
    }

def print_stats(conn):
    # Listening behaviour profile (summary)
    profile = get_listening_profile(conn)
    print("\nListening Behaviour Profile:")
    for label in ["night", "morning", "afternoon", "evening"]:
        pct = profile["bucket_pct"][label]
        print(f"  {label.title():<9}: {pct:.1f}% of listening time")
    print(f"Primary profile: {profile['primary_profile']} ({profile['primary_pct']:.1f}%)")
    print(f"Confidence: {profile['confidence']}")
    if profile['peak_hour'] is not None:
        print(f"Peak listening hour: {profile['peak_hour']:02d}:00–{profile['peak_hour']:02d}:59")
    print(f"Skew: {profile['skew']}")
    if profile['very_low_night']:
        print("Very low night usage (<10%)")
    cur = conn.cursor()

    # Top 10 artists
    cur.execute('''
        SELECT artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE artist_name IS NOT NULL
        GROUP BY artist_name
        ORDER BY minutes DESC
        LIMIT 10
    ''')
    top_artists = cur.fetchall()

    # Top 10 tracks
    cur.execute('''
        SELECT track_name, artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE track_name IS NOT NULL AND artist_name IS NOT NULL
        GROUP BY track_name, artist_name
        ORDER BY minutes DESC
        LIMIT 10
    ''')
    top_tracks = cur.fetchall()

    # Total listening time (minutes, hours)
    cur.execute('SELECT SUM(ms_played) FROM plays')
    total_ms = cur.fetchone()[0] or 0
    total_minutes = total_ms // 60000
    total_hours = total_minutes / 60

    # Total play count
    cur.execute('SELECT COUNT(*) FROM plays')
    play_count = cur.fetchone()[0]

    print("\n===== Spotify Listening Stats =====\n")
    print("Top 10 Artists (by listening time):")
    for idx, (artist, minutes) in enumerate(top_artists, 1):
        print(f"{idx}. {artist} - {int(minutes)} minutes")

    print("\nTop 10 Tracks (by listening time):")
    for idx, (track, artist, minutes) in enumerate(top_tracks, 1):
        print(f"{idx}. {track} by {artist} - {int(minutes)} minutes")

    print(f"\nTotal listening time: {total_minutes} minutes ({total_hours:.1f} hours)")
    print(f"Total play count: {play_count}")

    # Monthly listening stats (plays + minutes)
    print("\nMonthly Listening Stats:")
    cur.execute('''
        SELECT substr(ts, 1, 7) AS month, COUNT(*), SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY month
        ORDER BY month
    ''')
    monthly = cur.fetchall()
    for month, count, minutes in monthly:
        print(f"{month}: {count} plays, {int(minutes)} minutes")

    # Peak month (by minutes)
    if monthly:
        peak_month = max(monthly, key=lambda x: x[2])
        print(f"\nPeak Month: {peak_month[0]} - {int(peak_month[2])} minutes")

    # Yearly summary

    # Yearly summary
    print("\nYearly Listening Summary:")
    cur.execute('''
        SELECT substr(ts, 1, 4) AS year, COUNT(*), SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY year
        ORDER BY year
    ''')
    yearly = cur.fetchall()
    for year, count, minutes in yearly:
        print(f"{year}: {count} plays, {int(minutes)} minutes")

    # Peak year (by minutes)
    if yearly:
        peak_year = max(yearly, key=lambda x: x[2])
        print(f"\nPeak Year: {peak_year[0]} - {int(peak_year[2])} minutes")

    # Hour-of-day listening patterns (optional)
    print("\nHour-of-Day Listening Patterns:")
    cur.execute('''
        SELECT CAST(strftime('%H', ts) AS INTEGER) AS hour, COUNT(*), SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY hour
        ORDER BY hour
    ''')
    hourly = cur.fetchall()
    for hour, count, minutes in hourly:
        print(f"{hour:02d}:00 - {hour:02d}:59 - {count} plays, {int(minutes)} minutes")

    # Peak hour (by minutes)
    if hourly:
        peak_hour = max(hourly, key=lambda x: x[2])
        print(f"\nPeak Hour: {peak_hour[0]:02d}:00 - {peak_hour[0]:02d}:59 - {int(peak_hour[2])} minutes")
def print_top_artists(conn):
    """
    Queries the plays table, groups by artist_name, sums ms_played (converted to minutes),
    sorts descending, limits to top 10, ignores NULL artist names.
    Prints and returns the results.
    """
    cur = conn.cursor()
    cur.execute('''
        SELECT artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE artist_name IS NOT NULL
        GROUP BY artist_name
        ORDER BY minutes DESC
        LIMIT 10
    ''')
    results = cur.fetchall()
    print("Top Artists:")
    for idx, (artist, minutes) in enumerate(results, 1):
        print(f"{idx}. {artist} - {int(minutes)} minutes")
    return results

def print_top_tracks(conn):
    """
    Queries the plays table, groups by track_name and artist_name, 
    sums ms_played (converted to minutes), sorts descending, limits to top 10.
    """
    cur = conn.cursor()
    cur.execute('''
        SELECT track_name, artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE track_name IS NOT NULL AND artist_name IS NOT NULL
        GROUP BY track_name, artist_name
        ORDER BY minutes DESC
        LIMIT 10
    ''')
    results = cur.fetchall()
    print("Top Tracks:")
    for idx, (track, artist, minutes) in enumerate(results, 1):
        print(f"{idx}. {track} by {artist} - {int(minutes)} minutes")
    return results

def print_monthly(conn):
    """
    Prints monthly listening stats (plays + minutes).
    """
    cur = conn.cursor()
    cur.execute('''
        SELECT substr(ts, 1, 7) AS month, COUNT(*), SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY month
        ORDER BY month
    ''')
    results = cur.fetchall()
    print("Monthly Listening Stats:")
    for month, count, minutes in results:
        print(f"{month}: {count} plays, {int(minutes)} minutes")
    
    # Show peak month
    if results:
        peak = max(results, key=lambda x: x[2])
        print(f"\nPeak Month: {peak[0]} - {int(peak[2])} minutes")
    return results

def print_yearly(conn):
    """
    Prints yearly listening stats (plays + minutes).
    """
    cur = conn.cursor()
    cur.execute('''
        SELECT substr(ts, 1, 4) AS year, COUNT(*), SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY year
        ORDER BY year
    ''')
    results = cur.fetchall()
    print("Yearly Listening Summary:")
    for year, count, minutes in results:
        print(f"{year}: {count} plays, {int(minutes)} minutes")
    
    # Show peak year
    if results:
        peak = max(results, key=lambda x: x[2])
        print(f"\nPeak Year: {peak[0]} - {int(peak[2])} minutes")
    return results

def print_hourly(conn):
    """
    Prints hour-of-day listening patterns (plays + minutes for each hour).
    """
    cur = conn.cursor()
    cur.execute('''
        SELECT CAST(strftime('%H', ts) AS INTEGER) AS hour, COUNT(*), SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE ts IS NOT NULL
        GROUP BY hour
        ORDER BY hour
    ''')
    results = cur.fetchall()
    print("Hour-of-Day Listening Patterns:")
    for hour, count, minutes in results:
        print(f"{hour:02d}:00 - {hour:02d}:59 - {count} plays, {int(minutes)} minutes")
    
    # Show peak hour
    if results:
        peak = max(results, key=lambda x: x[2])
        print(f"\nPeak Hour: {peak[0]:02d}:00 - {peak[0]:02d}:59 - {int(peak[2])} minutes")
    return results

def print_insights(conn):
    """
    Prints insights from trend analysis.
    """
    trend = get_yearly_trend(conn)
    print("Listening Insights:")
    if "insights" in trend and trend["insights"]:
        for idx, insight in enumerate(trend["insights"], 1):
            print(f"{idx}. {insight}")
    
    if "trend_segments" in trend and trend["trend_segments"]:
        print("\nTrend Segments:")
        for segment_type, period in trend["trend_segments"].items():
            print(f"  {segment_type.capitalize()}: {period}")
    
    if "trend" in trend:
        print(f"\nOverall Trend: {trend['trend'].capitalize()}")
    
    if "data_confidence" in trend:
        print(f"Data Confidence: {trend['data_confidence'].capitalize()}")
    
    if "flags" in trend and trend["flags"]:
        print("\nFlags:")
        for flag in trend["flags"]:
            print(f"  • {flag}")
    
    return trend
