"""扩展操作：把 iwork-mcp 里有、Deck 还没包的能力补齐。

这些函数接收一个已打开的 `Deck`，操作它的文档。之所以单独成文件，是为了让
`deck.py` 只保留“创建内容”的主线，查询 / 排版 / 表格读写这类操作集中在这里。
"""

from __future__ import annotations

from typing import Sequence

from .deck import Deck, _rgb
from .runner import applescript, esc_text, jxa, KeynoteError

# ─────────────────────────── 文档级 ───────────────────────────
def list_documents() -> list[dict]:
    return jxa(r"""
function run() {
  const K = Application('Keynote');
  const out = [];
  for (const d of K.documents()) {
    let p = null;
    try { p = String(d.file()); } catch (e) {}
    out.push({ name: d.name(), slides: d.slides.length, path: p });
  }
  return JSON.stringify(out);
}
""").get("value", [])


def open_document(path: str) -> dict:
    out = jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const d = K.open(Path(p.path));
  return JSON.stringify({ name: d.name(), slides: d.slides.length });
}
""", {"path": path})
    return out


def list_themes() -> list[str]:
    return jxa(r"""
function run() {
  const K = Application('Keynote');
  try { return JSON.stringify(K.themes.name()); } catch (e) { return JSON.stringify([]); }
}
""").get("value", [])


def set_theme(deck: Deck, theme: str) -> dict:
    applescript(f'''
        tell application "Keynote"
          tell document {esc_text(deck.doc)}
            set document theme of it to theme {esc_text(theme)}
          end tell
        end tell''')
    return {"theme": theme}


def list_layouts(deck: Deck) -> list[str]:
    return jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const d = Application('Keynote').documents.byName(p.doc);
  return JSON.stringify(d.masterSlides.name());
}
""", {"doc": deck.doc}).get("value", [])


def set_layout(deck: Deck, slide: int, layout: str) -> dict:
    applescript(f'''
        tell application "Keynote"
          tell document {esc_text(deck.doc)}
            set base slide of slide {slide} of it to master slide {esc_text(layout)} of it
          end tell
        end tell''')
    return {"slide": slide, "layout": layout}


# ─────────────────────────── 页面级 ───────────────────────────
def list_slides(deck: Deck) -> list[dict]:
    return jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const d = Application('Keynote').documents.byName(p.doc);
  const out = [];
  for (let i = 0; i < d.slides.length; i++) {
    const s = d.slides[i];
    let title = '';
    try { title = String(s.defaultTitleItem.objectText()); } catch (e) {}
    let skipped = false;
    try { skipped = s.skipped(); } catch (e) {}
    out.push({ slide: i + 1, title: title, skipped: skipped });
  }
  return JSON.stringify(out);
}
""", {"doc": deck.doc}).get("value", [])


def get_slide_content(deck: Deck, slide: int) -> dict:
    return jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const d = Application('Keynote').documents.byName(p.doc);
  const s = d.slides[p.slide - 1];
  const read = (fn) => { try { return String(fn()); } catch (e) { return ''; } };
  return JSON.stringify({
    slide: p.slide,
    title: read(() => s.defaultTitleItem.objectText()),
    body: read(() => s.defaultBodyItem.objectText()),
    notes: read(() => s.presenterNotes()),
    items: s.textItems.length + s.shapes.length + s.images.length + s.tables.length
  });
}
""", {"doc": deck.doc, "slide": slide})


def set_title(deck: Deck, slide: int, title: str) -> dict:
    applescript(f'''
        tell application "Keynote"
          tell document {esc_text(deck.doc)}
            set object text of default title item of slide {slide} of it to {esc_text(title)}
          end tell
        end tell''')
    return {"slide": slide, "title": title}


def set_body(deck: Deck, slide: int, body: str) -> dict:
    applescript(f'''
        tell application "Keynote"
          tell document {esc_text(deck.doc)}
            set object text of default body item of slide {slide} of it to {esc_text(body)}
          end tell
        end tell''')
    return {"slide": slide}


