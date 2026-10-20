"""Share images: Open Graph tags from frontmatter and the first-slide capture."""

from pathlib import Path

import pytest

import colloquium.export as export_mod
from colloquium.build import build_deck, build_file, share_image_name
from colloquium.deck import Deck
from colloquium.export import export_share_image
from colloquium.parse import parse_markdown


def test_no_share_tags_by_default():
    html = build_deck(Deck(title="Plain"))
    assert "og:image" not in html
    assert "og:title" not in html


def test_auto_share_image_resolves_against_the_deck_url(tmp_path):
    src = tmp_path / "lecture.md"
    src.write_text(
        '---\ntitle: "Open Weight Language Models"\nauthor: "Nathan Lambert"\ndate: "October 2026"\n'
        'url: "https://example.com/slides/2026/harvard/lecture.html"\nshare_image: auto\n---\n\n# Open Weight Language Models\n'
    )
    out = tmp_path / "lecture.html"
    build_file(str(src), str(out))
    html = out.read_text()
    assert '<meta property="og:image" content="https://example.com/slides/2026/harvard/lecture-share.png">' in html
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert '<meta property="og:title" content="Open Weight Language Models">' in html
    assert '<meta property="og:description" content="Nathan Lambert · October 2026">' in html
    assert '<link rel="canonical" href="https://example.com/slides/2026/harvard/lecture.html">' in html


def test_explicit_share_image_path_and_absolute_url():
    deck = parse_markdown('---\ntitle: "T"\nshare_image: assets/cover.png\n---\n\n## S\n')
    html = build_deck(deck)
    assert '<meta property="og:image" content="assets/cover.png">' in html
    deck = parse_markdown('---\ntitle: "T"\nshare_image: https://cdn.example.com/cover.png\nurl: "https://example.com/deck.html"\n---\n\n## S\n')
    html = build_deck(deck)
    assert '<meta property="og:image" content="https://cdn.example.com/cover.png">' in html


def test_url_without_image_gets_canonical_and_summary_card():
    html = build_deck(Deck(title="T", url="https://example.com/deck.html"))
    assert '<meta property="og:url" content="https://example.com/deck.html">' in html
    assert '<meta name="twitter:card" content="summary">' in html
    assert "og:image" not in html


def test_share_image_round_trips_in_markdown():
    deck = parse_markdown('---\ntitle: "T"\nurl: "https://example.com/d.html"\nshare_image: auto\n---\n\n## S\n')
    md = deck.to_markdown()
    assert 'url: "https://example.com/d.html"' in md
    assert "share_image: auto" in md


def test_share_image_name():
    assert share_image_name("lecture") == "lecture-share.png"


def test_export_share_image_captures_first_slide(monkeypatch, tmp_path):
    src = tmp_path / "talk.md"
    src.write_text('---\ntitle: "T"\nshare_image: auto\n---\n\n# Title\n\n---\n\n## Second\n')
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        shot = next(arg for arg in cmd if arg.startswith("--screenshot=")).split("=", 1)[1]
        Path(shot).write_bytes(b"\x89PNG fake")

    monkeypatch.setattr(export_mod, "_find_browser", lambda: "/fake/chrome")
    monkeypatch.setattr(export_mod.subprocess, "run", fake_run)
    result = export_share_image(str(src))
    assert result == str(tmp_path / "talk-share.png")
    assert Path(result).exists()
    cmd = seen["cmd"]
    assert "--window-size=1280,720" in cmd
    assert "--force-device-scale-factor=2" in cmd
    assert cmd[-1].endswith("/talk.html?capture#1")


def test_export_share_image_without_browser(monkeypatch, tmp_path):
    src = tmp_path / "talk.md"
    src.write_text('---\ntitle: "T"\n---\n\n# Title\n')
    monkeypatch.setattr(export_mod, "_find_browser", lambda: None)
    assert export_share_image(str(src)) is None
