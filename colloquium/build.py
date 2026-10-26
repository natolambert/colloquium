"""HTML builder — converts a Deck into a self-contained HTML file."""

from __future__ import annotations

import base64
import html as html_module
from urllib.parse import unquote, urljoin
import re
import sys
import tempfile
from pathlib import Path
from string import Template

import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

from colloquium.md import create_base_md

from colloquium import elements
from colloquium.deck import CHAPTER_BAR_DEFAULTS, Deck
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
    md = create_base_md()
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


_TITLE_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def _render_title_markdown(title: str, md: MarkdownIt) -> str:
    """Render a slide title; each line of a multi-line title becomes a <br> break."""
    return "<br>".join(_render_inline_markdown(line, md) for line in title.split("\n"))


def _plain_title_text(heading_html: str) -> str:
    """One-line plain text for a rendered title (chapters, picker, table of contents)."""
    text = _HTML_TAG_RE.sub("", _TITLE_BREAK_RE.sub(" ", heading_html))
    return " ".join(html_module.unescape(text).split())


_FIGURE_TITLE_IMG_RE = re.compile(r'<img\b[^>]*\bsrc="([^"]+\.svg)"[^>]*>', re.IGNORECASE)
_SVG_TITLE_TEXT_RE = re.compile(r'<text\b[^>]*\bdata-role="title"[^>]*>.*?</text>', re.DOTALL)
_SVG_ROOT_RE = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
_SVG_ROOT_TITLE_RE = re.compile(r"(<svg\b[^>]*>\s*(?:<!--.*?-->\s*)*<title\b[^>]*>).*?(</title>)", re.DOTALL | re.IGNORECASE)
_ARIA_LABELLEDBY_RE = re.compile(r'\baria-labelledby="([^"\s]+)')


def _retitle_svg_document(svg: str, heading: str) -> str:
    """Replace the SVG's own document <title> (never a per-element tooltip <title>).

    The document title is the element named by the root's ``aria-labelledby``
    or, failing that, a <title> that directly follows the root tag.
    """
    root = _SVG_ROOT_RE.search(svg)
    labelled = _ARIA_LABELLEDBY_RE.search(root.group(0)) if root else None
    if labelled:
        by_id = re.compile(r'(<title\b[^>]*\bid="' + re.escape(labelled.group(1)) + r'"[^>]*>).*?(</title>)', re.DOTALL)
        return by_id.sub(lambda m: m.group(1) + heading + m.group(2), svg, count=1)
    return _SVG_ROOT_TITLE_RE.sub(lambda m: m.group(1) + heading + m.group(2), svg, count=1)


def retitle_svg(svg: str, heading: str) -> str | None:
    """Put ``heading`` (already HTML-escaped) into an exported plot's title.

    The first ``<text data-role="title">`` takes the heading and any further
    wrapped title lines are dropped; the document <title> follows. Returns None
    when the SVG has no such title text.
    """
    titles = list(_SVG_TITLE_TEXT_RE.finditer(svg))
    if not titles:
        return None
    first = titles[0].group(0)
    retitled = first[: first.index(">") + 1] + heading + "</text>"
    pieces, position = [], 0
    for index, found in enumerate(titles):
        pieces.append(svg[position:found.start()])
        pieces.append(retitled if index == 0 else "")
        position = found.end()
    pieces.append(svg[position:])
    return _retitle_svg_document("".join(pieces), heading)


def _apply_figure_title(slide_html: str, slide: Slide, source_dir: str, md: MarkdownIt) -> str:
    """For ``figure-title: heading``, retitle the slide's first SVG figure with the heading.

    The SVG must mark its title text with ``data-role="title"`` (the
    Interconnects plot exporter does); the first such line takes the heading
    and any further wrapped lines are dropped. The retitled copy is embedded
    as a data URI and the original path is kept in ``data-plot`` so hover
    helpers still find the plot's data. Anything else leaves the slide as is.
    """
    if slide.metadata.get("figure_title") != "heading" or not slide.title:
        return slide_html
    match = _FIGURE_TITLE_IMG_RE.search(slide_html)
    if not match:
        return slide_html
    src = html_module.unescape(match.group(1))
    if src.startswith(("data:", "http:", "https:", "//")):
        return slide_html
    # Markdown percent-encodes paths such as <my plot.svg>; open the real file.
    path = Path(source_dir or ".") / unquote(src)
    try:
        svg = path.read_text(encoding="utf-8")
    except OSError:
        print(f"  figure-title: cannot read {path}; keeping the figure's own title")
        return slide_html
    heading = html_module.escape(_plain_title_text(_render_title_markdown(slide.title, md)), quote=False)
    retitled_svg = retitle_svg(svg, heading)
    if retitled_svg is None:
        print(f'  figure-title: {path} has no <text data-role="title">; keeping its own title')
        return slide_html
    svg = retitled_svg
    data_uri = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
    img = match.group(0)
    retitled_img = img.replace(f'src="{match.group(1)}"', f'src="{data_uri}" data-plot="{match.group(1)}"', 1)
    return slide_html[:match.start()] + retitled_img + slide_html[match.end():]


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


# ===== Fragment processing (incremental reveal) =====

_STEP_MARKER_RE = re.compile(r"\s*<!--\s*step\s*-->\s*")
_CLASS_ATTR_RE = re.compile(r'\sclass=(["\'])(.*?)\1')
_LI_TAG_RE = re.compile(r"<li\b([^>]*)>")
_GENERATED_FRAGMENT_RE = re.compile(r'\sdata-colloquium-fragment="1"')
_EMPTY_DIV_RE = re.compile(r"<div\b([^>]*)>\s*</div>", re.DOTALL)
_FRAGMENT_BLOCK_TAGS = frozenset(
    (
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "ul",
        "ol",
        "pre",
        "blockquote",
        "table",
        "figure",
        "div",
    )
)


def _wrap_fragment_html(content: str) -> str:
    """Wrap *content* in a generated fragment container."""
    return f'<div class="fragment" data-colloquium-fragment="1">{content}</div>'