def move_slide(deck: Deck, source: int, target: int) -> dict:
    """移动页面：复制到目标位置后删除原页（Keynote 没有原生 move）。"""
    if source == target:
        return {"slide": source, "target": target}
    applescript(f'''
        tell application "Keynote"
          tell document {esc_text(deck.doc)}
            duplicate slide {source} of it to after slide {target} of it
          end tell
        end tell''')
    deck.remove_slide(source if source < target else source)
    return {"moved": True, "from": source, "to": target, "total": deck.slide_count()}


def skip_slide(deck: Deck, slide: int, skipped: bool = True) -> dict:
    applescript(f'''
        tell application "Keynote"
          tell document {esc_text(deck.doc)}
            set skipped of slide {slide} of it to {str(skipped).lower()}
          end tell
        end tell''')
    return {"slide": slide, "skipped": skipped}


# ─────────────────────────── 排版级 ───────────────────────────
_ITEMS = {"shape": "shapes", "image": "images", "text": "textItems"}


def position_item(deck: Deck, slide: int, kind: str, index: int,
                  x: float, y: float, w: float | None = None, h: float | None = None) -> dict:
    pool = _ITEMS.get(kind)
    if not pool:
        raise KeynoteError(f"不支持的元素类型：{kind}（可选 shape / image / text）")
    return jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const s = K.documents.byName(p.doc).slides[p.slide - 1];
  const item = s[p.pool][p.index];
  if (!item) throw new Error('index out of range');
  if (p.w !== null) item.width = p.w;
  if (p.h !== null) item.height = p.h;
  item.position = [p.x, p.y];
  const pos = item.position();
  return JSON.stringify({ x: pos.x, y: pos.y, w: item.width(), h: item.height() });
}
""", {"doc": deck.doc, "slide": slide, "pool": pool, "index": index,
      "x": x, "y": y, "w": w, "h": h})


def align_items(deck: Deck, slide: int, kind: str, indexes: Sequence[int],
                alignment: str = "left") -> dict:
    pool = _ITEMS.get(kind)
    if not pool:
        raise KeynoteError(f"不支持的元素类型：{kind}")
    return jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const s = K.documents.byName(p.doc).slides[p.slide - 1];
  const items = p.indexes.map(i => s[p.pool][i]).filter(Boolean);
  if (!items.length) throw new Error('no items');
  const boxes = items.map(it => { const q = it.position(); return { it: it, x: q.x, y: q.y, w: it.width(), h: it.height() }; });
  const ref = boxes[0];
  for (const b of boxes) {
    if (p.alignment === 'left') b.it.position = [ref.x, b.y];
    else if (p.alignment === 'right') b.it.position = [ref.x + ref.w - b.w, b.y];
    else if (p.alignment === 'top') b.it.position = [b.x, ref.y];
    else if (p.alignment === 'bottom') b.it.position = [b.x, ref.y + ref.h - b.h];
    else if (p.alignment === 'center') b.it.position = [ref.x + (ref.w - b.w) / 2, b.y];
    else if (p.alignment === 'middle') b.it.position = [b.x, ref.y + (ref.h - b.h) / 2];
  }
  return JSON.stringify({ aligned: true, count: boxes.length, alignment: p.alignment });
}
""", {"doc": deck.doc, "slide": slide, "pool": pool,
      "indexes": list(indexes), "alignment": alignment})


