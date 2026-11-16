from __future__ import annotations

import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import tomlkit

from .davbackend import DavBackend
from .errors import RuntimeFailure, UsageError
from .model import SourceInfo
from .paths import dav_path, display_path

KINDS = ("caldav", "carddav", "tasks")

KIND_SELECTION = {
    "caldav": "calendars",
    "carddav": "contacts",
    "tasks": "tasks",
}


def validate_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise UsageError(f"URL が不正です: {url}") from exc
    if parts.scheme not in ("http", "https"):
        raise UsageError("URL は http:// または https:// で始めてください")
    if not parts.hostname:
        raise UsageError("URL にホスト名がありません")
    if parts.username or parts.password:
        raise UsageError("URL にユーザー名やパスワードを含めないでください")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, parts.fragment))


def _read_document(path: Path):
    if not path.exists():
        return tomlkit.document()
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except (OSError, tomlkit.exceptions.TOMLKitError) as exc:
        raise RuntimeFailure(f"設定を読めません: {display_path(path)}: {exc}") from exc


def _write_document(path: Path, document) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(tomlkit.dumps(document))
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def _selection_array(document, key: str):
    sources = document.get("sources")
    if sources is None:
        sources = tomlkit.table()
        document["sources"] = sources
    array = sources.get(key)
    if array is None:
        array = tomlkit.array()
        sources[key] = array
    return array


def select_uid(config_file: Path | None, kind: str, uid: str, *, select: bool = True) -> bool:
    if config_file is None or not config_file.exists():
        return False
    key = KIND_SELECTION[kind]
    document = _read_document(config_file)
    array = _selection_array(document, key)
    items = [str(item) for item in array]
    if select:
        if uid in items:
            return True
        array.append(uid)
    else:
        if uid not in items:
            return True
        for index in range(len(array) - 1, -1, -1):
            if str(array[index]) == uid:
                del array[index]
    _write_document(config_file, document)
    return True


def read_records(path: Path) -> list[dict[str, str]]:
    document = _read_document(path)
    raw = document.get("sources", [])
    records: list[dict[str, str]] = []
    for entry in raw:
        record = {str(key): str(value) for key, value in dict(entry).items()}
        if record.get("uid"):
            records.append(record)
    return records


def write_records(path: Path, records: list[dict[str, str]]) -> None:
    document = tomlkit.document()
    array = tomlkit.aot()
    for record in records:
        table = tomlkit.table()
        for key in ("uid", "kind", "url", "name", "user"):
            if key in record:
                table[key] = record[key]
        array.append(table)
    if records:
        document["sources"] = array
    _write_document(path, document)


def _record(uid: str, kind: str, url: str, name: str, user: str) -> dict[str, str]:
    return {"uid": uid, "kind": kind, "url": url, "name": name, "user": user}


def _record_duplicate(
    records: list[dict[str, str]], kind: str, url: str, user: str
) -> SourceInfo | None:
    for entry in records:
        if entry.get("kind") != kind or entry.get("user") != user:
            continue
        if validate_url(entry.get("url", "")) == url:
            return SourceInfo(
                uid=entry["uid"],
                name=entry.get("name", ""),
                kind=entry.get("kind", ""),
                origin="paperphone",
                credentials="keyring",
            )
    return None


def _resolve_target(backend: DavBackend, target: str) -> SourceInfo:
    managed = backend.managed_sources()
    for info in managed:
        if info.uid == target:
            return info
    for info in managed:
        if info.name.casefold() == target.casefold():
            return info
    raise UsageError(
        f"paperphone 管理の source が見つかりません: {target}\n"
        "GNOME 管理の source は GNOME の設定から削除してください"
    )


def add_source(
    backend: DavBackend,
    *,
    kind: str,
    url: str,
    name: str,
    user: str,
    password_getter,
    config_file: Path | None = None,
    no_select: bool = False,
    adopt: bool = False,
) -> str:
    if kind not in KINDS:
        raise UsageError(f"種類が不正です: {kind}（{', '.join(KINDS)}）")
    normalized = validate_url(url)
    if not name.strip():
        raise UsageError("--name を指定してください")
    if not user.strip():
        raise UsageError("--user を指定してください")

    record_path = dav_path() if config_file is None else config_file.with_name("dav.toml")
    records = read_records(record_path)
    duplicate = backend.find_duplicate(kind, normalized, user) or _record_duplicate(
        records, kind, normalized, user
    )

    if duplicate is not None:
        if not adopt:
            raise UsageError(
                f"同じ URL・種類・ユーザーの source が登録済みです: {duplicate.uid}\n"
                f"既存の source を使うなら --adopt を付けてください"
            )
        uid = duplicate.uid
        records = [entry for entry in records if entry.get("uid") != uid]
        records.append(_record(uid, kind, normalized, name, user))
        write_records(record_path, records)
    else:
        password = password_getter()
        if password is None or password == "":
            raise UsageError("パスワードが入力されませんでした")
        uid = backend.create(kind, normalized, name.strip(), user, password)
        try:
            backend.verify(uid, kind)
        except RuntimeFailure:
            backend.remove(uid)
            raise
        records.append(_record(uid, kind, normalized, name.strip(), user))
        write_records(record_path, records)

    if not no_select and kind in ("caldav", "tasks"):
        select_uid(config_file, kind, uid, select=True)
    return uid


def remove_source(
    backend: DavBackend,
    target: str,
    *,
    config_file: Path | None = None,
) -> str:
    info = _resolve_target(backend, target)
    backend.remove(info.uid)
    record_path = dav_path() if config_file is None else config_file.with_name("dav.toml")
    records = [entry for entry in read_records(record_path) if entry.get("uid") != info.uid]
    write_records(record_path, records)
    for kind in KINDS:
        select_uid(config_file, kind, info.uid, select=False)
    return info.uid

