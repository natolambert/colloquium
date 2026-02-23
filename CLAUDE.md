# Colloquium — Agent Instructions

## What This Is
Colloquium is an agent-native slide creation tool for research talks. Markdown-based, git-friendly, AI-drivable.

## Commands
- Use `uv` for all Python operations
- `uv pip install -e .` to install in dev mode
- `uv run colloquium build examples/hello/hello.md` to build slides
- `uv run colloquium serve examples/hello/hello.md` for dev server
- `uv run pytest` to run tests

## Architecture Patterns

### CSS
- Slides use `display:none` by default, `display:flex` on `.active`
- CSS specificity: `.slide--type.active` not `.slide--type` (avoids display override bugs)
- CSS custom properties (`--colloquium-*`) for all theme colors/fonts
- Humans can override with custom CSS or per-slide `style` directives

### Navigation (presentation.js)
- Keyboard: arrows, Home/End, Space, PgUp/PgDn, F (fullscreen), Esc
- Click zones: left 1/3 back, right 2/3 forward
- Touch swipe support
- Hash-based URL routing (#1, #2, ...)
- Slide counter + progress bar

### Slide Directives
Per-slide configuration via HTML comments:
- `<!-- layout: two-column -->` — slide layout
- `<!-- class: highlight -->` — CSS classes
- `<!-- style: background: #1a1a2e -->` — inline styles
- `<!-- notes: Speaker notes here -->` — speaker notes (hidden in presentation)

### Output
- All output is a single self-contained HTML file (CSS/JS inlined)
- KaTeX (CDN) for LaTeX math
- highlight.js (CDN) for code syntax highlighting

### PDF Export
- Primary: `@media print` CSS makes all slides visible with page breaks, hides nav
- Users can `Cmd+P` in any browser for a clean PDF
- CLI convenience: `colloquium export` tries system Chrome `--headless --print-to-pdf`
- Optional ghostscript compression if `gs` is on PATH

### Dependencies
- Only 3 runtime deps: markdown-it-py, mdit-py-plugins, pyyaml
- Everything else is stdlib or browser-side CDN

### Citation Convention (Forward-Compatible)
- Use `[@key]` pandoc-style citations in slides (bibtex support planned)
- For now, use plain text citations and manual References slides

## File Layout
```
src/colloquium/
├── __init__.py       # Version, top-level imports
├── cli.py            # argparse CLI entry points
├── parse.py          # Markdown → Slide data structures
├── build.py          # Slides → HTML generation
├── serve.py          # Dev server with live reload
├── export.py         # PDF export (system Chrome + print CSS)
├── deck.py           # Deck class (agent-facing API)
├── slide.py          # Slide dataclass
└── themes/default/
    ├── theme.css     # Default theme
    └── presentation.js  # Navigation engine
```
