from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import ConfigError
from .paperapps import DEFAULT_PAPER_APP, PAPER_APPS
from .paths import config_path, display_path, missing_config_message, require_file

PANEL_KEYS = ("contacts", "calendar", "tasks", "photo", "notes", "paper_app", "weather", "map")


@dataclass(frozen=True)
class PanelSelection:
    contacts: bool = False
    calendar: bool = False
    tasks: bool = False
    photo: bool = False
    notes: bool = False
    paper_app: bool = False
    weather: bool = False
    map: bool = False

    def enabled(self) -> tuple[str, ...]:
        return tuple(name for name in PANEL_KEYS if getattr(self, name))


@dataclass(frozen=True)
class SourceSelection:
    calendars: tuple[str, ...] = ()
    contacts: tuple[str, ...] = ()
    tasks: tuple[str, ...] = ()


@dataclass(frozen=True)
class WeatherConfig:
    latitude: float
    longitude: float
    label: str = ""


@dataclass(frozen=True)
class PlaceConfig:
    latitude: float
    longitude: float
    label: str = ""
    address: tuple[str, ...] = ()


@dataclass(frozen=True)
class MapsConfig:
    origin: PlaceConfig
    destination: PlaceConfig
    tile_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    router_url: str = ""


@dataclass(frozen=True)
class Config:
    path: Path
    name: str
    timezone: str | None = None
    panels: PanelSelection = field(default_factory=PanelSelection)
    sources: SourceSelection = field(default_factory=SourceSelection)
    weather: WeatherConfig | None = None
    maps: MapsConfig | None = None
    photo: str | None = None
    paper_app: str = DEFAULT_PAPER_APP

    def zone(self) -> ZoneInfo:
        if self.timezone:
            return load_zone(self.timezone)
        return system_zone()


def system_zone() -> ZoneInfo:
    import datetime

    local = datetime.datetime.now().astimezone().tzinfo
    name = getattr(local, "key", None) or "UTC"
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def load_zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ConfigError(f"タイムゾーンが無効です: {name}") from exc


