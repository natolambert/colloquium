# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once public releases begin.

## [Unreleased]

### Added

- GitHub Pages website with rendered example decks.
- CI workflows for tests, changelog enforcement, and site deploy.
- `pytest` as a dev optional dependency.
- Release checklist in `RELEASING.md`.

### Changed

- Simplified README: install section, site link, removed internal release details.
- Generated example artifacts are no longer tracked in git.

## [0.1.0] - 2026-03-10

### Added

- Markdown-first deck authoring with self-contained HTML output.
- Live preview server with slide navigation and hot rebuilds.
- PDF export through browser print CSS and a Chromium CLI path.
- Experimental PPTX export.
- Research-oriented elements including citations, conversation blocks, box callouts, footnotes, math, and charts.
- Example decks for hello, title slides, rows/columns, and footnotes.
