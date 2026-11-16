from __future__ import annotations

import ctypes.util
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import __version__, eds
from .config import load_config
from .dav import read_records
from .errors import ConfigError, PaperphoneError
from .paperapps import asset_root
from .paths import dav_path, display_path

CJK_FAMILIES = (
    "Noto Sans CJK JP",
    "Noto Sans JP",
    "Source Han Sans",
    "IPAGothic",
    "TakaoGothic",
)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    required: bool = True
    detail: str = ""
    hint: str = ""

    @property
    def status(self) -> str:
        if self.ok:
            return "ok"
        return "失敗" if self.required else "警告"


def check_python() -> Check:
    version = sys.version_info
    ok = version >= (3, 12)
    return Check(
        name="Python",
        ok=ok,
        detail=f"{version.major}.{version.minor}.{version.micro}",
        hint="Python 3.12 以上が必要です",
    )


def _import_gi() -> Check:
    try:
        import gi

        return Check(name="gi", ok=True, detail=getattr(gi, "__version__", ""))
    except ImportError as exc:
        return Check(
            name="gi",
            ok=False,
            detail=str(exc),
            hint="python3-gi（Debian/Ubuntu: python3-gi, Fedora: python3-gobject）",
        )


def _typelib(namespace: str, version: str) -> Check:
    try:
        import gi

        gi.require_version(namespace, version)
        __import__("gi.repository", fromlist=[namespace])
        getattr(__import__("gi.repository", fromlist=[namespace]), namespace)
        return Check(name=namespace, ok=True)
    except Exception as exc:
        return Check(
            name=namespace,
            ok=False,
            detail=str(exc),
            hint="evolution-data-server と gir1.2-eds-*（Fedora: evolution-data-server-devel）",
        )


def check_eds() -> list[Check]:
    checks = [_import_gi()]
    if not checks[0].ok:
        return checks
    checks.extend(
        _typelib(namespace, version)
        for namespace, version in (
            ("EDataServer", "1.2"),
            ("ECal", "2.0"),
            ("EBook", "1.2"),
            ("ICalGLib", "3.0"),
        )
    )
    return checks


def _session_bus():
    import gi

    gi.require_version("Gio", "2.0")
    from gi.repository import Gio

    return Gio.bus_get_sync(Gio.BusType.SESSION, None)


def check_dbus() -> Check:
    try:
        bus = _session_bus()
        if bus is None:
            raise RuntimeError("セッションバスに接続できません")
        return Check(name="D-Bus", ok=True)
    except Exception as exc:
        return Check(
            name="D-Bus",
            ok=False,
            detail=str(exc),
            hint="GNOME のセッションで実行してください（DBUS_SESSION_BUS_ADDRESS）",
        )


def _managed_sources_exist() -> bool:
    try:
        registry = eds.open_registry()
        for source in registry.list_sources(None) or []:
            if eds.kind_of(source) and eds.is_managed_uid(str(source.get_uid())):
                return True
    except Exception:
        return False
    return False


def check_keyring() -> Check:
    try:
        records = read_records(dav_path())
    except PaperphoneError:
        records = []
    required = bool(records) or _managed_sources_exist()
    try:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib

        bus = _session_bus()
        result = bus.call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "NameHasOwner",
            GLib.Variant("(s)", ("org.freedesktop.secrets",)),
            GLib.VariantType.new("(b)"),
            Gio.DBusCallFlags.NONE,
            5000,
            None,
        )
        ok = bool(result.unpack()[0])
        detail = "" if ok else "org.freedesktop.secrets がありません"
    except Exception as exc:
        ok = False
        detail = str(exc)
    return Check(
        name="キーリング",
        ok=ok,
        required=required,
        detail=detail,
        hint="gnome-keyring / libsecret を入れ、ログイン時にキーリングを解錠してください",
    )


