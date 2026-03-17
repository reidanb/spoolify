def print_stats(conn):
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
        print(f"{idx}. {artist} — {int(minutes)} minutes")

    print("\nTop 10 Tracks (by listening time):")
    for idx, (track, artist, minutes) in enumerate(top_tracks, 1):
        print(f"{idx}. {track} by {artist} — {int(minutes)} minutes")

    print(f"\nTotal listening time: {total_minutes} minutes ({total_hours:.1f} hours)")
    print(f"Total play count: {play_count}")
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
        print(f"{idx}. {artist} — {int(minutes)} minutes")
    return results
