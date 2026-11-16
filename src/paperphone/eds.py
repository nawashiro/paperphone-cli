from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from .errors import RuntimeFailure
from .model import Contact, Event, SourceInfo, Task, task_sort_key

SOURCE_CALENDAR = "Calendar"
SOURCE_TASK_LIST = "Task List"
SOURCE_ADDRESS_BOOK = "Address Book"
SOURCE_AUTHENTICATION = "Authentication"
SOURCE_WEBDAV = "WebDAV Backend"

MANAGED_PREFIX = "paperphone-"

CAL_QUERY_ALL = '(contains? "summary" "")'
BOOK_QUERY_ALL = '(exists "id")'

ECAL_EVENT = "EVENTS"
ECAL_TASKS = "TASKS"


class EdsUnavailable(RuntimeFailure):
    pass


def is_managed_uid(uid: str) -> bool:
    return uid.startswith(MANAGED_PREFIX)


def load_gi() -> SimpleNamespace:
    try:
        import gi

        gi.require_version("EDataServer", "1.2")
        gi.require_version("ECal", "2.0")
        gi.require_version("EBook", "1.2")
        gi.require_version("EBookContacts", "1.2")
        gi.require_version("ICalGLib", "3.0")
        from gi.repository import EBook, EBookContacts, ECal, EDataServer, ICalGLib

        return SimpleNamespace(
            ECal=ECal,
            EBook=EBook,
            EBookContacts=EBookContacts,
            EDataServer=EDataServer,
            ICalGLib=ICalGLib,
        )
    except (ImportError, ValueError) as exc:
        raise EdsUnavailable(
            "Evolution Data Server の GI バインディングがありません。"
            "python3-gi と evolution-data-server を入れてください"
        ) from exc


def open_registry():
    modules = load_gi()
    try:
        return modules.EDataServer.SourceRegistry.new_sync(None)
    except Exception as exc:
        raise EdsUnavailable(
            "Evolution Data Server の source registry に接続できません。"
            "GNOME のセッションで実行しているか確認してください"
        ) from exc


def kind_of(source) -> str | None:
    if source.has_extension(SOURCE_TASK_LIST):
        return "tasks"
    if source.has_extension(SOURCE_CALENDAR):
        return "calendar"
    if source.has_extension(SOURCE_ADDRESS_BOOK):
        return "contacts"
    return None


class CredentialStore:
    def __init__(self, registry, provider=None):
        self._registry = registry
        modules = load_gi()
        self._modules = modules
        self._provider = provider or modules.EDataServer.SourceCredentialsProvider.new(registry)

    @property
    def provider(self):
        return self._provider

    def lookup_password(self, source) -> str | None:
        try:
            result = self._provider.lookup_sync(source, None)
        except Exception:
            return None
        params = result[1] if isinstance(result, tuple) and len(result) == 2 else result
        if params is None:
            return None
        try:
            return params.get("password")
        except Exception:
            return None

    def has_password(self, source) -> bool:
        return bool(self.lookup_password(source))

    def store_password(self, source, user: str, password: str) -> None:
        modules = self._modules
        params = modules.EDataServer.NamedParameters.new()
        params.set("username", user)
        params.set("password", password)
        try:
            self._provider.store_sync(source, params, True, None)
        except Exception as exc:
            raise RuntimeFailure(
                f"キーリングにパスワードを保存できません: {exc}"
            ) from exc

    def delete_password(self, source) -> None:
        try:
            self._provider.delete_sync(source, None)
        except Exception:
            return


def source_display_name(source) -> str:
    name = source.get_display_name()
    if name:
        return str(name)
    return str(source.get_uid())


def describe_source(source, credentials: CredentialStore | None) -> SourceInfo:
    uid = str(source.get_uid())
    kind = kind_of(source) or "calendar"
    managed = is_managed_uid(uid)
    if credentials is None:
        credential_state = "none"
    elif managed:
        credential_state = "keyring" if credentials.has_password(source) else "none"
    else:
        credential_state = "gnome"
    return SourceInfo(
        uid=uid,
        name=source_display_name(source),
        kind=kind,
        origin="paperphone" if managed else "gnome",
        credentials=credential_state,
    )


def list_sources(registry, credentials: CredentialStore | None = None) -> list[SourceInfo]:
    infos: list[SourceInfo] = []
    for source in registry.list_sources(None) or []:
        if kind_of(source) is None:
            continue
        infos.append(describe_source(source, credentials))
    infos.sort(key=lambda info: (info.kind, info.origin, info.name.casefold(), info.uid))
    return infos


def find_source(registry, uid: str):
    try:
        return registry.ref_source(uid)
    except Exception:
        return None


def _out_list(result) -> list:
    if isinstance(result, tuple):
        if len(result) >= 2 and isinstance(result[0], bool):
            return list(result[1] or [])
        return list(result)
    return list(result or [])


