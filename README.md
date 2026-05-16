
<p align="center">
   <img src="docs/img/logo.png" alt="Spoolify (Spooly) logo" width="320" />
</p>

<h1 align="center">Spoolify</h1>
<p align="center"><em>spool back your listening history</em></p>

---

<p align="center">
   <b>Spoolify</b> (aka <b>Spooly</b>) converts your Spotify Extended Streaming History JSON into a fast, queryable SQLite database. Designed for speed, privacy, and reproducibility—no Spotify API required.
</p>

<p align="center">
   Use it as a <b>CLI tool</b> for local workflows or run it as a <b>web API</b> with FastAPI.
</p>

---

## ⚡ Features

- Import Spotify Extended Streaming History JSON (file or directory)
- Multi-user support — each account gets its own isolated SQLite database
- Local auth with bcrypt-hashed credentials (no email, no external service)
- Idempotent inserts (no duplicates)
- High-performance bulk insert
- CLI analytics commands (stats, top artists/tracks, monthly/yearly/hourly, trends, wrapped)
- Read-only FastAPI web API for dashboards, scripts, and integrations
- No Spotify API or account required

---

## 🚀 Usage

### CLI Mode

All CLI commands require a username. Pass it with `--user` or set `SPOOLIFY_USER` in your environment to avoid repeating it:

```sh
python entrypoint.py --user <username> import <path_to_json_or_directory>
python entrypoint.py --user <username> stats
python entrypoint.py --user <username> top-artists
python entrypoint.py --user <username> top-tracks
python entrypoint.py --user <username> monthly
python entrypoint.py --user <username> yearly
python entrypoint.py --user <username> hourly
python entrypoint.py --user <username> trends
python entrypoint.py --user <username> insights
python entrypoint.py --user <username> wrapped --year 2025 --json
```

To reset a local account password from the shell:

```sh
python entrypoint.py reset-password <username>
```

Example output:

```
Inserted: 7504
Duplicates skipped: 0
Total rows in database: 7504
```

### Web API Mode

Start the API server:

```sh
python entrypoint.py serve
```

Optional environment variables:

```env
SPOOLIFY_API_HOST=0.0.0.0
SPOOLIFY_API_PORT=8000
SPOOLIFY_LOG_LEVEL=INFO
SPOOLIFY_LOG_FILE=spoolify.log
SPOOLIFY_IMPORT_BASE=C:\Users\you
```

Useful URLs after startup:

- API base: `http://localhost:8000`
- Onboarding UI: `http://localhost:8000/`
- Dashboard UI (main post-import hub): `http://localhost:8000/dashboard`
- Raw stats JSON endpoint: `http://localhost:8000/stats`
- Swagger docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Main endpoints:

- `GET /health`
- `GET /dashboard-summary`
- `GET /stats`
- `GET /top-artists?limit=10`
- `GET /top-tracks?limit=10`
- `GET /monthly`
- `GET /yearly`
- `GET /hourly`
- `GET /trends`
- `GET /wrapped?year=2025`
- `POST /onboarding/validate-archive`
- `POST /onboarding/import`
- `POST /onboarding/validate-archive-zip`
- `POST /onboarding/import-zip`

Auth endpoints:

- `GET /login` — login page
- `GET /setup` — first-run account creation page
- `POST /auth/setup` — create first account
- `POST /auth/login` — sign in, sets session cookie
- `POST /auth/logout` — sign out, clears cookie
- `GET /auth/me` — returns current authenticated username
- `GET /users` — list users with a local database

See full API details in `docs/API.md`.

### Frontend Routes

When API mode is running:

- `http://localhost:8000/` — onboarding/import flow (redirects to `/login` if not authenticated, `/dashboard` if data already exists)
- `http://localhost:8000/setup` — first-run account creation
- `http://localhost:8000/login` — sign in
- `http://localhost:8000/dashboard` — main listening hub after import

The onboarding flow helps you:

- request and prepare Spotify Extended Streaming History
- validate archive file/folder structure before import
- validate and import the delivered ZIP archive directly
- import in either `historical_backfill` or `ongoing_sync_prep` mode (both ZIP-only)
- choose between first-time full import and recent ZIP top-up behavior
- keep a privacy-first, local-first setup

---

## 🛠️ Environment Setup

Spoolify uses a `.env` file for configuration. See `.env_example`:

```
SPOOLIFY_DATA_DIR=data           # Directory for per-user databases and auth.db
SPOOLIFY_SECRET_KEY=             # Optional — auto-generated at data/.secret_key if absent
SPOOLIFY_API_HOST=0.0.0.0
SPOOLIFY_API_PORT=8000
SPOOLIFY_LOG_LEVEL=INFO          # DEBUG / INFO / WARNING / ERROR
SPOOLIFY_LOG_FILE=spoolify.log   # Omit to log to stderr only
SPOOLIFY_IMPORT_BASE=C:\Users\you  # Import paths must be inside this directory
```

Copy `.env_example` to `.env` and adjust as needed:

```sh
cp .env_example .env
# or manually create/edit .env
```

---

## ⚡ Performance

- ~166,000 plays imported in ~14 seconds (~11,700 rows/sec)
- Local-first, no network required

Example (Windows PowerShell):

```
Measure-Command { python main.py import "C:/Users/nonadmin_reidan/Downloads/Spotify Extended Streaming History" }

Days              : 0
Hours             : 0
Minutes           : 0
Seconds           : 13
Milliseconds      : 923
Total play count  : 166,140
```

---

## 🧪 Performance Testing

- Configure your import directory in `tests/tests.json`:
   ```json
   {
      "import_dir": "C:/Users/nonadmin_reidan/Downloads/Spotify Extended Streaming History"
   }
   ```
- Run the test script:
   ```powershell
   ./tests/perf_import.ps1
   ```
- Uses a temporary test database and cleans up after the run
- Prints all import output and errors in the summary

---

## 🔌 API Dependencies

CLI mode works with the standard library.

API mode requires:

```sh
pip install fastapi uvicorn python-multipart bcrypt itsdangerous
```

---

## 📁 Project Structure

```
Spoolify/
├── entrypoint.py
├── api.py
├── auth.py
├── query_data.py
├── main.py
├── db.py
├── queries.py
├── importer.py
├── frontend/
│   ├── index.html
│   ├── login.html
│   ├── setup.html
│   ├── dashboard.html
│   ├── app.js
│   ├── dashboard.js
│   └── styles.css
├── tests/
│   ├── perf_import.ps1
│   └── tests.json
├── docs/
│   ├── API.md
│   └── img/
│       └── logo.png
├── .env_example
├── ROADMAP.md
└── README.md
```

---

## 📝 Notes

- No Spotify API or account required
- Local database, privacy-first
- Reliability and reproducibility focused

---

## 🔒 Security

Spoolify implements multi-layered security for archive imports and data handling:

- **ZIP bomb protection**: Compression ratio validation, size limits, entry count checks
- **Path security**: Directory traversal prevention, symlink blocking, encrypted entry rejection
- **Data validation**: Required field checking, type coercion, deduplication via SHA256 hashing
- **Account export detection**: Rejects non-streaming-history exports automatically
- **Privacy-first**: No external API calls, all data stays local

For detailed security documentation, see [docs/SECURITY.md](docs/SECURITY.md).

---

## ⚠️ Disclaimer

Spoolify is not affiliated with Spotify AB or any of its subsidiaries.

---

## 🛣️ Roadmap

See [ROADMAP.md](ROADMAP.md) for upcoming features and development plans.
