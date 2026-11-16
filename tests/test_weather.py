from __future__ import annotations

import datetime as dt
import json
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx

from paperphone import weather


def payload(times, temperatures, codes):
    return {
        "hourly": {
            "time": times,
            "temperature_2m": temperatures,
            "weather_code": codes,
        }
    }


def test_parse_picks_nine_twelve_eighteen_and_truncates():
    data = payload(
        [f"2026-11-17T{hour:02d}:00" for hour in range(24)],
        [float(hour) for hour in range(24)],
        [0] * 24,
    )
    data["hourly"]["temperature_2m"][9] = 12.8
    data["hourly"]["temperature_2m"][12] = 15.2
    data["hourly"]["weather_code"][12] = 3
    periods = weather.parse_payload(data, dt.date(2026, 11, 17))
    assert [period.label for period in periods] == ["MORNING", "AFTERNOON", "EVENING"]
    assert periods[0].temperature == 12
    assert periods[1].name == "Clouds"
    assert periods[1].icon == "cloudy"


def test_unknown_code_falls_back():
    name, icon = weather.describe(12345)
    assert name == "Unknown"
    assert icon == "cloudy"


@respx.mock
def test_fetch_sends_timezone_and_dates():
    route = respx.get(weather.FORECAST_URL).mock(
        return_value=httpx.Response(
            200,
            json=payload(
                ["2026-11-17T09:00", "2026-11-17T12:00", "2026-11-17T18:00"],
                [9.0, 12.0, 18.0],
                [0, 3, 61],
            ),
        )
    )
    periods = weather.fetch(35.6812, 139.7671, "Asia/Tokyo", dt.date(2026, 11, 17))
    request = route.calls[0].request
    assert request.url.params["timezone"] == "Asia/Tokyo"
    assert request.url.params["start_date"] == "2026-11-17"
    assert len(periods) == 3


def test_cache_matches_location(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    periods = [
        weather.WeatherPeriod(9, "MORNING", 9, 0, "Clear", "sunny"),
    ]
    weather.write_cache(35.68124, 139.76714, "Tokyo", periods)
    cached = weather.read_cache(35.6812, 139.7671)
    assert cached == periods
    assert weather.read_cache(35.0, 139.0) is None


def test_cache_payload_is_json(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    periods = [weather.WeatherPeriod(9, "MORNING", 9, 0, "Clear", "sunny")]
    weather.write_cache(1.0, 2.0, "X", periods)
    data = json.loads((tmp_path / "paperphone" / "weather.json").read_text())
    assert data["latitude"] == 1.0
    assert data["periods"][0]["temperature"] == 9


def test_get_report_uses_cache_on_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    periods = [weather.WeatherPeriod(9, "MORNING", 7, 0, "Clear", "sunny")]
    weather.write_cache(35.6812, 139.7671, "Tokyo", periods)
    warnings = []

    with respx.mock:
        respx.get(weather.FORECAST_URL).mock(side_effect=httpx.ConnectError("offline"))
        report = weather.get_report(
            35.6812,
            139.7671,
            "Tokyo",
            ZoneInfo("Asia/Tokyo"),
            dt.date(2026, 11, 17),
            warn=warnings.append,
        )
    assert report.cached is True
    assert report.periods == periods
    assert warnings


def test_get_report_without_cache_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    warnings = []
    with respx.mock:
        respx.get(weather.FORECAST_URL).mock(side_effect=httpx.ConnectError("offline"))
        report = weather.get_report(
            1.0,
            2.0,
            "Nowhere",
            ZoneInfo("UTC"),
            dt.date(2026, 11, 17),
            warn=warnings.append,
        )
    assert report.periods == []
    assert report.label == "Nowhere"


def test_get_report_writes_cache_on_success(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    with respx.mock:
        respx.get(weather.FORECAST_URL).mock(
            return_value=httpx.Response(
                200,
                json=payload(
                    ["2026-11-17T09:00", "2026-11-17T12:00", "2026-11-17T18:00"],
                    [9, 12, 18],
                    [0, 3, 61],
                ),
            )
        )
        report = weather.get_report(
            35.0,
            139.0,
            "Tokyo",
            ZoneInfo("Asia/Tokyo"),
            dt.date(2026, 11, 17),
            warn=lambda message: pytest.fail(message),
        )
    assert not report.cached
    assert weather.read_cache(35.0, 139.0) is not None