def _icaltime_datetime(icaltime, zone) -> dt.datetime | None:
    if icaltime is None:
        return None
    if isinstance(icaltime, (int, float)):
        return dt.datetime.fromtimestamp(icaltime, zone)
    if isinstance(icaltime, dt.datetime):
        return icaltime.astimezone(zone)
    is_date = _is_date(icaltime)
    try:
        year = int(icaltime.get_year())
        month = int(icaltime.get_month())
        day = int(icaltime.get_day())
    except Exception:
        return None
    if is_date:
        return dt.datetime(year, month, day, tzinfo=zone)
    try:
        hour = int(icaltime.get_hour())
        minute = int(icaltime.get_minute())
        second = int(icaltime.get_second())
    except Exception:
        hour = minute = second = 0
    source_zone = dt.UTC
    try:
        if not icaltime.is_utc():
            source_zone = _zone_from_tzid(icaltime.get_tzid(), zone)
    except Exception:
        source_zone = zone
    moment = dt.datetime(year, month, day, hour, minute, second, tzinfo=source_zone)
    return moment.astimezone(zone)


def _zone_from_tzid(tzid, fallback):
    if not tzid:
        return fallback
    text = str(tzid)
    candidates = [text]
    if "/Tzfile/" in text:
        candidates.append(text.rsplit("/Tzfile/", 1)[-1])
    parts = text.split("/")
    if len(parts) >= 2:
        candidates.append("/".join(parts[-2:]))
    for candidate in candidates:
        try:
            return ZoneInfo(candidate)
        except Exception:
            continue
    return fallback


def _icaltime_date(icaltime) -> dt.date | None:
    if icaltime is None:
        return None
    try:
        return dt.date(
            int(icaltime.get_year()),
            int(icaltime.get_month()),
            int(icaltime.get_day()),
        )
    except Exception:
        return None


def _unwrap_icaltime(value):
    if value is None:
        return None
    if hasattr(value, "is_date"):
        return value
    if hasattr(value, "get_value"):
        return value.get_value()
    return getattr(value, "value", value)


def _component_datetime(component):
    return _unwrap_icaltime(component.get_dtstart())


def _component_end(component):
    for getter in ("get_dtend", "get_due"):
        try:
            value = getattr(component, getter)()
        except Exception:
            continue
        if value is not None:
            return _unwrap_icaltime(value)
    return None


def _component_summary(component) -> str:
    try:
        summary = component.get_summary()
    except Exception:
        return ""
    if summary is None:
        return ""
    if hasattr(summary, "get_value"):
        summary = summary.get_value()
    else:
        summary = getattr(summary, "value", summary)
    return str(summary) if summary is not None else ""


def _is_date(icaltime) -> bool:
    try:
        return bool(icaltime.is_date())
    except Exception:
        return False


def event_client(source, zone_name: str | None = None):
    modules = load_gi()
    client = modules.ECal.Client.connect_sync(
        source, modules.ECal.ClientSourceType.EVENTS, 10, None
    )
    if zone_name:
        try:
            timezone = modules.ICalGLib.Timezone.get_builtin_timezone(zone_name)
            if timezone is not None:
                client.set_default_timezone(timezone)
        except Exception:
            pass
    return client


def task_client(source):
    modules = load_gi()
    return modules.ECal.Client.connect_sync(
        source, modules.ECal.ClientSourceType.TASKS, 10, None
    )


def book_client(source):
    modules = load_gi()
    return modules.EBook.BookClient.connect_sync(source, 10, None)


def read_events(
    source,
    start: dt.datetime,
    end: dt.datetime,
    zone,
    *,
    client_factory: Callable[[object, str], object] | None = None,
) -> list[Event]:
    factory = client_factory or event_client
    client = factory(source, zone.key)
    events: list[Event] = []

    def collect(component, instance_start, instance_end, *rest) -> bool:
        summary = _component_summary(component)
        dtstart = _component_datetime(component)
        all_day = _is_date(dtstart)
        start = _icaltime_datetime(instance_start, zone)
        end = _icaltime_datetime(instance_end, zone)
        if start is None:
            return True
        if end is None or end <= start:
            end = start + dt.timedelta(hours=1)
        events.append(Event(summary=summary, start=start, end=end, all_day=all_day))
        return True

    client.generate_instances_sync(
        int(start.timestamp()), int(end.timestamp()), None, collect, None
    )
    events.sort(key=lambda event: (event.start, event.summary.casefold()))
    return events


