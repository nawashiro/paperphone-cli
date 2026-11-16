from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        elif raw.strip():
            lines.append(raw.strip())
    return lines


def _parse_value(name: str, params: dict[str, str], value: str):
    if name in ("DTSTART", "DTEND", "DUE"):
        if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
            return dt.date(int(value[:4]), int(value[4:6]), int(value[6:8]))
        return dt.datetime.strptime(value.rstrip("Z"), "%Y%m%dT%H%M%S").replace(
            tzinfo=dt.UTC
        )
    return value


def _components(path: Path, kind: str) -> list[dict]:
    result: list[dict] = []
    current = None
    for line in _unfold(path.read_text(encoding="utf-8")):
        if line == f"BEGIN:{kind}":
            current = {}
        elif line == f"END:{kind}":
            if current is not None:
                result.append(current)
            current = None
        elif current is not None:
            name, _, raw = line.partition(":")
            params = {}
            if ";" in name:
                name, raw_params = name.split(";", 1)
                for item in raw_params.split(";"):
                    key, _, value = item.partition("=")
                    params[key] = value
            current[name] = _parse_value(name, params, raw)
    return result


@dataclass
class FixtureEvent:
    uid: str
    summary: str
    start: dt.datetime | dt.date
    end: dt.datetime | dt.date
    rrule: str = ""


def calendar_events() -> list[FixtureEvent]:
    events = []
    for data in _components(FIXTURES / "calendar.ics", "VEVENT"):
        events.append(
            FixtureEvent(
                uid=str(data.get("UID", "")),
                summary=str(data.get("SUMMARY", "")),
                start=data["DTSTART"],
                end=data["DTEND"],
                rrule=str(data.get("RRULE", "")),
            )
        )
    return events


def task_components() -> list[dict]:
    return _components(FIXTURES / "tasks.ics", "VTODO")


def contact_rows() -> list[dict]:
    return _components(FIXTURES / "contacts.vcf", "VCARD")


class FakeICalTime:
    def __init__(self, value: dt.datetime | dt.date):
        self.value = value

    def is_date(self) -> bool:
        return isinstance(self.value, dt.date) and not isinstance(self.value, dt.datetime)

    def get_year(self) -> int:
        return self.value.year

    def get_month(self) -> int:
        return self.value.month

    def get_day(self) -> int:
        return self.value.day


class FakeCalDateTime:
    def __init__(self, value: FakeICalTime):
        self.value = value

    def get_value(self) -> FakeICalTime:
        return self.value


class FakeText:
    def __init__(self, value: str):
        self.value = value

    def get_value(self) -> str:
        return self.value


class FakeStatus:
    def __init__(self, name: str):
        self.value_nick = name

    def __str__(self) -> str:
        return self.value_nick


class FakeEventComponent:
    def __init__(self, summary: str, dtstart: FakeICalTime, uid: str = ""):
        self._summary = summary
        self._dtstart = dtstart
        self._uid = uid

    def get_summary(self) -> str:
        return self._summary

    def get_dtstart(self) -> FakeICalTime:
        return self._dtstart

    def get_uid(self) -> str:
        return self._uid


class FakeTaskComponent:
    def __init__(self, data: dict):
        self.data = data

    def get_summary(self) -> FakeText:
        return FakeText(str(self.data.get("SUMMARY", "")))

    def get_uid(self) -> str:
        return str(self.data.get("UID", ""))

    def get_status(self) -> FakeStatus:
        return FakeStatus(str(self.data.get("STATUS", "NEEDS-ACTION")))

    def get_completed(self):
        if "COMPLETED" in self.data:
            return FakeICalTime(self.data["COMPLETED"])
        return None

    def get_due(self):
        due = self.data.get("DUE")
        if due is None:
            return None
        return FakeCalDateTime(FakeICalTime(due))


def _expand(event: FixtureEvent) -> list[FixtureEvent]:
    if not event.rrule:
        return [event]
    match = re.search(r"COUNT=(\d+)", event.rrule)
    count = int(match.group(1)) if match else 1
    result = []
    for index in range(count):
        if isinstance(event.start, dt.datetime):
            start = event.start + dt.timedelta(days=index)
        else:
            start = event.start + dt.timedelta(days=index)
        end = event.end + dt.timedelta(days=index) if isinstance(event.end, dt.datetime) else event.end
        result.append(FixtureEvent(event.uid, event.summary, start, end))
    return result


