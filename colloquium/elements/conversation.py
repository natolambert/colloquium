"""Conversation element — renders ```conversation YAML blocks as chat bubbles."""

import html as html_module
import re

import yaml
from markdown_it import MarkdownIt

PATTERN = re.compile(
    r'<pre><code class="language-conversation">(.*?)</code></pre>',
    re.DOTALL,
)

_conversation_counter = 0
_inline_md = MarkdownIt("commonmark", {"html": True})


def reset() -> None:
    """Reset the conversation counter between builds."""
    global _conversation_counter
    _conversation_counter = 0


def process(yaml_str: str) -> str:
    """Convert a YAML conversation spec to chat-bubble HTML."""
    global _conversation_counter
    _conversation_counter += 1
    conv_id = f"colloquium-conversation-{_conversation_counter}"

    raw = html_module.unescape(yaml_str.strip())
    try:
        spec = yaml.safe_load(raw)
    except yaml.YAMLError:
        return '<p style="color:red">Invalid conversation YAML</p>'

    if not isinstance(spec, dict):
        return '<p style="color:red">Conversation spec must be a YAML mapping</p>'

    messages = spec.get("messages", [])
    if not messages:
        return '<p style="color:red">Conversation has no messages</p>'

    size_value = spec.get("size")
    size_style = ""
    if size_value not in {None, ""}:
        try:
            scale = float(size_value)
        except (TypeError, ValueError):
            scale = None
        if scale is not None and scale > 0:
            size_style = f' style="font-size: {scale:g}em"'

    # Sort system messages above others
    system_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "system"]
    other_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") != "system"]
    ordered = system_msgs + other_msgs

    parts = [f'<div class="colloquium-conversation" id="{conv_id}"{size_style}>']
    for msg in ordered:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "user")
        content = msg.get("content", "")
        # Render content through markdown for bold/italic/code
        rendered = _inline_md.render(content).strip()
        parts.append(
            f'<div class="colloquium-message colloquium-message--{html_module.escape(role)}">'
            f'<div class="colloquium-message-role">{html_module.escape(role.capitalize())}</div>'
            f'<div class="colloquium-message-content">{rendered}</div>'
            f'</div>'
        )
    parts.append('</div>')
    return "\n".join(parts)
