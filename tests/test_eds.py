from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from conftest import (
    FakeBookClient,
    FakeContactFields,
    FakeCredentialStore,
    FakeECalClient,
    FakeRegistry,
    FakeSource,
)

from paperphone import eds
from paperphone.model import Contact, Task


def source(uid, name, extensions):
    return FakeSource(uid, name, extensions)


def test_list_sources_classifies_and_marks_origin():
    registry = FakeRegistry(
        [
            source("gnome-cal", "Google Calendar", {eds.SOURCE_CALENDAR}),
            source("paperphone-1", "Nextcloud", {eds.SOURCE_CALENDAR}),
            source("tasks-1", "Tasks", {eds.SOURCE_TASK_LIST}),
            source("book-1", "Contacts", {eds.SOURCE_ADDRESS_BOOK}),
            source("ignored", "Mail", {"Mail Account"}),
        ]
    )
    credentials = FakeCredentialStore({"paperphone-1": "secret"})
    infos = eds.list_sources(registry, credentials)
    by_uid = {info.uid: info for info in infos}
    assert set(by_uid) == {"gnome-cal", "paperphone-1", "tasks-1", "book-1"}
    assert by_uid["gnome-cal"].kind == "calendar"
    assert by_uid["gnome-cal"].origin == "gnome"
    assert by_uid["gnome-cal"].credentials == "gnome"
    assert by_uid["paperphone-1"].origin == "paperphone"
    assert by_uid["paperphone-1"].credentials == "keyring"
    assert by_uid["tasks-1"].kind == "tasks"
    assert by_uid["book-1"].kind == "contacts"


def test_managed_source_without_password_is_not_usable():
    registry = FakeRegistry([source("paperphone-2", "Broken", {eds.SOURCE_CALENDAR})])
    infos = eds.list_sources(registry, FakeCredentialStore())
    assert infos[0].origin == "paperphone"
    assert infos[0].credentials == "none"
    assert not infos[0].usable_credentials


def test_read_events_expands_recurrence_and_filters_by_day():
    zone = ZoneInfo("Asia/Tokyo")
    start = dt.datetime(2026, 11, 17, 0, 0, tzinfo=zone)
    end = dt.datetime(2026, 11, 18, 0, 0, tzinfo=zone)
    client = FakeECalClient()
    events = eds.read_events(
        source("cal-uid", "Calendar", {eds.SOURCE_CALENDAR}),
        start,
        end,
        zone,
        client_factory=lambda source, zone_name: client,
    )
    summaries = [event.summary for event in events]
    assert "Morning standup" in summaries
    assert "Aki's birthday" in summaries
    assert "Tomorrow planning" not in summaries
    assert summaries.count("Daily sync") == 1
    assert [event.start for event in events] == sorted(event.start for event in events)
    birthday = next(event for event in events if event.summary == "Aki's birthday")
    assert birthday.all_day is True


def test_read_tasks_filters_completed_and_sorts():
    client = FakeECalClient()
    tasks = eds.read_tasks(
        source("tasks-uid", "Tasks", {eds.SOURCE_TASK_LIST}),
        client_factory=lambda source: client,
    )
    assert [task.summary for task in tasks] == ["Pay rent", "Buy milk", "No due"]
    assert tasks[0].due == dt.date(2026, 11, 17)
    assert tasks[1].due == dt.date(2026, 11, 18)
    assert tasks[2].due is None


def test_read_contacts_extracts_uid_name_phone():
    client = FakeBookClient()
    contacts = eds.read_contacts(
        source("book-uid", "Contacts", {eds.SOURCE_ADDRESS_BOOK}),
        client_factory=lambda source: client,
        fields=FakeContactFields,
    )
    assert contacts[0] == Contact("contact-1", "Aki Tanaka", "+81 90 1234 5678")
    assert contacts[2].phone == ""


def test_task_sort_puts_no_due_last():
    tasks = [Task("b", None), Task("a", dt.date(2026, 1, 2)), Task("a", None)]
    tasks.sort(key=eds.task_sort_key)
    assert tasks[0].summary == "a"
    assert tasks[0].due == dt.date(2026, 1, 2)
    assert tasks[1:] == [Task("a", None), Task("b", None)]


def test_managed_prefix():
    assert eds.is_managed_uid("paperphone-123")
    assert not eds.is_managed_uid("gnome-123")


def test_recurrence_generation_continues_until_callback_stops():
    class StopEarlyClient(FakeECalClient):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def generate_instances_sync(self, start, end, cancellable, callback, data):
            super().generate_instances_sync(start, end, cancellable, callback, data)
            self.calls += 1

    client = FakeECalClient()
    events = eds.read_events(
        source("cal-uid", "Calendar", {eds.SOURCE_CALENDAR}),
        dt.datetime(2026, 11, 17, 0, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        dt.datetime(2026, 11, 18, 0, 0, tzinfo=ZoneInfo("Asia/Tokyo")),
        ZoneInfo("Asia/Tokyo"),
        client_factory=lambda source, zone_name: client,
    )
    assert {event.summary for event in events} == {
        "Morning standup",
        "Aki's birthday",
        "Daily sync",
    }
