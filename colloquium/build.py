"""HTML builder — converts a Deck into a self-contained HTML file."""

from __future__ import annotations

import html as html_module
import re
import tempfile
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
    md.enable(["table", "replacements", "smartquotes"])
    dollarmath_plugin(md, double_inline=True)
    return md


def _render_markdown(text: str, md: MarkdownIt) -> str:
    """Render markdown text to HTML."""
    if not text:
        return ""
    rendered = md.render(text)
    rendered = elements.process_all(rendered)
    return rendered


def _render_inline_markdown(text: str, md: MarkdownIt) -> str:
    """Render inline markdown text to HTML."""
    if not text:
        return ""
    rendered = md.renderInline(text)
    rendered = elements.process_all(rendered)
    return rendered


_STANDALONE_IMAGE_PARAGRAPH_RE = re.compile(r"<p>\s*(<img\b[^>]*>)\s*</p>", re.DOTALL)
_IMAGE_ALT_ATTR_RE = re.compile(r'\balt="([^"]*)"')


def _render_figure_captions(rendered: str, md: MarkdownIt) -> str:
    """Convert standalone image paragraphs into figure/caption markup."""

    def _replace(match: re.Match[str]) -> str:
        image_html = match.group(1)
        alt_match = _IMAGE_ALT_ATTR_RE.search(image_html)
        alt_text = html_module.unescape(alt_match.group(1)).strip() if alt_match else ""
        caption_html = _render_inline_markdown(alt_text, md).strip() if alt_text else ""
        if not caption_html:
            return match.group(0)
        return (
            '<figure class="colloquium-figure">'
            f"{image_html}"
            f'<figcaption class="colloquium-figure-caption">{caption_html}</figcaption>'
            "</figure>"
        )

    return _STANDALONE_IMAGE_PARAGRAPH_RE.sub(_replace, rendered)


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


def _normalize_bibtex_field(text: str) -> str:
    """Drop plain BibTeX grouping braces while preserving LaTeX macro arguments."""
    result: list[str] = []
    preserve_stack: list[bool] = []
    preserve_next_group = False
    i = 0

    while i < len(text):
        char = text[i]

        if char == "\\":
            # Preserve control words like \textsc and control symbols like \%.
            result.append(char)
            i += 1
            if i < len(text):
                result.append(text[i])
                if text[i].isalpha():
                    i += 1
                    while i < len(text) and text[i].isalpha():
                        result.append(text[i])
                        i += 1
                    preserve_next_group = True
                    continue
                preserve_next_group = True
            continue

        if char == "{":
            preserve_group = preserve_next_group or (preserve_stack[-1] if preserve_stack else False)
            preserve_stack.append(preserve_group)
            if preserve_group:
                result.append(char)
            preserve_next_group = False
            i += 1
            continue

        if char == "}":
            preserve_group = preserve_stack.pop() if preserve_stack else False
            if preserve_group:
                result.append(char)
            preserve_next_group = False
            i += 1
            continue

        if not char.isspace():
            preserve_next_group = False
        result.append(char)
        i += 1

    return "".join(result).strip()


def _get_title(entry) -> str:
    """Extract title from a pybtex entry."""
    return _normalize_bibtex_field(entry.fields.get("title", "Untitled"))


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


def _resolve_citation_order(style: str, citation_order: str) -> str:
    """Resolve the effective citation ordering policy."""
    if style == "numeric":
        return "appearance"
    if citation_order in {"appearance", "alphabetical"}:
        return citation_order
    return "alphabetical"


def _dedupe_keys(keys: list[str]) -> list[str]:
    """Preserve the first occurrence of each citation key."""
    unique = []
    seen = set()
    for key in keys:
        if key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def _citation_sort_key(
    key: str,
    bib_entries: dict,
    style: str,
    citation_numbers: dict[str, int] | None,
) -> tuple[int, str, str]:
    """Return a stable sort key for non-numeric citation styles."""
    if key not in bib_entries:
        return (1, key.lower(), key.lower())
    number = citation_numbers.get(key, 1) if citation_numbers else 1
    label = _format_citation_label(bib_entries[key], key, style, number)
    return (0, html_module.unescape(label).lower(), key.lower())


