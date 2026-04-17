"""
Data retrieval functions (return data, no printing).
These are reused by both CLI and API layers.
"""


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
