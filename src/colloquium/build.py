"""HTML builder — converts a Deck into a self-contained HTML file."""

from __future__ import annotations

import html as html_module
import json
import re
from pathlib import Path
from string import Template

import yaml
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
    """Create a markdown-it renderer with math and table support.

    The dollarmath plugin protects $...$ and $$...$$ from markdown
    processing (e.g. _ becoming <em>). KaTeX renders the resulting
    .math elements client-side.
    """
    md = MarkdownIt("commonmark", {"html": True, "typographer": True})
    md.enable("table")
    dollarmath_plugin(md, double_inline=True)
    return md


def _render_markdown(text: str, md: MarkdownIt) -> str:
    """Render markdown text to HTML."""
    if not text:
        return ""
    rendered = md.render(text)
    rendered = _process_charts(rendered)
    return rendered


# Chart block pattern: <pre><code class="language-chart">YAML</code></pre>
_CHART_BLOCK_RE = re.compile(
    r'<pre><code class="language-chart">(.*?)</code></pre>',
    re.DOTALL,
)

_chart_counter = 0


def _build_chart_html(yaml_str: str) -> str:
    """Convert a YAML chart spec to a <canvas> + JSON config."""
    global _chart_counter
    _chart_counter += 1
    chart_id = f"colloquium-chart-{_chart_counter}"

    raw = html_module.unescape(yaml_str.strip())
    try:
        spec = yaml.safe_load(raw)
    except yaml.YAMLError:
        return f'<p style="color:red">Invalid chart YAML</p>'

    if not isinstance(spec, dict):
        return f'<p style="color:red">Chart spec must be a YAML mapping</p>'

    chart_type = spec.get("type", "bar")
    data = spec.get("data", {})
    title = spec.get("title", "")
    options = spec.get("options", {})

    # Build Chart.js config
    datasets = []
    colors = [
        "#0f3460", "#e94560", "#16213e", "#0ea5e9",
        "#10b981", "#f59e0b", "#8b5cf6", "#ec4899",
    ]
    for i, ds in enumerate(data.get("datasets", [])):
        dataset = {
            "label": ds.get("label", f"Series {i+1}"),
            "data": ds.get("data", []),
            "borderColor": ds.get("color", colors[i % len(colors)]),
            "backgroundColor": ds.get("color", colors[i % len(colors)]),
        }
        if chart_type in ("line", "scatter"):
            dataset["backgroundColor"] = "transparent"
            dataset["borderWidth"] = 2.5
            dataset["pointRadius"] = 3
            dataset["tension"] = 0.3
        elif chart_type in ("bar",):
            dataset["backgroundColor"] = ds.get("color", colors[i % len(colors)]) + "cc"
        datasets.append(dataset)

    chart_options = {
        "responsive": True,
        "maintainAspectRatio": False,
        "plugins": {
            "legend": {"display": len(datasets) > 1},
            "title": {"display": bool(title), "text": title, "font": {"size": 16}},
        },
    }
    # Deep-merge user options
    for key, value in options.items():
        if key in chart_options and isinstance(chart_options[key], dict) and isinstance(value, dict):
            chart_options[key].update(value)
        else:
            chart_options[key] = value

    config = {
        "type": chart_type,
        "data": {
            "labels": data.get("labels", []),
            "datasets": datasets,
        },
        "options": chart_options,
    }

    config_json = json.dumps(config)
    return (
        f'<div class="colloquium-chart-container">'
        f'<canvas id="{chart_id}" data-chart-config=\'{config_json}\'></canvas>'
        f'</div>'
    )


def _process_charts(html_str: str) -> str:
    """Replace chart code blocks with canvas elements."""
    return _CHART_BLOCK_RE.sub(lambda m: _build_chart_html(m.group(1)), html_str)


_IMAGE_URL_RE = re.compile(r"\.(png|jpg|jpeg|gif|svg|webp)$|^https?://", re.IGNORECASE)


def _build_footer_html(footer: dict | None, index: int, total: int) -> str:
    """Build the three-zone footer HTML for a slide."""
    if footer is None:
        footer = {"right": "auto"}

    logo_scale = footer.get("logo_scale", 1)
    logo_height = int(24 * float(logo_scale))

    zones = []
    for zone in ("left", "center", "right"):
        value = footer.get(zone, "")
        inner = ""
        if value == "auto":
            inner = f'<span class="colloquium-counter">{index + 1} / {total}</span>'
        elif value and _IMAGE_URL_RE.search(value):
            inner = f'<img class="colloquium-footer-logo" src="{value}" alt="" style="height: {logo_height}px">'
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

<!-- Chart.js for inline charts -->
<script defer src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>

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

<button class="colloquium-present" title="Present (F)">&#9654;</button>

<div class="colloquium-progress">
    <div class="colloquium-progress-bar" style="width: 0%"></div>
</div>

<script>
$presentation_js
</script>

<script>
// Render KaTeX math elements and highlight code after deferred scripts load
window.addEventListener("load", function() {
    if (typeof katex !== "undefined") {
        document.querySelectorAll(".math").forEach(function(el) {
            var displayMode = el.tagName === "DIV";
            katex.render(el.textContent, el, {
                displayMode: displayMode,
                throwOnError: false
            });
        });
    }
    if (typeof hljs !== "undefined") {
        hljs.highlightAll();
    }
    // Initialize Chart.js charts
    if (typeof Chart !== "undefined") {
        document.querySelectorAll("[data-chart-config]").forEach(function(canvas) {
            var config = JSON.parse(canvas.getAttribute("data-chart-config"));
            new Chart(canvas, config);
        });
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
    global _chart_counter
    _chart_counter = 0
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
