"""PDF export via system browser and print CSS."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _find_browser() -> str | None:
    """Find a headless-capable browser on the system."""
    # macOS application paths
    mac_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]

    # Check macOS application paths first
    for path in mac_paths:
        if os.path.isfile(path):
            return path

    # Check PATH for common browser commands
    for cmd in ["google-chrome", "chromium", "chromium-browser", "microsoft-edge", "brave"]:
        found = shutil.which(cmd)
        if found:
            return found

    return None


def _is_chromium_based(browser_path: str) -> bool:
    """Check if the browser is Chromium-based (supports --print-to-pdf)."""
    name = browser_path.lower()
    return any(x in name for x in ["chrome", "chromium", "edge", "brave"])


def export_pdf(input_path: str, output_path: str | None = None) -> str | None:
    """Export a presentation to PDF using a system browser.

    Returns the output path on success, or None if no browser was found.
    """
    from colloquium.build import build_file

    input_path = str(Path(input_path).resolve())

    # Build HTML first
    html_path = build_file(input_path)

    if output_path is None:
        output_path = str(Path(input_path).with_suffix(".pdf"))

    html_url = f"file://{Path(html_path).resolve()}"

    browser = _find_browser()
    if browser is None:
        return None

    if not _is_chromium_based(browser):
        return None

    # Use Chromium's headless print-to-pdf
    # 10in x 5.625in = 16:9 landscape, matching @page size in print CSS
    cmd = [
        browser,
        "--headless",
        "--disable-gpu",
        f"--print-to-pdf={output_path}",
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        "--no-margins",
        f"--paper-width=10",
        f"--paper-height=5.625",
        html_url,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return None

    if Path(output_path).exists():
        # Optional ghostscript compression
        _compress_pdf(output_path)
        return output_path

    return None


def _compress_pdf(pdf_path: str) -> None:
    """Compress PDF with ghostscript if available."""
    gs = shutil.which("gs")
    if not gs:
        return

    compressed = pdf_path + ".compressed"
    cmd = [
        gs,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dPDFSETTINGS=/prepress",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={compressed}",
        pdf_path,
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=30, check=True)
        # Only replace if compressed is smaller
        if Path(compressed).stat().st_size < Path(pdf_path).stat().st_size:
            os.replace(compressed, pdf_path)
        else:
            os.unlink(compressed)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError):
        if os.path.exists(compressed):
            os.unlink(compressed)
