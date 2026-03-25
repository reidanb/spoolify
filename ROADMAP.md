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
- Monthly listening stats (plays + minutes) ✅
- Yearly summary ✅
- Hour-of-day listening patterns ✅

---

## Phase 3.5 — Analysis & Audit ✅

- Peak listening hour / month / year
- Listening behaviour profile (time-of-day buckets, primary profile, confidence)
- Year-over-year trend analysis (minutes-based)
- Deterministic insights (peak, decline, recovery)
- Trend segmentation (growth / decline / recovery)
- Data validation:
  - baseline years
  - low-signal years
  - partial years
- Platform switch detection (flag + data confidence)
- Fully deterministic structured output (no randomness)

---

## Phase 4 — Wrapped ✅
- Deterministic yearly summary ✅
- Top artists and tracks per year ✅
- Peak hour / month ✅
- Total minutes + plays ✅
- Output formats:
  - CLI (text) ✅
  - JSON ✅

---

## Phase 5 — CLI ✅
- import <path> ✅
- stats ✅
- top-artists ✅
- top-tracks ✅
- monthly ✅
- yearly ✅
- hourly ✅
- trends ✅
- insights ✅
- wrapped ✅

---

## Phase 6 — Service (optional) ✅
- FastAPI layer ✅
- Read-only endpoints:
  - /health ✅
  - /stats ✅
  - /top-artists ✅
  - /top-tracks ✅
  - /monthly ✅
  - /yearly ✅
  - /hourly ✅
  - /trends ✅
  - /wrapped ✅
- No auth, no multi-user (v1) ✅

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
