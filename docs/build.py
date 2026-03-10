#!/usr/bin/env python3
"""Build a minimal project website for GitHub Pages."""

from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from markdown_it import MarkdownIt

from colloquium import __version__
from colloquium.build import build_file
from colloquium.export import export_pdf
from colloquium.parse import parse_file


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "dist" / "site"
REPO_URL = "https://github.com/natolambert/colloquium"
PYPI_URL = "https://pypi.org/project/colloquium/"
GITHUB_API_REPO_URL = "https://api.github.com/repos/natolambert/colloquium"


@dataclass
class Example:
    slug: str
    title: str
    deck_path: Path
    deck_filename: str
    pdf_filename: str
    readme_path: Path | None
    summary: str
    docs_html: str


_FIRST_HEADING_RE = re.compile(r"^\s*<h[1-3][^>]*>.*?</h[1-3]>\s*", re.DOTALL)
_EXAMPLE_LINK_RE = re.compile(r'href="\.\./([a-z0-9-]+)/?"')


def _make_md() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": True})
    md.enable("table")
    return md


def _extract_summary(readme_text: str) -> str:
    for line in readme_text.splitlines():
        stripped = line.strip()
        if (
            not stripped
            or stripped.startswith("#")
            or stripped.startswith("```")
            or stripped.startswith("|")
        ):
            continue
        return stripped
    return "Rendered example deck with copy-paste patterns."


def _strip_leading_heading(docs_html: str) -> str:
    return _FIRST_HEADING_RE.sub("", docs_html, count=1).strip()


def _rewrite_inline_example_links(docs_html: str) -> str:
    return _EXAMPLE_LINK_RE.sub(r'href="#\1"', docs_html)


def _fetch_repo_stars() -> int | None:
    request = Request(
        GITHUB_API_REPO_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "colloquium-docs-builder",
        },
    )
    try:
        with urlopen(request, timeout=4) as response:
            payload = json.load(response)
    except (OSError, URLError, ValueError):
        return None
    stars = payload.get("stargazers_count")
    return stars if isinstance(stars, int) else None


def _load_examples() -> list[Example]:
    md = _make_md()
    examples: list[Example] = []

    for example_dir in sorted(p for p in EXAMPLES_DIR.iterdir() if p.is_dir()):
        deck_candidates = sorted(
            p for p in example_dir.glob("*.md") if p.name.lower() != "readme.md"
        )
        if not deck_candidates:
            continue
        deck_path = deck_candidates[0]
        deck = parse_file(str(deck_path))
        readme_path = example_dir / "README.md"
        readme_text = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
        docs_html = (
            _rewrite_inline_example_links(_strip_leading_heading(md.render(readme_text)))
            if readme_text
            else ""
        )
        summary = _extract_summary(readme_text) if readme_text else (
            deck.author.strip() or "Minimal example deck for a specific Colloquium pattern."
        )
        examples.append(
            Example(
                slug=example_dir.name,
                title=deck.title or example_dir.name.replace("-", " ").title(),
                deck_path=deck_path,
                deck_filename=f"{deck_path.stem}.html",
                pdf_filename=f"{deck_path.stem}.pdf",
                readme_path=readme_path if readme_path.exists() else None,
                summary=summary,
                docs_html=docs_html,
            )
        )
    return examples


