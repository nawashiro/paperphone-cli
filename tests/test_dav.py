from __future__ import annotations

from pathlib import Path

import pytest
from conftest import FakeDavBackend

from paperphone import dav
from paperphone.errors import RuntimeFailure, UsageError


def write_config(tmp_path: Path) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(
        """# keep this comment
[booklet]
name = "Aki"

[sources]
calendars = ["existing"]
tasks = []
contacts = []
""",
        encoding="utf-8",
    )
    return path


def test_validate_url_normalizes():
    assert dav.validate_url("HTTPS://Example.COM/cal/") == "https://example.com/cal"
    with pytest.raises(UsageError):
        dav.validate_url("ftp://example.com")
    with pytest.raises(UsageError):
        dav.validate_url("https:///no-host")


def test_add_creates_record_and_selects(tmp_path):
    config = write_config(tmp_path)
    backend = FakeDavBackend()
    uid = dav.add_source(
        backend,
        kind="caldav",
        url="https://example.com/cal",
        name="Nextcloud",
        user="aki",
        password_getter=lambda: "secret",
        config_file=config,
    )
    assert uid.startswith("paperphone-")
    assert backend.created[0]["user"] == "aki"
    records = dav.read_records(tmp_path / "dav.toml")
    assert records[0]["uid"] == uid
    text = config.read_text()
    assert "# keep this comment" in text
    assert uid in text
    assert "existing" in text


def test_carddav_is_not_selected(tmp_path):
    config = write_config(tmp_path)
    backend = FakeDavBackend()
    uid = dav.add_source(
        backend,
        kind="carddav",
        url="https://example.com/card",
        name="Cards",
        user="aki",
        password_getter=lambda: "secret",
        config_file=config,
    )
    assert uid not in config.read_text()


def test_no_select_leaves_config_alone(tmp_path):
    config = write_config(tmp_path)
    before = config.read_text()
    backend = FakeDavBackend()
    uid = dav.add_source(
        backend,
        kind="caldav",
        url="https://example.com/cal",
        name="Nextcloud",
        user="aki",
        password_getter=lambda: "secret",
        config_file=config,
        no_select=True,
    )
    assert uid
    assert config.read_text() == before


def test_duplicate_is_rejected_with_adopt_hint(tmp_path):
    config = write_config(tmp_path)
    backend = FakeDavBackend()
    first = dav.add_source(
        backend,
        kind="caldav",
        url="https://example.com/cal",
        name="Nextcloud",
        user="aki",
        password_getter=lambda: "secret",
        config_file=config,
    )
    with pytest.raises(UsageError) as error:
        dav.add_source(
            backend,
            kind="caldav",
            url="https://example.com/cal/",
            name="Nextcloud",
            user="aki",
            password_getter=lambda: "secret",
            config_file=config,
        )
    assert "--adopt" in str(error.value)
    assert first in str(error.value)


def test_adopt_reuses_existing_source(tmp_path):
    config = write_config(tmp_path)
    backend = FakeDavBackend()
    first = dav.add_source(
        backend,
        kind="caldav",
        url="https://example.com/cal",
        name="Nextcloud",
        user="aki",
        password_getter=lambda: "secret",
        config_file=config,
    )
    uid = dav.add_source(
        backend,
        kind="caldav",
        url="https://example.com/cal",
        name="Nextcloud",
        user="aki",
        password_getter=lambda: "other",
        config_file=config,
        adopt=True,
    )
    assert uid == first
    assert len(backend.created) == 1


def test_verification_failure_rolls_back(tmp_path):
    config = write_config(tmp_path)
    backend = FakeDavBackend()
    backend.fail_verify = True
    with pytest.raises(RuntimeFailure):
        dav.add_source(
            backend,
            kind="caldav",
            url="https://example.com/cal",
            name="Nextcloud",
            user="aki",
            password_getter=lambda: "secret",
            config_file=config,
        )
    assert backend.removed == ["paperphone-1"]
    assert dav.read_records(tmp_path / "dav.toml") == []


def test_remove_managed_source_updates_everything(tmp_path):
    config = write_config(tmp_path)
    backend = FakeDavBackend()
    uid = dav.add_source(
        backend,
        kind="caldav",
        url="https://example.com/cal",
        name="Nextcloud",
        user="aki",
        password_getter=lambda: "secret",
        config_file=config,
    )
    removed = dav.remove_source(backend, uid, config_file=config)
    assert removed == uid
    assert backend.removed == [uid]
    assert dav.read_records(tmp_path / "dav.toml") == []
    assert uid not in config.read_text()
    assert "existing" in config.read_text()


def test_remove_by_name(tmp_path):
    config = write_config(tmp_path)
    backend = FakeDavBackend()
    uid = dav.add_source(
        backend,
        kind="tasks",
        url="https://example.com/tasks",
        name="My Tasks",
        user="aki",
        password_getter=lambda: "secret",
        config_file=config,
    )
    assert dav.remove_source(backend, "my tasks", config_file=config) == uid


def test_remove_unknown_target(tmp_path):
    backend = FakeDavBackend()
    with pytest.raises(UsageError) as error:
        dav.remove_source(backend, "gnome-source", config_file=write_config(tmp_path))
    assert "GNOME" in str(error.value)


def test_records_roundtrip(tmp_path):
    path = tmp_path / "dav.toml"
    records = [
        {"uid": "paperphone-1", "kind": "caldav", "url": "https://x/cal", "name": "X", "user": "u"}
    ]
    dav.write_records(path, records)
    assert dav.read_records(path) == records


def test_password_never_reaches_config_or_records(tmp_path):
    config = write_config(tmp_path)
    backend = FakeDavBackend()
    dav.add_source(
        backend,
        kind="caldav",
        url="https://example.com/cal",
        name="Nextcloud",
        user="aki",
        password_getter=lambda: "correct horse battery staple",
        config_file=config,
    )
    assert "correct horse battery staple" not in config.read_text()
    assert "correct horse battery staple" not in (tmp_path / "dav.toml").read_text()


def test_duplicate_from_records_is_detected(tmp_path):
    config = write_config(tmp_path)
    dav.write_records(
        tmp_path / "dav.toml",
        [
            {
                "uid": "paperphone-known",
                "kind": "caldav",
                "url": "https://example.com/cal",
                "name": "Known",
                "user": "aki",
            }
        ],
    )
    backend = FakeDavBackend()
    with pytest.raises(UsageError) as error:
        dav.add_source(
            backend,
            kind="caldav",
            url="https://example.com/cal",
            name="Known",
            user="aki",
            password_getter=lambda: "secret",
            config_file=config,
        )
    assert "paperphone-known" in str(error.value)
    assert backend.created == []
