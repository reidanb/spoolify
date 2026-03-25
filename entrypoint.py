#!/usr/bin/env python3
"""
Spoolify entry point.
Routes to CLI mode (main.py) or API mode (api.py) based on command.

Usage:
  python entrypoint.py import <path>      # CLI: Import data
  python entrypoint.py stats              # CLI: Show statistics
  python entrypoint.py serve              # API: Start FastAPI server
"""

import sys
import os


def run_cli():
    """Run CLI interface."""
    from main import main
    main()


def run_api():
    """Run API server."""
    try:
        import uvicorn
    except ImportError:
        print("Error: FastAPI and uvicorn are required for API mode.")
        print("Install with: pip install fastapi uvicorn")
        sys.exit(1)
    
    from api import app
    
    # Parse optional host:port from remaining args
    host = os.environ.get("SPOOLIFY_API_HOST", "0.0.0.0")
    port = int(os.environ.get("SPOOLIFY_API_PORT", "8000"))
    
    print(f"Starting Spoolify API on {host}:{port}")
    print(f"Documentation: http://localhost:{port}/docs")
    uvicorn.run(app, host=host, port=port)


def main():
    """Main entry point: route to CLI or API."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python entrypoint.py serve              Start FastAPI server")
        print("  python entrypoint.py <cli-command> ...  Run CLI command")
        print()
        print("Available CLI commands:")
        print("  import <path>    Import Spotify JSON file or directory")
        print("  stats            Show overall statistics")
        print("  top-artists      Show top 10 artists by listening time")
        print("  top-tracks       Show top 10 tracks by listening time")
        print("  monthly          Show monthly listening stats")
        print("  yearly           Show yearly listening stats")
        print("  hourly           Show hour-of-day listening patterns")
        print("  trends           Show yearly trend analysis (JSON format)")
        print("  insights         Show listening insights and trends")
        print("  wrapped [--year <year>]  Show yearly wrapped summary")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "serve":
        run_api()
    else:
        # Run as CLI
        run_cli()


if __name__ == "__main__":
    main()