def _site_css() -> str:
    return """
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.55;
  color: #17203c;
  background: #f5f6fb;
}
main {
  max-width: 980px;
  margin: 0 auto;
  padding: 2.5rem 1.25rem 4rem;
}
h1, h2, h3 { line-height: 1.1; color: #17203c; }
h1 { margin: 0 0 0.75rem; font-size: clamp(2rem, 5vw, 3.2rem); }
h2 { margin: 2.5rem 0 0.9rem; font-size: 1.45rem; }
h3 { margin: 0 0 0.4rem; font-size: 1.15rem; }
p, ul, ol { margin: 0.75rem 0; }
a { color: #2f4ca0; }
code, pre {
  font-family: ui-monospace, SFMono-Regular, SFMono-Regular, Menlo, monospace;
}
pre {
  overflow-x: auto;
  padding: 0.9rem 1rem;
  border-radius: 10px;
  border: 1px solid #d6dbeb;
  background: #ffffff;
}
.muted { color: #5b6380; }
.lede { max-width: 42rem; }
.top-links {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-top: 0.9rem;
  align-items: baseline;
}
.star-count { color: #5b6380; margin-left: -0.55rem; }
.example-list { display: grid; gap: 1.5rem; }
.example-item {
  padding-top: 1.25rem;
  border-top: 1px solid #dfe3f0;
}
.example-links {
  display: flex;
  gap: 0.9rem;
  flex-wrap: wrap;
  margin-top: 0.45rem;
}
.preview-panel,
.inline-preview {
  overflow: hidden;
  border: 1px solid #dfe3f0;
  border-radius: 12px;
  background: #ffffff;
}
.preview-panel iframe,
.inline-preview iframe {
  display: block;
  width: 100%;
  border: 0;
}
.preview-panel iframe { min-height: 76vh; }
.inline-preview {
  margin-top: 0.85rem;
  aspect-ratio: 16 / 9;
}
.inline-preview iframe {
  height: 100%;
}
.inline-notes {
  margin-top: 0.85rem;
  color: #38405b;
}
.inline-notes details {
  padding-left: 0;
}
.inline-notes summary {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  cursor: pointer;
  color: #2f4ca0;
  font-weight: 600;
  font-size: 1.02rem;
  margin-bottom: 0.35rem;
  list-style: none;
}
.inline-notes summary::-webkit-details-marker {
  display: none;
}
.inline-notes summary::before {
  content: "▸";
  display: inline-block;
  width: 0.7em;
  color: #2f4ca0;
  transform-origin: 40% 50%;
  transition: transform 120ms ease;
}
.inline-notes details[open] summary::before {
  transform: rotate(90deg);
}
.inline-notes details[open] summary {
  margin-bottom: 0.65rem;
}
.inline-notes h1:first-child,
.inline-notes h2:first-child,
.inline-notes h3:first-child {
  margin-top: 0;
}
.footer-note {
  margin-top: 2.5rem;
  color: #6a728d;
  font-size: 0.95rem;
}
@media (max-width: 900px) {
  main { padding-inline: 1rem; }
  .preview-panel iframe { min-height: 68vh; }
}
"""


