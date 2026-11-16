from __future__ import annotations

import os
import tempfile
from pathlib import Path

from . import paperapps
from .errors import RuntimeFailure


def render_html_to_pdf(html_text: str, target: Path) -> None:
    from weasyprint import HTML

    HTML(string=html_text, base_url=str(paperapps.asset_root())).write_pdf(str(target))


def rotate_second_page(source: Path, target: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(source))
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    if len(reader.pages) > 1:
        second = reader.pages[1]
        second.rotate(180)
        writer.add_page(second)
    with open(target, "wb") as handle:
        writer.write(handle)


def page_count(path: Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(str(path)).pages)


def _temporary_pdf(directory: Path, prefix: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=".pdf", dir=directory)
    os.close(fd)
    return Path(name)


def write_pdf_atomic(
    destination: Path,
    html_text: str,
    *,
    rotate_map: bool,
    expected_pages: int,
) -> Path:
    destination = Path(destination).expanduser().resolve()
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeFailure(f"出力先を作れません: {destination.parent}: {exc}") from exc

    rendered: Path | None = None
    rotated: Path | None = None
    try:
        rendered = _temporary_pdf(destination.parent, ".paperphone-render.")
        render_html_to_pdf(html_text, rendered)
        pages = page_count(rendered)
        if pages != expected_pages:
            raise RuntimeFailure(
                f"PDF のページ数が想定と違います: {pages}（想定 {expected_pages}）"
            )
        final_source = rendered
        if rotate_map:
            rotated = _temporary_pdf(destination.parent, ".paperphone-rotate.")
            rotate_second_page(rendered, rotated)
            final_source = rotated
        os.replace(final_source, destination)
        return destination
    except RuntimeFailure:
        raise
    except OSError as exc:
        raise RuntimeFailure(f"PDF を書き出せません: {destination}: {exc}") from exc
    except Exception as exc:
        raise RuntimeFailure(f"PDF を描画できません: {exc}") from exc
    finally:
        for path in (rendered, rotated):
            if path is not None and path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