def _ordered_citation_keys(
    keys: list[str],
    bib_entries: dict,
    style: str,
    citation_order: str,
    citation_numbers: dict[str, int] | None = None,
) -> list[str]:
    """Return keys in appearance or alphabetical order."""
    unique = _dedupe_keys(keys)
    if _resolve_citation_order(style, citation_order) == "appearance":
        return unique
    return sorted(
        unique,
        key=lambda key: _citation_sort_key(key, bib_entries, style, citation_numbers),
    )


def _discover_citation_keys(text: str, bib_entries: dict, cited_keys: list) -> None:
    """Append cited keys in first-appearance order without rendering citations."""
    for match in _CITATION_RE.finditer(text):
        keys = [k.strip().lstrip("@") for k in match.group(1).split(";")]
        for key in keys:
            if key in bib_entries and key not in cited_keys:
                cited_keys.append(key)


def _get_citation_number(
    key: str,
    cited_keys: list[str],
    citation_numbers: dict[str, int] | None = None,
) -> int:
    """Return the numeric citation index for a key."""
    if citation_numbers and key in citation_numbers:
        return citation_numbers[key]
    if key not in cited_keys:
        cited_keys.append(key)
    return cited_keys.index(key) + 1


def _process_citations(
    html: str,
    bib_entries: dict,
    style: str,
    cited_keys: list,
    citation_order: str = "auto",
    citation_numbers: dict[str, int] | None = None,
) -> str:
    """Replace [@key] with citation links. Tracks cited keys."""
    def _replace(m):
        raw = m.group(1)
        keys = [k.strip().lstrip("@") for k in raw.split(";")]
        keys = _ordered_citation_keys(keys, bib_entries, style, citation_order, citation_numbers)
        parts = []
        for key in keys:
            if key in bib_entries:
                number = _get_citation_number(key, cited_keys, citation_numbers)
                entry = bib_entries[key]
                label = _format_citation_label(entry, key, style, number)
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
    venue = _normalize_bibtex_field(venue)
    url = _normalize_bibtex_field(entry.fields.get("url", ""))

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


def _count_references_slides(
    cited_keys: list,
    bib_entries: dict,
    style: str,
    citation_order: str,
    citation_numbers: dict[str, int] | None = None,
) -> int:
    """Return how many slides the references will need."""
    refs = []
    ordered_keys = _ordered_citation_keys(cited_keys, bib_entries, style, citation_order, citation_numbers)
    for key in ordered_keys:
        if key in bib_entries:
            number = _get_citation_number(key, cited_keys, citation_numbers)
            refs.append(_format_reference(bib_entries[key], key, style, number))
    if not refs:
        return 0
    return len(_paginate_refs(refs))


def _build_references_slides_html(
    bib_entries: dict, cited_keys: list, style: str,
    start_index: int, total: int, footer: dict | None,
    citation_order: str = "auto", citation_numbers: dict[str, int] | None = None,
) -> list[str]:
    """Generate one or more References <section> elements, paginated."""
    refs = []
    ordered_keys = _ordered_citation_keys(cited_keys, bib_entries, style, citation_order, citation_numbers)
    for key in ordered_keys:
        if key in bib_entries:
            number = _get_citation_number(key, cited_keys, citation_numbers)
            refs.append(_format_reference(bib_entries[key], key, style, number))

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


def _build_slide_cite_html(
    keys: list,
    bib_entries: dict,
    style: str,
    cited_keys: list,
    citation_order: str = "auto",
    citation_numbers: dict[str, int] | None = None,
) -> str:
    """Build per-slide citation links."""
    if not keys or not bib_entries:
        return ""
    keys = _ordered_citation_keys(keys, bib_entries, style, citation_order, citation_numbers)
    labels = []
    for key in keys:
        if key in bib_entries:
            entry = bib_entries[key]
            number = _get_citation_number(key, cited_keys, citation_numbers)
            label = _format_citation_label(entry, key, style, number)
            labels.append(
                f'<a href="#colloquium-ref-{html_module.escape(key)}" '
                f'class="colloquium-cite">{html_module.escape(label)}</a>'
            )
    if not labels:
        return ""
    return f'<div class="colloquium-slide-cite">{"; ".join(labels)}</div>'


