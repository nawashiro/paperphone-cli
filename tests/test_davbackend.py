from __future__ import annotations

import pytest

from paperphone import davbackend, eds


class Credentials:
    def store_password(self, source, user: str, password: str) -> None:
        pass


def source_for(monkeypatch, authentication: dict) -> None:
    monkeypatch.setattr(eds, "new_dav_source", lambda uid, name, kind: object())
    monkeypatch.setattr(eds, "set_dav_url", lambda source, value: None)
    monkeypatch.setattr(
        eds,
        "set_authentication",
        lambda source, host, user, port=None: authentication.update(host=host, port=port),
    )
    monkeypatch.setattr(eds, "commit_source", lambda registry, source: None)
    monkeypatch.setattr(eds, "remove_source", lambda source: None)


@pytest.mark.parametrize(
    ("url", "port"),
    [
        ("https://example.com/cal", 443),
        ("http://example.com/cal", 80),
        ("https://example.com:8443/cal", 8443),
    ],
)
def test_create_uses_url_port(monkeypatch, url: str, port: int):
    authentication: dict = {}
    source_for(monkeypatch, authentication)
    backend = davbackend.EdsDavBackend(registry=object(), credentials=Credentials())

    backend.create("caldav", url, "Calendar", "aki", "secret")

    assert authentication == {"host": "example.com", "port": port}
