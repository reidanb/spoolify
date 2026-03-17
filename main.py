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
from queries import print_top_artists, print_stats

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {os.path.basename(sys.argv[0])} <spotify_json_file> [--top-artists]\n       or: {os.path.basename(sys.argv[0])} --top-artists")
        sys.exit(1)


    # If only --top-artists or --stats is supplied
    if sys.argv[1] == "--top-artists":
        conn = get_connection()
        init_db(conn)
        print_top_artists(conn)
        conn.close()
        return
    if sys.argv[1] == "--stats":
        conn = get_connection()
        init_db(conn)
        print_stats(conn)
        conn.close()
        return

    path = sys.argv[1]
    if not (os.path.isfile(path) or os.path.isdir(path)):
        print(f"File or directory not found: {path}")
        sys.exit(1)

    conn = get_connection()
    init_db(conn)

    if os.path.isdir(path):
        json_files = [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith('.json')]
        if not json_files:
            print(f"No JSON files found in directory: {path}")
            conn.close()
            sys.exit(1)
        for json_file in json_files:
            print(f"Importing {json_file}...")
            import_file(conn, json_file)
    else:
        import_file(conn, path)

    if len(sys.argv) > 2:
        if sys.argv[2] == "--top-artists":
            print_top_artists(conn)
        elif sys.argv[2] == "--stats":
            print_stats(conn)
    conn.close()

if __name__ == "__main__":
    main()