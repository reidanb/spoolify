# Spoolify FastAPI Service (Phase 6)

## Overview

The FastAPI service provides a lightweight, read-only REST API to access Spoolify analytics. It reuses all existing query logic from the CLI and exposes it as JSON endpoints.

**Key features:**
- Zero authentication (internal use only)
- Read-only access to analytics
- Full Swagger/OpenAPI documentation
- Graceful error handling
- Simple JSON response models

## Installation

### Prerequisites
- Python 3.8+
- FastAPI and uvicorn

### Install Dependencies

```bash
pip install fastapi uvicorn python-multipart
```

Or with optional dotenv support:

```bash
pip install fastapi uvicorn python-dotenv
```

## Running the API

### Start the API server

```bash
# Using entrypoint.py (recommended)
python entrypoint.py serve

# Or directly with uvicorn
uvicorn api:app --host 0.0.0.0 --port 8000

# Or directly with Python
python api.py
```

The API will be available at `http://localhost:8000`

### Environment Variables

Configure the API with standard Spoolify environment variables:

```bash
# Database file location (default: spoolify.db in project root)
export SPOOLIFY_DB_FILE=/path/to/spotify.db

# API host and port (optional)
export SPOOLIFY_API_HOST=0.0.0.0
export SPOOLIFY_API_PORT=8000
```

## API Endpoints

### Frontend Routes

```
GET /
```

Serves the Phase 7 onboarding web UI for archive preparation and guided import.

```
GET /dashboard
```

Serves the user-facing listening dashboard hub after onboarding/import.

### Health Check

```
GET /health
```

Returns server status and database connectivity.

**Response:**
```json
{
  "status": "healthy",
  "message": "Spoolify API is running and database is accessible"
}
```

### Dashboard Summary

```
GET /dashboard-summary
```

Returns aggregated dashboard payload for the user-facing `/dashboard` route.

Current payload includes:
- `data.totals` (plays, hours, unique artists, unique tracks, date range)
- `data.profile` (primary period, bucket percentages, peak hour)
- `data.peaks` (peak month and year)
- `data.trends` (trend label and segments)
- `data.insights` (ordered narrative insights)

All analytics endpoints now return a stable envelope:
- `meta.generated_at` (UTC ISO timestamp)
- `meta.schema_version` (compatibility-sensitive response schema version; `2.x` uses the `meta` + `data` envelope)
- `data` (endpoint payload)

### Overall Statistics

```
GET /stats
```

Returns comprehensive statistics including overall listening time, listening profile, and top artists/tracks.

`/stats` remains a raw analytics endpoint and source of truth for programmatic consumers.

All analytics endpoints now return a stable envelope:
- `meta.generated_at` (UTC ISO timestamp)
- `meta.schema_version` (compatibility-sensitive response schema version; `2.x` uses the `meta` + `data` envelope)
- `data` (endpoint payload)

Compatibility expectations:
- `meta.schema_version` follows compatibility semantics for response shape and field contract.
- Additive fields may appear in minor updates; existing fields keep meaning within a major version.
- Breaking field renames/removals are reserved for a major version.

Field semantics for `/stats`:
- `data.overall.total_minutes`: integer convenience total (rounded down from milliseconds)
- `data.overall.total_minutes_exact`: precise total minutes from raw milliseconds
- `data.overall.total_hours`: derived convenience field from `overall.total_minutes`, rounded to 1 decimal
- `data.profile.total_minutes_exact`: canonical precise total minutes for profile context
- `data.profile.total_minutes`: compatibility alias for `profile.total_minutes_exact` (deprecated; do not use for new clients)
- `top_artists[].name` and `top_tracks[].name` are intentionally kept for compatibility

**Response:**
```json
{
  "meta": {
    "generated_at": "2026-04-07T09:15:23.123456+00:00",
    "schema_version": "2.0.0"
  },
  "data": {
    "overall": {
      "total_minutes": 278199,
      "total_minutes_exact": 278199.47235,
      "total_hours": 4636.6,
      "total_plays": 166140
    },
    "profile": {
      "bucket_minutes": {
        "night": 12141.9719333333,
        "morning": 49060.8814833333,
        "afternoon": 122971.165066667,
        "evening": 94025.4538666667
      },
      "bucket_pct": {
        "night": 4.36448417057299,
        "morning": 17.6351454116384,
        "afternoon": 44.2025155647879,
        "evening": 33.7978548530007
      },
      "primary_profile": "afternoon",
      "primary_pct": 44.2025155647879,
      "peak_hour": 15,
      "confidence": "high",
      "skew": "balanced",
      "very_low_night": true,
      "total_minutes_exact": 278199.47235,
      "total_minutes": 278199.47235
    },
    "top_artists": [
      {"name": "Eminem", "minutes": 4186},
      {"name": "The Smiths", "minutes": 3117}
    ],
    "top_tracks": [
      {"name": "The Suburbs", "artist": "Arcade Fire", "minutes": 615}
    ]
  }
}
```

