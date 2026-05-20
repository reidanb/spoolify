import sys
import os
from db import get_connection, init_db
from importer import import_file
from queries import (
    print_top_artists, print_top_tracks, print_monthly, print_yearly,
    print_hourly, print_insights, print_stats,
)
from query_data import get_yearly_trend, get_wrapped

def print_usage():
    exe = os.path.basename(sys.argv[0])
    print(f"""Usage:
  {exe} --user <username> import <path>     Import Spotify JSON file or directory
  {exe} --user <username> stats             Show overall statistics
  {exe} --user <username> top-artists       Show top 10 artists by listening time
  {exe} --user <username> top-tracks        Show top 10 tracks by listening time
  {exe} --user <username> monthly           Show monthly listening stats
  {exe} --user <username> yearly            Show yearly listening stats
  {exe} --user <username> hourly            Show hour-of-day listening patterns
  {exe} --user <username> trends            Show yearly trend analysis (JSON format)
  {exe} --user <username> insights          Show listening insights and trends
  {exe} --user <username> wrapped [--year <year>] [--json]

  Set SPOOLIFY_USER to avoid passing --user every time.""")

def _resolve_user(args: list) -> tuple:
    """Extract --user from args list, falling back to SPOOLIFY_USER env var."""
    username = os.environ.get("SPOOLIFY_USER", "").strip()
    if "--user" in args:
        idx = args.index("--user")
        if idx + 1 >= len(args):
            print("Error: --user requires a username argument")
            sys.exit(1)
        username = args[idx + 1]
        args = args[:idx] + args[idx + 2:]
    if not username:
        print("Error: username required. Use --user <username> or set SPOOLIFY_USER.")
        sys.exit(1)
    return username, args


def main():
    args = sys.argv[1:]

    if not args:
        print_usage()
        sys.exit(1)

    username, args = _resolve_user(args)

    if not args:
        print_usage()
        sys.exit(1)

    command = args[0]

    # Import command
    if command == "import":
        if len(args) < 2:
            print(f"Usage: {os.path.basename(sys.argv[0])} --user <username> import <spotify_json_file_or_dir>")
            sys.exit(1)
        path = args[1]
        if not (os.path.isfile(path) or os.path.isdir(path)):
            print(f"File or directory not found: {path}")
            sys.exit(1)
        conn = get_connection(username)
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

    # All other commands require database connection
    conn = get_connection(username)
    init_db(conn)

    try:
        if command == "stats":
            print_stats(conn)

        elif command == "top-artists":
            print_top_artists(conn)

        elif command == "top-tracks":
            print_top_tracks(conn)

        elif command == "monthly":
            print_monthly(conn)

        elif command == "yearly":
            print_yearly(conn)

        elif command == "hourly":
            print_hourly(conn)

        elif command == "trends":
            trend = get_yearly_trend(conn)
            import json
            print(json.dumps(trend, indent=2))

        elif command == "insights":
            print_insights(conn)

        elif command == "wrapped":
            import json
            year = None
            as_json = False

            wrapped_args = args[1:]
            if "--json" in wrapped_args:
                as_json = True
                wrapped_args.remove("--json")
            if len(wrapped_args) >= 2 and wrapped_args[0] == "--year":
                year = wrapped_args[1]

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
                        print(f"  {idx}. {a['artist']} - {a['minutes']} minutes")
                    print("\nTop Tracks:")
                    for idx, t in enumerate(result['top_tracks'], 1):
                        print(f"  {idx}. {t['track']} by {t['artist']} - {t['minutes']} minutes")
                    if result['peak_month']:
                        print(f"\nPeak Month: {result['peak_month']}")
                    if result['peak_hour'] is not None:
                        print(f"Peak Hour: {result['peak_hour']:02d}:00-{result['peak_hour']:02d}:59")
                    print("\nListening Profile:")
                    for label, pct in result['profile']['bucket_pct'].items():
                        print(f"  {label.title():<9}: {pct:.1f}% of listening time")
                    print(f"Primary profile: {result['profile']['primary']}")

        else:
            print(f"Unknown command: {command}")
            print_usage()
            sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
