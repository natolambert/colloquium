"""Dev server with file watching and auto-rebuild."""

from __future__ import annotations

import http.server
import os
import re
import socketserver
import threading
import time
from pathlib import Path


_COMMENT_OPEN_RE = re.compile(r"<!--")
_COMMENT_CLOSE_RE = re.compile(r"-->")
_FENCE_LINE_RE = re.compile(r"^(?:```|~~~)", re.MULTILINE)
_SECTION_RE = re.compile(r"<section\b[^>]*>(.*?)</section>", re.DOTALL)


def _has_unclosed_html_comment(text: str) -> bool:
    """Return True if the text ends inside an unclosed <!-- block.

    Only checks whether the *last* ``<!--`` has a matching ``-->``.
    Stray ``-->`` in content (e.g. arrow notation) is harmless.
    """
    last_open = -1
    for m in _COMMENT_OPEN_RE.finditer(text):
        last_open = m.start()
    if last_open == -1:
        return False
    return _COMMENT_CLOSE_RE.search(text, last_open + 4) is None


def _has_unclosed_fenced_code_block(text: str) -> bool:
    """Return True if the text ends inside an unclosed fenced code block."""
    backticks = 0
    tildes = 0
    for match in _FENCE_LINE_RE.finditer(text):
        token = match.group(0)
        if token.startswith("```"):
            backticks += 1
        else:
            tildes += 1
    return backticks % 2 != 0 or tildes % 2 != 0


def _source_text_is_stable_for_rebuild(text: str) -> bool:
    """Return True when a source snapshot is in a stable enough state to rebuild."""
    if not text.strip():
        return False
    return not _has_unclosed_html_comment(text) and not _has_unclosed_fenced_code_block(text)


def _read_quiescent_source(input_path: str) -> str | None:
    """Read a source snapshot only if the file stays unchanged during the read."""
    try:
        before = os.stat(input_path)
        text = Path(input_path).read_text(encoding="utf-8")
        after = os.stat(input_path)
    except OSError:
        return None

    before_sig = (before.st_mtime_ns, before.st_size)
    after_sig = (after.st_mtime_ns, after.st_size)
    if before_sig != after_sig:
        return None
    return text


def _read_stable_source_snapshot(input_path: str, settle_seconds: float = 0.06) -> str | None:
    """Return source text only when two consecutive quiescent reads match.

    This avoids promoting transient editor states that happen to be syntactically
    balanced but are still mid-save or mid-rename.
    """
    first = _read_quiescent_source(input_path)
    if first is None:
        return None
    time.sleep(settle_seconds)
    second = _read_quiescent_source(input_path)
    if second is None or second != first:
        return None
    return second


def _render_matches_deck_structure(deck, html: str) -> bool:
    """Reject broken renders that lost row/column wrappers during live editing."""
    sections = _SECTION_RE.findall(html)
    if len(sections) < len(deck.slides):
        return False

    for slide, section_html in zip(deck.slides, sections):
        has_columns = any(cls.startswith("cols-") for cls in slide.classes)
        has_rows = any(cls.startswith("rows-") for cls in slide.classes)
        if has_columns and "colloquium-grid" not in section_html:
            return False
        if has_rows and "colloquium-rows" not in section_html:
            return False
    return True


def _build_snapshot_html(input_path: str, text: str) -> str:
    """Build HTML from a single source snapshot without rereading the file."""
    from colloquium.build import build_deck
    from colloquium.parse import parse_markdown

    deck = parse_markdown(text)
    if deck.bibliography and not Path(deck.bibliography).is_absolute():
        deck.bibliography = str(Path(input_path).parent / deck.bibliography)
    html = build_deck(deck)
    if not _render_matches_deck_structure(deck, html):
        raise ValueError("rendered HTML failed structural validation")
    return html


# After this many seconds of "unstable", build anyway to avoid getting
# permanently stuck.
_MAX_STABLE_WAIT = 3.0
_DEFAULT_HOST = "127.0.0.1"


