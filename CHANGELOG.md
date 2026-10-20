# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once public releases begin.

Each entry must reference the PR that introduced it as a link (e.g. `([#14](https://github.com/natolambert/colloquium/pull/14))`).
One line per PR for easy copy into GitHub releases.

## [Unreleased]

- Figure columns: the image rule matches the theme's generic image rule's specificity so a figure fills a tall column instead of stopping at the generic height cap ([#60](https://github.com/natolambert/colloquium/pull/60))
- Fixed: the dev server's live rebuild silently failed on decks that cite papers and have column or row slides after the references, because the render check compared slides out of order; build errors are now flushed to the log ([#61](https://github.com/natolambert/colloquium/pull/61))
- `animate: bullets`/`items`: blocks after an animated list (a takeaway line, a caption) now appear after the last bullet instead of being visible from the first click; text before the list stays visible ([#59](https://github.com/natolambert/colloquium/pull/59))
- Consecutive leading `##` (or `#`) lines form one multi-line slide title with a line break between them, instead of the second line becoming a stray heading in the body; chapters, the slide picker, and `toc` blocks read it as one line ([#57](https://github.com/natolambert/colloquium/pull/57))
- Figure columns: a grid column or row cell holding an image followed by its caption fits the image to the column's height with the caption beneath, keeping the width from the `columns` directive; the builder emits the column tracks as `--colloquium-columns` on each slide, and `img-tall-right` now lays the slide out on that grid so the full-height figure column follows the chosen ratio and works with raw `<img>` + caption as well as captioned figures ([#56](https://github.com/natolambert/colloquium/pull/56))
- Share images: `url` and `share_image` frontmatter emit Open Graph and Twitter card tags (`share_image: auto` points at `<deck>-share.png`, resolved against `url`), and `colloquium share-image` captures the first slide as that PNG ([#58](https://github.com/natolambert/colloquium/pull/58))
- Add chapters for long decks: section breaks and `<!-- chapter: ... -->` start chapters, which group the slide picker into collapsible sections with only the current chapter open; slides carry `data-chapter` attributes and `window.colloquium.chapters` for future chapter-aware features; `chapters: false` opts out; an opt-in chapter bar (`chapter_bar: true`, `bars`, or a `labels`/`slides`/`progress` mapping) adds one segment per chapter along the bottom of slides that shades as the talk progresses, with `<!-- chapter-short: ... -->` labels and per-slide `<!-- chapter-bar: ... -->` overrides; `footer.section_break` swaps footer zones such as a white logo on section breaks; and a ```` ```toc ```` block lists the chapters with the current one highlighted; documented in the README and an `examples/chapters` deck that shows every option ([#55](https://github.com/natolambert/colloquium/pull/55))
- Fix bibliography citations in figure captions without corrupting image alt attributes, while preserving citations between literal comparisons in raw HTML ([#53](https://github.com/natolambert/colloquium/pull/53))
- Overhaul PDF export fidelity: iframe embeds print as real page screenshots captured at export time (compact linked card as offline fallback), slide links keep their screen color, and ghostscript compression is off by default (`COLLOQUIUM_PDF_COMPRESS=1` to opt in) since gs 10.x breaks ICC profiles and blanks images in Apple's PDF viewers ([#51](https://github.com/natolambert/colloquium/pull/51))
- Fix captioned-figure fitting overflowing captions onto the footer (reserve caption height, skip absolutely positioned figures) and add the opt-in `img-tall-right` class for full-slide-height right-column figures ([#50](https://github.com/natolambert/colloquium/pull/50))

## [0.2.3] - 2026-08-03

- Warn on stderr when a bibliography fails to parse (or pybtex is missing) instead of silently rendering every citation unresolved ([#48](https://github.com/natolambert/colloquium/pull/48))
- Fix a purely numeric `rows` count spec (e.g. a typo'd `rows: 100000000`) allocating a count-sized list and potentially exhausting memory during builds ([#47](https://github.com/natolambert/colloquium/pull/47))
- Cap printed row images at their row's height share (emitted as `--colloquium-print-row-frac`) so tall figures in `rows` slides stop overflowing the page and silently shifting onto the next PDF page during export ([#46](https://github.com/natolambert/colloquium/pull/46))
- Raise the PDF export virtual-time budget (5s → 30s, overridable via `COLLOQUIUM_PDF_TIME_BUDGET_MS`) so the last images in image-heavy decks stop rendering blank in exported PDFs ([#45](https://github.com/natolambert/colloquium/pull/45))
- Apply smart typography (en/em dashes, curly quotes) inside `box` and `conversation` elements by sharing the main pipeline's markdown-it config ([#44](https://github.com/natolambert/colloquium/pull/44))
- Fix paragraph spacing swallowed by generated step/animate fragment wrappers (stepped paragraphs rendered flush with no line break) ([#43](https://github.com/natolambert/colloquium/pull/43))
- Upgrade locked Pillow to 12.3.0 to fix 13 Dependabot alerts (heap OOB read/writes, decompression-bomb bypasses, DoS, command injection) ([#42](https://github.com/natolambert/colloquium/pull/42))
- Update presentation navigation: left/right step through reveal states then slides; up/down, typed slide numbers, and the picker jump straight to a slide with all reveals shown ([#39](https://github.com/natolambert/colloquium/pull/39))
- Load Google Fonts with a `<link>` in `<head>` so custom `fonts:` from the frontmatter actually render instead of silently falling back to the theme default ([#41](https://github.com/natolambert/colloquium/pull/41))

## [0.2.2] - 2026-06-19

- Make slide text easier to get out: click-drag/selection no longer advances the slide, and press `c` to copy the current slide's markdown source to the clipboard ([#37](https://github.com/natolambert/colloquium/pull/37))
- Fix `title: center` leaking center alignment to the whole slide body, and citation author surnames (keep full multi-word names, strip BibTeX braces) ([#36](https://github.com/natolambert/colloquium/pull/36))
- Fix block animations for generated div-based elements ([#33](https://github.com/natolambert/colloquium/pull/33))
- Bind dev server to loopback, change default port to 8090, and error on port conflicts ([#28](https://github.com/natolambert/colloquium/pull/28))
- Upgrade locked Pillow to 12.2.0 to fix CVE-2026-40192 ([#29](https://github.com/natolambert/colloquium/pull/29))
- Upgrade locked pytest to 9.0.3 and Pygments to 2.20.0 to fix CVE-2025-71176 and CVE-2026-4539 ([#30](https://github.com/natolambert/colloquium/pull/30))
- Upgrade locked lxml to 6.1.0 to fix CVE-2026-41066 (XXE in iterparse/ETCompatXMLParser) ([#31](https://github.com/natolambert/colloquium/pull/31))
- Add a built-in iframe element for embedding external or local HTML content ([#32](https://github.com/natolambert/colloquium/pull/32))
- Add fragment-based animations: `<!-- animate: bullets|blocks -->` and `<!-- step -->` for incremental reveal ([#25](https://github.com/natolambert/colloquium/pull/25))
- Hide the mobile slide picker trigger when decks are embedded in iframes ([#35](https://github.com/natolambert/colloquium/pull/35))
- Add `<!-- after: references -->` for post-reference appendix slides excluded from the footer total ([#34](https://github.com/natolambert/colloquium/pull/34))

## [0.2.1] - 2026-03-25

- Fix chart rendering breaking slide navigation when data contains single quotes ([#20](https://github.com/natolambert/colloquium/pull/20))
- Normalize BibTeX braces in citations and references ([#19](https://github.com/natolambert/colloquium/pull/19))
- Add `colloquium capture` command for per-slide PNG export via Ghostscript ([#17](https://github.com/natolambert/colloquium/pull/17))
- Fix code block scrollbars and add changelog commit hook ([#23](https://github.com/natolambert/colloquium/pull/23))
- Fix PDF export clipping for printed equations and captioned figures ([#18](https://github.com/natolambert/colloquium/pull/18))
- Fix KaTeX delimiter rendering on hidden slides ([#16](https://github.com/natolambert/colloquium/pull/16))
- Enable typographic replacements: `--` to en-dash, `---` to em-dash, smart quotes ([#15](https://github.com/natolambert/colloquium/pull/15))

## [0.2.0] - 2026-03-10

- Add GitHub Pages website with rendered example decks and CI workflows ([#13](https://github.com/natolambert/colloquium/pull/13))
- Clean up README for launch: site link, simplified install, trim internals ([#14](https://github.com/natolambert/colloquium/pull/14))
- Add mobile navigation, figure captions, and box callouts ([#11](https://github.com/natolambert/colloquium/pull/11))
- Add inline footnotes, model labels, title markdown, img-valign, and harden live preview ([#9](https://github.com/natolambert/colloquium/pull/9))
- Add rows/columns layouts, citation ordering, and conversation sizing ([#6](https://github.com/natolambert/colloquium/pull/6))
- Add experimental PPTX export, title layouts, footer nav, and rendering fixes ([#5](https://github.com/natolambert/colloquium/pull/5))
- Fix footer overwriting slide counter ([#4](https://github.com/natolambert/colloquium/pull/4))
- Update repo URL and encourage uv for installation ([#3](https://github.com/natolambert/colloquium/pull/3))
- Add citations, conversations, and elements architecture ([#2](https://github.com/natolambert/colloquium/pull/2))
- Fix chart bugs: apostrophes, sizing, tick labels ([#1](https://github.com/natolambert/colloquium/pull/1))
