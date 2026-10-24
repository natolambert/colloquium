"""Dev server with file watching and auto-rebuild."""

from __future__ import annotations

import http.server
import os
import re
import socketserver
import threading
import time
from pathlib import Path
from urllib.parse import unquote


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
    # The build renders regular slides, then any generated References pages,
    # then ``after: references`` slides. Pair source slides with sections by
    # position from both ends, so the generated pages in the middle (which have
    # no source slide) are skipped without inspecting section content.
    sections = _SECTION_RE.findall(html)
    main_slides = [slide for slide in deck.slides if slide.metadata.get("after") != "references"]
    post_slides = [slide for slide in deck.slides if slide.metadata.get("after") == "references"]
    if len(sections) < len(main_slides) + len(post_slides):
        return False
    pairs = list(zip(main_slides, sections[:len(main_slides)]))
    if post_slides:
        pairs += list(zip(post_slides, sections[len(sections) - len(post_slides):]))

    for slide, section_html in pairs:
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
    deck.source_dir = str(Path(input_path).parent)
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


def _stylesheet_path(input_path: str) -> str | None:
    """The deck's ``custom_css`` file, resolved next to the deck, or None."""
    from colloquium.parse import is_stylesheet_path, parse_frontmatter

    try:
        metadata, _ = parse_frontmatter(Path(input_path).read_text(encoding="utf-8"))
    except Exception:  # a half-saved frontmatter must not stop the watcher
        return None
    value = metadata.get("custom_css", "")
    if not is_stylesheet_path(value):
        return None
    css_path = Path(str(value).strip())
    if not css_path.is_absolute():
        css_path = Path(input_path).parent / css_path
    return str(css_path)


def _latest_mtime(*paths: str | None) -> float:
    """The newest modification time among the paths that exist."""
    latest = 0.0
    for path in paths:
        if not path:
            continue
        try:
            latest = max(latest, os.stat(path).st_mtime)
        except OSError:
            continue
    return latest


def _watch_and_rebuild(input_path: str, output_path: str, stop_event: threading.Event):
    """Poll for file changes and rebuild on modification.

    The deck's ``custom_css`` stylesheet (when the frontmatter names a .css
    file) is watched alongside the markdown, so editing either rebuilds.
    """
    from colloquium.build import _write_text_atomic

    stylesheet = _stylesheet_path(input_path)

    # serve() has just built the deck, so start from the source's current
    # mtime: a watcher seeded with 0 would rebuild the unchanged file once,
    # bump the output's mtime, and reload any tab that opened in the meantime.
    last_mtime = _latest_mtime(input_path, stylesheet)
    pending_mtime = 0.0
    pending_since = 0.0
    debounce_seconds = 0.35
    waiting_for_stable_source = False
    unstable_since = 0.0

    while not stop_event.is_set():
        try:
            mtime = _latest_mtime(input_path, stylesheet)
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
                        print("  Waiting for stable source before rebuild...", flush=True)
                        waiting_for_stable_source = True
                        unstable_since = time.monotonic()
                else:
                    if timed_out and not stable:
                        print("  Stability wait timed out, rebuilding anyway.", flush=True)
                    print(f"  Rebuilding {input_path}...", flush=True)
                    snapshot = source_snapshot
                    if snapshot is None:
                        snapshot = Path(input_path).read_text(encoding="utf-8")
                    html = _build_snapshot_html(input_path, snapshot)
                    _write_text_atomic(output_path, html)
                    # The frontmatter may have pointed at a different stylesheet.
                    stylesheet = _stylesheet_path(input_path)
                    last_mtime = pending_mtime
                    pending_mtime = 0.0
                    pending_since = 0.0
                    waiting_for_stable_source = False
                    unstable_since = 0.0
        except OSError:
            pass
        except Exception as e:
            print(f"  Build error: {e}", flush=True)
            last_mtime = pending_mtime or last_mtime
            pending_mtime = 0.0
            pending_since = 0.0
            waiting_for_stable_source = False
            unstable_since = 0.0

        stop_event.wait(timeout=0.15)


_VERSION_PATH = "/__colloquium/version"

# Injected into the served deck only (never into the file on disk). Polls the
# version endpoint and reloads when the build changes; the deck keeps the
# current slide in the URL hash, so the reload lands on the same slide.
_LIVE_RELOAD_SCRIPT = (
    "<script>(function(){var seen=null;function tick(){"
    "fetch('" + _VERSION_PATH + "',{cache:'no-store'}).then(function(r){return r.text();})"
    ".then(function(v){if(seen===null){seen=v;}else if(v!==seen){location.reload();}})"
    ".catch(function(){}).then(function(){setTimeout(tick,500);});}tick();})();</script>"
)


def _inject_live_reload(html: bytes) -> bytes:
    """Return the deck HTML with the reload script before </body>."""
    marker = b"</body>"
    index = html.rfind(marker)
    script = _LIVE_RELOAD_SCRIPT.encode("utf-8")
    if index == -1:
        return html + script
    return html[:index] + script + html[index:]


def _output_version(output_path: str) -> str:
    """Identify the current build by the output file's modification time."""
    try:
        return str(os.stat(output_path).st_mtime_ns)
    except OSError:
        return "0"


def _make_request_handler(serve_dir: str, output_path: str, live_reload: bool):
    """Build the request handler: static files, plus the reload hooks when enabled."""
    deck_name = os.path.basename(output_path)

    class PresentationHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=serve_dir, **kwargs)

        def log_message(self, format, *args):
            pass

        def _send_bytes(self, body: bytes, content_type: str):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not live_reload:
                return super().do_GET()
            path = unquote(self.path.split("?", 1)[0].split("#", 1)[0])
            if path == _VERSION_PATH:
                return self._send_bytes(_output_version(output_path).encode("ascii"), "text/plain")
            if path.lstrip("/") == deck_name:
                try:
                    html = Path(output_path).read_bytes()
                except OSError:
                    return super().do_GET()
                return self._send_bytes(_inject_live_reload(html), "text/html; charset=utf-8")
            return super().do_GET()

    return PresentationHandler


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


def serve(
    input_path: str,
    port: int = 8090,
    output_dir: str | None = None,
    live_reload: bool = True,
):
    """Serve a presentation with live rebuilding on file changes.

    With ``live_reload`` (the default) the served deck reloads itself in the
    browser after each rebuild, staying on the current slide.
    """
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

    handler = _make_request_handler(serve_dir, output_path, live_reload)

    try:
        with _create_http_server(port, handler) as httpd:
            url = f"http://{_DEFAULT_HOST}:{port}/{stem}.html"
            print(f"  Serving at {url}")
            if live_reload:
                print("  Watching for changes, the browser tab reloads on save (Ctrl+C to stop)")
            else:
                print("  Watching for changes... (Ctrl+C to stop)")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down.")
    finally:
        stop_event.set()
        watcher.join(timeout=2)
