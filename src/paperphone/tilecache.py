from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .paths import cache_dir

DEFAULT_MAX_AGE = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class CachedTile:
    content: bytes
    etag: str | None
    expires_at: float

    def is_fresh(self, now: float | None = None) -> bool:
        return _now(now) < self.expires_at


def tiles_dir() -> Path:
    return cache_dir() / "tiles"


def tile_path(url: str) -> Path:
    return tiles_dir() / f"{_digest(url)}.tile"


def meta_path(url: str) -> Path:
    return tiles_dir() / f"{_digest(url)}.json"


def freshness(headers: Mapping[str, str]) -> int | None:
    """Cache-Control から鮮度の秒数を返す。保存してはならない場合は None。"""
    directives: dict[str, str] = {}
    for part in (_header(headers, "cache-control") or "").split(","):
        name, _, value = part.strip().partition("=")
        if name:
            directives[name.lower()] = value.strip().strip('"')
    if "no-store" in directives:
        return None
    try:
        return max(0, int(directives["max-age"]))
    except (KeyError, ValueError):
        return DEFAULT_MAX_AGE


def read_tile(url: str) -> CachedTile | None:
    try:
        payload = json.loads(meta_path(url).read_text(encoding="utf-8"))
        etag = payload.get("etag")
        expires_at = float(payload["expires_at"])
        content = tile_path(url).read_bytes()
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    if etag is not None and not isinstance(etag, str):
        return None
    return CachedTile(content=content, etag=etag, expires_at=expires_at)


def store_tile(
    url: str,
    content: bytes,
    *,
    etag: str | None,
    max_age: int,
    now: float | None = None,
) -> None:
    expires_at = _now(now) + max_age
    try:
        tiles_dir().mkdir(parents=True, exist_ok=True)
        _write_atomic(tile_path(url), content)
        _write_atomic(meta_path(url), _metadata(etag, expires_at))
    except OSError:
        pass


def renew_tile(
    url: str,
    cached: CachedTile,
    *,
    etag: str | None,
    max_age: int | None,
    now: float | None = None,
) -> CachedTile:
    if max_age is None:
        return cached
    renewed = CachedTile(
        content=cached.content,
        etag=etag,
        expires_at=_now(now) + max_age,
    )
    try:
        tiles_dir().mkdir(parents=True, exist_ok=True)
        _write_atomic(meta_path(url), _metadata(etag, renewed.expires_at))
    except OSError:
        pass
    return renewed


def _digest(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _header(headers: Mapping[str, str], name: str) -> str | None:
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return None


def _now(now: float | None) -> float:
    return time.time() if now is None else now


def _metadata(etag: str | None, expires_at: float) -> bytes:
    return json.dumps({"etag": etag, "expires_at": expires_at}).encode("utf-8")


def _write_atomic(path: Path, content: bytes) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(name, path)
    except OSError:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise
