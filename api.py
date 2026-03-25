"""
FastAPI service for Spoolify.
Exposes analytics endpoints for read-only access to listening data.
"""

from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from db import get_connection, init_db
from query_data import (
    get_top_artists, get_top_tracks, get_monthly_stats, 
    get_yearly_stats, get_hourly_stats, get_overall_stats,
    get_listening_profile_data
)
from queries import get_yearly_trend, get_wrapped

app = FastAPI(
    title="Spoolify API",
    description="Read-only FastAPI service for Spotify listening analytics",
    version="1.0.0"
)


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


# ==============================================================================
# ENDPOINTS
# ==============================================================================

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
