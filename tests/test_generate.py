from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from conftest import (
    FakeBookClient,
    FakeCredentialStore,
    FakeRegistry,
    FakeSource,
    FakeUnreadableContact,
)
from pypdf import PdfReader

from paperphone import eds, generate, maps, weather
from paperphone.config import load_config
from paperphone.errors import RuntimeFailure
from paperphone.model import Contact, Event, Task

DATE = dt.date(2026, 11, 17)
ZONE = ZoneInfo("Asia/Tokyo")


def write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")
    return path


def base_config(tmp_path: Path, extra_panels: str = "", extra: str = "") -> Path:
    return write_config(
        tmp_path,
        f"""
[booklet]
name = "Aki"
timezone = "Asia/Tokyo"

[panels]
contacts = true
calendar = true
tasks = true
notes = true
paper_app = true
{extra_panels}

[sources]
calendars = ["cal-uid"]
contacts = ["contact-1"]
tasks = ["tasks-uid"]
{extra}
""",
    )


def patch_eds(monkeypatch, *, fail_calendar=False):
    registry = FakeRegistry(
        [
            FakeSource("cal-uid", "Calendar", {eds.SOURCE_CALENDAR}),
            FakeSource("tasks-uid", "Tasks", {eds.SOURCE_TASK_LIST}),
            FakeSource("book-uid", "Contacts", {eds.SOURCE_ADDRESS_BOOK}),
        ]
    )
    monkeypatch.setattr(eds, "open_registry", lambda: registry)
    monkeypatch.setattr(eds, "CredentialStore", lambda registry: FakeCredentialStore())
    monkeypatch.setattr(
        eds,
        "read_events",
        lambda source, start, end, zone: (_ for _ in ()).throw(RuntimeFailure("calendar down"))
        if fail_calendar
        else [
            Event(
                "Standup",
                dt.datetime(2026, 11, 17, 9, tzinfo=zone),
                dt.datetime(2026, 11, 17, 10, tzinfo=zone),
            )
        ],
    )
    monkeypatch.setattr(eds, "read_tasks", lambda source: [Task("Pay rent", DATE)])
    monkeypatch.setattr(
        eds,
        "read_contacts",
        lambda source, warn=None: [Contact("contact-1", "Aki Tanaka", "123")],
    )


def test_generate_offline_still_writes_pdf(tmp_path, monkeypatch):
    config_path = base_config(
        tmp_path,
        extra_panels="weather = true\nmap = true\n",
        extra="""
[weather]
latitude = 35.6812
longitude = 139.7671
label = "Tokyo"

[maps]
[maps.from]
latitude = 35.68
longitude = 139.76
label = "Home"
address = ["1-1 Chiyoda", "Tokyo"]
[maps.to]
latitude = 35.69
longitude = 139.70
label = "Station"
address = ["2-2 Chuo", "Tokyo"]
""",
    )
    config = load_config(config_path)
    patch_eds(monkeypatch)
    monkeypatch.setattr(
        weather, "fetch", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeFailure("offline"))
    )
    monkeypatch.setattr(
        maps, "fetch_mosaic", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeFailure("offline"))
    )
    out = generate.generate(config, date=DATE, zone=ZONE, out=tmp_path / "book.pdf")
    reader = PdfReader(str(out))
    assert len(reader.pages) == 2
    text = reader.pages[0].extract_text()
    assert "AKI TANAKA" in text
    assert "Standup" in text


def test_weather_is_not_fetched_when_disabled(tmp_path, monkeypatch):
    config_path = write_config(
        tmp_path,
        """
[booklet]
name = "Aki"
[panels]
notes = true
""",
    )
    config = load_config(config_path)
    monkeypatch.setattr(
        weather,
        "get_report",
        lambda *args, **kwargs: pytest.fail("weather fetched while disabled"),
    )
    generate.generate(config, date=DATE, zone=ZONE, out=tmp_path / "book.pdf")


def test_unreadable_contacts_are_warned(tmp_path, monkeypatch, capsys):
    config_path = base_config(tmp_path)
    config = load_config(config_path)
    registry = FakeRegistry(
        [FakeSource("book-uid", "Contacts", {eds.SOURCE_ADDRESS_BOOK})]
    )
    monkeypatch.setattr(
        eds,
        "book_client",
        lambda source: FakeBookClient(contact_class=FakeUnreadableContact),
    )
    warn = generate.WarningCollector()
    contacts = generate._selected_contacts(
        config, registry, FakeCredentialStore(), warn
    )
    assert contacts == []
    captured = capsys.readouterr()
    assert "Contacts: 3 件の連絡先を読み出せませんでした" in captured.err


