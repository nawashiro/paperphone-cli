from __future__ import annotations

import io
import json
import math
import time
from pathlib import Path

import httpx
import pytest
import respx
from PIL import Image

from paperphone import maps, tilecache
from paperphone.config import MapsConfig, PlaceConfig
from paperphone.errors import RuntimeFailure

FIXTURES = Path(__file__).parent / "fixtures"
TILE = (FIXTURES / "tiles" / "tile.png").read_bytes()
ROUTE = json.loads((FIXTURES / "route-response.json").read_text())
TILE_URL_REGEX = r"https://tiles\.test/.*"


@pytest.fixture(autouse=True)
def _cache_home(cache_home):
    return cache_home


def world_to_lonlat(x: float, y: float, zoom: int) -> tuple[float, float]:
    scale = maps.TILE_SIZE * (2**zoom)
    longitude = x / scale * 360.0 - 180.0
    sin_latitude = math.tanh((0.5 - y / scale) * 2 * math.pi)
    return math.degrees(math.asin(sin_latitude)), longitude


def pixel_of(latitude: float, longitude: float, viewport) -> tuple[float, float]:
    x, y = maps.lonlat_to_world(latitude, longitude, viewport.zoom)
    return (
        x - (viewport.center_x - maps.MAP_PIXELS / 2),
        y - (viewport.center_y - maps.MAP_PIXELS / 2),
    )


def disc_is_black(image: Image.Image, center: tuple[float, float]) -> bool:
    radius = maps.marker_radius(image.width)
    for step in range(8):
        angle = math.radians(step * 45)
        x = round(center[0] + math.cos(angle) * radius * 0.85)
        y = round(center[1] + math.sin(angle) * radius * 0.85)
        if image.getpixel((x, y)) != 0:
            return False
    return True


def make_config(tile_url="https://tiles.test/{z}/{x}/{y}.png", router="") -> MapsConfig:
    return MapsConfig(
        origin=PlaceConfig(35.6812, 139.7671, "Home", ("1-1 Chiyoda", "Tokyo")),
        destination=PlaceConfig(35.6900, 139.7000, "Station", ("2-2 Chuo", "Tokyo")),
        tile_url=tile_url,
        router_url=router,
    )


def uniform_tile(value: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (maps.TILE_SIZE, maps.TILE_SIZE), (value, value, value)).save(
        buffer, format="PNG"
    )
    return buffer.getvalue()


def tile_urls(config: MapsConfig) -> list[str]:
    viewport = maps.viewport_for(config)
    x0, y0, x1, y1 = maps.tile_range(viewport)
    return [
        config.tile_url.format(z=viewport.zoom, x=x, y=y)
        for y in range(y0, y1 + 1)
        for x in range(x0, x1 + 1)
    ]


def expire_cache() -> None:
    for path in tilecache.tiles_dir().glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["expires_at"] = 0
        path.write_text(json.dumps(payload), encoding="utf-8")


def cached_bytes() -> list[bytes]:
    return [path.read_bytes() for path in tilecache.tiles_dir().glob("*.tile")]


def cached_metadata() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in tilecache.tiles_dir().glob("*.json")
    ]


def test_decode_polyline():
    points = maps.decode_polyline("_zx`cAwruqiGolFvk`@owH~s`B")
    assert points[0] == pytest.approx((35.6812, 139.7671), abs=1e-5)
    assert points[-1] == pytest.approx((35.6900, 139.7000), abs=1e-5)


def test_zoom_is_clamped():
    assert maps.choose_zoom(0.000001, 0.000001) == maps.MAX_ZOOM
    assert maps.choose_zoom(20, 20) == maps.MIN_ZOOM


def test_tile_range_covers_viewport():
    viewport = maps.viewport_for(make_config())
    x0, y0, x1, y1 = maps.tile_range(viewport)
    assert 1 <= x1 - x0 + 1 <= 5
    assert 1 <= y1 - y0 + 1 <= 5


@respx.mock
def test_fetch_mosaic_composes_tiles():
    route = respx.get(url__regex=r"https://tiles\.test/.*").mock(
        return_value=httpx.Response(200, content=TILE)
    )
    viewport = maps.viewport_for(make_config())
    image = maps.fetch_mosaic(make_config(), viewport)
    assert image.size == (maps.MAP_PIXELS, maps.MAP_PIXELS)
    assert route.called