def check_pango() -> Check:
    missing = [
        name
        for name in ("pango-1.0", "pangoft2-1.0", "harfbuzz", "fontconfig", "cairo")
        if ctypes.util.find_library(name) is None
    ]
    return Check(
        name="Pango",
        ok=not missing,
        detail="見つかりません: " + ", ".join(missing) if missing else "",
        hint="libpango-1.0-0 / libpangoft2-1.0-0 / libharfbuzz0b / libfontconfig1",
    )


def check_fonts() -> Check:
    missing = [
        name for name in ("varela_regular.otf", "worksans_regular.ttf")
        if not (asset_root() / "fonts" / name).exists()
    ]
    if missing:
        return Check(
            name="フォント",
            ok=False,
            detail="同梱フォントがありません: " + ", ".join(missing),
            hint="インストールをやり直してください",
        )
    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{family}", "Noto Sans CJK JP:lang=ja"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        family = result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return Check(
            name="フォント",
            ok=False,
            detail=f"fontconfig を実行できません: {exc}",
            hint="fontconfig と Noto Sans CJK JP を入れてください",
        )
    ok = any(candidate in family for candidate in CJK_FAMILIES)
    return Check(
        name="フォント",
        ok=ok,
        detail=family,
        hint="fonts-noto-cjk（Fedora: google-noto-sans-cjk-fonts）を入れてください",
    )


def check_zoneinfo() -> Check:
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo("Asia/Tokyo")
        return Check(name="zoneinfo", ok=True)
    except Exception as exc:
        return Check(
            name="zoneinfo",
            ok=False,
            detail=str(exc),
            hint="tzdata を入れてください",
        )


def check_config(path: Path | None) -> Check:
    try:
        config = load_config(path)
        return Check(
            name="設定",
            ok=True,
            detail=f"{display_path(config.path)}（{config.name}）",
        )
    except ConfigError as exc:
        return Check(
            name="設定",
            ok=False,
            detail=str(exc).splitlines()[0],
            hint="設定ファイルを用意してください",
        )


def _writable(directory: Path) -> bool:
    probe = directory
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    if not probe.is_dir():
        return False
    try:
        fd, name = tempfile.mkstemp(prefix=".paperphone-doctor.", dir=probe)
        os.close(fd)
        os.unlink(name)
        return True
    except OSError:
        return False


def check_output(out: Path | None) -> Check:
    if out is None:
        directory = Path.cwd()
    else:
        directory = out.expanduser().resolve().parent
    return Check(
        name="出力先",
        ok=_writable(directory),
        detail=display_path(directory),
        hint="書き込み権限のあるディレクトリを --out で指定してください",
    )


def check_network() -> Check:
    try:
        import httpx

        response = httpx.get(
            "https://tile.openstreetmap.org/0/0/0.png",
            timeout=5.0,
            headers={"User-Agent": f"paperphone/{__version__}"},
        )
        ok = response.status_code == 200
        detail = f"HTTP {response.status_code}"
    except Exception as exc:
        ok = False
        detail = str(exc)
    return Check(
        name="ネットワーク",
        ok=ok,
        required=False,
        detail=detail,
        hint="天気と地図は取得できませんが、予定・連絡先・タスクだけで PDF を作れます",
    )


def collect_checks(*, config_file: Path | None = None, out: Path | None = None) -> list[Check]:
    checks = [check_python()]
    checks.extend(check_eds())
    checks.append(check_dbus())
    checks.append(check_keyring())
    checks.append(check_pango())
    checks.append(check_fonts())
    checks.append(check_zoneinfo())
    checks.append(check_config(config_file))
    checks.append(check_output(out))
    checks.append(check_network())
    return checks


def run_doctor(*, config_file: Path | None = None, out: Path | None = None, stream=None) -> int:
    stream = stream or sys.stderr
    checks = collect_checks(config_file=config_file, out=out)
    for check in checks:
        line = f"[{check.status}] {check.name}"
        if check.detail:
            line += f": {check.detail}"
        print(line, file=stream)
        if not check.ok and check.hint:
            print(f"       {check.hint}", file=stream)
    failed = [check for check in checks if check.required and not check.ok]
    return 1 if failed else 0