class FakeECalClient:
    def __init__(self, events=None, tasks=None):
        self.events = events if events is not None else calendar_events()
        self.tasks = tasks if tasks is not None else task_components()

    def generate_instances_sync(self, start, end, cancellable, callback, data):
        start_dt = dt.datetime.fromtimestamp(start, dt.UTC)
        end_dt = dt.datetime.fromtimestamp(end, dt.UTC)
        for event in self.events:
            for instance in _expand(event):
                if isinstance(instance.start, dt.datetime):
                    instance_start = instance.start
                    instance_end = instance.end
                else:
                    instance_start = dt.datetime.combine(
                        instance.start, dt.time(0, 0), tzinfo=dt.UTC
                    )
                    instance_end = dt.datetime.combine(
                        instance.end, dt.time(0, 0), tzinfo=dt.UTC
                    )
                if instance_start >= end_dt or instance_end <= start_dt:
                    continue
                keep_going = callback(
                    FakeEventComponent(
                        instance.summary, FakeICalTime(instance.start), instance.uid
                    ),
                    int(instance_start.timestamp()),
                    int(instance_end.timestamp()),
                    data,
                )
                if not keep_going:
                    return

    def get_object_list_as_comps_sync(self, sexp, cancellable):
        return (True, [FakeTaskComponent(data) for data in self.tasks])


class FakeContact:
    def __init__(self, data: dict):
        self.data = data

    def get_const(self, field: str):
        return self.data.get(field)

    def to_string(self, version: int = 1) -> str:
        lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"UID:{self.data.get('UID', '')}",
            f"FN:{self.data.get('FN', '')}",
        ]
        for key in ("TEL", "TEL-MOBILE", "TEL-HOME", "TEL-BUSINESS"):
            if self.data.get(key):
                lines.append(f"TEL:{self.data[key]}")
        lines.append("END:VCARD")
        return "\r\n".join(lines)


class FakeContactFields:
    UID = "UID"
    FULL_NAME = "FN"
    PHONE_PRIMARY = "TEL"
    PHONE_MOBILE = "TEL-MOBILE"
    PHONE_HOME = "TEL-HOME"
    PHONE_BUSINESS = "TEL-BUSINESS"


class FakeBookClient:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else contact_rows()

    def get_contacts_sync(self, sexp, cancellable):
        return (True, [FakeContact(row) for row in self.rows])

    def get_contacts_uids_sync(self, sexp, cancellable):
        return [str(row.get("UID", "")) for row in self.rows]


class FakeSource:
    def __init__(self, uid: str, name: str, extensions: set[str]):
        self.uid = uid
        self.name = name
        self.extensions = set(extensions)

    def has_extension(self, name: str) -> bool:
        return name in self.extensions

    def get_uid(self) -> str:
        return self.uid

    def get_display_name(self) -> str:
        return self.name

    def get_extension(self, name: str):
        return SimpleNamespace()

    def remove_sync(self, cancellable) -> None:
        return None


class FakeRegistry:
    def __init__(self, sources: list[FakeSource]):
        self.sources = list(sources)

    def list_sources(self, extension):
        return list(self.sources)

    def ref_source(self, uid):
        for source in self.sources:
            if source.uid == uid:
                return source
        raise LookupError(uid)


class FakeCredentialStore:
    def __init__(self, passwords: dict[str, str] | None = None):
        self.passwords = passwords or {}

    def has_password(self, source) -> bool:
        return source.get_uid() in self.passwords

    def lookup_password(self, source):
        return self.passwords.get(source.get_uid())

    def store_password(self, source, user, password) -> None:
        self.passwords[source.get_uid()] = password

    def delete_password(self, source) -> None:
        self.passwords.pop(source.get_uid(), None)


class FakeDavBackend:
    def __init__(self, managed=None):

        self._managed = list(managed or [])
        self.created: list[dict] = []
        self.removed: list[str] = []
        self.fail_verify = False

    def managed_sources(self):
        return list(self._managed)

    def find_duplicate(self, kind, url, user):
        for info in self._managed:
            if getattr(info, "kind", None) == kind:
                return info
        return None

    def create(self, kind, url, name, user, password):
        from paperphone.model import SourceInfo

        uid = f"paperphone-{len(self.created) + 1}"
        self.created.append(
            {"uid": uid, "kind": kind, "url": url, "name": name, "user": user}
        )
        self._managed.append(SourceInfo(uid, name, kind, "paperphone", "keyring"))
        return uid

    def verify(self, uid, kind):
        if self.fail_verify:
            from paperphone.errors import RuntimeFailure

            raise RuntimeFailure("verify failed")

    def remove(self, uid):
        self.removed.append(uid)
        self._managed = [info for info in self._managed if info.uid != uid]


@pytest.fixture
def sample_config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        """
[booklet]
name = "Aki"
timezone = "Asia/Tokyo"

[panels]
contacts = true
calendar = true
tasks = true
notes = true
paper_app = true

[sources]
calendars = ["cal-uid"]
contacts = ["contact-1", "contact-2"]
tasks = ["tasks-uid"]
""",
        encoding="utf-8",
    )
    return path
