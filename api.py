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
    get_listening_profile_data
)
from queries import get_yearly_trend, get_wrapped

app = FastAPI(
    title="Spoolify API",
    description="FastAPI service for Spotify listening analytics and onboarding",
    version="1.0.0"
)

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
        with zip_path.open("wb") as f:
            upload.file.seek(0)
            shutil.copyfileobj(upload.file, f)

        try:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(temp_dir_path)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid ZIP archive")

        extracted_files = sorted(p for p in temp_dir_path.rglob("*.json") if p.is_file())
        if not extracted_files:
            raise HTTPException(status_code=400, detail="No .json files found inside ZIP archive")

        staged_dir = Path(tempfile.mkdtemp(prefix="spoolify_zip_staged_"))
        staged_files: List[Path] = []
        for idx, source_file in enumerate(extracted_files):
            # Keep original file names for export-type detection while avoiding collisions.
            target_dir = staged_dir / f"{idx:04d}"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / source_file.name
            shutil.copy2(source_file, target)
            staged_files.append(target)

    return staged_files


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


@app.get("/stats", response_model=StatsResponse)
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
        return {
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/top-artists", response_model=List[Artist])
def top_artists(limit: int = Query(10, ge=1, le=100)):
    """Get top artists by listening time."""
    try:
        conn = get_connection()
        init_db(conn)
        data = get_top_artists(conn, limit=limit)
        conn.close()
        
        return [{"name": artist, "minutes": int(minutes)} for artist, minutes in data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/top-tracks", response_model=List[Track])
def top_tracks(limit: int = Query(10, ge=1, le=100)):
    """Get top tracks by listening time."""
    try:
        conn = get_connection()
        init_db(conn)
        data = get_top_tracks(conn, limit=limit)
        conn.close()
        
        return [
            {"name": track, "artist": artist, "minutes": int(minutes)}
            for track, artist, minutes in data
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/monthly")
def monthly() -> List[MonthlyEntry]:
    """Get monthly listening statistics."""
    try:
        conn = get_connection()
        init_db(conn)
        data = get_monthly_stats(conn)
        conn.close()
        
        return [
            {"month": month, "plays": plays, "minutes": int(minutes)}
            for month, plays, minutes in data
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/yearly")
def yearly() -> List[YearlyEntry]:
    """Get yearly listening statistics."""
    try:
        conn = get_connection()
        init_db(conn)
        data = get_yearly_stats(conn)
        conn.close()
        
        return [
            {"year": year, "plays": plays, "minutes": int(minutes)}
            for year, plays, minutes in data
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/hourly")
def hourly() -> List[HourlyEntry]:
    """Get hour-of-day listening statistics."""
    try:
        conn = get_connection()
        init_db(conn)
        data = get_hourly_stats(conn)
        conn.close()
        
        return [
            {"hour": hour, "plays": plays, "minutes": int(minutes)}
            for hour, plays, minutes in data
        ]
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
        return data
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
        
        return data
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
