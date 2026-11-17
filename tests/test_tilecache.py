from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from paperphone import tilecache

URL = "https://tiles.test/16/58169/25824.png"


def digest(url: str = URL) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def test_paths_are_hashed_copies_of_the_url(cache_home):
    tile = tilecache.tile_path(URL)
    meta = tilecache.meta_path(URL)
    assert tile.parent == cache_home / "paperphone" / "tiles"
    assert tile.name == f"{digest()}.tile"
    assert meta.name == f"{digest()}.json"
    assert URL not in str(tile)
    assert "58169" not in tile.name
    assert "25824" not in tile.name
    assert tilecache.tile_path("https://tiles.test/16/1/2.png") != tile


def test_store_and_read_round_trip(cache_home):
    tilecache.store_tile(URL, b"tile-bytes", etag='"v1"', max_age=600, now=1000.0)
    cached = tilecache.read_tile(URL)
    assert cached is not None
    assert cached.content == b"tile-bytes"
    assert cached.etag == '"v1"'
    assert cached.expires_at == 1600.0
    payload = json.loads(tilecache.meta_path(URL).read_text(encoding="utf-8"))
    assert payload == {"etag": '"v1"', "expires_at": 1600.0}


def test_store_keeps_no_temporary_files(cache_home):
    tilecache.store_tile(URL, b"tile-bytes", etag=None, max_age=60, now=0)
    assert sorted(path.name for path in tilecache.tiles_dir().iterdir()) == sorted(
        [f"{digest()}.json", f"{digest()}.tile"]
    )


def test_failed_replace_keeps_previous_files(cache_home, monkeypatch):
    tilecache.store_tile(URL, b"old", etag='"v1"', max_age=60, now=0)

    def fail(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(tilecache.os, "replace", fail)
    tilecache.store_tile(URL, b"new", etag='"v2"', max_age=60, now=100)
    assert tilecache.read_tile(URL).content == b"old"
    assert len(list(tilecache.tiles_dir().iterdir())) == 2


def test_store_is_silent_when_the_directory_cannot_be_created(cache_home):
    blocked = cache_home / "paperphone" / "tiles"
    blocked.parent.mkdir(parents=True)
    blocked.write_text("not a directory", encoding="utf-8")
    tilecache.store_tile(URL, b"tile-bytes", etag=None, max_age=60)
    assert tilecache.read_tile(URL) is None


@pytest.mark.parametrize(
    ("cache_control", "expected"),
    [
        ("max-age=3600", 3600),
        ("public, max-age=0", 0),
        ("max-age=3600, stale-while-revalidate=604800", 3600),
        ("max-age=abc", tilecache.DEFAULT_MAX_AGE),
        ("no-cache", tilecache.DEFAULT_MAX_AGE),
        (None, tilecache.DEFAULT_MAX_AGE),
        ("no-store", None),
        ("no-store, max-age=3600", None),
    ],
)
def test_freshness_follows_cache_control(cache_control, expected):
    headers = {} if cache_control is None else {"Cache-Control": cache_control}
    assert tilecache.freshness(headers) == expected


def test_freshness_accepts_any_header_case():
    assert tilecache.freshness(httpx.Headers({"cache-control": "max-age=42"})) == 42
    assert tilecache.freshness({"cache-control": "max-age=42"}) == 42


def test_freshness_until_expiry():
    cached = tilecache.CachedTile(content=b"tile", etag=None, expires_at=100.0)
    assert cached.is_fresh(now=99.9)
    assert not cached.is_fresh(now=100.0)
    assert not cached.is_fresh(now=100.1)


def test_expiry_uses_the_observation_time():
    tilecache.store_tile(URL, b"tile", etag=None, max_age=604800, now=10.0)
    assert tilecache.read_tile(URL).expires_at == 10.0 + 604800


def test_renew_tile_updates_freshness_without_touching_the_bytes(cache_home):
    tilecache.store_tile(URL, b"tile-bytes", etag='"v1"', max_age=60, now=0)
    cached = tilecache.read_tile(URL)
    renewed = tilecache.renew_tile(
        URL, cached, etag='"v2"', max_age=300, now=1000.0
    )
    assert renewed.content == b"tile-bytes"
    assert renewed.etag == '"v2"'
    assert renewed.expires_at == 1300.0
    stored = tilecache.read_tile(URL)
    assert stored == renewed
    assert tilecache.tile_path(URL).read_bytes() == b"tile-bytes"


def test_renew_tile_without_storable_freshness_keeps_the_old_metadata(cache_home):
    tilecache.store_tile(URL, b"tile-bytes", etag='"v1"', max_age=60, now=0)
    cached = tilecache.read_tile(URL)
    renewed = tilecache.renew_tile(URL, cached, etag='"v1"', max_age=None, now=1000.0)
    assert renewed == cached
    assert tilecache.read_tile(URL) == cached


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        "{}",
        '{"expires_at": "soon"}',
        '{"expires_at": 100, "etag": 7}',
    ],
)
def test_broken_metadata_is_a_miss(cache_home, payload):
    tilecache.tiles_dir().mkdir(parents=True)
    tilecache.tile_path(URL).write_bytes(b"tile-bytes")
    tilecache.meta_path(URL).write_text(payload, encoding="utf-8")
    assert tilecache.read_tile(URL) is None


def test_missing_tile_file_is_a_miss(cache_home):
    tilecache.tiles_dir().mkdir(parents=True)
    tilecache.meta_path(URL).write_text('{"expires_at": 100, "etag": null}', encoding="utf-8")
    assert tilecache.read_tile(URL) is None


def test_unreadable_tile_is_a_miss(cache_home):
    tilecache.store_tile(URL, b"tile-bytes", etag=None, max_age=60, now=0)
    tile = tilecache.tile_path(URL)
    tile.unlink()
    tile.mkdir()
    assert tilecache.read_tile(URL) is None
