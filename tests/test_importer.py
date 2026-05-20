import json
import sqlite3
import tempfile
import os
import pytest
from db import init_db
from importer import generate_hash, import_file_stats


def _make_db():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    return conn


def _write_json(path, entries):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f)


ENTRY = {
    "ts": "2023-06-01T10:00:00Z",
    "spotify_track_uri": "spotify:track:abc123",
    "master_metadata_track_name": "Song A",
    "master_metadata_album_artist_name": "Artist A",
    "master_metadata_album_album_name": "Album A",
    "ms_played": 240_000,
    "platform": "android",
    "skipped": False,
}


# ── generate_hash ─────────────────────────────────────────────────────────────

class TestGenerateHash:
    def test_deterministic(self):
        assert generate_hash(ENTRY) == generate_hash(ENTRY)

    def test_differs_on_ts(self):
        other = {**ENTRY, "ts": "2023-06-01T11:00:00Z"}
        assert generate_hash(ENTRY) != generate_hash(other)

    def test_differs_on_uri(self):
        other = {**ENTRY, "spotify_track_uri": "spotify:track:xyz"}
        assert generate_hash(ENTRY) != generate_hash(other)

    def test_differs_on_ms_played(self):
        other = {**ENTRY, "ms_played": 999}
        assert generate_hash(ENTRY) != generate_hash(other)

    def test_missing_fields_do_not_raise(self):
        assert generate_hash({}) is not None


# ── import_file_stats ─────────────────────────────────────────────────────────

class TestImportFileStats:
    def test_basic_import(self):
        conn = _make_db()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump([ENTRY], f)
            path = f.name
        try:
            stats = import_file_stats(conn, path)
            assert stats["inserted"] == 1
            assert stats["duplicates"] == 0
            assert stats["attempted"] == 1
        finally:
            os.unlink(path)
            conn.close()

    def test_duplicate_skipped(self):
        conn = _make_db()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump([ENTRY, ENTRY], f)
            path = f.name
        try:
            stats = import_file_stats(conn, path)
            assert stats["inserted"] == 1
            assert stats["duplicates"] == 1
        finally:
            os.unlink(path)
            conn.close()

    def test_reimport_same_file_is_idempotent(self):
        conn = _make_db()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump([ENTRY], f)
            path = f.name
        try:
            import_file_stats(conn, path)
            stats = import_file_stats(conn, path)
            assert stats["inserted"] == 0
            assert stats["duplicates"] == 1
        finally:
            os.unlink(path)
            conn.close()

    def test_missing_track_uri_skipped(self):
        conn = _make_db()
        entry = {**ENTRY, "spotify_track_uri": None}
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump([entry], f)
            path = f.name
        try:
            stats = import_file_stats(conn, path)
            assert stats["inserted"] == 0
            assert stats["skipped_missing_track_uri"] == 1
        finally:
            os.unlink(path)
            conn.close()
