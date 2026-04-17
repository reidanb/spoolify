"""
FastAPI service for Spoolify.
Exposes analytics endpoints, onboarding helpers, and import APIs.
"""

from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import tempfile
import zipfile

from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from db import get_connection, init_db
from importer import import_file_stats
from query_data import (
    get_top_artists, get_top_tracks, get_monthly_stats, 
    get_yearly_stats, get_hourly_stats, get_overall_stats,
    get_listening_profile_data, get_unique_artist_count,
    get_unique_track_count, get_date_range, get_peak_month,
    get_overall_stats_filtered, get_unique_artist_count_filtered,
    get_unique_track_count_filtered, get_monthly_stats_filtered,
    get_hourly_stats_filtered, get_yearly_stats_filtered,
    get_top_artists_filtered, get_top_tracks_filtered,
    get_date_range_filtered, get_peak_month_filtered
)
from queries import get_yearly_trend, get_wrapped

app = FastAPI(
    title="Spoolify API",
    description="FastAPI service for Spotify listening analytics and onboarding",
    version="1.0.0"
)

API_SCHEMA_VERSION = "2.0.0"

# ZIP safety limits for onboarding uploads.
MAX_ZIP_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_ZIP_ENTRIES = 2000
MAX_ZIP_JSON_FILES = 500
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_ZIP_FILE_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 200

ACCOUNT_INFO_EXPORT_MARKERS = {
    "yoursoundcapsule.json",
    "yourlibrary.json",
    "wrapped2025.json",
    "userdata.json",
    "streaminghistory_podcast_0.json",
    "streaminghistory_music_0.json",
    "streaminghistory_music_1.json",
    "searchqueries.json",
    "playlists1.json",
    "payments.json",
    "messagedata.json",
    "marquee.json",
    "identity.json",
    "identifiers.json",
    "follow.json",
    "duonewfamily.json",
}

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


# ==============================================================================
# PYDANTIC MODELS
# ==============================================================================

class Artist(BaseModel):
    name: str
    minutes: int


class Track(BaseModel):
    name: str
    artist: str
    minutes: int


class MonthlyEntry(BaseModel):
    month: str
    plays: int
    minutes: int


class YearlyEntry(BaseModel):
    year: str
    plays: int
    minutes: int


class HourlyEntry(BaseModel):
    hour: int
    plays: int
    minutes: int


class OverallStats(BaseModel):
    total_minutes: int
    total_minutes_exact: float
    total_hours: float
    total_plays: int


class BucketStats(BaseModel):
    night: float
    morning: float
    afternoon: float
    evening: float


class ListeningProfile(BaseModel):
    bucket_minutes: BucketStats
    bucket_pct: BucketStats
    primary_profile: str
    primary_pct: float
    peak_hour: Optional[int]
    confidence: str
    skew: Optional[str] = None
    very_low_night: Optional[bool] = None
    total_minutes: Optional[float] = None
    total_minutes_exact: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    message: str


class StatsResponse(BaseModel):
    overall: OverallStats
    profile: ListeningProfile
    top_artists: List[Artist]
    top_tracks: List[Track]


class ArchivePathRequest(BaseModel):
    path: str


class OnboardingImportRequest(BaseModel):
    path: str
    mode: str = "historical_backfill"


def _generated_at_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _with_meta(data: Any, year: Optional[Any] = None, **extra_meta: Any) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "generated_at": _generated_at_utc(),
        "schema_version": API_SCHEMA_VERSION,
    }
    if year is not None:
        meta["year"] = str(year)
    meta.update(extra_meta)
    return {
        "meta": meta,
        "data": data,
    }


def _discover_json_files(input_path: str) -> List[Path]:
    path = Path(input_path).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {input_path}")

    if path.is_file():
        if path.suffix.lower() != ".json":
            raise HTTPException(status_code=400, detail="Expected a .json file or directory containing .json files")
        return [path]

    files = sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".json")
    if not files:
        raise HTTPException(status_code=400, detail="No .json files were found in the provided directory")
    return files


