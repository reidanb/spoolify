
import sqlite3
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional, fallback to os.environ only

DB_FILE = os.environ.get("SPOOLIFY_DB_FILE", "spoolify.db")

def get_connection():
    """Returns a new SQLite connection to the database file."""
    return sqlite3.connect(DB_FILE)

def init_db(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS plays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        track_uri TEXT,
        track_name TEXT,
        artist_name TEXT,
        album_name TEXT,
        ms_played INTEGER,
        platform TEXT,
        skipped INTEGER,
        hash TEXT UNIQUE
    )
    """)
    # Add indexes for performance
    conn.execute("CREATE INDEX IF NOT EXISTS idx_artist ON plays(artist_name);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_track ON plays(track_name);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON plays(ts);")