def _is_spacer_only_div(html: str) -> bool:
    """Return True for empty spacer helper divs that should not consume a step."""
    match = _EMPTY_DIV_RE.fullmatch(html.strip())
    if not match:
        return False
    class_match = _CLASS_ATTR_RE.search(match.group(1))
    if not class_match:
        return False
    return any(cls.startswith("colloquium-spacer-") for cls in class_match.group(2).split())


def _contains_generated_fragments(html: str) -> bool:
    """Return True when *html* contains generated fragment markers."""
    return _GENERATED_FRAGMENT_RE.search(html) is not None


def _process_step_markers(html: str) -> list[tuple[str, bool]]:
    """Split rendered HTML at ``<!-- step -->`` markers.

    Returns a list of *(html_chunk, is_fragment)* tuples.
    The first chunk (before any step marker) has *is_fragment=False*.
    """
    parts = _STEP_MARKER_RE.split(html)
    result = []
    for i, part in enumerate(parts):
        part = part.strip()
        if part:
            result.append((part, i > 0))
    return result


def _wrap_blocks_as_fragments(
    html: str, preserve_column_markers: bool = False,
) -> str:
    """Wrap each top-level block element as a fragment div.

    Uses depth tracking so nested block elements (e.g. ``<blockquote>``
    containing ``<p>``) are treated as a single top-level block.

    When *preserve_column_markers* is True, ``<p>|||</p>`` markers are
    passed through unwrapped so that column splitting can find them later.
    """
    open_re = re.compile(
        r"<(" + "|".join(_FRAGMENT_BLOCK_TAGS) + r")[\s>]"
    )
    close_re = re.compile(
        r"</(" + "|".join(_FRAGMENT_BLOCK_TAGS) + r")>"
    )

    lines = html.split("\n")
    blocks: list[str] = []
    current: list[str] = []
    depth = 0

    for line in lines:
        opens = sum(1 for _ in open_re.finditer(line))
        closes = sum(1 for _ in close_re.finditer(line))

        if depth == 0 and opens == 0 and not current:
            # Non-block content outside any block — pass through
            if line.strip():
                blocks.append(line)
            continue

        current.append(line)
        depth += opens - closes

        if depth <= 0:
            depth = 0
            block_html = "\n".join(current)
            stripped = block_html.strip()
            if stripped:
                if (
                    (preserve_column_markers and stripped == "<p>|||</p>")
                    or _is_spacer_only_div(stripped)
                ):
                    blocks.append(block_html)
                else:
                    blocks.append(_wrap_fragment_html(block_html))
            current = []

    if current:
        block_html = "\n".join(current)
        stripped = block_html.strip()
        if stripped:
            if _is_spacer_only_div(stripped):
                blocks.append(block_html)
            else:
                blocks.append(_wrap_fragment_html(block_html))

    return "\n".join(blocks)


def _apply_auto_animate(html: str, animate_type: str) -> str:
    """Add ``class="fragment"`` to elements based on *animate_type*.

    * ``bullets`` / ``items`` — each ``<li>`` becomes a fragment.
    * ``blocks`` — each top-level block element becomes a fragment.
    """
    if animate_type in ("bullets", "items"):
        def _fragmentize(match: re.Match[str]) -> str:
            attrs = match.group(1)
            class_match = _CLASS_ATTR_RE.search(attrs)
            if class_match:
                classes = class_match.group(2).split()
                classes = ["fragment", *(cls for cls in classes if cls != "fragment")]
                attrs = _CLASS_ATTR_RE.sub(
                    f' class="{" ".join(classes)}"',
                    attrs,
                    count=1,
                )
            else:
                attrs = f'{attrs} class="fragment"'
            if not _contains_generated_fragments(attrs):
                attrs = f'{attrs} data-colloquium-fragment="1"'
            return f"<li{attrs}>"

        html = _LI_TAG_RE.sub(_fragmentize, html)
        return _wrap_blocks_after_animated_lists(html)
    if animate_type == "blocks":
        return _wrap_blocks_as_fragments(html)
    return html


def _wrap_blocks_after_animated_lists(html: str) -> str:
    """Reveal blocks that follow an animated list after its bullets.

    With ``animate: bullets``, a paragraph written after the list (a
    takeaway, a caption, a closing line) used to be visible from the first
    click while the bullets above it were still hidden. Blocks before the
    first animated list stay visible; every top-level block after one is
    wrapped as its own fragment, so it appears once the bullets are done,
    as if a ``<!-- step -->`` preceded it.
    """
    open_re = re.compile(r"<(" + "|".join(_FRAGMENT_BLOCK_TAGS) + r")[\s>]")
    close_re = re.compile(r"</(" + "|".join(_FRAGMENT_BLOCK_TAGS) + r")>")
    blocks: list[str] = []
    current: list[str] = []
    depth = 0
    seen_animated_list = False

    def _emit_block(block_html: str) -> None:
        nonlocal seen_animated_list
        stripped = block_html.strip()
        if not stripped:
            return
        is_list = stripped.startswith(("<ul", "<ol"))
        if is_list and _contains_generated_fragments(block_html):
            seen_animated_list = True
            blocks.append(block_html)
            return
        if (
            not seen_animated_list
            or _is_spacer_only_div(stripped)
            or stripped.startswith('<div class="fragment" data-colloquium-fragment="1">')
        ):
            blocks.append(block_html)
            return
        blocks.append(_wrap_fragment_html(block_html))

    for line in html.split("\n"):
        opens = sum(1 for _ in open_re.finditer(line))
        closes = sum(1 for _ in close_re.finditer(line))
        if depth == 0 and opens == 0 and not current:
            if line.strip():
                blocks.append(line)
            continue
        current.append(line)
        depth += opens - closes
        if depth <= 0:
            depth = 0
            _emit_block("\n".join(current))
            current = []
    if current:
        _emit_block("\n".join(current))
    return "\n".join(blocks)