def test_background_is_lightened():
    gray = Image.new("L", (64, 64), 200)
    lightened = maps.lighten_background(gray)
    assert lightened.mode == "L"
    assert lightened.size == gray.size
    assert lightened.getpixel((32, 32)) > 200


def test_route_has_white_halo_around_black_core():
    viewport = maps.viewport_for(make_config())
    image = Image.new("L", (maps.MAP_PIXELS, maps.MAP_PIXELS), 200)
    points = [
        world_to_lonlat(viewport.center_x + step, viewport.center_y, viewport.zoom)
        for step in range(-120, 121, 60)
    ]
    maps.draw_route(image, points, viewport)
    x = y = maps.MAP_PIXELS // 2
    assert image.getpixel((x, y)) == 0
    assert image.getpixel((x, y - 5)) == 255
    assert image.getpixel((x, y - 9)) == 200


def test_markers_sit_on_projected_points():
    viewport = maps.viewport_for(make_config())
    image = Image.new("L", (maps.MAP_PIXELS, maps.MAP_PIXELS), 200)
    anchors = [(35.6812, 139.7671), (35.6900, 139.7000)]
    maps.draw_markers(image, viewport, anchors)
    for latitude, longitude in anchors:
        assert disc_is_black(image, pixel_of(latitude, longitude, viewport))


def test_marker_center_is_clamped_inside_the_image():
    viewport = maps.viewport_for(make_config())
    image = Image.new("L", (maps.MAP_PIXELS, maps.MAP_PIXELS), 200)
    edge = world_to_lonlat(4, 4, viewport.zoom)
    maps.draw_markers(image, viewport, [edge, edge])
    radius = maps.marker_radius()
    assert disc_is_black(image, (radius, radius))


@respx.mock
def test_fetch_route_decodes_shape():
    respx.post("https://router.test/route").mock(return_value=httpx.Response(200, json=ROUTE))
    points = maps.fetch_route(make_config(router="https://router.test/route"))
    assert len(points) == 3


@respx.mock
def test_tile_failure_returns_no_image():
    respx.get(url__regex=r"https://tiles\.test/.*").mock(side_effect=httpx.ConnectError("offline"))
    warnings = []
    page = maps.build_map_page(make_config(), warn=warnings.append)
    assert page.image is None
    assert warnings


@respx.mock
def test_route_failure_keeps_map():
    respx.get(url__regex=r"https://tiles\.test/.*").mock(
        return_value=httpx.Response(200, content=TILE)
    )
    respx.post("https://router.test/route").mock(side_effect=httpx.ConnectError("offline"))
    warnings = []
    page = maps.build_map_page(
        make_config(router="https://router.test/route"), warn=warnings.append
    )
    assert page.image is not None
    assert page.has_route is False
    assert warnings


@respx.mock
def test_route_draws_black_line():
    respx.get(url__regex=r"https://tiles\.test/.*").mock(
        return_value=httpx.Response(200, content=TILE)
    )
    respx.post("https://router.test/route").mock(return_value=httpx.Response(200, json=ROUTE))
    page = maps.build_map_page(
        make_config(router="https://router.test/route"), warn=lambda message: None
    )
    assert page.image is not None
    assert page.has_route is True
    assert page.image.mode == "L"
    assert page.image.getextrema()[0] == 0


@respx.mock
def test_route_endpoints_get_markers():
    respx.get(url__regex=r"https://tiles\.test/.*").mock(
        return_value=httpx.Response(200, content=TILE)
    )
    respx.post("https://router.test/route").mock(return_value=httpx.Response(200, json=ROUTE))
    config = make_config(router="https://router.test/route")
    page = maps.build_map_page(config, warn=lambda message: None)
    assert page.image is not None
    viewport = maps.viewport_for(config)
    for place in (config.origin, config.destination):
        assert disc_is_black(page.image, pixel_of(place.latitude, place.longitude, viewport))
    assert page.image.getextrema()[0] == 0


@respx.mock
def test_route_failure_marks_configured_places():
    respx.get(url__regex=r"https://tiles\.test/.*").mock(
        return_value=httpx.Response(200, content=TILE)
    )
    respx.post("https://router.test/route").mock(side_effect=httpx.ConnectError("offline"))
    config = make_config(router="https://router.test/route")
    page = maps.build_map_page(config, warn=lambda message: None)
    assert page.image is not None
    assert page.has_route is False
    viewport = maps.viewport_for(config)
    for place in (config.origin, config.destination):
        assert disc_is_black(page.image, pixel_of(place.latitude, place.longitude, viewport))


