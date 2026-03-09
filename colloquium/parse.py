"""Markdown parser — converts markdown files into Deck objects."""

from __future__ import annotations

import re

import yaml

from colloquium.deck import Deck
from colloquium.slide import Slide


# Directive patterns: <!-- key: value -->
_DIRECTIVE_RE = re.compile(
    r"<!--\s*(layout|class|style|notes|title|align|valign|columns|rows|padding|size|cite|cite-left|cite-right|footnote|footnote-right|footnotes|img-align|img-valign|img-fill|img-overflow)\s*:\s*(.*?)\s*-->",
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

    # Find closing ---
    end = text.find("---", 3)
    if end == -1:
        return {}, text

    yaml_str = text[3:end].strip()
    remaining = text[end + 3 :].strip()

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

    # Parse remaining content for title
    lines = remaining.strip().splitlines()
    content_parts = []

    for line in lines:
        stripped = line.strip()
        if not title and stripped.startswith("# "):
            title = stripped[2:].strip()
            if layout == "content":
                layout = "title"
        elif not title and stripped.startswith("## "):
            title = stripped[3:].strip()
        else:
            content_parts.append(line)

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


def parse_markdown(text: str) -> Deck:
    """Parse a full markdown file into a Deck."""
    metadata, body = parse_frontmatter(text)

    deck = Deck(
        title=metadata.get("title", "Untitled"),
        author=metadata.get("author", ""),
        date=str(metadata.get("date", "")),
        theme=metadata.get("theme", "default"),
        aspect_ratio=str(metadata.get("aspect_ratio", "16:9")),
        custom_css=metadata.get("custom_css", ""),
        footer=metadata.get("footer", None),
        fonts=metadata.get("fonts", None),
        bibliography=metadata.get("bibliography", ""),
        citation_style=metadata.get("citation_style", "author-year"),
        citation_order=metadata.get("citation_order", "auto"),
        figure_captions=bool(metadata.get("figure_captions", False)),
    )

    # Split on --- slide separators (horizontal rules)
    # A --- on its own line (possibly with whitespace) separates slides
    slide_texts = re.split(r"\n---\s*\n", body)

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

    return deck