def _wrap_non_fragment_blocks(html: str) -> str:
    """Wrap top-level block elements that aren't already fully fragmentized.

    Used for step groups where auto-animate (bullets/items) has fragmentized
    ``<li>`` elements but left other block content (paragraphs, blockquotes,
    etc.) without a fragment wrapper.

    Skip rules:
    * ``<div class="fragment ...">`` — already a fragment wrapper.
    * ``<ul>``/``<ol>`` where every ``<li>`` has ``class="fragment"`` — the
      list is fully animated, wrapping it would add a redundant empty-list
      reveal step.
    * Everything else is wrapped so it stays hidden until the step click.
    """
    open_re = re.compile(
        r"<(" + "|".join(_FRAGMENT_BLOCK_TAGS) + r")[\s>]"
    )
    close_re = re.compile(
        r"</(" + "|".join(_FRAGMENT_BLOCK_TAGS) + r")>"
    )

    lines = html.split("\n")
    blocks: list[str] = []
    current: list[str] = []
    depth = 0

    def _emit_block(block_html: str) -> None:
        stripped = block_html.strip()
        if not stripped:
            return
        # Spacer helper divs are layout-only; revealing them would be a blank click.
        if _is_spacer_only_div(stripped):
            blocks.append(block_html)
            return
        # Already a fragment wrapper div — skip
        if stripped.startswith('<div class="fragment" data-colloquium-fragment="1">'):
            blocks.append(block_html)
            return
        # Fully-animated list (all <li> are fragments) — skip
        is_list = stripped.startswith(("<ul", "<ol"))
        if is_list and "<li>" not in block_html and _contains_generated_fragments(block_html):
            blocks.append(block_html)
            return
        # Wrap everything else
        blocks.append(_wrap_fragment_html(block_html))

    for line in lines:
        opens = sum(1 for _ in open_re.finditer(line))
        closes = sum(1 for _ in close_re.finditer(line))

        if depth == 0 and opens == 0 and not current:
            if line.strip():
                blocks.append(line)
            continue

        current.append(line)
        depth += opens - closes

        if depth <= 0:
            depth = 0
            _emit_block("\n".join(current))
            current = []

    if current:
        _emit_block("\n".join(current))

    return "\n".join(blocks)


def _number_fragments(html: str) -> tuple[str, int]:
    """Add sequential ``data-fragment-index`` to all fragment elements.

    Handles both ``class="fragment"`` and ``class="fragment extra-cls"``
    (elements with additional classes).

    Returns *(processed_html, total_fragment_count)*.
    """
    count = 0

    def _replace(m: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return f' data-fragment-index="{count}"'

    result = _GENERATED_FRAGMENT_RE.sub(_replace, html)
    return result, count


def _prepare_fragments(html: str, animate_type: str | None) -> str:
    """Process step markers and auto-animate without assigning indices.

    *animate_type* should be ``"bullets"``/``"items"`` or ``None``.
    ``"blocks"`` mode is applied earlier in the pipeline (before
    column/row splitting) so it should not be passed here.

    Pre-existing generated fragment markers (e.g. from an earlier
    blocks-wrapping pass) are preserved for a later whole-slide numbering
    pass.
    """
    has_existing = _contains_generated_fragments(html)
    if not animate_type and "<!-- step" not in html and not has_existing:
        return html

    # Split at step markers
    groups = _process_step_markers(html)
    if not groups:
        return html

    # No step markers — single group, just apply auto-animate
    if len(groups) == 1 and not groups[0][1]:
        if animate_type:
            return _apply_auto_animate(groups[0][0], animate_type)
        return html

    # Multiple groups (step markers present)
    parts = []
    for chunk, is_fragment in groups:
        if animate_type:
            chunk = _apply_auto_animate(chunk, animate_type)

        if is_fragment:
            has_inner = _contains_generated_fragments(chunk)
            if has_inner:
                # Some elements are already fragments (auto-animate or
                # pre-existing blocks wrapping).  Wrap any remaining
                # non-fragment blocks so they stay hidden until the step.
                chunk = _wrap_non_fragment_blocks(chunk)
                parts.append(chunk)
            else:
                parts.append(_wrap_fragment_html(chunk))
        else:
            parts.append(chunk)

    result = "\n".join(parts)
    return result


def _process_fragments(
    html: str, animate_type: str | None,
) -> tuple[str, int]:
    """Process fragments and assign sequential ``data-fragment-index`` values.

    Returns *(processed_html, fragment_count)*.
    """
    result = _prepare_fragments(html, animate_type)
    return _number_fragments(result)


# ===== Citation processing =====

_CITATION_RE = re.compile(r'\[@([\w:.\-]+(?:\s*;\s*@[\w:.\-]+)*)\]')
# Require a markup opener so comparisons such as "< 5% ... >" remain text.
_HTML_TAG_RE = re.compile(
    r'''<!--.*?-->|<(?:/?[A-Za-z]|[!?])(?:"[^"]*"|'[^']*'|[^'"<>])*>''',
    re.DOTALL,
)


def _parse_bib_file(path: str) -> dict:
    """Parse a .bib file using pybtex. Returns dict of key -> entry.

    Failures are non-fatal (the deck still builds) but must be loud: a
    single malformed entry makes pybtex raise, and silently returning {}
    leaves every citation in the deck unresolved with no hint why.
    """
    try:
        from pybtex.database import parse_file as pybtex_parse
    except ImportError:
        print(
            f"Warning: pybtex is not installed; skipping bibliography {path!r} "
            "(citations will not resolve)",
            file=sys.stderr,
        )
        return {}
    try:
        bib = pybtex_parse(path, bib_format="bibtex")
        return dict(bib.entries)
    except Exception as exc:
        print(
            f"Warning: failed to parse bibliography {path!r}: {exc} "
            "-- citations will not resolve",
            file=sys.stderr,
        )
        return {}


def _person_surname(person) -> str:
    """Full last name of a pybtex Person: join multi-word names, drop BibTeX braces.

    pybtex splits an unprotected "Ben Allal" into ["Ben", "Allal"] (so taking only
    the first token drops "Allal"), and keeps the braces from a protected
    "{Ben Allal}" (so it renders literally). Joining the parts and normalizing
    handles both.
    """
    surnames = person.last_names
    if surnames:
        return _normalize_bibtex_field(" ".join(surnames))
    return _normalize_bibtex_field(str(person))


def _get_author_surname(entry) -> str:
    """Extract the first author's surname from a pybtex entry."""
    try:
        persons = entry.persons.get("author", [])
        if not persons:
            return "Unknown"
        return _person_surname(persons[0])
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
            surname += f" & {_person_surname(authors[1])}"
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
    """Replace [@key] in HTML text with citation links. Tracks cited keys.

    Tags and comments are copied verbatim so citation syntax in an attribute
    cannot inject link markup into the surrounding tag.
    """

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

    parts = []
    text_start = 0
    for tag_match in _HTML_TAG_RE.finditer(html):
        parts.append(_CITATION_RE.sub(_replace, html[text_start:tag_match.start()]))
        parts.append(tag_match.group(0))
        text_start = tag_match.end()
    parts.append(_CITATION_RE.sub(_replace, html[text_start:]))
    return "".join(parts)


def _format_reference(entry, key: str, style: str, number: int) -> str:
    """Format a single reference entry for the references slide.

    Style: Authors. "Title." *Venue*, Year.
    """
    authors = entry.persons.get("author", [])
    author_strs = []
    for person in authors:
        surnames = _person_surname(person)
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
    # Initials already end the author line with "." -- don't double it.
    parts = [f'{prefix}{html_module.escape(author_line.rstrip("."))}.']
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
    chapter: int | None = None, chapter_bars: list[str] | None = None,
) -> list[str]:
    """Generate one or more References <section> elements, paginated.

    When ``chapter`` is given, the pages form a chapter titled "References".
    ``chapter_bars`` holds each page's chapter-bar HTML ("" for no bar).
    """
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

        chapter_bar = chapter_bars[page_num] if chapter_bars else ""
        content = (
            f'<h2>{heading}</h2>\n'
            f'<div class="slide-content colloquium-references-slide">{refs_html}</div>\n'
            f'{chapter_bar}'
            f'{_build_footer_html(footer, slide_index, total)}'
        )

        classes = "slide slide--content"
        if chapter_bar:
            classes += " has-chapter-bar"
        chapter_attr = _chapter_attr(chapter, "References" if page_num == 0 else None)
        slides.append(
            f'<section class="{classes}" data-index="{slide_index}"{chapter_attr}>\n{content}\n</section>'
        )

    return slides