def test_calendar_failure_is_a_warning(tmp_path, monkeypatch):
    config_path = base_config(tmp_path)
    config = load_config(config_path)
    patch_eds(monkeypatch, fail_calendar=True)
    out = generate.generate(config, date=DATE, zone=ZONE, out=tmp_path / "book.pdf")
    text = PdfReader(str(out)).pages[0].extract_text()
    assert "AKI TANAKA" in text
    assert "Pay rent" in text


def test_no_map_produces_one_page(tmp_path, monkeypatch):
    config_path = base_config(
        tmp_path,
        extra_panels="map = true\n",
        extra="""
[maps]
[maps.from]
latitude = 35.68
longitude = 139.76
[maps.to]
latitude = 35.69
longitude = 139.70
""",
    )
    config = load_config(config_path)
    patch_eds(monkeypatch)
    out = generate.generate(
        config, date=DATE, zone=ZONE, out=tmp_path / "book.pdf", no_map=True
    )
    assert len(PdfReader(str(out)).pages) == 1


def test_empty_panels_produce_cover_only(tmp_path):
    config_path = write_config(
        tmp_path,
        """
[booklet]
name = "Aki"
[panels]
""",
    )
    config = load_config(config_path)
    out = generate.generate(config, date=DATE, zone=ZONE, out=tmp_path / "book.pdf")
    text = PdfReader(str(out)).pages[0].extract_text()
    assert "PHONE" in text
    assert "CONTACTS" not in text


def test_missing_out_parent_is_created(tmp_path):
    config_path = write_config(
        tmp_path,
        """
[booklet]
name = "Aki"
[panels]
notes = true
""",
    )
    config = load_config(config_path)
    out = tmp_path / "2026" / "11" / "book.pdf"
    generate.generate(config, date=DATE, zone=ZONE, out=out)
    assert out.exists()


def test_edited_photo_path_is_warned_and_skipped(tmp_path, monkeypatch):
    photo = tmp_path / "photo.jpg"
    from PIL import Image

    Image.new("RGB", (300, 500), "white").save(photo)
    config_path = write_config(
        tmp_path,
        f"""
[booklet]
name = "Aki"
[panels]
photo = true
[photo]
path = "{tmp_path / 'missing.jpg'}"
""",
    )
    config = load_config(config_path)
    out = generate.generate(config, date=DATE, zone=ZONE, out=tmp_path / "book.pdf")
    text = PdfReader(str(out)).pages[0].extract_text()
    assert "PHONE" in text


def test_source_without_credentials_is_skipped(tmp_path, monkeypatch):
    config_path = write_config(
        tmp_path,
        """
[booklet]
name = "Aki"
[panels]
contacts = true
calendar = true
tasks = true
[sources]
calendars = ["paperphone-cal"]
contacts = ["contact-1"]
tasks = ["paperphone-tasks"]
""",
    )
    config = load_config(config_path)
    registry = FakeRegistry(
        [
            FakeSource("paperphone-cal", "Calendar", {eds.SOURCE_CALENDAR}),
            FakeSource("paperphone-tasks", "Tasks", {eds.SOURCE_TASK_LIST}),
            FakeSource("paperphone-book", "Contacts", {eds.SOURCE_ADDRESS_BOOK}),
        ]
    )
    monkeypatch.setattr(eds, "open_registry", lambda: registry)

    class EmptyCredentials(FakeCredentialStore):
        def has_password(self, source):
            return False

    monkeypatch.setattr(eds, "CredentialStore", lambda registry: EmptyCredentials())
    monkeypatch.setattr(eds, "read_events", lambda *args, **kwargs: pytest.fail("should skip"))
    monkeypatch.setattr(eds, "read_contacts", lambda *args, **kwargs: pytest.fail("should skip"))
    out = generate.generate(config, date=DATE, zone=ZONE, out=tmp_path / "book.pdf")
    assert out.exists()
    text = PdfReader(str(out)).pages[0].extract_text()
    assert "TASKS" in text
