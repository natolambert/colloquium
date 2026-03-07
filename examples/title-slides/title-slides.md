---
title: "Title Slide Options"
author: "Colloquium"
date: "March 2026"
fonts:
  heading: "Space Grotesk"
  body: "Source Sans 3"
footer:
  left: "examples/title-slides"
  center: ""
  right: "auto"
---

<!--
Default `title` layout using only built-in title utility classes.
-->

<!-- valign: center -->
# Centered Hero

<div class="colloquium-title-eyebrow">Classic Title</div>

<p class="colloquium-title-name">A centered, high-ceremony opener for talks with short metadata.</p>

<div class="colloquium-title-meta">
<p>Nathan Lambert</p>
<p>SALA 2026, Quito</p>
<p>11 March 2026</p>
</div>

---

<!-- layout: title-left -->
<!--
Built-in `title-left` layout.
The left alignment, spacing, and large headline are theme-level.
The eyebrow + accent rule are built-in utility classes:
`.colloquium-title-eyebrow` and `.colloquium-title-rule`.
-->

# Building Language Models in the Era of Agents

<div class="colloquium-title-eyebrow">Title Left</div>
<div class="colloquium-title-rule"></div>

<div class="colloquium-title-meta">
<p class="colloquium-title-name">Nathan Lambert</p>
<p>Amazon AGI, Seattle WA <br>
18 February 2026</p>
</div>

<p class="colloquium-title-note">Uses width more intelligently than the centered hero and keeps supporting details in a clean vertical stack.</p>

---

<!-- layout: title-sidebar -->
<!-- valign: bottom -->
<!--
Built-in `title-sidebar` layout.
The two-column composition is theme-level.
-->

# An Introduction to Reinforcement Learning from Human Feedback and Post-training

<div class="colloquium-title-eyebrow">Title Sidebar</div>

<div class="colloquium-title-meta">
<p class="colloquium-title-name">Nathan Lambert</p>
<p>rlhfbook.com<br>
SALA 2026, Quito<br>
11 March 2026</p>
</div>

<p class="colloquium-title-note">Best when the title is long and you want the byline to feel anchored rather than dropped underneath.</p>

---

<!-- layout: title-banner -->
<!--
Built-in `title-banner` layout.
This intentionally pins the headline higher and the metadata lower.
-->

# Post-Training for Useful Language Models

<div class="colloquium-title-eyebrow">Title Banner</div>
<div class="colloquium-title-rule"></div>

<div class="colloquium-title-meta">
<p class="colloquium-title-name">Nathan Lambert</p>
<p>Research talk</p>
<p>Spring 2026</p>
</div>

<p class="colloquium-title-note">A stronger editorial feel: big headline near the top, metadata and framing copy collected near the bottom.</p>

---

## When To Use Which

- `title`: best for short titles and minimal metadata
- `title-left`: strongest default for research talks
- `title-sidebar`: safest option for long titles
- `title-banner`: useful when you want atmosphere without adding images

This example uses only built-in layouts plus the built-in title utility classes, so it should be directly copyable into another deck.
