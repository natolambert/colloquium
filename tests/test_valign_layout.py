"""Layout checks for the valign directive, measured in a real browser.

The valign classes only set justify-content on the slide, so they depend on
the content block not stretching to fill it. A string match on the CSS cannot
tell whether a slide really moved, so these tests measure it.
"""

import json
import re
import subprocess

import pytest

from colloquium.build import build_deck
from colloquium.export import _find_browser, _is_chromium_based
from colloquium.parse import parse_markdown

_browser = _find_browser()
needs_chromium = pytest.mark.skipif(
    _browser is None or not _is_chromium_based(_browser), reason="needs a Chromium-based browser"
)

SLIDE_HEIGHT = 720
PADDING = 60

DECK = """---
title: valign
---

## default

- One
- Two

---

<!-- valign: center -->

## center

- One
- Two

---

<!-- valign: bottom -->

## bottom

- One
- Two

---

<!-- layout: section-break -->

## section break

With a subtitle line.

---

<!-- valign: center -->
<!-- columns: 50/50 -->

## center columns

- Left one
- Left two

|||

- Right one

---

<!-- valign: center -->
<!-- rows: 50/50 -->

## center rows

Top row

===

Bottom row
"""

_MEASURE = """<script>
window.addEventListener('load', function () {
  var out = {};
  document.querySelectorAll('.slide').forEach(function (slide) {
    slide.classList.add('active');
    var box = slide.getBoundingClientRect(), scale = box.height / 720;
    var heading = slide.querySelector(':scope > h2').getBoundingClientRect();
    var block = slide.querySelector(':scope > .slide-content');
    var textBottom = 0;
    block.querySelectorAll('p, li').forEach(function (el) {
      textBottom = Math.max(textBottom, el.getBoundingClientRect().bottom);
    });
    out[slide.querySelector(':scope > h2').textContent.trim()] = {
      top: (heading.top - box.top) / scale,
      bottom: (textBottom - box.top) / scale,
      blockBottom: (block.getBoundingClientRect().bottom - box.top) / scale
    };
    slide.classList.remove('active');
  });
  var pre = document.createElement('pre');
  pre.id = 'measure';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
});
</script></body>"""


@pytest.fixture(scope="module")
def groups(tmp_path_factory):
    """Per slide, in slide px: top of the heading, bottom of the last text line,
    and bottom of the content block (which can extend past its text)."""
    html = build_deck(parse_markdown(DECK))
    assert html.count("</body>") == 1
    page = tmp_path_factory.mktemp("valign") / "deck.html"
    page.write_text(html.replace("</body>", _MEASURE), encoding="utf-8")
    dom = subprocess.run(
        [_browser, "--headless=new", "--disable-gpu", "--window-size=1280,720",
         "--virtual-time-budget=5000", "--dump-dom", page.as_uri()],
        capture_output=True, text=True, timeout=120,
    ).stdout
    match = re.search(r'<pre id="measure">(.*?)</pre>', dom, re.S)
    assert match, "the measuring script did not run"
    return json.loads(match.group(1).replace("&quot;", '"'))


def _middle(group):
    """Midpoint of the visible group, from the heading to the last text line."""
    return (group["top"] + group["bottom"]) / 2


@needs_chromium
def test_default_slide_starts_at_the_top(groups):
    assert groups["default"]["top"] == pytest.approx(PADDING, abs=2)


@needs_chromium
def test_valign_center_centers_heading_and_content_together(groups):
    assert _middle(groups["center"]) == pytest.approx(SLIDE_HEIGHT / 2, abs=12)


@needs_chromium
def test_valign_bottom_ends_at_the_bottom_padding(groups):
    group = groups["bottom"]
    assert group["bottom"] == pytest.approx(SLIDE_HEIGHT - PADDING, abs=24)
    assert group["top"] > SLIDE_HEIGHT / 2


@needs_chromium
def test_section_break_with_body_text_is_centered(groups):
    assert _middle(groups["section break"]) == pytest.approx(SLIDE_HEIGHT / 2, abs=12)


@needs_chromium
def test_valign_center_centers_a_columns_slide(groups):
    assert _middle(groups["center columns"]) == pytest.approx(SLIDE_HEIGHT / 2, abs=12)


@needs_chromium
def test_rows_keep_filling_the_slide_under_valign_center(groups):
    group = groups["center rows"]
    assert group["top"] == pytest.approx(PADDING, abs=2)
    assert group["blockBottom"] == pytest.approx(SLIDE_HEIGHT - PADDING, abs=2)
