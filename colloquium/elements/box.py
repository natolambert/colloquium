"""Box element — renders ```box YAML blocks as callout boxes."""

import html as html_module
import re

import yaml
from markdown_it import MarkdownIt

PATTERN = re.compile(
    r'<pre><code class="language-box">(.*?)</code></pre>',
    re.DOTALL,
)

_block_md = MarkdownIt("commonmark", {"html": True})
_SIMPLE_SCALAR_RE = re.compile(r"^(title|tone|align|size|compact):\s*(.+?)\s*$")


def reset() -> None:
    """Reset element-local state between builds."""
    return None


def _quote_simple_scalars(raw: str) -> str:
    """Make common one-line box fields tolerant of unquoted colons.

    This keeps authoring lightweight for values like:
    `title: DPO became very popular as it is:`
    """
    lines = []
    for line in raw.splitlines():
        match = _SIMPLE_SCALAR_RE.match(line)
        if not match:
            lines.append(line)
            continue

        key, value = match.groups()
        value = value.strip()
        if not value or value in {"|", ">"} or value[0] in {'"', "'", "[", "{", "&", "*", "!"}:
            lines.append(line)
            continue

        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key}: "{escaped}"')
    return "\n".join(lines)


def process(yaml_str: str) -> str:
    """Convert a YAML box spec to callout HTML."""
    raw = html_module.unescape(yaml_str.strip())
    try:
        spec = yaml.safe_load(raw)
    except yaml.YAMLError:
        try:
            spec = yaml.safe_load(_quote_simple_scalars(raw))
        except yaml.YAMLError:
            return '<p style="color:red">Invalid box YAML</p>'

    if not isinstance(spec, dict):
        return '<p style="color:red">Box spec must be a YAML mapping</p>'

    title = spec.get("title", "")
    content = spec.get("content", "")
    title_text = str(title).strip()
    content_text = content.strip() if isinstance(content, str) else ""
    if not title_text and not content_text:
        return '<p style="color:red">Box requires title or content</p>'

    tone = str(spec.get("tone", "accent")).strip().lower() or "accent"
    size_value = spec.get("size")
    align = str(spec.get("align", "")).strip().lower()
    compact_value = spec.get("compact", False)

    classes = ["colloquium-box", f"colloquium-box--{html_module.escape(tone)}"]
    if align in {"left", "center", "right"}:
        classes.append(f"colloquium-box--align-{align}")
    if compact_value:
        classes.append("colloquium-box--compact")

    style_attr = ""
    if size_value not in {None, ""}:
        try:
            scale = float(size_value)
        except (TypeError, ValueError):
            scale = None
        if scale is not None and scale > 0:
            style_attr = f' style="font-size: {scale:g}em"'

    parts = [f'<div class="{" ".join(classes)}"{style_attr}>']
    if title_text:
        title_html = _block_md.renderInline(title_text).strip()
        parts.append(f'<div class="colloquium-box-title">{title_html}</div>')
    if content_text:
        parts.append(f'<div class="colloquium-box-content">{_block_md.render(content_text).strip()}</div>')
    parts.append("</div>")
    return "\n".join(parts)
