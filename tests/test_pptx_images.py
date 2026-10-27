"""Regression coverage for the Google Slides import image-size workaround."""

import io

import pytest

pytest.importorskip("pptx")
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from colloquium.export import export_pptx
from colloquium.pptx_images import add_picture, google_slides_mode


@pytest.mark.parametrize("size", [(3201, 1681), (900, 3001), (2464, 968)])
def test_tiles_reconstruct_original_pixels_and_cover_exact_bounds(tmp_path, size):
    # A nonuniform RGBA image detects missing/repeated rows and lost alpha.
    source = Image.new("RGBA", size)
    row = bytes(v for x in range(size[0]) for v in (x % 256, (x // 256) % 256, 70, x % 255))
    source.frombytes(row * size[1])
    path = tmp_path / "source.png"
    source.save(path)
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bounds = (123457, 234569, Inches(8.3), Inches(4.2))
    add_picture(slide.shapes, path, *bounds, google_slides=True)
    out = tmp_path / "test.pptx"
    prs.save(out)
    group = Presentation(out).slides[0].shapes[0]
    assert group.shape_type == 6
    assert (group.left, group.top, group.width, group.height) == bounds
    reconstructed = Image.new("RGBA", size)
    rectangles = []
    for tile in group.shapes:
        pixels = Image.open(io.BytesIO(tile.image.blob)).convert("RGBA")
        assert max(pixels.size) <= 1600
        x0 = round((tile.left - group.left) * size[0] / group.width)
        y0 = round((tile.top - group.top) * size[1] / group.height)
        x1, y1 = x0 + pixels.width, y0 + pixels.height
        assert tile.left == group.left + round(group.width * x0 / size[0])
        assert tile.top == group.top + round(group.height * y0 / size[1])
        assert tile.left + tile.width == group.left + round(group.width * x1 / size[0])
        assert tile.top + tile.height == group.top + round(group.height * y1 / size[1])
        rectangles.append((x0, y0, x1, y1))
        reconstructed.paste(pixels, (x0, y0))
    assert sum((x1-x0)*(y1-y0) for x0,y0,x1,y1 in rectangles) == size[0]*size[1]
    assert reconstructed.tobytes() == source.tobytes()


@pytest.mark.parametrize("mode,size", [(False, (3200, 1680)), (True, (2048, 900)), ("resize", (2000, 900)), ("resize", (400, 600))])
def test_disabled_mode_and_small_images_preserve_original_file(tmp_path, mode, size):
    path = tmp_path / "original.jpg"
    Image.new("RGB", size, "#123456").save(path)
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    picture = add_picture(slide.shapes, path, 0, 0, Inches(8), Inches(4), google_slides=mode)
    assert picture.shape_type == 13
    assert picture.image.blob == path.read_bytes()


def test_google_slides_frontmatter_and_python_override(tmp_path):
    Image.new("RGB", (2400, 1000), "white").save(tmp_path / "image.png")
    md = tmp_path / "talk.md"
    md.write_text('---\ntitle: Test\npptx:\n  google_slides: true\n---\n\n## Image\n\n![Image](image.png)\n')
    prs = Presentation(export_pptx(str(md)))
    assert any(s.shape_type == 6 for s in prs.slides[0].shapes)
    prs = Presentation(export_pptx(str(md), google_slides=False))
    assert any(s.shape_type == 13 for s in prs.slides[0].shapes)
    assert not any(s.shape_type == 6 for s in prs.slides[0].shapes)


def test_google_slides_config_rejects_quoted_boolean():
    with pytest.raises(ValueError, match="must be"):
        google_slides_mode({"google_slides": "false"})


@pytest.mark.parametrize("size,expected", [((3200, 1680), (2000, 1050)), ((900, 3000), (600, 2000))])
def test_resize_retains_alpha_bounds_and_source_file(tmp_path, size, expected):
    image = Image.new("RGBA", size, (20, 40, 60, 128))
    path = tmp_path / "source.png"
    image.save(path)
    original = path.read_bytes()
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bounds = (123457, 234569, Inches(8.3), Inches(4.2))
    add_picture(slide.shapes, path, *bounds, google_slides="resize")
    output = tmp_path / "resized.pptx"
    prs.save(output)
    picture = Presentation(output).slides[0].shapes[0]
    assert picture.shape_type == 13  # remains a single editable picture
    assert (picture.left, picture.top, picture.width, picture.height) == bounds
    pixels = Image.open(io.BytesIO(picture.image.blob))
    assert pixels.format == "PNG"
    assert pixels.size == expected
    assert pixels.mode == "RGBA"
    assert pixels.getextrema()[3] == (128, 128)
    assert path.read_bytes() == original


def test_resize_palette_chart_filters_edges_and_keeps_transparency():
    # Palette PNGs otherwise silently use nearest-neighbor in Pillow, even if
    # Lanczos is requested. Fine stripes expose that failure on real charts.
    image = Image.new("P", (3200, 40))
    image.putpalette([255, 255, 255, 0, 0, 0] + [0] * 762)
    image.frombytes(bytes(x % 2 for x in range(3200)) * 40)
    source = io.BytesIO()
    image.save(source, format="PNG", transparency=0)
    source.seek(0)
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    picture = add_picture(slide.shapes, source, 0, 0, Inches(8), Inches(1), google_slides="resize")
    pixels = Image.open(io.BytesIO(picture.image.blob))
    assert pixels.mode == "RGBA"
    assert pixels.size == (2000, 25)
    alpha = pixels.getchannel("A")
    assert sum(alpha.histogram()[1:-1]) > 0


def test_resize_cli_and_frontmatter_with_override(tmp_path, monkeypatch):
    from colloquium.cli import main

    Image.new("RGB", (3200, 1680), "white").save(tmp_path / "image.png")
    md = tmp_path / "talk.md"
    md.write_text('---\ntitle: Test\npptx:\n  google_slides: resize\n---\n\n## Image\n\n![Image](image.png)\n')
    prs = Presentation(export_pptx(str(md)))
    picture = next(s for s in prs.slides[0].shapes if s.shape_type == 13)
    assert picture.image.size == (2000, 1050)
    prs = Presentation(export_pptx(str(md), google_slides="tile"))
    assert any(s.shape_type == 6 for s in prs.slides[0].shapes)
    output = tmp_path / "cli.pptx"
    monkeypatch.setattr("sys.argv", ["colloquium", "export", str(md), "--google-slides", "resize", "-o", str(output)])
    main()
    picture = next(s for s in Presentation(output).slides[0].shapes if s.shape_type == 13)
    assert picture.image.size == (2000, 1050)