### Top Artists

```
GET /top-artists?limit=10
```

**Query Parameters:**
- `limit` (integer, 1-100): Number of results (default: 10)

**Response:**
```json
{
  "meta": {
    "generated_at": "2026-04-07T09:15:23.123456+00:00",
    "schema_version": "2.0.0"
  },
  "data": [
    {"name": "Eminem", "minutes": 4186},
    {"name": "The Smiths", "minutes": 3117},
    {"name": "Skepta", "minutes": 2863}
  ]
}
```

### Top Tracks

```
GET /top-tracks?limit=10
```

**Query Parameters:**
- `limit` (integer, 1-100): Number of results (default: 10)

**Response:**
```json
{
  "meta": {
    "generated_at": "2026-04-07T09:15:23.123456+00:00",
    "schema_version": "2.0.0"
  },
  "data": [
    {"name": "The Suburbs", "artist": "Arcade Fire", "minutes": 615},
    {"name": "Redbone", "artist": "Childish Gambino", "minutes": 558}
  ]
}
```

### Monthly Statistics

```
GET /monthly
```

Returns monthly listening stats (plays and minutes per month).

**Response:**
```json
{
  "meta": {
    "generated_at": "2026-04-07T09:15:23.123456+00:00",
    "schema_version": "2.0.0"
  },
  "data": [
    {"month": "2019-01", "plays": 4585, "minutes": 7067},
    {"month": "2019-02", "plays": 3949, "minutes": 6995}
  ]
}
```

### Yearly Statistics

```
GET /yearly
```

Returns yearly listening stats.

**Response:**
```json
{
  "meta": {
    "generated_at": "2026-04-07T09:15:23.123456+00:00",
    "schema_version": "2.0.0"
  },
  "data": [
    {"year": "2018", "plays": 23682, "minutes": 32727},
    {"year": "2019", "plays": 28088, "minutes": 42922}
  ]
}
```

### Hourly Statistics

```
GET /hourly
```

Returns hour-of-day listening patterns (0-23).

**Response:**
```json
{
  "meta": {
    "generated_at": "2026-04-07T09:15:23.123456+00:00",
    "schema_version": "2.0.0"
  },
  "data": [
    {"hour": 0, "plays": 3490, "minutes": 5052},
    {"hour": 1, "plays": 1841, "minutes": 2732}
  ]
}
```

### Trends

```
GET /trends
```

Returns yearly trend analysis with growth/decline/recovery segments.

**Response:**
```json
{
  "meta": {
    "generated_at": "2026-04-07T09:15:23.123456+00:00",
    "schema_version": "2.0.0"
  },
  "data": {
    "yearly_changes": {
      "2016": {"change_pct": null, "change_minutes": null, "baseline": true},
      "2017": {"change_pct": 195.2, "change_minutes": 10086}
    },
    "peak_year": 2019,
    "lowest_year": 2014,
    "trend": "volatile",
    "insights": [
      "Listening peaked in 2019",
      "Sharp decline between 2019–2021"
    ],
    "trend_segments": {
      "growth": "2017–2019",
      "decline": "2019–2021",
      "recovery": "2022–2025"
    },
    "flags": ["possible_platform_switch"],
    "data_confidence": "medium"
  }
}
```

### Wrapped Summary

```
GET /wrapped?year=2019
```

Returns yearly wrapped summary (like Spotify Wrapped).

**Query Parameters:**
- `year` (integer, optional): Specific year to analyze. Defaults to most recent complete year.

**Response:**
```json
{
  "meta": {
    "generated_at": "2026-04-07T09:15:23.123456+00:00",
    "schema_version": "2.0.0",
    "year": "2019"
  },
  "data": {
    "year": 2019,
    "total_minutes": 42922,
    "total_plays": 28088,
    "top_artists": [
      {"artist": "Eminem", "minutes": 1200},
      {"artist": "The Smiths", "minutes": 950}
    ],
    "top_tracks": [
      {"track": "The Suburbs", "artist": "Arcade Fire", "minutes": 100}
    ],
    "peak_month": "01",
    "peak_hour": 15,
    "profile": {
      "bucket_pct": {
        "night": 4.4,
        "morning": 17.6,
        "afternoon": 44.2,
        "evening": 33.8
      },
      "primary": "afternoon"
    }
  }
}
```

### Validate Archive (Phase 7)

```
POST /onboarding/validate-archive
```

Validates a Spotify archive file/directory before import by sampling JSON structure and timestamps.

**Request Body:**
```json
{
  "path": "C:/Users/you/Downloads/Spotify Extended Streaming History"
}
```

### Validate Archive ZIP (Phase 7)

```
POST /onboarding/validate-archive-zip
```

Validates a Spotify ZIP archive upload (multipart form-data).

**Form fields:**

- `file`: ZIP file containing one or more streaming history JSON files

