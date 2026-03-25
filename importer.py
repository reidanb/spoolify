import json
import hashlib

def generate_hash(entry):
    ts = entry.get("ts", "")
    track_uri = entry.get("spotify_track_uri", "")
    ms_played = str(entry.get("ms_played", ""))
    key = ts + track_uri + ms_played
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def import_file_stats(conn, path):
    """Import one Spotify JSON file and return insertion statistics."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    to_insert = []
    skipped_missing_track_uri = 0
    for entry in data:
        track_uri = entry.get("spotify_track_uri")
        if not track_uri:
            skipped_missing_track_uri += 1
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
    return {
        "inserted": inserted,
        "duplicates": duplicates,
        "total_rows": total_after,
        "attempted": total_attempted,
        "skipped_missing_track_uri": skipped_missing_track_uri
    }

def import_file(conn, path):
    stats = import_file_stats(conn, path)
    print(f"Inserted: {stats['inserted']}")
    print(f"Duplicates skipped: {stats['duplicates']}")
    print(f"Total rows in database: {stats['total_rows']}")