def read_tasks(
    source,
    *,
    client_factory: Callable[[object], object] | None = None,
    modules=None,
) -> list[Task]:
    if modules is None and client_factory is None:
        modules = load_gi()
    factory = client_factory or task_client
    client = factory(source)
    components = _out_list(client.get_object_list_as_comps_sync(CAL_QUERY_ALL, None))
    tasks: list[Task] = []
    completed_status = (
        getattr(modules.ICalGLib.PropertyStatus, "COMPLETED", None) if modules else None
    )
    for component in components:
        try:
            status = component.get_status()
        except Exception:
            status = None
        try:
            completed = component.get_completed()
        except Exception:
            completed = None
        if completed is not None:
            continue
        if completed_status is not None and status == completed_status:
            continue
        if _status_is_completed(status):
            continue
        summary = _component_summary(component)
        if not summary:
            continue
        due_time = _component_end(component)
        tasks.append(Task(summary=summary, due=_icaltime_date(due_time)))
    tasks.sort(key=task_sort_key)
    return tasks


def read_contacts(
    source,
    *,
    client_factory: Callable[[object], object] | None = None,
    fields=None,
) -> list[Contact]:
    factory = client_factory or book_client
    client = factory(source)
    contacts = _out_list(client.get_contacts_sync(BOOK_QUERY_ALL, None))
    result: list[Contact] = []
    for contact in contacts:
        uid, name, phone = _vcard_fields(contact)
        result.append(Contact(uid=uid, name=name or uid, phone=phone))
    result.sort(key=lambda contact: (contact.name.casefold(), contact.uid))
    return result


def _vcard_fields(contact) -> tuple[str, str, str]:
    text = None
    for version in (1, 0):
        try:
            text = contact.to_string(version)
            break
        except Exception:
            continue
    if text is None:
        return "", "", ""
    lines: list[str] = []
    for raw in str(text).replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        elif raw.strip():
            lines.append(raw)
    uid = name = phone = ""
    phones: list[str] = []
    for line in lines:
        upper = line.upper()
        if upper.startswith("UID"):
            uid = line.split(":", 1)[-1].strip()
        elif upper.startswith("FN"):
            name = line.split(":", 1)[-1].strip()
        elif upper.startswith("TEL"):
            phones.append(line.split(":", 1)[-1].strip())
    if phones:
        phone = phones[0]
    return uid, name, phone


def _status_is_completed(status) -> bool:
    if status is None:
        return False
    name = getattr(status, "value_nick", None) or str(status)
    return "COMPLETED" in name.upper()


def new_dav_source(uid: str, name: str, kind: str):
    modules = load_gi()
    source = modules.EDataServer.Source.new_with_uid(uid, None)
    source.set_display_name(name)
    if kind == "tasks":
        extension_name = SOURCE_TASK_LIST
    elif kind == "contacts":
        extension_name = SOURCE_ADDRESS_BOOK
    else:
        extension_name = SOURCE_CALENDAR
    extension = source.get_extension(extension_name)
    extension.set_backend_name("carddav" if kind == "contacts" else "caldav")
    try:
        extension.set_selected(True)
    except Exception:
        pass
    return source


def set_dav_url(source, url: str) -> None:
    from gi.repository import GLib

    webdav = source.get_extension(SOURCE_WEBDAV)
    parsed = GLib.Uri.parse(url, GLib.UriFlags.NONE)
    webdav.set_uri(parsed)


def set_authentication(source, host: str, user: str, port: int | None = None) -> None:
    auth = source.get_extension(SOURCE_AUTHENTICATION)
    auth.set_host(host)
    auth.set_user(user)
    auth.set_method("plain/password")
    try:
        auth.set_remember_password(True)
    except Exception:
        pass
    if port:
        try:
            auth.set_port(port)
        except Exception:
            pass


def commit_source(registry, source) -> None:
    try:
        registry.commit_source_sync(source, None)
    except Exception as exc:
        raise RuntimeFailure(f"source を登録できません: {exc}") from exc


def remove_source(source) -> None:
    try:
        source.remove_sync(None)
    except Exception as exc:
        raise RuntimeFailure(f"source を削除できません: {exc}") from exc


def source_uri(source) -> str | None:
    try:
        extension = source.get_extension(SOURCE_WEBDAV)
        uri = extension.dup_uri()
        return uri.to_string() if uri is not None else None
    except Exception:
        return None


def source_user(source) -> str | None:
    try:
        return source.get_extension(SOURCE_AUTHENTICATION).get_user()
    except Exception:
        return None


def verify_source(source, kind: str) -> None:
    try:
        if kind == "contacts":
            client = book_client(source)
            client.get_contacts_uids_sync(BOOK_QUERY_ALL, None)
        elif kind == "tasks":
            client = task_client(source)
            client.get_object_list_as_comps_sync(CAL_QUERY_ALL, None)
        else:
            client = event_client(source)
            client.get_object_list_as_comps_sync(CAL_QUERY_ALL, None)
    except Exception as exc:
        raise RuntimeFailure(f"登録した source を読めません: {exc}") from exc

