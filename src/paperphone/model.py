from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class Contact:
    uid: str
    name: str
    phone: str = ""


@dataclass(frozen=True)
class Event:
    summary: str
    start: dt.datetime
    end: dt.datetime
    all_day: bool = False


@dataclass(frozen=True)
class Task:
    summary: str
    due: dt.date | None = None


def task_sort_key(task: Task) -> tuple[int, str]:
    if task.due is None:
        return (1, task.summary.casefold())
    return (0, task.due.isoformat() + "\0" + task.summary.casefold())


@dataclass(frozen=True)
class SourceInfo:
    uid: str
    name: str
    kind: str
    origin: str
    credentials: str

    @property
    def managed(self) -> bool:
        return self.origin == "paperphone"

    @property
    def usable_credentials(self) -> bool:
        return self.credentials in ("keyring", "gnome")