def _chapter_start_title(slide: Slide) -> str | None:
    """Return the chapter title a slide opens, or None if it opens no chapter.

    An explicit ``<!-- chapter: ... -->`` directive opens a chapter; section-break
    slides open one implicitly. An empty title means "use the slide's heading".
    """
    if "chapter" in slide.metadata:
        return slide.metadata["chapter"]
    if slide.layout == "section-break":
        return ""
    return None


def _chapter_attr(chapter: int | None, start_title: str | None) -> str:
    """Build the data-chapter attributes for a slide <section>."""
    if chapter is None:
        return ""
    attr = f' data-chapter="{chapter}"'
    if start_title is not None:
        attr += " data-chapter-start"
        if start_title:
            attr += f' data-chapter-title="{html_module.escape(start_title, quote=True)}"'
    return attr


def _plan_chapters(
    openers: list[tuple[Slide | None, str | None]], md: MarkdownIt,
) -> tuple[list[int | None], list[dict]]:
    """Assign every rendered slide to a chapter.

    ``openers`` has one ``(slide, start_title)`` pair per slide in render order;
    ``slide`` is None for generated References pages. Returns the chapter index
    of each slide (None before the first chapter) and the chapters as
    ``{"title", "short", "start", "end", "references"}`` dicts with inclusive
    indices; ``short`` is the chapter bar label from ``<!-- chapter-short -->``.
    """
    slide_chapters: list[int | None] = []
    chapters: list[dict] = []
    for i, (slide, start_title) in enumerate(openers):
        if start_title is not None:
            title = start_title
            if not title and slide is not None and slide.title:
                heading_html = _render_title_markdown(slide.title, md)
                title = _plain_title_text(heading_html)
            short = slide.metadata.get("chapter_short", "") if slide is not None else ""
            chapters.append({
                "title": title or f"Slide {i + 1}",
                "short": short,
                "start": i,
                "end": i,
                "references": slide is None,
            })
        if chapters:
            chapters[-1]["end"] = i
        slide_chapters.append(len(chapters) - 1 if chapters else None)
    return slide_chapters, chapters


def _chapter_state(chapter_index: int, current: int | None) -> str:
    """Classify a chapter relative to the current one: done, current, or upcoming."""
    if current is None or chapter_index > current:
        return "upcoming"
    return "current" if chapter_index == current else "done"


def _build_chapter_bar_html(
    chapters: list[dict], index: int, current: int | None,
    labels: bool = True, progress: str = "slides",
) -> str:
    """Build the chapter navigation bar for the slide at ``index``.

    One segment per chapter (generated References excluded). Finished chapters
    are fully shaded and later ones stay empty. With ``progress="slides"`` the
    current chapter fills as its slides advance; with ``"chapters"`` it is shown
    whole, and the CSS tells it apart from finished chapters. Segments are
    labeled with the chapter's short name when it has one; ``labels=False``
    draws the tracks alone.
    """
    items = []
    for chapter_index, chapter in enumerate(chapters):
        if chapter["references"]:
            continue
        state = _chapter_state(chapter_index, current)
        if state == "done" or (state == "current" and progress == "chapters"):
            fill = 100.0
        elif state == "current":
            span = chapter["end"] - chapter["start"] + 1
            fill = 100.0 * (index - chapter["start"] + 1) / span
        else:
            fill = 0.0
        title = html_module.escape(chapter["title"], quote=True)
        label = html_module.escape(chapter["short"] or chapter["title"])
        label_html = f'<span class="colloquium-chapter-bar-label">{label}</span>' if labels else ""
        aria_current = ' aria-current="step"' if state == "current" else ""
        items.append(
            f'<a class="colloquium-chapter-bar-item {state}" href="#{chapter["start"] + 1}"'
            f' title="{title}" style="--chapter-progress: {fill:g}%"{aria_current}>'
            f'{label_html}</a>'
        )
    if not items:
        return ""
    classes = "colloquium-chapter-bar"
    if not labels:
        classes += " colloquium-chapter-bar--bars"
    if progress == "chapters":
        classes += " colloquium-chapter-bar--chapters"
    return f'<nav class="{classes}" aria-label="Chapters">{"".join(items)}</nav>\n'


_TOC_RE = re.compile(r'<pre><code class="language-toc">(.*?)</code></pre>', re.DOTALL)


