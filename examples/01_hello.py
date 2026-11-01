"""最小示例：一页标题 + 一行正文。

    python examples/01_hello.py
"""

from pathlib import Path

from keynote_kit import Deck

OUT = Path("out")
OUT.mkdir(exist_ok=True)

deck = Deck.create(theme="乳色纸")
slide = deck.add_slide("空白")

deck.add_text(slide, "Hello, Keynote", 160, 380, 1400, 140,
              size=96, color="#2B2420", font="Songti SC Bold")
deck.add_text(slide, "由 keynote-kit 生成 · 坐标与字号完全可控", 160, 540, 1400, 80,
              size=34, color="#6E6259")

print(deck.verify(slide, expect=2))
deck.export(str(OUT / "hello"), "images")
print("导出 →", OUT / "hello")
