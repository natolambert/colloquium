"""Tests for PPTX export."""

import tempfile
from pathlib import Path

import pytest

from colloquium.export import export_pptx

pytest.importorskip("pptx", reason="python-pptx not installed")

def test_export_scatter_chart_smoke():
    md_content = """---
title: Scatter
---

## XY Chart

```chart
type: scatter
data:
  datasets:
    - label: Series
      data:
        - {x: 1, y: 2}
        - {x: 2, y: 3}
        - {x: 3, y: 5}
```
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        md_path = Path(tmpdir) / "scatter.md"
        md_path.write_text(md_content)

        result = export_pptx(str(md_path))

        assert Path(result).exists()
        assert Path(result).suffix == ".pptx"
