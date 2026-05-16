
import re
import sqlite3
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATA_DIR = os.environ.get("SPOOLIFY_DATA_DIR", "data")

_USERNAME_RE = re.compile(r'^[a-zA-Z0-9_.\-]{1,64}$')


def _safe_username(username: str) -> str:
    if not _USERNAME_RE.match(username):
        raise ValueError(f"Invalid username: {username!r}")
    return username


def get_db_path(username: str) -> str:
    safe = _safe_username(username)
    user_dir = os.path.join(DATA_DIR, safe)
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, "spoolify.db")


def get_connection(username: str):
    return sqlite3.connect(get_db_path(username))


def list_users() -> list:
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted(
        d for d in os.listdir(DATA_DIR)
        if os.path.isfile(os.path.join(DATA_DIR, d, "spoolify.db"))
    )


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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_artist ON plays(artist_name);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_track ON plays(track_name);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON plays(ts);")
