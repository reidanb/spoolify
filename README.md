
<p align="center">
   <img src="docs/img/logo.png" alt="Spoolify (Spooly) logo" width="320" />
</p>

<h1 align="center">Spoolify</h1>
<p align="center"><em>spool back your listening history</em></p>

---

<p align="center">
   <b>Spoolify</b> (aka <b>Spooly</b>) converts your Spotify Extended Streaming History JSON into a fast, queryable SQLite database. Designed for speed, privacy, and reproducibility—no Spotify API required.
</p>

---

## ⚡ Features

- Import Spotify Extended Streaming History JSON (file or directory)
- Local SQLite storage
- Idempotent inserts (no duplicates)
- High-performance bulk insert
- No API or account required

---

## 🚀 Usage

```sh
python main.py <path_to_json_or_directory>
```

Examples:

```sh
python main.py "Streaming_History_Audio_2025-2026_10.json"
python main.py "C:/Users/nonadmin_reidan/Downloads/Spotify Extended Streaming History"
```

Example output:

```
Inserted: 7504
Duplicates skipped: 0
Total rows in database: 7504
```

---

## 🛠️ Environment Setup

Spoolify uses a `.env` file for configuration. See `.env_example`:

```
SPOOLIFY_DB_FILE=spoolify.db
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
Measure-Command { python main.py "C:/Users/nonadmin_reidan/Downloads/Spotify Extended Streaming History" }

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

## 📁 Project Structure

```
Spoolify/
├── main.py
├── db.py
├── queries.py
├── importer.py
├── tests/
│   ├── perf_import.ps1
│   └── tests.json
├── docs/
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

## ⚠️ Disclaimer

Spoolify is not affiliated with Spotify AB or any of its subsidiaries.

---

## 🛣️ Roadmap

See [ROADMAP.md](ROADMAP.md) for upcoming features and development plans.
