---
title: "Chapters"
author: "Colloquium"
footer:
  left: "examples/chapters"
  right: "auto"
---

# Chapters

Grouping long talks in the slide picker

---

## Outline

Slides before the first chapter stay ungrouped at the top of the picker.

1. Background
2. Method
3. Results

---

<!-- layout: section-break -->

## Part 1: Background

---

## Why chapters?

A 60-slide talk makes the slide picker a long flat list.

Chapters fold it into a few sections, and only the one you are in starts open.

---

## Section breaks start chapters

Any slide with the `section-break` layout starts a chapter named after its heading.

The chapter runs until the next one starts.

---

<!-- layout: section-break -->
<!-- chapter: Method -->

## Part 2: How the method works, in more detail than fits in a picker row

---

## Shorter picker names

The section break above adds a `chapter: Method` directive, so the picker shows "Method" instead of the full heading.

---

## Step by step

- Parse the slides
- Mark where each chapter starts
- Group the picker by chapter

---

<!-- chapter: Results -->

## Results without a section break

A `chapter` directive on an ordinary content slide starts a chapter too.

---

## What builds on chapters

- `data-chapter="N"` on every slide in a chapter
- `window.colloquium.chapters` with each chapter's title and slide range
- Future chapter-aware progress bars and agenda slides
