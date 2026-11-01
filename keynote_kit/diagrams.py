"""信息图渲染：泳道图 / 层级图 / 集成图，输出 1920×1080 透明 PNG。

Keynote 的脚本层没有图表与流程图 API（`chart` 类并不存在），
实践中最稳的做法是先用 Python 画好、再作为整页或局部图片插入。

    from keynote_kit import diagrams
    diagrams.swimlane(
        stages=["① 扫码", "② 入驻", "③ 下单"],
        lanes=[("采购商", ["扫码", "传执照", "下单"]), ("系统", ["绑定", "", "注入价格"])],
        out="flow.png",
    )
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFont

SCALE = 2
WIDTH, HEIGHT = 1920, 1080
FONT_SANS = "/System/Library/Fonts/Hiragino Sans GB.ttc"
FONT_SERIF = "/System/Library/Fonts/Supplemental/Songti.ttc"

# 默认“米纸墨色”配色，与 Keynote「乳色纸」主题配套
PAPER = {
    "ink": (43, 36, 30),
    "sub": (110, 98, 84),
    "accent": (31, 58, 95),
    "deep": (43, 33, 24),
    "warm": (184, 92, 56),
    "light": (239, 230, 214),
    "border": (216, 205, 184),
    "highlight": (250, 236, 224),
}

BLUE = {
    "ink": (31, 35, 41),
    "sub": (100, 106, 115),
    "accent": (10, 132, 255),
    "deep": (22, 52, 94),
    "warm": (255, 122, 69),
    "light": (244, 246, 250),
    "border": (217, 222, 231),
    "highlight": (236, 245, 255),
}


def _font(size: float, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_SANS, int(size * SCALE), index=1 if bold else 0)


def _serif(size: float) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_SERIF, int(size * SCALE), index=1)
    except Exception:
        return ImageFont.truetype(FONT_SERIF, int(size * SCALE), index=0)


class Canvas:
    """透明画布 + 常用绘图原语（坐标按 1× 逻辑像素给出，内部 2× 超采样）。"""

    def __init__(self, palette: dict | None = None):
        self.pal = palette or PAPER
        self.img = Image.new("RGBA", (WIDTH * SCALE, HEIGHT * SCALE), (255, 255, 255, 0))
        self.d = ImageDraw.Draw(self.img)

    # ── 原语 ──
    def box(self, x, y, w, h, r=14, fill=None, outline=None, width=1.5):
        self.d.rounded_rectangle(
            [x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE],
            radius=r * SCALE, fill=fill, outline=outline,
            width=max(1, int(width * SCALE)))

    def rect(self, x, y, w, h, fill=None, outline=None, width=1.5):
        self.d.rectangle([x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE],
                         fill=fill, outline=outline, width=max(1, int(width * SCALE)))

    def _text(self, x, cy, text, font, color, center=False):
        bbox = self.d.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        px = x * SCALE - (w / 2 if center else 0)
        self.d.text((px, cy * SCALE - h / 2 - 2 * SCALE), text, font=font, fill=color)

    def text(self, x, cy, text, size=20, color=None, bold=False, serif=False):
        self._text(x, cy, text, _serif(size) if serif else _font(size, bold),
                   color or self.pal["ink"])

    def center(self, cx, cy, text, size=20, color=None, bold=False, serif=False):
        self._text(cx, cy, text, _serif(size) if serif else _font(size, bold),
                   color or self.pal["ink"], center=True)

    def arrow(self, x1, y1, x2, y2, color=None, width=2.5, head=12, both=False):
        color = color or self.pal["sub"]
        self.d.line([x1 * SCALE, y1 * SCALE, x2 * SCALE, y2 * SCALE],
                    fill=color, width=max(1, int(width * SCALE)))
        angle = math.atan2(y2 - y1, x2 - x1)

        def head_at(px, py, a):
            p1 = (px - head * math.cos(a - 0.42), py - head * math.sin(a - 0.42))
            p2 = (px - head * math.cos(a + 0.42), py - head * math.sin(a + 0.42))
            self.d.polygon([(px * SCALE, py * SCALE), (p1[0] * SCALE, p1[1] * SCALE),
                            (p2[0] * SCALE, p2[1] * SCALE)], fill=color)

        head_at(x2, y2, angle)
        if both:
            head_at(x1, y1, angle + math.pi)

    def header(self, kicker: str, title: str, subtitle: str | None = None):
        self.text(90, 78, kicker, 21, self.pal["accent"], bold=True)
        self.text(90, 134, title, 48, serif=True)
        self.d.line([90 * SCALE, 172 * SCALE, 1830 * SCALE, 172 * SCALE],
                    fill=self.pal["border"], width=int(2 * SCALE))
        if subtitle:
            self.text(90, 206, subtitle, 23, self.pal["sub"])

    def save(self, path: str) -> str:
        self.img.resize((WIDTH, HEIGHT), Image.LANCZOS).save(path)
        return path


# ─────────────────────────── 泳道图 ───────────────────────────
def swimlane(stages: Sequence[str], lanes: Iterable[tuple[str, Sequence[str]]],
             out: str, title: str, kicker: str = "PROCESS",
             subtitle: str | None = None, highlight: set[tuple[int, int]] | None = None,
             palette: dict | None = None) -> str:
    """横向泳道图：行=角色，列=阶段；highlight 用 (行, 列) 标出定制点。"""
    c = Canvas(palette)
    c.header(kicker, title, subtitle)

    lanes = [(name, list(items)) for name, items in lanes]
    x0, y0 = 306, 292
    # 列宽自适应：阶段少时拉开填满可用宽度，多时收窄
    colw = int(min(300, max(150, (1830 - x0) / max(1, len(stages)))))
    laneh, labw = 130, 196
    total = colw * len(stages)
    hl = highlight or set()

    for i, stage in enumerate(stages):
        cx = x0 + colw * i + colw / 2
        c.box(cx - 94, 236, 188, 44, 22, fill=c.pal["light"])
        c.center(cx, 258, stage, 20, c.pal["deep"], bold=True)

    for i, (name, _) in enumerate(lanes):
        ly = y0 + laneh * i
        c.box(90, ly + 18, labw, laneh - 36, 12, fill=(255, 255, 255, 235),
              outline=c.pal["border"])
        c.center(90 + labw / 2, ly + laneh / 2, name, 19, c.pal["deep"], bold=True)

    for i in range(len(stages) + 1):
        gx = x0 + colw * i
        c.d.line([gx * SCALE, y0 * SCALE, gx * SCALE, (y0 + laneh * len(lanes)) * SCALE],
                 fill=c.pal["border"], width=max(1, int(1.2 * SCALE)))

    for r, (_, items) in enumerate(lanes):
        for col, text in enumerate(items):
            if not text:
                continue
            cx = x0 + colw * col + colw / 2
            cy = y0 + laneh * r + laneh / 2
            bw, bh = colw - 40, 84
            is_hl = (r, col) in hl
            c.box(cx - bw / 2, cy - bh / 2, bw, bh, 10,
                  fill=c.pal["highlight"] if is_hl else (255, 255, 255, 235),
                  outline=c.pal["warm"] if is_hl else c.pal["border"],
                  width=2 if is_hl else 1.5)
            lines = text.split("\n")
            if len(lines) == 1:
                c.center(cx, cy, text, 19, bold=True)
            else:
                c.center(cx, cy - 19, lines[0], 19, bold=True)
                c.center(cx, cy + 21, lines[1], 17, c.pal["sub"])

    ay = y0 + laneh * len(lanes) + 46
    c.text(90, ay, "推进", 19, c.pal["deep"], bold=True)
    c.arrow(200, ay, x0 + total - 20, ay, c.pal["deep"], 2.5, 12)

    ly = ay + 50
    c.box(90, ly - 12, 24, 24, 6, fill=c.pal["highlight"], outline=c.pal["warm"], width=2)
    c.text(128, ly, "高亮 = 关键差异点", 20, c.pal["sub"])
    return c.save(out)


# ─────────────────────────── 层级图 ───────────────────────────
def hierarchy(rows: Sequence[tuple[str, str]], cards: Sequence[tuple[str, str]],
              out: str, title: str, kicker: str = "GOVERNANCE",
              subtitle: str | None = None, palette: dict | None = None) -> str:
    """左侧纵向层级 + 右侧标签卡，适合组织架构 / 角色权限页。"""
    c = Canvas(palette)
    c.header(kicker, title, subtitle)

    x, w = 90, 700
    total_h = len(rows) * 124 + (len(rows) - 1) * 26
    y = 296
    for i, (name, desc) in enumerate(rows):
        primary = i == 0
        c.box(x, y, w, 124, 14,
              fill=c.pal["deep"] if primary else c.pal["light"],
              outline=None if primary else c.pal["border"])
        c.text(x + 34, y + 40, name, 27,
               (255, 255, 255) if primary else c.pal["ink"], bold=True)
        c.text(x + 34, y + 84, desc, 18,
               (255, 255, 255) if primary else c.pal["sub"])
        if i < len(rows) - 1:
            c.arrow(x + 60, y + 124, x + 60, y + 150, c.pal["accent"], 2.5, 9)
        y += 150

    accent_cycle = [c.pal["warm"], c.pal["accent"], c.pal["sub"]]
    cy = 296
    for i, (tag, desc) in enumerate(cards):
        color = accent_cycle[i % len(accent_cycle)]
        c.box(880, cy, 950, 150, 16, outline=c.pal["border"])
        c.d.rounded_rectangle([(880 + 34) * SCALE, (cy + 42) * SCALE,
                               (880 + 42) * SCALE, (cy + 108) * SCALE],
                              radius=4 * SCALE, fill=color)
        c.text(942, cy + 54, tag, 24, color, bold=True)
        c.text(942, cy + 100, desc, 21, c.pal["sub"])
        cy += 178
    return c.save(out)


# ─────────────────────────── 集成图 ───────────────────────────
def integration(lanes: Sequence[tuple[str, Sequence[tuple[str, str, bool]]]],
                out: str, title: str, left_label: str = "外部系统",
                right_label: str = "业务平台", kicker: str = "INTEGRATION",
                subtitle: str | None = None, palette: dict | None = None,
                footer: str | None = None) -> str:
    """双端集成图：lanes 里每项是 (方向标签, 说明, 是否双向)。"""
    c = Canvas(palette)
    c.header(kicker, title, subtitle)

    lab_x, lab_w = 90, 150
    left_x, left_w = 270, 210
    right_x, right_w = 1440, 390
    mid_l, mid_r = 530, 1390

    c.box(left_x, 246, left_w, 54, 10, fill=c.pal["deep"])
    c.center(left_x + left_w / 2, 273, left_label, 23, (255, 255, 255), bold=True)
    c.box(right_x, 246, right_w, 54, 10, fill=c.pal["accent"])
    c.center(right_x + right_w / 2, 273, right_label, 23, (255, 255, 255), bold=True)

    y = 330
    laneh = 200
    for i, (name, flows) in enumerate(lanes):
        ly = y + i * laneh
        c.rect(lab_x, ly, right_x + right_w - lab_x, laneh - 22,
               fill=(255, 255, 255, 110), outline=c.pal["border"])
        c.box(lab_x + 14, ly + (laneh - 22) / 2 - 40, lab_w - 28, 80, 10,
              fill=(255, 255, 255, 235), outline=c.pal["border"])
        c.center(lab_x + lab_w / 2, ly + (laneh - 22) / 2, name, 24, c.pal["deep"], bold=True)

        for j, (direction, desc, both) in enumerate(flows):
            ry = ly + 54 + j * 84
            to_right = "→" in direction and direction.index("→") > 2
            color = c.pal["accent"] if to_right or both else c.pal["deep"]
            c.text(mid_l, ry - 26, direction, 21, color, bold=True)
            c.text(mid_l, ry + 30, desc, 19, c.pal["sub"])
            if both:
                c.arrow(mid_l + 30, ry, mid_r, ry, color, 2.5, 12)
                c.arrow(mid_r, ry, mid_l + 30, ry, color, 2.5, 12)
            elif to_right:
                c.arrow(left_x + left_w + 24, ry, right_x - 24, ry, color, 2.5, 12)
            else:
                c.arrow(right_x - 24, ry, left_x + left_w + 24, ry, color, 2.5, 12)

    if footer:
        c.box(90, 964, 1740, 74, 12, fill=c.pal["light"])
        c.text(122, 1001, footer, 22, c.pal["sub"])
    return c.save(out)
