"""声明式建页：一个 spec 生成一整页。

    python examples/04_declarative.py

对比 02_demo_deck.py：那边是逐元素调用，这里是「描述整页 → 一次生成」。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keynote_kit import Deck
from keynote_kit.page import apply_page

COVER = {
    "background": {"type": "solid", "color": "#F4EBDD"},
    "elements": [
        {"id": "k", "type": "text", "text": "KEYNOTE KIT · 声明式页面",
         "box": [150, 300, 1600, 60], "style": {"size": 26, "color": "#6E6259"}},
        {"id": "t", "type": "text", "text": "一次调用\n生成一整页",
         "box": [150, 380, 1500, 320], "style": {"size": 96, "font": "Songti SC Bold", "color": "#2B2420"}},
        {"id": "s", "type": "text", "text": "page spec → 编译 → 校验 → 回滚",
         "box": [150, 760, 1500, 60], "style": {"size": 30, "color": "#1F3A5F"}},
    ],
}

CARDS = {
    "background": {"type": "solid", "color": "#F4EBDD"},
    "elements": [
        {"id": "t", "type": "text", "text": "三个改动",
         "box": [150, 110, 1620, 110], "style": {"size": 54, "font": "Songti SC Bold", "color": "#2B2420"}},
        {"id": "c1", "type": "card", "box": [150, 290, 500, 400],
         "style": {"fill": "#FFFFFF", "radius": 26},
         "text": {"title": "整页 Spec", "body": "一页一个 JSON，元素顺序即 z 序。",
                  "titleSize": 30, "bodySize": 17, "valign": "center"}},
        {"id": "c2", "type": "card", "box": [710, 290, 500, 400],
         "style": {"fill": "#1F3A5F", "radius": 26},
         "text": {"title": "事务回滚", "body": "写完立刻回读，不符就清空本页并抛错。",
                  "titleColor": "#FFFFFF", "bodyColor": "#C9D2E0",
                  "titleSize": 30, "bodySize": 17, "valign": "center"}},
        {"id": "c3", "type": "card", "box": [1270, 290, 500, 400],
         "style": {"fill": "#FFFFFF", "radius": 26, "border": "#D9CFBE", "borderWidth": 2},
         "text": {"title": "背景仿真", "body": "底层整页图解决 Keynote 没有背景 API。",
                  "titleSize": 30, "bodySize": 17, "valign": "center"}},
    ],
}


def main() -> None:
    deck = Deck.create(theme="乳色纸")
    for i, spec in enumerate([COVER, CARDS], start=1):
        deck.add_slide("空白")
        result = apply_page(deck, i, spec)
        print(f"第 {i} 页：{result['elements']} 元素，revision {result['revision']}")
    out = deck.export("/tmp/declarative-demo", "images")
    print("导出：", out)


if __name__ == "__main__":
    main()
