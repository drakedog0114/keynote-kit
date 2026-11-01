"""声明式页面：一个 spec 建一整页，带事务回滚与回读校验。

性能设计（实测 osascript 每次跨越 AppleEvent 约 60–90ms）：

    1 次 JXA   清空 + 建全部元素 + 上样式
    1 次 AS    批量取文本列表 → 内存里匹配索引 → 逐元素 set properties → 批量回读位置
               （每元素只花 1 次事件，匹配不花事件）

Keynote 的坑：空白版式会带 0×0 占位符、JXA 设 position 会被静默丢弃，
所以定位必须走 AppleScript，且不能依赖「新建元素在末尾」的假设。
"""

from __future__ import annotations

import hashlib
import os

from PIL import Image

from .runner import KeynoteError, applescript, esc_text, jxa

CACHE_DIR = os.path.expanduser("~/.cache/keynote-kit/bg")
TOLERANCE = 20.0


class SpecError(KeynoteError):
    """spec 不合法。"""


class VerifyError(KeynoteError):
    """写入后回读不符。"""


# ────────────────────────── 背景 ──────────────────────────
def solid_png(hex_color: str) -> str:
    key = hex_color.lstrip("#").lower()
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{key}.png")
    if not os.path.exists(path):
        rgb = tuple(int(key[i:i + 2], 16) for i in (0, 2, 4))
        Image.new("RGB", (192, 108), rgb).save(path)
    return path


CARD_DIR = os.path.expanduser("~/.cache/keynote-kit/cards")


