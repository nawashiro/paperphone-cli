from __future__ import annotations

import io
import math
from dataclasses import dataclass

import httpx
from PIL import Image, ImageDraw

from . import __version__
from .config import MapsConfig, PlaceConfig
from .errors import RuntimeFailure

TILE_SIZE = 256
MAP_PIXELS = 1024
MIN_ZOOM = 12
MAX_ZOOM = 17
ATTRIBUTION = "© OpenStreetMap contributors"
USER_AGENT = f"paperphone/{__version__} (+https://github.com/google/paper-phone)"


@dataclass(frozen=True)
class MapPage:
    origin: PlaceConfig
    destination: PlaceConfig
    image: Image.Image | None
    has_route: bool = False


@dataclass(frozen=True)
class _Viewport:
    zoom: int
    center_x: float
    center_y: float


def lonlat_to_world(latitude: float, longitude: float, zoom: int) -> tuple[float, float]:
    scale = TILE_SIZE * (2**zoom)
    x = (longitude + 180.0) / 360.0 * scale
    sin_latitude = math.sin(math.radians(latitude))
    y = (
        0.5
        - math.log((1 + sin_latitude) / (1 - sin_latitude)) / (4 * math.pi)
    ) * scale
    return x, y


def _fit_zoom(south: float, north: float, west: float, east: float, pixels: int) -> int:
    x_west, y_north = lonlat_to_world(north, west, 0)
    x_east, y_south = lonlat_to_world(south, east, 0)
    needed = max(abs(x_east - x_west), abs(y_south - y_north), 1e-9)
    zoom = math.floor(math.log2(pixels * 0.8 / needed))
    return max(MIN_ZOOM, min(MAX_ZOOM, zoom))


def choose_zoom(latitude_span: float, longitude_span: float, pixels: int = MAP_PIXELS) -> int:
    if latitude_span <= 0 and longitude_span <= 0:
        return MAX_ZOOM
    return _fit_zoom(
        -min(89.0, latitude_span / 2),
        min(89.0, latitude_span / 2),
        -longitude_span / 2,
        longitude_span / 2,
        pixels,
    )


def viewport_for(config: MapsConfig, pixels: int = MAP_PIXELS) -> _Viewport:
    south = min(config.origin.latitude, config.destination.latitude)
    north = max(config.origin.latitude, config.destination.latitude)
    west = min(config.origin.longitude, config.destination.longitude)
    east = max(config.origin.longitude, config.destination.longitude)
    zoom = _fit_zoom(south, north, west, east, pixels)
    x_west, y_north = lonlat_to_world(north, west, zoom)
    x_east, y_south = lonlat_to_world(south, east, zoom)
    return _Viewport(
        zoom=zoom,
        center_x=(x_west + x_east) / 2,
        center_y=(y_north + y_south) / 2,
    )


def tile_range(viewport: _Viewport, pixels: int = MAP_PIXELS) -> tuple[int, int, int, int]:
    half = pixels / 2
    max_index = 2**viewport.zoom
    x0 = math.floor((viewport.center_x - half) / TILE_SIZE)
    x1 = math.floor((viewport.center_x + half - 1) / TILE_SIZE)
    y0 = math.floor((viewport.center_y - half) / TILE_SIZE)
    y1 = math.floor((viewport.center_y + half - 1) / TILE_SIZE)
    x0 = max(0, min(max_index - 1, x0))
    x1 = max(0, min(max_index - 1, x1))
    y0 = max(0, min(max_index - 1, y0))
    y1 = max(0, min(max_index - 1, y1))
    return x0, y0, x1, y1


def _tile_url(template: str, zoom: int, x: int, y: int) -> str:
    return template.format(z=zoom, x=x, y=y)


