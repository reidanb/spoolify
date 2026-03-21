# Spoolify Usage Guide

## CLI Commands

### Import Data
```
python main.py import <path-to-spotify-json>
```
- Imports one or more Spotify Extended Streaming History JSON files into the database.
- Supports both single files and directories containing multiple JSON files.

### View Top Artists
```
python main.py --top-artists
```
- Shows the top 10 artists by total listening time (minutes).

### View Stats
```
python main.py --stats
```
- Shows overall listening stats, top artists, top tracks, monthly and yearly summaries, and listening profile.

### Wrapped Summary
```
python main.py wrapped
```
- Shows a deterministic yearly summary ("Wrapped") for the most recent complete year.

#### Wrapped for a Specific Year
```
python main.py wrapped --year <year>
```
- Shows the wrapped summary for the specified year (if available).

#### Wrapped as JSON
```
python main.py wrapped --json
```
- Outputs the wrapped summary in structured JSON format.

## Output Examples

- CLI summary output is formatted for readability.
- JSON output is structured for programmatic use.

## Notes
- All analytics are deterministic and based on imported data only.
- No new analytics logic is introduced in wrapped output; all values are composed from existing stats, profile, and trend analysis.
- Partial years are excluded from wrapped summaries.

---

For more details, see the ROADMAP.md.
