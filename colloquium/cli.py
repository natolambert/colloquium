"""CLI entry point for colloquium."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _build(args):
    """Build a markdown file into an HTML presentation."""
    from colloquium.build import build_file

    input_path = args.file
    if not Path(input_path).exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_dir = args.output
        stem = Path(input_path).stem
        output_path = str(Path(output_dir) / f"{stem}.html")
    else:
        output_path = None  # build_file will default to same dir as input

    result = build_file(input_path, output_path)
    print(f"Built: {result}")


def _serve(args):
    """Serve a presentation with live reload."""
    from colloquium.serve import serve

    input_path = args.file
    if not Path(input_path).exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    serve(input_path, port=args.port)


def _export(args):
    """Export a presentation to PDF or PPTX."""
    input_path = args.file
    if not Path(input_path).exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    output_path = args.output

    if args.pptx:
        from colloquium.export import export_pptx

        try:
            result = export_pptx(input_path, output_path)
            print(f"Exported: {result}")
        except ImportError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        from colloquium.export import export_pdf

        result = export_pdf(input_path, output_path)

        if result:
            print(f"Exported: {result}")
        else:
            from colloquium.build import build_file

            html_path = build_file(input_path)
            print("No compatible browser found for headless PDF export.")
            print(f"HTML built at: {html_path}")
            print(f"Open it in a browser and use Cmd+P / Ctrl+P to print to PDF.")


def _capture(args):
    """Capture individual slides as PNG images."""
    from colloquium.export import capture_slides

    input_path = args.file
    if not Path(input_path).exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    result = capture_slides(input_path, args.output, slide=args.slide)

    if result is None:
        print("Slide capture requires a Chromium browser and Ghostscript (gs).")
        print("  macOS:  brew install ghostscript")
        print("  Linux:  apt install ghostscript")
        sys.exit(1)
    elif len(result) == 0:
        print("No slides found to capture.", file=sys.stderr)
        sys.exit(1)
    else:
        for path in result:
            print(f"Captured: {path}")


def main():
    parser = argparse.ArgumentParser(
        prog="colloquium",
        description="Agent-native slide creation tool for research talks",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # build
    build_parser = subparsers.add_parser("build", help="Build markdown to HTML")
    build_parser.add_argument("file", help="Input markdown file")
    build_parser.add_argument("-o", "--output", help="Output directory")
    build_parser.set_defaults(func=_build)

    # serve
    serve_parser = subparsers.add_parser("serve", help="Dev server with live reload")
    serve_parser.add_argument("file", help="Input markdown file")
    serve_parser.add_argument("-p", "--port", type=int, default=8080, help="Port (default: 8080)")
    serve_parser.set_defaults(func=_serve)

    # export
    export_parser = subparsers.add_parser("export", help="Export to PDF or PPTX")
    export_parser.add_argument("file", help="Input markdown file")
    export_parser.add_argument("--pptx", action="store_true", help="Export as PPTX (requires: pip install colloquium[pptx])")
    export_parser.add_argument("-o", "--output", help="Output file path")
    export_parser.set_defaults(func=_export)

    # capture
    capture_parser = subparsers.add_parser("capture", help="Capture slides as PNG images")
    capture_parser.add_argument("file", help="Input markdown file")
    capture_parser.add_argument("-o", "--output", help="Output directory (default: slides/ next to input)")
    capture_parser.add_argument("-s", "--slide", type=int, help="Capture a single slide (1-indexed)")
    capture_parser.set_defaults(func=_capture)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


def _get_version() -> str:
    try:
        from colloquium import __version__
        return __version__
    except ImportError:
        return "unknown"


if __name__ == "__main__":
    main()