def fetch_mosaic(
    config: MapsConfig,
    viewport: _Viewport,
    *,
    client: httpx.Client | None = None,
    pixels: int = MAP_PIXELS,
) -> Image.Image:
    x0, y0, x1, y1 = tile_range(viewport, pixels)
    columns = x1 - x0 + 1
    rows = y1 - y0 + 1
    if columns <= 0 or rows <= 0:
        raise RuntimeFailure("地図タイルの範囲を決められません")
    mosaic = Image.new("RGB", (columns * TILE_SIZE, rows * TILE_SIZE), "white")
    owns_client = client is None
    http = client or httpx.Client(timeout=12.0, headers={"User-Agent": USER_AGENT})
    try:
        for row in range(rows):
            for column in range(columns):
                url = _tile_url(config.tile_url, viewport.zoom, x0 + column, y0 + row)
                response = http.get(url)
                response.raise_for_status()
                with Image.open(io.BytesIO(response.content)) as tile:
                    mosaic.paste(tile.convert("RGB"), (column * TILE_SIZE, row * TILE_SIZE))
    except (httpx.HTTPError, OSError) as exc:
        raise RuntimeFailure(f"地図タイルを取得できません: {exc}") from exc
    finally:
        if owns_client:
            http.close()
    half = pixels / 2
    left = int(round(viewport.center_x - half - x0 * TILE_SIZE))
    top = int(round(viewport.center_y - half - y0 * TILE_SIZE))
    cropped = mosaic.crop((left, top, left + pixels, top + pixels))
    return cropped


def decode_polyline(encoded: str, precision: int = 6) -> list[tuple[float, float]]:
    factor = 10**precision
    index = 0
    latitude = 0
    longitude = 0
    points: list[tuple[float, float]] = []
    while index < len(encoded):
        result = 0
        shift = 0
        while True:
            if index >= len(encoded):
                raise RuntimeFailure("polyline が途中で切れています")
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        latitude += ~(result >> 1) if result & 1 else (result >> 1)
        result = 0
        shift = 0
        while True:
            if index >= len(encoded):
                raise RuntimeFailure("polyline が途中で切れています")
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        longitude += ~(result >> 1) if result & 1 else (result >> 1)
        points.append((latitude / factor, longitude / factor))
    return points


def fetch_route(config: MapsConfig, *, client: httpx.Client | None = None) -> list[tuple[float, float]]:
    if not config.router_url:
        return []
    payload = {
        "locations": [
            {"lat": config.origin.latitude, "lon": config.origin.longitude},
            {"lat": config.destination.latitude, "lon": config.destination.longitude},
        ],
        "costing": "pedestrian",
        "units": "kilometers",
    }
    owns_client = client is None
    http = client or httpx.Client(timeout=12.0, headers={"User-Agent": USER_AGENT})
    try:
        response = http.post(config.router_url, json=payload)
        response.raise_for_status()
        data = response.json()
        trips = data.get("trips") or []
        if not trips and data.get("trip"):
            trips = [data["trip"]]
        points: list[tuple[float, float]] = []
        for leg in trips[0].get("legs") or []:
            shape = leg.get("shape")
            if shape:
                points.extend(decode_polyline(str(shape)))
        return points
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeFailure(f"徒歩経路を取得できません: {exc}") from exc
    finally:
        if owns_client:
            http.close()


def draw_route(image: Image.Image, points: list[tuple[float, float]], viewport: _Viewport) -> None:
    if not points:
        return
    half = image.width / 2
    origin_x = viewport.center_x - half
    origin_y = viewport.center_y - half
    pixels = [
        (
            lonlat_to_world(latitude, longitude, viewport.zoom)[0] - origin_x,
            lonlat_to_world(latitude, longitude, viewport.zoom)[1] - origin_y,
        )
        for latitude, longitude in points
    ]
    draw = ImageDraw.Draw(image)
    draw.line(pixels, fill=(0, 0, 0), width=4, joint="curve")


def build_map_page(
    config: MapsConfig,
    *,
    warn,
    client: httpx.Client | None = None,
) -> MapPage:
    viewport = viewport_for(config)
    image: Image.Image | None = None
    points: list[tuple[float, float]] = []
    try:
        image = fetch_mosaic(config, viewport, client=client)
    except RuntimeFailure as exc:
        warn(str(exc))
    if image is not None and config.router_url:
        try:
            points = fetch_route(config, client=client)
            draw_route(image, points, viewport)
        except RuntimeFailure as exc:
            warn(str(exc))
    if image is not None:
        image = image.convert("L")
    return MapPage(
        origin=config.origin,
        destination=config.destination,
        image=image,
        has_route=bool(points),
    )