def _extract_inline_footnotes(
    text: str,
    slide_index: int,
    position: str = "right",
) -> tuple[str, dict[str, list[dict[str, str]]]]:
    r"""Replace inline footnotes with markers and return collected footnotes.

    Footnotes can contain nested square brackets, which is common in math
    (e.g. ``\left[ ... \right]``) and citations (e.g. ``[@key]``).
    """
    notes: dict[str, list[dict[str, str]]] = {"left": [], "right": []}
    target = "left" if position == "left" else "right"

    def _build_marker(note_text: str) -> str:
        number = len(notes[target]) + 1
        note_id = f"colloquium-footnote-{slide_index + 1}-{target}-{number}"
        ref_id = f"colloquium-footnote-ref-{slide_index + 1}-{target}-{number}"
        notes[target].append(
            {
                "number": str(number),
                "text": note_text.strip(),
                "id": note_id,
                "ref_id": ref_id,
            }
        )
        return (
            f'<sup class="colloquium-footnote-ref">'
            f'<a href="#{html_module.escape(note_id)}" id="{html_module.escape(ref_id)}">{number}</a>'
            f"</sup>"
        )

    parts: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("^[", i):
            j = i + 2
            depth = 1
            while j < len(text) and depth > 0:
                if text[j] == "[":
                    depth += 1
                elif text[j] == "]":
                    depth -= 1
                j += 1

            if depth == 0:
                note_text = text[i + 2 : j - 1]
                parts.append(_build_marker(note_text))
                i = j
                continue

        parts.append(text[i])
        i += 1

    return "".join(parts), notes


def _render_footnote_text(
    text: str,
    md: MarkdownIt,
    bib_entries: dict,
    style: str,
    cited_keys: list,
    citation_order: str = "auto",
    citation_numbers: dict[str, int] | None = None,
) -> str:
    """Render inline footnote text with citation support."""
    rendered = _render_inline_markdown(text.strip(), md).strip()
    if not rendered:
        return ""
    return _process_citations(
        rendered,
        bib_entries,
        style,
        cited_keys,
        citation_order,
        citation_numbers,
    )


def _build_slide_footnote_html(
    text: str,
    inline_footnotes: list[dict[str, str]],
    md: MarkdownIt,
    bib_entries: dict,
    style: str,
    cited_keys: list,
    citation_order: str = "auto",
    citation_numbers: dict[str, int] | None = None,
) -> str:
    """Build per-slide floating footnote content."""
    parts: list[str] = []

    if inline_footnotes:
        items = []
        for note in inline_footnotes:
            rendered_text = _render_footnote_text(
                note["text"],
                md,
                bib_entries,
                style,
                cited_keys,
                citation_order,
                citation_numbers,
            )
            if not rendered_text:
                continue
            items.append(
                '<div class="colloquium-slide-footnote-item" '
                f'id="{html_module.escape(note["id"])}">'
                f'<span class="colloquium-slide-footnote-label">{html_module.escape(note["number"])}:</span> '
                f'<span class="colloquium-slide-footnote-text">{rendered_text}</span>'
                "</div>"
            )
        if items:
            parts.append("".join(items))

    if text and text.strip():
        rendered = _render_markdown(text.strip(), md).strip()
        if rendered:
            rendered = _process_citations(
                rendered,
                bib_entries,
                style,
                cited_keys,
                citation_order,
                citation_numbers,
            )
            parts.append(rendered)

    if not parts:
        return ""
    return f'<div class="colloquium-slide-footnote">{"".join(parts)}</div>'


def _build_slide_meta_stack_html(
    position: str,
    cite_keys: list,
    footnote_text: str,
    inline_footnotes: list[dict[str, str]],
    bib_entries: dict,
    style: str,
    cited_keys: list,
    md: MarkdownIt,
    citation_order: str = "auto",
    citation_numbers: dict[str, int] | None = None,
) -> str:
    """Build the floating left/right footnote area for a slide."""
    cite_html = _build_slide_cite_html(
        cite_keys, bib_entries, style, cited_keys, citation_order, citation_numbers
    )
    footnote_html = _build_slide_footnote_html(
        footnote_text,
        inline_footnotes,
        md,
        bib_entries,
        style,
        cited_keys,
        citation_order,
        citation_numbers,
    )
    if not cite_html and not footnote_html:
        return ""
    inner = "".join(part for part in (cite_html, footnote_html) if part)
    return f'<div class="colloquium-slide-meta colloquium-slide-meta--{position}">{inner}</div>'


