# Spoolify

Simple Spotify streaming history importer.

## What it does

- Imports Spotify Extended Streaming History JSON
- Stores plays in SQLite
- Safe to re-run (no duplicates)
- Fast bulk inserts

## Usage

python main.py <path_to_json>

Example:

python main.py "Streaming_History_Audio_2025-2026_10.json"

## Output

Inserted: 7504
Duplicates skipped: 0
Total rows in database: 7504

## Notes

- No Spotify API required
- Local database (SQLite)
- Designed to be simple and reliable

## Next

- Top artists
- Top tracks
- Monthly stats
