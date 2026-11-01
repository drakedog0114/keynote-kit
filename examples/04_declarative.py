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


CHART = {
    "background": {"type": "solid", "color": "#F4EBDD"},
    "elements": [
        {"id": "t", "type": "text", "text": "图表也是元素",
         "box": [150, 90, 1620, 90], "style": {"size": 50, "font": "Songti SC Bold", "color": "#2B2420"}},
        {"id": "ch", "type": "chart", "box": [150, 200, 1620, 760],
         "chart": {"kind": "line", "labels": ["1月", "2月", "3月", "4月"],
                   "series": {"会员数": [1200, 1800, 2600, 3900], "复购率": [12, 15, 19, 24]},
                   "title": "增长趋势"}},
    ],
}

DIAGRAM = {
    "background": {"type": "solid", "color": "#F4EBDD"},
    "elements": [
        {"id": "dg", "type": "diagram", "box": [130, 120, 1660, 900],
         "diagram": {"kind": "swimlane", "title": "采购商入驻与下单",
                     "subtitle": "两泳道 · 三阶段 · 一个定制点",
                     "stages": ["① 扫码", "② 入驻", "③ 下单"],
                     "lanes": [["采购商", ["扫门店码", "上传执照", "选品下单"]],
                               ["系统", ["绑定门店关系", "校验资质", "注入采购价"]]],
                     "highlight": [[1, 2]]}},
    ],
}


SLOT = {
    "elements": [
        {"id": "h", "type": "text", "slot": "title",
         "text": "写进母版占位符", "box": [150, 90, 1620, 100]},
        {"id": "b", "type": "text", "slot": "body",
         "text": "文字仍然是可编辑的文本框\n左对齐、项目符号、段间距都来自母版\n这是 card 做不到的",
         "box": [150, 260, 760, 420]},
        {"id": "ch", "type": "chart", "box": [980, 240, 760, 380],
         "chart": {"kind": "bar", "labels": ["A", "B", "C"], "values": [18, 26, 22],
                   "title": "模块工作量"}},
        {"id": "c1", "type": "card", "box": [980, 660, 760, 180],
         "style": {"fill": "#1F3A5F", "radius": 24},
         "text": {"title": "卡片", "body": "栅格化，用于装饰与强调。",
                  "titleColor": "#FFFFFF", "bodyColor": "#C9D2E0",
                  "titleSize": 24, "bodySize": 15, "valign": "center"}},
    ],
}


def main() -> None:
    specs = [(COVER, "空白"), (CARDS, "空白"), (CHART, "空白"),
             (DIAGRAM, "空白"), (SLOT, "标题与项目符号")]
    deck = Deck.create(theme="乳色纸")
    for i, (spec, master) in enumerate(specs, start=1):
        deck.add_slide(master)
        if i == 1 and deck.slide_count() > 1:
            deck.remove_slide(1)          # 删掉新建文稿自带的空页
        idx = deck.slide_count()
        result = apply_page(deck, idx, spec)
        print(f"第 {idx} 页：{result['elements']} 元素，revision {result['revision']}")
    deck.save(__import__("os").path.expanduser("~/Desktop/声明式示例-5页.key"))
    out = deck.export("/tmp/declarative-demo", "images")
    print("导出：", out)


if __name__ == "__main__":
    main()
