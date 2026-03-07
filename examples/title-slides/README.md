# Title Slides

This example deck is meant to be copied into real talks.
It uses only built-in Colloquium title layouts and built-in title utility classes.

Files:

- `title-slides.md` — the source deck
- `title-slides.html` — the built preview

## Built-in Title Layouts

### `title`

Centered title slide.
Best for short titles and minimal metadata.

```markdown
# My Talk Title

<div class="colloquium-title-eyebrow">Conference</div>
<div class="colloquium-title-rule"></div>

<div class="colloquium-title-meta">
<p class="colloquium-title-name">Jane Doe</p>
<p>Institution</p>
<p>March 2026</p>
</div>
```

### `title-left`

Left-aligned title slide with the whole composition vertically centered by default.
This is the strongest default for research talks.

```markdown
<!-- layout: title-left -->

# Building Useful Language Models

<div class="colloquium-title-eyebrow">Invited Talk</div>
<div class="colloquium-title-rule"></div>

<div class="colloquium-title-meta">
<p class="colloquium-title-name">Jane Doe</p>
<p>Institution</p>
<p>March 2026</p>
</div>

<p class="colloquium-title-note">One sentence of framing copy.</p>
```

### `title-sidebar`

Wide title with a metadata rail on the right.
Best when the title is long.

```markdown
<!-- layout: title-sidebar -->

# An Introduction to Reinforcement Learning from Human Feedback

<div class="colloquium-title-eyebrow">Tutorial</div>
<div class="colloquium-title-rule"></div>

<div class="colloquium-title-meta">
<p class="colloquium-title-name">Jane Doe</p>
<p>Institution</p>
<p>March 2026</p>
</div>

<p class="colloquium-title-note">Use this when centered titles start feeling too tall.</p>
```

Optional rail behavior:

- default: the vertical rule tracks the right-hand content block
- `<!-- class: title-sidebar-rule-full -->`: stretch the rule the full height of the right column

```markdown
<!-- layout: title-sidebar -->
<!-- class: title-sidebar-rule-full -->
```

### `title-banner`

Headline high on the slide, metadata lower on the slide.
Useful when you want a more editorial composition.

```markdown
<!-- layout: title-banner -->

# Post-Training for Useful Language Models

<div class="colloquium-title-eyebrow">Research Talk</div>
<div class="colloquium-title-rule"></div>

<div class="colloquium-title-meta">
<p class="colloquium-title-name">Jane Doe</p>
<p>Institution</p>
<p>March 2026</p>
</div>

<p class="colloquium-title-note">Short framing copy goes here.</p>
```

## Built-in Title Utility Classes

These classes are available in the default theme and are safe to copy:

- `colloquium-title-eyebrow` — small uppercase kicker above metadata
- `colloquium-title-rule` — short accent line
- `colloquium-title-meta` — vertical stack for byline / venue / date
- `colloquium-title-name` — larger author line
- `colloquium-title-note` — subdued framing note

## Vertical Positioning

`valign` is a global utility, so it can affect title slides too:

- `<!-- valign: top -->`
- `<!-- valign: center -->`
- `<!-- valign: bottom -->`

Current guidance:

- `title`: `center` usually works best
- `title-left`: `top`, `center`, and `bottom` are all reasonable
- `title-banner`: use carefully; the layout is intentionally top-weighted
- `title-sidebar`: `top`, `center`, and `bottom` are supported

Example:

```markdown
<!-- layout: title-left -->
<!-- valign: bottom -->

# My Talk Title

<div class="colloquium-title-meta">
<p class="colloquium-title-name">Jane Doe</p>
<p>Institution</p>
</div>
```

## Recommended Starting Point

If you are not sure which layout to choose:

1. Start with `title-left`.
2. Switch to `title-sidebar` if the title wraps too much.
3. Use `title-banner` only when you want a deliberately more designed look.
