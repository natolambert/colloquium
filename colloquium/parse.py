"""Markdown parser — converts markdown files into Deck objects."""

from __future__ import annotations

import re

import yaml

from colloquium.deck import Deck
from colloquium.slide import Slide


# Directive patterns: <!-- key: value -->
_DIRECTIVE_RE = re.compile(
    r"<!--\s*(layout|class|style|notes|title|align|valign|columns|rows|padding|size|cite|cite-left|cite-right|footnote|footnote-right|footnotes|img-align|img-valign|img-fill|img-overflow|animate|after|eyebrow|chapter|chapter-short|chapter-bar|figure-title|only)\s*:\s*(.*?)\s*-->",
    re.DOTALL,
)

# Map directive keys to CSS class names
_DIRECTIVE_CLASS_MAP = {
    "title": lambda v: f"title-{v}",
    "align": lambda v: f"align-{v}",
    "valign": lambda v: f"valign-{v}",
    "padding": lambda v: f"pad-{v}",
    "size": lambda v: f"size-{v}",
    "img-align": lambda v: f"img-align-{v}",
    "img-valign": lambda v: f"img-valign-{v}",
    "img-fill": lambda v: "img-fill",
    "img-overflow": lambda v: "img-overflow",
}

_GRID_SPEC_RE = re.compile(r"^\d+(?:/\d+)*$")

_FRONTMATTER_END_RE = re.compile(r"^---[ \t]*\r?$", re.MULTILINE)


def _normalize_grid_spec(value: str) -> str | None:
    """Return a normalized class suffix for valid grid specs only."""
    value = value.strip()
    if not value or not _GRID_SPEC_RE.fullmatch(value):
        return None
    return value.replace("/", "-")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown text.

    Returns (metadata_dict, remaining_text).
    """
    text = text.strip()
    if not text.startswith("---"):
        return {}, text

    # Find the closing --- on its own line, so a "---" inside a value
    # (e.g. title: "RLHF --- a primer") does not end the frontmatter early.
    end = _FRONTMATTER_END_RE.search(text, 3)
    if end is None:
        return {}, text

    yaml_str = text[3 : end.start()].strip()
    remaining = text[end.end() :].strip()

    try:
        metadata = yaml.safe_load(yaml_str) or {}
    except yaml.YAMLError:
        metadata = {}

    if not isinstance(metadata, dict):
        return {}, text

    return metadata, remaining


def parse_slide(text: str) -> Slide:
    """Parse a single slide's markdown text into a Slide object."""
    layout = "content"
    classes = []
    style = ""
    notes = ""
    title = ""
    content_lines = []

    metadata = {}

    # Extract directives and notes
    remaining = text
    for match in _DIRECTIVE_RE.finditer(text):
        key = match.group(1)
        value = match.group(2).strip()
        if key == "layout":
            layout = value
        elif key == "class":
            classes.extend(value.split())
        elif key == "style":
            style = value
        elif key == "notes":
            notes = value
        elif key in {"cite", "cite-left"}:
            metadata.setdefault("cite_left", []).extend(
                k.strip() for k in value.split(",") if k.strip()
            )
        elif key == "cite-right":
            metadata.setdefault("cite_right", []).extend(
                k.strip() for k in value.split(",") if k.strip()
            )
        elif key == "footnote":
            metadata["footnote_left"] = value
        elif key == "footnote-right":
            metadata["footnote_right"] = value
        elif key == "footnotes":
            if value in {"left", "right"}:
                metadata["footnotes_position"] = value
        elif key == "animate":
            metadata["animate"] = value
        elif key == "after":
            metadata["after"] = value
        elif key == "eyebrow":
            metadata["eyebrow"] = value
        elif key == "figure-title":
            metadata["figure_title"] = value
        elif key == "chapter":
            metadata["chapter"] = value
        elif key == "chapter-short":
            metadata["chapter_short"] = value
        elif key == "chapter-bar":
            metadata["chapter_bar"] = value
        elif key == "only":
            metadata["only"] = value.lower()
        elif key == "columns":
            spec = _normalize_grid_spec(value)
            if spec:
                classes.append(f"cols-{spec}")
        elif key == "rows":
            spec = _normalize_grid_spec(value)
            if spec:
                classes.append(f"rows-{spec}")
        elif key in _DIRECTIVE_CLASS_MAP:
            classes.append(_DIRECTIVE_CLASS_MAP[key](value))
        remaining = remaining.replace(match.group(0), "")

    # Parse remaining content for title. Consecutive heading lines of the same
    # level at the top of the slide form one multi-line title (a line break
    # between them); a heading after any other line stays in the content.
    lines = remaining.strip().splitlines()
    content_parts = []
    title_lines: list[str] = []
    title_prefix = ""

    for line in lines:
        stripped = line.strip()
        if title_lines and not content_parts and stripped.startswith(title_prefix):
            title_lines.append(stripped[len(title_prefix):].strip())
        elif not title_lines and stripped.startswith("# "):
            title_prefix = "# "
            title_lines.append(stripped[2:].strip())
            if layout == "content":
                layout = "title"
        elif not title_lines and stripped.startswith("## "):
            title_prefix = "## "
            title_lines.append(stripped[3:].strip())
        else:
            content_parts.append(line)

    title = "\n".join(title_lines)
    content = "\n".join(content_parts).strip()

    return Slide(
        title=title,
        content=content,
        layout=layout,
        speaker_notes=notes,
        classes=classes,
        style=style,
        metadata=metadata,
    )


