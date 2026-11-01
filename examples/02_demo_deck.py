"""完整示例：5 页 deck，覆盖文本 / 卡片 / 表格 / 图表 / 结论。

    python examples/02_demo_deck.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw

from keynote_kit import Deck, charts

Path = pathlib.Path
OUT = Path("out")
OUT.mkdir(exist_ok=True)

INK, SUB, ACCENT, WARM = "#2B2420", "#6E6259", "#1F3A5F", "#B85C38"
CARD, BORDER = (250, 240, 226, 255), (214, 202, 182, 255)


def card_strip(path: Path, count: int, w: int, h: int, gap: int) -> str:
    """把 count 个圆角卡片底板合成一张透明 PNG（多图元素的 z 序不可靠）。"""
    strip = Image.new("RGBA", (w * count + gap * (count - 1), h), (0, 0, 0, 0))
    for i in range(count):
        c = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
        d = ImageDraw.Draw(c)
        d.rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1], radius=56, fill=CARD, outline=BORDER, width=3)
        strip.alpha_composite(c.resize((w, h), Image.LANCZOS), (i * (w + gap), 0))
    strip.save(path)
    return str(path)


deck = Deck.create(theme="乳色纸")

# ── 封面 ──
s = deck.add_slide("空白")
deck.add_text(s, "keynote-kit", 150, 300, 1500, 120, size=84, color=INK, font="Songti SC Bold")
deck.add_text(s, "精确排版 · 原生表格 · 图表 · 信息图", 150, 450, 1500, 80, size=34, color=SUB)
deck.add_text(s, "示例文档", 150, 560, 900, 60, size=26, color=WARM)
deck.verify(s, expect=3)

# ── 三卡 ──
s = deck.add_slide("空白")
deck.add_text(s, "三个补齐点", 150, 120, 1200, 100, size=56, color=INK, font="Songti SC Bold")
cw, ch, gap, top = 480, 340, 60, 330
deck.add_image(s, card_strip(OUT / "cards.png", 3, cw, ch, gap), 150, top, cw * 3 + gap * 2, ch)
for i, (title, desc) in enumerate([
    ("精确排版", "文本框可指定坐标 / 字号 / 颜色 / 字体"),
    ("原生表格", "建表、写单元格、定位尺寸一次完成"),
    ("图表能力", "matplotlib 出图，透明背景叠加"),
]):
    x = 150 + i * (cw + gap)
    deck.add_text(s, title, x + 40, top + 50, cw - 80, 60, size=38, color=ACCENT, font="Songti SC Bold")
    deck.add_text(s, desc, x + 40, top + 140, cw - 80, 160, size=24, color=SUB)

# ── 表格 ──
s = deck.add_slide("空白")
deck.add_text(s, "原生表格", 150, 120, 1200, 100, size=56, color=INK, font="Songti SC Bold")
deck.add_table(s, [
    ["业务域", "承接方式", "关键结论"],
    ["准入与资格", "全定制", "B2B 多员工 + 资质审核"],
    ["可售与价格", "定制", "采购商 × 商品专属价"],
    ["采购交易", "定制", "现付 / 记账双通道"],
], 150, 300, 1620, 420)

# ── 图表 ──
s = deck.add_slide("空白")
deck.add_text(s, "图表能力", 150, 120, 1200, 100, size=56, color=INK, font="Songti SC Bold")
bar = charts.bar_chart(["准入", "价格", "交易", "赠品", "资金"], [18, 26, 22, 14, 20],
                       title="各域工作量占比", path=str(OUT / "bar.png"), value_suffix="%")
line = charts.line_chart(["W1", "W2", "W3", "W4", "W5"], {"开发": [2, 5, 9, 14, 18],
                                                        "联调": [0, 1, 3, 6, 11]},
                         title="进度趋势", path=str(OUT / "line.png"))
deck.add_image(s, bar, 110, 280, 860, 480)
deck.add_image(s, line, 1000, 280, 820, 480)

print("页数:", deck.slide_count())
deck.export(str(OUT / "demo"), "images")
deck.save(str(OUT / "demo.key"))
print("完成 →", OUT / "demo.key")
