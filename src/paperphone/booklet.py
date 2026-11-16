from __future__ import annotations

import base64
import datetime as dt
import html
import io
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from PIL import Image

from . import paperapps
from .config import PanelSelection
from .maps import ATTRIBUTION as MAP_ATTRIBUTION
from .model import Contact, Event, Task, task_sort_key
from .timeutil import clock, cover_date, weather_date
from .weather import WeatherReport

PAGE_WIDTH = 842
PAGE_HEIGHT = 595
MARGIN = 28
SLOT_WIDTH = 154
SLOT_HEIGHT = 242
COLUMN_X = (0, 212, 420, 632)
ROW_Y = (0, 300)

SLOT_ORDER = ("contacts", "calendar", "tasks", "photo", "notes", "cover", "weather", "paper_app")
ROTATED = {"contacts", "calendar"}

MAX_CONTACTS = 7
MAX_EVENTS = 6
MAX_TASKS = 9


@dataclass
class BookletContent:
    name: str
    date: dt.date
    zone: ZoneInfo
    panels: PanelSelection = field(default_factory=PanelSelection)
    contacts: list[Contact] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    weather: WeatherReport | None = None
    photo: Image.Image | None = None
    map_page: object | None = None
    paper_app: str = paperapps.DEFAULT_PAPER_APP


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _data_uri(image: Image.Image, fmt: str = "PNG") -> str:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/{fmt.lower()};base64,{encoded}"


def _stylesheet() -> str:
    assets = paperapps.asset_root()
    font_dir = assets / "fonts"
    dots = paperapps.asset_url(assets / "dots.svg")
    varela = paperapps.asset_url(font_dir / "varela_regular.otf")
    worksans = paperapps.asset_url(font_dir / "worksans_regular.ttf")
    return f"""
@font-face {{ font-family: Varela; src: url("{varela}"); }}
@font-face {{ font-family: "Work Sans"; src: url("{worksans}"); }}
@page {{ size: 297mm 210mm; margin: 0; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  font-family: Varela, "Work Sans", "Noto Sans CJK JP", "Noto Sans JP",
    "Noto Sans", "DejaVu Sans", sans-serif;
  color: #000;
}}
.page {{ position: relative; width: {PAGE_WIDTH}pt; height: {PAGE_HEIGHT}pt;
  overflow: hidden; page-break-after: always; }}
.page:last-child {{ page-break-after: auto; }}
.slot {{ position: absolute; width: {SLOT_WIDTH}pt; height: {SLOT_HEIGHT}pt;
  overflow: hidden; }}
.panel {{ position: absolute; left: 0; top: 0; width: {SLOT_WIDTH}pt;
  height: {SLOT_HEIGHT}pt; }}
.rotated .panel {{ transform: rotate(180deg); transform-origin: 50% 50%; }}
.title {{ font-family: Varela; font-size: 11.33pt; line-height: 11.33pt;
  letter-spacing: 0.1pt; }}
.dots {{ background-image: url("{dots}"); background-repeat: repeat;
  background-size: 17pt 17pt; }}
.fill {{ position: absolute; left: 0; top: 0; width: {SLOT_WIDTH}pt;
  height: {SLOT_HEIGHT}pt; }}
.contact-list {{ position: absolute; left: 0; top: 24pt; }}
.contact {{ margin-top: 24pt; }}
.contact:first-child {{ margin-top: 0; }}
.contact-name {{ font-family: "Work Sans"; font-size: 7.31pt;
  line-height: 8pt; letter-spacing: 0.12pt; white-space: nowrap;
  overflow: hidden; }}
.contact-phone {{ font-family: "Work Sans"; font-size: 7.31pt;
  line-height: 8pt; letter-spacing: 0.12pt; white-space: nowrap;
  overflow: hidden; }}
.rule {{ border-top: 0.5pt solid #000; width: 154pt; margin-top: 9pt; }}
.event {{ margin-top: 15pt; }}
.event-name {{ font-family: Varela; font-size: 9pt; line-height: 10pt;
  white-space: nowrap; overflow: hidden; }}
.event-time {{ font-family: "Work Sans"; font-size: 6.47pt; line-height: 8pt;
  letter-spacing: 0.12pt; margin-top: 1pt; }}
.task-list {{ position: absolute; left: 0; top: 24pt; }}
.task {{ position: relative; height: 22pt; }}
.task.empty {{ height: 20pt; }}
.circle {{ position: absolute; left: 0; top: 2pt; width: 5.8pt;
  height: 5.8pt; border: 0.5pt solid #000; border-radius: 50%; }}
.task.empty .circle {{ top: 6pt; }}
.task-name {{ position: absolute; left: 16pt; top: 0; width: 138pt;
  font-family: Varela; font-size: 9pt; line-height: 9pt;
  white-space: nowrap; overflow: hidden; }}
.task-due {{ position: absolute; left: 16pt; top: 10pt;
  font-family: "Work Sans"; font-size: 6.47pt; line-height: 7pt; }}
.photo {{ display: block; width: 117.5pt; height: auto; }}
.notes-dots {{ position: absolute; left: 0; top: 38pt; width: 153pt;
  height: 204pt; }}
.cover-name {{ font-family: Varela; font-size: 17.78pt; line-height: 21pt;
  letter-spacing: 0.1pt; }}
.cover-date {{ position: absolute; left: 0; bottom: 0; font-family: Varela;
  font-size: 9pt; }}
.weather-meta {{ font-family: "Work Sans"; font-size: 7.31pt;
  line-height: 9pt; margin-top: 8pt; }}
.weather-period {{ position: relative; height: 35pt; margin-top: 2pt; }}
.weather-label {{ font-family: Varela; font-size: 8.5pt; line-height: 9pt;
  letter-spacing: 0.12pt; }}
.weather-period .rule {{ margin-top: 2pt; }}
.weather-icon {{ position: absolute; left: 0; top: 12pt; width: 19pt;
  height: 19pt; }}
.weather-temp {{ position: absolute; left: 26pt; top: 12pt;
  font-family: Varela; font-size: 8.5pt; }}
.weather-name {{ position: absolute; left: 26pt; top: 23pt;
  font-family: "Work Sans"; font-size: 6pt; }}
.weather-attribution {{ position: absolute; right: 0; bottom: 0;
  font-family: "Work Sans"; font-size: 4.5pt; }}
.paper-app {{ display: block; width: 154pt; height: 242pt; }}
.fold-square {{ position: absolute; width: 5pt; height: 5pt;
  background: #000; }}
.fold-circle {{ position: absolute; width: 6pt; height: 6pt;
  background: #000; border-radius: 50%; }}
.map-title {{ position: absolute; left: 28pt; top: 28pt; }}
.map-address {{ position: absolute; left: 28pt; width: 250pt; }}
.map-marker {{ position: absolute; left: 0; top: 0; width: 14pt;
  height: 14pt; background: #000; border-radius: 50%;
  color: #fff; font-family: Varela; font-size: 8.36pt;
  text-align: center; line-height: 14pt; }}
.direction {{ position: absolute; left: 24pt; top: 0; font-family: Varela;
  font-size: 6pt; line-height: 7pt; letter-spacing: 0.12pt; }}
.place-name {{ position: absolute; left: 24pt; top: 9pt;
  font-family: "Work Sans"; font-size: 9pt; line-height: 10pt; }}
.address-line {{ position: absolute; left: 24pt; font-family: "Work Sans";
  font-size: 9pt; line-height: 10pt; }}
.map-image {{ position: absolute; left: 322pt; top: 28pt; width: 493pt;
  height: 493pt; }}
.map-attribution {{ position: absolute; left: 322pt; top: 524pt;
  font-family: "Work Sans"; font-size: 5.5pt; }}
.map-dots {{ position: absolute; left: 28pt; top: 260pt; width: 250pt;
  height: 272pt; }}
"""


