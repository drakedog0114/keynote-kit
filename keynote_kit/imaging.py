"""图片预加工（圆角 / 裁剪 / 信箱）与文本尺寸估算。

Keynote 的图片对象没有裁剪、蒙版、圆角 API，所以这些效果只能**预渲染**：
在插入前把 PNG 处理好，再作为普通图片插入。

文本方面同理——Keynote 没有 autoFit 接口，只能先量出文字实际占多高，
再决定是加高文本框还是缩小字号。
"""

from __future__ import annotations

import hashlib
import os

from PIL import Image, ImageDraw, ImageFont

CACHE_DIR = os.path.expanduser("~/.cache/keynote-kit/imaged")
os.makedirs(CACHE_DIR, exist_ok=True)

FONT_SERIF = "/System/Library/Fonts/Supplemental/Songti.ttc"
FONT_SANS = "/System/Library/Fonts/Hiragino Sans GB.ttc"

# Keynote 画布是 1920×1080 pt；1 pt = 1 px @72dpi，所以 1 px ≈ 1 pt。
PX_PER_PT = 1.0


def _font(name: str | None, size_pt: float):
    """按字体名挑一个能用的字体文件。"""
    size = max(6, int(round(size_pt * PX_PER_PT)))
    path = FONT_SERIF if name and "serif" in name.lower() else FONT_SANS
    try:
        return ImageFont.truetype(path, size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def _cached(tag: str, fn) -> str:
    """按内容哈希缓存产物，重复调用不重算。"""
    path = os.path.join(CACHE_DIR, f"{tag}.png")
    if not os.path.exists(path):
        fn(path)
    return path


def _round_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1],
                                           radius=max(0, radius), fill=255)
    return mask


def _ellipse_mask(size: tuple[int, int]) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size[0] - 1, size[1] - 1], fill=255)
    return mask


def prepare_image(src: str, box, *, radius: int = 0, shape: str = "rect",
                  crop: str = "none", focus: tuple[float, float] = (0.5, 0.5),
                  pad: float = 1.0) -> str:
    """按目标框预处理图片，返回可插入的 PNG 路径。

    radius  圆角半径（px），0 表示不处理
    shape   rect | ellipse（椭圆/圆形头像）
    crop    none | cover | contain —— cover 按目标比例裁切填满，
            contain 缩放后留白（信箱）
    focus   裁切时的焦点，0~1，(0.5, 0.5) 为正中
    """
    src = os.path.abspath(src)
    w_pt, h_pt = float(box[2]), float(box[3])
    if radius <= 0 and shape == "rect" and crop == "none":
        return src

    w = max(1, int(round(w_pt * PX_PER_PT * pad)))
    h = max(1, int(round(h_pt * PX_PER_PT * pad)))
    key = hashlib.sha1(
        f"{src}|{w}|{h}|{radius}|{shape}|{crop}|{focus[0]:.3f}|{focus[1]:.3f}"
        f"|{os.path.getmtime(src):.0f}".encode()).hexdigest()[:16]

    def build(path: str) -> None:
        im = Image.open(src).convert("RGBA")
        if crop == "cover":
            # 目标比例 = 目标框比例；按焦点裁切
            target = w / h
            sw, sh = im.size
            if sw / sh > target:          # 太宽 → 裁两侧
                nw = int(sh * target)
                x = int((sw - nw) * max(0.0, min(1.0, focus[0])))
                im = im.crop((x, 0, x + nw, sh))
            else:                          # 太高 → 裁上下
                nh = int(sw / target)
                y = int((sh - nh) * max(0.0, min(1.0, focus[1])))
                im = im.crop((0, y, sw, y + nh))
            im = im.resize((w, h), Image.LANCZOS)
        elif crop == "contain":
            im.thumbnail((w, h), Image.LANCZOS)
            canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            canvas.paste(im, ((w - im.width) // 2, (h - im.height) // 2), im)
            im = canvas
        else:
            im = im.resize((w, h), Image.LANCZOS)

        if shape == "ellipse":
            im.putalpha(_ellipse_mask(im.size))
        elif radius > 0:
            im.putalpha(_round_mask(im.size, radius))
        im.save(path)

    return _cached(key, build)


# ────────────────────────── 文本尺寸估算 ──────────────────────────
def measure(text: str, box, *, size: float = 18, font: str | None = None,
            line_spacing: float = 1.25, bold: bool = False) -> dict:
    """估算一段文字放进 box 之后实际占多大。

    返回 {"lines", "width", "height", "overflow"}：
    height 是单段高度（pt），overflow 为 True 表示比 box 高。
    """
    box_w, box_h = float(box[2]), float(box[3])
    fnt = _font(font, size)
    lines = 0
    max_w = 0.0
    for para in str(text).split("\n"):
        if not para:
            lines += 1
            continue
        # 与 page._wrap 同策略：按字符贪心换行
        cur = ""
        para_lines = 1
        for ch in para:
            trial = cur + ch
            if fnt.getlength(trial) > box_w and cur:
                max_w = max(max_w, fnt.getlength(cur))
                cur = ch
                para_lines += 1
            else:
                cur = trial
        max_w = max(max_w, fnt.getlength(cur))
        lines += para_lines

    height = lines * size * line_spacing
    return {"lines": lines, "width": round(max_w, 1), "height": round(height, 1),
            "overflow": height > box_h + 0.5}


def fit_text(text: str, box, *, size: float = 18, font: str | None = None,
             line_spacing: float = 1.25, min_size: float = 8.0,
             max_size: float = 200.0, mode: str = "shrink",
             grow_max: float = 1.6) -> dict:
    """让文字装进 box。

    mode="shrink"  放不下就缩小字号（保持框大小不变）
    mode="grow"    先放大到放得下，再考虑缩（框可以变高）
    返回 {"size", "lines", "height", "overflow", "changed"}
    """
    m = measure(text, box, size=size, font=font, line_spacing=line_spacing)
    if not m["overflow"]:
        return {"size": size, "lines": m["lines"], "height": m["height"],
                "overflow": False, "changed": False}

    if mode == "grow":
        # 允许框变高：算出需要的字号上限（受 max_size 限制）
        want = size * (m["height"] / max(1.0, float(box[3])))
        want = min(max_size, max(min_size, want))
        m2 = measure(text, box, size=want, font=font, line_spacing=line_spacing)
        if m2["height"] <= float(box[3]) * grow_max:
            return {"size": round(want, 1), "lines": m2["lines"],
                    "height": m2["height"], "overflow": False, "changed": True}

    # 二分找能放下的最大字号
    lo, hi = min_size, size
    best = min_size
    for _ in range(12):
        mid = (lo + hi) / 2
        mm = measure(text, box, size=mid, font=font, line_spacing=line_spacing)
        if mm["overflow"]:
            hi = mid
        else:
            best = mid
            lo = mid
    final = max(min_size, round(best, 1))
    mm = measure(text, box, size=final, font=font, line_spacing=line_spacing)
    return {"size": final, "lines": mm["lines"], "height": mm["height"],
            "overflow": mm["overflow"], "changed": final != size}
