"""HTML builder — converts a Deck into a self-contained HTML file."""

from __future__ import annotations

import html as html_module
import re
from pathlib import Path
from string import Template

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

from colloquium import elements
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
    rendered = elements.process_all(rendered)
    return rendered


# ===== Citation processing =====

_CITATION_RE = re.compile(r'\[@([\w:.\-]+(?:\s*;\s*@[\w:.\-]+)*)\]')


def _parse_bib_file(path: str) -> dict:
    """Parse a .bib file using pybtex. Returns dict of key -> entry."""
    try:
        from pybtex.database import parse_file as pybtex_parse
        bib = pybtex_parse(path, bib_format="bibtex")
        return dict(bib.entries)
    except Exception:
        return {}


def _get_author_surname(entry) -> str:
    """Extract the first author's surname from a pybtex entry."""
    try:
        persons = entry.persons.get("author", [])
        if not persons:
            return "Unknown"
        first = persons[0]
        surnames = first.last_names
        if surnames:
            return surnames[0]
        return str(first)
    except Exception:
        return "Unknown"


def _get_year(entry) -> str:
    """Extract year from a pybtex entry."""
    return entry.fields.get("year", "n.d.")


def _get_title(entry) -> str:
    """Extract title from a pybtex entry."""
    return entry.fields.get("title", "Untitled").strip("{}")


def _format_citation_label(entry, key: str, style: str, number: int) -> str:
    """Format the inline citation label based on style."""
    if style == "numeric":
        return str(number)
    elif style == "title-year":
        title = _get_title(entry)
        # Shorten long titles
        if len(title) > 30:
            title = title[:27] + "..."
        return f"{title}, {_get_year(entry)}"
    else:  # author-year (default)
        surname = _get_author_surname(entry)
        authors = entry.persons.get("author", [])
        if len(authors) > 2:
            surname += " et al."
        elif len(authors) == 2:
            second = authors[1].last_names
            if second:
                surname += f" & {second[0]}"
        return f"{surname}, {_get_year(entry)}"


def _process_citations(html: str, bib_entries: dict, style: str, cited_keys: list) -> str:
    """Replace [@key] with citation links. Tracks cited keys."""
    key_numbers = {}

    def _replace(m):
        raw = m.group(1)
        keys = [k.strip().lstrip("@") for k in raw.split(";")]
        parts = []
        for key in keys:
            if key in bib_entries:
                if key not in key_numbers:
                    key_numbers[key] = len(key_numbers) + 1
                    if key not in cited_keys:
                        cited_keys.append(key)
                entry = bib_entries[key]
                label = _format_citation_label(entry, key, style, key_numbers[key])
                css_class = "colloquium-cite"
                if style == "numeric":
                    label = f"[{label}]"
                else:
                    label = f"({label})"
                parts.append(
                    f'<a href="#colloquium-ref-{html_module.escape(key)}" '
                    f'class="{css_class}">{html_module.escape(label)}</a>'
                )
            else:
                parts.append(
                    f'<span class="colloquium-cite colloquium-cite-missing">[{html_module.escape(key)}?]</span>'
                )
                if key not in cited_keys:
                    cited_keys.append(key)
        return " ".join(parts)

    return _CITATION_RE.sub(_replace, html)


def _format_reference(entry, key: str, style: str, number: int) -> str:
    """Format a single reference entry for the references slide.

    Style: Authors. "Title." *Venue*, Year.
    """
    authors = entry.persons.get("author", [])
    author_strs = []
    for person in authors:
        surnames = " ".join(person.last_names)
        firsts = " ".join(n[0] + "." for n in person.first_names if n) if person.first_names else ""
        if firsts:
            author_strs.append(f"{surnames}, {firsts}")
        else:
            author_strs.append(surnames)

    # Truncate long author lists
    if len(author_strs) > 5:
        author_line = ", ".join(author_strs[:5]) + ", et al."
    elif len(author_strs) > 1:
        author_line = ", ".join(author_strs[:-1]) + ", and " + author_strs[-1]
    elif author_strs:
        author_line = author_strs[0]
    else:
        author_line = "Unknown"

    title = _get_title(entry)
    year = _get_year(entry)
    venue = entry.fields.get("journal", entry.fields.get("booktitle", entry.fields.get("publisher", "")))
    venue = venue.strip("{}")
    url = entry.fields.get("url", "").strip("{}")

    prefix = f"[{number}] " if style == "numeric" else ""

    # Build: Authors. "Title." Venue, Year.
    parts = [f'{prefix}{html_module.escape(author_line)}.']
    parts.append(f' &ldquo;<em>{html_module.escape(title)}</em>.&rdquo;')
    if venue:
        parts.append(f' <em>{html_module.escape(venue)}</em>,')
    parts.append(f' {html_module.escape(year)}.')

    ref_text = "".join(parts)

    if url:
        ref_text += f' <a href="{html_module.escape(url)}" class="colloquium-ref-url">[link]</a>'

    return (
        f'<div class="colloquium-reference" id="colloquium-ref-{html_module.escape(key)}">'
        f'{ref_text}'
        f'</div>'
    )


