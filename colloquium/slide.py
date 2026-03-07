"""Slide data model."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Slide:
    """A single presentation slide."""

    title: str = ""
    content: str = ""
    layout: str = "content"
    speaker_notes: str = ""
    classes: list[str] = field(default_factory=list)
    style: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def is_title_slide(self) -> bool:
        return self.layout == "title" or self.layout.startswith("title-")

    def to_markdown(self) -> str:
        """Serialize this slide back to markdown."""
        parts = []

        if self.layout != "content":
            parts.append(f"<!-- layout: {self.layout} -->")
        if self.classes:
            parts.append(f"<!-- class: {' '.join(self.classes)} -->")
        if self.style:
            parts.append(f"<!-- style: {self.style} -->")

        if self.title:
            prefix = "# " if self.is_title_slide else "## "
            parts.append(f"{prefix}{self.title}")

        if self.content:
            parts.append(self.content)

        if self.speaker_notes:
            parts.append(f"<!-- notes: {self.speaker_notes} -->")

        return "\n\n".join(parts)