FONT_SERIF = "/System/Library/Fonts/Supplemental/Songti.ttc"
FONT_SANS = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def _font(path: str, size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(path, size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def _wrap(text: str, font, max_width: float) -> list[str]:
    """按字符贪心换行，中英文都适用。"""
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        trial = cur + ch
        if font.getlength(trial) > max_width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def card_png(fill: str, width: float, height: float, radius: int = 24,
             border: str | None = None, border_width: int = 0, alpha: float = 1.0,
             text: dict | None = None) -> str:
    """Keynote 的 shape 没有填充色、文本也不可设对齐，所以卡片连文字一起渲染成 PNG。

    text: {title, body, titleSize, bodySize, titleColor, bodyColor,
           padding, gap, align: left|center, lineHeight}
    """
    from PIL import ImageDraw

    t = text or {}
    meta = (t.get("title", ""), t.get("body", ""), t.get("titleSize", 0),
            t.get("bodySize", 0), t.get("align", "left"), t.get("padding", 40))
    border_key = border.lstrip("#").lower() if border else "none"
    key = (f"{fill.lstrip('#').lower()}_{int(width)}x{int(height)}_r{radius}_"
           f"{border_key}_{border_width}_a{alpha:.2f}_{abs(hash(meta)) % 10**8}")
    os.makedirs(CARD_DIR, exist_ok=True)
    path = os.path.join(CARD_DIR, f"{key}.png")
    if os.path.exists(path):
        return path

    scale = 2
    w, h = max(2, int(width * scale)), max(2, int(height * scale))
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    rgb = tuple(int(fill.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    draw.rounded_rectangle(
        [0, 0, w - 1, h - 1], radius=radius * scale, fill=rgb + (max(0, min(255, int(255 * alpha))),),
        outline=(tuple(int(border.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (255,)) if border else None,
        width=max(1, border_width * scale) if border else 0)

    if t.get("title") or t.get("body"):
        pad = int(t.get("padding", 40) * scale)
        inner = w - pad * 2
        align = t.get("align", "left")
        # 先算总高，支持垂直居中
        total = 0
        tf = bf = None
        if t.get("title"):
            tf = _font(FONT_SERIF, int(t.get("titleSize", 34) * scale))
            tl = _wrap(str(t["title"]), tf, inner)
            total += len(tl) * int(tf.size * 1.25) + int(t.get("gap", 16) * scale)
        if t.get("body"):
            bf = _font(FONT_SANS, int(t.get("bodySize", 19) * scale))
            bl = _wrap(str(t["body"]), bf, inner)
            total += len(bl) * int(bf.size * float(t.get("lineHeight", 1.55)))
        y = pad
        if t.get("valign") == "center":
            y = max(pad, (h - total) // 2)
        if t.get("title"):
            tf = _font(FONT_SERIF, int(t.get("titleSize", 34) * scale))
            for line in _wrap(str(t["title"]), tf, inner):
                draw.text((pad, y), line, font=tf, fill=t.get("titleColor", "#2B2420"))
                y += int(tf.size * 1.25)
            y += int(t.get("gap", 16) * scale)
        if t.get("body"):
            bf = _font(FONT_SANS, int(t.get("bodySize", 19) * scale))
            lh = int(bf.size * float(t.get("lineHeight", 1.55)))
            for line in _wrap(str(t["body"]), bf, inner):
                x = pad
                if align == "center":
                    x = (w - bf.getlength(line)) / 2
                draw.text((x, y), line, font=bf, fill=t.get("bodyColor", "#6E6259"))
                y += lh
    im.save(path)
    return path


FIT_DIR = os.path.expanduser("~/.cache/keynote-kit/fit")


def _trim(path: str) -> str:
    """裁掉透明边（图/流程图模板常留大片空白），让内容真正填满 box。"""
    try:
        with Image.open(path) as im:
            if im.mode != "RGBA":
                return path
            bbox = im.getchannel("A").getbbox()
            if bbox and bbox != (0, 0, im.width, im.height):
                im.crop(bbox).save(path)
    except Exception:  # noqa: BLE001
        pass
    return path


def _hash_name(prefix: str, cfg) -> str:
    import json as _json
    os.makedirs(FIT_DIR, exist_ok=True)
    key = hashlib.sha1(_json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    return os.path.join(FIT_DIR, f"{prefix}_{key}.png")


def chart_png(cfg: dict) -> str:
    """条形 / 折线 / 环形图，透明底，自动贴合主题。"""
    from . import charts as ch

    path = _hash_name("chart", cfg)
    if os.path.exists(path):
        return path
    kind = cfg.get("kind", "bar")
    labels = cfg.get("labels") or []
    title = cfg.get("title", "")
    if kind == "bar":
        ch.bar_chart(labels, cfg.get("values") or [], title=title, path=path,
                     color=cfg.get("color", ch.ACCENT), value_suffix=cfg.get("suffix", ""))
    elif kind == "line":
        ch.line_chart(labels, cfg.get("series") or {}, title=title, path=path)
    elif kind == "donut":
        ch.donut_chart(labels, cfg.get("values") or [], title=title, path=path)
    else:
        raise SpecError(f"chart.kind 不支持：{kind}")
    return _trim(path)


def diagram_png(cfg: dict) -> str:
    """泳道 / 层级 / 集成信息图。"""
    from . import diagrams as dg

    path = _hash_name("diagram", cfg)
    if os.path.exists(path):
        return path
    kind = cfg.get("kind", "swimlane")
    pal = dg.PAPER if cfg.get("palette", "paper") == "paper" else dg.BLUE
    if kind == "swimlane":
        dg.swimlane(stages=cfg.get("stages") or [], lanes=cfg.get("lanes") or [],
                    out=path, title=cfg.get("title", ""), kicker=cfg.get("kicker", "PROCESS"),
                    subtitle=cfg.get("subtitle"), highlight={tuple(h) for h in cfg.get("highlight", [])},
                    palette=pal)
    elif kind == "hierarchy":
        dg.hierarchy(rows=cfg.get("rows") or [], cards=cfg.get("cards") or [],
                     out=path, title=cfg.get("title", ""), kicker=cfg.get("kicker", "GOVERNANCE"),
                     subtitle=cfg.get("subtitle"), palette=pal)
    elif kind == "integration":
        dg.integration(lanes=cfg.get("lanes") or [], out=path, title=cfg.get("title", ""),
                       kicker=cfg.get("kicker", "INTEGRATION"), subtitle=cfg.get("subtitle"),
                       palette=pal)
    else:
        raise SpecError(f"diagram.kind 不支持：{kind}")
    return _trim(path)


# ────────────────────────── spec 校验 ──────────────────────────
def normalise(spec: dict):
    if not isinstance(spec, dict):
        raise SpecError("spec 必须是对象")

    bg = spec.get("background")
    if bg:
        kind = bg.get("type", "solid")
        if kind not in ("solid", "image"):
            raise SpecError(f"background.type 不支持：{kind}")
        if kind == "image":
            if not bg.get("path") or not os.path.exists(bg["path"]):
                raise SpecError(f"背景图不存在：{bg.get('path')}")
            bg["path"] = os.path.abspath(bg["path"])
        else:
            bg["path"] = solid_png(bg.get("color", "#FFFFFF"))

    out, ids = [], set()
    for i, raw in enumerate(spec.get("elements", [])):
        box = raw.get("box")
        if not (isinstance(box, (list, tuple)) and len(box) == 4):
            raise SpecError(f"第 {i} 个元素 box 必须是 [x, y, w, h]")
        kind = raw.get("type", "text")
        if kind not in ("text", "shape", "image", "table", "card", "chart", "diagram"):
            raise SpecError(f"第 {i} 个元素类型不支持：{kind}")
        eid = str(raw.get("id") or f"{kind}{i}")
        if eid in ids:
            raise SpecError(f"元素 id 重复：{eid}")
        ids.add(eid)
        item = {"id": eid, "type": kind, "box": [float(v) for v in box],
                "text": str(raw.get("text", "")), "style": raw.get("style") or {}}
        if raw.get("slot"):
            if kind != "text":
                raise SpecError(f"元素 {eid}：slot 只能用于 text")
            item["slot"] = str(raw["slot"])
        if kind == "image":
            path = raw.get("path", "")
            if not path or not os.path.exists(path):
                raise SpecError(f"图片不存在：{path}")
            item["path"] = os.path.abspath(path)
        if kind == "chart":
            item["path"] = chart_png(raw.get("chart") or {})
        if kind == "diagram":
            item["path"] = diagram_png(raw.get("diagram") or {})
        if kind == "card":
            st = item["style"]
            item["path"] = card_png(
                fill=st.get("fill", "#FFFFFF"),
                width=item["box"][2], height=item["box"][3],
                radius=int(st.get("radius", 24)),
                border=st.get("border"),
                border_width=int(st.get("borderWidth", 0)),
                alpha=float(st.get("alpha", 1.0)),
                text=raw.get("text") or None,
            )
        if kind == "table":
            data = raw.get("data") or []
            if not data:
                raise SpecError(f"表格 {eid} 缺少 data")
            item["data"] = data
        # 图片类保持比例：偏差 >5% 时按 PNG 真实比例修正高度，避免拉伸
        if kind in ("image", "chart", "diagram") and item.get("path"):
            try:
                with Image.open(item["path"]) as im:
                    pw, ph = im.size
                bw, bh = item["box"][2], item["box"][3]
                if bw > 0 and ph > 0 and abs((bh / bw) - (ph / pw)) / (ph / pw) > 0.05:
                    item["box"][3] = round(bw * ph / pw, 1)
            except Exception:  # noqa: BLE001
                pass
        out.append(item)
    return bg, out


# ────────────────────────── 建元素（JXA） ──────────────────────────
_JXA_CREATE = r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const slide = K.documents.byName(p.doc).slides[p.slide - 1];

  if (p.clear) {
    const kill = (list) => { for (let i = list.length - 1; i >= 0; i--) { try { list[i].delete(); } catch (e) {} } };
    kill(slide.movies); kill(slide.tables); kill(slide.images);
    kill(slide.shapes); kill(slide.lines); kill(slide.textItems);
  }

  const styleParas = (obj, st) => {
    const paras = obj.objectText.paragraphs;
    for (let i = 0; i < paras.length; i++) {
      if (st.size !== null && st.size !== undefined) paras[i].size = st.size;
      if (st.color !== null && st.color !== undefined) paras[i].color = st.color;
      if (st.font !== null && st.font !== undefined) paras[i].font = st.font;
    }
  };

  let n = 0;
  const idxOf = {};
  if (p.bg) {
    slide.images.push(K.Image({ file: Path(p.bg) }));
    idxOf['bg'] = { type: 'image', index: slide.images.length };
    n++;
  }

  for (const el of p.elements) {
    const st = el.style || {};
    if (el.type === 'text') {
      slide.textItems.push(K.TextItem({ objectText: el.text }));
      styleParas(slide.textItems[slide.textItems.length - 1], st);
    } else if (el.type === 'shape') {
      slide.shapes.push(K.Shape({ objectText: el.text }));
      styleParas(slide.shapes[slide.shapes.length - 1], st);
    } else if (['image', 'card', 'chart', 'diagram'].indexOf(el.type) >= 0) {
      slide.images.push(K.Image({ file: Path(el.path) }));
    } else if (el.type === 'table') {
      const rows = el.data.length;
      const cols = Math.max.apply(null, el.data.map(r => r.length));
      slide.tables.push(K.Table({ rowCount: rows, columnCount: cols }));
      const t = slide.tables[slide.tables.length - 1];
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < el.data[r].length; c++) {
          t.cells[r * cols + c].value = String(el.data[r][c]);
        }
      }
    }
    const coll = el.type === 'text' ? slide.textItems : el.type === 'shape' ? slide.shapes
               : el.type === 'image' ? slide.images : slide.tables;
    idxOf[el.id] = { type: el.type, index: coll.length };
    n++;
  }
  return JSON.stringify({ created: n, idx: idxOf });
}
"""


# ────────────────────────── 几何 + 校验（AppleScript） ──────────────────────────
def _prefix(text: str, n: int = 18) -> str:
    head = text.split("\n")[0][:n]
    return head or text[:n]


def _keys(elements):
    """为 text/shape 生成同类型内唯一的 (前缀, 第几个命中)。"""
    keys, seen = {}, {}
    for el in elements:
        if el["type"] not in ("text", "shape") or not el["text"]:
            continue
        base = _prefix(el["text"])
        seen[(el["type"], base)] = seen.get((el["type"], base), 0) + 1
        keys[el["id"]] = (base, seen[(el["type"], base)])
    return keys


def _match_block(kind: str, var: str, base: str, kth: int) -> str:
    q = esc_text(base)
    return (
        f"        set idx to 0\n"
        f"        set seen to 0\n"
        f"        repeat with i from 1 to (count of {var})\n"
        f"          if (item i of {var}) begins with {q} then\n"
        f"            set seen to seen + 1\n"
        f"            if seen = {kth} then\n"
        f"              set idx to i\n"
        f"              exit repeat\n"
        f"            end if\n"
        f"          end if\n"
        f"        end repeat\n"
    )


_SEP = "\x1f"   # ASCII 31 单元分隔符（与 AppleScript 侧一致）


def _list_elements(doc: str, slide: int) -> dict:
    """一次取回三类元素的文本/文件名列表（用分隔符拼接，避免逐项读）。"""
    script = (
        'tell application "Keynote"\n'
        f'  tell document {esc_text(doc)}\n'
        f'    set s to slide {slide} of it\n'
        '    set txts to (object text of text items of s) as list\n'
        '    set shps to (object text of shapes of s) as list\n'
        '    set imgs to (file name of images of s) as list\n'
        '    set AppleScript\'s text item delimiters to (ASCII character 31)\n'
        '    set r to (txts as text) & "##" & (shps as text) & "##" & (imgs as text)\n'
        '    set AppleScript\'s text item delimiters to ""\n'
        '    return r\n'
        '  end tell\n'
        'end tell')
    raw = applescript(script) or ""
    parts = raw.split("##")
    while len(parts) < 3:
        parts.append("")
    return {"text": parts[0].split(_SEP) if parts[0] else [],
            "shape": parts[1].split(_SEP) if parts[1] else [],
            "image": parts[2].split(_SEP) if parts[2] else []}


def _locate(lists: dict, plan, keys) -> dict:
    """在 Python 侧把每个元素映射到 (集合, 1-based 下标)。"""
    used, out = {}, {}
    for item in plan:
        eid, kind = item["id"], item["type"]
        pool = lists.get("image" if kind in ("card", "chart", "diagram") else kind, [])
        if kind == "text" or (kind == "shape" and item.get("text")):
            base, kth = keys.get(eid, ("", 1))
            seen = 0
            for i, content in enumerate(pool, start=1):
                if used.get((kind, i)):
                    continue
                if content == item["text"] or (base and content.startswith(base)):
                    seen += 1
                    if seen == kth:
                        out[eid] = (kind, i)
                        used[(kind, i)] = eid
                        break
        elif kind in ("image", "card", "chart", "diagram"):
            base = os.path.basename(item["path"])
            for i, name in enumerate(pool, start=1):
                if used.get((kind, i)):
                    continue
                if name and (name == base or base in name):
                    out[eid] = ("image", i)
                    used[("image", i)] = eid
                    break
        else:
            i = item["ordinal"]
            out[eid] = (kind, i)
            used[(kind, i)] = eid

    # 兜底：内容匹配失败的（重复文本、空白差异），按同类型剩余位置顺序补上
    for item in plan:
        eid = item["id"]
        if eid in out:
            continue
        kind = item["type"]
        pool_kind = "image" if kind == "card" else kind
        for i in range(1, len(lists.get(pool_kind, [])) + 1):
            if used.get((pool_kind, i)):
                continue
            out[eid] = (pool_kind, i)
            used[(pool_kind, i)] = eid
            break
    return out


def _apply_geometry(doc: str, slide: int, plan, located: dict) -> dict:
    """按下标设几何 + 批量回读位置。"""
    coll = {"text": "text item", "shape": "shape", "image": "image",
            "table": "table", "card": "image", "chart": "image", "diagram": "image"}
    blocks = []
    for item in plan:
        hit = located.get(item["id"])
        if not hit:
            continue
        kind, idx = hit
        x, y, w, h = (int(round(v)) for v in item["box"])
        blocks.append(f"        set properties of {coll[kind]} {idx} of s to "
                      f"{{width:{w}, height:{h}, position:{{{x}, {y}}}}}")

    reads = []
    for kind, coll_name in (("text", "text item"), ("shape", "shape"),
                            ("image", "image"), ("table", "table")):
        reads += [f"        set ps to position of {coll_name}s of s",
                  "        repeat with i from 1 to (count of ps)",
                  "          set q to item i of ps",
                  f'          set out to out & "{kind}|" & i & "|" & (item 1 of q) & "|" & (item 2 of q) & linefeed',
                  "        end repeat"]

    script = (
        'tell application "Keynote"\n'
        f'  tell document {esc_text(doc)}\n'
        f'    set s to slide {slide} of it\n'
        + "\n".join(blocks) + "\n"
        '    set out to ""\n'
        + "\n".join(reads) + "\n"
        '    return out\n'
        '  end tell\n'
        'end tell')

    raw = applescript(script) or ""
    positions = {}
    for line in raw.splitlines():
        bits = line.strip().split("|")
        if len(bits) >= 4 and bits[1].isdigit():
            try:
                positions[(bits[0], int(bits[1]))] = (float(bits[2]), float(bits[3]))
            except ValueError:
                continue

    result = {}
    for item in plan:
        hit = located.get(item["id"])
        if hit and positions.get(hit):
            result[item["id"]] = positions[hit]
    return result


_AS_SLOTS = '''
        tell application "Keynote"
          tell document {doc}
            set s to slide {slide} of it
            set out to ""
            set ps to position of text items of s
            set ws to width of text items of s
            repeat with i from 1 to (count of ps)
              set q to item i of ps
              set out to out & i & "|" & (item 1 of q) & "|" & (item 2 of q) & "|" & (item i of ws) & linefeed
            end repeat
            return out
          end tell
        end tell
'''


def find_slots(doc: str, slide: int) -> dict:
    """找出母版占位符：宽度>0 的前两个，按 y 排序 → title / body。"""
    raw = applescript(_AS_SLOTS.format(doc=esc_text(doc), slide=slide)) or ""
    cands = []
    for line in raw.splitlines():
        bits = line.strip().split("|")
        if len(bits) == 4 and bits[0].isdigit():
            try:
                cands.append({"index": int(bits[0]), "x": float(bits[1]),
                              "y": float(bits[2]), "w": float(bits[3])})
            except ValueError:
                continue
    real, seen = [], set()
    for c in cands:
        if c["w"] <= 40:                     # 幽灵占位符（0 宽）
            continue
        key = (round(c["x"]), round(c["y"]), round(c["w"]))
        if key in seen:                      # 同一占位符会被枚举两次
            continue
        seen.add(key)
        real.append(c)
    real.sort(key=lambda c: c["y"])
    slots = {}
    if real:
        slots["title"] = real[0]
    if len(real) > 1:
        slots["body"] = real[1]
    return slots


def write_slot(doc: str, slide: int, index: int, text: str, box) -> None:
    x, y, w, h = (int(round(v)) for v in box)
    body = " & linefeed & ".join(esc_text(line) for line in text.split("\n"))
    applescript(f'''
        tell application "Keynote"
          tell document {esc_text(doc)}
            set tgt to text item {index} of slide {slide} of it
            set object text of tgt to ({body})
            set width of tgt to {w}
            set height of tgt to {h}
            set position of tgt to {{{x}, {y}}}
          end tell
        end tell''')


def clear_slide(deck, slide: int) -> int:
    before = deck.inspect(slide)["count"]
    lines = ['tell application "Keynote"',
             f'  tell document {esc_text(deck.doc)}',
             f'    tell slide {slide} of it']
    for plural, single in (("text items", "text item"), ("shapes", "shape"),
                           ("images", "image"), ("tables", "table"),
                           ("lines", "line"), ("movies", "movie")):
        lines += [f'      repeat with i from (count of {plural}) to 1 by -1',
                  '        try', f'          delete {single} i', '        end try',
                  '      end repeat']
    lines += ['    end tell', '  end tell', 'end tell']
    applescript("\n".join(lines))
    return before - deck.inspect(slide)["count"]


def apply_page(deck, slide: int, spec: dict, mode: str = "replace") -> dict:
    bg, elements = normalise(spec)
    if slide > deck.slide_count():
        raise SpecError(f"第 {slide} 页不存在（当前 {deck.slide_count()} 页）")

    slot_els = [el for el in elements if el.get("slot")]
    normal = [el for el in elements if not el.get("slot")]

    # 有 slot 时不能清空（占位符会被删掉），改为在现有页面上写；
    # 也不能插整页背景图 —— 占位符比新插入的图更靠后，会被盖住，背景交给母版
    if slot_els:
        if mode == "replace":
            mode = "append"
        bg = None

    payload = {"doc": deck.doc, "slide": slide, "clear": mode == "replace",
               "bg": bg["path"] if bg else None, "elements": []}
    for el in normal:
        st = el.get("style") or {}
        color = st.get("color")
        payload["elements"].append({
            "id": el["id"], "type": el["type"], "text": el["text"],
            "path": el.get("path"), "data": el.get("data"),
            "style": {"size": st.get("size"),
                      "color": _rgb(color) if color else None,
                      "font": st.get("font")},
        })

    built = jxa(_JXA_CREATE, payload) or {}

    if slot_els:
        slots = find_slots(deck.doc, slide)
        for el in slot_els:
            slot = slots.get(el.get("slot"))
            if not slot:
                raise SpecError(f"元素 {el['id']}：本页没有 {el['slot']} 占位符（请用带该版式的母版建页）")
            write_slot(deck.doc, slide, slot["index"], el["text"], el["box"])

    keys = _keys(normal)
    plan, ordinals = [], {"shape": 0, "table": 0}
    if bg:
        plan.append({"id": "bg", "type": "image", "path": bg["path"], "box": [0, 0, 1920, 1080]})
    for el in normal:
        ordinals[el["type"]] = ordinals.get(el["type"], 0) + 1
        plan.append({"id": el["id"], "type": el["type"], "path": el.get("path"),
                     "text": el["text"], "ordinal": ordinals[el["type"]], "box": el["box"]})

    lists = _list_elements(deck.doc, slide)
    located = _locate(lists, plan, keys)
    got = _apply_geometry(deck.doc, slide, plan, located)

    problems = []
    for el in normal:
        pos = got.get(el["id"])
        if pos is None:
            problems.append(f"元素 {el['id']} 未落位")
            continue
        x, y = el["box"][0], el["box"][1]
        if abs(pos[0] - x) > TOLERANCE or abs(pos[1] - y) > TOLERANCE:
            problems.append(f"元素 {el['id']} 位置偏差 ({pos[0]:.0f},{pos[1]:.0f}) vs ({x:.0f},{y:.0f})")

    if problems:
        if mode == "replace":
            clear_slide(deck, slide)
        raise VerifyError("；".join(problems))

    return {"slide": slide, "elements": len(normal) + len(slot_els) + (1 if bg else 0),
            "background": bool(bg), "revision": _fingerprint(got), "verified": True}


def _fingerprint(got: dict) -> str:
    payload = "|".join(f"{k}:{round(v[0])}:{round(v[1])}" for k, v in sorted(got.items()))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


from .deck import _rgb  # noqa: E402  （避免循环导入，放在末尾）


# ────────────────────────── 反向：页面 → spec ──────────────────────────
_JXA_EXTRACT = r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const d = K.documents.byName(p.doc);
  const out = [];
  for (let i = 0; i < d.slides.length; i++) {
    const s = d.slides[i];
    const els = [];
    for (let j = 0; j < s.textItems.length; j++) {
      const ti = s.textItems[j];
      let text = ''; try { text = String(ti.objectText()); } catch (e) {}
      if (!text) continue;
      const q = ti.position();
      const st = { size: null, font: null, color: null };
      try {
        const para = ti.objectText.paragraphs[0];
        st.size = Number(para.size());
        st.font = String(para.font());
        st.color = String(para.color());
      } catch (e) {}
      els.push({ type: 'text', text: text,
                 box: [q.x, q.y, ti.width(), ti.height()], style: st });
    }
    out.push({ n: i + 1, elements: els,
               images: s.images.length, tables: s.tables.length });
  }
  return JSON.stringify(out);
}
"""


def _applescript_color_to_hex(value: str | None) -> str | None:
    """'RGB 0.16 0.14 0.12' → '#29241F'"""
    try:
        parts = (value or "").split()
        if parts and parts[0].lower() == "rgb" and len(parts) >= 4:
            r, g, b = (max(0, min(255, int(round(float(v) * 255)))) for v in parts[1:4])
            return f"#{r:02X}{g:02X}{b:02X}"
    except (TypeError, ValueError):
        pass
    return None


def extract_page(deck, slide: int, *, with_background: str | None = None) -> dict:
    """把一页读成 page spec（text / table / image 计数一并返回）。

    注意：只能还原「元素」，不能还原主题装饰（纸纹、发丝线、项目符号），
    这些是版式自带的，不在元素模型里。
    """
    raw = jxa(_JXA_EXTRACT, {"doc": deck.doc})
    pages = raw if isinstance(raw, list) else raw.get("value", [])
    page = next((p for p in pages if p["n"] == slide), None)
    if page is None:
        raise SpecError(f"第 {slide} 页不存在")

    elements = []
    for i, el in enumerate(page["elements"]):
        style = {"size": el["style"].get("size"), "font": el["style"].get("font")}
        hexc = _applescript_color_to_hex(el["style"].get("color"))
        if hexc:
            style["color"] = hexc
        elements.append({"id": f"t{i}", "type": "text", "text": el["text"],
                         "box": [round(v, 1) for v in el["box"]], "style": style})

    spec = {"elements": elements}
    if with_background:
        spec["background"] = {"type": "solid", "color": with_background}
    return {"slide": slide, "spec": spec,
            "images": page["images"], "tables": page["tables"]}
