from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

_DATE_FORMAT = "%Y-%m-%d"


def parse_date(text: str) -> dt.date:
    try:
        return dt.datetime.strptime(text, _DATE_FORMAT).date()
    except ValueError as exc:
        raise ValueError(f"YYYY-MM-DD の日付ではありません: {text}") from exc


def today(zone: ZoneInfo, now: dt.datetime | None = None) -> dt.date:
    moment = now or dt.datetime.now(dt.UTC)
    return moment.astimezone(zone).date()


def resolve_date(zone: ZoneInfo, date_text: str | None, now: dt.datetime | None = None) -> dt.date:
    if date_text:
        return parse_date(date_text)
    return today(zone, now)


def output_path(out: str | None, date: dt.date) -> Path:
    if out:
        return Path(out).expanduser().resolve()
    return (Path.cwd() / f"paperphone-{date.isoformat()}.pdf").resolve()


def cover_date(date: dt.date) -> str:
    return f"{date.day:02d} {date.strftime('%B')} {date.year}"


def weather_date(date: dt.date) -> str:
    return f"{date.strftime('%A')} {date.day:02d}, {date.strftime('%B')}"


def clock(moment: dt.datetime) -> str:
    return moment.strftime("%H:%M")


def day_bounds(date: dt.date, zone: ZoneInfo) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(date, dt.time.min, tzinfo=zone)
    end = dt.datetime.combine(date + dt.timedelta(days=1), dt.time.min, tzinfo=zone)
    return start, end