def _build_toc_html(options_text: str, chapters: list[dict], current: int | None) -> str:
    """Build a table-of-contents list of the deck's chapters.

    The chapter containing the slide is marked current, so a TOC repeated at
    the start of each chapter works as an agenda. Options (YAML in the block):
    ``numbered`` (default true) chooses an ordered or plain list.
    """
    try:
        options = yaml.safe_load(html_module.unescape(options_text)) or {}
    except yaml.YAMLError:
        options = {}
    if not isinstance(options, dict):
        options = {}
    tag = "ol" if options.get("numbered", True) is not False else "ul"

    items = []
    for chapter_index, chapter in enumerate(chapters):
        if chapter["references"]:
            continue
        state = _chapter_state(chapter_index, current)
        title = html_module.escape(chapter["title"])
        items.append(
            f'<li class="colloquium-toc-item {state}">'
            f'<a href="#{chapter["start"] + 1}">{title}</a></li>'
        )
    if not items:
        return ""
    classes = "colloquium-toc"
    if current is not None:
        classes += " colloquium-toc--has-current"
    return f'<{tag} class="{classes}">{"".join(items)}</{tag}>'


def slides_for_format(slides: list[Slide], fmt: str) -> list[Slide]:
    """Drop slides marked ``<!-- only: ... -->`` for another output format.

    ``fmt`` is ``"html"`` (the HTML build, and the PDF and captures made from
    it) or ``"pptx"`` (native PowerPoint export).
    """
    return [slide for slide in slides if slide.metadata.get("only", fmt) == fmt]


_TOC_FENCE_RE = re.compile(r"^```toc[^\n]*\n(.*?)^```[ \t]*$", re.DOTALL | re.MULTILINE)


def expand_toc_markdown(slides: list[Slide], chapters_enabled: bool = True) -> list[Slide]:
    """Return copies of ``slides`` with ```toc blocks expanded to markdown lists.

    For native exporters, which cannot run the HTML pipeline. The current
    chapter is bolded; ``numbered: false`` gives a bullet list.
    """
    from dataclasses import replace

    if not any(_TOC_FENCE_RE.search(slide.content) for slide in slides):
        return slides
    openers = [(slide, _chapter_start_title(slide)) for slide in slides]
    if chapters_enabled and any(title is not None for _, title in openers):
        slide_chapters, chapters = _plan_chapters(openers, _create_md_renderer())
    else:
        slide_chapters, chapters = [None] * len(slides), []

    def expand(match: re.Match, current: int | None) -> str:
        try:
            options = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            options = {}
        numbered = not (isinstance(options, dict) and options.get("numbered") is False)
        lines = []
        for chapter_index, chapter in enumerate(chapters):
            if chapter["references"]:
                continue
            title = chapter["title"].replace("*", "\\*")
            if chapter_index == current:
                title = f"**{title}**"
            lines.append(f"{len(lines) + 1}. {title}" if numbered else f"- {title}")
        return "\n".join(lines)

    return [
        replace(slide, content=_TOC_FENCE_RE.sub(lambda m: expand(m, slide_chapters[i]), slide.content))
        if _TOC_FENCE_RE.search(slide.content) else slide
        for i, slide in enumerate(slides)
    ]


def _replace_toc_blocks(slide_html: str, chapters: list[dict], current: int | None) -> str:
    """Swap every ```toc block in a built slide for the chapter list."""
    return _TOC_RE.sub(lambda m: _build_toc_html(m.group(1), chapters, current), slide_html)


_IMAGE_URL_RE = re.compile(r"\.(png|jpg|jpeg|gif|svg|webp)$|^https?://", re.IGNORECASE)


def _footer_for_slide(footer: dict | None, slide: Slide) -> dict | None:
    """Apply ``footer.section_break`` zone overrides on section-break slides."""
    if not footer:
        return footer
    overrides = footer.get("section_break")
    if slide.layout != "section-break" or not isinstance(overrides, dict):
        return footer
    return {**footer, **overrides}


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


def _build_columns_html(rendered: str, animate_type: str | None) -> str:
    """Build column wrappers after processing fragments inside each column."""
    col_parts = re.split(r"<p>\|\|\|</p>", rendered)
    return "".join(
        f'<div class="col">{_prepare_fragments(part.strip(), animate_type)}</div>'
        for part in col_parts
    )


def _extract_grid_spec(classes: list[str], prefix: str) -> str | None:
    """Return the first grid spec found for a class prefix such as cols- or rows-."""
    for cls in classes:
        if cls.startswith(prefix):
            return cls[len(prefix):]
    return None


def _grid_template_tracks(spec: str) -> str:
    """Convert a class-like grid spec (2, 60-40, 1-2-1) to a CSS track list."""
    if spec.isdigit():
        count = max(int(spec), 1)
        return f"repeat({count}, minmax(0, 1fr))"

    parts = [p for p in spec.split("-") if p]
    if len(parts) >= 2 and all(part.isdigit() for part in parts):
        return " ".join(f"minmax(0, {int(part)}fr)" for part in parts)

    return ""


def _grid_template_style(spec: str, axis: str) -> str:
    """Convert a class-like grid spec to an inline CSS grid template declaration."""
    tracks = _grid_template_tracks(spec)
    return f"grid-template-{axis}: {tracks};" if tracks else ""


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


def _row_print_fractions(rows_spec: str | None, row_count: int) -> list[float]:
    """Height fraction of each row, for the print-time image size cap.

    Printed slides never run the runtime figure fit pass, so the theme's print
    CSS caps row images at (usable slide height x row fraction) via the
    --colloquium-print-row-frac variable emitted here. Without the cap, a row
    image taller than its row overflows the fixed-height slide and Chromium's
    print fragmentation moves it to the next PDF page.
    """
    if row_count <= 0:
        return []
    if rows_spec:
        # A pure count spec means equal rows whether or not it matches the
        # actual row blocks, so return directly instead of materializing a
        # count-sized list -- a spec like `rows: 100000000` would otherwise
        # exhaust memory.
        if rows_spec.isdigit():
            return [1 / row_count] * row_count
        parts = [p for p in rows_spec.split("-") if p]
        if (
            len(parts) == row_count
            and all(p.isdigit() for p in parts)
            and any(int(p) > 0 for p in parts)
        ):
            total = sum(int(p) for p in parts)
            return [int(p) / total for p in parts]
    return [1 / row_count] * row_count


