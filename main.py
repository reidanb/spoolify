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
from queries import print_top_artists, print_stats, get_yearly_trend

def main():
    if sys.argv[1] == "--trends":
        conn = get_connection()
        init_db(conn)
        trend = get_yearly_trend(conn)
        import json
        print(json.dumps(trend, indent=2))
        conn.close()
        return

    if sys.argv[1] == "wrapped":
        import json
        conn = get_connection()
        init_db(conn)
        year = None
        as_json = False
        # Parse options
        args = sys.argv[2:]
        if "--json" in args:
            as_json = True
            args.remove("--json")
        if len(args) >= 2 and args[0] == "--year":
            year = args[1]
        result = None
        from queries import get_wrapped
        result = get_wrapped(conn, year)
        if as_json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            if "error" in result:
                print(f"Error: {result['error']}")
            else:
                print(f"===== Wrapped Summary for {result['year']} =====")
                print(f"Total listening time: {result['total_minutes']} minutes")
                print(f"Total plays: {result['total_plays']}")
                print("\nTop Artists:")
                for idx, a in enumerate(result['top_artists'], 1):
                    print(f"  {idx}. {a['artist']} — {a['minutes']} minutes")
                print("\nTop Tracks:")
                for idx, t in enumerate(result['top_tracks'], 1):
                    print(f"  {idx}. {t['track']} by {t['artist']} — {t['minutes']} minutes")
                if result['peak_month']:
                    print(f"\nPeak Month: {result['peak_month']}")
                if result['peak_hour'] is not None:
                    print(f"Peak Hour: {result['peak_hour']:02d}:00–{result['peak_hour']:02d}:59")
                print("\nListening Profile:")
                for label, pct in result['profile']['bucket_pct'].items():
                    print(f"  {label.title():<9}: {pct:.1f}% of listening time")
                print(f"Primary profile: {result['profile']['primary']}")
        conn.close()
        return
    if len(sys.argv) < 2:
        print(f"Usage: {os.path.basename(sys.argv[0])} import <spotify_json_file_or_dir>\n       or: {os.path.basename(sys.argv[0])} --top-artists\n       or: {os.path.basename(sys.argv[0])} --stats")
        sys.exit(1)

    if sys.argv[1] == "import":
        if len(sys.argv) < 3:
            print(f"Usage: {os.path.basename(sys.argv[0])} import <spotify_json_file_or_dir>")
            sys.exit(1)
        path = sys.argv[2]
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
        conn.close()
        return

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

    # If not a recognized command, print help and exit
    print(f"Usage: {os.path.basename(sys.argv[0])} import <spotify_json_file_or_dir>\n       or: {os.path.basename(sys.argv[0])} --top-artists\n       or: {os.path.basename(sys.argv[0])} --stats")
    sys.exit(1)


if __name__ == "__main__":
    main()