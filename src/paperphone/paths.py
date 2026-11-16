from __future__ import annotations

from pathlib import Path

from .errors import ConfigError


def config_path() -> Path:
    import os

    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "paperphone" / "config.toml"
    return Path.home() / ".config" / "paperphone" / "config.toml"


def cache_dir() -> Path:
    import os

    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base) / "paperphone"
    return Path.home() / ".cache" / "paperphone"


def data_dir() -> Path:
    import os

    base = os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base) / "paperphone"
    return Path.home() / ".local" / "share" / "paperphone"


def dav_path() -> Path:
    return config_path().with_name("dav.toml")


def display_path(path: Path) -> str:
    try:
        return str(path.expanduser().resolve())
    except OSError:
        return str(path)


def missing_config_message(path: Path) -> str:
    return (
        f"設定ファイルがありません: {display_path(path)}\n"
        "次の内容で作成してください:\n\n"
        "[booklet]\n"
        'name = "Aki"\n'
        'timezone = "Asia/Tokyo"\n\n'
        "[panels]\n"
        "contacts = true\n"
        "calendar = true\n"
        "tasks = true\n"
    )


def require_file(path: Path) -> None:
    if not path.exists():
        raise ConfigError(missing_config_message(path))
    if not path.is_file():
        raise ConfigError(f"設定ファイルではありません: {display_path(path)}")
