from pathlib import Path

from scripts.build_examples_site import build_examples_site


def test_build_examples_site(tmp_path: Path):
    output_dir = tmp_path / "site"
    result = build_examples_site(output_dir)

    assert result == output_dir
    assert (output_dir / "index.html").exists()
    assert (output_dir / ".nojekyll").exists()

    expected_examples = {
        "hello": "hello.html",
        "footnotes": "footnotes.html",
        "rows-and-columns": "rows-and-columns.html",
        "title-slides": "title-slides.html",
    }

    for slug, deck_file in expected_examples.items():
        example_dir = output_dir / "docs" / slug
        assert (example_dir / "index.html").exists()
        assert (example_dir / deck_file).exists()
