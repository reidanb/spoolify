# Spoolify Roadmap

## Phase 1 — Importer ✅
- Import Spotify Extended Streaming History JSON
- Store plays in SQLite
- Idempotent inserts (no duplicates)
- Restart-safe import
- Bulk insert performance

---

## Phase 2 — Stats
- Top artists (by total listening time)
- Top tracks (by total listening time)
- Total listening time (minutes / hours)
- Total play count

---

## Phase 3 — Time
- Monthly listening stats (plays + minutes)
- Yearly summary
- (Optional) hour-of-day listening patterns

---

## Phase 4 — Wrapped
- Year summary output
- Top artists and tracks per year
- Most active month
- Simple text/JSON export

---

## Phase 5 — CLI
- import <file>
- stats
- top-artists
- top-tracks
- monthly

---

## Phase 6 — Service (optional)
- FastAPI layer
- Read-only endpoints:
  - /stats
  - /top-artists
  - /top-tracks
  - /timeline
- No auth, no multi-user (v1)

---

## Phase 7 — Docker
- Single container (app + SQLite)
- Volume-mounted DB (/data/db.sqlite)
- Config via env vars (DB_PATH)
- Simple docker run / docker-compose

---

## Phase 8 — Nice to Have (later)
- Optional metadata enrichment (Spotify API)
- Basic web UI (only if needed)
- Export formats (CSV / JSON)