import sqlite3
import pytest
from db import init_db
from query_data import _is_partial_year, get_wrapped, get_yearly_trend


def _make_db():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    return conn


def _insert(conn, rows):
    conn.executemany(
        "INSERT INTO plays (ts, track_uri, track_name, artist_name, ms_played, hash) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()


# ── _is_partial_year ──────────────────────────────────────────────────────────

class TestIsPartialYear:
    def test_last_year_is_partial(self):
        year_data = {2022: {"minutes": 1000}, 2023: {"minutes": 400}}
        assert _is_partial_year(year_data, [2022, 2023]) is True

    def test_last_year_not_partial(self):
        year_data = {2022: {"minutes": 1000}, 2023: {"minutes": 600}}
        assert _is_partial_year(year_data, [2022, 2023]) is False

    def test_exactly_at_threshold_is_not_partial(self):
        # < 0.5, so exactly 0.5 should not be partial
        year_data = {2022: {"minutes": 1000}, 2023: {"minutes": 500}}
        assert _is_partial_year(year_data, [2022, 2023]) is False

    def test_single_year_never_partial(self):
        year_data = {2022: {"minutes": 1000}}
        assert _is_partial_year(year_data, [2022]) is False

    def test_empty_never_partial(self):
        assert _is_partial_year({}, []) is False


# ── get_wrapped ───────────────────────────────────────────────────────────────

class TestGetWrapped:
    def test_no_data_returns_error(self):
        conn = _make_db()
        result = get_wrapped(conn)
        assert "error" in result
        conn.close()

    def test_returns_correct_year(self):
        conn = _make_db()
        _insert(conn, [
            ("2023-06-01T10:00:00", "uri:1", "Song A", "Artist A", 300_000, "h1"),
            ("2023-07-01T10:00:00", "uri:2", "Song B", "Artist B", 180_000, "h2"),
        ])
        result = get_wrapped(conn)
        assert result["year"] == 2023
        assert result["total_plays"] == 2
        conn.close()

    def test_skips_partial_year(self):
        conn = _make_db()
        rows = [
            (f"2022-06-{i+1:02d}T10:00:00", f"uri:{i}", f"Song {i}", "Artist", 600_000, f"h{i}")
            for i in range(20)
        ]
        # 2023 has far less data than 2022 — should be treated as partial
        rows.append(("2023-01-01T10:00:00", "uri:99", "Song X", "Artist", 60_000, "h99"))
        _insert(conn, rows)
        result = get_wrapped(conn)
        assert result["year"] == 2022
        conn.close()

    def test_specific_year_requested(self):
        conn = _make_db()
        _insert(conn, [
            ("2022-06-01T10:00:00", "uri:1", "Song A", "Artist A", 600_000, "h1"),
            ("2022-07-01T10:00:00", "uri:2", "Song B", "Artist B", 600_000, "h2"),
            ("2023-06-01T10:00:00", "uri:3", "Song C", "Artist C", 600_000, "h3"),
        ])
        result = get_wrapped(conn, year="2022")
        assert result["year"] == 2022
        conn.close()

    def test_unknown_year_returns_error(self):
        conn = _make_db()
        _insert(conn, [
            ("2023-06-01T10:00:00", "uri:1", "Song A", "Artist A", 300_000, "h1"),
        ])
        result = get_wrapped(conn, year="2019")
        assert "error" in result
        conn.close()


# ── get_yearly_trend ──────────────────────────────────────────────────────────

class TestGetYearlyTrend:
    def test_no_data(self):
        conn = _make_db()
        result = get_yearly_trend(conn)
        assert result["trend"] == "stable"
        assert "No data available" in result["insights"]
        conn.close()

    def test_increasing_trend(self):
        conn = _make_db()
        _insert(conn, [
            ("2021-06-01T10:00:00", "uri:1", "Song A", "Artist", 600_000, "h1"),
            ("2021-07-01T10:00:00", "uri:2", "Song B", "Artist", 600_000, "h2"),
            ("2022-06-01T10:00:00", "uri:3", "Song C", "Artist", 1_200_000, "h3"),
            ("2022-07-01T10:00:00", "uri:4", "Song D", "Artist", 1_200_000, "h4"),
            ("2023-06-01T10:00:00", "uri:5", "Song E", "Artist", 1_800_000, "h5"),
            ("2023-07-01T10:00:00", "uri:6", "Song F", "Artist", 1_800_000, "h6"),
        ])
        result = get_yearly_trend(conn)
        assert result["trend"] == "increasing"
        assert result["peak_year"] == 2023
        conn.close()

    def test_partial_year_flagged(self):
        conn = _make_db()
        rows = [
            (f"2022-06-{i+1:02d}T10:00:00", f"uri:{i}", f"Song {i}", "Artist", 600_000, f"h{i}")
            for i in range(20)
        ]
        rows.append(("2023-01-01T10:00:00", "uri:99", "Song X", "Artist", 60_000, "h99"))
        _insert(conn, rows)
        result = get_yearly_trend(conn)
        assert result["yearly_changes"][2023].get("partial") is True
        conn.close()
