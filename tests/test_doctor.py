from __future__ import annotations

import io

from paperphone import doctor
from paperphone.doctor import Check


def _ok_checks():
    return [
        Check("Python", True),
        Check("設定", True),
        Check("出力先", True),
        Check("ネットワーク", False, required=False, detail="offline"),
    ]


def test_run_doctor_returns_zero(monkeypatch):
    monkeypatch.setattr(doctor, "collect_checks", lambda **kwargs: _ok_checks())
    stream = io.StringIO()
    assert doctor.run_doctor(stream=stream) == 0
    output = stream.getvalue()
    assert "[ok] Python" in output
    assert "[警告] ネットワーク" in output


def test_required_failure_returns_one(monkeypatch):
    checks = _ok_checks()
    checks[1] = Check("設定", False, hint="設定ファイルを用意してください")
    monkeypatch.setattr(doctor, "collect_checks", lambda **kwargs: checks)
    stream = io.StringIO()
    assert doctor.run_doctor(stream=stream) == 1
    assert "設定ファイルを用意してください" in stream.getvalue()


def test_python_check():
    assert doctor.check_python().ok


def test_output_check_on_writable(tmp_path):
    assert doctor.check_output(tmp_path / "book.pdf").ok


def test_output_check_on_unwritable():
    check = doctor.check_output(__import__("pathlib").Path("/proc/x.pdf"))
    assert not check.ok