@respx.mock
def test_background_is_lightened_before_drawing():
    respx.get(url__regex=r"https://tiles\.test/.*").mock(
        return_value=httpx.Response(200, content=uniform_tile(200))
    )
    page = maps.build_map_page(make_config(), warn=lambda message: None)
    assert page.image is not None
    assert page.image.getpixel((512, 512)) > 200


def test_attribution_constant():
    assert maps.ATTRIBUTION == "© OpenStreetMap contributors"


@respx.mock
def test_fresh_cache_avoids_tile_requests(cache_home):
    route = respx.get(url__regex=TILE_URL_REGEX).mock(
        return_value=httpx.Response(
            200,
            content=TILE,
            headers={"Cache-Control": "max-age=600", "ETag": '"v1"'},
        )
    )
    config = make_config()
    viewport = maps.viewport_for(config)
    maps.fetch_mosaic(config, viewport)
    calls = route.call_count
    assert calls == len(tile_urls(config))
    image = maps.fetch_mosaic(config, viewport)
    assert route.call_count == calls
    assert image.size == (maps.MAP_PIXELS, maps.MAP_PIXELS)
    assert len(cached_bytes()) == calls


@respx.mock
def test_expired_tile_is_revalidated_with_its_etag(cache_home):
    conditional: list[str] = []

    def responder(request):
        etag = request.headers.get("If-None-Match")
        if etag is None:
            return httpx.Response(
                200,
                content=TILE,
                headers={"Cache-Control": "max-age=600", "ETag": '"v1"'},
            )
        conditional.append(etag)
        return httpx.Response(
            304, headers={"Cache-Control": "max-age=600", "ETag": '"v1"'}
        )

    route = respx.get(url__regex=TILE_URL_REGEX).mock(side_effect=responder)
    config = make_config()
    viewport = maps.viewport_for(config)
    maps.fetch_mosaic(config, viewport)
    calls = route.call_count
    expire_cache()
    image = maps.fetch_mosaic(config, viewport)
    assert image.size == (maps.MAP_PIXELS, maps.MAP_PIXELS)
    assert route.call_count == calls * 2
    assert conditional == ['"v1"'] * calls
    assert cached_bytes() == [TILE] * calls
    assert all(payload["expires_at"] > time.time() for payload in cached_metadata())


@respx.mock
def test_revalidated_200_replaces_the_cached_tile(cache_home):
    state = {"tile": uniform_tile(10), "etag": '"v1"'}

    def responder(request):
        if request.headers.get("If-None-Match"):
            state["tile"] = uniform_tile(200)
            state["etag"] = '"v2"'
        return httpx.Response(
            200,
            content=state["tile"],
            headers={"Cache-Control": "max-age=600", "ETag": state["etag"]},
        )

    respx.get(url__regex=TILE_URL_REGEX).mock(side_effect=responder)
    config = make_config()
    viewport = maps.viewport_for(config)
    first = maps.fetch_mosaic(config, viewport)
    assert first.getpixel((512, 512)) == (10, 10, 10)
    expire_cache()
    second = maps.fetch_mosaic(config, viewport)
    assert second.getpixel((512, 512)) == (200, 200, 200)
    assert cached_bytes() == [uniform_tile(200)] * len(tile_urls(config))
    assert all(payload["etag"] == '"v2"' for payload in cached_metadata())


@respx.mock
def test_tiles_without_cache_headers_are_fresh_for_seven_days(cache_home):
    route = respx.get(url__regex=TILE_URL_REGEX).mock(
        return_value=httpx.Response(200, content=TILE)
    )
    before = time.time()
    config = make_config()
    viewport = maps.viewport_for(config)
    maps.fetch_mosaic(config, viewport)
    metadata = cached_metadata()
    assert len(metadata) == route.call_count
    for payload in metadata:
        assert payload["etag"] is None
        assert before + tilecache.DEFAULT_MAX_AGE <= payload["expires_at"]
        assert payload["expires_at"] <= time.time() + tilecache.DEFAULT_MAX_AGE
    calls = route.call_count
    maps.fetch_mosaic(config, viewport)
    assert route.call_count == calls


