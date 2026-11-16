from __future__ import annotations

import datetime as dt
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from zoneinfo import ZoneInfo

from . import booklet, eds, maps, photos, rendering
from . import weather as weather_mod
from .config import Config
from .model import Contact, Event, SourceInfo, Task, task_sort_key
from .timeutil import day_bounds


class WarningCollector:
    def __init__(self, stream=None):
        self._stream = stream or sys.stderr
        self.messages: list[str] = []

    def __call__(self, message: str) -> None:
        self.messages.append(message)
        print(f"paperphone: 警告: {message}", file=self._stream)


def _sources(registry, credentials, wanted_kinds: set[str]) -> dict[str, SourceInfo]:
    infos = eds.list_sources(registry, credentials)
    return {info.uid: info for info in infos if info.kind in wanted_kinds}


def _selected_contacts(config: Config, registry, credentials, warn) -> list[Contact]:
    selected = list(config.sources.contacts)
    if not selected:
        return []
    infos = _sources(registry, credentials, {"contacts"})
    contacts: dict[str, Contact] = {}
    for uid, info in infos.items():
        if not info.usable_credentials:
            warn(f"認証情報が無いため連絡先を飛ばします: {info.name}")
            continue
        source = eds.find_source(registry, uid)
        if source is None:
            continue
        try:
            for contact in eds.read_contacts(source):
                contacts[contact.uid] = contact
        except Exception as exc:
            warn(f"連絡先を読めません: {info.name}: {exc}")
    result = []
    for uid in selected:
        contact = contacts.get(uid)
        if contact is None:
            warn(f"連絡先が見つかりません: {uid}")
            continue
        result.append(contact)
    result.sort(key=lambda contact: contact.name.casefold())
    return result


def _read_sources(
    config: Config, registry, credentials, warn, verbose, date: dt.date, zone: ZoneInfo
) -> tuple[list[Event], list[Task]]:
    infos = _sources(registry, credentials, {"calendar", "tasks"})
    events: list[Event] = []
    tasks: list[Task] = []

    start, end = day_bounds(date, zone)
    for uid in config.sources.calendars:
        info = infos.get(uid)
        if info is None or info.kind != "calendar":
            warn(f"カレンダーが見つかりません: {uid}")
            continue
        if not info.usable_credentials:
            warn(f"認証情報が無いためカレンダーを飛ばします: {info.name}")
            continue
        source = eds.find_source(registry, uid)
        if source is None:
            warn(f"カレンダーが見つかりません: {uid}")
            continue
        try:
            found = eds.read_events(source, start, end, zone)
            events.extend(found)
            if verbose:
                print(f"paperphone: {info.name}: {len(found)} 件の予定", file=sys.stderr)
        except Exception as exc:
            warn(f"カレンダーを読めません: {info.name}: {exc}")

    for uid in config.sources.tasks:
        info = infos.get(uid)
        if info is None or info.kind != "tasks":
            warn(f"タスクリストが見つかりません: {uid}")
            continue
        if not info.usable_credentials:
            warn(f"認証情報が無いためタスクリストを飛ばします: {info.name}")
            continue
        source = eds.find_source(registry, uid)
        if source is None:
            warn(f"タスクリストが見つかりません: {uid}")
            continue
        try:
            found = eds.read_tasks(source)
            tasks.extend(found)
            if verbose:
                print(f"paperphone: {info.name}: {len(found)} 件のタスク", file=sys.stderr)
        except Exception as exc:
            warn(f"タスクリストを読めません: {info.name}: {exc}")

    events.sort(key=lambda event: (event.start, event.summary.casefold()))
    tasks.sort(key=task_sort_key)
    return events, tasks


def _filter_day(events: list[Event], date: dt.date, zone: ZoneInfo) -> list[Event]:
    start, end = day_bounds(date, zone)
    result = [event for event in events if event.start < end and event.end > start]
    result.sort(key=lambda event: (event.start, event.summary.casefold()))
    return result


def generate(
    config: Config,
    *,
    date: dt.date,
    zone: ZoneInfo,
    out: Path,
    no_map: bool = False,
    verbose: bool = False,
    registry=None,
) -> Path:
    warn = WarningCollector()
    panels = config.panels

    needs_eds = bool(
        (panels.contacts and config.sources.contacts)
        or (panels.calendar and config.sources.calendars)
        or (panels.tasks and config.sources.tasks)
    )
    contacts: list[Contact] = []
    events: list[Event] = []
    tasks: list[Task] = []
    if needs_eds:
        try:
            registry = registry or eds.open_registry()
            credentials = eds.CredentialStore(registry)
            if panels.contacts and config.sources.contacts:
                contacts = _selected_contacts(config, registry, credentials, warn)
            events, tasks = _read_sources(
                config, registry, credentials, warn, verbose, date, zone
            )
        except eds.EdsUnavailable as exc:
            warn(str(exc))

    zone_events = _filter_day(events, date, zone)

    weather_report = None
    map_page = None

    with ThreadPoolExecutor(max_workers=2) as executor:
        weather_future = None
        map_future = None
        if panels.weather and config.weather is not None:
            weather_future = executor.submit(
                weather_mod.get_report,
                config.weather.latitude,
                config.weather.longitude,
                config.weather.label,
                zone,
                date,
                warn=warn,
            )
        if panels.map and config.maps is not None and not no_map:
            map_future = executor.submit(
                maps.build_map_page,
                config.maps,
                warn=warn,
            )
        if weather_future is not None:
            try:
                weather_report = weather_future.result(timeout=30)
            except FutureTimeout:
                warn("天気の取得がタイムアウトしました")
            except Exception as exc:
                warn(f"天気を取得できません: {exc}")
        if map_future is not None:
            try:
                map_page = map_future.result(timeout=60)
            except FutureTimeout:
                warn("地図の取得がタイムアウトしました")
                map_page = maps.MapPage(
                    origin=config.maps.origin,
                    destination=config.maps.destination,
                    image=None,
                )
            except Exception as exc:
                warn(f"地図を取得できません: {exc}")
                map_page = maps.MapPage(
                    origin=config.maps.origin,
                    destination=config.maps.destination,
                    image=None,
                )

    photo_image = None
    if panels.photo:
        try:
            photo_image = photos.prepare_photo(config.photo)
        except photos.PhotoError as exc:
            warn(str(exc))

    content = booklet.BookletContent(
        name=config.name,
        date=date,
        zone=zone,
        panels=panels,
        contacts=contacts,
        events=zone_events,
        tasks=tasks,
        weather=weather_report,
        photo=photo_image,
        map_page=map_page,
        paper_app=config.paper_app,
    )
    html_text = booklet.render_html(content)
    expected_pages = 2 if (panels.map and map_page is not None) else 1
    destination = rendering.write_pdf_atomic(
        out,
        html_text,
        rotate_map=expected_pages == 2,
        expected_pages=expected_pages,
    )
    return destination
