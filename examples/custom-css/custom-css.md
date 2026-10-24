---
title: "Custom CSS from a file"
author: "Colloquium examples"
custom_css: custom-css.css
footer:
  left: "custom_css: custom-css.css"
  right: "{n}/{N}"
---

## Styles live in custom-css.css

The frontmatter names a stylesheet next to the deck instead of holding the CSS inline, so the markdown stays about the slides.

<div class="callout">Edit <code>custom-css.css</code> while <code>colloquium serve</code> runs and the deck rebuilds.</div>

---

## The built HTML is still one file

The file's contents are inlined at build time, so PDF export, share images, and hosting work exactly as before.

- Relative paths resolve next to the markdown file
- Inline CSS in `custom_css` keeps working
- A missing file is a build error that names the path