def _table(data: dict[str, Any], key: str, where: str) -> dict[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ConfigError(f"{where}.{key} はテーブルでなければなりません")
    return value


def _string(table: dict[str, Any], key: str, where: str, *, default: str | None = None) -> str | None:
    value = table.get(key, default)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{where}.{key} は文字列でなければなりません")
    return value


def _number(table: dict[str, Any], key: str, where: str) -> float:
    value = table.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{where}.{key} は数値でなければなりません")
    return float(value)


def _bool(table: dict[str, Any], key: str, where: str) -> bool:
    value = table.get(key)
    if not isinstance(value, bool):
        raise ConfigError(f"{where}.{key} は true / false でなければなりません")
    return value


def _string_list(table: dict[str, Any], key: str, where: str) -> tuple[str, ...]:
    value = table.get(key, [])
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{where}.{key} は文字列の配列でなければなりません")
    return tuple(value)


def _latitude(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{where}.latitude は数値でなければなりません")
    latitude = float(value)
    if not -90.0 <= latitude <= 90.0:
        raise ConfigError(f"{where}.latitude は -90 から 90 の範囲で指定してください")
    return latitude


def _longitude(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{where}.longitude は数値でなければなりません")
    longitude = float(value)
    if not -180.0 <= longitude <= 180.0:
        raise ConfigError(f"{where}.longitude は -180 から 180 の範囲で指定してください")
    return longitude


def _place(table: dict[str, Any], where: str) -> PlaceConfig:
    if "latitude" not in table:
        raise ConfigError(f"{where}.latitude がありません")
    if "longitude" not in table:
        raise ConfigError(f"{where}.longitude がありません")
    raw_address = table.get("address", [])
    if isinstance(raw_address, str):
        address = (raw_address,)
    else:
        address = _string_list(table, "address", where)
    label = _string(table, "label", where, default="") or ""
    return PlaceConfig(
        latitude=_latitude(table["latitude"], where),
        longitude=_longitude(table["longitude"], where),
        label=label,
        address=address,
    )


def _panels(table: dict[str, Any], no_map: bool) -> PanelSelection:
    unknown = sorted(set(table) - set(PANEL_KEYS))
    if unknown:
        raise ConfigError(f"[panels] に知らない項目があります: {', '.join(unknown)}")
    values = {key: _bool(table, key, "[panels]") if key in table else False for key in PANEL_KEYS}
    if no_map:
        values["map"] = False
    return PanelSelection(**values)


def _sources(table: dict[str, Any]) -> SourceSelection:
    selection = SourceSelection(
        calendars=_string_list(table, "calendars", "[sources]"),
        contacts=_string_list(table, "contacts", "[sources]"),
        tasks=_string_list(table, "tasks", "[sources]"),
    )
    if len(selection.contacts) > 7:
        raise ConfigError("[sources].contacts は最大7件です")
    return selection


def _weather(table: dict[str, Any]) -> WeatherConfig:
    if "latitude" not in table:
        raise ConfigError("[weather].latitude がありません")
    if "longitude" not in table:
        raise ConfigError("[weather].longitude がありません")
    return WeatherConfig(
        latitude=_latitude(table["latitude"], "[weather]"),
        longitude=_longitude(table["longitude"], "[weather]"),
        label=_string(table, "label", "[weather]", default="") or "",
    )


def _maps(table: dict[str, Any]) -> MapsConfig:
    if "from" not in table:
        raise ConfigError("[maps].from がありません")
    if "to" not in table:
        raise ConfigError("[maps].to がありません")
    origin = _place(_table(table, "from", "[maps]"), "[maps].from")
    destination = _place(_table(table, "to", "[maps]"), "[maps].to")
    tile_url = _string(
        table, "tile_url", "[maps]", default="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    )
    router_url = _string(table, "router_url", "[maps]", default="") or ""
    assert tile_url is not None
    if "{z}" not in tile_url or "{x}" not in tile_url or "{y}" not in tile_url:
        raise ConfigError("[maps].tile_url には {z} {x} {y} を含めてください")
    return MapsConfig(
        origin=origin,
        destination=destination,
        tile_url=tile_url,
        router_url=router_url,
    )


def parse_config(data: dict[str, Any], path: Path, *, no_map: bool = False) -> Config:
    booklet = _table(data, "booklet", "設定")
    name = _string(booklet, "name", "[booklet]")
    if name is None or not name.strip():
        raise ConfigError("[booklet].name がありません")
    timezone_name = _string(booklet, "timezone", "[booklet]")
    if timezone_name is not None:
        load_zone(timezone_name)

    panels = _panels(_table(data, "panels", "設定"), no_map)
    sources = _sources(_table(data, "sources", "設定"))

    paper_app_table = _table(data, "paper_app", "設定")
    paper_app = _string(paper_app_table, "name", "[paper_app]", default=DEFAULT_PAPER_APP)
    assert paper_app is not None
    if paper_app not in PAPER_APPS:
        raise ConfigError(
            f"知らない紙アプリです: {paper_app}（選べるのは {', '.join(sorted(PAPER_APPS))}）"
        )

    photo_table = _table(data, "photo", "設定")
    photo = _string(photo_table, "path", "[photo]")

    weather = None
    if panels.weather:
        weather = _weather(_table(data, "weather", "設定"))

    maps = None
    if panels.map:
        maps = _maps(_table(data, "maps", "設定"))

    return Config(
        path=path,
        name=name.strip(),
        timezone=timezone_name,
        panels=panels,
        sources=sources,
        weather=weather,
        maps=maps,
        photo=photo,
        paper_app=paper_app,
    )


def load_config(path: Path | str | None = None, *, no_map: bool = False) -> Config:
    target = Path(path).expanduser() if path is not None else config_path()
    if path is None and not target.exists():
        raise ConfigError(missing_config_message(target))
    require_file(target)
    try:
        raw = target.read_bytes()
    except OSError as exc:
        raise ConfigError(f"設定を読めません: {display_path(target)}: {exc}") from exc
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"設定が TOML として不正です: {display_path(target)}: {exc}") from exc
    return parse_config(data, target, no_map=no_map)