def distribute_items(deck: Deck, slide: int, kind: str, indexes: Sequence[int],
                     direction: str = "horizontal") -> dict:
    pool = _ITEMS.get(kind)
    if not pool:
        raise KeynoteError(f"不支持的元素类型：{kind}")
    return jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const s = K.documents.byName(p.doc).slides[p.slide - 1];
  const items = p.indexes.map(i => s[p.pool][i]).filter(Boolean);
  if (items.length < 2) throw new Error('need at least 2 items');
  const boxes = items.map(it => { const q = it.position(); return { it: it, x: q.x, y: q.y, w: it.width(), h: it.height() }; });
  const horiz = p.direction === 'horizontal';
  boxes.sort((a, b) => horiz ? a.x - b.x : a.y - b.y);
  const first = boxes[0], last = boxes[boxes.length - 1];
  const span = horiz ? (last.x - first.x) : (last.y - first.y);
  const step = span / (boxes.length - 1);
  boxes.forEach((b, i) => {
    if (horiz) b.it.position = [first.x + step * i, b.y];
    else b.it.position = [b.x, first.y + step * i];
  });
  return JSON.stringify({ distributed: true, count: boxes.length, direction: p.direction });
}
""", {"doc": deck.doc, "slide": slide, "pool": pool,
      "indexes": list(indexes), "direction": direction})


def get_shape_info(deck: Deck, slide: int, index: int) -> dict:
    return jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const s = K.documents.byName(p.doc).slides[p.slide - 1];
  const sh = s.shapes[p.index];
  if (!sh) throw new Error('index out of range');
  const q = sh.position();
  const out = { x: q.x, y: q.y, w: sh.width(), h: sh.height() };
  try { out.text = String(sh.objectText()); } catch (e) { out.text = ''; }
  try { out.opacity = sh.opacity(); } catch (e) {}
  try {
    const para = sh.objectText.paragraphs[0];
    out.font = String(para.font()); out.size = para.size();
  } catch (e) {}
  return JSON.stringify(out);
}
""", {"doc": deck.doc, "slide": slide, "index": index})


def format_shape(deck: Deck, slide: int, index: int, size: float | None = None,
                 color: str | None = None, font: str | None = None,
                 alignment: str | None = None) -> dict:
    return jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const s = K.documents.byName(p.doc).slides[p.slide - 1];
  const sh = s.shapes[p.index];
  if (!sh) throw new Error('index out of range');
  const paras = sh.objectText.paragraphs;
  for (let i = 0; i < paras.length; i++) {
    if (p.size !== null) paras[i].size = p.size;
    if (p.font !== null) paras[i].font = p.font;
    if (p.color !== null) paras[i].color = p.color;
  }
  let aligned = null;
  if (p.alignment !== null) {
    try { sh.objectText.alignment = p.alignment; aligned = p.alignment; } catch (e) { aligned = 'unsupported'; }
  }
  return JSON.stringify({ formatted: true, paragraphs: paras.length, alignment: aligned });
}
""", {"doc": deck.doc, "slide": slide, "index": index,
      "size": size, "font": font,
      "color": _rgb(color) if color else None, "alignment": alignment})


# ─────────────────────────── 表格级 ───────────────────────────
def read_table(deck: Deck, slide: int, index: int = 0) -> dict:
    return jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const s = K.documents.byName(p.doc).slides[p.slide - 1];
  const t = s.tables[p.index];
  if (!t) throw new Error('table not found');
  const rows = t.rowCount(), cols = t.columnCount();
  const data = [];
  for (let r = 0; r < rows; r++) {
    const row = [];
    for (let c = 0; c < cols; c++) row.push(String(t.cells[r * cols + c].value()));
    data.push(row);
  }
  return JSON.stringify({ rows: rows, columns: cols, data: data });
}
""", {"doc": deck.doc, "slide": slide, "index": index})


def write_table(deck: Deck, slide: int, data: list[list], index: int = 0) -> dict:
    return jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const s = K.documents.byName(p.doc).slides[p.slide - 1];
  const t = s.tables[p.index];
  if (!t) throw new Error('table not found');
  const cols = t.columnCount();
  let n = 0;
  for (let r = 0; r < p.data.length; r++) {
    for (let c = 0; c < p.data[r].length; c++) {
      t.cells[r * cols + c].value = String(p.data[r][c]);
      n++;
    }
  }
  return JSON.stringify({ written: n });
}
""", {"doc": deck.doc, "slide": slide, "index": index, "data": data})


# ─────────────────────────── 放映 ───────────────────────────
def start_slideshow(deck: Deck) -> dict:
    applescript(f'tell application "Keynote" to start document {esc_text(deck.doc)}')
    return {"playing": True}


def stop_slideshow(deck: Deck) -> dict:
    applescript('tell application "Keynote" to stop')
    return {"playing": False}
