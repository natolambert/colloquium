"""HTML builder — converts a Deck into a self-contained HTML file."""

from __future__ import annotations

import re
from pathlib import Path
from string import Template

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

from colloquium.deck import Deck
from colloquium.slide import Slide


def _get_theme_path(theme: str = "default") -> Path:
    """Get the path to a theme directory."""
    themes_dir = Path(__file__).parent / "themes" / theme
    if not themes_dir.exists():
        themes_dir = Path(__file__).parent / "themes" / "default"
    return themes_dir


def _read_theme_css(theme: str = "default") -> str:
    """Read the theme CSS file."""
    return (_get_theme_path(theme) / "theme.css").read_text(encoding="utf-8")


def _read_presentation_js(theme: str = "default") -> str:
    """Read the presentation JS file."""
    return (_get_theme_path(theme) / "presentation.js").read_text(encoding="utf-8")


def _create_md_renderer() -> MarkdownIt:
    """Create a markdown-it renderer with math and table support."""
    md = MarkdownIt("commonmark", {"html": True, "typographer": True})
    md.enable("table")
    dollarmath_plugin(md, double_inline=True)
    return md


def _render_markdown(text: str, md: MarkdownIt) -> str:
    """Render markdown text to HTML."""
    if not text:
        return ""
    return md.render(text)


_IMAGE_URL_RE = re.compile(r"\.(png|jpg|jpeg|gif|svg|webp)$|^https?://", re.IGNORECASE)


def _build_footer_html(footer: dict | None, index: int, total: int) -> str:
    """Build the three-zone footer HTML for a slide."""
    if footer is None:
        footer = {"right": "auto"}

    zones = []
    for zone in ("left", "center", "right"):
        value = footer.get(zone, "")
        inner = ""
        if value == "auto":
            inner = f'<span class="colloquium-counter">{index + 1} / {total}</span>'
        elif value and _IMAGE_URL_RE.search(value):
            inner = f'<img class="colloquium-footer-logo" src="{value}" alt="">'
        elif value:
            inner = value
        zones.append(f'<div class="colloquium-footer-{zone}">{inner}</div>')

    return f'<div class="colloquium-footer">{"".join(zones)}</div>'


def _build_slide_html(slide: Slide, index: int, total: int, md: MarkdownIt, footer: dict | None) -> str:
    """Build the HTML for a single slide."""
    # CSS classes
    classes = ["slide", f"slide--{slide.layout}"]
    if index == 0:
        classes.append("active")
    classes.extend(slide.classes)

    class_str = " ".join(classes)

    # Style attribute
    style_attr = f' style="{slide.style}"' if slide.style else ""

    # Slide content
    parts = []
    if slide.title:
        tag = "h1" if slide.is_title_slide else "h2"
        parts.append(f"<{tag}>{slide.title}</{tag}>")

    has_columns = any(c.startswith("cols-") for c in slide.classes)

    if slide.content:
        rendered = _render_markdown(slide.content, md)
        if has_columns:
            # Split content at <hr> tags into column divs
            col_parts = re.split(r"<hr\s*/?>", rendered)
            rendered = "".join(
                f'<div class="col">{p.strip()}</div>' for p in col_parts if p.strip()
            )
        parts.append(f'<div class="slide-content">{rendered}</div>')

    parts.append(_build_footer_html(footer, index, total))

    inner = "\n".join(parts)

    return f'<section class="{class_str}"{style_attr} data-index="{index}">\n{inner}\n</section>'


# HTML template — uses $-style substitution
_HTML_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>

<!-- KaTeX for LaTeX math -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/contrib/auto-render.min.js"></script>

<!-- highlight.js for code syntax highlighting -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/styles/github.min.css">
<script defer src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/highlight.min.js"></script>

<style>
$theme_css
$custom_css
</style>
</head>
<body>
<div class="colloquium-deck">
$slides_html
</div>

<div class="colloquium-progress">
    <div class="colloquium-progress-bar" style="width: 0%"></div>
</div>

<script>
$presentation_js
</script>

<script>
// Initialize KaTeX and highlight.js after all deferred scripts have loaded
window.addEventListener("load", function() {
    if (typeof renderMathInElement !== "undefined") {
        renderMathInElement(document.body, {
            delimiters: [
                {left: "$$$$", right: "$$$$", display: true},
                {left: "$$", right: "$$", display: false},
                {left: "\\\\(", right: "\\\\)", display: false},
                {left: "\\\\[", right: "\\\\]", display: true}
            ],
            throwOnError: false
        });
    }
    if (typeof hljs !== "undefined") {
        hljs.highlightAll();
    }
});
</script>
</body>
</html>
""")


def _build_font_css(fonts: dict | None) -> str:
    """Build CSS for custom font overrides, including Google Fonts @import."""
    if not fonts:
        return ""
    parts = []
    imports = []
    overrides = []
    for key, prop in (("heading", "--colloquium-font-heading"), ("body", "--colloquium-font-body")):
        name = fonts.get(key)
        if not name:
            continue
        # Google Fonts URL: spaces become +
        imports.append(name.replace(" ", "+"))
        overrides.append(f'    {prop}: "{name}", sans-serif;')
    if imports:
        families = "&family=".join(f"{f}:wght@400;600;700" for f in imports)
        parts.append(f'@import url("https://fonts.googleapis.com/css2?family={families}&display=swap");')
    if overrides:
        parts.append(":root {\n" + "\n".join(overrides) + "\n}")
    return "\n".join(parts)


def build_deck(deck: Deck) -> str:
    """Build a Deck into a self-contained HTML string."""
    md = _create_md_renderer()
    theme_css = _read_theme_css(deck.theme)
    presentation_js = _read_presentation_js(deck.theme)

    font_css = _build_font_css(deck.fonts)
    custom_css = font_css + ("\n" + deck.custom_css if deck.custom_css else "")

    total = len(deck.slides)
    slides_html_parts = []
    for i, slide in enumerate(deck.slides):
        slides_html_parts.append(_build_slide_html(slide, i, total, md, deck.footer))

    slides_html = "\n\n".join(slides_html_parts)

    return _HTML_TEMPLATE.substitute(
        title=deck.title,
        theme_css=theme_css,
        custom_css=custom_css,
        slides_html=slides_html,
        presentation_js=presentation_js,
    )


def build_file(input_path: str, output_path: str | None = None) -> str:
    """Build a markdown file into an HTML file. Returns the output path."""
    from colloquium.parse import parse_file

    deck = parse_file(input_path)
    html = build_deck(deck)

    if output_path is None:
        output_path = str(Path(input_path).with_suffix(".html"))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    return output_path
