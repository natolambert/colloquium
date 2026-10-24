# Custom CSS from a file

`custom-css.md` points its `custom_css` frontmatter key at `custom-css.css`, a stylesheet next to the deck. The file is read at build time and inlined into the HTML, so the output stays a single self-contained file. Running `colloquium serve custom-css.md` also rebuilds when the stylesheet changes.

```bash
colloquium build custom-css.md
```
