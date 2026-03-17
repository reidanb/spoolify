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
import sys
import os
from db import get_connection, init_db
from importer import import_file
from queries import print_top_artists

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {os.path.basename(sys.argv[0])} <spotify_json_file> [--top-artists]")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        sys.exit(1)
    conn = get_connection()
    init_db(conn)
    import_file(conn, path)
    if len(sys.argv) > 2 and sys.argv[2] == "--top-artists":
        print_top_artists(conn)
    conn.close()

if __name__ == "__main__":
    main()