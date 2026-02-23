"""Element registry — discovers and runs all block-element processors."""

from colloquium.elements.chart import (
    PATTERN as CHART_PATTERN,
    process as process_chart,
    reset as reset_charts,
)
from colloquium.elements.conversation import (
    PATTERN as CONV_PATTERN,
    process as process_conversation,
    reset as reset_conversations,
)

ELEMENTS = [
    (CHART_PATTERN, process_chart),
    (CONV_PATTERN, process_conversation),
]


def process_all(html_str: str) -> str:
    """Run every registered element processor on *html_str*."""
    for pattern, processor in ELEMENTS:
        html_str = pattern.sub(lambda m: processor(m.group(1)), html_str)
    return html_str


def reset() -> None:
    """Reset all element counters (call before each build)."""
    reset_charts()
    reset_conversations()
