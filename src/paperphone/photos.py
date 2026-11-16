from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


class PhotoError(Exception):
    pass


def prepare_photo(path: str | None, *, width_px: int = 490) -> Image.Image | None:
    if not path:
        raise PhotoError("写真が設定されていません")
    target = Path(path).expanduser()
    try:
        with Image.open(target) as image:
            photo = ImageOps.exif_transpose(image)
            photo = photo.convert("L")
            if photo.width > photo.height:
                photo = photo.transpose(Image.Transpose.ROTATE_90)
            ratio = width_px / photo.width
            height = max(1, int(round(photo.height * ratio)))
            return photo.resize((width_px, height), Image.Resampling.LANCZOS)
    except (OSError, ValueError) as exc:
        raise PhotoError(f"写真を読めません: {target}: {exc}") from exc
