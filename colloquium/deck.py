"""Deck class — the agent-facing API for building presentations."""

from __future__ import annotations

import os
from pathlib import Path

from colloquium.slide import Slide


class Deck:
    """A presentation deck composed of slides."""

    def __init__(
        self,
        title: str = "Untitled",
        author: str = "",
        date: str = "",
        theme: str = "default",
        aspect_ratio: str = "16:9",
        custom_css: str = "",
        footer: dict | None = None,
        fonts: dict | None = None,
        bibliography: str = "",
        citation_style: str = "author-year",
        citation_order: str = "auto",
    ):
        self.title = title
        self.author = author
        self.date = date
        self.theme = theme
        self.aspect_ratio = aspect_ratio
        self.custom_css = custom_css
        self.footer = footer
        self.fonts = fonts
        self.bibliography = bibliography
        self.citation_style = citation_style
        self.citation_order = citation_order
        self.slides: list[Slide] = []

    def add_slide(
        self,
        title: str = "",
        content: str = "",
        layout: str = "content",
        speaker_notes: str = "",
        classes: list[str] | None = None,
        style: str = "",
        **metadata,
    ) -> Slide:
        """Add a slide to the deck and return it."""
        slide = Slide(
            title=title,
            content=content,
            layout=layout,
            speaker_notes=speaker_notes,
            classes=classes or [],
            style=style,
            metadata=metadata,
        )
        self.slides.append(slide)
        return slide

    def add_title_slide(
        self,
        title: str = "",
        subtitle: str = "",
        author: str = "",
        date: str = "",
    ) -> Slide:
        """Add a title slide to the deck."""
        parts = []
        if subtitle:
            parts.append(subtitle)
        # Use deck-level author/date as fallback
        slide_author = author or self.author
        slide_date = date or self.date
        if slide_author:
            parts.append(slide_author)
        if slide_date:
            parts.append(slide_date)
        return self.add_slide(
            title=title or self.title,
            content="\n\n".join(parts),
            layout="title",
        )

    def insert_figure(
        self,
        src: str,
        alt: str = "",
        caption: str = "",
        slide_title: str = "",
    ) -> Slide:
        """Add a slide with a figure."""
        parts = [f"![{alt}]({src})"]
        if caption:
            parts.append(f"*{caption}*")
        return self.add_slide(
            title=slide_title,
            content="\n\n".join(parts),
            layout="content",
        )

    def set_theme(self, theme: str) -> None:
        """Set the deck theme."""
        self.theme = theme

    def build(self, output_dir: str = ".") -> str:
        """Build the deck to HTML and return the output path."""
        from colloquium.build import build_deck

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate a filename from the deck title
        safe_title = self.title.lower().replace(" ", "-")
        safe_title = "".join(c for c in safe_title if c.isalnum() or c == "-")
        filename = f"{safe_title or 'presentation'}.html"
        filepath = output_path / filename

        html = build_deck(self)
        filepath.write_text(html, encoding="utf-8")
        return str(filepath)

    def to_markdown(self) -> str:
        """Serialize the deck back to markdown format."""
        lines = ["---"]
        lines.append(f"title: {self.title}")
        if self.author:
            lines.append(f"author: {self.author}")
        if self.date:
            lines.append(f"date: {self.date}")
        if self.theme != "default":
            lines.append(f"theme: {self.theme}")
        if self.aspect_ratio != "16:9":
            lines.append(f"aspect_ratio: {self.aspect_ratio}")
        if self.custom_css:
            lines.append(f"custom_css: {self.custom_css}")
        if self.footer:
            lines.append("footer:")
            for key in ("left", "center", "right"):
                if key in self.footer:
                    lines.append(f"  {key}: \"{self.footer[key]}\"")
        if self.fonts:
            lines.append("fonts:")
            for key in ("heading", "body"):
                if key in self.fonts:
                    lines.append(f"  {key}: \"{self.fonts[key]}\"")
        if self.bibliography:
            lines.append(f"bibliography: {self.bibliography}")
        if self.citation_style != "author-year":
            lines.append(f"citation_style: {self.citation_style}")
        if self.citation_order != "auto":
            lines.append(f"citation_order: {self.citation_order}")
        lines.append("---")

        for slide in self.slides:
            lines.append("")
            lines.append("---")
            lines.append("")
            lines.append(slide.to_markdown())

        return "\n".join(lines)
