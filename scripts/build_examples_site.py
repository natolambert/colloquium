#!/usr/bin/env python3
"""Build a minimal examples/docs site for GitHub Pages."""

from __future__ import annotations

import html
import shutil
from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt

from colloquium import __version__
from colloquium.build import build_file
from colloquium.parse import parse_file


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "dist" / "site"
REPO_URL = "https://github.com/natolambert/colloquium"
PAGES_URL = "https://natolambert.github.io/colloquium/"


@dataclass
class Example:
    slug: str
    title: str
    deck_path: Path
    deck_filename: str
    readme_path: Path | None
    summary: str
    docs_html: str


def _make_md() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": True})
    md.enable("table")
    return md


def _extract_summary(readme_text: str) -> str:
    for line in readme_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("```"):
            continue
        return stripped
    return "Rendered example deck with copy-paste patterns."


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
        docs_html = md.render(readme_text) if readme_text else ""
        summary = _extract_summary(readme_text) if readme_text else (
            deck.author.strip() or "Minimal example deck for a specific Colloquium pattern."
        )
        examples.append(
            Example(
                slug=example_dir.name,
                title=deck.title or example_dir.name.replace("-", " ").title(),
                deck_path=deck_path,
                deck_filename=f"{deck_path.stem}.html",
                readme_path=readme_path if readme_path.exists() else None,
                summary=summary,
                docs_html=docs_html,
            )
        )
    return examples


def _site_css() -> str:
    return """
body {
  margin: 0;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  color: #101828;
  background: #f7f8fc;
}
a { color: #2454ff; text-decoration: none; }
a:hover { text-decoration: underline; }
code, pre {
  font-family: "SFMono-Regular", "Menlo", "Monaco", monospace;
}
code {
  background: #eef1f8;
  padding: 0.14rem 0.32rem;
  border-radius: 0.35rem;
}
pre {
  background: #111827;
  color: #f8fafc;
  padding: 1rem 1.1rem;
  border-radius: 0.8rem;
  overflow-x: auto;
}
.shell {
  display: grid;
  gap: 2rem;
  max-width: 1180px;
  margin: 0 auto;
  padding: 2.5rem 1.25rem 4rem;
}
.hero {
  background: linear-gradient(135deg, #152b5c 0%, #1f4aa5 100%);
  color: white;
  border-radius: 1.4rem;
  padding: 2rem 2.2rem;
  box-shadow: 0 18px 50px rgba(21, 43, 92, 0.18);
}
.hero h1 {
  margin: 0 0 0.65rem;
  font-size: clamp(2rem, 4vw, 3.3rem);
  line-height: 1.05;
}
.hero p {
  margin: 0;
  max-width: 46rem;
  font-size: 1.06rem;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.92);
}
.hero-links {
  display: flex;
  gap: 0.8rem;
  flex-wrap: wrap;
  margin-top: 1.15rem;
}
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  padding: 0.72rem 1rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: white;
  font-weight: 600;
}
.button.secondary {
  background: white;
  color: #152b5c;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1rem;
}
.card {
  background: white;
  border: 1px solid #e4e7ec;
  border-radius: 1rem;
  padding: 1.15rem 1.2rem;
  box-shadow: 0 8px 24px rgba(16, 24, 40, 0.05);
}
.card h2, .card h3 {
  margin: 0 0 0.55rem;
  line-height: 1.15;
}
.card p {
  margin: 0;
  color: #344054;
  line-height: 1.55;
}
.eyebrow {
  display: inline-block;
  margin-bottom: 0.55rem;
  color: #2454ff;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.section-title {
  margin: 0 0 0.85rem;
  font-size: 1.5rem;
}
.pair {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1rem;
}
.pair .card p + p {
  margin-top: 0.8rem;
}
.example-links {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-top: 0.95rem;
}
.example-page {
  display: grid;
  grid-template-columns: minmax(300px, 420px) minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}
.docs-card {
  position: sticky;
  top: 1rem;
}
.preview-card {
  min-height: calc(100vh - 5rem);
  overflow: hidden;
  padding: 0;
}
.preview-card iframe {
  width: 100%;
  min-height: calc(100vh - 5rem);
  border: 0;
  background: #f2f4f7;
}
.doc-body {
  color: #344054;
  line-height: 1.65;
}
.doc-body h1:first-child { margin-top: 0; }
.doc-body h1, .doc-body h2, .doc-body h3 { color: #101828; }
.doc-body ul, .doc-body ol { padding-left: 1.25rem; }
.doc-body table {
  border-collapse: collapse;
  width: 100%;
}
.doc-body th, .doc-body td {
  border: 1px solid #e4e7ec;
  padding: 0.55rem 0.65rem;
  text-align: left;
}
.back-link {
  display: inline-block;
  margin-bottom: 0.85rem;
  font-weight: 600;
}
.footer-note {
  color: #667085;
  font-size: 0.95rem;
}
@media (max-width: 920px) {
  .example-page {
    grid-template-columns: 1fr;
  }
  .docs-card {
    position: static;
  }
  .preview-card iframe {
    min-height: 70vh;
  }
}
"""


