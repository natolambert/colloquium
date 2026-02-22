"""Dev server with file watching and auto-rebuild."""

from __future__ import annotations

import http.server
import os
import socketserver
import threading
import time
from pathlib import Path


def _watch_and_rebuild(input_path: str, output_path: str, stop_event: threading.Event):
    """Poll for file changes and rebuild on modification."""
    from colloquium.build import build_file

    last_mtime = 0.0

    while not stop_event.is_set():
        try:
            mtime = os.stat(input_path).st_mtime
            if mtime > last_mtime:
                if last_mtime > 0:
                    print(f"  Rebuilding {input_path}...")
                build_file(input_path, output_path)
                last_mtime = mtime
        except OSError:
            pass
        except Exception as e:
            print(f"  Build error: {e}")

        stop_event.wait(timeout=0.5)


def serve(input_path: str, port: int = 8080, output_dir: str | None = None):
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

    handler = http.server.SimpleHTTPRequestHandler

    # Suppress request logging
    class QuietHandler(handler):
        def log_message(self, format, *args):
            pass

    try:
        with socketserver.TCPServer(("", port), QuietHandler) as httpd:
            url = f"http://localhost:{port}/{stem}.html"
            print(f"  Serving at {url}")
            print(f"  Watching for changes... (Ctrl+C to stop)")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down.")
    finally:
        stop_event.set()
        watcher.join(timeout=2)
