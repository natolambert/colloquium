"""Tests for the HTML builder."""

import tempfile
from pathlib import Path

from colloquium.build import build_deck, build_file
from colloquium.deck import Deck


class TestBuildDeck:
    def test_basic_output(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Hello", content="World")
        html = build_deck(deck)

        assert "<!DOCTYPE html>" in html
        assert "<title>Test</title>" in html
        assert "Hello" in html
        assert "World" in html

    def test_contains_katex(self):
        deck = Deck(title="Math")
        deck.add_slide(title="Equations", content="$E = mc^2$")
        html = build_deck(deck)

        assert "katex" in html
        assert "renderMathInElement" in html

    def test_contains_highlightjs(self):
        deck = Deck(title="Code")
        deck.add_slide(title="Example", content="```python\nprint('hi')\n```")
        html = build_deck(deck)

        assert "highlight" in html
        assert "hljs" in html

    def test_inlines_css_and_js(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S1", content="Content")
        html = build_deck(deck)

        assert "<style>" in html
        assert "--colloquium-bg" in html  # Theme CSS is inlined
        assert "ColloquiumPresentation" in html  # JS is inlined

    def test_slide_classes(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S1", content="C", classes=["highlight"])
        html = build_deck(deck)

        assert "highlight" in html

    def test_slide_style(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S1", content="C", style="background: red")
        html = build_deck(deck)

        assert 'style="background: red"' in html

    def test_custom_css(self):
        deck = Deck(title="Test", custom_css=".custom { color: blue; }")
        deck.add_slide(title="S1", content="C")
        html = build_deck(deck)

        assert ".custom { color: blue; }" in html

    def test_multiple_slides(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Slide 1", content="A")
        deck.add_slide(title="Slide 2", content="B")
        deck.add_slide(title="Slide 3", content="C")
        html = build_deck(deck)

        assert html.count("<section") == 3
        # First slide is active
        assert 'class="slide slide--content active"' in html

    def test_title_slide_layout(self):
        deck = Deck(title="Test")
        deck.add_title_slide(title="My Talk", subtitle="A great talk")
        html = build_deck(deck)

        assert "slide--title" in html
        assert "<h1>" in html

    def test_columns_splits_at_hr(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Cols",
            content="Left content\n\n---\n\nRight content",
            classes=["cols-2"],
        )
        html = build_deck(deck)

        assert 'class="col"' in html
        assert "<hr" not in html.split("slide-content")[1].split("</section>")[0]
        assert "Left content" in html
        assert "Right content" in html

    def test_columns_three_way_split(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Three",
            content="A\n\n---\n\nB\n\n---\n\nC",
            classes=["cols-3"],
        )
        html = build_deck(deck)

        assert html.count('class="col"') == 3

    def test_columns_ratio_class(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Ratio",
            content="Wide\n\n---\n\nNarrow",
            classes=["cols-60-40"],
        )
        html = build_deck(deck)

        assert "cols-60-40" in html
        assert 'class="col"' in html

    def test_no_columns_preserves_hr(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Normal", content="Above\n\n---\n\nBelow")
        html = build_deck(deck)

        assert "<hr" in html
        assert 'class="col"' not in html

    def test_utility_classes_on_section(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Styled",
            content="Content",
            classes=["align-center", "size-large", "pad-compact"],
        )
        html = build_deck(deck)

        assert "align-center" in html
        assert "size-large" in html
        assert "pad-compact" in html

    def test_title_hidden_class(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Hidden", content="Body", classes=["title-hidden"])
        html = build_deck(deck)

        assert "title-hidden" in html


class TestBuildFile:
    def test_build_from_markdown(self):
        md_content = """---
title: File Test
---

## Slide One

Content here
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "test.md"
            md_path.write_text(md_content)

            result = build_file(str(md_path))
            assert Path(result).exists()
            assert result.endswith(".html")

            html = Path(result).read_text()
            assert "File Test" in html
            assert "Slide One" in html

    def test_build_custom_output(self):
        md_content = "---\ntitle: Test\n---\n\n## S1\n\nHello"

        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "input.md"
            md_path.write_text(md_content)

            out_path = str(Path(tmpdir) / "output" / "custom.html")
            result = build_file(str(md_path), out_path)
            assert Path(result).exists()
            assert "output" in result
