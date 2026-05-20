from query_data import get_listening_profile_data, get_yearly_trend


def print_stats(conn):
    profile = get_listening_profile_data(conn)
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

    cur.execute('''
        SELECT artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE artist_name IS NOT NULL
        GROUP BY artist_name
        ORDER BY minutes DESC
        LIMIT 10
    ''')
    top_artists = cur.fetchall()

    cur.execute('''
        SELECT track_name, artist_name, SUM(ms_played) / 60000 AS minutes
        FROM plays
        WHERE track_name IS NOT NULL AND artist_name IS NOT NULL
        GROUP BY track_name, artist_name
        ORDER BY minutes DESC
        LIMIT 10
    ''')
    top_tracks = cur.fetchall()

    cur.execute('SELECT SUM(ms_played) FROM plays')
    total_ms = cur.fetchone()[0] or 0
    total_minutes = total_ms // 60000
    total_hours = total_minutes / 60

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

    if monthly:
        peak_month = max(monthly, key=lambda x: x[2])
        print(f"\nPeak Month: {peak_month[0]} - {int(peak_month[2])} minutes")

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

    if yearly:
        peak_year = max(yearly, key=lambda x: x[2])
        print(f"\nPeak Year: {peak_year[0]} - {int(peak_year[2])} minutes")

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

    if hourly:
        peak_hour = max(hourly, key=lambda x: x[2])
        print(f"\nPeak Hour: {peak_hour[0]:02d}:00 - {peak_hour[0]:02d}:59 - {int(peak_hour[2])} minutes")


def print_top_artists(conn):
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
    if results:
        peak = max(results, key=lambda x: x[2])
        print(f"\nPeak Month: {peak[0]} - {int(peak[2])} minutes")
    return results


def print_yearly(conn):
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
    if results:
        peak = max(results, key=lambda x: x[2])
        print(f"\nPeak Year: {peak[0]} - {int(peak[2])} minutes")
    return results


def print_hourly(conn):
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
    if results:
        peak = max(results, key=lambda x: x[2])
        print(f"\nPeak Hour: {peak[0]:02d}:00 - {peak[0]:02d}:59 - {int(peak[2])} minutes")
    return results


def print_insights(conn):
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
