"""Figure columns: image-plus-caption cells fit their column; img-tall-right follows the columns ratio."""

from colloquium.build import build_deck
from colloquium.deck import Deck


def _build(content: str, classes: list[str], style: str = "") -> str:
    deck = Deck(title="Test")
    deck.add_slide(title="Slide", content=content, classes=classes, style=style)
    return build_deck(deck)


class TestColumnTracksOnSlide:
    def test_columns_emit_their_tracks_on_the_slide(self):
        html = _build("Wide\n\n|||\n\nNarrow", ["cols-60-40"])
        assert 'style="--colloquium-columns: minmax(0, 60fr) minmax(0, 40fr);" data-index=' in html
        assert 'style="grid-template-columns: minmax(0, 60fr) minmax(0, 40fr);"' in html

    def test_equal_columns_emit_repeat_tracks(self):
        html = _build("A\n\n|||\n\nB\n\n|||\n\nC", ["cols-3"])
        assert 'style="--colloquium-columns: repeat(3, minmax(0, 1fr));" data-index=' in html

    def test_tracks_follow_an_authored_slide_style(self):
        html = _build("Wide\n\n|||\n\nNarrow", ["cols-40-60"], style="background: #fff")
        assert 'style="background: #fff; --colloquium-columns: minmax(0, 40fr) minmax(0, 60fr);"' in html

    def test_slides_without_columns_keep_their_plain_style(self):
        html = _build("Just text", [], style="background: #fff")
        assert 'style="background: #fff" data-index=' in html
        assert "--colloquium-columns" not in html.split("<section", 1)[1].split(">", 1)[0]


class TestFigureColumnTheme:
    def test_image_and_caption_cells_lay_out_as_flex_figure_columns(self):
        html = _build("Text\n\n|||\n\n![A chart](chart.png)\n\n*Caption*", ["cols-60-40"])
        tail = ":has(> p:not(:first-child)):not(:has(> :not(:first-child):not(p)))"
        bare = f".slide .colloquium-grid > .col:has(> img:first-child){tail}"
        wrapped = f".slide .colloquium-grid > .col:has(> p:first-child > img:only-child){tail}"
        # Whole selectors sit in :where() so any deck rule outranks them.
        assert f":where({bare})," in html
        assert f":where({wrapped} > p:first-child)," in html
        assert f":where({bare} > img:first-child)," in html
        assert f":where(.slide.img-valign-bottom .colloquium-grid > .col:has(> img:first-child){tail})," in html

    def test_figure_column_rules_have_zero_specificity(self):
        import pathlib
        import re
        css = pathlib.Path("colloquium/themes/default/theme.css").read_text()
        block = css[css.index("/* ===== Figure columns ====="):css.index(".img-overflow .colloquium-grid > .col,")]
        block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
        selectors = [line.strip() for line in re.findall(r"^(.+?)(?:,|\s\{)$", block, re.M)]
        assert selectors
        for selector in selectors:
            assert selector.startswith(":where(") and selector.endswith(")"), selector

    def test_figure_column_selectors_never_nest_has(self):
        import pathlib
        import re
        css = pathlib.Path("colloquium/themes/default/theme.css").read_text()
        for match in re.finditer(r":has\(", css):
            depth, i = 1, match.end()
            while i < len(css) and depth:
                depth += {"(": 1, ")": -1}.get(css[i], 0)
                i += 1
            assert ":has(" not in css[match.end():i - 1], css[match.start():i]

    def test_tall_right_uses_the_slide_grid_instead_of_a_fixed_width(self):
        html = _build("Text\n\n|||\n\n![Caption](figure.png)", ["cols-60-40", "img-tall-right", "figure-captions"])
        assert "grid-template-columns: var(--colloquium-columns, minmax(0, 1fr) minmax(0, 1fr));" in html
        assert ".slide.img-tall-right > .slide-content.colloquium-grid { display: contents; }" in html
        assert ".slide.img-tall-right { display: grid !important; }" in html
        assert "width: 55%" not in html
