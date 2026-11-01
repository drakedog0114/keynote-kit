"""幻灯片转场、对象透明度/旋转、以及元素 z 序调整。

三块能力都是 Keynote **原生可用**的（之前没被用到）：

* 转场：slide 的 `transition properties`（12 种效果 + 时长 + 延迟）
* 透明度 / 旋转：shape / image / text item 都支持
* z 序：Keynote 没有 z-index API，但**插入顺序即层级**（后插的在上），
  所以「提到最上层」= 删掉再用文件重新插入，「下沉」= 重建整页元素顺序。

动画构建（逐个对象出现）**没有 API**，只能靠 UI 自动化，见 `animate.py`。
"""

from __future__ import annotations

from .runner import applescript, esc_text, jxa

# sdef 里 transition effects 枚举的全部取值
TRANSITIONS = [
    "no transition effect", "magic move", "shimmer", "sparkle", "swing",
    "object cube", "object flip", "object pop", "object push",
    "object revolve", "object zoom", "perspective",
]

# 元素类型 → AppleScript 集合名
KIND_MAP = {
    "text": "text items", "image": "images", "shape": "shapes",
    "table": "tables", "chart": "charts",
}


def set_transition(doc: str, slide: int, effect: str = "object push",
                   duration: float = 0.6, delay: float = 0.0) -> dict:
    """给某页设置转场效果。"""
    if effect not in TRANSITIONS:
        raise ValueError(f"不支持的转场：{effect}；可选：{', '.join(TRANSITIONS)}")
    applescript(f'''
tell application "Keynote"
  tell document {esc_text(doc)}
    set transition properties of slide {slide} of it to ¬
      {{transition effect:{effect}, transition duration:{float(duration)}, transition delay:{float(delay)}}}
  end tell
end tell''')
    return {"slide": slide, "transition": effect,
            "duration": duration, "delay": delay}


def get_transition(doc: str, slide: int) -> dict:
    """读回某页的转场设置。

    注意：`transition properties` 是 record 类型，JXA 访问会报「不能转换类型」，
    所以这里走 AppleScript（AppleScript 能直接读 record 的属性）。
    """
    raw = applescript(f'''
tell application "Keynote"
  tell document {esc_text(doc)}
    set tp to transition properties of slide {slide} of it
    return ((transition effect of tp) as text) & "|" & ((transition duration of tp) as text) & "|" & ((transition delay of tp) as text)
  end tell
end tell''').strip()
    parts = raw.split("|")
    if len(parts) != 3:
        return {"error": raw}
    try:
        return {"effect": parts[0], "duration": float(parts[1]), "delay": float(parts[2])}
    except ValueError:
        return {"error": raw}


def set_opacity(doc: str, slide: int, kind: str, index: int, opacity: float) -> float:
    """设置元素不透明度。

    这里用 **0~1** 的直觉写法，底层 Keynote 用的是 **0~100 百分比**，这里做换算。
    实测：40（百分比）= 黑图叠白底得到 (153,153,153)，即 40% 不透明。
    """
    coll = KIND_MAP.get(kind)
    if not coll:
        raise ValueError(f"不支持的元素类型：{kind}")
    pct = max(0.0, min(1.0, float(opacity))) * 100.0
    applescript(f'''
tell application "Keynote"
  tell document {esc_text(doc)}
    set opacity of {kind} {index} of slide {slide} of it to {pct}
  end tell
end tell''')
    return round(pct / 100.0, 4)


def set_rotation(doc: str, slide: int, kind: str, index: int, degrees: float) -> float:
    """设置元素旋转角度（度，顺时针）。"""
    coll = KIND_MAP.get(kind)
    if not coll:
        raise ValueError(f"不支持的元素类型：{kind}")
    applescript(f'''
tell application "Keynote"
  tell document {esc_text(doc)}
    set rotation of {kind} {index} of slide {slide} of it to {float(degrees)}
    return (rotation of {kind} {index} of slide {slide} of it as text)
  end tell
end tell''')
    return float(degrees)


