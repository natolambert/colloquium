"""Element registry — discovers and runs all block-element processors."""

from colloquium.elements.builtwith import (
    PATTERN as BUILTWITH_PATTERN,
    process as process_builtwith,
    reset as reset_builtwith,
)
from colloquium.elements.box import (
    PATTERN as BOX_PATTERN,
    process as process_box,
    reset as reset_boxes,
)
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
    (BUILTWITH_PATTERN, process_builtwith),
    (BOX_PATTERN, process_box),
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
    reset_builtwith()
    reset_boxes()
    reset_charts()
    reset_conversations()
