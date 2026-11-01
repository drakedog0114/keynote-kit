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
        if kind not in ("text", "shape", "image", "table"):
            raise SpecError(f"第 {i} 个元素类型不支持：{kind}")
        eid = str(raw.get("id") or f"{kind}{i}")
        if eid in ids:
            raise SpecError(f"元素 id 重复：{eid}")
        ids.add(eid)
        item = {"id": eid, "type": kind, "box": [float(v) for v in box],
                "text": str(raw.get("text", "")), "style": raw.get("style") or {}}
        if kind == "image":
            path = raw.get("path", "")
            if not path or not os.path.exists(path):
                raise SpecError(f"图片不存在：{path}")
            item["path"] = os.path.abspath(path)
        if kind == "table":
            data = raw.get("data") or []
            if not data:
                raise SpecError(f"表格 {eid} 缺少 data")
            item["data"] = data
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
    } else if (el.type === 'image') {
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
        pool = lists.get(kind, [])
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
        elif kind == "image":
            base = os.path.basename(item["path"])
            for i, name in enumerate(pool, start=1):
                if used.get((kind, i)):
                    continue
                if name and (name == base or base in name):
                    out[eid] = (kind, i)
                    used[(kind, i)] = eid
                    break
        else:
            i = item["ordinal"]
            out[eid] = (kind, i)
            used[(kind, i)] = eid
    return out


def _apply_geometry(doc: str, slide: int, plan, located: dict) -> dict:
    """按下标设几何 + 批量回读位置。"""
    coll = {"text": "text item", "shape": "shape", "image": "image", "table": "table"}
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

    payload = {"doc": deck.doc, "slide": slide, "clear": mode == "replace",
               "bg": bg["path"] if bg else None, "elements": []}
    for el in elements:
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

    keys = _keys(elements)
    plan, ordinals = [], {"shape": 0, "table": 0}
    if bg:
        plan.append({"id": "bg", "type": "image", "path": bg["path"], "box": [0, 0, 1920, 1080]})
    for el in elements:
        ordinals[el["type"]] = ordinals.get(el["type"], 0) + 1
        plan.append({"id": el["id"], "type": el["type"], "path": el.get("path"),
                     "text": el["text"], "ordinal": ordinals[el["type"]], "box": el["box"]})

    lists = _list_elements(deck.doc, slide)
    located = _locate(lists, plan, keys)
    got = _apply_geometry(deck.doc, slide, plan, located)

    problems = []
    for el in elements:
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

    return {"slide": slide, "elements": len(elements) + (1 if bg else 0),
            "background": bool(bg), "revision": _fingerprint(got), "verified": True}


def _fingerprint(got: dict) -> str:
    payload = "|".join(f"{k}:{round(v[0])}:{round(v[1])}" for k, v in sorted(got.items()))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


from .deck import _rgb  # noqa: E402  （避免循环导入，放在末尾）
