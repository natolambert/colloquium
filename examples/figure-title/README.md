# Plot titles from the heading

`widgets.svg` is an exported-style plot whose title text carries `data-role="title"`. The first slide uses `<!-- figure-title: heading -->`, so its `##` heading replaces the title inside the figure at build time; the second slide shows the same file with its own title.

```bash
colloquium build figure-title.md
```