# ────────────────────────── z 序 ──────────────────────────
def element_order(doc: str, slide: int) -> dict:
    """按画布实际叠放顺序列出页面元素。

    Keynote 的 AppleScript 集合按类型分组，且**没有 z-index**；
    只能靠「重新插入顺序」反推。这里返回各类元素当前的插入顺序，
    供上层判断谁盖住了谁。
    """
    raw = jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  let doc = null; const ds = K.documents();
  for (let i = 0; i < ds.length; i++) if (String(ds[i].name()) === p.doc) doc = ds[i];
  const s = doc.slides[p.slide - 1];
  const grab = (arr, kind) => {
    const out = [];
    for (let i = 0; i < arr.length; i++) {
      const e = arr[i]; const q = e.position();
      out.push({ kind: kind, index: i + 1,
                 x: Math.round(q.x), y: Math.round(q.y),
                 w: Math.round(e.width()), h: Math.round(e.height()) });
    }
    return out;
  };
  return JSON.stringify({
    text: grab(s.textItems, 'text'),
    image: grab(s.images, 'image'),
    shape: grab(s.shapes, 'shape'),
    table: grab(s.tables, 'table')
  });
}""", {"doc": doc, "slide": slide})
    return raw if isinstance(raw, dict) else raw.get("value", raw)


def bring_to_front(doc: str, slide: int, kind: str, index: int,
                   image_path: str | None = None) -> dict:
    """把某个元素提到最上层。

    Keynote 没有 z-index，只能**删掉再重新插入**（新插入的会在最上面）。
    文字元素无法重建（读不出富文本），所以只支持 image / shape / table，
    且需要知道图片在磁盘上的路径。
    """
    coll = KIND_MAP.get(kind)
    if not coll:
        raise ValueError(f"不支持的元素类型：{kind}")
    if kind == "text":
        raise ValueError(
            "文字元素无法重建（Keynote 读不回富文本结构），"
            "请改用「按 spec 重建整页」的方式调整层级")
    if not image_path:
        raise ValueError("提到顶层需要提供该元素的原始文件路径")

    # 记下几何 → 删 → 重新插入 → 复位几何
    geo = jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  let doc = null; const ds = K.documents();
  for (let i = 0; i < ds.length; i++) if (String(ds[i].name()) === p.doc) doc = ds[i];
  const s = doc.slides[p.slide - 1];
  const arr = p.kind === 'image' ? s.images : (p.kind === 'shape' ? s.shapes : s.tables);
  const e = arr[p.index - 1]; const q = e.position();
  return JSON.stringify({ x: q.x, y: q.y, w: e.width(), h: e.height() });
}""", {"doc": doc, "slide": slide, "kind": kind, "index": index})
    if isinstance(geo, dict) and "error" in geo:
        raise RuntimeError(geo["error"])

    applescript(f'''
tell application "Keynote"
  tell document {esc_text(doc)}
    delete {kind} {index} of slide {slide} of it
  end tell
end tell''')

    if kind == "image":
        jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  let doc = null; const ds = K.documents();
  for (let i = 0; i < ds.length; i++) if (String(ds[i].name()) === p.doc) doc = ds[i];
  doc.slides[p.slide - 1].images.push(K.Image({ file: Path(p.path) }));
  return "ok";
}""", {"doc": doc, "slide": slide, "path": image_path})
    else:
        raise ValueError("目前只有图片支持提到顶层")

    applescript(f'''
tell application "Keynote"
  tell document {esc_text(doc)}
    set e to image 1 of slide {slide} of it
    set width of e to {geo["w"]}
    set height of e to {geo["h"]}
    set position of e to {{{geo["x"]}, {geo["y"]}}}
  end tell
end tell''')
    return {"slide": slide, "kind": kind, "from": index, "action": "brought_to_front"}