def _select_files_for_sampling(files: List[Path], max_files: int = 8) -> List[Path]:
    """Select files evenly across sorted archive list to avoid oldest-file bias."""
    if len(files) <= max_files:
        return files

    selected: List[Path] = []
    for i in range(max_files):
        idx = round(i * (len(files) - 1) / (max_files - 1))
        selected.append(files[idx])
    return selected


def _iter_sample_entries(data: List[Any], per_file_limit: int = 250) -> List[Any]:
    """Sample entries from both start and end of a file for better timespan coverage."""
    if len(data) <= per_file_limit:
        return data

    head_n = per_file_limit // 2
    tail_n = per_file_limit - head_n
    return data[:head_n] + data[-tail_n:]


def _detect_account_export_markers(files: List[Path]) -> List[str]:
    markers_found = {
        p.name.lower()
        for p in files
        if p.name.lower() in ACCOUNT_INFO_EXPORT_MARKERS
    }
    return sorted(markers_found)


def _validate_archive_files(files: List[Path], source_label: str, archive_type: str) -> Dict[str, Any]:
    expected_keys = {
        "ts",
        "ms_played",
        "spotify_track_uri",
        "master_metadata_track_name",
        "master_metadata_album_artist_name",
    }

    issues: List[str] = []
    files_sampled = 0
    sampled_entries = 0
    valid_track_uri_entries = 0
    missing_track_uri_entries = 0
    expected_key_hits = 0
    expected_key_checks = 0
    min_ts = None
    max_ts = None

    sampled_files = _select_files_for_sampling(files, max_files=8)
    account_markers = _detect_account_export_markers(files)
    detected_export_type = "account_info_export" if account_markers else "extended_streaming_history_archive"

    if account_markers:
        issues.append(
            "Detected account-info export markers. This looks like an account export package, not a pure Extended Streaming History drop."
        )

    # Sample across the archive and from both ends of each file.
    for file_path in sampled_files:
        files_sampled += 1
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            issues.append(f"Failed to parse {file_path.name}: {exc}")
            continue

        if not isinstance(data, list):
            issues.append(f"{file_path.name} is not a JSON array.")
            continue

        for entry in _iter_sample_entries(data, per_file_limit=250):
            if not isinstance(entry, dict):
                continue

            sampled_entries += 1
            for key in expected_keys:
                expected_key_checks += 1
                if key in entry:
                    expected_key_hits += 1

            if entry.get("spotify_track_uri"):
                valid_track_uri_entries += 1
            else:
                missing_track_uri_entries += 1

            parsed_ts = _parse_ts(entry.get("ts"))
            if parsed_ts is not None:
                if min_ts is None or parsed_ts < min_ts:
                    min_ts = parsed_ts
                if max_ts is None or parsed_ts > max_ts:
                    max_ts = parsed_ts

    if sampled_entries == 0:
        issues.append("No valid entries found while sampling archive files.")

    conn = get_connection()
    init_db(conn)
    db_total_rows = _get_db_total_rows(conn)
    db_latest_ts = _get_db_latest_ts(conn)
    recommendation = _recommend_mode(db_total_rows, max_ts, db_latest_ts)
    conn.close()

    key_match_pct = round((expected_key_hits / expected_key_checks) * 100, 2) if expected_key_checks else 0.0

    return {
        "path": source_label,
        "archive_type": archive_type,
        "json_files_found": len(files),
        "json_files_sampled": files_sampled,
        "sampled_file_names": [p.name for p in sampled_files],
        "sampled_entries": sampled_entries,
        "detected_export_type": detected_export_type,
        "account_export_markers_found": account_markers,
        "entries_with_track_uri": valid_track_uri_entries,
        "entries_missing_track_uri": missing_track_uri_entries,
        "expected_key_match_pct": key_match_pct,
        "archive_timespan": {
            "start": min_ts.isoformat() if min_ts else None,
            "end": max_ts.isoformat() if max_ts else None,
        },
        "db_state": {
            "total_rows": db_total_rows,
            "latest_ts": db_latest_ts.isoformat() if db_latest_ts else None,
        },
        "issues": issues,
        **recommendation,
    }