def _render_index(examples: list[Example]) -> str:
    cards = "\n".join(
        f"""
        <article class="card">
          <div class="eyebrow">Example</div>
          <h3>{html.escape(example.title)}</h3>
          <p>{html.escape(example.summary)}</p>
          <div class="example-links">
            <a href="docs/{html.escape(example.slug)}/" class="button secondary">Docs & preview</a>
            <a href="docs/{html.escape(example.slug)}/{html.escape(example.deck_filename)}">Deck only</a>
          </div>
        </article>
        """
        for example in examples
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Colloquium docs</title>
  <style>{_site_css()}</style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <h1>Colloquium docs</h1>
      <p>Minimal docs and rendered example decks for a markdown-first slide tool aimed at research talks. The examples are the source of truth for most authoring patterns.</p>
      <div class="hero-links">
        <a class="button secondary" href="{PAGES_URL}">Docs site</a>
        <a class="button" href="{REPO_URL}">GitHub</a>
      </div>
    </section>

    <section class="pair">
      <article class="card">
        <div class="eyebrow">Install</div>
        <h2 class="section-title">Latest release</h2>
        <pre><code>uv tool install colloquium
# or inside a project
uv pip install colloquium</code></pre>
        <p>Use the GitHub install path if you need unreleased main:</p>
        <pre><code>uv tool install --from git+https://github.com/natolambert/colloquium colloquium</code></pre>
      </article>
      <article class="card">
        <div class="eyebrow">Workflow</div>
        <h2 class="section-title">Core commands</h2>
        <pre><code>uv run colloquium build examples/hello/hello.md
uv run colloquium serve examples/hello/hello.md
uv run colloquium export examples/hello/hello.md</code></pre>
        <p>PDF export uses print CSS and a Chromium-based browser for the CLI path. PPTX export remains experimental.</p>
      </article>
    </section>

    <section>
      <div class="eyebrow">Examples</div>
      <h2 class="section-title">Worked examples with copy-paste docs</h2>
      <div class="grid">
        {cards}
      </div>
    </section>

    <p class="footer-note">Built from Colloquium {html.escape(__version__)}.</p>
  </main>
</body>
</html>
"""


def _render_example_page(example: Example) -> str:
    docs_html = example.docs_html or (
        f"<p class='doc-body'>Open the rendered deck for <strong>{html.escape(example.title)}</strong>.</p>"
    )
    source_rel = example.deck_path.relative_to(REPO_ROOT).as_posix()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(example.title)} · Colloquium docs</title>
  <style>{_site_css()}</style>
</head>
<body>
  <main class="shell">
    <a class="back-link" href="../../">← Back to examples</a>
    <section class="example-page">
      <article class="card docs-card">
        <div class="eyebrow">Docs</div>
        <h1>{html.escape(example.title)}</h1>
        <div class="example-links">
          <a class="button secondary" href="{html.escape(example.deck_filename)}">Open deck</a>
          <a href="{REPO_URL}/blob/main/{source_rel}">View source</a>
        </div>
        <div class="doc-body">{docs_html}</div>
      </article>
      <article class="card preview-card">
        <iframe src="{html.escape(example.deck_filename)}" title="{html.escape(example.title)} preview"></iframe>
      </article>
    </section>
  </main>
</body>
</html>
"""


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


def build_examples_site(output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    examples = _load_examples()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")

    for example in examples:
        example_dir = output_dir / "docs" / example.slug
        example_dir.mkdir(parents=True, exist_ok=True)
        build_file(str(example.deck_path), str(example_dir / example.deck_filename))
        _copy_example_assets(example.deck_path.parent, example_dir)
        (example_dir / "index.html").write_text(
            _render_example_page(example),
            encoding="utf-8",
        )

    (output_dir / "index.html").write_text(_render_index(examples), encoding="utf-8")
    return output_dir


def main() -> None:
    path = build_examples_site()
    print(f"Built examples site: {path}")


if __name__ == "__main__":
    main()