def _page_shell(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{_site_css()}</style>
</head>
<body>
  <main>{body}</main>
</body>
</html>
"""


def _render_home_page(examples: list[Example], repo_stars: int | None) -> str:
    hello = next((example for example in examples if example.slug == "hello"), examples[0])
    others = [example for example in examples if example.slug != hello.slug]
    github_label = (
        f'<a href="{REPO_URL}">GitHub</a><span class="star-count">★ {repo_stars:,}</span>'
        if repo_stars is not None
        else f'<a href="{REPO_URL}">GitHub</a>'
    )
    example_jump_list = " · ".join(
        f'<a href="#{html.escape(example.slug)}">{html.escape(example.title)}</a>'
        for example in others
    )
    def notes_block(example: Example) -> str:
        docs = example.docs_html or f"<p>{html.escape(example.summary)}</p>"
        return f"""
        <div class="inline-notes">
          <details>
            <summary>More details</summary>
            {docs}
          </details>
        </div>
        """

    items = "\n".join(
        f"""
        <section class="example-item" id="{html.escape(example.slug)}">
          <h3>{html.escape(example.title)}</h3>
          <p>{html.escape(example.summary)}</p>
          <div class="example-links">
            <a href="examples/{html.escape(example.slug)}/{html.escape(example.deck_filename)}">Deck</a>
            <a href="examples/{html.escape(example.slug)}/{html.escape(example.pdf_filename)}">PDF</a>
            <a href="{REPO_URL}/blob/main/{example.deck_path.relative_to(REPO_ROOT).as_posix()}">Source</a>
          </div>
          <div class="inline-preview">
            <iframe src="examples/{html.escape(example.slug)}/{html.escape(example.deck_filename)}" title="{html.escape(example.title)} preview"></iframe>
          </div>
          {notes_block(example)}
        </section>
        """
        for example in others
    )
    body = f"""
    <h1>Colloquium</h1>
    <p class="lede">Markdown-first slides for research talks. The website is intentionally small: start with the hello deck, then browse the focused examples. The main documentation stays in the repository README.</p>
    <p class="muted">Built by Nathan Lambert.</p>
    <p class="top-links">
      <a href="examples/{html.escape(hello.slug)}/{html.escape(hello.deck_filename)}">Explore Colloquium</a>
      <a href="{REPO_URL}/blob/main/README.md">README</a>
      <a href="{PYPI_URL}">PyPI</a>
      {github_label}
    </p>

    <section>
      <h2>Quick start</h2>
      <pre><code>uv tool install colloquium   # install the CLI on your PATH
# or inside a project/venv:
# uv pip install colloquium   # install into the active project environment

uv run colloquium build examples/hello/hello.md   # build self-contained HTML
uv run colloquium serve examples/hello/hello.md   # launch local preview server
uv run colloquium export examples/hello/hello.md  # export PDF via Chromium</code></pre>
    </section>

    <section>
      <h2>Core features</h2>
      <p>What makes Colloquium especially useful for academics and for building slides with agents:</p>
      <ul>
        <li>Markdown native</li>
        <li>Equations and code highlighting</li>
        <li>BibTeX via Pybtex</li>
        <li>Charts</li>
      </ul>
      <p class="muted">More coming soon.</p>
    </section>

    <section>
      <h2>Get started</h2>
      <div>
        <div id="{html.escape(hello.slug)}"></div>
        <h3>{html.escape(hello.title)}</h3>
        <p>{html.escape(hello.summary)}</p>
        <div class="example-links">
          <a href="examples/{html.escape(hello.slug)}/{html.escape(hello.deck_filename)}">Deck</a>
          <a href="examples/{html.escape(hello.slug)}/{html.escape(hello.pdf_filename)}">PDF</a>
          <a href="{REPO_URL}/blob/main/{hello.deck_path.relative_to(REPO_ROOT).as_posix()}">Source</a>
        </div>
        <div class="inline-preview">
          <iframe src="examples/{html.escape(hello.slug)}/{html.escape(hello.deck_filename)}" title="{html.escape(hello.title)} preview"></iframe>
        </div>
        {notes_block(hello)}
      </div>
    </section>

    <section>
      <h2>All examples</h2>
      <p class="muted">{example_jump_list}</p>
      <div class="example-list">{items}</div>
    </section>

    <p class="footer-note">Built by Nathan Lambert. Colloquium {html.escape(__version__)} on <a href="{PYPI_URL}">PyPI</a>.</p>
    """
    return _page_shell("Colloquium", body)


def _copy_example_assets(example_dir: Path, output_dir: Path) -> None:
    for path in example_dir.iterdir():
        if path.is_dir():
            shutil.copytree(path, output_dir / path.name, dirs_exist_ok=True)
            continue
        if path.suffix.lower() in {".html", ".pdf", ".pptx"}:
            continue
        if path.name.lower() in {"readme.md"}:
            continue
        shutil.copy2(path, output_dir / path.name)


def build_examples_site(output_dir: Path = DEFAULT_OUTPUT_DIR, repo_stars: int | None = None) -> Path:
    examples = _load_examples()
    if repo_stars is None:
        repo_stars = _fetch_repo_stars()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")

    for example in examples:
        example_dir = output_dir / "examples" / example.slug
        example_dir.mkdir(parents=True, exist_ok=True)
        deck_output = example_dir / example.deck_filename
        build_file(str(example.deck_path), str(deck_output))
        export_pdf(str(deck_output), str(example_dir / example.pdf_filename))
        _copy_example_assets(example.deck_path.parent, example_dir)

    (output_dir / "index.html").write_text(
        _render_home_page(examples, repo_stars),
        encoding="utf-8",
    )
    return output_dir


def main() -> None:
    path = build_examples_site()
    print(f"Built examples site: {path}")


if __name__ == "__main__":
    main()
