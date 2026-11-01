"""keynote-kit — 用 Python 精确驱动 Apple Keynote。

补齐 iwork-mcp / AppleScript 在版式、图表、错误处理上的缺口。
"""
from .deck import Deck
from .runner import KeynoteError

__version__ = "0.4.0"
__all__ = ["Deck", "KeynoteError", "__version__"]
