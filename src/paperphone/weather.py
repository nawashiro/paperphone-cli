from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx

from .errors import RuntimeFailure
from .paths import cache_dir

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ATTRIBUTION = "Weather data by Open-Meteo"

PERIOD_HOURS = (9, 12, 18)
PERIOD_LABELS = {9: "MORNING", 12: "AFTERNOON", 18: "EVENING"}

WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("Clear", "sunny"),
    1: ("Mainly Clear", "sun_cloud"),
    2: ("Partly Cloudy", "sun_cloud"),
    3: ("Clouds", "cloudy"),
    45: ("Fog", "cloudy"),
    48: ("Fog", "cloudy"),
    51: ("Drizzle", "rain"),
    53: ("Drizzle", "rain"),
    55: ("Drizzle", "rain"),
    56: ("Freezing Drizzle", "rain"),
    57: ("Freezing Drizzle", "rain"),
    61: ("Rain", "rain"),
    63: ("Rain", "rain"),
    65: ("Rain", "rain"),
    66: ("Freezing Rain", "rain"),
    67: ("Freezing Rain", "rain"),
    71: ("Snow", "snow"),
    73: ("Snow", "snow"),
    75: ("Snow", "snow"),
    77: ("Snow Grains", "snow"),
    80: ("Showers", "rain"),
    81: ("Showers", "rain"),
    82: ("Showers", "rain"),
    85: ("Snow Showers", "snow"),
    86: ("Snow Showers", "snow"),
    95: ("Thunderstorm", "thunder"),
    96: ("Thunderstorm", "thunder"),
    99: ("Thunderstorm", "thunder"),
}


@dataclass(frozen=True)
class WeatherPeriod:
    hour: int
    label: str
    temperature: int
    code: int
    name: str
    icon: str

    def as_record(self) -> dict[str, int]:
        return {"hour": self.hour, "temperature": self.temperature, "code": self.code}


@dataclass(frozen=True)
class WeatherReport:
    label: str
    date: dt.date
    periods: list[WeatherPeriod]
    cached: bool = False

    def period(self, hour: int) -> WeatherPeriod | None:
        for period in self.periods:
            if period.hour == hour:
                return period
        return None


def describe(code: int) -> tuple[str, str]:
    return WMO_CODES.get(code, ("Unknown", "cloudy"))


def _rounded(value: float) -> float:
    return round(value, 3)


def cache_path() -> Path:
    return cache_dir() / "weather.json"


def _build_period(hour: int, temperature: float, code: int) -> WeatherPeriod:
    name, icon = describe(code)
    return WeatherPeriod(
        hour=hour,
        label=PERIOD_LABELS[hour],
        temperature=int(temperature),
        code=code,
        name=name,
        icon=icon,
    )


def parse_payload(payload: dict, date: dt.date) -> list[WeatherPeriod]:
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    temperatures = hourly.get("temperature_2m") or []
    codes = hourly.get("weather_code") or []
    if len(times) != len(temperatures) or len(times) != len(codes):
        raise RuntimeFailure("Open-Meteo の応答が不正です")

    entries: list[tuple[dt.datetime, float, int]] = []
    for raw_time, raw_temperature, raw_code in zip(times, temperatures, codes, strict=False):
        try:
            moment = dt.datetime.fromisoformat(str(raw_time))
        except ValueError:
            continue
        if moment.date() != date:
            continue
        if raw_temperature is None or raw_code is None:
            continue
        entries.append((moment, float(raw_temperature), int(raw_code)))

    periods: list[WeatherPeriod] = []
    for hour in PERIOD_HOURS:
        target = dt.datetime.combine(date, dt.time(hour=hour))
        candidates = [entry for entry in entries if entry[0].date() == date]
        if not candidates:
            continue
        moment, temperature, code = min(
            candidates, key=lambda entry: abs((entry[0] - target).total_seconds())
        )
        periods.append(_build_period(hour, temperature, code))
    return periods


def fetch(latitude: float, longitude: float, zone_name: str, date: dt.date,
          *, client: httpx.Client | None = None) -> list[WeatherPeriod]:
    params = {
        "latitude": f"{latitude:.4f}",
        "longitude": f"{longitude:.4f}",
        "hourly": "temperature_2m,weather_code",
        "timezone": zone_name,
        "start_date": date.isoformat(),
        "end_date": date.isoformat(),
    }
    owns_client = client is None
    http = client or httpx.Client(timeout=12.0, headers={"User-Agent": "paperphone"})
    try:
        response = http.get(FORECAST_URL, params=params)
        response.raise_for_status()
        return parse_payload(response.json(), date)
    except httpx.HTTPError as exc:
        raise RuntimeFailure(f"Open-Meteo から予報を取得できません: {exc}") from exc
    finally:
        if owns_client:
            http.close()


def write_cache(latitude: float, longitude: float, label: str, periods: list[WeatherPeriod]) -> None:
    path = cache_path()
    payload = {
        "latitude": _rounded(latitude),
        "longitude": _rounded(longitude),
        "label": label,
        "periods": [period.as_record() for period in periods],
    }
    temp_name = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".weather.", suffix=".json", dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        os.replace(temp_name, path)
    except OSError:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except OSError:
                pass


def read_cache(latitude: float, longitude: float) -> list[WeatherPeriod] | None:
    path = cache_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        cached_latitude = float(payload.get("latitude"))
        cached_longitude = float(payload.get("longitude"))
    except (TypeError, ValueError):
        return None
    if cached_latitude != _rounded(latitude) or cached_longitude != _rounded(longitude):
        return None
    periods: list[WeatherPeriod] = []
    for record in payload.get("periods") or []:
        try:
            hour = int(record["hour"])
            temperature = int(record["temperature"])
            code = int(record["code"])
        except (KeyError, TypeError, ValueError):
            continue
        if hour in PERIOD_LABELS:
            periods.append(_build_period(hour, temperature, code))
    periods.sort(key=lambda period: PERIOD_HOURS.index(period.hour))
    return periods or None


def get_report(
    latitude: float,
    longitude: float,
    label: str,
    zone,
    date: dt.date,
    *,
    warn,
    client: httpx.Client | None = None,
) -> WeatherReport:
    try:
        periods = fetch(latitude, longitude, zone.key, date, client=client)
        if periods:
            write_cache(latitude, longitude, label, periods)
            return WeatherReport(label=label, date=date, periods=periods)
    except RuntimeFailure as exc:
        warn(str(exc))
    cached = read_cache(latitude, longitude)
    if cached:
        warn("天気は前回取得した予報を使います")
        return WeatherReport(label=label, date=date, periods=cached, cached=True)
    return WeatherReport(label=label, date=date, periods=[])