class PortUnavailableError(RuntimeError):
    """Raised when the dev server cannot bind to the requested port."""

    def __init__(self, port: int, cause: OSError):
        detail = cause.strerror or str(cause)
        super().__init__(f"Port {port} is unavailable: {detail}")


def _watch_and_rebuild(input_path: str, output_path: str, stop_event: threading.Event):
    """Poll for file changes and rebuild on modification."""
    from colloquium.build import _write_text_atomic

    last_mtime = 0.0
    pending_mtime = 0.0
    pending_since = 0.0
    debounce_seconds = 0.35
    waiting_for_stable_source = False
    unstable_since = 0.0

    while not stop_event.is_set():
        try:
            mtime = os.stat(input_path).st_mtime
            if mtime > max(last_mtime, pending_mtime):
                pending_mtime = mtime
                pending_since = time.monotonic()

            if pending_mtime and time.monotonic() - pending_since >= debounce_seconds:
                source_snapshot = _read_stable_source_snapshot(input_path)
                stable = (
                    source_snapshot is not None
                    and _source_text_is_stable_for_rebuild(source_snapshot)
                )
                timed_out = (
                    unstable_since > 0
                    and time.monotonic() - unstable_since >= _MAX_STABLE_WAIT
                )

                if not stable and not timed_out:
                    if not waiting_for_stable_source:
                        print("  Waiting for stable source before rebuild...")
                        waiting_for_stable_source = True
                        unstable_since = time.monotonic()
                else:
                    if timed_out and not stable:
                        print("  Stability wait timed out, rebuilding anyway.")
                    if last_mtime > 0:
                        print(f"  Rebuilding {input_path}...")
                    snapshot = source_snapshot
                    if snapshot is None:
                        snapshot = Path(input_path).read_text(encoding="utf-8")
                    html = _build_snapshot_html(input_path, snapshot)
                    _write_text_atomic(output_path, html)
                    last_mtime = pending_mtime
                    pending_mtime = 0.0
                    pending_since = 0.0
                    waiting_for_stable_source = False
                    unstable_since = 0.0
        except OSError:
            pass
        except Exception as e:
            print(f"  Build error: {e}")
            last_mtime = pending_mtime or last_mtime
            pending_mtime = 0.0
            pending_since = 0.0
            waiting_for_stable_source = False
            unstable_since = 0.0

        stop_event.wait(timeout=0.15)


def _create_http_server(port: int, handler):
    """Create the HTTP server bound to loopback with address reuse enabled.

    This preserves immediate restarts after ``TIME_WAIT`` while still
    rejecting the macOS overlap case caused by wildcard binds.
    """

    class PresentationTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    try:
        return PresentationTCPServer((_DEFAULT_HOST, port), handler)
    except OSError as exc:
        raise PortUnavailableError(port, exc) from exc


def serve(input_path: str, port: int = 8090, output_dir: str | None = None):
    """Serve a presentation with live rebuilding on file changes."""
    from colloquium.build import build_file

    input_path = str(Path(input_path).resolve())
    stem = Path(input_path).stem

    if output_dir:
        serve_dir = str(Path(output_dir).resolve())
    else:
        serve_dir = str(Path(input_path).parent)

    output_path = os.path.join(serve_dir, f"{stem}.html")

    # Initial build
    print(f"Building {input_path}...")
    build_file(input_path, output_path)
    print(f"  Output: {output_path}")

    # Start file watcher in background
    stop_event = threading.Event()
    watcher = threading.Thread(
        target=_watch_and_rebuild,
        args=(input_path, output_path, stop_event),
        daemon=True,
    )
    watcher.start()

    # Serve from the output directory
    os.chdir(serve_dir)

    # Suppress request logging
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    try:
        with _create_http_server(port, QuietHandler) as httpd:
            url = f"http://{_DEFAULT_HOST}:{port}/{stem}.html"
            print(f"  Serving at {url}")
            print(f"  Watching for changes... (Ctrl+C to stop)")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down.")
    finally:
        stop_event.set()
        watcher.join(timeout=2)
