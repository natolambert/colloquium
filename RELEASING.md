# Releasing Colloquium

This document is the manual checklist for a release.

## Before the first release

1. Enable GitHub Pages for the repository.
2. Confirm the docs site workflow can deploy from `main`.

## Release checklist

1. Make sure `main` is clean and up to date.
2. Update the version in:
   - [`pyproject.toml`](./pyproject.toml)
   - [`colloquium/__init__.py`](./colloquium/__init__.py)
3. Move notable changes from `Unreleased` into a dated release section in [`CHANGELOG.md`](./CHANGELOG.md).
4. Run verification:

   ```bash
   uv run pytest
   uv run python scripts/build_examples_site.py
   uv run colloquium build examples/hello/hello.md
   uv run colloquium export examples/hello/hello.md
   ```

5. Commit the version/changelog update.
6. Tag the release:

   ```bash
   git tag v0.1.0
   git push origin main --tags
   ```

7. Build and publish manually:

   ```bash
   uv build
   uv publish
   ```

8. Confirm the `Examples site` workflow has deployed the latest docs site.

## Notes

- `uv build` writes distributions to `dist/`.
- Generated example HTML/PDF/PPTX files should remain untracked.
- If `uv publish` is not configured locally yet, finish PyPI setup before tagging.
