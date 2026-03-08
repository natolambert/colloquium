"""Tests for the HTML builder."""

import tempfile
from pathlib import Path

from colloquium.build import build_deck, build_file, _process_citations, _parse_bib_file, _build_references_slides_html
from colloquium.deck import Deck
from colloquium.slide import Slide
from colloquium.elements.conversation import process as process_conversation, PATTERN as CONV_PATTERN


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
        assert "katex.render" in html
        assert "colloquiumFitDisplayMathIn" in html

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

    def test_title_sidebar_with_valign_class(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Long Title",
            content="Meta",
            layout="title-sidebar",
            classes=["valign-bottom"],
        )
        html = build_deck(deck)

        assert 'class="slide slide--title-sidebar active valign-bottom"' in html

    def test_columns_splits_at_divider(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Cols",
            content="Left content\n\n|||\n\nRight content",
            classes=["cols-2"],
        )
        html = build_deck(deck)

        assert 'class="col"' in html
        assert "|||" not in html.split("slide-content")[1].split("</section>")[0]
        assert "Left content" in html
        assert "Right content" in html

    def test_columns_three_way_split(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Three",
            content="A\n\n|||\n\nB\n\n|||\n\nC",
            classes=["cols-3"],
        )
        html = build_deck(deck)

        assert html.count('class="col"') == 3

    def test_columns_ratio_class(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Ratio",
            content="Wide\n\n|||\n\nNarrow",
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

    def test_footer_inside_section(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S1", content="C")
        html = build_deck(deck)

        # Footer must be inside the <section>, not outside
        section = html.split("<section")[1].split("</section>")[0]
        assert 'class="colloquium-footer"' in section

    def test_default_footer_has_counter(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S1", content="C")
        html = build_deck(deck)

        assert 'class="colloquium-counter"' in html
        assert "1 / 1" in html

    def test_correct_static_slide_numbers(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S1", content="A")
        deck.add_slide(title="S2", content="B")
        html = build_deck(deck)

        assert "1 / 2" in html
        assert "2 / 2" in html

    def test_custom_footer_counter_template_is_clickable(self):
        deck = Deck(title="Test", footer={"right": "Lambert {n}/{N}"})
        deck.add_slide(title="S1", content="A")
        deck.add_slide(title="S2", content="B")
        html = build_deck(deck)

        assert html.count('class="colloquium-counter"') == 2
        assert "Lambert 1/2" in html
        assert "Lambert 2/2" in html

    def test_right_footer_zone_is_always_nav_trigger(self):
        deck = Deck(title="Test", footer={"left": "ACME", "right": "Appendix"})
        deck.add_slide(title="S1", content="A")
        html = build_deck(deck)

        assert 'class="colloquium-footer-right colloquium-footer-nav"' in html
        assert ">Appendix<" in html

    def test_img_align_utility_styles_only_images(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Image", content="![alt](demo.png)", classes=["img-align-right"])
        html = build_deck(deck)

        assert ".img-align-right .slide-content img {\n    display: block;" in html
        assert ".img-align-right .slide-content img { margin-left: auto; }" in html
        assert ".img-align-center .slide-content { display: flex;" not in html

    def test_chart_print_image_hidden_on_screen(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Chart", content="```chart\ntype: bar\ndata:\n  labels: [A]\n  datasets:\n    - label: Series\n      data: [1]\n```")
        html = build_deck(deck)

        assert ".slide .slide-content img.colloquium-chart-print {" in html
        assert "max-height: none;" in html

    def test_no_old_nav_div(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S1", content="C")
        html = build_deck(deck)

        assert "colloquium-nav" not in html

    def test_image_logo_detected(self):
        deck = Deck(title="Test", footer={"left": "https://example.com/logo.png", "right": "auto"})
        deck.add_slide(title="S1", content="C")
        html = build_deck(deck)

        assert 'class="colloquium-footer-logo"' in html
        assert "https://example.com/logo.png" in html

    def test_footer_text_zones(self):
        deck = Deck(title="Test", footer={"left": "ACME Corp", "center": "My Talk", "right": "auto"})
        deck.add_slide(title="S1", content="C")
        html = build_deck(deck)

        assert "ACME Corp" in html
        assert "My Talk" in html
        assert "1 / 1" in html


    def test_footer_placeholder_n(self):
        """Footer text with {n} gets current slide number."""
        deck = Deck(title="Test", footer={"left": "rlhfbook.com", "right": "Lambert {n}"})
        deck.add_slide(title="S1", content="A")
        deck.add_slide(title="S2", content="B")
        html = build_deck(deck)

        assert "Lambert 1" in html
        assert "Lambert 2" in html
        assert 'class="colloquium-counter"' in html

    def test_footer_placeholder_N(self):
        """Footer text with {N} gets total slide count."""
        deck = Deck(title="Test", footer={"right": "{n}/{N}"})
        deck.add_slide(title="S1", content="A")
        deck.add_slide(title="S2", content="B")
        html = build_deck(deck)

        assert "1/2" in html
        assert "2/2" in html

    def test_footer_auto_inject_counter_when_missing(self):
        """Counter appears in empty center zone when no zone uses auto or placeholders."""
        deck = Deck(title="Test", footer={"left": "rlhfbook.com", "right": "Lambert"})
        deck.add_slide(title="S1", content="A")
        deck.add_slide(title="S2", content="B")
        html = build_deck(deck)

        assert "1 / 2" in html
        assert "2 / 2" in html
        assert 'class="colloquium-counter"' in html


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


class TestConversationRendering:
    def test_basic_rendering(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Chat",
            content='```conversation\nmessages:\n  - role: user\n    content: "Hello"\n  - role: assistant\n    content: "Hi there"\n```',
        )
        html = build_deck(deck)

        assert "colloquium-conversation" in html
        assert "colloquium-message--user" in html
        assert "colloquium-message--assistant" in html
        assert "Hello" in html
        assert "Hi there" in html

    def test_system_messages(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Chat",
            content='```conversation\nmessages:\n  - role: system\n    content: "You are helpful."\n```',
        )
        html = build_deck(deck)

        assert "colloquium-message--system" in html
        assert "You are helpful." in html

    def test_markdown_in_content(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Chat",
            content='```conversation\nmessages:\n  - role: assistant\n    content: "This is **bold** and `code`"\n```',
        )
        html = build_deck(deck)

        assert "<strong>bold</strong>" in html
        assert "<code>code</code>" in html

    def test_invalid_yaml(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Chat",
            content='```conversation\n[invalid yaml: {{{\n```',
        )
        html = build_deck(deck)

        assert "Invalid conversation YAML" in html

    def test_unique_ids(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Chat 1",
            content='```conversation\nmessages:\n  - role: user\n    content: "A"\n```',
        )
        deck.add_slide(
            title="Chat 2",
            content='```conversation\nmessages:\n  - role: user\n    content: "B"\n```',
        )
        html = build_deck(deck)

        assert "colloquium-conversation-1" in html
        assert "colloquium-conversation-2" in html

    def test_system_renders_above_others(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Chat",
            content='```conversation\nmessages:\n  - role: user\n    content: "Hi"\n  - role: assistant\n    content: "Hello"\n  - role: system\n    content: "Be helpful"\n```',
        )
        html = build_deck(deck)

        # Extract just the conversation div by its unique ID
        conv_start = html.index('id="colloquium-conversation-1"')
        conv_html = html[conv_start:]
        # System should appear before user and assistant within the conversation
        sys_pos = conv_html.index("colloquium-message--system")
        user_pos = conv_html.index("colloquium-message--user")
        asst_pos = conv_html.index("colloquium-message--assistant")
        assert sys_pos < user_pos
        assert sys_pos < asst_pos

    def test_role_labels(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Chat",
            content='```conversation\nmessages:\n  - role: user\n    content: "Hi"\n  - role: assistant\n    content: "Hello"\n```',
        )
        html = build_deck(deck)

        assert "User" in html
        assert "Assistant" in html


class TestCitationRendering:
    def _make_bib(self, tmpdir):
        bib_content = """@article{smith2024,
  author = {Smith, John and Doe, Jane},
  title = {A Great Paper},
  journal = {Nature},
  year = {2024},
}

@article{jones2023,
  author = {Jones, Alice and Brown, Bob and White, Charlie},
  title = {Another Paper},
  journal = {Science},
  year = {2023},
}

@book{lee2025,
  author = {Lee, David},
  title = {The Big Book},
  booktitle = {Academic Press},
  year = {2025},
}
"""
        bib_path = Path(tmpdir) / "refs.bib"
        bib_path.write_text(bib_content)
        return str(bib_path)

    def test_author_year_style(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = []

            result = _process_citations(
                "See [@smith2024] for details.",
                bib_entries, "author-year", cited_keys,
            )

            assert "Smith" in result
            assert "2024" in result
            assert "colloquium-cite" in result
            assert "smith2024" in cited_keys

    def test_numeric_style(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = []

            result = _process_citations(
                "See [@smith2024] for details.",
                bib_entries, "numeric", cited_keys,
            )

            assert "[1]" in result

    def test_title_year_style(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = []

            result = _process_citations(
                "See [@smith2024] for details.",
                bib_entries, "title-year", cited_keys,
            )

            assert "A Great Paper" in result
            assert "2024" in result

    def test_multiple_citations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = []

            result = _process_citations(
                "See [@smith2024; @jones2023] for details.",
                bib_entries, "author-year", cited_keys,
            )

            assert "Smith" in result
            assert "Jones" in result
            assert len(cited_keys) == 2

    def test_references_slide_generated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = ["smith2024", "jones2023"]

            ref_slides = _build_references_slides_html(
                bib_entries, cited_keys, "author-year", 5, 7, None,
            )
            ref_html = "\n".join(ref_slides)

            assert "References" in ref_html
            assert "colloquium-reference" in ref_html
            assert "smith2024" in ref_html
            assert "jones2023" in ref_html

    def test_only_cited_works_included(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = ["smith2024"]

            ref_slides = _build_references_slides_html(
                bib_entries, cited_keys, "author-year", 5, 6, None,
            )
            ref_html = "\n".join(ref_slides)

            assert "smith2024" in ref_html
            assert "jones2023" not in ref_html

    def test_missing_key_handling(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = []

            result = _process_citations(
                "See [@nonexistent] for details.",
                bib_entries, "author-year", cited_keys,
            )

            assert "colloquium-cite-missing" in result
            assert "nonexistent?" in result

    def test_no_bib_passthrough(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S1", content="See [@key] for details.")
        html = build_deck(deck)

        # Without bibliography, [@key] should pass through as-is
        assert "[@key]" in html

    def test_et_al_for_three_plus_authors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = []

            result = _process_citations(
                "[@jones2023]",
                bib_entries, "author-year", cited_keys,
            )

            assert "et al." in result

    def test_two_authors_shows_both(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = []

            result = _process_citations(
                "[@smith2024]",
                bib_entries, "author-year", cited_keys,
            )

            assert "Smith" in result
            assert "Doe" in result

    def test_full_build_with_bib(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path)
            deck.add_slide(title="Intro", content="See [@smith2024] for details.")
            html = build_deck(deck)

            assert "Smith" in html
            assert "colloquium-cite" in html
            assert "References" in html
            assert "colloquium-reference" in html

    def test_reference_has_italic_title(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = ["smith2024"]

            ref_slides = _build_references_slides_html(
                bib_entries, cited_keys, "author-year", 5, 6, None,
            )
            ref_html = "\n".join(ref_slides)

            # Title should be in <em> tags (italicized)
            assert "<em>A Great Paper</em>" in ref_html

    def test_reference_has_venue_italic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = ["smith2024"]

            ref_slides = _build_references_slides_html(
                bib_entries, cited_keys, "author-year", 5, 6, None,
            )
            ref_html = "\n".join(ref_slides)

            assert "<em>Nature</em>" in ref_html

    def test_references_paginate(self):
        """Many references with long text should split across slides."""
        # Generate refs with long author lists and titles so each takes ~3+ lines
        bib_content = ""
        for i in range(20):
            authors = " and ".join(
                f"Author{i}_{j}, FirstName{j}" for j in range(6)
            )
            bib_content += f"""@article{{ref{i},
  author = {{{authors}}},
  title = {{A Very Long Paper Title Number {i} About Something Interesting in Machine Learning Research}},
  journal = {{Proceedings of the International Conference on Learning Representations}},
  year = {{2024}},
}}

"""
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = Path(tmpdir) / "refs.bib"
            bib_path.write_text(bib_content)
            bib_entries = _parse_bib_file(str(bib_path))
            cited_keys = [f"ref{i}" for i in range(20)]

            ref_slides = _build_references_slides_html(
                bib_entries, cited_keys, "author-year", 10, 13, None,
            )

            # With ~3 lines per ref and 24-line budget, should need multiple pages
            assert len(ref_slides) >= 2
            combined = "\n".join(ref_slides)
            total_pages = len(ref_slides)
            assert f"References (1/{total_pages})" in combined
            assert f"References ({total_pages}/{total_pages})" in combined

    def test_references_fit_single_page(self):
        """Few short references should fit on one page without pagination."""
        bib_content = ""
        for i in range(5):
            bib_content += f"""@article{{ref{i},
  author = {{Author{i}, A.}},
  title = {{Short Title {i}}},
  journal = {{Journal}},
  year = {{2024}},
}}

"""
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = Path(tmpdir) / "refs.bib"
            bib_path.write_text(bib_content)
            bib_entries = _parse_bib_file(str(bib_path))
            cited_keys = [f"ref{i}" for i in range(5)]

            ref_slides = _build_references_slides_html(
                bib_entries, cited_keys, "author-year", 5, 6, None,
            )

            assert len(ref_slides) == 1
            assert "References" in ref_slides[0]
            # No page numbers when single page
            assert "(1/" not in ref_slides[0]

    def test_per_slide_cite_left(self):
        from colloquium.parse import parse_slide

        slide = parse_slide("## Test\n\n<!-- cite: smith2024, jones2023 -->\n\nContent")
        assert slide.metadata.get("cite_left") == ["smith2024", "jones2023"]

    def test_per_slide_cite_right(self):
        from colloquium.parse import parse_slide

        slide = parse_slide("## Test\n\n<!-- cite-right: smith2024 -->\n\nContent")
        assert slide.metadata.get("cite_right") == ["smith2024"]

    def test_per_slide_cite_renders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path)
            slide = Slide(
                title="Intro",
                content="Some content.",
                metadata={"cite_left": ["smith2024"]},
            )
            deck.slides.append(slide)
            html = build_deck(deck)

            assert "colloquium-slide-cite--left" in html
            assert "Smith" in html

    def test_per_slide_cite_right_renders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path)
            slide = Slide(
                title="Intro",
                content="Some content.",
                metadata={"cite_right": ["jones2023"]},
            )
            deck.slides.append(slide)
            html = build_deck(deck)

            assert "colloquium-slide-cite--right" in html
            assert "Jones" in html