_ROW_SPLIT_RE = re.compile(r"^\s*===+\s*$", re.MULTILINE)
_ROW_COLUMNS_RE = re.compile(r"<!--\s*row-columns\s*:\s*(.*?)\s*-->")


def _split_columns_from_rendered(rendered: str) -> str:
    """Split rendered HTML into .col wrappers at ||| markers."""
    col_parts = re.split(r"<p>\|\|\|</p>", rendered)
    return "".join(f'<div class="col">{p.strip()}</div>' for p in col_parts)


def _extract_grid_spec(classes: list[str], prefix: str) -> str | None:
    """Return the first grid spec found for a class prefix such as cols- or rows-."""
    for cls in classes:
        if cls.startswith(prefix):
            return cls[len(prefix):]
    return None


def _grid_template_style(spec: str, axis: str) -> str:
    """Convert a class-like grid spec to an inline CSS grid template declaration."""
    if spec.isdigit():
        count = max(int(spec), 1)
        return f"grid-template-{axis}: repeat({count}, minmax(0, 1fr));"

    parts = [p for p in spec.split("-") if p]
    if len(parts) >= 2 and all(part.isdigit() for part in parts):
        tracks = " ".join(f"minmax(0, {int(part)}fr)" for part in parts)
        return f"grid-template-{axis}: {tracks};"

    return ""


def _slide_uses_figure_captions(classes: list[str], deck_figure_captions: bool = False) -> bool:
    """Return whether standalone images should render as figures on this slide."""
    if "no-figure-captions" in classes:
        return False
    if "figure-caption" in classes or "figure-captions" in classes:
        return True
    return deck_figure_captions