def _slot(name: str, content: BookletContent) -> str:
    index = SLOT_ORDER.index(name)
    x = COLUMN_X[index % 4] + MARGIN
    y = ROW_Y[index // 4] + MARGIN
    inner, enabled = _slot_body(name, content)
    rotated = name in ROTATED and enabled
    classes = "slot rotated" if rotated else "slot"
    return f'<div class="{classes}" style="left:{x}pt;top:{y}pt">{inner}</div>'


def _slot_body(name: str, content: BookletContent) -> tuple[str, bool]:
    panels = content.panels
    if name == "cover":
        return _cover(content), True
    if name == "contacts":
        if not panels.contacts:
            return _empty(), False
        return _contacts(content), True
    if name == "calendar":
        if not panels.calendar:
            return _empty(), False
        return _calendar(content), True
    if name == "tasks":
        if not panels.tasks:
            return _empty(), False
        return _tasks(content), True
    if name == "photo":
        if not panels.photo or content.photo is None:
            return _empty(), False
        return _photo(content.photo), True
    if name == "notes":
        if not panels.notes:
            return _empty(), False
        return _notes(), True
    if name == "weather":
        if not panels.weather:
            return _empty(), False
        return _weather(content), True
    if name == "paper_app":
        if not panels.paper_app:
            return _empty(), False
        return _paper_app(content.paper_app), True
    return _empty(), False


def _empty() -> str:
    return '<div class="panel"><div class="dots fill"></div></div>'


def _contacts(content: BookletContent) -> str:
    contacts = sorted(content.contacts, key=lambda contact: contact.name.casefold())[
        :MAX_CONTACTS
    ]
    rows = []
    for contact in contacts:
        rows.append(
            '<div class="contact">'
            f'<div class="contact-name">{_escape(contact.name.upper())}</div>'
            f'<div class="contact-phone">{_escape(contact.phone)}</div>'
            "</div>"
        )
    return (
        '<div class="panel"><div class="title">CONTACTS</div>'
        f'<div class="contact-list">{"".join(rows)}</div></div>'
    )


def _calendar(content: BookletContent) -> str:
    events = sorted(content.events, key=lambda event: event.start)[:MAX_EVENTS]
    rows = ['<div class="rule"></div>']
    for event in events:
        time_html = ""
        if not event.all_day:
            time_html = (
                f'<div class="event-time">{clock(event.start)} - '
                f"{clock(event.end)}</div>"
            )
        rows.append(
            '<div class="event">'
            f'<div class="event-name">{_escape(event.summary)}</div>'
            f"{time_html}</div>"
        )
    return (
        '<div class="panel"><div class="title">CALENDAR</div>'
        f'{"".join(rows)}</div>'
    )


def _tasks(content: BookletContent) -> str:
    tasks = sorted(content.tasks, key=task_sort_key)[:MAX_TASKS]
    rows = []
    for task in tasks:
        label = ""
        if task.due is not None:
            if task.due == content.date:
                label = "Today"
            elif task.due == content.date + dt.timedelta(days=1):
                label = "Tomorrow"
        label_html = f'<div class="task-due">{label}</div>' if label else ""
        rows.append(
            '<div class="task"><div class="circle"></div>'
            f'<div class="task-name">{_escape(task.summary)}</div>'
            f"{label_html}</div>"
        )
    for _ in range(max(0, MAX_TASKS - len(tasks))):
        rows.append('<div class="task empty"><div class="circle"></div></div>')
    return (
        '<div class="panel"><div class="title">TASKS</div>'
        f'<div class="task-list">{"".join(rows)}</div></div>'
    )


def _photo(photo: Image.Image) -> str:
    return (
        '<div class="panel">'
        f'<img class="photo" src="{_data_uri(photo)}" alt="">'
        "</div>"
    )


def _notes() -> str:
    return (
        '<div class="panel"><div class="title">NOTES</div>'
        '<div class="notes-dots dots"></div></div>'
    )


def _cover(content: BookletContent) -> str:
    return (
        '<div class="panel">'
        f'<div class="cover-name">{_escape(content.name.upper())}\'S</div>'
        '<div class="cover-name">PHONE</div>'
        f'<div class="cover-date">{cover_date(content.date)}</div>'
        "</div>"
    )


def _weather(content: BookletContent) -> str:
    report = content.weather
    periods = report.periods if report is not None else []
    rows = []
    for period in periods:
        icon = paperapps.asset_url(paperapps.asset_root() / "weather" / f"{period.icon}.svg")
        rows.append(
            '<div class="weather-period">'
            f'<div class="weather-label">{period.label}</div>'
            '<div class="rule"></div>'
            f'<img class="weather-icon" src="{icon}" alt="">'
            f'<div class="weather-temp">{period.temperature}º</div>'
            f'<div class="weather-name">{_escape(period.name)}</div>'
            "</div>"
        )
    label = report.label if report is not None else ""
    return (
        '<div class="panel">'
        '<div class="title">WEATHER</div>'
        f'<div class="weather-meta">{_escape(label)}<br>'
        f"{_escape(weather_date(content.date))}</div>"
        f'{"".join(rows)}'
        '<div class="weather-attribution">Weather data by Open-Meteo</div>'
        "</div>"
    )


def _paper_app(name: str) -> str:
    source = paperapps.asset_url(paperapps.paper_app_path(name))
    return (
        '<div class="panel"><img class="paper-app" '
        f'style="width:154pt;height:242pt" src="{source}" alt=""></div>'
    )


def _map_page(content: BookletContent) -> str:
    page = content.map_page
    if page is None:
        return ""
    origin = page.origin
    destination = page.destination
    image_html = ""
    if page.image is not None:
        image_html = (
            f'<img class="map-image" src="{_data_uri(page.image)}" alt="">'
        )

    def address_block(place, marker: str, direction: str, top: int) -> str:
        lines = list(place.address[:2]) or [place.label]
        address = "".join(
            f'<div class="address-line" style="top:{9 + (index + 1) * 11}pt">'
            f"{_escape(line)}</div>"
            for index, line in enumerate(lines)
        )
        return (
            f'<div class="map-address" style="top:{top}pt">'
            f'<div class="map-marker">{marker}</div>'
            f'<div class="direction">{direction}</div>'
            f'<div class="place-name">{_escape(place.label)}</div>'
            f"{address}</div>"
        )

    return (
        '<div class="page">'
        '<div class="map-title title">MAPS</div>'
        f'{address_block(origin, "A", "LEAVING FROM", 70)}'
        f'{address_block(destination, "B", "GOING TO", 170)}'
        f"{image_html}"
        f'<div class="map-attribution">{MAP_ATTRIBUTION}</div>'
        '<div class="map-dots dots"></div>'
        '<div class="fold-circle" style="left:30pt;top:561pt"></div>'
        '<div class="fold-circle" style="left:809pt;top:561pt"></div>'
        "</div>"
    )


def render_html(content: BookletContent) -> str:
    slots = "".join(_slot(name, content) for name in SLOT_ORDER)
    page_one = (
        '<div class="page">'
        f"{slots}"
        '<div class="fold-square" style="left:629pt;top:28pt"></div>'
        '<div class="fold-square" style="left:629pt;top:565pt"></div>'
        "</div>"
    )
    pages = [page_one]
    if content.panels.map and content.map_page is not None:
        pages.append(_map_page(content))
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<style>{_stylesheet()}</style></head><body>{''.join(pages)}</body></html>"
    )