def _build_rows_html(
    content: str, md: MarkdownIt, figure_captions: bool = False,
    animate_type: str | None = None, rows_spec: str | None = None,
) -> str:
    """Build a row-based slide body with optional nested columns in each row."""
    frag_animate = animate_type if animate_type in ("bullets", "items") else None
    row_blocks = [block.strip() for block in _ROW_SPLIT_RE.split(content) if block.strip()]
    row_fractions = _row_print_fractions(rows_spec, len(row_blocks))
    rows_html = []
    for row_index, block in enumerate(row_blocks):
        row_classes = ["colloquium-row"]
        row_style = f"--colloquium-print-row-frac: {row_fractions[row_index]:.4f};"
        for match in _ROW_COLUMNS_RE.finditer(block):
            spec = match.group(1).strip()
            row_classes.append(f'cols-{spec.replace("/", "-")}')
            row_classes.append("colloquium-grid")
            row_style += " " + _grid_template_style(spec.replace("/", "-"), "columns")
            block = block.replace(match.group(0), "")

        rendered = _render_markdown(block.strip(), md)
        if figure_captions:
            rendered = _render_figure_captions(rendered, md)
        # Apply blocks wrapping per-row BEFORE column splitting
        has_row_cols = any(cls.startswith("cols-") for cls in row_classes)
        if animate_type == "blocks":
            rendered = _wrap_blocks_as_fragments(
                rendered, preserve_column_markers=has_row_cols,
            )
        if has_row_cols:
            rendered = _build_columns_html(rendered, frag_animate)
        else:
            rendered = _prepare_fragments(rendered, frag_animate)

        style_attr = f' style="{row_style}"' if row_style else ""
        rows_html.append(f'<div class="{" ".join(row_classes)}"{style_attr}>{rendered}</div>')

    return "".join(rows_html)


def _build_slide_html(
    slide: Slide, index: int, total: int, md: MarkdownIt,
    footer: dict | None, bib_entries: dict | None = None,
    citation_style: str = "author-year", cited_keys: list | None = None,
    citation_order: str = "auto", citation_numbers: dict[str, int] | None = None,
    deck_figure_captions: bool = False, chapter_attr: str = "",
    chapter_bar_html: str = "",
) -> str:
    """Build the HTML for a single slide."""
    if bib_entries is None:
        bib_entries = {}
    if cited_keys is None:
        cited_keys = []
    fragment_count = 0

    # CSS classes
    classes = ["slide", f"slide--{slide.layout}"]
    if index == 0:
        classes.append("active")
    classes.extend(slide.classes)
    # figure-title: heading moves the heading into the figure, so hide it here
    # whether the slide came from Markdown or from Deck.add_slide().
    if slide.metadata.get("figure_title") == "heading" and "title-hidden" not in classes:
        classes.append("title-hidden")
    if chapter_bar_html:
        classes.append("has-chapter-bar")

    class_str = " ".join(classes)

    # Style attribute
    slide_style = (slide.style or "").strip()

    # Slide content
    parts = []
    eyebrow = slide.metadata.get("eyebrow")
    if eyebrow:
        parts.append(f'<div class="slide-eyebrow">{_render_inline_markdown(eyebrow, md)}</div>')
    if slide.title:
        tag = "h1" if slide.is_title_slide else "h2"
        title_html = _render_title_markdown(slide.title, md)
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

    animate_type = slide.metadata.get("animate")
    # blocks wrapping runs before column/row splitting (it targets raw
    # block-level elements which get obscured by wrapper divs); bullets
    # and step markers run after splitting, inside each layout container.
    frag_animate = animate_type if animate_type in ("bullets", "items") else None
    if slide_content:
        figure_captions = _slide_uses_figure_captions(slide.classes, deck_figure_captions)
        if has_rows:
            rows_spec = _extract_grid_spec(slide.classes, "rows-")
            rendered = _build_rows_html(
                slide_content, md, figure_captions=figure_captions,
                animate_type=animate_type, rows_spec=rows_spec,
            )
            rendered, fragment_count = _number_fragments(rendered)
            rows_style = _grid_template_style(rows_spec or "", "rows")
            content_style_attr = f' style="{rows_style}"' if rows_style else ""
            parts.append(f'<div class="slide-content colloquium-rows"{content_style_attr}>{rendered}</div>')
        else:
            rendered = _render_markdown(slide_content, md)
            if figure_captions:
                rendered = _render_figure_captions(rendered, md)
            # Apply blocks wrapping before column splitting
            if animate_type == "blocks":
                rendered = _wrap_blocks_as_fragments(
                    rendered, preserve_column_markers=has_columns,
                )
            content_classes = ["slide-content"]
            content_style = ""
            if has_columns:
                cols_spec = _extract_grid_spec(slide.classes, "cols-")
                content_classes.append("colloquium-grid")
                content_style = _grid_template_style(cols_spec or "", "columns")
                # The slide itself learns the column tracks so layouts that
                # restructure the slide (img-tall-right) follow the same ratio.
                tracks = _grid_template_tracks(cols_spec or "")
                if tracks:
                    if slide_style and not slide_style.endswith(";"):
                        slide_style += ";"
                    slide_style = f"{slide_style} --colloquium-columns: {tracks};".strip()
                rendered = _build_columns_html(rendered, frag_animate)
                rendered, fragment_count = _number_fragments(rendered)
            else:
                rendered, fragment_count = _process_fragments(rendered, frag_animate)
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

    if chapter_bar_html:
        parts.append(chapter_bar_html.rstrip("\n"))
    parts.append(_build_footer_html(_footer_for_slide(footer, slide), index, total))

    inner = "\n".join(parts)

    fragment_attr = f' data-fragment-count="{fragment_count}"' if fragment_count > 0 else ""
    # Embed the slide's markdown source (base64 of UTF-8) so the presentation
    # engine can copy it to the clipboard. Base64 sidesteps all HTML-escaping
    # and unicode pitfalls of carrying raw markdown in an attribute.
    md_source = base64.b64encode(slide.to_markdown().encode("utf-8")).decode("ascii")
    md_attr = f' data-colloquium-md="{md_source}"'
    slide_style_attr = f' style="{slide_style}"' if slide_style else ""
    return f'<section class="{class_str}"{slide_style_attr} data-index="{index}"{chapter_attr}{fragment_attr}{md_attr}>\n{inner}\n</section>'


