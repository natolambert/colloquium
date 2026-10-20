"""Tests for live-reload stability checks."""

import http.server
import os
import socket
import socketserver
import threading
from urllib.request import urlopen

import pytest

from colloquium.serve import (
    _LIVE_RELOAD_SCRIPT,
    _VERSION_PATH,
    _inject_live_reload,
    _make_request_handler,
    _build_snapshot_html,
    _create_http_server,
    _has_unclosed_fenced_code_block,
    _has_unclosed_html_comment,
    _read_quiescent_source,
    _read_stable_source_snapshot,
    _render_matches_deck_structure,
    _source_text_is_stable_for_rebuild,
    PortUnavailableError,
)
from colloquium.parse import parse_markdown


class TestServeSnapshotAndValidation:
    def test_source_text_stability_uses_balance_checks(self):
        assert _source_text_is_stable_for_rebuild("## Slide\n\nBody")
        assert not _source_text_is_stable_for_rebuild("<!-- columns: 50/50\n## Slide")
        assert not _source_text_is_stable_for_rebuild("```conversation\nmessages: []")

    def test_render_structure_accepts_matching_columns_and_rows(self):
        text = (
            "<!-- columns: 50/50 -->\n## Cols\n\nA\n\n|||\n\nB\n\n---\n"
            "<!-- rows: 40/60 -->\n## Rows\n\nTop\n\n===\n\nBottom"
        )
        deck = parse_markdown(text)
        html = _build_snapshot_html("/tmp/slides.md", text)

        assert _render_matches_deck_structure(deck, html)

    def test_render_structure_handles_slides_after_references(self, tmp_path):
        bib = tmp_path / "refs.bib"
        bib.write_text(
            "@article{key2024,\n  title={A Paper},\n  author={Author, A.},\n  year={2024}\n}\n",
            encoding="utf-8",
        )
        text = (
            "---\nbibliography: refs.bib\n---\n\n"
            "## Main\n\nCites [@key2024]\n\n---\n\n"
            "<!-- after: references -->\n<!-- columns: 40/60 -->\n## Extra\n\nA\n\n|||\n\nB"
        )
        source = tmp_path / "slides.md"
        source.write_text(text, encoding="utf-8")
        deck = parse_markdown(text)
        html = _build_snapshot_html(str(source), text)

        assert "colloquium-references-slide" in html
        assert _render_matches_deck_structure(deck, html)

    def test_render_structure_keeps_slides_that_mention_the_references_class(self, tmp_path):
        text = (
            "<!-- columns: 50/50 -->\n## Cols\n\nSee `colloquium-references-slide` "
            "and <div class=\"slide-content colloquium-references-slide\">x</div>\n\n|||\n\nB"
        )
        deck = parse_markdown(text)
        html = _build_snapshot_html(str(tmp_path / "slides.md"), text)

        assert len(deck.slides) == 1
        assert _render_matches_deck_structure(deck, html)

    def test_render_structure_rejects_missing_column_wrapper(self):
        text = "<!-- columns: 50/50 -->\n## Cols\n\nA\n\n|||\n\nB"
        deck = parse_markdown(text)
        html = '<section><h2>Cols</h2><div class="slide-content"><div class="col">A</div></div></section>'

        assert not _render_matches_deck_structure(deck, html)

    def test_render_structure_rejects_missing_rows_wrapper(self):
        text = "<!-- rows: 40/60 -->\n## Rows\n\nTop\n\n===\n\nBottom"
        deck = parse_markdown(text)
        html = '<section><h2>Rows</h2><div class="slide-content">Top Bottom</div></section>'

        assert not _render_matches_deck_structure(deck, html)

    def test_stable_source_snapshot_accepts_matching_reads(self, monkeypatch):
        reads = iter(["## Slide\n\nBody", "## Slide\n\nBody"])
        monkeypatch.setattr(
            "colloquium.serve._read_quiescent_source",
            lambda path: next(reads),
        )

        assert _read_stable_source_snapshot("slides.md", settle_seconds=0) == "## Slide\n\nBody"

    def test_stable_source_snapshot_rejects_changed_reads(self, monkeypatch):
        reads = iter(["## Slide\n\nBody", "## Slide\n\nBody changed"])
        monkeypatch.setattr(
            "colloquium.serve._read_quiescent_source",
            lambda path: next(reads),
        )

        assert _read_stable_source_snapshot("slides.md", settle_seconds=0) is None


