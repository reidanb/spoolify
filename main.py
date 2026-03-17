import sys
import json
import sqlite3
import hashlib
import os

DB_FILE = "spoolify.db"

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

def generate_hash(entry):
    ts = entry.get("ts", "")
    track_uri = entry.get("spotify_track_uri", "")
    ms_played = str(entry.get("ms_played", ""))
    key = ts + track_uri + ms_played
    return hashlib.sha256(key.encode("utf-8")).hexdigest()

def import_file(conn, path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    to_insert = []
    for entry in data:
        track_uri = entry.get("spotify_track_uri")
        if not track_uri:
            continue  # Ignore entries without spotify_track_uri
        # Data cleanup
        ms_played = entry.get("ms_played")
        try:
            ms_played = int(ms_played) if ms_played is not None else 0
        except Exception:
            ms_played = 0
        skipped = entry.get("skipped", False)
        skipped = 1 if skipped in (1, True, "1", "true", "True") else 0
        row = (
            entry.get("ts"),
            track_uri,
            entry.get("master_metadata_track_name"),
            entry.get("master_metadata_album_artist_name"),
            entry.get("master_metadata_album_album_name"),
            ms_played,
            entry.get("platform"),
            skipped,
            generate_hash(entry)
        )
        to_insert.append(row)
    total_attempted = len(to_insert)
    with conn:
        cur = conn.cursor()
        total_before = cur.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
        cur.executemany("""
            INSERT OR IGNORE INTO plays
            (ts, track_uri, track_name, artist_name, album_name, ms_played, platform, skipped, hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, to_insert)
        total_after = cur.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
        inserted = total_after - total_before
        duplicates = total_attempted - inserted
        print(f"Inserted: {inserted}")
        print(f"Duplicates skipped: {duplicates}")
        print(f"Total rows in database: {total_after}")

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {os.path.basename(sys.argv[0])} <spotify_json_file>")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        sys.exit(1)
    conn = sqlite3.connect(DB_FILE)
    init_db(conn)
    import_file(conn, path)
    conn.close()

if __name__ == "__main__":
    main()