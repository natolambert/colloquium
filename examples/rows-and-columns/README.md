# Rows and Columns

This example deck shows how to combine:

- slide-level `rows:`
- the `===` row divider
- row-local `row-columns:`
- arbitrary ratios such as `35/65` or `25/75`
- image fitting inside row/grid boxes by default

Patterns in [`rows-and-columns.md`](./rows-and-columns.md):

- simple top-text / bottom-visual slide
- top row split into columns, bottom row full width
- big image on top with a short note row below
- three equal rows

Basic usage:

```md
<!-- rows: 35/65 -->
## Slide title

Top row

===

Bottom row
```

Nested columns inside a row:

```md
<!-- rows: 35/65 -->
## Slide title

<!-- row-columns: 40/60 -->
Left

|||

Right

===

Bottom row
```

Notes:

- Use `columns:` or `rows:` at the slide root, not both.
- Use `row-columns:` only inside a row block.
- Ratios are not limited to presets; any numeric split is allowed.
- Images fit their row/grid box by default; add `<!-- img-overflow: true -->` if you want a deliberate bleed.
