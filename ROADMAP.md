# Spoolify Roadmap (Refined)

## Phase 1 — Importer ✅
- Import Spotify Extended Streaming History JSON
- Store plays in SQLite
- Idempotent inserts (no duplicates)
- Restart-safe import
- Bulk insert performance

---

## Phase 2 — Stats ✅
- Top artists (by total listening time)
- Top tracks (by total listening time)
- Total listening time (minutes / hours)
- Total play count

---

## Phase 3 — Time ✅
- Monthly listening stats (plays + minutes)
- Yearly summary
- Hour-of-day listening patterns

---

## Phase 3.5 — Analysis & Audit 🔥
- Peak listening hour / month / year
- Listening behaviour profile (e.g. afternoon vs night listener)
- Trend analysis (year-over-year growth/decline)
- Data validation:
  - duplicate detection
  - zero-minute or malformed plays
  - gaps in timeline (missing months/years)
- Import summary:
  - files processed
  - rows ingested
  - duplicates skipped
- JSON export support for all outputs

---

## Phase 4 — Wrapped
- Deterministic yearly summary
- Top artists and tracks per year
- Peak hour / month
- Total minutes + plays
- Output formats:
  - CLI (text)
  - JSON

---

## Phase 5 — CLI
- import <path>
- stats
- top-artists
- top-tracks
- monthly
- yearly
- hourly
- audit
- insights
- wrapped

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

## Phase 8 — Nice to Have
- CSV export
- Metadata enrichment (Spotify API)
- Minimal web UI (only if needed)
