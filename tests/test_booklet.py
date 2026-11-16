from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from PIL import Image
from pypdf import PdfReader

from paperphone import booklet, maps, photos
from paperphone.booklet import BookletContent
from paperphone.config import PanelSelection, PlaceConfig
from paperphone.model import Contact, Event, Task
from paperphone.rendering import write_pdf_atomic
from paperphone.weather import WeatherPeriod, WeatherReport

DATE = dt.date(2026, 11, 17)
ZONE = ZoneInfo("Asia/Tokyo")


def content(**kwargs) -> BookletContent:
    base = dict(name="Aki", date=DATE, zone=ZONE)
    base.update(kwargs)
    return BookletContent(**base)


def render(data: BookletContent, tmp_path: Path) -> tuple[Path, str]:
    html = booklet.render_html(data)
    pages = 2 if data.panels.map and data.map_page is not None else 1
    path = write_pdf_atomic(
        tmp_path / "book.pdf", html, rotate_map=pages == 2, expected_pages=pages
    )
    return path, html


def test_page_size_and_single_page(tmp_path):
    path, _ = render(content(panels=PanelSelection(notes=True)), tmp_path)
    reader = PdfReader(str(path))
    assert len(reader.pages) == 1
    box = reader.pages[0].mediabox
    assert round(float(box.width)) == 842
    assert round(float(box.height)) == 595


def test_fixed_slot_order_and_positions(tmp_path):
    _, html = render(
        content(
            panels=PanelSelection(
                contacts=True, calendar=True, tasks=True, notes=True, weather=True, paper_app=True
            )
        ),
        tmp_path,
    )
    positions = [
        'style="left:28pt;top:28pt"',
        'style="left:240pt;top:28pt"',
        'style="left:448pt;top:28pt"',
        'style="left:660pt;top:28pt"',
        'style="left:28pt;top:328pt"',
        'style="left:240pt;top:328pt"',
        'style="left:448pt;top:328pt"',
        'style="left:660pt;top:328pt"',
    ]
    for position in positions:
        assert position in html
    assert html.index("CONTACTS") < html.index("CALENDAR") < html.index("TASKS")
    assert html.index("NOTES") < html.index("PHONE") < html.index("WEATHER")


def test_empty_panels_show_cover_and_dots(tmp_path):
    data = content(panels=PanelSelection())
    _, html = render(data, tmp_path)
    assert "CONTACTS" not in html
    assert "PHONE" in html
    assert html.count("dots fill") == 7


def test_contacts_are_uppercased_and_sorted(tmp_path):
    data = content(
        panels=PanelSelection(contacts=True),
        contacts=[Contact("b", "bea ito", "123"), Contact("a", "Aki Tanaka", "")],
    )
    _, html = render(data, tmp_path)
    assert "AKI TANAKA" in html
    assert "BEA ITO" in html
    assert html.index("AKI TANAKA") < html.index("BEA ITO")


def test_calendar_formats_times_and_skips_all_day_time(tmp_path):
    events = [
        Event("Standup", dt.datetime(2026, 11, 17, 9, tzinfo=ZONE),
              dt.datetime(2026, 11, 17, 10, tzinfo=ZONE)),
        Event("Birthday", dt.datetime(2026, 11, 17, tzinfo=ZONE),
              dt.datetime(2026, 11, 18, tzinfo=ZONE), all_day=True),
    ]
    _, html = render(content(panels=PanelSelection(calendar=True), events=events), tmp_path)
    assert "Standup" in html
    assert "09:00 - 10:00" in html
    assert html.count('class="event-time"') == 1


def test_calendar_limits_to_six(tmp_path):
    events = [
        Event(f"Event {index}", dt.datetime(2026, 11, 17, index, tzinfo=ZONE),
              dt.datetime(2026, 11, 17, index, 30, tzinfo=ZONE))
        for index in range(8)
    ]
    _, html = render(content(panels=PanelSelection(calendar=True), events=events), tmp_path)
    assert "Event 5" in html
    assert "Event 6" not in html


def test_tasks_show_today_tomorrow_and_empty_circles(tmp_path):
    tasks = [Task("Pay rent", dt.date(2026, 11, 17)), Task("Buy milk", dt.date(2026, 11, 18))]
    _, html = render(content(panels=PanelSelection(tasks=True), tasks=tasks), tmp_path)
    assert "Today" in html
    assert "Tomorrow" in html
    assert html.count('class="circle"') == 9


def test_tasks_show_max_nine_without_empty_circles(tmp_path):
    tasks = [Task(f"Task {index:02d}", None) for index in range(11)]
    _, html = render(content(panels=PanelSelection(tasks=True), tasks=tasks), tmp_path)
    assert "Task 08" in html
    assert "Task 09" not in html
    assert html.count('class="circle"') == 9


def test_cover_uses_capitalized_name_and_date(tmp_path):
    _, html = render(content(name="Aki", panels=PanelSelection()), tmp_path)
    assert "AKI&#x27;S" in html or "AKI'S" in html
    assert "17 November 2026" in html


