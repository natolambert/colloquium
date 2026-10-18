---
title: "Chapters"
author: "Colloquium"
chapter_bar: true
footer:
  left: "mark.svg"
  right: "auto"
  section_break:
    left: "mark-white.svg"
---

# Chapters

Organizing long talks: the slide picker, the chapter bar, and tables of contents

---

## Table of contents

```toc
```

Slides before the first chapter stay ungrouped. The `toc` block above lists the chapters, linked to their first slides.

---

<!-- size: small -->

## Frontmatter settings

| Setting | Effect |
|---------|--------|
| `chapters: false` | No chapters; flat picker, no bar, empty `toc` blocks |
| `chapter_bar: true` | Labeled bar on every slide; the current chapter fills slide by slide |
| `chapter_bar: bars` | Same, as thin tracks without labels |
| `chapter_bar:` `slides: section-breaks` | Bar only on section breaks |
| `chapter_bar:` `progress: chapters` | Whole-chapter states: done, current, upcoming |
| `chapter_bar:` `labels: false` | Tracks only, combinable with the keys above |
| `footer:` `section_break:` | Footer zones swapped on section breaks, e.g. a white logo |

---

<!-- size: small -->

## Slide directives and blocks

| On a slide | Effect |
|------------|--------|
| <code>&lt;!&#45;&#45; chapter: Title &#45;&#45;&gt;</code> | Start a chapter here, or rename a section break's chapter |
| <code>&lt;!&#45;&#45; chapter-short: Label &#45;&#45;&gt;</code> | Shorter label in the chapter bar only |
| <code>&lt;!&#45;&#45; chapter-bar: bars chapters &#45;&#45;&gt;</code> | Restyle this slide's bar: `labels`/`bars`, `slides`/`chapters` |
| <code>&lt;!&#45;&#45; chapter-bar: hide &#45;&#45;&gt;</code> | Hide the bar here (also the `no-chapter-bar` class) |
| ```` ```toc ```` block | List the chapters; inside a chapter, highlight it |

Every `section-break` slide starts a chapter named after its heading.

---

<!-- layout: section-break -->
<!-- chapter-short: Picker -->

## Part 1: The slide picker

---

## Chapters group the picker

Click the slide counter in the footer. Slides before the first chapter sit at the top, and each chapter is a collapsible group showing its slide range.

Only the chapter you are in starts open; click another to see its slides.

---

## Section breaks start chapters

Any slide with the `section-break` layout starts a chapter named after its heading. The chapter runs until the next one starts.

This chapter's section break also adds <code>&lt;!&#45;&#45; chapter-short: Picker &#45;&#45;&gt;</code>, so the bar below reads "Picker" while the picker and table of contents keep "Part 1: The slide picker".

---

<!-- layout: section-break -->
<!-- chapter: Chapter bar -->

## Part 2: Showing progress along the bottom of every slide, in more detail than fits

---

## Renaming a chapter

The section break above adds <code>&lt;!&#45;&#45; chapter: Chapter bar &#45;&#45;&gt;</code>, which renames the chapter everywhere: the picker, the table of contents, and the bar.

Use `chapter-short` instead when only the bar needs a shorter name.

---

## Default: labeled, slide by slide

This deck sets `chapter_bar: true`. Finished chapters are shaded, the current chapter's track fills as you advance through it, and later chapters stay empty.

Click a segment to jump to that chapter. Hover it to see the full title.

---

<!-- chapter-bar: bars -->

## Tracks only

<code>&lt;!&#45;&#45; chapter-bar: bars &#45;&#45;&gt;</code> drops the labels on this slide. Deck-wide, use `chapter_bar: bars`.

The footer lifts slightly to clear the tracks, and slides keep their full content height.

---

<!-- chapter-bar: chapters -->

## Whole-chapter progress

<code>&lt;!&#45;&#45; chapter-bar: chapters &#45;&#45;&gt;</code> shows chapters instead of slides: finished chapters are dimmed, the current one is solid and bold, and upcoming ones stay empty.

Deck-wide, use `progress: chapters` under `chapter_bar:`.

---

<!-- chapter-bar: bars chapters -->

## Both together

<code>&lt;!&#45;&#45; chapter-bar: bars chapters &#45;&#45;&gt;</code>: whole-chapter tracks without labels.

---

<!-- chapter-bar: hide -->

## A slide without the bar

<code>&lt;!&#45;&#45; chapter-bar: hide &#45;&#45;&gt;</code>, or the `no-chapter-bar` class, hides the bar on one slide. Title slides never show it.

A `chapter-bar` directive with any other value shows the bar on its slide even when the deck has no `chapter_bar` setting.

---

<!-- layout: section-break -->
<!-- chapter-short: Section breaks -->
<!-- chapter-bar: chapters -->

## Part 3: Section breaks

---

## Bars on section breaks only

The section break before this slide shows whole-chapter progress. To show the bar only on section breaks, deck-wide:

```yaml
chapter_bar:
  slides: section-breaks
  progress: chapters
```

Add `chapter-short` labels so no name is cut off.

---

## A footer for section breaks

Section breaks sit on the accent color, so this deck swaps in a white logo there:

```yaml
footer:
  left: "mark.svg"
  section_break:
    left: "mark-white.svg"
```

Any footer zone (`left`, `center`, `right`) can be overridden this way.

---

<!-- chapter: Table of contents -->
<!-- chapter-short: Contents -->

## Where we are

```toc
```

A `chapter` directive on an ordinary content slide starts a chapter too. Inside a chapter, a `toc` block highlights it, so repeating it makes an agenda slide.

---

## An unnumbered list

```toc
numbered: false
```

Set `numbered: false` inside the block for a plain list.

---

## What builds on chapters

- `data-chapter="N"` on every slide in a chapter, and `data-chapter-start` on its first slide
- `window.colloquium.chapters` with each chapter's title and slide range
- Generated references form a "References" chapter in the picker, left out of the bar and `toc` blocks
