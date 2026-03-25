# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once public releases begin.

Each entry must reference the PR that introduced it as a link (e.g. `([#14](https://github.com/natolambert/colloquium/pull/14))`).
One line per PR for easy copy into GitHub releases.

## [Unreleased]

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
