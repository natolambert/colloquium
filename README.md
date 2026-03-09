# Colloquium

Markdown-based slide creation tool for research talks. Git-friendly, AI-drivable, single-file HTML output.

## Install

Colloquium uses [uv](https://docs.astral.sh/uv/) for fast, reliable Python package management.

```bash
uv pip install git+https://github.com/natolambert/colloquium.git
```

Or for development:

```bash
git clone https://github.com/natolambert/colloquium.git
cd colloquium
uv pip install -e .
```

### Using colloquium from another uv project

uv's venv doesn't process `.pth` files, so `uv pip install -e` from another project's venv won't work. Use a symlink instead:

```bash
# From your other project's directory:
ln -s /path/to/colloquium/colloquium .venv/lib/python3.*/site-packages/colloquium
```

This gives you a true editable install — changes to colloquium source are reflected immediately.

## Quick Start

Create a markdown file:

```markdown
---
title: "My Talk"
author: "Jane Doe"
date: "2026-02-22"
---

# My Talk

Jane Doe

---

## Key Results

- Finding one
- Finding two

---

## Conclusion

Thanks for listening!
```

Build it:

```bash
colloquium build slides.md        # → slides.html
colloquium serve slides.md        # dev server with live reload
colloquium export slides.md       # PDF via a headless Chromium-based browser
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `colloquium build <file.md>` | Build to self-contained HTML |
| `colloquium serve <file.md>` | Dev server with live reload |
| `colloquium export <file.md>` | PDF export (requires a Chromium-based browser) |

## Frontmatter Reference

All configuration goes in the YAML frontmatter block at the top of the file.

```yaml
---
title: "Talk Title"
author: "Author Name"
date: "2026-02-22"
theme: default
aspect_ratio: "16:9"

fonts:
  heading: "Playfair Display"    # Google Font for h1/h2/h3
  body: "Source Sans 3"          # Google Font for body text

footer:
  left: "https://example.com/logo.png"   # image URL → logo, plain text → text
  center: "My Talk Title"
  right: "auto"                           # "auto" → slide numbers "3 / 12"

custom_css: ".slide h2 { color: red; }"   # inline CSS overrides
---
```

| Key | Default | Description |
|-----|---------|-------------|
| `title` | `"Untitled"` | Presentation title (used in `<title>` and title slides) |
| `author` | `""` | Author name |
| `date` | `""` | Date string |
| `theme` | `"default"` | Theme name |
| `aspect_ratio` | `"16:9"` | Slide aspect ratio |
| `fonts.heading` | Inter | Google Font for headings |
| `fonts.body` | Inter | Google Font for body text |
| `footer.left` | `""` | Left footer zone (text, image URL, or `"auto"`) |
| `footer.center` | `""` | Center footer zone |
| `footer.right` | `"auto"` | Right footer zone (`"auto"` = slide numbers) |
| `custom_css` | `""` | Additional CSS injected into the page |

Footer text supports `{n}` (slide number) and `{N}` (total slides) for custom counters, e.g. `"Lambert {n}/{N}"` → `"Lambert 6/23"`.

When `footer:` is omitted entirely, a minimal footer with just the slide counter in the right zone is used.

Use `{n}` and `{N}` placeholders to embed the current slide number and total count inline with text:

```yaml
footer:
  left: "rlhfbook.com"
  right: "Lambert {n}/{N}"    # renders as "Lambert 3/25"
```

If no zone uses `"auto"`, `{n}`, or `{N}`, the slide counter is automatically placed in the first empty zone.

## Slide Structure

Slides are separated by `---` on its own line. The first heading in each slide becomes the slide title:

| Heading | Behavior |
|---------|----------|
| `# Title` | Title slide — centered, large text, `slide--title` layout |
| `## Title` | Content slide — standard layout with heading at top |
| `###` through `######` | Rendered as subheadings within slide content |

```markdown
# Welcome              ← title slide (centered, large)

---

## Key Results         ← content slide (heading + body)

### Sub-section        ← rendered as h3 inside the slide body

Normal paragraph text.
```

## Slide Directives

Per-slide configuration via HTML comments. Place them anywhere in the slide.

```markdown
## My Slide

<!-- layout: section-break -->
<!-- class: highlight special -->
<!-- style: background: #1a1a2e -->
<!-- notes: Remember to mention X -->
<!-- align: center -->
<!-- valign: bottom -->
<!-- columns: 2 -->
<!-- rows: 35/65 -->
<!-- padding: compact -->
<!-- size: large -->
<!-- title: hidden -->
```

### Layouts

| Directive | Effect |
|-----------|--------|
| `<!-- layout: title -->` | Centered title slide (used with `# Heading`) |
| `<!-- layout: title-left -->` | Left-aligned title slide with stacked metadata |
| `<!-- layout: title-sidebar -->` | Wide title with a right-side metadata rail |
| `<!-- layout: title-banner -->` | Editorial title slide with headline up top and metadata near the bottom |
| `<!-- layout: content -->` | Default content layout (used with `## Heading`) |
| `<!-- layout: section-break -->` | Dark accent background, centered text |
| `<!-- layout: two-column -->` | Two-column grid |
| `<!-- layout: image-left -->` | Image on left, text on right |
| `<!-- layout: image-right -->` | Text on left, image on right |
| `<!-- layout: code -->` | Optimized for large code blocks |

### Columns

Split content with `|||` between columns:

```markdown
<!-- columns: 2 -->
## Results

Left column content

|||

Right column content
```

| Value | Effect |
|-------|--------|
| `2` | Two equal columns |
| `3` | Three equal columns |
| `60/40` | 60%/40% split |
| `40/60` | 40%/60% split |
| `70/30` | 70%/30% split |
| `30/70` | 30%/70% split |

Arbitrary numeric ratios are allowed, e.g. `25/75`, `33/67`, or `1/2/1`.

### Rows

Split a slide vertically with `===` between row blocks:

```markdown
<!-- rows: 35/65 -->
## Overview

Top row content

===

Bottom row content
```

| Value | Effect |
|-------|--------|
| `2` | Two equal rows |
| `3` | Three equal rows |
| `60/40` | 60%/40% split |
| `40/60` | 40%/60% split |
| `35/65` | 35%/65% split |
| `65/35` | 65%/35% split |
| `70/30` | 70%/30% split |
| `30/70` | 30%/70% split |

Arbitrary numeric ratios are allowed here too, e.g. `25/75` or `20/30/50`.

To use columns inside a specific row block, add a row-local directive at the top of that row:

```markdown
<!-- rows: 35/65 -->
## Overview

<!-- row-columns: 40/60 -->
Left text

|||

Right text

===

![Wide image](figure.png)
```

At the slide root, use either `columns:` or `rows:`. For nested layouts, use `row-columns:` inside a row block.

### Text & Spacing

| Directive | Values |
|-----------|--------|
| `<!-- align: ... -->` | `left`, `center`, `right` |
| `<!-- valign: ... -->` | `top`, `center`, `bottom` |
| `<!-- size: ... -->` | `small` (20px), `normal` (24px), `large` (28px) |
| `<!-- padding: ... -->` | `compact` (30px), `normal` (60px), `wide` (90px) |
| `<!-- title: ... -->` | `top`, `center`, `hidden` |

### Other

| Directive | Description |
|-----------|-------------|
| `<!-- class: name1 name2 -->` | Add CSS classes to the slide |
| `<!-- style: css-here -->` | Inline CSS on the slide element |
| `<!-- notes: text -->` | Speaker notes (hidden in presentation) |
| `<!-- class: figure-captions -->` | Turn standalone markdown images on that slide into numbered figures with captions taken from `![alt](...)` |
| `<!-- class: no-figure-captions -->` | Disable deck-wide figure captions for a specific slide |
| `<!-- img-align: center -->` | Align images only (`left`, `center`, `right`) — title unaffected |
| `<!-- img-valign: top -->` | Vertically align standalone images in grid/row cells (`top`, `center`, `bottom`) |
| `<!-- img-fill: true -->` | Expand image to fill available slide space |
| `<!-- img-overflow: true -->` | Let images in grid cells bleed outside their box instead of fitting inside |

See [`examples/title-slides/title-slides.md`](./examples/title-slides/title-slides.md) for concrete title-slide compositions using the built-in title layouts, [`examples/title-slides/README.md`](./examples/title-slides/README.md) for copy-paste guidance on when to use each layout, [`examples/rows-and-columns/rows-and-columns.md`](./examples/rows-and-columns/rows-and-columns.md) for nested row/column layouts, and [`examples/footnotes/footnotes.md`](./examples/footnotes/footnotes.md) for numbered inline footnotes and floating slide notes.

Generated example HTML is not tracked in git. Build any example locally with `uv run colloquium build examples/.../*.md`.

### Bibliography

Frontmatter options:

```yaml
bibliography: refs.bib
citation_style: author-year
citation_order: auto
```

- `citation_style: numeric` keeps citations and references in first-appearance order.
- Non-numeric styles default to alphabetical ordering.
- Set `citation_order: appearance` to keep author-year or title-year citations in source order.

## Content Features

**Math** (KaTeX) — inline `$E=mc^2$` and display `$$\sum_{i=1}^n x_i$$`

**Code** (highlight.js) — fenced code blocks with language syntax highlighting

**Tables** — standard markdown tables

**Images** — `![alt](url)` with automatic sizing (SVG supported for vector graphics)

To enable numbered figure captions across a whole deck, add this to frontmatter:

```yaml
figure_captions: true
```

Standalone markdown images will render as numbered figures, using the alt text as the caption:

```markdown
![Training recipe overview](assets/recipe.png)
```

This renders as `Figure 1: Training recipe overview`. Leave the alt text empty to suppress the caption:

```markdown
![](assets/recipe.png)
```

If you only want captions on selected slides, use `figure-captions` as a slide class instead:

```markdown
<!-- class: figure-captions -->

![Training recipe overview](assets/recipe.png)
```

If the deck enables `figure_captions: true`, add `no-figure-captions` to a slide to opt that slide out.

### Text Sizes

Control font size on any element or block using HTML class attributes:

```markdown
<span class="text-2xl">Big emphasis text</span>

Normal paragraph text.

<div class="text-sm">

- Dense bullet point one
- Dense bullet point two

</div>

<span class="text-xs">Footnote or citation</span>

<div class="colloquium-spacer-md"></div>

<div class="colloquium-footnote">
This is useful for speaker-side caveats or details that should stay visually secondary.
</div>
```

| Class | Scale | Use case |
|-------|-------|----------|
| `text-xs` | 0.65em | Footnotes, citations |
| `text-sm` | 0.8em | Dense lists, fine details |
| `text-base` | 1em | Default |
| `text-lg` | 1.2em | Callouts |
| `text-xl` | 1.4em | Key takeaways |
| `text-2xl` | 1.7em | Emphasis |
| `text-3xl` | 2.2em | Large statements |
| `text-4xl` | 2.8em | Hero text |

### Spacing and Footnotes

Use small spacer blocks when you want more breathing room between prose and an example:

```markdown
After pretraining we are left with a glorified autocomplete model.

<div class="colloquium-spacer-md"></div>

```conversation
messages:
  ...
```
```

Available spacer helpers:

- `colloquium-spacer-sm`
- `colloquium-spacer-md`
- `colloquium-spacer-lg`

Use `colloquium-footnote` for secondary caveats or context inside the slide body:

```markdown
<div class="colloquium-footnote">
Base models are also becoming more flexible through midtraining and related data mixtures.
</div>
```

For slide-level footnotes that sit above the footer, use directives:

```markdown
<!-- footnote: Base models are also becoming more flexible through midtraining. -->
<!-- footnote-right: Right-aligned note for this slide. -->
```

These share the same bottom-left / bottom-right area as floating citations, with citations stacked above the footnote when both are present.

For inline numbered footnotes, use `^[...]` where you want the marker to appear:

```markdown
This sentence ends with a numbered footnote.^[Base models are also becoming more flexible through midtraining.]
```

Inline footnotes collect into the same floating footer area and are numbered per slide. They default to the right side; set the side explicitly when needed:

```markdown
<!-- footnotes: left -->
```

Use the dedicated example deck in [`examples/footnotes/`](./examples/footnotes/) for copy-paste patterns.

### Charts

Inline charts via Chart.js using YAML in fenced code blocks:

````markdown
```chart
type: line
height: 500
width: 800
data:
  labels: [Q1, Q2, Q3, Q4]
  datasets:
    - label: Revenue
      data: [10, 25, 40, 60]
      color: "#4AA691"
options:
  scales:
    y:
      ticks:
        prefix: "$"
        suffix: "K"
```
````

| Key | Default | Description |
|-----|---------|-------------|
| `type` | `bar` | Chart type: `line`, `bar`, `scatter`, `pie`, `doughnut` |
| `height` | `400` | Container height in pixels |
| `width` | `100%` | Container width in pixels (omit for full width) |
| `data.labels` | `[]` | X-axis labels |
| `data.datasets[].label` | `"Series N"` | Legend label |
| `data.datasets[].data` | `[]` | Data values |
| `data.datasets[].color` | auto | Series color |
| `options.scales.{x,y}.ticks.prefix` | `""` | Prepend to tick labels (e.g. `"$"`) |
| `options.scales.{x,y}.ticks.suffix` | `""` | Append to tick labels (e.g. `"%"`) |
| `options.scales.{x,y}.grid.display` | `true` | Show/hide grid lines |

### Conversations

Render LLM-style chat bubbles using YAML in fenced code blocks:

````markdown
```conversation
size: 0.9
messages:
  - role: user
    content: "What is RLHF?"
  - role: assistant
    model: "Tülu 3 405B"
    content: "**RLHF** is a technique for aligning language models..."
  - role: system
    content: "You are a helpful AI assistant."
```
````

| Role | Styling |
|------|---------|
| `user` | Right-aligned bubble, accent background, white text |
| `assistant` | Left-aligned bubble, code-bg background |
| `system` | Centered, bordered, muted italic text |

Message content supports markdown formatting (bold, italic, inline code).

Optional conversation settings:

| Key | Default | Description |
|-----|---------|-------------|
| `size` | unset | Bubble font scale as a positive numeric value like `0.9` or `1.05` |
| `messages[].model` | unset | Optional model label shown next to the role, e.g. `ASSISTANT (Llama 3.1 405B Base)` |

### Boxes

Render a rounded callout card using YAML in fenced code blocks:

````markdown
```box
title: DPO became popular because:
tone: accent
content: |
  - Far simpler to implement
  - Far cheaper to run
  - Often reaches most of the final performance
```
````

Optional box settings:

| Key | Default | Description |
|-----|---------|-------------|
| `title` | unset | Bold heading shown at the top of the box |
| `tone` | `accent` | Visual style: `accent`, `muted`, or `surface` |
| `size` | unset | Font scale as a positive numeric value like `0.9` or `1.05` |
| `align` | unset | Text alignment inside the box: `left`, `center`, or `right` |

The supported tones are:

| Tone | Use |
|------|-----|
| `accent` | High-contrast highlight box using the deck accent color |
| `muted` | Softer supporting card using the code/background surface |
| `surface` | Neutral bordered panel for references, caveats, or side notes |

### Built With Badge

Render a compact GitHub badge anywhere in a slide using the normal layout tools:

````markdown
<!-- align: right -->
<!-- valign: bottom -->

```builtwith
repo: natolambert/colloquium
```
````

Optional settings:

| Key | Default | Description |
|-----|---------|-------------|
| `label` | `"Built with"` | Small label above the repo name |
| `repo` | `"natolambert/colloquium"` | GitHub repository slug |
| `url` | `https://github.com/<repo>` | Link target override |
| `stars` | `auto` | Fetch GitHub stars automatically, hide with `false`, or pin a numeric value |
| `icon` | `true` | Show/hide the GitHub icon |

Because it is a normal block element, you can place it with columns, rows, alignment utilities, or raw HTML wrappers instead of relying on footer-specific behavior.

### Citations

Add a `.bib` file to your project and reference it in frontmatter:

```yaml
---
bibliography: refs.bib
citation_style: author-year   # or "numeric" or "title-year"
---
```

Use `[@key]` to cite in slides:

```markdown
The foundational work on RLHF [@christiano2017] introduced reward models.

Multiple citations: [@christiano2017; @ouyang2022]
```

A **References** slide is automatically appended with only the cited works.

| Key | Default | Description |
|-----|---------|-------------|
| `bibliography` | `""` | Path to `.bib` file (relative to markdown file) |
| `citation_style` | `"author-year"` | Citation format: `author-year`, `numeric`, `title-year` |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Right / Down / Space / PgDn | Next slide |
| Left / Up / PgUp | Previous slide |
| Home | First slide |
| End | Last slide |
| F | Toggle fullscreen |
| Escape | Close picker / exit fullscreen |

Click the slide counter to open the slide picker. Click left 1/3 of screen to go back, right 2/3 to go forward.

## PPTX Export (Experimental)

Export to PowerPoint/Google Slides format:

```bash
uv pip install colloquium[pptx]     # install optional dependency
colloquium export --pptx slides.md  # → slides.pptx
```

This produces a reasonable starting point, but some colloquium features lose fidelity: citations are flattened, math renders as raw LaTeX, and custom themes/CSS aren't applied. Charts and tables become native editable PPTX objects.

## PDF Export

Two options:

1. **Browser**: Open the HTML file and `Cmd+P` / `Ctrl+P` — print CSS makes all slides visible with page breaks, footers with slide numbers included
2. **CLI**: `colloquium export slides.md` uses headless Chrome

## Output

Everything builds to a single self-contained HTML file. CSS and JS are inlined; math (KaTeX) and code highlighting (highlight.js) load from CDN.

## Contributing Elements

Custom block-level elements live in `colloquium/elements/`. Each module exposes:

- `PATTERN` — compiled regex matching `<pre><code class="language-X">...</code></pre>`
- `process(yaml_str) -> str` — converts the YAML content to HTML
- `reset()` (optional) — resets any counters between builds

The registry in `colloquium/elements/__init__.py` auto-wires them into the build pipeline. To add a new element:

1. Create `colloquium/elements/my_element.py` with `PATTERN`, `process`, and optionally `reset`
2. Import and register it in `colloquium/elements/__init__.py`
3. Add any element-specific CSS to `colloquium/themes/default/theme.css`
