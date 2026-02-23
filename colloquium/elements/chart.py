"""Chart element — renders ```chart YAML blocks as Chart.js canvases."""

import html as html_module
import json
import re

import yaml

PATTERN = re.compile(
    r'<pre><code class="language-chart">(.*?)</code></pre>',
    re.DOTALL,
)

_chart_counter = 0


def reset() -> None:
    """Reset the chart counter between builds."""
    global _chart_counter
    _chart_counter = 0


def process(yaml_str: str) -> str:
    """Convert a YAML chart spec to a <canvas> + JSON config."""
    global _chart_counter
    _chart_counter += 1
    chart_id = f"colloquium-chart-{_chart_counter}"

    raw = html_module.unescape(yaml_str.strip())
    try:
        spec = yaml.safe_load(raw)
    except yaml.YAMLError:
        return '<p style="color:red">Invalid chart YAML</p>'

    if not isinstance(spec, dict):
        return '<p style="color:red">Chart spec must be a YAML mapping</p>'

    chart_type = spec.get("type", "bar")
    data = spec.get("data", {})
    title = spec.get("title", "")
    options = spec.get("options", {})

    # Build Chart.js config
    datasets = []
    colors = [
        "#0f3460", "#e94560", "#16213e", "#0ea5e9",
        "#10b981", "#f59e0b", "#8b5cf6", "#ec4899",
    ]
    for i, ds in enumerate(data.get("datasets", [])):
        dataset = {
            "label": ds.get("label", f"Series {i+1}"),
            "data": ds.get("data", []),
            "borderColor": ds.get("color", colors[i % len(colors)]),
            "backgroundColor": ds.get("color", colors[i % len(colors)]),
        }
        if chart_type in ("line", "scatter"):
            dataset["backgroundColor"] = "transparent"
            dataset["borderWidth"] = 2.5
            dataset["pointRadius"] = 3
            dataset["tension"] = 0.3
        elif chart_type in ("bar",):
            dataset["backgroundColor"] = ds.get("color", colors[i % len(colors)]) + "cc"
        datasets.append(dataset)

    chart_options = {
        "responsive": True,
        "maintainAspectRatio": False,
        "animation": False,
        "devicePixelRatio": 3,
        "plugins": {
            "legend": {"display": len(datasets) > 1},
            "title": {"display": bool(title), "text": title, "font": {"size": 16}},
        },
    }
    # Deep-merge user options
    for key, value in options.items():
        if key in chart_options and isinstance(chart_options[key], dict) and isinstance(value, dict):
            chart_options[key].update(value)
        else:
            chart_options[key] = value

    config = {
        "type": chart_type,
        "data": {
            "labels": data.get("labels", []),
            "datasets": datasets,
        },
        "options": chart_options,
    }

    config_json = json.dumps(config)
    return (
        f'<div class="colloquium-chart-container">'
        f'<canvas id="{chart_id}" data-chart-config=\'{config_json}\'></canvas>'
        f'</div>'
    )