# HTML template — uses $-style substitution
_HTML_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
$share_meta

<!-- KaTeX for LaTeX math -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.js"></script>

<!-- Chart.js for inline charts -->
<script defer src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>

<!-- highlight.js for code syntax highlighting -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/styles/github.min.css">
<script defer src="https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.11.1/build/highlight.min.js"></script>
$font_link

<style>
$theme_css
$font_css
$custom_css
</style>
</head>
<body$body_attr>
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

        // Authors can take over layout entirely (e.g. absolutely positioned
        // full-height figures); leave those untouched.
        if (window.getComputedStyle(figure).position === "absolute") return;

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
        // The caption sits below the image inside the figure: reserve its
        // height (plus the figure's own gap) so the scaled image + caption
        // fit the cell together instead of the caption overflowing onto
        // whatever sits below (usually the footer).
        var captionHeight = caption.offsetHeight || 0;
        var figureStyle = window.getComputedStyle(figure);
        var figureGap = parseFloat(figureStyle.rowGap || figureStyle.gap) || 0;
        var availableHeight = container.clientHeight - captionHeight - figureGap;
        if (!availableWidth || availableHeight <= 0) return;

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
                s.style.display = s.classList.contains("img-tall-right") ? "grid" : "flex";
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
                s.style.display = s.classList.contains("img-tall-right") ? "grid" : "flex";
                if (!s.classList.contains("active")) {
                    s.style.visibility = "hidden";
                }
            });

            chartCanvases.forEach(function(canvas) {
                try {
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
                } catch(e) {
                    var slideEl = canvas.closest(".slide");
                    var slideNum = slideEl ? (slideEl.getAttribute("data-index") || "?") : "?";
                    var chartId = canvas.id || "unknown";
                    console.error(
                        "Colloquium: failed to render chart '" + chartId +
                        "' on slide " + (parseInt(slideNum, 10) + 1) + ": " + e.message
                    );
                }
            });

            // After a frame, capture each chart as a static image for print,
            // then always restore slide visibility (even if chart rendering failed).
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


def _build_font_link(fonts: dict | None) -> str:
    """Build a <link> tag to load Google Fonts."""
    if not fonts:
        return ""
    imports = []
    for key in ("heading", "body"):
        name = fonts.get(key)
        if name:
            imports.append(name.replace(" ", "+"))
    if not imports:
        return ""
    families = "&family=".join(f"{f}:wght@400;600;700" for f in imports)
    return f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={families}&display=swap">'


def _build_font_css(fonts: dict | None) -> str:
    """Build CSS custom property overrides for font families."""
    if not fonts:
        return ""
    overrides = []
    for key, prop in (("heading", "--colloquium-font-heading"), ("body", "--colloquium-font-body")):
        name = fonts.get(key)
        if not name:
            continue
        overrides.append(f'    {prop}: "{name}", sans-serif;')
    if not overrides:
        return ""
    return ":root {\n" + "\n".join(overrides) + "\n}"


def share_image_name(stem: str) -> str:
    """Default share image filename for a deck built as ``<stem>.html``."""
    return f"{stem}-share.png"


def _share_meta_html(deck: Deck, output_stem: str | None = None) -> str:
    """Open Graph and Twitter card tags for the deck's share image and URL."""
    image = deck.share_image
    if image is True or (isinstance(image, str) and image.strip().lower() in ("auto", "true")):
        image = share_image_name(output_stem or "deck")
    elif not image:
        image = ""
    url = (deck.url or "").strip()
    if image and url and not re.match(r"^[a-z][a-z0-9+.-]*:", image, re.IGNORECASE):
        image = urljoin(url, image)
    if not image and not url:
        return ""
    description = " · ".join(part for part in (deck.author, deck.date) if part)
    tags = ['<meta property="og:type" content="website">', f'<meta property="og:title" content="{html_module.escape(deck.title, quote=True)}">']
    if description:
        tags.append(f'<meta property="og:description" content="{html_module.escape(description, quote=True)}">')
    if url:
        tags.append(f'<meta property="og:url" content="{html_module.escape(url, quote=True)}">')
        tags.append(f'<link rel="canonical" href="{html_module.escape(url, quote=True)}">')
    if image:
        tags.append(f'<meta property="og:image" content="{html_module.escape(image, quote=True)}">')
        tags.append('<meta name="twitter:card" content="summary_large_image">')
        tags.append(f'<meta name="twitter:image" content="{html_module.escape(image, quote=True)}">')
    else:
        tags.append('<meta name="twitter:card" content="summary">')
    tags.append(f'<meta name="twitter:title" content="{html_module.escape(deck.title, quote=True)}">')
    return "\n".join(tags)


def _load_custom_css(deck: Deck) -> str:
    """Return the deck's custom CSS, reading ``custom_css_path`` when it is set.

    A relative path resolves against the deck's source directory (the folder
    of the markdown file), so ``custom_css: deck.css`` finds the file next to
    the deck. The file's contents are inlined, keeping the HTML self-contained.
    """
    inline = deck.custom_css or ""
    path = getattr(deck, "custom_css_path", "") or ""
    if not path:
        return inline
    css_path = Path(path)
    if not css_path.is_absolute():
        css_path = Path(getattr(deck, "source_dir", "") or ".") / css_path
    try:
        file_css = css_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(
            f"custom_css stylesheet not found: {css_path} "
            f"(frontmatter custom_css: {path})"
        ) from None
    return f"{file_css}\n{inline}" if inline else file_css