def _write_text_atomic(output_path: str, text: str) -> None:
    """Write text atomically so generated HTML is never partially updated."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(output.parent),
        delete=False,
        suffix=output.suffix,
    ) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(output)


def _build_rows_html(content: str, md: MarkdownIt, figure_captions: bool = False) -> str:
    """Build a row-based slide body with optional nested columns in each row."""
    row_blocks = [block.strip() for block in _ROW_SPLIT_RE.split(content) if block.strip()]
    rows_html = []
    for block in row_blocks:
        row_classes = ["colloquium-row"]
        row_style = ""
        for match in _ROW_COLUMNS_RE.finditer(block):
            spec = match.group(1).strip()
            row_classes.append(f'cols-{spec.replace("/", "-")}')
            row_classes.append("colloquium-grid")
            row_style = _grid_template_style(spec.replace("/", "-"), "columns")
            block = block.replace(match.group(0), "")

        rendered = _render_markdown(block.strip(), md)
        if figure_captions:
            rendered = _render_figure_captions(rendered, md)
        if any(cls.startswith("cols-") for cls in row_classes):
            rendered = _split_columns_from_rendered(rendered)

        style_attr = f' style="{row_style}"' if row_style else ""
        rows_html.append(f'<div class="{" ".join(row_classes)}"{style_attr}>{rendered}</div>')

    return "".join(rows_html)


def _build_slide_html(
    slide: Slide, index: int, total: int, md: MarkdownIt,
    footer: dict | None, bib_entries: dict | None = None,
    citation_style: str = "author-year", cited_keys: list | None = None,
    citation_order: str = "auto", citation_numbers: dict[str, int] | None = None,
    deck_figure_captions: bool = False,
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
    slide_style_attr = f' style="{slide.style}"' if slide.style else ""

    # Slide content
    parts = []
    if slide.title:
        tag = "h1" if slide.is_title_slide else "h2"
        title_html = _render_inline_markdown(slide.title, md)
        parts.append(f"<{tag}>{title_html}</{tag}>")

    has_columns = any(c.startswith("cols-") for c in slide.classes)
    has_rows = any(c.startswith("rows-") for c in slide.classes)
    inline_footnote_side = slide.metadata.get("footnotes_position", "right")
    slide_content = slide.content
    inline_footnotes = {"left": [], "right": []}
    if slide_content:
        slide_content, inline_footnotes = _extract_inline_footnotes(
            slide_content,
            index,
            inline_footnote_side,
        )

    if slide_content:
        figure_captions = _slide_uses_figure_captions(slide.classes, deck_figure_captions)
        if has_rows:
            rendered = _build_rows_html(slide_content, md, figure_captions=figure_captions)
            rows_spec = _extract_grid_spec(slide.classes, "rows-")
            rows_style = _grid_template_style(rows_spec or "", "rows")
            content_style_attr = f' style="{rows_style}"' if rows_style else ""
            parts.append(f'<div class="slide-content colloquium-rows"{content_style_attr}>{rendered}</div>')
        else:
            rendered = _render_markdown(slide_content, md)
            if figure_captions:
                rendered = _render_figure_captions(rendered, md)
            content_classes = ["slide-content"]
            content_style = ""
            if has_columns:
                cols_spec = _extract_grid_spec(slide.classes, "cols-")
                content_classes.append("colloquium-grid")
                content_style = _grid_template_style(cols_spec or "", "columns")
                rendered = _split_columns_from_rendered(rendered)
            content_style_attr = f' style="{content_style}"' if content_style else ""
            parts.append(f'<div class="{" ".join(content_classes)}"{content_style_attr}>{rendered}</div>')

    # Per-slide citation footnotes (floating above footer)
    cite_left = slide.metadata.get("cite_left", [])
    cite_right = slide.metadata.get("cite_right", [])
    footnote_left = slide.metadata.get("footnote_left", "")
    footnote_right = slide.metadata.get("footnote_right", "")
    left_meta = _build_slide_meta_stack_html(
        "left",
        cite_left,
        footnote_left,
        inline_footnotes["left"],
        bib_entries,
        citation_style,
        cited_keys,
        md,
        citation_order,
        citation_numbers,
    )
    right_meta = _build_slide_meta_stack_html(
        "right",
        cite_right,
        footnote_right,
        inline_footnotes["right"],
        bib_entries,
        citation_style,
        cited_keys,
        md,
        citation_order,
        citation_numbers,
    )
    if left_meta:
        parts.append(left_meta)
    if right_meta:
        parts.append(right_meta)

    parts.append(_build_footer_html(footer, index, total))

    inner = "\n".join(parts)

    return f'<section class="{class_str}"{slide_style_attr} data-index="{index}">\n{inner}\n</section>'


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

<button class="colloquium-picker-trigger" title="Open slide picker">
    <span class="colloquium-picker-trigger-label">Slides</span>
    <span class="colloquium-picker-trigger-count">1 / $total_slides</span>
</button>

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

window.colloquiumFitCaptionedFiguresIn = function(root) {
    var scope = root || document;
    var selector = [
        ".slide-content > figure.colloquium-figure:first-child:last-child",
        ".colloquium-grid > .col > figure.colloquium-figure:first-child:last-child",
        ".colloquium-row > figure.colloquium-figure:first-child:last-child"
    ].join(", ");

    scope.querySelectorAll(selector).forEach(function(figure) {
        var img = figure.querySelector("img");
        var caption = figure.querySelector("figcaption");
        if (!img || !caption) return;

        var container = figure.parentElement;
        if (!container) return;

        figure.style.width = "";
        img.style.width = "";
        img.style.height = "";
        img.style.maxWidth = "";
        img.style.maxHeight = "";

        var naturalWidth = img.naturalWidth || 0;
        var naturalHeight = img.naturalHeight || 0;
        if (!naturalWidth || !naturalHeight) {
            img.addEventListener("load", function() {
                window.colloquiumFitCaptionedFiguresIn(scope);
            }, { once: true });
            return;
        }

        var availableWidth = container.clientWidth;
        var availableHeight = container.clientHeight;
        if (!availableWidth || !availableHeight) return;

        var scale = Math.min(
            availableWidth / naturalWidth,
            availableHeight / naturalHeight
        );
        if (!isFinite(scale) || scale <= 0) return;

        var renderWidth = Math.max(1, Math.floor(naturalWidth * scale));
        var renderHeight = Math.max(1, Math.floor(naturalHeight * scale));

        figure.style.width = renderWidth + "px";
        img.style.width = renderWidth + "px";
        img.style.height = renderHeight + "px";
        img.style.maxWidth = "none";
        img.style.maxHeight = "none";
    });
};

// Render KaTeX math elements and highlight code after deferred scripts load
window.addEventListener("load", function() {
    if (typeof katex !== "undefined") {
        var mathEls = document.querySelectorAll(".math");
        if (mathEls.length > 0) {
            // Temporarily show all slides so KaTeX can measure container
            // dimensions for delimiter sizing (e.g. tall parentheses)
            var mathSlides = document.querySelectorAll(".slide");
            var mathOrigDisplay = [];
            var mathOrigVisibility = [];
            mathSlides.forEach(function(s) {
                mathOrigDisplay.push(s.style.display);
                mathOrigVisibility.push(s.style.visibility);
                s.style.display = "flex";
                if (!s.classList.contains("active")) {
                    s.style.visibility = "hidden";
                }
            });

            mathEls.forEach(function(el) {
                var displayMode = el.tagName === "DIV";
                katex.render(el.textContent, el, {
                    displayMode: displayMode,
                    throwOnError: false
                });
            });
            window.colloquiumFitDisplayMathIn(document);

            // Restore original slide display and visibility
            mathSlides.forEach(function(s, i) {
                s.style.display = mathOrigDisplay[i];
                s.style.visibility = mathOrigVisibility[i];
            });
        }

        if (document.fonts && document.fonts.ready) {
            document.fonts.ready.then(function() {
                window.colloquiumFitDisplayMathIn(document);
                window.colloquiumFitCaptionedFiguresIn(document);
            });
        }
    }
    if (typeof hljs !== "undefined") {
        hljs.highlightAll();
    }
    window.colloquiumFitCaptionedFiguresIn(document);
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
    citation_order = deck.citation_order
    citation_numbers: dict[str, int] = {}

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
                _discover_citation_keys(rendered, bib_entries, cited_keys)
            if slide.title:
                _discover_citation_keys(slide.title, bib_entries, cited_keys)
            # Also discover keys from per-slide cite directives
            for key in slide.metadata.get("cite_left", []) + slide.metadata.get("cite_right", []):
                if key not in cited_keys and key in bib_entries:
                    cited_keys.append(key)

        citation_numbers = {key: i + 1 for i, key in enumerate(cited_keys)}

        # Add reference slides to total count
        ref_slide_count = _count_references_slides(
            cited_keys, bib_entries, citation_style, citation_order, citation_numbers,
        )
        if ref_slide_count:
            total = len(deck.slides) + ref_slide_count

        # Reset counters for the real build pass
        elements.reset()

    slides_html_parts = []
    for i, slide in enumerate(deck.slides):
        slide_html = _build_slide_html(
            slide, i, total, md, deck.footer,
            bib_entries=bib_entries,
            citation_style=citation_style,
            cited_keys=cited_keys,
            citation_order=citation_order,
            citation_numbers=citation_numbers,
            deck_figure_captions=deck.figure_captions,
        )
        if bib_entries:
            slide_html = _process_citations(
                slide_html, bib_entries, citation_style, cited_keys, citation_order, citation_numbers,
            )
        slides_html_parts.append(slide_html)

    # Append references slides if we have citations
    if bib_entries and cited_keys:
        ref_slides = _build_references_slides_html(
            bib_entries, cited_keys, citation_style,
            len(deck.slides), total, deck.footer, citation_order, citation_numbers,
        )
        slides_html_parts.extend(ref_slides)

    slides_html = "\n\n".join(slides_html_parts)

    return _HTML_TEMPLATE.substitute(
        title=deck.title,
        theme_css=theme_css,
        custom_css=custom_css,
        slides_html=slides_html,
        total_slides=str(total),
        presentation_js=presentation_js,
    )


def build_file(input_path: str, output_path: str | None = None) -> str:
    """Build a markdown file into an HTML file. Returns the output path."""
    from colloquium.parse import parse_file

    deck = parse_file(input_path)
    html = build_deck(deck)

    if output_path is None:
        output_path = str(Path(input_path).with_suffix(".html"))

    _write_text_atomic(output_path, html)
    return output_path