def _import_archive_files(files: List[Path], mode: str) -> Dict[str, Any]:
    if mode not in {"historical_backfill", "ongoing_sync_prep"}:
        raise HTTPException(status_code=400, detail="mode must be either historical_backfill or ongoing_sync_prep")

    account_markers = _detect_account_export_markers(files)
    if account_markers:
        joined = ", ".join(account_markers)
        raise HTTPException(
            status_code=400,
            detail=(
                "Detected Spotify account-info export files "
                f"({joined}). Spoolify currently imports only Extended Streaming History JSON files."
            ),
        )

    conn = get_connection()
    init_db(conn)

    totals = {
        "inserted": 0,
        "duplicates": 0,
        "attempted": 0,
        "skipped_missing_track_uri": 0,
    }
    file_summaries: List[Dict[str, Any]] = []

    try:
        for file_path in files:
            stats = import_file_stats(conn, str(file_path))
            totals["inserted"] += stats["inserted"]
            totals["duplicates"] += stats["duplicates"]
            totals["attempted"] += stats["attempted"]
            totals["skipped_missing_track_uri"] += stats["skipped_missing_track_uri"]
            file_summaries.append(
                {
                    "file": file_path.name,
                    "inserted": stats["inserted"],
                    "duplicates": stats["duplicates"],
                    "attempted": stats["attempted"],
                }
            )

        totals["total_rows"] = _get_db_total_rows(conn)
        return {
            "mode": mode,
            "files_processed": len(files),
            "totals": totals,
            "files": file_summaries,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
    finally:
        conn.close()


def _extract_zip_json_files(upload: UploadFile) -> List[Path]:
    if not upload.filename or not upload.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a .zip archive")

    with tempfile.TemporaryDirectory(prefix="spoolify_zip_") as temp_dir:
        temp_dir_path = Path(temp_dir)
        zip_path = temp_dir_path / "upload.zip"

        # Copy uploaded bytes with a strict upper bound to prevent oversized uploads.
        total_uploaded = 0
        upload.file.seek(0)
        with zip_path.open("wb") as f:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                total_uploaded += len(chunk)
                if total_uploaded > MAX_ZIP_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "ZIP upload is too large. "
                            f"Max allowed size is {MAX_ZIP_UPLOAD_BYTES // (1024 * 1024)} MB."
                        ),
                    )
                f.write(chunk)

        try:
            with zipfile.ZipFile(zip_path) as zf:
                infos = zf.infolist()
                if len(infos) > MAX_ZIP_ENTRIES:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "ZIP has too many entries. "
                            f"Max allowed is {MAX_ZIP_ENTRIES}."
                        ),
                    )

                json_infos = []
                total_uncompressed = 0
                for info in infos:
                    if info.is_dir():
                        continue

                    normalized_name = info.filename.replace("\\", "/")
                    parts = Path(normalized_name).parts
                    if normalized_name.startswith("/") or ".." in parts:
                        raise HTTPException(status_code=400, detail="ZIP contains unsafe file paths")

                    # Block symlink-like entries from untrusted archives.
                    mode_bits = (info.external_attr >> 16) & 0o170000
                    if mode_bits == 0o120000:
                        raise HTTPException(status_code=400, detail="ZIP contains unsupported symlink entries")

                    if info.flag_bits & 0x1:
                        raise HTTPException(status_code=400, detail="Encrypted ZIP entries are not supported")

                    if not normalized_name.lower().endswith(".json"):
                        continue

                    if info.file_size > MAX_ZIP_FILE_UNCOMPRESSED_BYTES:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"ZIP entry {Path(normalized_name).name} is too large after decompression. "
                                f"Max per JSON file is {MAX_ZIP_FILE_UNCOMPRESSED_BYTES // (1024 * 1024)} MB."
                            ),
                        )

                    compressed_size = max(info.compress_size, 1)
                    ratio = info.file_size / compressed_size
                    if info.file_size >= (1024 * 1024) and ratio > MAX_ZIP_COMPRESSION_RATIO:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"ZIP entry {Path(normalized_name).name} has suspicious compression ratio ({ratio:.1f}x)."
                            ),
                        )

                    total_uncompressed += info.file_size
                    if total_uncompressed > MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                "Total decompressed JSON size is too large. "
                                f"Max allowed is {MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES // (1024 * 1024)} MB."
                            ),
                        )

                    json_infos.append(info)

                if not json_infos:
                    raise HTTPException(status_code=400, detail="No .json files found inside ZIP archive")
                if len(json_infos) > MAX_ZIP_JSON_FILES:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "ZIP contains too many JSON files. "
                            f"Max allowed is {MAX_ZIP_JSON_FILES}."
                        ),
                    )

                staged_dir = Path(tempfile.mkdtemp(prefix="spoolify_zip_staged_"))
                staged_files: List[Path] = []
                try:
                    for idx, info in enumerate(json_infos):
                        target_dir = staged_dir / f"{idx:04d}"
                        target_dir.mkdir(parents=True, exist_ok=True)
                        target = target_dir / Path(info.filename).name

                        with zf.open(info, "r") as src, target.open("wb") as dst:
                            written = 0
                            while True:
                                chunk = src.read(1024 * 1024)
                                if not chunk:
                                    break
                                written += len(chunk)
                                if written > MAX_ZIP_FILE_UNCOMPRESSED_BYTES:
                                    raise HTTPException(
                                        status_code=400,
                                        detail=(
                                            f"ZIP entry {target.name} exceeded per-file decompression limit."
                                        ),
                                    )
                                dst.write(chunk)

                        staged_files.append(target)

                    return staged_files
                except Exception:
                    shutil.rmtree(staged_dir, ignore_errors=True)
                    raise
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid ZIP archive")


