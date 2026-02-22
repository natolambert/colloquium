"""Tests for the Deck class."""

import tempfile
from pathlib import Path

from colloquium.deck import Deck
from colloquium.slide import Slide


class TestSlide:
    def test_default_values(self):
        slide = Slide()
        assert slide.title == ""
        assert slide.content == ""
        assert slide.layout == "content"
        assert slide.classes == []
        assert slide.style == ""

    def test_is_title_slide(self):
        slide = Slide(layout="title")
        assert slide.is_title_slide is True

        slide = Slide(layout="content")
        assert slide.is_title_slide is False

    def test_to_markdown(self):
        slide = Slide(title="Hello", content="World", layout="content")
        md = slide.to_markdown()
        assert "## Hello" in md
        assert "World" in md

    def test_to_markdown_title_slide(self):
        slide = Slide(title="Title", layout="title")
        md = slide.to_markdown()
        assert "# Title" in md

    def test_to_markdown_with_directives(self):
        slide = Slide(
            title="S",
            content="C",
            layout="two-column",
            classes=["highlight"],
            style="background: red",
            speaker_notes="Note here",
        )
        md = slide.to_markdown()
        assert "<!-- layout: two-column -->" in md
        assert "<!-- class: highlight -->" in md
        assert "<!-- style: background: red -->" in md
        assert "<!-- notes: Note here -->" in md


class TestDeck:
    def test_create_deck(self):
        deck = Deck(title="Test", author="Me")
        assert deck.title == "Test"
        assert deck.author == "Me"
        assert deck.slides == []

    def test_add_slide(self):
        deck = Deck(title="Test")
        slide = deck.add_slide(title="S1", content="C1")
        assert len(deck.slides) == 1
        assert slide.title == "S1"
        assert isinstance(slide, Slide)

    def test_add_title_slide(self):
        deck = Deck(title="My Talk", author="Author", date="2026-01-01")
        slide = deck.add_title_slide(subtitle="A subtitle")
        assert slide.layout == "title"
        assert slide.title == "My Talk"
        assert "A subtitle" in slide.content
        assert "Author" in slide.content

    def test_insert_figure(self):
        deck = Deck(title="Test")
        slide = deck.insert_figure(
            src="fig1.png",
            alt="Figure 1",
            caption="A great figure",
            slide_title="Results",
        )
        assert slide.title == "Results"
        assert "![Figure 1](fig1.png)" in slide.content
        assert "*A great figure*" in slide.content

    def test_set_theme(self):
        deck = Deck(title="Test")
        deck.set_theme("dark")
        assert deck.theme == "dark"

    def test_to_markdown(self):
        deck = Deck(title="Test", author="Me")
        deck.add_slide(title="S1", content="Content")
        md = deck.to_markdown()
        assert "title: Test" in md
        assert "author: Me" in md
        assert "## S1" in md
        assert "Content" in md

    def test_build(self):
        deck = Deck(title="Build Test")
        deck.add_slide(title="Hello", content="World")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = deck.build(tmpdir)
            assert Path(result).exists()
            html = Path(result).read_text()
            assert "Build Test" in html
            assert "Hello" in html

    def test_roundtrip(self):
        """Create a deck, serialize to markdown, parse back, verify."""
        from colloquium.parse import parse_markdown

        deck = Deck(title="Roundtrip", author="Test")
        deck.add_title_slide(title="Roundtrip", subtitle="Testing")
        deck.add_slide(title="Slide 2", content="Some content")

        md = deck.to_markdown()
        deck2 = parse_markdown(md)

        assert deck2.title == "Roundtrip"
        assert deck2.author == "Test"
        assert len(deck2.slides) == 2
