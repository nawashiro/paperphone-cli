from __future__ import annotations

from conftest import (
    FakeBookClient,
    FakeContact,
    FakeCredentialStore,
    FakeRegistry,
    FakeSource,
    FakeUnreadableContact,
)

from paperphone import cli, eds
from paperphone.model import Contact


class MixedBookClient(FakeBookClient):
    def get_contacts_sync(self, sexp, cancellable):
        return (
            True,
            [FakeUnreadableContact({})]
            + [FakeContact(row) for row in self.rows],
        )


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
    monkeypatch.setattr(
        cli.eds, "read_contacts", lambda source, **kwargs: contacts
    )

    assert cli.main(["contacts", "list", "--query", "aki"]) == 0
    out = capsys.readouterr().out
    assert "Aki Tanaka" in out
    assert "Bea Ito" not in out

    assert cli.main(["contacts", "list", "--query", "2222"]) == 0
    out = capsys.readouterr().out
    assert "Bea Ito" in out
    assert "Aki Tanaka" not in out


def test_contacts_list_skips_unreadable_contacts(monkeypatch, capsys):
    patch_registry(
        monkeypatch,
        [FakeSource("book-1", "Book", {eds.SOURCE_ADDRESS_BOOK})],
    )
    monkeypatch.setattr(cli.eds, "find_source", lambda registry, uid: object())
    monkeypatch.setattr(cli.eds, "book_client", lambda source: MixedBookClient())

    assert cli.main(["contacts", "list"]) == 0
    captured = capsys.readouterr()
    assert "Book: 1 件の連絡先を読み出せませんでした" in captured.err
    assert "Aki Tanaka" in captured.out
    assert not any(line == "\t\t" for line in captured.out.splitlines())
    assert "\t\t\n" not in captured.out


def test_contacts_list_empty_result(monkeypatch, capsys):
    patch_registry(monkeypatch, [])
    assert cli.main(["contacts", "list"]) == 0
    out = capsys.readouterr().out
    assert "UID" in out