@respx.mock
def test_no_store_tile_is_never_cached(cache_home):
    route = respx.get(url__regex=TILE_URL_REGEX).mock(
        return_value=httpx.Response(
            200,
            content=TILE,
            headers={"Cache-Control": "no-store", "ETag": '"v1"'},
        )
    )
    config = make_config()
    viewport = maps.viewport_for(config)
    maps.fetch_mosaic(config, viewport)
    calls = route.call_count
    assert calls > 0
    assert cached_bytes() == []
    maps.fetch_mosaic(config, viewport)
    assert route.call_count == calls * 2


@respx.mock
def test_broken_cached_tile_is_refetched_after_a_304(cache_home):
    conditional: list[bool] = []

    def responder(request):
        asked = request.headers.get("If-None-Match") is not None
        conditional.append(asked)
        if asked:
            return httpx.Response(304, headers={"ETag": '"v1"'})
        return httpx.Response(
            200,
            content=TILE,
            headers={"Cache-Control": "max-age=600", "ETag": '"v1"'},
        )

    respx.get(url__regex=TILE_URL_REGEX).mock(side_effect=responder)
    config = make_config()
    viewport = maps.viewport_for(config)
    maps.fetch_mosaic(config, viewport)
    first_calls = len(conditional)
    for path in tilecache.tiles_dir().glob("*.tile"):
        path.write_bytes(b"broken")
    image = maps.fetch_mosaic(config, viewport)
    assert image.size == (maps.MAP_PIXELS, maps.MAP_PIXELS)
    assert conditional[first_calls:] == [True, False] * first_calls
    assert cached_bytes() == [TILE] * first_calls


@respx.mock
def test_broken_metadata_is_refetched_without_conditions(cache_home):
    conditional: list[bool] = []

    def responder(request):
        conditional.append(request.headers.get("If-None-Match") is not None)
        return httpx.Response(
            200,
            content=TILE,
            headers={"Cache-Control": "max-age=600", "ETag": '"v1"'},
        )

    route = respx.get(url__regex=TILE_URL_REGEX).mock(side_effect=responder)
    config = make_config()
    viewport = maps.viewport_for(config)
    maps.fetch_mosaic(config, viewport)
    calls = route.call_count
    for path in tilecache.tiles_dir().glob("*.json"):
        path.write_text("{broken", encoding="utf-8")
    maps.fetch_mosaic(config, viewport)
    assert conditional[calls:] == [False] * calls
    assert route.call_count == calls * 2


@respx.mock
def test_cache_write_failure_still_builds_the_map(cache_home):
    blocked = cache_home / "paperphone" / "tiles"
    blocked.parent.mkdir(parents=True)
    blocked.write_text("not a directory", encoding="utf-8")
    respx.get(url__regex=TILE_URL_REGEX).mock(return_value=httpx.Response(200, content=TILE))
    config = make_config()
    image = maps.fetch_mosaic(config, maps.viewport_for(config))
    assert image.size == (maps.MAP_PIXELS, maps.MAP_PIXELS)
    assert blocked.is_file()


@respx.mock
def test_expired_tile_is_not_used_when_the_network_fails(cache_home):
    state = {"online": True}

    def responder(request):
        if not state["online"]:
            raise httpx.ConnectError("offline")
        return httpx.Response(
            200,
            content=TILE,
            headers={"Cache-Control": "max-age=600", "ETag": '"v1"'},
        )

    respx.get(url__regex=TILE_URL_REGEX).mock(side_effect=responder)
    config = make_config()
    maps.fetch_mosaic(config, maps.viewport_for(config))
    expire_cache()
    state["online"] = False
    warnings = []
    page = maps.build_map_page(config, warn=warnings.append)
    assert page.image is None
    assert warnings


@respx.mock
def test_unopenable_tile_is_not_cached(cache_home):
    respx.get(url__regex=TILE_URL_REGEX).mock(
        return_value=httpx.Response(
            200, content=b"not an image", headers={"Cache-Control": "max-age=600"}
        )
    )
    config = make_config()
    with pytest.raises(RuntimeFailure):
        maps.fetch_mosaic(config, maps.viewport_for(config))
    assert cached_bytes() == []
