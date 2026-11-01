"""Shared markdown-it configuration.

Every renderer in colloquium (main slide pipeline and block elements like box
and conversation) should build on this base so typography is consistent:
smart quotes, en/em dashes from ``--``/``---``, and table support everywhere.
"""

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin


def create_base_md() -> MarkdownIt:
    """Return a markdown-it renderer with the deck's shared typography."""
    md = MarkdownIt("commonmark", {"html": True, "typographer": True})
    md.enable(["table", "replacements", "smartquotes"])
    return md


def create_math_md() -> MarkdownIt:
    """Return the shared renderer plus $...$ / $$...$$ math support.

    The dollarmath plugin protects math from markdown processing (e.g. _
    becoming <em>). KaTeX renders the resulting .math elements client-side.
    """
    md = create_base_md()
    dollarmath_plugin(md, double_inline=True)
    return md