def _cleanup_staged_files(files: List[Path]) -> None:
    if not files:
        return
    try:
        shutil.rmtree(files[0].parent)
    except Exception:
        pass


def _parse_ts(ts_value: Any) -> Optional[datetime]:
    if not ts_value or not isinstance(ts_value, str):
        return None
    try:
        return datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _get_db_total_rows(conn) -> int:
    cur = conn.cursor()
    return int(cur.execute("SELECT COUNT(*) FROM plays").fetchone()[0])


def _get_db_latest_ts(conn) -> Optional[datetime]:
    cur = conn.cursor()
    max_ts = cur.execute("SELECT MAX(ts) FROM plays").fetchone()[0]
    return _parse_ts(max_ts)


def _recommend_mode(total_rows: int, archive_latest: Optional[datetime], db_latest: Optional[datetime]) -> Dict[str, str]:
    if total_rows == 0:
        return {
            "recommended_mode": "historical_backfill",
            "reason": "Database is empty, so importing full archive history is recommended first."
        }

    if archive_latest is None:
        return {
            "recommended_mode": "historical_backfill",
            "reason": "Archive timestamps are incomplete, so treat this as a backfill import."
        }

    now_utc = datetime.now(timezone.utc)
    recency_days = (now_utc - archive_latest.astimezone(timezone.utc)).days
    if recency_days <= 30 and db_latest is not None:
        return {
            "recommended_mode": "ongoing_sync_prep",
            "reason": "Archive includes recent playback and database already has data; use this to top up before sync."
        }

    return {
        "recommended_mode": "historical_backfill",
        "reason": "Archive appears to be a broad history import rather than a recent incremental update."
    }