def test_weather_panel_content(tmp_path):
    report = WeatherReport(
        "Tokyo",
        DATE,
        [
            WeatherPeriod(9, "MORNING", 12, 0, "Clear", "sunny"),
            WeatherPeriod(12, "AFTERNOON", 15, 3, "Clouds", "cloudy"),
            WeatherPeriod(18, "EVENING", 10, 61, "Rain", "rain"),
        ],
    )
    _, html = render(
        content(panels=PanelSelection(weather=True), weather=report), tmp_path
    )
    assert "WEATHER" in html
    assert "MORNING" in html and "AFTERNOON" in html and "EVENING" in html
    assert "12º" in html
    assert "Clouds" in html
    assert "Open-Meteo" in html


def test_weather_without_forecast_still_shows_header(tmp_path):
    report = WeatherReport("Tokyo", DATE, [])
    _, html = render(
        content(panels=PanelSelection(weather=True), weather=report), tmp_path
    )
    assert "WEATHER" in html
    assert "Tokyo" in html
    assert "MORNING" not in html


def test_notes_has_dots_and_title(tmp_path):
    _, html = render(content(panels=PanelSelection(notes=True)), tmp_path)
    assert "NOTES" in html
    assert "notes-dots dots" in html


def test_paper_app_all_names_resolve():
    from paperphone.paperapps import PAPER_APPS, paper_app_path

    assert len(PAPER_APPS) == 13
    for name in PAPER_APPS:
        assert paper_app_path(name).exists()


def test_paper_app_is_stretched(tmp_path):
    _, html = render(
        content(panels=PanelSelection(paper_app=True), paper_app="sudoku"), tmp_path
    )
    assert "paper_apps/sudoku.png" in html
    assert "width:154pt;height:242pt" in html


def test_rotated_panels_use_transform(tmp_path):
    _, html = render(
        content(
            panels=PanelSelection(contacts=True, calendar=True),
            contacts=[Contact("a", "Aki", "")],
            events=[Event("X", dt.datetime(2026, 11, 17, 9, tzinfo=ZONE),
                          dt.datetime(2026, 11, 17, 10, tzinfo=ZONE))],
        ),
        tmp_path,
    )
    assert html.count("slot rotated") == 2


def test_fold_marks(tmp_path):
    _, html = render(content(), tmp_path)
    assert html.count('class="fold-square"') == 2
    assert "left:629pt;top:28pt" in html
    assert "left:629pt;top:565pt" in html


def test_map_page_is_rotated_and_attributed(tmp_path):
    map_page = maps.MapPage(
        origin=PlaceConfig(35.68, 139.76, "Home", ("1-1 Chiyoda", "Tokyo")),
        destination=PlaceConfig(35.69, 139.70, "Station", ("2-2 Chuo", "Tokyo")),
        image=Image.new("L", (100, 100), "white"),
    )
    data = content(panels=PanelSelection(map=True), map_page=map_page)
    path, html = render(data, tmp_path)
    reader = PdfReader(str(path))
    assert len(reader.pages) == 2
    assert reader.pages[1].rotation == 180
    assert "© OpenStreetMap contributors" in html
    assert "LEAVING FROM" in html and "GOING TO" in html
    assert "LEAVING FROM" in reader.pages[1].extract_text()
    assert "fold-circle" in html


def test_map_without_image_keeps_page(tmp_path):
    place = PlaceConfig(35.68, 139.76, "Home", ("1-1 Chiyoda", "Tokyo"))
    map_page = maps.MapPage(origin=place, destination=place, image=None)
    path, _ = render(content(panels=PanelSelection(map=True), map_page=map_page), tmp_path)
    assert len(PdfReader(str(path)).pages) == 2


def test_photo_panel_embeds_grayscale(tmp_path):
    photo = Image.new("L", (490, 300), 128)
    _, html = render(content(panels=PanelSelection(photo=True), photo=photo), tmp_path)
    assert "data:image/png;base64," in html


def test_photo_preparation_rotates_landscape(tmp_path):
    source = tmp_path / "photo.jpg"
    Image.new("RGB", (800, 400), "white").save(source)
    prepared = photos.prepare_photo(str(source))
    assert prepared is not None
    assert prepared.mode == "L"
    assert prepared.height > prepared.width


def test_unreadable_photo_raises(tmp_path):
    with pytest.raises(photos.PhotoError):
        photos.prepare_photo(str(tmp_path / "missing.jpg"))


def test_cjk_name_renders_without_tofu(tmp_path):
    data = content(name="あき", panels=PanelSelection())
    path, _ = render(data, tmp_path)
    text = PdfReader(str(path)).pages[0].extract_text()
    assert "あき" in text


def test_monochrome_pdf_has_no_color_operators(tmp_path):
    path, _ = render(
        content(
            panels=PanelSelection(contacts=True),
            contacts=[Contact("a", "Aki", "123")],
        ),
        tmp_path,
    )
    import re

    raw = PdfReader(str(path)).pages[0].get_contents().get_data().decode("latin-1")
    for match in re.findall(r"([\d.]+) ([\d.]+) ([\d.]+) (?:rg|RG)", raw):
        red, green, blue = (float(value) for value in match)
        assert red == green == blue


def test_paper_app_assets_are_grayscale():
    from paperphone.paperapps import PAPER_APPS, paper_app_path

    for name in PAPER_APPS:
        with Image.open(paper_app_path(name)) as image:
            assert image.mode in ("L", "1"), name
