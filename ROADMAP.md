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

## Phase 7 — Onboarding & Data Acquisition
- First-run onboarding flow
- Guide users through requesting Spotify Extended Streaming History
- Explain Spotify export wait time and expected archive contents
- Validate downloaded archive structure before import
- Distinguish historical backfill from ongoing sync
- Add onboarding for Spotify Developer app creation
- Explain required scopes, redirect URIs, and local configuration
- Keep privacy-first positioning clear throughout setup

---

## Phase 8 — Docker Runtime
- Single container for API + sync worker runtime
- Persistent SQLite volume mount
- Config via env vars
- Clean startup modes for:
  - import-only workflows
  - API service
  - long-running sync service
- Simple docker run / docker compose flow
- Stable local deployment story before adding more product surface

---

## Phase 9 — Spotify Account Connection
- Spotify Web API developer registration support
- OAuth login / authorization flow
- Access token and refresh token handling
- Secure local secret management
- Connect / disconnect account flow
- Store sync metadata separately from analytics data
- Preserve local-first operation for users who only want archive import

---

## Phase 10 — Near-Real-Time Sync
- Poll Spotify playback endpoints on a configurable interval
- Use recently played history as the authoritative sync source
- Optionally use currently playing state for fresher status
- Cursor-based incremental sync
- Deduplicate API-synced plays against imported archive data
- Track last successful sync time
- Handle expired tokens, network failures, and rate limits safely
- Realtime-enough freshness without promising true realtime streaming

---

## Phase 11 — Unified Analytics
- Merge historical archive imports and synced playback into one analytics layer
- Show sync freshness and data-source status
- Expose sync-aware API endpoints
- Add live-ish listening summaries and rolling recent activity
- Separate provisional now-playing state from finalized listening history
- Preserve deterministic historical analytics while improving recency

---

## Phase 12 — Hardening & Product Maturity
- Background worker supervision and restart safety
- Observability for sync health, errors, and rate limiting
- Schema evolution / migration strategy
- Backup and restore workflow
- Better operational docs for local and container deployments
- Performance tuning for long-running sync workloads
- Optional future additions:
  - metadata enrichment
  - CSV export
  - minimal web UI
  - multi-user support only if product scope expands

---

## Product Direction
- Historical Spotify archive import remains the foundation
- Spotify Web API sync extends freshness, not historical completeness
- Local-first, privacy-first operation remains the default
- Docker is a deployment step, not a change in product ownership model