def _build_profile_from_hourly_rows(hourly_rows: List[Any]) -> Dict[str, Any]:
    bucket_minutes = {
        "night": 0.0,
        "morning": 0.0,
        "afternoon": 0.0,
        "evening": 0.0,
    }
    total_minutes = 0.0
    peak_hour = None
    peak_hour_minutes = -1.0

    for hour, _plays, minutes in hourly_rows:
        minute_value = float(minutes or 0)
        total_minutes += minute_value
        numeric_hour = int(hour)

        if numeric_hour < 6:
            bucket_minutes["night"] += minute_value
        elif numeric_hour < 12:
            bucket_minutes["morning"] += minute_value
        elif numeric_hour < 18:
            bucket_minutes["afternoon"] += minute_value
        else:
            bucket_minutes["evening"] += minute_value

        if minute_value > peak_hour_minutes:
            peak_hour_minutes = minute_value
            peak_hour = numeric_hour

    if total_minutes <= 0:
        return {
            "primary_profile": "unknown",
            "primary_pct": 0,
            "bucket_pct": {key: 0 for key in bucket_minutes},
            "peak_hour": None,
        }

    bucket_pct = {
        key: round((value / total_minutes) * 100, 1)
        for key, value in bucket_minutes.items()
    }
    primary_profile = max(bucket_pct, key=bucket_pct.get)

    return {
        "primary_profile": primary_profile,
        "primary_pct": bucket_pct[primary_profile],
        "bucket_pct": bucket_pct,
        "peak_hour": peak_hour,
    }


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@app.get("/", include_in_schema=False)
def onboarding_home():
    """Serve the onboarding frontend."""
    index = FRONTEND_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=500, detail="Frontend assets are missing")
    return FileResponse(index)

