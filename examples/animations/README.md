# Animations

Incrementally reveal bullets, paragraphs, or arbitrary content groups without duplicating slides.

Two composable primitives:

- `<!-- animate: bullets -->` reveals each list item one click at a time
- `<!-- animate: blocks -->` reveals each top-level block element (paragraph, list, code block) sequentially
- `<!-- step -->` markers split arbitrary content into reveal groups

Patterns in [`animations.md`](./animations.md):

- bullet-by-bullet reveal
- block-by-block reveal (paragraphs, lists, code)
- step markers for arbitrary content grouping
- composing `animate` + `step` on the same slide
- animations inside column layouts
- a plain slide showing backward compatibility

Basic usage:

```md
## My Slide
<!-- animate: bullets -->

- First point
- Second point
- Third point
```

Step markers for custom grouping:

```md
## My Slide

This text appears immediately.

<!-- step -->

This appears on the first click.

<!-- step -->

This appears on the second click.
```

Notes:

- Navigation steps through fragments before advancing to the next slide.
- Going backward hides fragments in reverse, then shows the previous slide fully built.
- Print and PDF export show all content (fragments forced visible).
- `items` is an alias for `bullets`.
