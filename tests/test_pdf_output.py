from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from paperphone.errors import RuntimeFailure
from paperphone.rendering import write_pdf_atomic


def blank_pdf(path: Path, pages: int = 1) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=842, height=595)
    with open(path, "wb") as handle:
        writer.write(handle)


def test_replaces_existing_file(tmp_path, monkeypatch):
    destination = tmp_path / "book.pdf"
    destination.write_bytes(b"old contents")
    monkeypatch.setattr(
        "paperphone.rendering.render_html_to_pdf",
        lambda html, target: blank_pdf(target),
    )
    write_pdf_atomic(destination, "<html></html>", rotate_map=False, expected_pages=1)
    assert len(PdfReader(str(destination)).pages) == 1
    assert not list(tmp_path.glob(".paperphone-*"))


def test_creates_parent_directories(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "paperphone.rendering.render_html_to_pdf",
        lambda html, target: blank_pdf(target),
    )
    destination = tmp_path / "2026" / "11" / "book.pdf"
    write_pdf_atomic(destination, "<html></html>", rotate_map=False, expected_pages=1)
    assert destination.exists()


def test_failure_keeps_existing_file_and_cleans_up(tmp_path, monkeypatch):
    destination = tmp_path / "book.pdf"
    destination.write_bytes(b"keep me")

    def fail(html, target):
        Path(target).write_bytes(b"partial")
        raise RuntimeError("boom")

    monkeypatch.setattr("paperphone.rendering.render_html_to_pdf", fail)
    with pytest.raises(RuntimeFailure):
        write_pdf_atomic(destination, "<html></html>", rotate_map=False, expected_pages=1)
    assert destination.read_bytes() == b"keep me"
    assert not list(tmp_path.glob(".paperphone-*"))


def test_wrong_page_count_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "paperphone.rendering.render_html_to_pdf",
        lambda html, target: blank_pdf(target, pages=1),
    )
    destination = tmp_path / "book.pdf"
    with pytest.raises(RuntimeFailure, match="ページ数"):
        write_pdf_atomic(destination, "<html></html>", rotate_map=True, expected_pages=2)
    assert not destination.exists()
    assert not list(tmp_path.glob(".paperphone-*"))


def test_rotation_failure_keeps_existing_file(tmp_path, monkeypatch):
    destination = tmp_path / "book.pdf"
    destination.write_bytes(b"keep me")
    monkeypatch.setattr(
        "paperphone.rendering.render_html_to_pdf",
        lambda html, target: blank_pdf(target, pages=2),
    )

    def fail(source, target):
        raise RuntimeError("rotate failed")

    monkeypatch.setattr("paperphone.rendering.rotate_second_page", fail)
    with pytest.raises(RuntimeFailure):
        write_pdf_atomic(destination, "<html></html>", rotate_map=True, expected_pages=2)
    assert destination.read_bytes() == b"keep me"
    assert not list(tmp_path.glob(".paperphone-*"))


def test_unwritable_destination(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "paperphone.rendering.render_html_to_pdf",
        lambda html, target: blank_pdf(target),
    )
    with pytest.raises(RuntimeFailure):
        write_pdf_atomic(
            Path("/proc/paperphone/book.pdf"), "<html></html>",
            rotate_map=False, expected_pages=1,
        )
