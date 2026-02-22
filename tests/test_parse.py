"""Tests for the markdown parser."""

from colloquium.parse import parse_frontmatter, parse_slide, parse_markdown


class TestParseFrontmatter:
    def test_basic_frontmatter(self):
        text = "---\ntitle: Hello\nauthor: Test\n---\n\nBody"
        meta, body = parse_frontmatter(text)
        assert meta["title"] == "Hello"
        assert meta["author"] == "Test"
        assert body == "Body"

    def test_no_frontmatter(self):
        text = "Just some content"
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert body == "Just some content"

    def test_empty_frontmatter(self):
        text = "---\n---\nBody"
        meta, body = parse_frontmatter(text)
        assert meta == {}
        assert body == "Body"

    def test_all_fields(self):
        text = "---\ntitle: Talk\nauthor: Me\ndate: 2026-01-01\ntheme: dark\naspect_ratio: '4:3'\n---\nBody"
        meta, body = parse_frontmatter(text)
        assert meta["title"] == "Talk"
        assert meta["theme"] == "dark"
        assert meta["aspect_ratio"] == "4:3"


class TestParseSlide:
    def test_basic_slide(self):
        text = "## My Slide\n\nSome content here."
        slide = parse_slide(text)
        assert slide.title == "My Slide"
        assert "Some content here." in slide.content

    def test_title_slide(self):
        text = "# Title Slide\n\nSubtitle"
        slide = parse_slide(text)
        assert slide.title == "Title Slide"
        assert slide.layout == "title"

    def test_layout_directive(self):
        text = "<!-- layout: two-column -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert slide.layout == "two-column"
        assert slide.title == "Slide"

    def test_class_directive(self):
        text = "<!-- class: highlight special -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "highlight" in slide.classes
        assert "special" in slide.classes

    def test_style_directive(self):
        text = "<!-- style: background: #1a1a2e -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert slide.style == "background: #1a1a2e"

    def test_speaker_notes(self):
        text = "## Slide\n\nContent\n\n<!-- notes: Remember to mention X -->"
        slide = parse_slide(text)
        assert slide.speaker_notes == "Remember to mention X"

    def test_no_title(self):
        text = "Just content without a title."
        slide = parse_slide(text)
        assert slide.title == ""
        assert "Just content without a title." in slide.content

    def test_title_directive_top(self):
        text = "<!-- title: top -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "title-top" in slide.classes

    def test_title_directive_center(self):
        text = "<!-- title: center -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "title-center" in slide.classes

    def test_title_directive_hidden(self):
        text = "<!-- title: hidden -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "title-hidden" in slide.classes

    def test_align_directive(self):
        text = "<!-- align: center -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "align-center" in slide.classes

    def test_align_right_directive(self):
        text = "<!-- align: right -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "align-right" in slide.classes

    def test_valign_directive(self):
        text = "<!-- valign: bottom -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "valign-bottom" in slide.classes

    def test_columns_equal(self):
        text = "<!-- columns: 2 -->\n## Slide\n\nCol 1\n\n---\n\nCol 2"
        slide = parse_slide(text)
        assert "cols-2" in slide.classes

    def test_columns_three(self):
        text = "<!-- columns: 3 -->\n## Slide\n\nCol 1\n\n---\n\nCol 2\n\n---\n\nCol 3"
        slide = parse_slide(text)
        assert "cols-3" in slide.classes

    def test_columns_ratio(self):
        text = "<!-- columns: 60/40 -->\n## Slide\n\nWide\n\n---\n\nNarrow"
        slide = parse_slide(text)
        assert "cols-60-40" in slide.classes

    def test_columns_ratio_30_70(self):
        text = "<!-- columns: 30/70 -->\n## Slide\n\nNarrow\n\n---\n\nWide"
        slide = parse_slide(text)
        assert "cols-30-70" in slide.classes

    def test_padding_directive(self):
        text = "<!-- padding: compact -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "pad-compact" in slide.classes

    def test_padding_wide(self):
        text = "<!-- padding: wide -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "pad-wide" in slide.classes

    def test_size_directive(self):
        text = "<!-- size: large -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "size-large" in slide.classes

    def test_size_small(self):
        text = "<!-- size: small -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "size-small" in slide.classes

    def test_multiple_directives(self):
        text = "<!-- align: center -->\n<!-- size: large -->\n<!-- padding: compact -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "align-center" in slide.classes
        assert "size-large" in slide.classes
        assert "pad-compact" in slide.classes

    def test_directive_with_class(self):
        text = "<!-- class: highlight -->\n<!-- align: center -->\n## Slide\n\nContent"
        slide = parse_slide(text)
        assert "highlight" in slide.classes
        assert "align-center" in slide.classes


class TestParseMarkdown:
    def test_full_document(self):
        text = """---
title: Test Talk
author: Author
---

# Test Talk

Author

---

## Slide Two

- Point 1
- Point 2

---

## Slide Three

Some math: $E = mc^2$
"""
        deck = parse_markdown(text)
        assert deck.title == "Test Talk"
        assert deck.author == "Author"
        assert len(deck.slides) == 3
        assert deck.slides[0].title == "Test Talk"
        assert deck.slides[1].title == "Slide Two"
        assert deck.slides[2].title == "Slide Three"

    def test_empty_document(self):
        deck = parse_markdown("")
        assert deck.title == "Untitled"
        assert len(deck.slides) == 0

    def test_no_frontmatter(self):
        text = "## Slide One\n\nContent"
        deck = parse_markdown(text)
        assert deck.title == "Untitled"
        assert len(deck.slides) == 1

    def test_preserves_math(self):
        text = "---\ntitle: Math\n---\n\n## Equations\n\n$$E = mc^2$$\n\nInline $x^2$"
        deck = parse_markdown(text)
        assert "$$E = mc^2$$" in deck.slides[0].content
        assert "$x^2$" in deck.slides[0].content
