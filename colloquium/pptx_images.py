"""Optional image preparation for Google Slides PPTX import."""

from __future__ import annotations

import io
import math
from pathlib import Path


# In a Google Slides PPTX import/round-trip checked in October 2026, images
# above 2048 px on either axis were resampled. Tiles of at most 1600 px were
# preserved byte-for-byte, including when grouped. Leave the normal export
# untouched: tiling trades a single editable picture for a group of pictures.
_IMPORT_IMAGE_LIMIT = 2048
_TILE_SIZE = 1600
# Stay just below the observed import ceiling rather than relying on its exact
# boundary. This is a pixel limit, independent of the image's DPI metadata.
_RESIZE_MAX_EDGE = 2000


def google_slides_mode(raw: dict, override: bool | str | None = None) -> str | None:
    value = raw.get("google_slides", False) if override is None else override
    if value is True:
        return "tile"
    if value is False:
        return None
    if isinstance(value, str) and value in {"tile", "resize"}:
        return value
    raise ValueError("pptx.google_slides must be true, false, 'tile', or 'resize'")


def add_picture(shapes, source, left, top, width, height, *, google_slides=False):
    """Place a picture, optionally resizing or tiling it for Google Slides.

    Tile edges use the same pixel-to-EMU mapping so their rectangles exactly
    cover the original bounds. No pixels are enlarged, resampled, or discarded.
    Resize mode uses Lanczos, retains alpha, and never enlarges an image.
    Both modes leave source files and the picture's slide bounds unchanged.
    """
    from PIL import Image

    if isinstance(source, Path):
        source = str(source)
    mode = google_slides_mode({}, google_slides)
    if mode is None:
        return shapes.add_picture(source, left, top, width, height)

    with Image.open(source) as image:
        limit = _RESIZE_MAX_EDGE if mode == "resize" else _IMPORT_IMAGE_LIMIT
        if max(image.size) <= limit:
            return shapes.add_picture(source, left, top, width, height)

        # PNG supports RGB, RGBA, palette and grayscale. Decode other color
        # modes as RGB, as required when converting e.g. a CMYK JPEG to PNG.
        if image.mode not in {"1", "L", "LA", "P", "RGB", "RGBA", "I", "I;16"}:
            image = image.convert("RGB")
        if mode == "resize":
            # Pillow forces nearest-neighbor for palette and bilevel images;
            # decode those first so charts also receive Lanczos filtering.
            if image.mode in {"1", "P"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            image.thumbnail((limit, limit), Image.Resampling.LANCZOS, reducing_gap=None)
            resized = io.BytesIO()
            image.save(resized, format="PNG")
            resized.seek(0)
            return shapes.add_picture(resized, left, top, width, height)

        pixel_w, pixel_h = image.size
        columns, rows = math.ceil(pixel_w / _TILE_SIZE), math.ceil(pixel_h / _TILE_SIZE)
        # Balance the tiles instead of leaving a very narrow final strip.
        xs = [round(i * pixel_w / columns) for i in range(columns + 1)]
        ys = [round(i * pixel_h / rows) for i in range(rows + 1)]
        group = shapes.add_group_shape()
        group.name = "Figure (original-resolution image tiles)"
        for y0, y1 in zip(ys, ys[1:]):
            for x0, x1 in zip(xs, xs[1:]):
                tile = io.BytesIO()
                image.crop((x0, y0, x1, y1)).save(tile, format="PNG")
                tile.seek(0)
                x = left + round(width * x0 / pixel_w)
                y = top + round(height * y0 / pixel_h)
                right = left + round(width * x1 / pixel_w)
                bottom = top + round(height * y1 / pixel_h)
                picture = group.shapes.add_picture(tile, x, y, right - x, bottom - y)
                picture.name = f"Figure pixels {x0},{y0}–{x1},{y1}"
        return group
