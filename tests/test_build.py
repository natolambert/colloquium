"""Tests for the HTML builder."""

import re
import tempfile
from pathlib import Path

import pytest

from colloquium.build import build_deck, build_file, _process_citations, _parse_bib_file, _build_references_slides_html
from colloquium.deck import Deck
from colloquium.elements import builtwith as builtwith_element
from colloquium.slide import Slide
from colloquium.elements.conversation import process as process_conversation, PATTERN as CONV_PATTERN


def _section_tags(html: str) -> list[str]:
    """Return each slide's opening <section> tag, in render order."""
    return re.findall(r"<section [^>]*>", html)


class TestBuildDeck:
    def test_basic_output(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Hello", content="World")
        html = build_deck(deck)

        assert "<!DOCTYPE html>" in html
        assert "<title>Test</title>" in html
        assert "Hello" in html
        assert "World" in html

    def test_slide_titles_support_inline_markdown(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="What is **RLHF** with *verifiable* [rewards](https://example.com)?",
            content="Body",
        )
        html = build_deck(deck)

        assert "<strong>RLHF</strong>" in html
        assert "<em>verifiable</em>" in html
        assert '<a href="https://example.com">' in html

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

    def test_block_code_preserves_preformatted_whitespace(self):
        deck = Deck(title="Code")
        deck.add_slide(
            title="Example",
            content="```python\nfrom colloquium import Deck\n\ndeck = Deck(title='My Talk')\n```",
        )
        html = build_deck(deck)

        assert ".slide pre code {" in html
        assert "white-space: pre-wrap;" in html
        assert "from colloquium import Deck" in html
        assert "deck = Deck" in html

    def test_spacing_and_footnote_utilities_are_in_theme(self):
        deck = Deck(title="Utils")
        deck.add_slide(
            title="Helpers",
            content='<div class="colloquium-spacer-md"></div><div class="colloquium-footnote">Note</div>',
        )
        html = build_deck(deck)

        assert ".colloquium-spacer-md { height: 1.25em; }" in html
        assert ".colloquium-footnote {" in html
        assert ".colloquium-footnote-ref {" in html

    def test_builtwith_element_renders_badge(self, monkeypatch):
        monkeypatch.setattr(builtwith_element, "_fetch_repo_stars", lambda repo: 321)

        deck = Deck(title="Badge")
        deck.add_slide(
            title="Closing",
            content="```builtwith\nrepo: natolambert/colloquium\n```",
        )
        html = build_deck(deck)

        assert "colloquium-builtwith" in html
        assert "Built with" in html
        assert "natolambert/colloquium" in html
        assert "321 stars" in html

    def test_builtwith_element_can_hide_stars(self):
        deck = Deck(title="Badge")
        deck.add_slide(
            title="Closing",
            content="```builtwith\nstars: false\n```",
        )
        html = build_deck(deck)

        assert "colloquium-builtwith" in html
        assert 'class="colloquium-builtwith-stars"' not in html

    def test_inlines_css_and_js(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S1", content="Content")
        html = build_deck(deck)

        assert "<style>" in html
        assert "--colloquium-bg" in html  # Theme CSS is inlined
        assert "ColloquiumPresentation" in html  # JS is inlined

    def test_print_css_reapplies_non_active_layout_utilities(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Centered", content="Body", classes=["align-center", "valign-center"])
        html = build_deck(deck)

        assert "@media print" in html
        assert ".align-center { text-align: center; }" in html
        assert ".valign-center { justify-content: center; }" in html
        assert ".slide--title-sidebar {" in html

    def test_print_css_keeps_captioned_grid_figures_within_slide_bounds(self):
        deck = Deck(title="Test", figure_captions=True)
        deck.add_slide(
            title="Columns",
            content="Left\n\n|||\n\n![Alt](image.png)",
            classes=["cols-45-55"],
        )
        html = build_deck(deck)

        assert ".slide .colloquium-grid > .col > figure.colloquium-figure:first-child:last-child," in html
        assert "width: 100% !important;" in html
        assert "height: auto !important;" in html
        assert "max-height: calc(720px - var(--colloquium-slide-padding) * 2 - 100px) !important;" in html

    def test_print_css_allows_display_math_to_overflow_columns(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Math",
            content="$$a + b + c + d + e + f + g$$",
            classes=["cols-60-40"],
        )
        html = build_deck(deck)

        assert ".slide .katex-display {" in html
        assert "overflow: visible !important;" in html

    def test_print_css_swaps_live_iframes_for_linked_fallbacks(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Embed",
            content=(
                "```iframe\n"
                "src: https://example.com/embed.html\n"
                "title: Interactive demo\n"
                "```"
            ),
        )
        html = build_deck(deck)

        assert '<iframe class="colloquium-iframe"' in html
        assert '<div class="colloquium-iframe-print-fallback">' in html
        assert (
            ".colloquium-iframe-print-fallback,\n"
            ".colloquium-iframe-print-snapshot {\n    display: none;"
        ) in html
        print_css = html[html.index("@media print") :]
        assert ".colloquium-iframe {\n        display: none !important;" in print_css
        assert ".colloquium-iframe-print-fallback {\n        display: flex !important;" in print_css

    def test_align_center_centers_standalone_images(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Centered", content="![Alt](image.png)", classes=["align-center"])
        html = build_deck(deck)

        assert ".align-center.active .slide-content > p > img {" in html
        assert "margin-left: auto;" in html
        assert "margin-right: auto;" in html

    def test_figure_captions_wrap_standalone_images(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Figure",
            content="![A *caption*](image.png)",
            classes=["figure-captions"],
        )
        html = build_deck(deck)

        assert '<figure class="colloquium-figure"><img src="image.png" alt="A caption" />' in html
        assert '<figcaption class="colloquium-figure-caption">A caption</figcaption>' in html
        assert 'content: "Figure " counter(colloquium-figure) ": ";' in html

    def test_deck_level_figure_captions_enable_figures(self):
        deck = Deck(title="Test", figure_captions=True)
        deck.add_slide(title="Figure", content="![Caption](image.png)")
        html = build_deck(deck)

        assert '<figure class="colloquium-figure"><img src="image.png" alt="Caption" />' in html
        assert '<figcaption class="colloquium-figure-caption">Caption</figcaption>' in html

    def test_no_figure_captions_class_overrides_deck_default(self):
        deck = Deck(title="Test", figure_captions=True)
        deck.add_slide(title="Figure", content="![Caption](image.png)", classes=["no-figure-captions"])
        html = build_deck(deck)

        assert '<figure class="colloquium-figure">' not in html
        assert '<p><img src="image.png" alt="Caption" /></p>' in html

    def test_figure_captions_omit_empty_alt_text(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Figure",
            content="![](image.png)",
            classes=["figure-captions"],
        )
        html = build_deck(deck)

        assert '<p><img src="image.png" alt="" /></p>' in html
        assert '<figure class="colloquium-figure">' not in html
        assert "colloquium-figure-caption" not in html

    def test_figure_captions_preserve_grid_image_layout_hooks(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Grid",
            content="![Caption](demo.png)\n\n|||\n\nText",
            classes=["cols-2", "figure-captions", "img-valign-bottom"],
        )
        html = build_deck(deck)

        assert ".slide .colloquium-grid > .col > figure.colloquium-figure:first-child:last-child," in html
        assert ".slide.img-valign-bottom .colloquium-grid > .col:has(> figure.colloquium-figure:first-child:last-child)," in html
        assert ".slide .colloquium-grid > .col > figure.colloquium-figure:first-child:last-child > img," in html

    def test_figure_captions_include_runtime_fit_helper(self):
        deck = Deck(title="Test", figure_captions=True)
        deck.add_slide(title="Figure", content="![Caption](image.png)")
        html = build_deck(deck)

        assert "window.colloquiumFitCaptionedFiguresIn = function(root)" in html
        assert '.slide-content > figure.colloquium-figure:first-child:last-child' in html

    def test_box_element_renders(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Box",
            content=(
                "```box\n"
                "title: Key point\n"
                "tone: accent\n"
                "content: |\n"
                "  - One\n"
                "  - Two\n"
                "```"
            ),
        )
        html = build_deck(deck)

        assert 'class="colloquium-box colloquium-box--accent"' in html
        assert "colloquium-box-title" in html
        assert "<li>One</li>" in html

    def test_box_element_applies_smart_typography(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Box",
            content=(
                "```box\n"
                "title: The plan\n"
                "content: |\n"
                "  **Basics** -- why models need \"tools\"\n"
                "```"
            ),
        )
        html = build_deck(deck)

        assert "\u2013 why models need \u201ctools\u201d" in html

    def test_conversation_element_applies_smart_typography(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Chat",
            content=(
                "```conversation\n"
                "messages:\n"
                "  - role: user\n"
                "    content: |\n"
                "      A question -- with a \"quote\"\n"
                "```"
            ),
        )
        html = build_deck(deck)

        assert "\u2013 with a \u201cquote\u201d" in html

    def test_box_element_allows_unquoted_colon_in_title(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Box",
            content=(
                "```box\n"
                "title: DPO became very popular as it is:\n"
                "tone: accent\n"
                "content: |\n"
                "  - One\n"
                "```"
            ),
        )
        html = build_deck(deck)

        assert "Invalid box YAML" not in html
        assert "DPO became very popular as it is:" in html

    def test_box_element_compact_option_renders_class(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Box",
            content=(
                "```box\n"
                "title: Compact\n"
                "tone: muted\n"
                "compact: true\n"
                "content: |\n"
                "  - One\n"
                "  - Two\n"
                "```"
            ),
        )
        html = build_deck(deck)

        assert "colloquium-box--compact" in html

    def test_box_element_allows_title_only(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Box",
            content=(
                "```box\n"
                "title: Quick takeaway\n"
                "tone: accent\n"
                "```"
            ),
        )
        html = build_deck(deck)

        assert "Quick takeaway" in html
        assert "Invalid box YAML" not in html
        assert "Box requires title or content" not in html
        assert 'class="colloquium-box-content"' not in html

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

    def test_custom_css_from_a_file_next_to_the_deck(self, tmp_path):
        (tmp_path / "deck.css").write_text(".from-file { color: green; }", encoding="utf-8")
        source = tmp_path / "deck.md"
        source.write_text("---\ncustom_css: deck.css\n---\n## S1\n\nC", encoding="utf-8")
        output = build_file(str(source))
        html = Path(output).read_text(encoding="utf-8")

        assert ".from-file { color: green; }" in html
        assert "deck.css" not in html.split("<body")[0].split("<style")[0]

    def test_custom_css_file_and_inline_css_combine(self, tmp_path):
        (tmp_path / "deck.css").write_text(".from-file { }", encoding="utf-8")
        deck = Deck(title="Test", custom_css=".inline { }", custom_css_path="deck.css", source_dir=str(tmp_path))
        deck.add_slide(title="S1", content="C")
        html = build_deck(deck)

        assert ".from-file { }\n.inline { }" in html

    def test_missing_custom_css_file_names_the_path(self, tmp_path):
        source = tmp_path / "deck.md"
        source.write_text("---\ncustom_css: missing.css\n---\n## S1\n\nC", encoding="utf-8")

        with pytest.raises(FileNotFoundError, match="missing.css"):
            build_file(str(source))

    def test_custom_css_path_round_trips_through_markdown(self):
        deck = Deck(title="Test", custom_css_path="deck.css")
        assert "custom_css: deck.css" in deck.to_markdown()

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
        assert 'grid-template-columns: minmax(0, 60fr) minmax(0, 40fr);' in html

    def test_columns_arbitrary_ratio_class(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Ratio",
            content="Wide\n\n|||\n\nNarrow",
            classes=["cols-25-75"],
        )
        html = build_deck(deck)

        assert 'grid-template-columns: minmax(0, 25fr) minmax(0, 75fr);' in html

    def test_rows_splits_at_divider(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Rows",
            content="Top row\n\n===\n\nBottom row",
            classes=["rows-2"],
        )
        html = build_deck(deck)

        assert 'class="slide slide--content active rows-2"' in html
        assert html.count('class="colloquium-row"') == 2
        assert "Top row" in html
        assert "Bottom row" in html
        assert 'grid-template-rows: repeat(2, minmax(0, 1fr));' in html

    def test_rows_with_nested_columns(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Rows",
            content="<!-- row-columns: 40/60 -->\nLeft\n\n|||\n\nRight\n\n===\n\nBottom",
            classes=["rows-35-65"],
        )
        html = build_deck(deck)

        assert 'class="colloquium-row cols-40-60 colloquium-grid"' in html
        assert html.count('class="col"') == 2
        assert "Bottom" in html
        assert 'grid-template-columns: minmax(0, 40fr) minmax(0, 60fr);' in html

    def test_rows_arbitrary_ratio_class(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Rows",
            content="Top\n\n===\n\nBottom",
            classes=["rows-25-75"],
        )
        html = build_deck(deck)

        assert 'grid-template-rows: minmax(0, 25fr) minmax(0, 75fr);' in html

    def test_rows_emit_print_row_fractions(self):
        """Each row carries its height share for the print image-size cap."""
        deck = Deck(title="Test")
        deck.add_slide(
            title="Rows",
            content="Top\n\n===\n\nBottom",
            classes=["rows-40-60"],
        )
        html = build_deck(deck)

        assert 'style="--colloquium-print-row-frac: 0.4000;"' in html
        assert 'style="--colloquium-print-row-frac: 0.6000;"' in html

    def test_rows_count_spec_emits_equal_print_fractions(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Rows",
            content="Top\n\n===\n\nBottom",
            classes=["rows-2"],
        )
        html = build_deck(deck)

        assert html.count('--colloquium-print-row-frac: 0.5000;') == 2

    def test_rows_huge_count_spec_does_not_allocate(self):
        """An absurd count spec must not materialize a count-sized list."""
        deck = Deck(title="Test")
        deck.add_slide(
            title="Rows",
            content="Top\n\n===\n\nBottom",
            classes=["rows-100000000"],
        )
        html = build_deck(deck)

        assert html.count('--colloquium-print-row-frac: 0.5000;') == 2

    def test_rows_mismatched_spec_falls_back_to_equal_fractions(self):
        """A spec that doesn't match the row count splits evenly instead."""
        deck = Deck(title="Test")
        deck.add_slide(
            title="Rows",
            content="One\n\n===\n\nTwo\n\n===\n\nThree",
            classes=["rows-40-60"],
        )
        html = build_deck(deck)

        assert html.count('--colloquium-print-row-frac: 0.3333;') == 3

    def test_rows_nested_columns_keep_print_fraction_and_grid(self):
        """The row-frac var must coexist with a nested column grid template."""
        deck = Deck(title="Test")
        deck.add_slide(
            title="Rows",
            content="<!-- row-columns: 40/60 -->\nLeft\n\n|||\n\nRight\n\n===\n\nBottom",
            classes=["rows-35-65"],
        )
        html = build_deck(deck)

        assert re.search(
            r'class="colloquium-row cols-40-60 colloquium-grid" '
            r'style="--colloquium-print-row-frac: 0\.3500; '
            r'grid-template-columns: minmax\(0, 40fr\) minmax\(0, 60fr\);"',
            html,
        )

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

    def test_build_includes_picker_trigger(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S1", content="A")
        deck.add_slide(title="S2", content="B")
        html = build_deck(deck)

        assert 'class="colloquium-picker-trigger"' in html
        assert 'class="colloquium-picker-trigger-label">Slides<' in html
        assert 'class="colloquium-picker-trigger-count">1 / 2<' in html

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

    def test_grid_images_top_align_by_default_with_img_valign_overrides(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Grid",
            content="![alt](demo.png)\n\n|||\n\nText",
            classes=["cols-2", "img-valign-bottom"],
        )
        html = build_deck(deck)

        assert ".slide .colloquium-grid > .col > p:first-child:last-child:has(> img)," in html
        assert "align-items: flex-start;" in html
        assert ".slide.img-valign-bottom .colloquium-grid > .col > p:first-child:last-child:has(> img)," in html
        assert "align-items: flex-end;" in html
        assert "object-position: top center;" in html
        assert ".slide.img-valign-center .colloquium-grid > .col > p:first-child:last-child:has(> img) > img," in html
        assert "object-position: center center;" in html
        assert ".slide.img-valign-bottom .colloquium-grid > .col > p:first-child:last-child:has(> img) > img," in html
        assert "object-position: bottom center;" in html
        assert ".slide .colloquium-grid > .col > p:first-child:last-child:has(> img) > img," in html
        assert "height: 100%;" in html

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

    def test_conversation_preserves_line_breaks(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Chat",
            content="```conversation\nmessages:\n  - role: assistant\n    content: 'Line one\\nLine two'\n```",
        )
        html = build_deck(deck)

        assert "Line one\nLine two" in html
        assert "white-space: pre-line;" in html

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

    def test_role_labels_can_include_model_name(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Chat",
            content='```conversation\nmessages:\n  - role: assistant\n    model: "Llama 3.1 405B Base"\n    content: "Hello"\n```',
        )
        html = build_deck(deck)

        assert "Assistant" in html
        assert "(Llama 3.1 405B Base)" in html
        assert "colloquium-message-model" in html

    def test_conversation_numeric_size_modifier(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Chat",
            content='```conversation\nsize: 0.88\nmessages:\n  - role: user\n    content: "Hi"\n  - role: assistant\n    content: "Hello"\n```',
        )
        html = build_deck(deck)

        assert 'class="colloquium-conversation"' in html
        assert 'style="font-size: 0.88em"' in html

    def test_conversation_non_numeric_size_is_ignored(self):
        deck = Deck(title="Test")
        deck.add_slide(
            title="Chat",
            content='```conversation\nsize: small\nmessages:\n  - role: user\n    content: "Hi"\n  - role: assistant\n    content: "Hello"\n```',
        )
        html = build_deck(deck)

        assert 'class="colloquium-conversation"' in html
        assert "colloquium-conversation--small" not in html
        assert 'style="font-size:' not in html


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

    def test_citations_expand_only_outside_html_tags_and_comments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = []

            result = _process_citations(
                '<img alt="Figure [@smith2024]" data-note="2 > 1">'
                '<span>See [@smith2024]</span><!-- [@smith2024] -->',
                bib_entries,
                "author-year",
                cited_keys,
            )

            assert 'alt="Figure [@smith2024]" data-note="2 > 1"' in result
            assert '<span>See <a href="#colloquium-ref-smith2024"' in result
            assert '<!-- [@smith2024] -->' in result
            assert result.count('class="colloquium-cite"') == 1

    @pytest.mark.parametrize("comparison", ["< 5%", "<= 5%", "<5%"])
    def test_citations_expand_between_comparisons_in_raw_html(self, comparison):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path)
            deck.add_slide(
                title="Results",
                content=f"<div>Error {comparison} [@smith2024]; accuracy > 95%.</div>",
            )

            html = build_deck(deck)

            assert (
                f'<div>Error {comparison} '
                '<a href="#colloquium-ref-smith2024" class="colloquium-cite">'
                '(Smith &amp; Doe, 2024)</a>; accuracy > 95%.</div>'
            ) in html

    def test_malformed_bib_warns_and_returns_empty(self, capsys):
        """A broken entry must not silently disable every citation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = Path(tmpdir) / "refs.bib"
            bib_path.write_text(
                "@article{broken2024,\n  title={Missing closing brace}\n"
                "@article{next2024,\n  title={Next},\n  year={2024}\n}\n"
            )
            assert _parse_bib_file(str(bib_path)) == {}
            err = capsys.readouterr().err
            assert "Warning: failed to parse bibliography" in err
            assert "refs.bib" in err
            assert "citations will not resolve" in err

    def test_missing_bib_file_warns_and_returns_empty(self, capsys):
        assert _parse_bib_file("/nonexistent/refs.bib") == {}
        assert "Warning: failed to parse bibliography" in capsys.readouterr().err

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

    def test_title_year_style_strips_inner_bibtex_braces(self):
        bib_content = """@article{smith2024,
  author = {Smith, John},
  title = {{A} Paper About {GPT}-{4}},
  journal = {Nature},
  year = {2024},
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = Path(tmpdir) / "refs.bib"
            bib_path.write_text(bib_content)
            bib_entries = _parse_bib_file(str(bib_path))
            cited_keys = []

            result = _process_citations(
                "See [@smith2024] for details.",
                bib_entries, "title-year", cited_keys,
            )

            assert "A Paper About GPT-4" in result
            assert "{" not in result
            assert "}" not in result

    def test_title_year_style_preserves_latex_macro_arguments(self):
        bib_content = r"""@article{smith2024,
  author = {Smith, John},
  title = {An {\LaTeX{}} Guide},
  journal = {Nature},
  year = {2024},
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = Path(tmpdir) / "refs.bib"
            bib_path.write_text(bib_content)
            bib_entries = _parse_bib_file(str(bib_path))
            cited_keys = []

            result = _process_citations(
                "See [@smith2024] for details.",
                bib_entries, "title-year", cited_keys,
            )

            assert r"\LaTeX{} Guide" in result
            assert r"\LaTeX Guide" not in result

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

    def test_author_year_multiple_citations_default_to_alphabetical(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = ["smith2024", "jones2023"]
            citation_numbers = {"smith2024": 1, "jones2023": 2}

            result = _process_citations(
                "See [@smith2024; @jones2023] for details.",
                bib_entries,
                "author-year",
                cited_keys,
                citation_numbers=citation_numbers,
            )

            assert result.index("Jones") < result.index("Smith")

    def test_author_year_can_preserve_appearance_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = ["smith2024", "jones2023"]
            citation_numbers = {"smith2024": 1, "jones2023": 2}

            result = _process_citations(
                "See [@smith2024; @jones2023] for details.",
                bib_entries,
                "author-year",
                cited_keys,
                citation_order="appearance",
                citation_numbers=citation_numbers,
            )

            assert result.index("Smith") < result.index("Jones")

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

    def test_references_default_to_alphabetical_for_author_year(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = ["smith2024", "jones2023"]
            citation_numbers = {"smith2024": 1, "jones2023": 2}

            ref_slides = _build_references_slides_html(
                bib_entries,
                cited_keys,
                "author-year",
                5,
                7,
                None,
                citation_numbers=citation_numbers,
            )
            ref_html = "\n".join(ref_slides)

            assert ref_html.index("jones2023") < ref_html.index("smith2024")

    def test_references_numeric_stay_in_appearance_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            bib_entries = _parse_bib_file(bib_path)
            cited_keys = ["smith2024", "jones2023"]
            citation_numbers = {"smith2024": 1, "jones2023": 2}

            ref_slides = _build_references_slides_html(
                bib_entries,
                cited_keys,
                "numeric",
                5,
                7,
                None,
                citation_numbers=citation_numbers,
            )
            ref_html = "\n".join(ref_slides)

            assert ref_html.index("smith2024") < ref_html.index("jones2023")
            assert "[1]" in ref_html
            assert "[2]" in ref_html

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

    def test_figure_caption_citation_does_not_corrupt_alt_attribute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path, figure_captions=True)
            deck.add_slide(
                title="Figure",
                content=(
                    "![Critical states in a simple gridworld navigation map "
                    "[@smith2024] ](image.png)"
                ),
            )
            html = build_deck(deck)

            figure_start = html.index('<figure class="colloquium-figure">')
            figure_end = html.index("</figure>", figure_start) + len("</figure>")
            figure_html = html[figure_start:figure_end]

            assert 'alt="Critical states in a simple gridworld navigation map [@smith2024] "' in figure_html
            assert 'alt="Critical states in a simple gridworld navigation map <a' not in figure_html
            assert (
                '<figcaption class="colloquium-figure-caption">'
                'Critical states in a simple gridworld navigation map '
                '<a href="#colloquium-ref-smith2024" class="colloquium-cite">'
                '(Smith &amp; Doe, 2024)</a></figcaption>'
            ) in figure_html
            assert figure_html.count('href="#colloquium-ref-smith2024"') == 1

    def test_numeric_citations_keep_global_numbers_across_slides(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path, citation_style="numeric")
            deck.add_slide(title="One", content="See [@smith2024].")
            deck.add_slide(title="Two", content="Compare [@jones2023].")
            html = build_deck(deck)

            first_slide = html.split("<section")[1]
            second_slide = html.split("<section")[2]
            assert "[1]" in first_slide
            assert "[2]" in second_slide

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

    def test_reference_strips_inner_bibtex_braces_from_title_and_venue(self):
        bib_content = """@article{smith2024,
  author = {Smith, John},
  title = {{A} Paper About {GPT}-{4}},
  journal = {{Transactions on {ML}}},
  year = {2024},
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = Path(tmpdir) / "refs.bib"
            bib_path.write_text(bib_content)
            bib_entries = _parse_bib_file(str(bib_path))
            cited_keys = ["smith2024"]

            ref_slides = _build_references_slides_html(
                bib_entries, cited_keys, "author-year", 5, 6, None,
            )
            ref_html = "\n".join(ref_slides)

            assert "<em>A Paper About GPT-4</em>" in ref_html
            assert "<em>Transactions on ML</em>" in ref_html
            assert "{" not in ref_html
            assert "}" not in ref_html

    def test_reference_preserves_latex_macro_arguments(self):
        bib_content = r"""@article{smith2024,
  author = {Smith, John},
  title = {An {\LaTeX{}} Guide},
  journal = {\textsc{ACL}},
  year = {2024},
}
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = Path(tmpdir) / "refs.bib"
            bib_path.write_text(bib_content)
            bib_entries = _parse_bib_file(str(bib_path))
            cited_keys = ["smith2024"]

            ref_slides = _build_references_slides_html(
                bib_entries, cited_keys, "author-year", 5, 6, None,
            )
            ref_html = "\n".join(ref_slides)

            assert r"<em>An \LaTeX{} Guide</em>" in ref_html
            assert r"<em>\textsc{ACL}</em>" in ref_html
            assert r"\LaTeX Guide" not in ref_html
            assert r"\textscACL" not in ref_html

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

    def test_footnote_citations_count_toward_reference_pages(self):
        """Citations that appear only in footnote directives size the References pages."""
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
            deck = Deck(title="Test", bibliography=str(bib_path), footer={"right": "{n}/{N}"})
            footnote = "Sources: " + "; ".join(f"[@ref{i}]" for i in range(1, 20))
            deck.slides.append(
                Slide(title="Intro", content="See [@ref0].", metadata={"footnote_right": footnote})
            )

            html = build_deck(deck)

            pages = len(re.findall(r"<h2>References \(\d+/\d+\)</h2>", html))
            assert pages >= 2
            total = 1 + pages
            assert f"{total}/{total}" in html
            assert f"{total}/{total - 1}" not in html

    def test_per_slide_cite_left(self):
        from colloquium.parse import parse_slide

        slide = parse_slide("## Test\n\n<!-- cite: smith2024, jones2023 -->\n\nContent")
        assert slide.metadata.get("cite_left") == ["smith2024", "jones2023"]

    def test_per_slide_cite_left_alias(self):
        from colloquium.parse import parse_slide

        slide = parse_slide("## Test\n\n<!-- cite-left: smith2024, jones2023 -->\n\nContent")
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

            assert "colloquium-slide-meta--left" in html
            assert "Smith" in html

    def test_after_references_slides_render_after_generated_references(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path)
            deck.slides.append(Slide(title="Intro", content="See [@smith2024]."))
            deck.slides.append(
                Slide(
                    title="Appendix",
                    content="Extra plot.",
                    metadata={"after": "references"},
                )
            )

            html = build_deck(deck)

            assert html.index("<h2>Intro</h2>") < html.index("<h2>References</h2>")
            assert html.index("<h2>References</h2>") < html.index("<h2>Appendix</h2>")
            assert 'data-index="2"' in html[html.index("<h2>Appendix</h2>") - 80:html.index("<h2>Appendix</h2>")]
            assert "3 / 2" in html
            # The progress bar fills at the end of the references, before the appendix.
            assert '<div class="colloquium-progress" data-main-slides="2">' in html

    def test_references_form_their_own_chapter_when_deck_has_chapters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path)
            deck.slides.append(Slide(title="Part 1", layout="section-break"))
            deck.slides.append(Slide(title="Intro", content="See [@smith2024]."))
            deck.slides.append(
                Slide(title="Appendix", content="Extra.", metadata={"after": "references"})
            )

            tags = _section_tags(build_deck(deck))

            assert 'data-chapter="0"' in tags[1]
            assert 'data-chapter="1" data-chapter-start data-chapter-title="References"' in tags[2]
            # Post-reference slides stay in the references chapter unless they open one.
            assert 'data-chapter="1"' in tags[3]
            assert "data-chapter-start" not in tags[3]

    def test_chapter_bar_and_toc_leave_out_references(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path, chapter_bar=True)
            deck.slides.append(Slide(title="Part 1", layout="section-break"))
            deck.slides.append(Slide(title="Intro", content="See [@smith2024].\n\n```toc\n```"))

            sections = _slide_sections(build_deck(deck))

            references_page = sections[2]
            assert "<h2>References</h2>" in references_page
            assert "has-chapter-bar" in references_page
            assert 'item done" href="#1" title="Part 1"' in references_page
            assert 'chapter-bar-label">References' not in references_page
            assert ">References</a>" not in sections[1]

    def test_references_get_no_chapter_when_deck_has_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path)
            deck.slides.append(Slide(title="Intro", content="See [@smith2024]."))

            tags = _section_tags(build_deck(deck))

            assert not any("data-chapter" in tag for tag in tags)

    def test_after_references_citations_use_render_order(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path, citation_style="numeric")
            deck.slides.append(
                Slide(
                    title="Appendix",
                    content="Appendix cites [@jones2023].",
                    metadata={"after": "references"},
                )
            )
            deck.slides.append(Slide(title="Main", content="Main cites [@smith2024]."))

            html = build_deck(deck)

            main_start = html.index("<h2>Main</h2>")
            references_start = html.index("<h2>References</h2>")
            appendix_start = html.index("<h2>Appendix</h2>")
            main_html = html[main_start:references_start]
            references_html = html[references_start:appendix_start]
            appendix_html = html[appendix_start:]

            assert "[1]" in main_html
            assert "[2]" in appendix_html
            assert references_html.index("Smith") < references_html.index("Jones")

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

            assert "colloquium-slide-meta--right" in html
            assert "Jones" in html

    def test_per_slide_cite_default_order_is_alphabetical(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path)
            slide = Slide(
                title="Intro",
                content="Some content.",
                metadata={"cite_right": ["smith2024", "jones2023"]},
            )
            deck.slides.append(slide)
            html = build_deck(deck)

            assert html.index("Jones") < html.index("Smith")

    def test_per_slide_footnote_left_renders(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Intro",
            content="Some content.",
            metadata={"footnote_left": "Base models are becoming more flexible."},
        )
        deck.slides.append(slide)
        html = build_deck(deck)

        assert "colloquium-slide-meta--left" in html
        assert "colloquium-slide-footnote" in html
        assert "Base models are becoming more flexible." in html

    def test_per_slide_footnote_and_cite_share_stack(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path)
            slide = Slide(
                title="Intro",
                content="Some content.",
                metadata={
                    "cite_right": ["smith2024"],
                    "footnote_right": "Midtraining also matters.",
                },
            )
            deck.slides.append(slide)
            html = build_deck(deck)

            assert html.count('class="colloquium-slide-meta colloquium-slide-meta--right"') == 1
            assert "Midtraining also matters." in html
            assert "Smith" in html

    def test_inline_footnote_renders_reference_marker_and_note(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Intro",
            content="A sentence with a note.^[This is the note.]",
        )
        deck.slides.append(slide)
        html = build_deck(deck)

        assert 'class="colloquium-footnote-ref"' in html
        assert 'id="colloquium-footnote-1-right-1"' in html
        assert "1:" in html
        assert "This is the note." in html

    def test_inline_footnotes_can_render_on_the_left(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Intro",
            content="Left note.^[Moves left.]",
            metadata={"footnotes_position": "left"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)

        assert 'class="colloquium-slide-meta colloquium-slide-meta--left"' in html
        assert "Moves left." in html

    def test_inline_footnote_and_slide_citation_share_stack(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bib_path = self._make_bib(tmpdir)
            deck = Deck(title="Test", bibliography=bib_path)
            slide = Slide(
                title="Intro",
                content="Inline note here.^[A note with context.]",
                metadata={"cite_right": ["smith2024"]},
            )
            deck.slides.append(slide)
            html = build_deck(deck)

            assert html.count('class="colloquium-slide-meta colloquium-slide-meta--right"') == 1
            assert "A note with context." in html
            assert "Smith" in html

    def test_multiple_inline_footnotes_increment_numbers(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Intro",
            content="First note.^[One.] Second note.^[Two.]",
        )
        deck.slides.append(slide)
        html = build_deck(deck)

        assert 'id="colloquium-footnote-1-right-1"' in html
        assert 'id="colloquium-footnote-1-right-2"' in html
        assert "1:" in html
        assert "2:" in html

    def test_inline_footnote_can_contain_math_with_square_brackets(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Intro",
            content=(
                "KL penalty.^[For discrete outputs, "
                "$D_{\\mathrm{KL}}(\\pi \\| \\pi_{\\mathrm{ref}})="
                "\\mathbb{E}_{y \\sim \\pi}\\!\\left[\\log \\pi(y \\mid x)-"
                "\\log \\pi_{\\mathrm{ref}}(y \\mid x)\\right]$.]"
            ),
            metadata={"footnotes_position": "right"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)

        assert 'class="colloquium-footnote-ref"' in html
        assert "\\left[" in html
        assert "\\right]" in html
        assert "colloquium-slide-footnote-text" in html


class TestFragments:
    """Tests for the fragment / incremental reveal system."""

    def test_animate_bullets_adds_fragment_class(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Bullets",
            content="- A\n- B\n- C",
            metadata={"animate": "bullets"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        assert 'class="fragment" data-fragment-index="1"' in html
        assert 'class="fragment" data-fragment-index="2"' in html
        assert 'class="fragment" data-fragment-index="3"' in html

    def test_animate_bullets_sets_fragment_count(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Bullets",
            content="- A\n- B\n- C",
            metadata={"animate": "bullets"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        assert 'data-fragment-count="3"' in html

    def test_animate_items_alias(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Items",
            content="- X\n- Y",
            metadata={"animate": "items"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        assert 'data-fragment-count="2"' in html

    def test_animate_blocks_wraps_elements(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Blocks",
            content="Para one.\n\nPara two.\n\nPara three.",
            metadata={"animate": "blocks"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        assert 'data-fragment-count="3"' in html
        assert '<div class="fragment" data-fragment-index="1"><p>' in html

    def test_step_markers_create_fragments(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Steps",
            content="Visible.\n\n<!-- step -->\n\nRevealed.",
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        assert 'data-fragment-count="1"' in html
        assert '<div class="fragment" data-fragment-index="1">' in html
        # Initial content should NOT be in a fragment div
        assert '<p>Visible.</p>' in html

    def test_step_initial_content_not_wrapped(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Steps",
            content="Initial.\n\n<!-- step -->\n\nLater.",
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        # The initial paragraph should not be wrapped in a fragment div
        section_start = html.index('class="slide-content"')
        fragment_start = html.index('class="fragment"', section_start)
        initial_p = html.index("<p>Initial.</p>", section_start)
        assert initial_p < fragment_start

    def test_multiple_step_markers(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Steps",
            content="A.\n\n<!-- step -->\n\nB.\n\n<!-- step -->\n\nC.",
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        assert 'data-fragment-count="2"' in html
        assert 'data-fragment-index="1"' in html
        assert 'data-fragment-index="2"' in html

    def test_step_and_animate_compose(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Composed",
            content="- A\n- B\n\n<!-- step -->\n\nConclusion.",
            metadata={"animate": "bullets"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        # 2 bullets + 1 step group = 3 fragments
        assert 'data-fragment-count="3"' in html
        assert 'data-fragment-index="1"' in html
        assert 'data-fragment-index="2"' in html
        assert 'data-fragment-index="3"' in html

    def test_no_animate_no_step_no_fragments(self):
        deck = Deck(title="Test")
        slide = Slide(title="Plain", content="Just text.")
        deck.slides.append(slide)
        html = build_deck(deck)
        # The section tag should not have data-fragment-count
        import re
        section = re.search(r'<section[^>]*data-index="0"[^>]*>', html).group()
        section_start = html.index(section)
        section_html = html[section_start:html.index("</section>", section_start)]
        assert "data-fragment-count" not in section
        assert 'data-fragment-index' not in section_html
        assert 'class="fragment"' not in section_html

    def test_fragment_css_present(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Bullets",
            content="- A",
            metadata={"animate": "bullets"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        assert ".fragment[data-fragment-index] {" in html
        assert ".fragment[data-fragment-index].visible {" in html
        assert "pointer-events: none" in html
        assert "pointer-events: auto" in html

    def test_print_css_shows_fragments(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S", content="text")
        html = build_deck(deck)
        assert "@media print" in html
        # Print block should force fragments visible
        print_idx = html.index("@media print")
        closing_brace = html.index("}", html.index(".fragment[data-fragment-index]", print_idx))
        print_fragment_section = html[print_idx:closing_brace]
        assert "opacity: 1" in print_fragment_section

    def test_capture_mode_shows_fragments(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S", content="text")
        html = build_deck(deck)
        assert ".colloquium-capture .fragment[data-fragment-index]" in html

    def test_fragment_js_present(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S", content="text")
        html = build_deck(deck)
        assert "fragmentStates" in html
        assert "_updateFragments" in html

    def test_left_right_step_fragments_while_up_down_jumps_slides(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S1", content="A\n\n<!-- step -->\n\nB")
        deck.add_slide(title="S2", content="C")
        html = build_deck(deck)

        import re

        # Jump-style navigation lands fully revealed (showAllFragments=true).
        assert re.search(
            r"nextSlide\(\) \{\s+this\.goTo\(this\.currentIndex \+ 1, true\);",
            html,
        )
        assert re.search(
            r"prevSlide\(\) \{\s+this\.goTo\(this\.currentIndex - 1, true\);",
            html,
        )
        # Left/Right (and Space/PageDown) advance through fragments then slides.
        assert re.search(
            r"case 'ArrowRight':\s+case ' ':\s+case 'PageDown':\s+"
            r"e\.preventDefault\(\);\s+this\.next\(\);",
            html,
        )
        assert re.search(
            r"case 'ArrowLeft':\s+case 'PageUp':\s+"
            r"e\.preventDefault\(\);\s+this\.prev\(\);",
            html,
        )
        # Up/Down jump whole slides, skipping fragments.
        assert re.search(
            r"case 'ArrowDown':\s+e\.preventDefault\(\);\s+this\.nextSlide\(\);",
            html,
        )
        assert re.search(
            r"case 'ArrowUp':\s+e\.preventDefault\(\);\s+this\.prevSlide\(\);",
            html,
        )

    def test_number_keys_buffer_direct_slide_jump(self):
        deck = Deck(title="Test")
        for i in range(20):
            deck.add_slide(title=f"S{i + 1}", content="Body")
        html = build_deck(deck)

        assert "this.slideNumberBuffer = '';" in html
        assert "this.slideNumberCommitDelay = 700;" in html
        assert "if (this._handleSlideNumberKey(e)) return;" in html
        assert "if (/^\\d$/.test(e.key)) {" in html
        assert "this._appendSlideNumberDigit(e.key);" in html
        assert "if (e.key === 'Enter') {" in html
        assert "this._commitSlideNumberBuffer();" in html
        assert "this.slideNumberBuffer += digit;" in html
        assert "this.slideNumberBuffer.length >= maxDigits" in html
        # Numeric jumps land fully revealed, like all jump-style navigation.
        assert "this.goTo(slideNumber - 1, true);" in html
        # goTo cancels any pending numeric jump so a stale digit can't fire
        # after the user navigates by click/touch/hash/picker; next()/prev()
        # cancel too, since fragment steps bypass goTo.
        assert "Cancel any pending numeric jump" in html
        assert "Fragment steps bypass goTo" in html
        # Opening or dismissing the picker cancels a pending digit too, so a
        # stale timer can't close the picker mid-browse and jump away.
        assert "Opening the picker cancels a pending numeric jump" in html
        assert "Dismissing the picker also cancels a pending numeric jump" in html

    def test_li_with_arbitrary_attributes_gets_fragment_index(self):
        """Bullets with any attribute order must still get data-fragment-index."""
        from colloquium.build import _apply_auto_animate, _number_fragments
        html = (
            '<ul>\n'
            '<li id="first" class="highlight">A</li>\n'
            '<li data-id="2">B</li>\n'
            '</ul>'
        )
        html = _apply_auto_animate(html, "bullets")
        html, count = _number_fragments(html)
        assert count == 2
        assert '<li id="first" class="fragment highlight" data-fragment-index="1">' in html
        assert '<li data-id="2" class="fragment" data-fragment-index="2">' in html

    def test_custom_fragment_class_without_animation_is_untouched(self):
        deck = Deck(title="Test")
        slide = Slide(
            title="Plain",
            content='<div class="fragment">Visible custom fragment</div>',
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        import re
        section = re.search(r'<section[^>]*data-index="0"[^>]*>', html).group()
        section_start = html.index(section)
        section_html = html[section_start:html.index("</section>", section_start)]
        assert "data-fragment-count" not in section
        assert 'data-fragment-index' not in section_html
        assert 'class="fragment">Visible custom fragment</div>' in section_html

    def test_step_mixed_content_wraps_non_fragment_blocks(self):
        """Step groups with bullets + paragraphs must hide paragraphs too."""
        deck = Deck(title="Test")
        slide = Slide(
            title="Mixed",
            content="- A\n- B\n\n<!-- step -->\n\n- C\n\nConclusion.",
            metadata={"animate": "bullets"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        # The conclusion paragraph should be in a fragment div
        assert '<div class="fragment" data-fragment-index=' in html
        # 2 bullets before step + 1 bullet after + 1 paragraph = 4
        assert 'data-fragment-count="4"' in html

    def test_step_only_bullets_no_extra_wrapper(self):
        """Step group with only bullets should not add redundant wrappers."""
        deck = Deck(title="Test")
        slide = Slide(
            title="Pure",
            content="Intro.\n\n<!-- step -->\n\n- A\n- B",
            metadata={"animate": "bullets"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        # 2 bullets in the step group, no extra paragraph to wrap
        assert 'data-fragment-count="2"' in html

    def test_blocks_with_columns(self):
        """Blocks mode must wrap paragraphs inside each column, not across."""
        deck = Deck(title="Test")
        slide = Slide(
            title="Cols",
            content="P1\n\nP2\n\n|||\n\nP3\n\nP4",
            classes=["cols-2"],
            metadata={"animate": "blocks"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        assert 'data-fragment-count="4"' in html
        # Each paragraph wrapped individually inside its column div
        assert '<div class="col"><div class="fragment"' in html

    def test_blocks_with_rows(self):
        """Blocks mode must wrap paragraphs inside each row, not across."""
        deck = Deck(title="Test")
        slide = Slide(
            title="Rows",
            content="P1\n\nP2\n\n===\n\nP3\n\nP4",
            classes=["rows-2"],
            metadata={"animate": "blocks"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        assert 'data-fragment-count="4"' in html
        assert re.search(r'<div class="colloquium-row" style="[^"]*"><div class="fragment"', html)

    def test_blocks_wraps_markdown_headings(self):
        """Blocks mode must treat markdown headings as top-level fragments."""
        deck = Deck(title="Test")
        slide = Slide(
            title="Headings",
            content="### Section\n\nDetails.",
            metadata={"animate": "blocks"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        assert 'data-fragment-count="2"' in html
        assert (
            '<div class="fragment" data-fragment-index="1">'
            '<h3>Section</h3></div>'
        ) in html
        assert (
            '<div class="fragment" data-fragment-index="2">'
            '<p>Details.</p></div>'
        ) in html

    def test_blocks_wrap_generated_div_elements(self):
        """Blocks mode must reveal built-in div-based elements incrementally."""
        deck = Deck(title="Test")
        slide = Slide(
            title="Generated",
            content=(
                "```box\n"
                "title: Key result\n"
                "content: Generated box\n"
                "```\n\n"
                "```chart\n"
                "type: bar\n"
                "data:\n"
                "  labels: [A]\n"
                "  datasets:\n"
                "    - label: Score\n"
                "      data: [1]\n"
                "```\n\n"
                "```conversation\n"
                "messages:\n"
                "  - role: user\n"
                "    content: Hello\n"
                "```\n\n"
                "```iframe\n"
                "src: https://example.com/embed.html\n"
                "```"
            ),
            metadata={"animate": "blocks"},
        )
        deck.slides.append(slide)

        html = build_deck(deck)

        assert 'data-fragment-count="4"' in html
        assert (
            '<div class="fragment" data-fragment-index="1">'
            '<div class="colloquium-box'
        ) in html
        assert (
            '<div class="fragment" data-fragment-index="2">'
            '<div class="colloquium-chart-container">'
        ) in html
        assert (
            '<div class="fragment" data-fragment-index="3">'
            '<div class="colloquium-conversation"'
        ) in html
        assert (
            '<div class="fragment" data-fragment-index="4">'
            '<div class="colloquium-iframe-container"'
        ) in html

    def test_blocks_skip_spacer_only_divs(self):
        """Layout spacer divs should not consume empty reveal steps."""
        deck = Deck(title="Test")
        slide = Slide(
            title="Spacer",
            content=(
                "Before\n\n"
                '<div class="colloquium-spacer-md"></div>\n\n'
                "```box\n"
                "title: Key result\n"
                "content: Generated box\n"
                "```"
            ),
            metadata={"animate": "blocks"},
        )
        deck.slides.append(slide)

        html = build_deck(deck)

        assert 'data-fragment-count="2"' in html
        assert (
            '<div class="fragment" data-fragment-index="1"><p>Before</p></div>\n'
            '<div class="colloquium-spacer-md"></div>\n'
            '<div class="fragment" data-fragment-index="2">'
            '<div class="colloquium-box'
        ) in html

    def test_step_with_columns_preserves_column_boundaries(self):
        """Step fragments in a column must not wrap sibling column divs."""
        deck = Deck(title="Test")
        slide = Slide(
            title="Cols",
            content="Left\n\n<!-- step -->\n\nLeft step\n\n|||\n\nRight",
            classes=["cols-2"],
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        assert 'data-fragment-count="1"' in html
        assert (
            '<div class="col"><p>Left</p>\n'
            '<div class="fragment" data-fragment-index="1"><p>Left step</p></div>'
            '</div><div class="col"><p>Right</p></div>'
        ) in html

    def test_step_with_rows_preserves_row_boundaries(self):
        """Step fragments in a row must not wrap sibling row divs."""
        deck = Deck(title="Test")
        slide = Slide(
            title="Rows",
            content="Top\n\n<!-- step -->\n\nTop step\n\n===\n\nBottom",
            classes=["rows-2"],
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        assert 'data-fragment-count="1"' in html
        assert re.search(
            r'<div class="colloquium-row" style="[^"]*"><p>Top</p>\n'
            r'<div class="fragment" data-fragment-index="1"><p>Top step</p></div>'
            r'</div><div class="colloquium-row" style="[^"]*"><p>Bottom</p>\n</div>',
            html,
        )

    def test_step_blockquote_with_nested_bullets(self):
        """Step group with a blockquote containing fragments must wrap the blockquote."""
        deck = Deck(title="Test")
        slide = Slide(
            title="BQ",
            content="Intro.\n\n<!-- step -->\n\n> Note\n>\n> - A\n> - B",
            metadata={"animate": "bullets"},
        )
        deck.slides.append(slide)
        html = build_deck(deck)
        # blockquote (frag 1) wraps the <p> and bullets (frags 2, 3)
        assert 'data-fragment-count="3"' in html
        assert '<div class="fragment" data-fragment-index="1"><blockquote>' in html


class TestImgTallRightUtility:
    def test_theme_ships_img_tall_right_rules(self):
        import pathlib
        css = (pathlib.Path("colloquium/themes/default/theme.css")).read_text()
        assert ".slide.img-tall-right.active {\n    display: grid;" in css
        assert "grid-template-columns: var(--colloquium-columns, minmax(0, 1fr) minmax(0, 1fr));" in css
        assert ".slide.img-tall-right > .slide-content.colloquium-grid > .col:last-child {" in css
        # The figure column follows the columns ratio; no fixed width remains.
        assert "width: 55%" not in css

    def test_class_directive_reaches_slide_markup(self, tmp_path):
        src = tmp_path / "deck.md"
        src.write_text(
            "---\ntitle: t\n---\n\n"
            "<!-- columns: 45/55 -->\n<!-- class: img-tall-right -->\n## S\n\nText\n\n|||\n\n"
            "![cap](x.png)\n"
        )
        out = tmp_path / "deck.html"
        build_file(str(src), str(out))
        html = out.read_text()
        assert "img-tall-right" in html


class TestEyebrow:
    def test_eyebrow_renders_before_heading(self):
        from colloquium.parse import parse_markdown

        deck = parse_markdown("---\ntitle: T\n---\n\n<!-- eyebrow: Part *1* -->\n\n## Heading\n")
        html = build_deck(deck)
        assert '<div class="slide-eyebrow">Part <em>1</em></div>\n<h2>Heading</h2>' in html

    def test_reference_does_not_double_initial_period(self, tmp_path):
        bib = tmp_path / "refs.bib"
        bib.write_text("@misc{a,\n  title = {T},\n  author = {Doe, Jane},\n  year = {2026}\n}\n")
        entries = _parse_bib_file(str(bib))
        from colloquium.build import _format_reference

        assert "Doe, J.. " not in _format_reference(entries["a"], "a", "author-year", 1)
        assert "Doe, J. " in _format_reference(entries["a"], "a", "author-year", 1)


class TestChapters:
    def test_section_breaks_open_chapters(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Talk", layout="title")
        deck.add_slide(title="Part 1", layout="section-break")
        deck.add_slide(title="A", content="a")
        deck.add_slide(title="Part 2", layout="section-break")
        deck.add_slide(title="B", content="b")

        tags = _section_tags(build_deck(deck))

        assert "data-chapter" not in tags[0]
        assert 'data-chapter="0" data-chapter-start' in tags[1]
        assert "data-chapter-title" not in tags[1]
        assert 'data-chapter="0"' in tags[2]
        assert "data-chapter-start" not in tags[2]
        assert 'data-chapter="1" data-chapter-start' in tags[3]
        assert 'data-chapter="1"' in tags[4]

    def test_chapter_directive_opens_titled_chapter(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Overview", content="x", chapter='Results & "caveats"')
        deck.add_slide(title="Detail", content="y")

        tags = _section_tags(build_deck(deck))

        assert (
            'data-chapter="0" data-chapter-start '
            'data-chapter-title="Results &amp; &quot;caveats&quot;"'
        ) in tags[0]
        assert 'data-chapter="0"' in tags[1]

    def test_chapter_directive_overrides_section_break_title(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Part 1: A long heading", layout="section-break", chapter="Part 1")

        tags = _section_tags(build_deck(deck))

        assert 'data-chapter-title="Part 1"' in tags[0]

    def test_deck_without_chapter_openers_has_no_chapter_attributes(self):
        deck = Deck(title="Test")
        deck.add_slide(title="A", content="a")
        deck.add_slide(title="B", content="b")

        tags = _section_tags(build_deck(deck))

        assert not any("data-chapter" in tag for tag in tags)

    def test_chapters_can_be_disabled(self):
        deck = Deck(title="Test", chapters=False)
        deck.add_slide(title="Part 1", layout="section-break")
        deck.add_slide(title="A", content="a", chapter="Explicit")

        tags = _section_tags(build_deck(deck))

        assert not any("data-chapter" in tag for tag in tags)

    def test_picker_groups_slides_by_chapter(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Part 1", layout="section-break")
        html = build_deck(deck)

        assert "_readChapters()" in html
        assert "colloquium-picker-chapter-header" in html


def _slide_sections(html: str) -> list[str]:
    """Return each slide's full <section> element, in render order."""
    return re.findall(r"<section [^>]*>.*?</section>", html, re.DOTALL)


def _chapter_bar_deck(**deck_kwargs) -> Deck:
    deck = Deck(title="Test", **deck_kwargs)
    deck.add_slide(title="Talk", layout="title")
    deck.add_slide(title="Part 1", layout="section-break")
    deck.add_slide(title="A", content="a")
    deck.add_slide(title="A2", content="a2")
    deck.add_slide(title="Part 2", layout="section-break")
    deck.add_slide(title="B", content="b")
    return deck


class TestChapterBar:
    def test_off_by_default(self):
        html = build_deck(_chapter_bar_deck())

        assert '<nav class="colloquium-chapter-bar"' not in html
        assert "<body>" in html

    def test_shades_done_current_and_upcoming_chapters(self):
        sections = _slide_sections(build_deck(_chapter_bar_deck(chapter_bar=True)))

        # Slide 3 is the second of three slides in chapter 1.
        assert (
            'class="colloquium-chapter-bar-item current" href="#2" title="Part 1" '
            'style="--chapter-progress: 66.6667%" aria-current="step"'
        ) in sections[2]
        assert (
            'class="colloquium-chapter-bar-item upcoming" href="#5" title="Part 2" '
            'style="--chapter-progress: 0%"'
        ) in sections[2]
        # On the Part 2 section break, Part 1 is done and Part 2 is half through.
        assert 'item done" href="#2" title="Part 1" style="--chapter-progress: 100%"' in sections[4]
        assert 'item current" href="#5" title="Part 2" style="--chapter-progress: 50%"' in sections[4]

    def test_skips_title_and_opted_out_slides(self):
        deck = _chapter_bar_deck(chapter_bar=True)
        deck.add_slide(title="Full bleed", content="x", classes=["no-chapter-bar"])

        html = build_deck(deck)
        sections = _slide_sections(html)

        assert '<body class="colloquium-has-chapter-bar">' in html
        assert "colloquium-chapter-bar" not in sections[0]
        assert "colloquium-chapter-bar" not in sections[-1]
        assert "has-chapter-bar" in _section_tags(html)[1]
        assert "has-chapter-bar" not in _section_tags(html)[0]

    def test_sits_before_footer(self):
        section = _slide_sections(build_deck(_chapter_bar_deck(chapter_bar=True)))[2]

        assert section.index('<nav class="colloquium-chapter-bar"') < section.index('class="colloquium-footer"')

    def test_labels_use_plain_heading_text(self):
        deck = Deck(title="Test", chapter_bar=True)
        deck.add_slide(title="Why **open** models?", layout="section-break")

        html = build_deck(deck)

        assert '<span class="colloquium-chapter-bar-label">Why open models?</span>' in html

    def test_chapter_short_sets_the_bar_label_only(self):
        deck = Deck(title="Test", chapter_bar=True)
        deck.add_slide(title="Outline", content="```toc\n```")
        deck.add_slide(
            title="Why should we care about open models?",
            layout="section-break",
            chapter_short="Why care",
        )

        html = build_deck(deck)
        tags = _section_tags(html)

        assert '<span class="colloquium-chapter-bar-label">Why care</span>' in html
        assert 'title="Why should we care about open models?"' in html
        # The picker and the table of contents keep the full title.
        assert "data-chapter-title" not in tags[1]
        assert '<a href="#2">Why should we care about open models?</a>' in html

    def test_bars_mode_drops_labels(self):
        html = build_deck(_chapter_bar_deck(chapter_bar="bars"))

        assert '<nav class="colloquium-chapter-bar colloquium-chapter-bar--bars"' in html
        assert '<span class="colloquium-chapter-bar-label">' not in html
        assert 'title="Part 1"' in html

    def test_section_breaks_scope_with_chapter_progress(self):
        deck = _chapter_bar_deck(chapter_bar={"slides": "section-breaks", "progress": "chapters"})

        html = build_deck(deck)
        sections = _slide_sections(html)

        assert [("colloquium-chapter-bar" in section) for section in sections] == [
            False, True, False, False, True, False,
        ]
        # Whole-chapter progress: the current chapter is full, not 1/n.
        assert 'colloquium-chapter-bar--chapters' in sections[4]
        assert 'item done" href="#2" title="Part 1" style="--chapter-progress: 100%"' in sections[4]
        assert 'item current" href="#5" title="Part 2" style="--chapter-progress: 100%"' in sections[4]
        # Other slides keep the window-edge progress line.
        assert "<body>" in html

    def test_slide_directive_restyles_shows_and_hides(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Part 1", layout="section-break")
        deck.add_slide(title="A", content="a", chapter_bar="bars chapters")
        deck.add_slide(title="B", content="b")
        deck.add_slide(title="C", content="c", chapter_bar="hide")

        sections = _slide_sections(build_deck(deck))

        # The deck has no chapter_bar, but the directive shows one on slide A.
        assert "colloquium-chapter-bar" not in sections[0]
        assert (
            '<nav class="colloquium-chapter-bar colloquium-chapter-bar--bars '
            'colloquium-chapter-bar--chapters"'
        ) in sections[1]
        assert "colloquium-chapter-bar" not in sections[2]

        deck.chapter_bar = {"labels": True, "slides": "all", "progress": "slides"}
        sections = _slide_sections(build_deck(deck))
        assert "colloquium-chapter-bar" in sections[2]
        assert "colloquium-chapter-bar" not in sections[3]

    def test_needs_chapters(self):
        deck = Deck(title="Test", chapter_bar=True)
        deck.add_slide(title="A", content="a")

        html = build_deck(deck)

        assert '<nav class="colloquium-chapter-bar"' not in html
        assert "<body>" in html


class TestSectionBreakFooter:
    def test_section_break_zones_override_the_footer(self):
        deck = Deck(
            title="Test",
            footer={"left": "logo.png", "right": "auto", "section_break": {"left": "logo-white.png"}},
        )
        deck.add_slide(title="Part 1", layout="section-break")
        deck.add_slide(title="A", content="a")

        sections = _slide_sections(build_deck(deck))

        assert 'src="logo-white.png"' in sections[0]
        assert 'src="logo.png"' not in sections[0]
        assert 'src="logo.png"' in sections[1]
        assert "1 / 2" in sections[0]

    def test_footer_zones_accept_lists_of_logos(self):
        deck = Deck(
            title="Test",
            footer={
                "left": ["logo.png", "partner.svg"],
                "right": "auto",
                "section_break": {"left": ["logo-white.png", "partner-white.svg"]},
            },
        )
        deck.add_slide(title="Part 1", layout="section-break")
        deck.add_slide(title="A", content="a")

        sections = _slide_sections(build_deck(deck))

        content_group = re.search(r'<span class="colloquium-footer-group">(.*?)</span>', sections[1]).group(1)
        assert content_group.index('src="logo.png"') < content_group.index('src="partner.svg"')
        assert content_group.count('class="colloquium-footer-logo"') == 2
        assert 'src="partner-white.svg"' in sections[0]
        assert 'src="partner.svg"' not in sections[0]
        assert "2 / 2" in sections[1]


class TestOnlyDirective:
    def test_pptx_only_slides_are_left_out_of_html(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Static", content="x", only="pptx")
        deck.add_slide(title="Live", content="y", only="html")
        deck.add_slide(title="Shared", content="z")

        html = build_deck(deck)

        assert "<h2>Static</h2>" not in html
        assert "<h2>Live</h2>" in html
        assert "2 / 2" in html


class TestTocBlock:
    def _deck(self, toc_slide_chapter: bool = False, toc: str = "```toc\n```") -> Deck:
        deck = Deck(title="Test")
        deck.add_slide(title="Outline", content=toc)
        deck.add_slide(title="Why open models?", layout="section-break")
        deck.add_slide(title="Measuring use", content="x", chapter="Adoption")
        if toc_slide_chapter:
            deck.add_slide(title="Agenda", content=toc)
        return deck

    def test_lists_chapters_with_links(self):
        sections = _slide_sections(build_deck(self._deck()))

        assert (
            '<ol class="colloquium-toc">'
            '<li class="colloquium-toc-item upcoming"><a href="#2">Why open models?</a></li>'
            '<li class="colloquium-toc-item upcoming"><a href="#3">Adoption</a></li>'
            "</ol>"
        ) in sections[0]
        assert "language-toc" not in sections[0]

    def test_marks_the_chapter_it_sits_in(self):
        sections = _slide_sections(build_deck(self._deck(toc_slide_chapter=True)))

        assert '<ol class="colloquium-toc colloquium-toc--has-current">' in sections[3]
        assert '<li class="colloquium-toc-item done"><a href="#2">' in sections[3]
        assert '<li class="colloquium-toc-item current"><a href="#3">Adoption</a></li>' in sections[3]

    def test_unnumbered_option(self):
        html = build_deck(self._deck(toc="```toc\nnumbered: false\n```"))

        assert '<ul class="colloquium-toc">' in html
        assert '<ol class="colloquium-toc"' not in html

    def test_renders_nothing_without_chapters(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Outline", content="```toc\n```")

        section = _slide_sections(build_deck(deck))[0]

        assert "colloquium-toc" not in section
        assert "language-toc" not in section


class TestMultiLineTitles:
    def test_title_lines_break_in_the_heading(self):
        deck = Deck(title="Test")
        deck.add_slide(title="How are open models built?\nThe role of distillation", content="Body")
        html = build_deck(deck)
        assert "<h2>How are open models built?<br>The role of distillation</h2>" in html

    def test_chapters_and_toc_read_the_title_as_one_line(self):
        deck = Deck(title="Test")
        deck.add_slide(title="Deck", layout="title")
        deck.add_slide(title="Outline", content="```toc\n```")
        deck.add_slide(title="How are open models built?\nThe role of distillation", layout="section-break")
        html = build_deck(deck)
        assert ">How are open models built? The role of distillation</a>" in html
        assert "built?The role" not in html


class TestBulletsTrailingBlocks:
    def _section(self, html: str) -> str:
        return html.split("<section", 1)[1].split("</section>", 1)[0]

    def test_paragraph_after_animated_list_becomes_the_last_fragment(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S", content="Intro line.\n\n- One\n- Two\n\nTakeaway line.", animate="bullets")
        section = self._section(build_deck(deck))
        assert '<p>Intro line.</p>' in section
        assert section.index("Intro line.") < section.index('data-fragment-index="1"')
        assert '<div class="fragment" data-fragment-index="3"><p>Takeaway line.</p></div>' in section
        assert 'data-fragment-count="3"' in section

    def test_intro_before_the_list_stays_visible(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S", content="Intro line.\n\n- One\n- Two", animate="bullets")
        section = self._section(build_deck(deck))
        assert "<p>Intro line.</p>" in section
        assert 'data-fragment-count="2"' in section

    def test_columns_only_affect_the_column_with_the_list(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S", content="Left stays.\n\n|||\n\n- One\n- Two\n\nRight tail.", classes=["cols-2"], animate="bullets")
        section = self._section(build_deck(deck))
        assert "<p>Left stays.</p>" in section
        assert '<div class="fragment" data-fragment-index="3"><p>Right tail.</p></div>' in section

    def test_explicit_step_after_list_is_unchanged(self):
        deck = Deck(title="Test")
        deck.add_slide(title="S", content="- One\n- Two\n\n<!-- step -->\n\nConclusion.", animate="bullets")
        section = self._section(build_deck(deck))
        assert 'data-fragment-count="3"' in section
        assert section.count("Conclusion.") == 1


class TestFigureTitle:
    SVG = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100">'
        '<title id="p-title">Old title</title>'
        '<text x="10" y="20" data-role="title">Old title that</text>'
        '<text x="10" y="40" data-role="title">wrapped</text>'
        '<text x="10" y="60" data-role="subtitle">Sub</text>'
        '<circle r="2"><title>point</title></circle></svg>'
    )

    def _build(self, tmp_path, markdown, svg=SVG):
        import base64
        (tmp_path / "plot.svg").write_text(svg, encoding="utf-8")
        source = tmp_path / "slides.md"
        source.write_text(markdown, encoding="utf-8")
        html = Path(build_file(str(source))).read_text(encoding="utf-8")
        match = re.search(r'<img[^>]*src="data:image/svg\+xml;base64,([^"]+)"', html)
        return html, (base64.b64decode(match.group(1)).decode("utf-8") if match else None)

    def test_heading_replaces_the_exported_title_and_keeps_hover_path(self, tmp_path):
        html, svg = self._build(tmp_path, "<!-- figure-title: heading -->\n## Downloads are **up**!\n\n![Old title](plot.svg)")
        assert svg is not None
        assert svg.count('data-role="title"') == 1
        assert '<text x="10" y="20" data-role="title">Downloads are up!</text>' in svg
        assert '<title id="p-title">Downloads are up!</title>' in svg
        assert '<text x="10" y="60" data-role="subtitle">Sub</text>' in svg
        assert '<circle r="2"><title>point</title></circle>' in svg
        assert 'data-plot="plot.svg"' in html
        assert "title-hidden" in re.search(r'<section class="([^"]*)"', html).group(1)
        assert "<h2>Downloads are <strong>up</strong>!</h2>" in html

    def test_only_the_document_title_is_replaced_and_percent_encoded_paths_open(self, tmp_path):
        tooltip_only = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<text data-role="title">Old</text>'
            '<circle r="2"><title>point tooltip</title></circle></svg>'
        )
        (tmp_path / "my plot.svg").write_text(tooltip_only, encoding="utf-8")
        html, _ = self._build(tmp_path, "<!-- figure-title: heading -->\n## New\n\n![Old](<my plot.svg>)")
        import base64
        match = re.search(r'src="data:image/svg\+xml;base64,([^"]+)"[^>]*data-plot="my%20plot.svg"', html)
        assert match, html
        svg = base64.b64decode(match.group(1)).decode("utf-8")
        assert '<text data-role="title">New</text>' in svg
        assert "<title>point tooltip</title>" in svg

    def test_programmatic_slides_and_serialization_keep_the_directive(self, tmp_path):
        from colloquium.parse import parse_markdown
        deck = parse_markdown("<!-- figure-title: heading -->\n## New\n\n![Old](plot.svg)")
        assert deck.slides[0].metadata["figure_title"] == "heading"
        assert "title-hidden" not in deck.slides[0].classes
        assert "<!-- figure-title: heading -->" in deck.slides[0].to_markdown()
        again = parse_markdown(deck.to_markdown())
        assert again.slides[0].metadata["figure_title"] == "heading"

        (tmp_path / "plot.svg").write_text(self.SVG, encoding="utf-8")
        api = Deck(title="t", source_dir=str(tmp_path))
        api.add_slide(title="New", content="![Old](plot.svg)", figure_title="heading")
        html = build_deck(api)
        assert "title-hidden" in re.search(r'<section class="([^"]*)"', html).group(1)
        assert 'data-plot="plot.svg"' in html

    def test_without_the_directive_or_a_title_role_the_figure_is_untouched(self, tmp_path):
        html, svg = self._build(tmp_path, "## Heading\n\n![Old title](plot.svg)")
        assert svg is None and 'src="plot.svg"' in html
        html, svg = self._build(tmp_path, "<!-- figure-title: heading -->\n## Heading\n\n![Old](plot.svg)", svg='<svg xmlns="http://www.w3.org/2000/svg"><text>Old</text></svg>')
        assert svg is None and 'src="plot.svg"' in html
        html, svg = self._build(tmp_path, "<!-- figure-title: heading -->\n## Heading\n\n![Missing](missing.svg)")
        assert svg is None and 'src="missing.svg"' in html
