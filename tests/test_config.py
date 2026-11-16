from __future__ import annotations

import pytest

from paperphone.config import load_config, parse_config
from paperphone.errors import ConfigError
from paperphone.paths import config_path


def write(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_minimal_config(tmp_path):
    path = write(
        tmp_path,
        """
[booklet]
name = "Aki"
""",
    )
    config = load_config(path)
    assert config.name == "Aki"
    assert config.panels.enabled() == ()
    assert config.paper_app == "pigeon_origami"


def test_empty_panels_are_all_disabled(tmp_path):
    path = write(
        tmp_path,
        """
[booklet]
name = "Aki"
[panels]
""",
    )
    assert load_config(path).panels.enabled() == ()


def test_name_is_required(tmp_path):
    path = write(tmp_path, "[booklet]\nname = '  '\n")
    with pytest.raises(ConfigError):
        load_config(path)


def test_unknown_panel_is_rejected(tmp_path):
    path = write(
        tmp_path,
        """
[booklet]
name = "Aki"
[panels]
mail = true
""",
    )
    with pytest.raises(ConfigError, match="mail"):
        load_config(path)


def test_unknown_paper_app_is_rejected(tmp_path):
    path = write(
        tmp_path,
        """
[booklet]
name = "Aki"
[paper_app]
name = "nope"
""",
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_paper_app_default_is_pigeon(tmp_path):
    path = write(tmp_path, '[booklet]\nname = "Aki"\n[paper_app]\n')
    assert load_config(path).paper_app == "pigeon_origami"


def test_latitude_out_of_range(tmp_path):
    path = write(
        tmp_path,
        """
[booklet]
name = "Aki"
[panels]
weather = true
[weather]
latitude = 100
longitude = 139
""",
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_weather_requires_latitude(tmp_path):
    path = write(
        tmp_path,
        """
[booklet]
name = "Aki"
[panels]
weather = true
[weather]
longitude = 139
""",
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_too_many_contacts(tmp_path):
    uids = ", ".join(f'"c{i}"' for i in range(8))
    path = write(
        tmp_path,
        f"""
[booklet]
name = "Aki"
[sources]
contacts = [{uids}]
""",
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_maps_requires_destination(tmp_path):
    path = write(
        tmp_path,
        """
[booklet]
name = "Aki"
[panels]
map = true
[maps]
[maps.from]
latitude = 35.0
longitude = 139.0
""",
    )
    with pytest.raises(ConfigError, match="to"):
        load_config(path)


def test_no_map_skips_map_validation(tmp_path):
    path = write(
        tmp_path,
        """
[booklet]
name = "Aki"
[panels]
map = true
""",
    )
    config = load_config(path, no_map=True)
    assert config.panels.map is False
    assert config.maps is None


def test_invalid_timezone(tmp_path):
    path = write(tmp_path, '[booklet]\nname = "Aki"\ntimezone = "Mars/Olympus"\n')
    with pytest.raises(ConfigError):
        load_config(path)


def test_missing_file_reports_path(tmp_path):
    missing = tmp_path / "nope.toml"
    with pytest.raises(ConfigError) as error:
        load_config(missing)
    assert str(missing) in str(error.value)
    assert "[booklet]" in str(error.value)


def test_invalid_toml(tmp_path):
    path = write(tmp_path, "[booklet\n")
    with pytest.raises(ConfigError):
        load_config(path)


def test_config_path_uses_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_path() == tmp_path / "paperphone" / "config.toml"


def test_panels_must_be_boolean(tmp_path):
    path = write(
        tmp_path,
        """
[booklet]
name = "Aki"
[panels]
contacts = "yes"
""",
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_parse_config_rejects_non_table():
    with pytest.raises(ConfigError):
        parse_config({"booklet": "Aki"}, config_path())
