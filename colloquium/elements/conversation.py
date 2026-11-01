"""Conversation element — renders ```conversation YAML blocks as chat bubbles."""

import html as html_module
import re

import yaml

from colloquium.md import create_math_md

PATTERN = re.compile(
    r'<pre><code class="language-conversation">(.*?)</code></pre>',
    re.DOTALL,
)

_conversation_counter = 0
_inline_md = create_math_md()
# Math spans (as dollarmath reads them) or a literal \n escape outside them.
_LITERAL_NEWLINE_RE = re.compile(
    r"((?<!\\)\$\$.+?(?<!\\)\$\$|(?<!\\)\$.+?(?<!\\)\$)|\\n",
    re.DOTALL,
)


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
        model = msg.get("model", "")
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        # Turn literal \n escapes into newlines, but not inside math, where
        # they start commands like \neq or \nabla.
        content = _LITERAL_NEWLINE_RE.sub(lambda m: m.group(1) or "\n", content)
        # Render content through markdown for bold/italic/code
        rendered = _inline_md.render(content).strip()
        role_html = (
            f'<span class="colloquium-message-role-name">{html_module.escape(role.capitalize())}</span>'
        )
        if model:
            role_html += (
                f' <span class="colloquium-message-model">({html_module.escape(str(model))})</span>'
            )
        parts.append(
            f'<div class="colloquium-message colloquium-message--{html_module.escape(role)}">'
            f'<div class="colloquium-message-role">{role_html}</div>'
            f'<div class="colloquium-message-content">{rendered}</div>'
            f'</div>'
        )
    parts.append('</div>')
    return "\n".join(parts)