**Response (example):**
```json
{
  "path": "C:/Users/you/Downloads/Spotify Extended Streaming History",
  "archive_type": "directory",
  "json_files_found": 12,
  "json_files_sampled": 8,
  "sampled_entries": 2000,
  "entries_with_track_uri": 1988,
  "entries_missing_track_uri": 12,
  "expected_key_match_pct": 99.3,
  "archive_timespan": {
    "start": "2018-01-01T07:15:00+00:00",
    "end": "2026-03-22T22:41:00+00:00"
  },
  "db_state": {
    "total_rows": 166140,
    "latest_ts": "2026-03-19T20:12:23+00:00"
  },
  "issues": [],
  "recommended_mode": "ongoing_sync_prep",
  "reason": "Archive includes recent playback and database already has data; use this ZIP to top up newer plays."
}
```

### Import Archive (Phase 7)

```
POST /onboarding/import
```

Imports a Spotify archive file/directory and returns per-file and total insertion stats.

**Request Body:**
```json
{
  "path": "C:/Users/you/Downloads/Spotify Extended Streaming History",
  "mode": "historical_backfill"
}
```

### Import Archive ZIP (Phase 7)

```
POST /onboarding/import-zip
```

Imports Spotify history from a ZIP upload (multipart form-data).

**Form fields:**

- `file`: ZIP file containing streaming history JSON files
- `mode`: `historical_backfill` or `ongoing_sync_prep` (both ZIP-only modes)

Allowed `mode` values:

- `historical_backfill`
- `ongoing_sync_prep`

Mode intent in ZIP-only operation:

- `historical_backfill`: first-time or full re-import behavior
- `ongoing_sync_prep`: recent ZIP top-up behavior (no live API sync required)

**Response (example):**
```json
{
  "mode": "historical_backfill",
  "files_processed": 12,
  "totals": {
    "inserted": 152321,
    "duplicates": 218,
    "attempted": 152539,
    "skipped_missing_track_uri": 941,
    "total_rows": 166140
  },
  "files": [
    {
      "file": "Streaming_History_Audio_2025-2026_0.json",
      "inserted": 12873,
      "duplicates": 2,
      "attempted": 12875
    }
  ]
}
```

## Interactive Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

Use these interfaces to test endpoints live in your browser.

## Error Handling

The API gracefully handles errors with descriptive HTTP status codes:

- `200 OK`: Successful request
- `404 Not Found`: Requested resource not available (e.g., invalid year for wrapped)
- `500 Internal Server Error`: Database or server error

**Error Response:**
```json
{
  "detail": "Database error: unable to connect"
}
```

## Code Architecture

### Module Layout

```
entrypoint.py      # Main entry point (routes to CLI or API)
main.py            # CLI interface (unchanged)
api.py             # FastAPI app and endpoints
query_data.py      # Data retrieval functions (reused by API)
queries.py         # Analytics logic (shared source of truth)
db.py              # Database connection and schema
importer.py        # Import logic (unchanged)
```

### Design Decisions

**1. No refactor of queries.py** (except where already returning data)
   - Existing `get_wrapped()`, `get_yearly_trend()`, `get_listening_profile()` already return data
   - Created `query_data.py` with new getter functions to avoid breaking CLI

**2. Pydantic models are minimal**
   - Only used for response validation and documentation
   - Avoids over-engineering the API

**3. Single connection per request**
   - Each request creates a new SQLite connection
   - Simple, thread-safe, no connection pooling needed for read-only workload

**4. No authentication or rate limiting**
   - Designed for internal/trusted use only
   - Future Docker image can add reverse proxy auth if needed

**5. Reusable entry point**
   - `entrypoint.py` can route to CLI or API mode
   - Supports future single-Docker-image deployment with `CMD ["python", "entrypoint.py", "serve"]`

## Testing the API

### Test with curl

```bash
# Health check
curl http://localhost:8000/health

# Dashboard summary payload (used by /dashboard)
curl http://localhost:8000/dashboard-summary

# Get stats (raw JSON analytics)
curl http://localhost:8000/stats

# Get top artists (limit to 5)
curl "http://localhost:8000/top-artists?limit=5"

# Get wrapped for specific year
curl "http://localhost:8000/wrapped?year=2019"
```

### Test with Python

```python
import requests

dashboard = requests.get("http://localhost:8000/dashboard-summary").json()
stats = requests.get("http://localhost:8000/stats").json()

print(dashboard["meta"], stats["meta"])
```
## Performance Notes

- All endpoints query the SQLite database directly
- Database indexes are used (see `db.py`)
- Queries are deterministic (no randomness)
- Response times depend on database size and query complexity
- For production, consider caching responses or adding a connection pool

## Future Enhancements

- Add caching (e.g., Redis)
- Add pagination for large result sets
- Add filtering options (date ranges, artist names, etc.)
- Add export formats (CSV, etc.)
- Add WebSocket endpoints for live updates (if needed)

---

For more information, see the main [README.md](../README.md) and [ROADMAP.md](../ROADMAP.md).

