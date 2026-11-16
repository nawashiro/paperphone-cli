from __future__ import annotations

from conftest import FakeCredentialStore, FakeRegistry, FakeSource

from paperphone import cli, eds
from paperphone.model import Contact


def patch_registry(monkeypatch, sources):
    registry = FakeRegistry(sources)
    monkeypatch.setattr(cli.eds, "open_registry", lambda: registry)
    monkeypatch.setattr(cli.eds, "CredentialStore", lambda registry: FakeCredentialStore())
    return registry


def test_sources_lists_uid_kind_and_origin(monkeypatch, capsys):
    patch_registry(
        monkeypatch,
        [
            FakeSource("gnome-1", "Google", {eds.SOURCE_CALENDAR}),
            FakeSource("paperphone-1", "Nextcloud", {eds.SOURCE_CALENDAR}),
        ],
    )
    assert cli.main(["sources"]) == 0
    out = capsys.readouterr().out
    assert "gnome-1" in out and "GNOME" in out
    assert "paperphone-1" in out


def test_sources_empty_has_guidance(monkeypatch, capsys):
    patch_registry(monkeypatch, [])
    assert cli.main(["sources"]) == 0
    out = capsys.readouterr().out
    assert "dav add" in out
    assert "GNOME" in out


def test_contacts_list_filters_by_name_and_phone(monkeypatch, capsys):
    patch_registry(
        monkeypatch,
        [FakeSource("book-1", "Book", {eds.SOURCE_ADDRESS_BOOK})],
    )
    contacts = [
        Contact("1", "Aki Tanaka", "+81 90 1111"),
        Contact("2", "Bea Ito", "+81 3 2222"),
    ]
    monkeypatch.setattr(cli.eds, "find_source", lambda registry, uid: object())
    monkeypatch.setattr(cli.eds, "read_contacts", lambda source: contacts)

    assert cli.main(["contacts", "list", "--query", "aki"]) == 0
    out = capsys.readouterr().out
    assert "Aki Tanaka" in out
    assert "Bea Ito" not in out

    assert cli.main(["contacts", "list", "--query", "2222"]) == 0
    out = capsys.readouterr().out
    assert "Bea Ito" in out
    assert "Aki Tanaka" not in out


def test_contacts_list_empty_result(monkeypatch, capsys):
    patch_registry(monkeypatch, [])
    assert cli.main(["contacts", "list"]) == 0
    out = capsys.readouterr().out
    assert "UID" in out