class TestServeStabilityChecks:
    def test_closed_html_comment(self):
        text = "<!-- columns: 50/50 -->\n## Slide\n\nContent"
        assert not _has_unclosed_html_comment(text)

    def test_unclosed_html_comment(self):
        text = "<!-- footnote: editing in progress\n## Slide\n\nContent"
        assert _has_unclosed_html_comment(text)

    def test_arrow_in_content_does_not_block_rebuild(self):
        """A --> in content must NOT be treated as an unclosed comment."""
        text = "<!-- columns: 40/60 -->\n## Slide\n\nData --> Model --> Output"
        assert not _has_unclosed_html_comment(text)

    def test_stray_close_token_without_open(self):
        text = "A --> B\n\n## Slide"
        assert not _has_unclosed_html_comment(text)

    def test_no_comments_at_all(self):
        text = "## Just a slide\n\nSome content"
        assert not _has_unclosed_html_comment(text)

    def test_multiple_directives_with_arrows(self):
        text = (
            "<!-- columns: 40/60 -->\n"
            "<!-- class: highlight -->\n"
            "## Slide\n\n"
            "A --> B --> C\n\n"
            "|||\n\n"
            "![image](img.png)"
        )
        assert not _has_unclosed_html_comment(text)

    def test_unclosed_comment_after_closed_ones(self):
        text = "<!-- columns: 40/60 -->\n## Slide\n\n<!-- editing"
        assert _has_unclosed_html_comment(text)

    def test_balanced_backtick_fences(self):
        text = "```conversation\nmessages: []\n```\n\n## Slide"
        assert not _has_unclosed_fenced_code_block(text)

    def test_unclosed_backtick_fences(self):
        text = "```conversation\nmessages: []\n\n## Slide"
        assert _has_unclosed_fenced_code_block(text)

    def test_balanced_tilde_fences(self):
        text = "~~~python\nprint('hi')\n~~~\n\n## Slide"
        assert not _has_unclosed_fenced_code_block(text)

    def test_unclosed_tilde_fences(self):
        text = "~~~python\nprint('hi')\n\n## Slide"
        assert _has_unclosed_fenced_code_block(text)


class TestServePortBinding:
    def test_create_http_server_binds_loopback_with_so_reuseaddr_enabled(self):
        httpd = _create_http_server(0, http.server.SimpleHTTPRequestHandler)

        try:
            assert httpd.allow_reuse_address is True
            assert httpd.server_address[0] == "127.0.0.1"
            assert httpd.socket.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) != 0
        finally:
            httpd.server_close()

    def test_create_http_server_rejects_port_already_in_use(self):
        class NoopHandler(socketserver.BaseRequestHandler):
            def handle(self):
                pass

        with socketserver.TCPServer(("127.0.0.1", 0), NoopHandler) as existing:
            port = existing.server_address[1]

            with pytest.raises(
                PortUnavailableError,
                match=rf"Port {port} is unavailable",
            ):
                _create_http_server(port, http.server.SimpleHTTPRequestHandler)


class TestServeLiveReload:
    @staticmethod
    def _start(tmp_path, live_reload):
        deck = tmp_path / "slides.html"
        deck.write_text("<html><body><h1>Hi</h1></body></html>", encoding="utf-8")
        httpd = _create_http_server(0, _make_request_handler(str(tmp_path), str(deck), live_reload))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd, deck, f"http://127.0.0.1:{httpd.server_address[1]}"

    def test_inject_live_reload_places_script_before_body_end(self):
        assert _inject_live_reload(b"<body>x</body></html>") == (
            b"<body>x" + _LIVE_RELOAD_SCRIPT.encode() + b"</body></html>"
        )
        assert _inject_live_reload(b"<p>x</p>") == b"<p>x</p>" + _LIVE_RELOAD_SCRIPT.encode()

    def test_served_deck_reloads_when_the_build_changes(self, tmp_path):
        httpd, deck, base = self._start(tmp_path, live_reload=True)
        try:
            html = urlopen(base + "/slides.html").read().decode("utf-8")
            assert _LIVE_RELOAD_SCRIPT in html
            assert html.endswith("</body></html>")
            assert _LIVE_RELOAD_SCRIPT not in deck.read_text(encoding="utf-8")

            first = urlopen(base + _VERSION_PATH).read().decode("ascii")
            os.utime(deck, ns=(1_000_000_000, 2_000_000_000))
            second = urlopen(base + _VERSION_PATH).read().decode("ascii")
            assert first != second
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_no_reload_serves_the_file_untouched(self, tmp_path):
        httpd, deck, base = self._start(tmp_path, live_reload=False)
        try:
            html = urlopen(base + "/slides.html").read().decode("utf-8")
            assert html == deck.read_text(encoding="utf-8")
            with pytest.raises(Exception):
                urlopen(base + _VERSION_PATH)
        finally:
            httpd.shutdown()
            httpd.server_close()
