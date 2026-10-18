# Chapters

This deck shows every way Colloquium organizes a long talk: chapters in the slide picker, the chapter bar along the bottom of each slide, tables of contents, and a section-break footer. Its first slides summarize every setting, and the rest show each one in place. Open the deck and click the slide counter in the footer to see the picker grouped by chapter.

## Frontmatter

| Setting | Effect |
|---------|--------|
| `chapters: false` | Turn chapters off: flat picker, no bar, empty `toc` blocks |
| `chapter_bar: true` | Labeled bar on every slide; the current chapter fills slide by slide |
| `chapter_bar: bars` | The same, as thin tracks without labels |
| `chapter_bar:` mapping | `labels: true/false`, `slides: all/section-breaks`, `progress: slides/chapters` |
| `footer.section_break` | Footer zones swapped in on section breaks, e.g. a white logo |

```yaml
chapter_bar:
  slides: section-breaks
  progress: chapters
footer:
  left: "mark.svg"
  section_break:
    left: "mark-white.svg"
```

## On a slide

| Directive or block | Effect |
|--------------------|--------|
| `<!-- chapter: Title -->` | Start a chapter on any slide, or rename a section break's chapter everywhere |
| `<!-- chapter-short: Label -->` | Shorter label for the chapter in the bar only |
| `<!-- chapter-bar: bars chapters -->` | Restyle this slide's bar (`labels`/`bars`, `slides`/`chapters`), or show it when the deck setting leaves it out |
| `<!-- chapter-bar: hide -->` | Hide the bar on this slide (the `no-chapter-bar` class does the same) |
| ```` ```toc ```` block | List the chapters, linked to their first slides; inside a chapter, highlight it. `numbered: false` for a plain list |

Every `section-break` slide starts a chapter named after its heading. Slides before the first chapter stay ungrouped.

With a labeled bar, keep the footer light: a logo and the slide counter in the corners, nothing in `footer.center`. This deck does the same.

Each slide's `<section>` carries `data-chapter="N"`, and `window.colloquium.chapters` lists `{title, start, end}` for every chapter, for custom CSS or scripts that build on chapters.