# Line budget for reference pagination.
# Slide is 720px tall.  Usable area for references (below h2, above footer):
#   720 - 60 (top pad) - 80 (heading+gap) - 50 (footer zone) ≈ 530px.
# References render at 0.75em of 24px base = 18px, line-height 1.5 = 27px.
# Each ref also has margin-bottom: 0.6em ≈ 11px, so a 2-line ref costs
#   2*27 + 11 = 65px and a 3-line ref costs 3*27 + 11 = 92px.
# We express the budget in px for accuracy.
_REF_PX_BUDGET = 530
_REF_LINE_HEIGHT_PX = 27
_REF_MARGIN_PX = 11
# Characters per rendered line.  The content area is ~1140px wide (1280 - 2*60
# padding - 2em hanging indent ≈ 36px).  At 18px font, average char width is
# ~9px for the proportional body font, giving ~127 chars.  We use 120 to
# account for italic text being slightly wider.
_REF_CHARS_PER_LINE = 120


def _estimate_ref_px(ref_html: str) -> int:
    """Estimate pixel height of a formatted reference."""
    import re as _re
    plain = _re.sub(r"<[^>]+>", "", ref_html)
    plain = html_module.unescape(plain)
    text_lines = max(1, -(-len(plain) // _REF_CHARS_PER_LINE))  # ceil division
    return text_lines * _REF_LINE_HEIGHT_PX + _REF_MARGIN_PX


def _paginate_refs(refs: list[str]) -> list[list[str]]:
    """Split refs into pages based on estimated pixel height."""
    pages: list[list[str]] = []
    current_page: list[str] = []
    current_px = 0

    for ref in refs:
        px = _estimate_ref_px(ref)
        # Start a new page if this ref would exceed the budget,
        # unless the current page is empty (always fit at least one).
        if current_page and current_px + px > _REF_PX_BUDGET:
            pages.append(current_page)
            current_page = []
            current_px = 0
        current_page.append(ref)
        current_px += px

    if current_page:
        pages.append(current_page)

    return pages


def _count_references_slides(cited_keys: list, bib_entries: dict) -> int:
    """Return how many slides the references will need."""
    refs = []
    for i, key in enumerate(cited_keys):
        if key in bib_entries:
            refs.append(_format_reference(bib_entries[key], key, "author-year", i + 1))
    if not refs:
        return 0
    return len(_paginate_refs(refs))


def _build_references_slides_html(
    bib_entries: dict, cited_keys: list, style: str,
    start_index: int, total: int, footer: dict | None,
) -> list[str]:
    """Generate one or more References <section> elements, paginated."""
    refs = []
    for i, key in enumerate(cited_keys):
        if key in bib_entries:
            refs.append(_format_reference(bib_entries[key], key, style, i + 1))

    if not refs:
        return []

    pages = _paginate_refs(refs)
    slides = []
    for page_num, chunk in enumerate(pages):
        slide_index = start_index + page_num
        refs_html = "\n".join(chunk)

        heading = "References"
        if len(pages) > 1:
            heading = f"References ({page_num + 1}/{len(pages)})"

        content = (
            f'<h2>{heading}</h2>\n'
            f'<div class="slide-content colloquium-references-slide">{refs_html}</div>\n'
            f'{_build_footer_html(footer, slide_index, total)}'
        )

        classes = "slide slide--content"
        slides.append(
            f'<section class="{classes}" data-index="{slide_index}">\n{content}\n</section>'
        )

    return slides


_IMAGE_URL_RE = re.compile(r"\.(png|jpg|jpeg|gif|svg|webp)$|^https?://", re.IGNORECASE)


def _build_footer_html(footer: dict | None, index: int, total: int) -> str:
    """Build the three-zone footer HTML for a slide."""
    if footer is None:
        footer = {"right": "auto"}

    # Support {n} (current slide) and {N} (total) placeholders in footer text
    counter_html = f'<span class="colloquium-counter">{index + 1} / {total}</span>'
    has_counter = any(
        footer.get(z) == "auto" or "{n}" in str(footer.get(z, "")) or "{N}" in str(footer.get(z, ""))
        for z in ("left", "center", "right")
    )
    # Auto-inject counter into first empty zone if no zone references it
    if not has_counter:
        for z in ("center", "right", "left"):
            if not footer.get(z):
                footer = {**footer, z: "auto"}
                break

    logo_scale = footer.get("logo_scale", 1)
    logo_height = int(24 * float(logo_scale))

    zones = []
    for zone in ("left", "center", "right"):
        value = footer.get(zone, "")
        inner = ""
        if value == "auto":
            inner = counter_html
        elif value and ("{n}" in value or "{N}" in value):
            text = value.replace("{n}", str(index + 1)).replace("{N}", str(total))
            inner = f'<span class="colloquium-counter">{text}</span>'
        elif value and _IMAGE_URL_RE.search(value):
            inner = f'<img class="colloquium-footer-logo" src="{value}" alt="" style="height: {logo_height}px">'
        elif value:
            # Substitute {n} (slide number) and {N} (total slides)
            rendered = value.replace("{n}", str(index + 1)).replace("{N}", str(total))
            if "{n}" in value or "{N}" in value:
                inner = f'<span class="colloquium-counter">{rendered}</span>'
            else:
                inner = rendered
        zone_classes = [f"colloquium-footer-{zone}"]
        if zone == "right":
            zone_classes.append("colloquium-footer-nav")
        zones.append(f'<div class="{" ".join(zone_classes)}">{inner}</div>')

    return f'<div class="colloquium-footer">{"".join(zones)}</div>'


def _build_slide_cite_html(keys: list, position: str, bib_entries: dict, style: str, cited_keys: list) -> str:
    """Build a per-slide floating citation footnote."""
    if not keys or not bib_entries:
        return ""
    labels = []
    for key in keys:
        if key in bib_entries:
            entry = bib_entries[key]
            if key not in cited_keys:
                cited_keys.append(key)
            label = _format_citation_label(entry, key, style, len(cited_keys))
            labels.append(
                f'<a href="#colloquium-ref-{html_module.escape(key)}" '
                f'class="colloquium-cite">{html_module.escape(label)}</a>'
            )
    if not labels:
        return ""
    return (
        f'<div class="colloquium-slide-cite colloquium-slide-cite--{position}">'
        + "; ".join(labels)
        + '</div>'
    )


def _build_slide_html(
    slide: Slide, index: int, total: int, md: MarkdownIt,
    footer: dict | None, bib_entries: dict | None = None,
    citation_style: str = "author-year", cited_keys: list | None = None,
) -> str:
    """Build the HTML for a single slide."""
    if bib_entries is None:
        bib_entries = {}
    if cited_keys is None:
        cited_keys = []

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
            # Split content at ||| column dividers
            col_parts = re.split(r"<p>\|\|\|</p>", rendered)
            rendered = "".join(
                f'<div class="col">{p.strip()}</div>' for p in col_parts
            )
        parts.append(f'<div class="slide-content">{rendered}</div>')

    # Per-slide citation footnotes (floating above footer)
    cite_left = slide.metadata.get("cite_left", [])
    cite_right = slide.metadata.get("cite_right", [])
    if cite_left:
        parts.append(_build_slide_cite_html(cite_left, "left", bib_entries, citation_style, cited_keys))
    if cite_right:
        parts.append(_build_slide_cite_html(cite_right, "right", bib_entries, citation_style, cited_keys))

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
window.colloquiumFitDisplayMathIn = function(root) {
    var scope = root || document;
    scope.querySelectorAll(".katex-display").forEach(function(display) {
        display.style.fontSize = "";
        var katexNode = display.querySelector(".katex");
        if (!katexNode) return;

        var availableWidth = display.clientWidth;
        var contentWidth = katexNode.scrollWidth;
        if (!availableWidth || !contentWidth || contentWidth <= availableWidth) return;

        var scale = availableWidth / contentWidth;
        display.style.fontSize = (scale * 100) + "%";
    });
};

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
        window.colloquiumFitDisplayMathIn(document);
        if (document.fonts && document.fonts.ready) {
            document.fonts.ready.then(function() {
                window.colloquiumFitDisplayMathIn(document);
            });
        }
    }
    if (typeof hljs !== "undefined") {
        hljs.highlightAll();
    }
    // Initialize Chart.js charts — temporarily show all slides so canvases
    // have dimensions, render charts, capture static print images, then restore.
    if (typeof Chart !== "undefined") {
        var chartCanvases = document.querySelectorAll("[data-chart-config]");
        if (chartCanvases.length > 0) {
            // Make all slides visible so Chart.js can measure canvas size
            // Use visibility:hidden to avoid a visual flash
            var slides = document.querySelectorAll(".slide");
            var origDisplay = [];
            slides.forEach(function(s) {
                origDisplay.push(s.style.display);
                s.style.display = "flex";
                if (!s.classList.contains("active")) {
                    s.style.visibility = "hidden";
                }
            });

            chartCanvases.forEach(function(canvas) {
                var config = JSON.parse(canvas.getAttribute("data-chart-config"));
                // Convert tick prefix/suffix strings into real callbacks
                var scales = config.options && config.options.scales;
                if (scales) {
                    Object.keys(scales).forEach(function(axis) {
                        var ticks = scales[axis].ticks;
                        if (!ticks) return;
                        var pre = ticks.prefix || "";
                        var suf = ticks.suffix || "";
                        if (pre || suf) {
                            delete ticks.prefix;
                            delete ticks.suffix;
                            ticks.callback = function(v) { return pre + v + suf; };
                        }
                    });
                }
                new Chart(canvas, config);
            });

            // After a frame, capture each chart as a static image for print
            requestAnimationFrame(function() {
                chartCanvases.forEach(function(canvas) {
                    try {
                        var img = document.createElement("img");
                        img.src = canvas.toDataURL("image/png");
                        img.className = "colloquium-chart-print";
                        canvas.parentNode.insertBefore(img, canvas.nextSibling);
                    } catch(e) {}
                });
                // Restore original slide visibility
                slides.forEach(function(s, i) {
                    s.style.display = origDisplay[i];
                    s.style.visibility = "";
                });
            });
        }
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
    elements.reset()
    md = _create_md_renderer()
    theme_css = _read_theme_css(deck.theme)
    presentation_js = _read_presentation_js(deck.theme)

    font_css = _build_font_css(deck.fonts)
    custom_css = font_css + ("\n" + deck.custom_css if deck.custom_css else "")

    # Load bibliography if configured
    bib_entries = {}
    if deck.bibliography:
        bib_entries = _parse_bib_file(deck.bibliography)

    citation_style = deck.citation_style

    # First pass: build slides and discover cited keys
    cited_keys: list[str] = []
    total = len(deck.slides)

    # If we have bib entries, we need a two-pass approach:
    # first discover citations, then rebuild with correct total (including references slide)
    if bib_entries:
        # Discovery pass — render slides to find cited keys
        for slide in deck.slides:
            if slide.content:
                rendered = _render_markdown(slide.content, md)
                _process_citations(rendered, bib_entries, citation_style, cited_keys)
            if slide.title:
                _process_citations(slide.title, bib_entries, citation_style, cited_keys)
            # Also discover keys from per-slide cite directives
            for key in slide.metadata.get("cite_left", []) + slide.metadata.get("cite_right", []):
                if key not in cited_keys and key in bib_entries:
                    cited_keys.append(key)

        # Add reference slides to total count
        ref_slide_count = _count_references_slides(cited_keys, bib_entries)
        if ref_slide_count:
            total = len(deck.slides) + ref_slide_count

        # Reset counters for the real build pass
        elements.reset()

    slides_html_parts = []
    for i, slide in enumerate(deck.slides):
        slide_html = _build_slide_html(
            slide, i, total, md, deck.footer,
            bib_entries=bib_entries, citation_style=citation_style, cited_keys=cited_keys,
        )
        if bib_entries:
            slide_html = _process_citations(slide_html, bib_entries, citation_style, cited_keys)
        slides_html_parts.append(slide_html)

    # Append references slides if we have citations
    if bib_entries and cited_keys:
        ref_slides = _build_references_slides_html(
            bib_entries, cited_keys, citation_style,
            len(deck.slides), total, deck.footer,
        )
        slides_html_parts.extend(ref_slides)

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