@app.get("/health", response_model=HealthResponse)
def health():
    """Health check endpoint."""
    try:
        conn = get_connection()
        init_db(conn)
        conn.close()
        return {
            "status": "healthy",
            "message": "Spoolify API is running and database is accessible"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@app.get("/stats")
def stats():
    """Get comprehensive listening statistics."""
    try:
        conn = get_connection()
        init_db(conn)
        
        overall = get_overall_stats(conn)
        profile = get_listening_profile_data(conn)
        top_artists_data = get_top_artists(conn, limit=10)
        top_tracks_data = get_top_tracks(conn, limit=10)
        
        conn.close()
        
        # Format response
        payload = {
            "overall": overall,
            "profile": profile,
            "top_artists": [
                {"name": artist, "minutes": int(minutes)}
                for artist, minutes in top_artists_data
            ],
            "top_tracks": [
                {"name": track, "artist": artist, "minutes": int(minutes)}
                for track, artist, minutes in top_tracks_data
            ]
        }
        return _with_meta(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/top-artists")
def top_artists(limit: int = Query(10, ge=1, le=100)):
    """Get top artists by listening time."""
    try:
        conn = get_connection()
        init_db(conn)
        data = get_top_artists(conn, limit=limit)
        conn.close()
        
        payload = [{"name": artist, "minutes": int(minutes)} for artist, minutes in data]
        return _with_meta(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/top-tracks")
def top_tracks(limit: int = Query(10, ge=1, le=100)):
    """Get top tracks by listening time."""
    try:
        conn = get_connection()
        init_db(conn)
        data = get_top_tracks(conn, limit=limit)
        conn.close()
        
        payload = [
            {"name": track, "artist": artist, "minutes": int(minutes)}
            for track, artist, minutes in data
        ]
        return _with_meta(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/monthly")
def monthly() -> Dict[str, Any]:
    """Get monthly listening statistics."""
    try:
        conn = get_connection()
        init_db(conn)
        data = get_monthly_stats(conn)
        conn.close()
        
        payload = [
            {"month": month, "plays": plays, "minutes": int(minutes)}
            for month, plays, minutes in data
        ]
        return _with_meta(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/yearly")
def yearly() -> Dict[str, Any]:
    """Get yearly listening statistics."""
    try:
        conn = get_connection()
        init_db(conn)
        data = get_yearly_stats(conn)
        conn.close()
        
        payload = [
            {"year": year, "plays": plays, "minutes": int(minutes)}
            for year, plays, minutes in data
        ]
        return _with_meta(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/hourly")
def hourly() -> Dict[str, Any]:
    """Get hour-of-day listening statistics."""
    try:
        conn = get_connection()
        init_db(conn)
        data = get_hourly_stats(conn)
        conn.close()
        
        payload = [
            {"hour": hour, "plays": plays, "minutes": int(minutes)}
            for hour, plays, minutes in data
        ]
        return _with_meta(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/trends")
def trends() -> Dict[str, Any]:
    """Get yearly trend analysis."""
    try:
        conn = get_connection()
        init_db(conn)
        data = get_yearly_trend(conn)
        conn.close()
        return _with_meta(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/wrapped")
def wrapped(year: Optional[int] = Query(None, description="Specific year to analyze (defaults to most recent)")):
    """Get wrapped summary for a year."""
    try:
        conn = get_connection()
        init_db(conn)
        year_str = str(year) if year else None
        data = get_wrapped(conn, year_str)
        conn.close()
        
        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])
        
        wrapped_year = data.get("year") if isinstance(data, dict) else year
        return _with_meta(data, year=wrapped_year)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/onboarding/validate-archive")
def onboarding_validate_archive(payload: ArchivePathRequest) -> Dict[str, Any]:
    """Validate Spotify archive structure before import."""
    files = _discover_json_files(payload.path)
    source = str(Path(payload.path).expanduser())
    archive_type = "directory" if Path(payload.path).expanduser().is_dir() else "file"
    return _validate_archive_files(files, source_label=source, archive_type=archive_type)


@app.post("/onboarding/validate-archive-zip")
async def onboarding_validate_archive_zip(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Validate Spotify archive from uploaded ZIP file."""
    staged_files = _extract_zip_json_files(file)
    try:
        return _validate_archive_files(
            staged_files,
            source_label=file.filename or "uploaded.zip",
            archive_type="zip_upload"
        )
    finally:
        _cleanup_staged_files(staged_files)


@app.post("/onboarding/import")
def onboarding_import_archive(payload: OnboardingImportRequest) -> Dict[str, Any]:
    """Import Spotify archive files through onboarding flow."""
    files = _discover_json_files(payload.path)
    return _import_archive_files(files, mode=payload.mode)


@app.post("/onboarding/import-zip")
async def onboarding_import_archive_zip(
    file: UploadFile = File(...),
    mode: str = Form("historical_backfill")
) -> Dict[str, Any]:
    """Import Spotify archive from uploaded ZIP file."""
    staged_files = _extract_zip_json_files(file)
    try:
        return _import_archive_files(staged_files, mode=mode)
    finally:
        _cleanup_staged_files(staged_files)


@app.get("/dashboard-summary")
def dashboard_summary() -> Dict[str, Any]:
    """Get comprehensive dashboard summary with aggregated stats."""
    try:
        conn = get_connection()
        init_db(conn)
        
        # Get all the data needed for the dashboard
        overall = get_overall_stats(conn)
        profile = get_listening_profile_data(conn)
        date_range = get_date_range(conn)
        peak_month = get_peak_month(conn)
        unique_artists = get_unique_artist_count(conn)
        unique_tracks = get_unique_track_count(conn)
        
        # Get trends for insights
        trends_data = get_yearly_trend(conn)
        
        # Generate insights
        insights = []
        if trends_data and "insights" in trends_data:
            insights = trends_data.get("insights", [])[:3]
        
        # Add profile insight if available
        if profile:
            primary = profile.get("primary_profile", "").replace("_", " ").title()
            if primary:
                insights.insert(0, f"{primary} is your dominant listening period")
        
        # Build response
        payload = {
            "totals": {
                "total_plays": overall.get("total_plays", 0),
                "total_minutes_exact": round(overall.get("total_minutes_exact", 0), 2),
                "total_hours": overall.get("total_hours", 0),
                "unique_artists": unique_artists,
                "unique_tracks": unique_tracks,
                "date_range": {
                    "start": date_range.get("start"),
                    "end": date_range.get("end")
                }
            },
            "profile": {
                "primary": profile.get("primary_profile", "unknown"),
                "primary_pct": round(profile.get("primary_pct", 0), 1),
                "bucket_pct": profile.get("bucket_pct", {}),
                "peak_hour": profile.get("peak_hour")
            },
            "peaks": {
                "peak_month": peak_month,
                "peak_year": trends_data.get("peak_year") if trends_data else None
            },
            "trends": {
                "trend": trends_data.get("trend") if trends_data else "unknown",
                "segments": trends_data.get("trend_segments", {}) if trends_data else {}
            },
            "insights": insights[:5]  # Return up to 5 insights
        }
        
        conn.close()
        return _with_meta(payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/dashboard-summary-filtered")
def dashboard_summary_filtered(start: Optional[str] = None, end: Optional[str] = None) -> Dict[str, Any]:
    """Get dashboard summary filtered by date range (YYYY-MM format)."""
    try:
        # Validate date format
        if start:
            if len(start) != 7 or start[4] != "-":
                raise HTTPException(status_code=400, detail="start must be in YYYY-MM format")
        if end:
            if len(end) != 7 or end[4] != "-":
                raise HTTPException(status_code=400, detail="end must be in YYYY-MM format")
        
        conn = get_connection()
        init_db(conn)

        overall = get_overall_stats_filtered(conn, start, end)
        monthly_data = get_monthly_stats_filtered(conn, start, end)
        hourly_data = get_hourly_stats_filtered(conn, start, end)
        yearly_data = get_yearly_stats_filtered(conn, start, end)
        top_artists_data = get_top_artists_filtered(conn, limit=25, start_month=start, end_month=end)
        top_tracks_data = get_top_tracks_filtered(conn, limit=25, start_month=start, end_month=end)
        profile = _build_profile_from_hourly_rows(hourly_data)
        unique_artists = get_unique_artist_count_filtered(conn, start, end)
        unique_tracks = get_unique_track_count_filtered(conn, start, end)
        date_range = get_date_range_filtered(conn, start, end)
        peak_month = get_peak_month_filtered(conn, start, end)

        peak_year = None
        if yearly_data:
            peak_year = max(yearly_data, key=lambda row: row[2] or 0)[0]

        insights = []
        primary = profile.get("primary_profile", "unknown")
        if primary and primary != "unknown":
            insights.append(f"{primary.replace('_', ' ').title()} is your dominant listening period in this range")
        if peak_month:
            insights.append(f"{peak_month} is the strongest month in the selected range")

        summary_payload = {
            "totals": {
                "total_plays": overall.get("total_plays", 0),
                "total_minutes_exact": round(overall.get("total_minutes_exact", 0), 2),
                "total_hours": overall.get("total_hours", 0),
                "unique_artists": unique_artists,
                "unique_tracks": unique_tracks,
                "date_range": date_range
            },
            "profile": {
                "primary": profile.get("primary_profile", "unknown"),
                "primary_pct": round(profile.get("primary_pct", 0), 1),
                "bucket_pct": profile.get("bucket_pct", {}),
                "peak_hour": profile.get("peak_hour")
            },
            "peaks": {
                "peak_month": peak_month,
                "peak_year": peak_year
            },
            "trends": {
                "trend": "filtered_range",
                "segments": {}
            },
            "insights": insights[:5]
        }

        payload = {
            "summary": summary_payload,
            "monthly": [
                {"month": month, "plays": plays, "minutes": int(minutes)}
                for month, plays, minutes in monthly_data
            ],
            "hourly": [
                {"hour": hour, "plays": plays, "minutes": int(minutes)}
                for hour, plays, minutes in hourly_data
            ],
            "yearly": [
                {"year": year, "plays": plays, "minutes": int(minutes)}
                for year, plays, minutes in yearly_data
            ],
            "top_artists": [
                {"name": artist, "minutes": int(minutes)}
                for artist, minutes in top_artists_data
            ],
            "top_tracks": [
                {"name": track, "artist": artist, "minutes": int(minutes)}
                for track, artist, minutes in top_tracks_data
            ],
        }

        conn.close()
        return _with_meta(payload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/dashboard", include_in_schema=False)
def dashboard_page():
    """Serve the dashboard frontend."""
    dashboard_file = FRONTEND_DIR / "dashboard.html"
    if not dashboard_file.exists():
        raise HTTPException(status_code=500, detail="Dashboard assets are missing")
    return FileResponse(dashboard_file)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
