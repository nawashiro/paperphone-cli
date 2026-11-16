from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader

from paperphone.cli import main


def config_without_sources(tmp_path, extra: str = "") -> Path:
    path = tmp_path / "config.toml"
    path.write_text(
        f"""
[booklet]
name = "Aki"
timezone = "Asia/Tokyo"

[panels]
notes = true
paper_app = true
{extra}
""",
        encoding="utf-8",
    )
    return path


def test_version(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--version"])
    assert error.value.code == 0
    assert "paperphone 0.1.0" in capsys.readouterr().out


def test_help_mentions_folding(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    out = capsys.readouterr().out
    assert "両面印刷" in out
    assert "OpenStreetMap" in out


def test_invalid_date_exits_2(tmp_path):
    config = config_without_sources(tmp_path)
    with pytest.raises(SystemExit) as error:
        main(["--config", str(config), "--date", "2026-02-30"])
    assert error.value.code == 2


def test_missing_config_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "empty"))
    assert main([]) == 2
    error = capsys.readouterr().err
    assert "config.toml" in error
    assert "[booklet]" in error


def test_generate_writes_pdf(tmp_path, capsys):
    config = config_without_sources(tmp_path)
    out = tmp_path / "book.pdf"
    code = main(
        [
            "--config",
            str(config),
            "--date",
            "2026-11-17",
            "--tz",
            "Asia/Tokyo",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    printed = capsys.readouterr().out.strip()
    assert printed == str(out.resolve())
    assert out.exists()
    assert len(PdfReader(str(out)).pages) == 1


def test_invalid_timezone_exits_2(tmp_path, capsys):
    config = config_without_sources(tmp_path)
    out = tmp_path / "book.pdf"
    code = main(
        ["--config", str(config), "--tz", "Mars/Olympus", "--out", str(out)]
    )
    assert code == 2
    assert not out.exists()


def test_no_map_makes_one_page(tmp_path):
    config = config_without_sources(tmp_path, "map = true")
    out = tmp_path / "book.pdf"
    assert main(["--config", str(config), "--no-map", "--out", str(out)]) == 0
    assert len(PdfReader(str(out)).pages) == 1


def test_map_without_config_exits_2(tmp_path):
    config = config_without_sources(tmp_path, "map = true")
    out = tmp_path / "book.pdf"
    assert main(["--config", str(config), "--out", str(out)]) == 2
    assert not out.exists()


def test_unknown_paper_app_exits_2(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[booklet]
name = "Aki"
[paper_app]
name = "nope"
""",
        encoding="utf-8",
    )
    assert main(["--config", str(config), "--out", str(tmp_path / "x.pdf")]) == 2


def test_runtime_failure_exits_1(tmp_path, monkeypatch, capsys):
    from paperphone.errors import RuntimeFailure

    config = config_without_sources(tmp_path)

    def fail(*args, **kwargs):
        raise RuntimeFailure("書き出せません")

    monkeypatch.setattr("paperphone.rendering.write_pdf_atomic", fail)
    assert main(["--config", str(config), "--out", str(tmp_path / "x.pdf")]) == 1
    assert "書き出せません" in capsys.readouterr().err


def test_module_entrypoint_runs(tmp_path):
    config = config_without_sources(tmp_path)
    out = tmp_path / "entry.pdf"
    result = subprocess.run(
        [sys.executable, "-m", "paperphone", "--config", str(config), "--out", str(out)],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(Path(__file__).parent.parent / "src")},
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()


def test_default_output_name_uses_date(tmp_path, monkeypatch):
    config = config_without_sources(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert (
        main(
            [
                "--config",
                str(config),
                "--date",
                "2026-11-17",
                "--tz",
                "Asia/Tokyo",
            ]
        )
        == 0
    )
    assert (tmp_path / "paperphone-2026-11-17.pdf").exists()


def test_missing_tz_uses_config_zone(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        """
[booklet]
name = "Aki"
timezone = "Asia/Tokyo"
[panels]
notes = true
""",
        encoding="utf-8",
    )
    out = tmp_path / "book.pdf"
    assert main(["--config", str(config), "--date", "2026-11-17", "--out", str(out)]) == 0
    assert out.exists()