def is_stylesheet_path(value) -> bool:
    """True when a ``custom_css`` value names a .css file rather than inline CSS."""
    if not isinstance(value, str):
        return False
    text = value.strip()
    return (
        text.lower().endswith(".css")
        and "\n" not in text
        and "{" not in text
    )


_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*?)\s*$")
_SEPARATOR_RE = re.compile(r"---\s*")
# CommonMark HTML blocks of types 1 and 2: their content is raw HTML, so a
# fence-looking line inside them is text, not a code fence.
_HTML_BLOCK_START_RE = re.compile(r"^ {0,3}<(?:(pre|script|style|textarea)(?:\s|>|$)|!--)", re.IGNORECASE)
_HTML_BLOCK_END_RE = re.compile(r"</(?:pre|script|style|textarea)>", re.IGNORECASE)
_HTML_COMMENT_END_RE = re.compile(r"-->")


def _split_slides(body: str) -> list[str]:
    """Split a deck body into slide texts at ``---`` lines.

    A ``---`` on its own line (possibly with trailing whitespace) between two
    other lines separates slides, except inside a fenced code block, where it
    is code (e.g. a YAML or Markdown sample). If the fences look unbalanced
    (one is never closed, or a new opener appears inside an open fence), fall
    back to splitting at every ``---`` line so one typo cannot merge slides.
    """
    legacy = re.split(r"\n---\s*\n", body)
    slides: list[str] = []
    current: list[str] = []
    fence = ""
    html_end = None  # end pattern of the raw HTML block we are in, if any
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if not fence and html_end is None:
            html = _HTML_BLOCK_START_RE.match(line)
            if html:
                html_end = _HTML_BLOCK_END_RE if html.group(1) else _HTML_COMMENT_END_RE
        if html_end is not None:
            if html_end.search(line):
                html_end = None
            match = None
        else:
            match = _FENCE_RE.match(line)
        if match and match.group(1)[0] == "`" and "`" in match.group(2):
            match = None  # a backtick fence's info string has no backticks
        if fence:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                if match.group(2):
                    return legacy  # an opener where a closer belongs
                fence = ""
        elif match:
            fence = match.group(1)
        elif 0 < i < len(lines) - 1 and _SEPARATOR_RE.fullmatch(line):
            slides.append("\n".join(current))
            current = []
            html_end = None  # each slide renders on its own, so an open HTML block ends here
            continue
        current.append(line)
    if fence:
        return legacy
    slides.append("\n".join(current))
    return slides


def parse_markdown(text: str) -> Deck:
    """Parse a full markdown file into a Deck."""
    metadata, body = parse_frontmatter(text)

    custom_css = metadata.get("custom_css", "")
    custom_css_path = ""
    if is_stylesheet_path(custom_css):
        custom_css_path = str(custom_css).strip()
        custom_css = ""

    deck = Deck(
        title=metadata.get("title", "Untitled"),
        author=metadata.get("author", ""),
        date=str(metadata.get("date", "")),
        theme=metadata.get("theme", "default"),
        aspect_ratio=str(metadata.get("aspect_ratio", "16:9")),
        custom_css=custom_css,
        custom_css_path=custom_css_path,
        footer=metadata.get("footer", None),
        fonts=metadata.get("fonts", None),
        bibliography=metadata.get("bibliography", ""),
        citation_style=metadata.get("citation_style", "author-year"),
        citation_order=metadata.get("citation_order", "auto"),
        figure_captions=bool(metadata.get("figure_captions", False)),
        show_animations=bool(metadata.get("show_animations", True)),
        pptx=metadata.get("pptx") if isinstance(metadata.get("pptx"), dict) else None,
        chapters=metadata.get("chapters", True) is not False,
        chapter_bar=metadata.get("chapter_bar", False),
        url=str(metadata.get("url", "") or ""),
        share_image=metadata.get("share_image", False),
    )

    slide_texts = _split_slides(body)

    for slide_text in slide_texts:
        slide_text = slide_text.strip()
        if not slide_text:
            continue
        slide = parse_slide(slide_text)
        deck.slides.append(slide)

    return deck


def parse_file(path: str) -> Deck:
    """Parse a markdown file into a Deck."""
    from pathlib import Path

    md_path = Path(path)
    text = md_path.read_text(encoding="utf-8")
    deck = parse_markdown(text)

    # Resolve bibliography path relative to the markdown file
    if deck.bibliography and not Path(deck.bibliography).is_absolute():
        deck.bibliography = str(md_path.parent / deck.bibliography)
    # Relative figure paths (figure-title) resolve against the markdown file too.
    deck.source_dir = str(md_path.parent)

    return deck
