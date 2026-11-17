from __future__ import annotations

import uuid
from typing import Protocol

from . import eds
from .errors import RuntimeFailure
from .model import SourceInfo

SOURCE_KIND = {
    "caldav": "calendar",
    "carddav": "contacts",
    "tasks": "tasks",
}


class DavBackend(Protocol):
    def managed_sources(self) -> list[SourceInfo]: ...

    def find_duplicate(self, kind: str, url: str, user: str) -> SourceInfo | None: ...

    def create(self, kind: str, url: str, name: str, user: str, password: str) -> str: ...

    def remove(self, uid: str) -> None: ...

    def verify(self, uid: str, kind: str) -> None: ...


class EdsDavBackend:
    def __init__(self, registry=None, credentials: eds.CredentialStore | None = None):
        self.registry = registry or eds.open_registry()
        self.credentials = credentials or eds.CredentialStore(self.registry)

    def managed_sources(self) -> list[SourceInfo]:
        return [
            info
            for info in eds.list_sources(self.registry, self.credentials)
            if info.managed
        ]

    def find_duplicate(self, kind: str, url: str, user: str) -> SourceInfo | None:
        wanted = SOURCE_KIND[kind]
        for info in self.managed_sources():
            if info.kind != wanted:
                continue
            source = eds.find_source(self.registry, info.uid)
            if source is None:
                continue
            uri = eds.source_uri(source)
            if (
                uri is not None
                and uri.rstrip("/") == url.rstrip("/")
                and (eds.source_user(source) or "") == user
            ):
                return info
        return None

    def create(self, kind: str, url: str, name: str, user: str, password: str) -> str:
        from urllib.parse import urlsplit

        uid = eds.MANAGED_PREFIX + str(uuid.uuid4())
        source = eds.new_dav_source(uid, name, SOURCE_KIND[kind])
        eds.set_dav_url(source, url)
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        eds.set_authentication(source, parts.hostname or "", user, port)
        eds.commit_source(self.registry, source)
        try:
            self.credentials.store_password(source, user, password)
        except RuntimeFailure:
            try:
                eds.remove_source(source)
            finally:
                raise
        return uid

    def remove(self, uid: str) -> None:
        source = eds.find_source(self.registry, uid)
        if source is None:
            raise RuntimeFailure(f"source が見つかりません: {uid}")
        self.credentials.delete_password(source)
        eds.remove_source(source)

    def verify(self, uid: str, kind: str) -> None:
        source = eds.find_source(self.registry, uid)
        if source is None:
            raise RuntimeFailure(f"source が見つかりません: {uid}")
        eds.verify_source(source, SOURCE_KIND[kind])
