"""Image placement that can retain original pixels through Google Slides import."""

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


def google_slides_enabled(raw: dict, override: bool | None = None) -> bool:
    value = raw.get("google_slides", False) if override is None else override
    if not isinstance(value, bool):
        raise ValueError("pptx.google_slides must be true or false")
    return value


def add_picture(shapes, source, left, top, width, height, *, google_slides=False):
    """Place a picture, optionally dividing large images into lossless PNG tiles.

    Tile edges use the same pixel-to-EMU mapping so their rectangles exactly
    cover the original bounds. No pixels are enlarged, resampled, or discarded.
    The returned picture or group can be moved and resized as one object.
    """
    from PIL import Image

    if isinstance(source, Path):
        source = str(source)
    if not google_slides:
        return shapes.add_picture(source, left, top, width, height)

    with Image.open(source) as image:
        if max(image.size) <= _IMPORT_IMAGE_LIMIT:
            return shapes.add_picture(source, left, top, width, height)

        # PNG supports RGB, RGBA, palette and grayscale. Decode other color
        # modes as RGB, as required when converting e.g. a CMYK JPEG to PNG.
        if image.mode not in {"1", "L", "LA", "P", "RGB", "RGBA", "I", "I;16"}:
            image = image.convert("RGB")
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
