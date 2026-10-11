"""Tests for template-aware PPTX export."""

from pathlib import Path

import pytest

pytest.importorskip("pptx", reason="python-pptx not installed")

from pptx import Presentation
from pptx.oxml.ns import qn

from colloquium.export import export_pptx


def _make_template(path: Path) -> Path:
    """A 3-slide template built from python-pptx's stock layouts:
    1 = Title Slide, 2 = Section Header, 3 = Title Only."""
    prs = Presentation()
    for layout_idx in (0, 2, 5):
        prs.slides.add_slide(prs.slide_layouts[layout_idx])
    prs.save(path)
    return path


def _write_deck(tmp_path: Path, body: str, pptx_block: str | None = None) -> Path:
    _make_template(tmp_path / "template.pptx")
    if pptx_block is None:
        pptx_block = """pptx:
  template: template.pptx
  layouts:
    title: {slide: 1, subtitle: 1}
    section-break: {slide: 2, eyebrow: 1}
    content: 3
  font: Inter
  colors: {text: "280016", accent: "FF0073", link: "D10060"}
"""
    md = tmp_path / "talk.md"
    md.write_text(f"---\ntitle: Talk\n{pptx_block}footer:\n  right: \"Me {{n}}/{{N}}\"\n---\n\n{body}")
    return md


def _texts(slide) -> list[str]:
    return [shape.text_frame.text for shape in slide.shapes if shape.has_text_frame]


def test_builds_on_template_layouts_and_drops_sample_slides(tmp_path):
    md = _write_deck(tmp_path, """# My Talk

Subtitle line

---

<!-- layout: section-break -->
<!-- eyebrow: Part 1 -->

## The Section

---

## Content

Hello **world** and [a link](https://example.com).
""")
    out = export_pptx(str(md))
    prs = Presentation(out)

    assert len(prs.slides) == 3
    names = [s.slide_layout.name for s in prs.slides]
    assert names == ["Title Slide", "Section Header", "Title Only"]
    # Layouts nothing uses are pruned.
    assert {layout.name for layout in prs.slide_masters[0].slide_layouts} == set(names)

    title, section, content = prs.slides
    assert "My Talk" in _texts(title)
    assert "Subtitle line" in _texts(title)
    assert _texts(section)[:2] == ["The Section", "Part 1"]

    body = next(s for s in content.shapes if s.has_text_frame and "Hello" in s.text_frame.text)
    runs = body.text_frame.paragraphs[0].runs
    bold = next(r for r in runs if r.text == "world")
    assert bold.font.bold
    link = next(r for r in runs if r.text == "a link")
    assert link.hyperlink.address == "https://example.com"
    assert str(link.font.color.rgb) == "D10060"
    assert all(r.font.name == "Inter" for r in runs)
    # Footer only on content slides, with {n}/{N} filled in.
    assert "Me 3/3" in _texts(content)
    assert not any("Me 1/3" in t for t in _texts(title))


def test_unused_placeholders_are_removed(tmp_path):
    md = _write_deck(tmp_path, """<!-- layout: section-break -->

## Only A Title
""")
    prs = Presentation(export_pptx(str(md)))
    slide = prs.slides[0]
    assert [ph.placeholder_format.idx for ph in slide.placeholders] == [0]


def test_lists_get_native_bullets_and_numbering(tmp_path):
    md = _write_deck(tmp_path, """## Lists

- alpha
- beta

5. fifth
6. sixth
""")
    prs = Presentation(export_pptx(str(md)))
    paras = [
        p for shape in prs.slides[0].shapes if shape.has_text_frame
        for p in shape.text_frame.paragraphs if p.text in {"alpha", "fifth", "sixth"}
    ]
    alpha, fifth, sixth = paras
    assert alpha._p.pPr.find(qn("a:buChar")) is not None
    auto = fifth._p.pPr.find(qn("a:buAutoNum"))
    assert auto.get("type") == "arabicPeriod" and auto.get("startAt") == "5"
    assert sixth._p.pPr.find(qn("a:buAutoNum")).get("startAt") == "6"


def test_stacked_h2_lines_merge_into_title(tmp_path):
    md = _write_deck(tmp_path, """## First line
## Second line

Body text
""")
    prs = Presentation(export_pptx(str(md)))
    title = prs.slides[0].placeholders[0]
    assert title.text_frame.text == "First line\vSecond line"
    assert any("Body text" in t for t in _texts(prs.slides[0]))


def test_image_with_html_legend_and_columns(tmp_path):
    from PIL import Image

    Image.new("RGB", (400, 200), "white").save(tmp_path / "plot.png")
    md = _write_deck(tmp_path, """<!-- columns: 50/50 -->
## Figure

Left text

|||

![plot](plot.png)

<div class="plot-legend">
  <span class="plot-legend-title">Region</span>
  <span class="plot-legend-item"><span class="plot-legend-line" style="--legend-color: #2258C3;"></span>USA</span>
</div>
""")
    prs = Presentation(export_pptx(str(md)))
    slide = prs.slides[0]
    pictures = [s for s in slide.shapes if s.shape_type == 13]
    assert len(pictures) == 1
    left_text = next(s for s in slide.shapes if s.has_text_frame and s.text_frame.text == "Left text")
    # Second column starts right of the first.
    assert pictures[0].left > left_text.left + left_text.width
    legend = next(s for s in slide.shapes if s.has_text_frame and "USA" in s.text_frame.text)
    swatch = next(r for r in legend.text_frame.paragraphs[0].runs if "━" in r.text)
    assert str(swatch.font.color.rgb) == "2258C3"


def test_cli_template_override_and_bad_config(tmp_path):
    md = _write_deck(tmp_path, "## Hi\n\ntext\n", pptx_block="")
    template = str(tmp_path / "template.pptx")
    with pytest.raises(ValueError, match="content"):
        export_pptx(str(md), template=template)

    md = _write_deck(tmp_path, "## Hi\n", pptx_block="pptx:\n  layouts: {content: 9}\n")
    with pytest.raises(ValueError, match="template has 3 slides"):
        export_pptx(str(md), template=template)

    md = _write_deck(tmp_path, "## Hi\n", pptx_block="pptx:\n  layouts: {content: 3}\n")
    with pytest.raises(FileNotFoundError):
        export_pptx(str(md), template=str(tmp_path / "missing.pptx"))
    out = export_pptx(str(md), template=template)
    assert len(Presentation(out).slides) == 1


def test_citations_and_references_slide(tmp_path):
    (tmp_path / "refs.bib").write_text(
        "@misc{doe2026,\n  title = {A Paper},\n  author = {Doe, Jane and Roe, Rick},\n"
        "  year = {2026},\n  url = {https://example.com/paper}\n}\n"
    )
    md = _write_deck(tmp_path, """<!-- cite: doe2026 -->
## Cited

Claim
""")
    text = md.read_text().replace("title: Talk\n", "title: Talk\nbibliography: refs.bib\n")
    md.write_text(text)
    prs = Presentation(export_pptx(str(md)))
    assert len(prs.slides) == 2
    assert any("Doe & Roe, 2026" in t for t in _texts(prs.slides[0]))
    refs = prs.slides[1]
    assert refs.placeholders[0].text_frame.text == "References"
    assert any("Doe, J., and Roe, R. “A Paper.” 2026." in t for t in _texts(refs))
