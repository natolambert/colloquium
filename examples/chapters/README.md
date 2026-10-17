# Chapters

This example deck shows how chapters organize a long talk in the slide picker. Open the deck, click the slide counter in the footer, and only the current chapter is expanded; click another chapter to see its slides.

Patterns in [`chapters.md`](./chapters.md):

- ungrouped title and outline slides before the first chapter
- section-break slides that start chapters named after their heading
- a `<!-- chapter: ... -->` directive giving a long section break a shorter picker name
- a chapter that starts on an ordinary content slide

Every section break starts a chapter automatically:

```md
<!-- layout: section-break -->

## Part 1: Background
```

Start a chapter anywhere, or rename a section break's chapter:

```md
<!-- chapter: Results -->

## Benchmark results
```

Turn chapters off and keep a flat picker:

```yaml
chapters: false
```

Each slide's `<section>` carries `data-chapter="N"`, and `window.colloquium.chapters` lists `{title, start, end}` for every chapter, for custom CSS or scripts that build on chapters.
