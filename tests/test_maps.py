from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from paperphone import maps
from paperphone.config import MapsConfig, PlaceConfig

FIXTURES = Path(__file__).parent / "fixtures"
TILE = (FIXTURES / "tiles" / "tile.png").read_bytes()
ROUTE = json.loads((FIXTURES / "route-response.json").read_text())


def make_config(tile_url="https://tiles.test/{z}/{x}/{y}.png", router="") -> MapsConfig:
    return MapsConfig(
        origin=PlaceConfig(35.6812, 139.7671, "Home", ("1-1 Chiyoda", "Tokyo")),
        destination=PlaceConfig(35.6900, 139.7000, "Station", ("2-2 Chuo", "Tokyo")),
        tile_url=tile_url,
        router_url=router,
    )


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


@respx.mock
def test_fetch_route_decodes_shape():
    respx.post("https://router.test/route").mock(
        return_value=httpx.Response(200, json=ROUTE)
    )
    points = maps.fetch_route(make_config(router="https://router.test/route"))
    assert len(points) == 3


@respx.mock
def test_tile_failure_returns_no_image():
    respx.get(url__regex=r"https://tiles\.test/.*").mock(
        side_effect=httpx.ConnectError("offline")
    )
    warnings = []
    page = maps.build_map_page(make_config(), warn=warnings.append)
    assert page.image is None
    assert warnings


@respx.mock
def test_route_failure_keeps_map():
    respx.get(url__regex=r"https://tiles\.test/.*").mock(
        return_value=httpx.Response(200, content=TILE)
    )
    respx.post("https://router.test/route").mock(
        side_effect=httpx.ConnectError("offline")
    )
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
    respx.post("https://router.test/route").mock(
        return_value=httpx.Response(200, json=ROUTE)
    )
    page = maps.build_map_page(
        make_config(router="https://router.test/route"), warn=lambda message: None
    )
    assert page.image is not None
    assert page.has_route is True
    assert page.image.mode == "L"
    assert page.image.getextrema()[0] == 0


def test_attribution_constant():
    assert maps.ATTRIBUTION == "© OpenStreetMap contributors"