def build_deck(deck: Deck, output_stem: str | None = None) -> str:
    """Build a Deck into a self-contained HTML string."""
    elements.reset()
    md = _create_md_renderer()
    theme_css = _read_theme_css(deck.theme)
    presentation_js = _read_presentation_js(deck.theme)

    font_link = _build_font_link(deck.fonts)
    font_css = _build_font_css(deck.fonts)
    custom_css = _load_custom_css(deck)

    # Load bibliography if configured
    bib_entries = {}
    if deck.bibliography:
        bib_entries = _parse_bib_file(deck.bibliography)

    citation_style = deck.citation_style
    citation_order = deck.citation_order
    citation_numbers: dict[str, int] = {}

    deck_slides = slides_for_format(deck.slides, "html")
    main_slides = [
        slide for slide in deck_slides
        if slide.metadata.get("after") != "references"
    ]
    post_reference_slides = [
        slide for slide in deck_slides
        if slide.metadata.get("after") == "references"
    ]
    render_order_slides = main_slides + post_reference_slides
    ref_slide_count = 0

    # First pass: build slides and discover cited keys
    cited_keys: list[str] = []
    total = len(main_slides)

    # If we have bib entries, we need a two-pass approach:
    # first discover citations, then rebuild with correct total (including references slide)
    if bib_entries:
        # Discovery pass — render slides to find cited keys
        for slide in render_order_slides:
            if slide.content:
                rendered = _render_markdown(slide.content, md)
                _discover_citation_keys(rendered, bib_entries, cited_keys)
            if slide.title:
                _discover_citation_keys(slide.title, bib_entries, cited_keys)
            # Footnote directives render citations too
            for side in ("footnote_left", "footnote_right"):
                if slide.metadata.get(side):
                    _discover_citation_keys(slide.metadata[side], bib_entries, cited_keys)
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
            total = len(main_slides) + ref_slide_count

        # Reset counters for the real build pass
        elements.reset()

    # Chapters group slides in the picker, the chapter bar, and ```toc blocks.
    # A chapter runs from the slide that opens it to the next opener; slides
    # before the first opener are ungrouped. Generated References pages form
    # their own chapter, but only when the deck's own slides open chapters.
    openers: list[tuple[Slide | None, str | None]] = [
        (slide, _chapter_start_title(slide)) for slide in main_slides
    ]
    openers += [(None, "References" if page == 0 else None) for page in range(ref_slide_count)]
    openers += [(slide, _chapter_start_title(slide)) for slide in post_reference_slides]
    use_chapters = deck.chapters and any(
        _chapter_start_title(slide) is not None for slide in render_order_slides
    )
    if use_chapters:
        slide_chapters, chapters = _plan_chapters(openers, md)
    else:
        slide_chapters, chapters = [None] * len(openers), []

    def chapter_attr_at(index: int) -> str:
        return _chapter_attr(slide_chapters[index], openers[index][1])

    bar = deck.chapter_bar

    def chapter_bar_at(index: int, slide: Slide | None) -> str:
        """Resolve the deck's chapter_bar settings and any per-slide override."""
        if not chapters:
            return ""
        tokens = slide.metadata.get("chapter_bar", "").split() if slide is not None else []
        if "hide" in tokens or (slide is not None and "no-chapter-bar" in slide.classes):
            return ""
        if tokens:
            # A chapter-bar directive shows the bar on this slide, restyled by its tokens.
            options = dict(bar or CHAPTER_BAR_DEFAULTS)
            for token in tokens:
                if token in ("labels", "bars"):
                    options["labels"] = token == "labels"
                elif token in ("slides", "chapters"):
                    options["progress"] = token
        else:
            if not bar or (slide is not None and slide.is_title_slide):
                return ""
            if bar["slides"] == "section-breaks" and (slide is None or slide.layout != "section-break"):
                return ""
            options = bar
        return _build_chapter_bar_html(
            chapters, index, slide_chapters[index],
            labels=options["labels"], progress=options["progress"],
        )

    def build_one(slide: Slide, index: int) -> str:
        slide_html = _build_slide_html(
            slide, index, total, md, deck.footer,
            bib_entries=bib_entries,
            citation_style=citation_style,
            cited_keys=cited_keys,
            citation_order=citation_order,
            citation_numbers=citation_numbers,
            deck_figure_captions=deck.figure_captions,
            chapter_attr=chapter_attr_at(index),
            chapter_bar_html=chapter_bar_at(index, slide),
        )
        if bib_entries:
            slide_html = _process_citations(
                slide_html, bib_entries, citation_style, cited_keys, citation_order, citation_numbers,
            )
        slide_html = _apply_figure_title(slide_html, slide, getattr(deck, "source_dir", ""), md)
        return _replace_toc_blocks(slide_html, chapters, slide_chapters[index])

    slides_html_parts = [build_one(slide, i) for i, slide in enumerate(main_slides)]

    # Append references slides if we have citations
    post_reference_start = len(main_slides)
    if bib_entries and cited_keys:
        ref_indices = range(len(main_slides), len(main_slides) + ref_slide_count)
        ref_slides = _build_references_slides_html(
            bib_entries, cited_keys, citation_style,
            len(main_slides), total, deck.footer, citation_order, citation_numbers,
            chapter=slide_chapters[len(main_slides)] if ref_slide_count else None,
            chapter_bars=[chapter_bar_at(i, None) for i in ref_indices],
        )
        slides_html_parts.extend(ref_slides)
        post_reference_start += ref_slide_count

    for offset, slide in enumerate(post_reference_slides):
        slides_html_parts.append(build_one(slide, post_reference_start + offset))

    slides_html = "\n\n".join(slides_html_parts)

    # The window-edge progress line is redundant only when every slide has a bar.
    body_attr = ""
    if bar and chapters and bar["slides"] == "all":
        body_attr = ' class="colloquium-has-chapter-bar"'

    return _HTML_TEMPLATE.substitute(
        title=deck.title,
        share_meta=_share_meta_html(deck, output_stem),
        font_link=font_link,
        font_css=font_css,
        theme_css=theme_css,
        custom_css=custom_css,
        slides_html=slides_html,
        total_slides=str(total),
        presentation_js=presentation_js,
        body_attr=body_attr,
    )


def build_file(input_path: str, output_path: str | None = None) -> str:
    """Build a markdown file into an HTML file. Returns the output path."""
    from colloquium.parse import parse_file

    deck = parse_file(input_path)

    if output_path is None:
        output_path = str(Path(input_path).with_suffix(".html"))
    html = build_deck(deck, output_stem=Path(output_path).stem)

    _write_text_atomic(output_path, html)
    return output_path
