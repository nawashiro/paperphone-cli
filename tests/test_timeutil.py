from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from paperphone.timeutil import cover_date, day_bounds, output_path, parse_date, resolve_date, today


def test_date_boundary_between_utc_and_tokyo():
    utc = dt.datetime(2026, 11, 16, 15, 30, tzinfo=dt.UTC)
    assert today(ZoneInfo("UTC"), utc) == dt.date(2026, 11, 16)
    assert today(ZoneInfo("Asia/Tokyo"), utc) == dt.date(2026, 11, 17)


def test_resolve_date_uses_zone_today():
    utc = dt.datetime(2026, 11, 16, 15, 30, tzinfo=dt.UTC)
    assert resolve_date(ZoneInfo("Asia/Tokyo"), None, utc) == dt.date(2026, 11, 17)


def test_resolve_date_prefers_explicit_date():
    utc = dt.datetime(2026, 11, 16, 15, 30, tzinfo=dt.UTC)
    assert resolve_date(ZoneInfo("Asia/Tokyo"), "2026-01-02", utc) == dt.date(2026, 1, 2)


def test_parse_date_rejects_invalid_calendar_date():
    try:
        parse_date("2026-02-30")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid date accepted")


def test_dst_day_bounds():
    start, end = day_bounds(dt.date(2026, 11, 1), ZoneInfo("America/New_York"))
    assert start.utcoffset() != end.utcoffset()
    assert (end.astimezone(dt.UTC) - start.astimezone(dt.UTC)).total_seconds() == 25 * 3600


def test_default_output_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = output_path(None, dt.date(2026, 11, 17))
    assert path == (tmp_path / "paperphone-2026-11-17.pdf").resolve()


def test_cover_date_format():
    assert cover_date(dt.date(2026, 11, 17)) == "17 November 2026"
