# Spoolify Security Documentation

This document describes the security features and practices implemented in Spoolify to protect user data and system integrity during archive imports and analytics queries.

## Table of Contents

1. [Design Principles](#design-principles)
2. [Privacy & Data Isolation](#privacy--data-isolation)
3. [Archive Import Security](#archive-import-security)
4. [ZIP File Upload Security](#zip-file-upload-security)
5. [Input Validation](#input-validation)
6. [Deduplication & Integrity](#deduplication--integrity)
7. [Database Security](#database-security)
8. [File Path Security](#file-path-security)
9. [Known Limitations](#known-limitations)

---

## Design Principles

Spoolify is designed around **privacy-first** and **zero-network** principles:

- **No External API Calls**: Spoolify never contacts Spotify or any external service. All data processing is local.
- **No Account Authentication**: Spoolify does not require Spotify account login or API credentials.
- **Reproducible Processing**: All operations are deterministic; same input always produces same output.
- **Local Database**: All data is stored in a configurable local SQLite database file. Default location: `spoolify.db` in project root.

---

## Privacy & Data Isolation

### Local-Only Processing

All Spotify Extended Streaming History data remains on your local machine:

- JSON import files are read directly from disk or ZIP archives.
- Data is inserted into a local SQLite database.
- Analytics are computed locally with no network transmission.
- No telemetry, logging, or external data forwarding is performed.

### Configurable Database Location

The database file path can be customized via environment variable:

```bash
# .env file
SPOOLIFY_DB_FILE=/path/to/custom/spoolify.db
```

This allows users to:
- Store the database on encrypted volumes
- Use remote storage (e.g., cloud sync) with appropriate caution
- Separate data and code locations

---

## Archive Import Security

### Account Export Detection

Spoolify detects and rejects Spotify account-info exports (full account packages) in favor of **Extended Streaming History** archives:

**Rejected Export Markers:**
- `yoursoundcapsule.json`
- `yourlibrary.json`
- `identity.json`
- `payments.json`
- `messagedata.json`
- And others (see `ACCOUNT_INFO_EXPORT_MARKERS` in `api.py`)

**Why:** Account exports contain sensitive information (payment data, identity, library metadata) beyond streaming history. Spoolify only processes extended streaming history JSON files.

### Archive Validation

Before importing, Spoolify validates the archive structure:

1. **File Discovery**: Only `.json` files matching Extended Streaming History format are considered.
2. **Sampling**: A random sample of files is analyzed to detect:
   - Expected key presence (`ts`, `ms_played`, `spotify_track_uri`, etc.)
   - Track URI validity (entries without `spotify_track_uri` are flagged as skipped)
   - Timestamp validity and timespan coverage
3. **Schema Validation**: Entries missing critical fields are skipped during import, not rejected.

### Mode Recommendations

The API provides intelligent import mode recommendations based on archive analysis:

- **`historical_backfill`**: Recommended for large archives or first-time imports.
- **`ongoing_sync_prep`**: Recommended when archive is recent (<=30 days old) and database already has data.

---

## ZIP File Upload Security

### Overview

Spoolify implements multi-layered ZIP file security to prevent:
- Zip bombs (decompression attacks)
- Directory traversal attacks
- Symlink exploitation
- Encrypted archive traps
- Resource exhaustion

### Upload Size Limits

```python
MAX_ZIP_UPLOAD_BYTES = 200 * 1024 * 1024          # 200 MB compressed size
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 512 * 1024 * 1024  # 512 MB total decompressed
MAX_ZIP_FILE_UNCOMPRESSED_BYTES = 64 * 1024 * 1024    # 64 MB per JSON file
```

**Validation Flow:**
1. Compressed upload is rejected if it exceeds `MAX_ZIP_UPLOAD_BYTES`.
2. Total decompressed size is checked against `MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES`.
3. Each JSON file is checked against `MAX_ZIP_FILE_UNCOMPRESSED_BYTES`.

### Entry Count Limits

```python
MAX_ZIP_ENTRIES = 2000          # Total entries (files + dirs)
MAX_ZIP_JSON_FILES = 500        # Only .json files count against this limit
```

These prevent archives with pathological entry counts from exhausting memory or file descriptors.

### Compression Ratio Validation (Zip Bomb Detection)

For each JSON file ≥1 MB, Spoolify checks the compression ratio:

```python
MAX_ZIP_COMPRESSION_RATIO = 200

ratio = uncompressed_size / compressed_size
if ratio > 200:  # File is >200x compressed
    REJECT  # Likely a zip bomb
```

**Example:** A 10 MB uncompressed file must have compressed size > 50 KB to be accepted. This prevents highly compressed payloads that explode on decompression.

### Path Safety Checks

All file paths inside the ZIP are validated:

```python
normalized_name = info.filename.replace("\\", "/")
parts = Path(normalized_name).parts

if normalized_name.startswith("/"):
    REJECT  # Absolute path
if ".." in parts:
    REJECT  # Directory traversal attempt
```

This prevents:
- Absolute path extraction (e.g., `/etc/passwd`)
- Directory traversal (e.g., `../../sensitive/file.json`)

### Symlink Detection & Blocking

Spoolify detects and blocks symlink entries in ZIP files:

```python
mode_bits = (info.external_attr >> 16) & 0o170000
if mode_bits == 0o120000:  # Unix symlink mode
    REJECT
```

**Why:** Symlinks could redirect extraction to sensitive filesystem locations.

### Encrypted Entry Rejection

Encrypted ZIP entries are rejected:

```python
if info.flag_bits & 0x1:  # Encryption flag
    REJECT
```

**Why:** Spoolify cannot securely validate encrypted entries; they are blocked outright.

### Staged Extraction & Cleanup

Extracted files are placed in a secure temporary directory with automatic cleanup:

```python
staged_dir = Path(tempfile.mkdtemp(prefix="spoolify_zip_staged_"))
# Extract and process files here
# ...
shutil.rmtree(staged_dir, ignore_errors=True)  # Cleanup on completion or error
```

---

## Input Validation

### JSON Structure Validation

Each imported JSON file must be a valid UTF-8 JSON array of objects:

```python
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)  # Raises JSONDecodeError on invalid JSON
```

Invalid JSON is reported with file name and error details.

### Data Type Coercion

Fields are normalized to expected types with fallback defaults:

| Field | Expected Type | Fallback |
|-------|---|---|
| `ms_played` | `int` | `0` |
| `skipped` | `bool` → `0/1` | `0` |
| `ts` | `str` (ISO 8601) | Stored as-is; invalid entries may be skipped at query time |

**Example:**
```python
ms_played = int(ms_played) if ms_played is not None else 0  # Never None or non-int
skipped = 1 if skipped in (1, True, "1", "true", "True") else 0  # Always 0 or 1
```

### Required Field Validation

Entries without required fields are skipped:

```python
if not track_uri:
    skipped_missing_track_uri += 1
    continue  # Skip this entry
```

**Skipped Entries:**
- Missing `spotify_track_uri`
- Missing `ts` (timestamp)
- Missing track metadata

These are counted and reported to the user but do not fail the import.

### Field Extraction from Nested JSON

Expected field names follow Spotify's Extended Streaming History schema:

- `ts` - ISO 8601 timestamp
- `spotify_track_uri` - Spotify track URI (required)
- `master_metadata_track_name` - Track name
- `master_metadata_album_artist_name` - Artist name
- `master_metadata_album_album_name` - Album name
- `ms_played` - Duration in milliseconds
- `platform` - Device/client platform
- `skipped` - Whether user skipped the track

Unrecognized fields are ignored.

---

## Deduplication & Integrity

### SHA256 Hash-Based Deduplication

Spoolify uses SHA256 hashing to detect and prevent duplicate entries:

```python
def generate_hash(entry):
    key = ts + track_uri + ms_played
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
```

**Hash Components:**
- `ts` - Timestamp (ISO 8601)
- `spotify_track_uri` - Track URI
- `ms_played` - Duration played (milliseconds)

**Why These Fields?**
- Together, they uniquely identify a play event.
- Timestamp + URI + duration combination is collision-resistant.

### UNIQUE Constraint on Hash Column

The database schema enforces uniqueness via SQL constraint:

```sql
CREATE TABLE plays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- ... other columns ...
    hash TEXT UNIQUE
);
```

### Idempotent Inserts

Duplicate entries are silently ignored during import:

```sql
INSERT OR IGNORE INTO plays (...) VALUES (...)
```

**Behavior:**
- First occurrence of an entry is inserted.
- Subsequent occurrences (same hash) are skipped.
- Import is idempotent: running the same file multiple times produces same result.

**Reporting:**
- Duplicate count is tracked and reported to user.
- Example: "Duplicates skipped: 42"

---

## Database Security

### SQLite Storage

Spoolify uses SQLite for local data storage:

- Single file database: `spoolify.db` (configurable via `SPOOLIFY_DB_FILE`).
- No server process; direct file access.
- All queries use parameterized statements (no SQL injection risk).

### Parameterized Queries

All SQL queries use parameter binding to prevent SQL injection:

```python
cur.executemany("""
    INSERT OR IGNORE INTO plays (ts, track_uri, ..., hash)
    VALUES (?, ?, ?, ...)
""", to_insert)
```

The `?` placeholders are filled safely with parameters; user data is never concatenated into SQL strings.

### Database Initialization

On first use, Spoolify creates the schema and indexes:

```sql
CREATE TABLE IF NOT EXISTS plays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    track_uri TEXT,
    track_name TEXT,
    artist_name TEXT,
    album_name TEXT,
    ms_played INTEGER,
    platform TEXT,
    skipped INTEGER,
    hash TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_artist ON plays(artist_name);
CREATE INDEX IF NOT EXISTS idx_track ON plays(track_name);
CREATE INDEX IF NOT EXISTS idx_ts ON plays(ts);
```

**Indexes** speed up analytics queries without exposing additional security surface.

---

## File Path Security

### Path Normalization

All file paths are normalized and resolved to prevent escapes:

```python
path = Path(input_path).expanduser().resolve()
```

**Steps:**
1. `expanduser()` - Resolve `~` to user home directory.
2. `resolve()` - Convert to absolute path and resolve symlinks.

### Existence & Type Checking

Paths are validated before use:

```python
if not path.exists():
    raise HTTPException(detail="Path does not exist")

if path.is_file():
    # Handle single file
elif path.is_dir():
    # Handle directory of files
```

**Result:** Path traversal attempts (e.g., `/path/../../etc/passwd`) are resolved to their canonical target and rejected if outside the intended directory.

### File Extension Validation

Only `.json` files are imported:

```python
if path.suffix.lower() != ".json":
    raise HTTPException(detail="Expected a .json file")
```

Directory imports also filter by extension:

```python
json_files = [f for f in os.listdir(path) if f.lower().endswith('.json')]
```

---

## Known Limitations

### 1. Database File Permissions

SQLite does not encrypt data at rest. If the database file is readable by other users on the same machine, data is visible.

**Mitigation:**
- Use file system permissions to restrict access: `chmod 600 spoolify.db`
- Store on encrypted filesystem volumes (e.g., BitLocker, LUKS)
- Use private cloud storage with encryption in transit

### 2. No Audit Logging

Spoolify does not log which files were imported or when. This is intentional (privacy-first design) but means:
- No audit trail of user actions
- Silent failures may go unnoticed

**Mitigation:**
- Regularly review database row counts and timestamps.
- Back up database snapshots before large imports.

### 3. Temporary Files

During ZIP extraction, files are temporarily stored on disk in a secure temp directory. On systems with accessible `/tmp` or `%TEMP%`, these files may be visible to root/admin.

**Mitigation:**
- Spoolify cleans up staged files even on error.
- Use a system temp directory on an encrypted volume.
- Consider using `TMPDIR` environment variable to redirect temp location.

### 4. No Input Sanitization for Display

User-provided data (artist name, track name) is displayed in output but not HTML-escaped. If using Spoolify output in web contexts, XSS is possible.

**Mitigation:**
- This is a CLI/backend tool; frontend (if used) should escape output.
- API responses are JSON; client is responsible for safe rendering.

### 5. Timestamp Parsing

Timestamps are stored and sorted as strings (ISO 8601 format). Malformed timestamps may break analytics.

**Mitigation:**
- Spotify's export format is standardized; malformed timestamps are rare.
- Entries with unparseable timestamps are handled gracefully (null comparison safe).

---

## Security Checklist for Deployers

If you are deploying Spoolify in a production or shared environment:

- [ ] **Database File Permissions**: Restrict read/write to intended users only.
- [ ] **Encrypted Storage**: Store `spoolify.db` on an encrypted filesystem.
- [ ] **Environment Variables**: Use `.env` file (or secure secrets manager) for `SPOOLIFY_DB_FILE`.
- [ ] **Temporary Directory**: Ensure `/tmp` or `%TEMP%` is on an encrypted volume or secure.
- [ ] **Input Archives**: Validate ZIP files are from trusted sources before importing.
- [ ] **Output Sanitization**: If exposing analytics via web interface, escape/sanitize HTML output.
- [ ] **Access Control**: Use firewall/network rules if API is exposed on network.
- [ ] **Regular Backups**: Back up database to secure location; test recovery.

---

## Contact & Reporting

If you discover a security issue in Spoolify:

1. **Do not** open a public GitHub issue.
2. Contact the maintainer privately with details.
3. Allow time for a fix before public disclosure.

---

**Document Version:** 1.0  
**Last Updated:** April 2026
