"""deck：Keynote 文档的高层操作，补齐 iwork-mcp 缺失的能力。"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .runner import applescript, esc_text, jxa, KeynoteError

JXA_CREATE = r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const d = K.documents.byName(p.doc);
  const s = d.slides[p.slide - 1];
  const out = { created: true, kind: p.kind };

  if (p.kind === 'text') {
    const ti = K.TextItem({ objectText: p.text || '' });
    s.textItems.push(ti);
    out.index = s.textItems.length - 1;
  } else if (p.kind === 'shape') {
    const sh = K.Shape({ objectText: p.text || '' });
    s.shapes.push(sh);
    out.index = s.shapes.length - 1;
  } else if (p.kind === 'image') {
    const img = K.Image({ file: Path(p.path) });
    s.images.push(img);
    out.index = s.images.length - 1;
    out.count = s.images.length;   // push 追加到末尾，AppleScript 索引 = count
  } else {
    throw new Error('unknown kind: ' + p.kind);
  }
  return JSON.stringify(out);
}
"""

JXA_TABLE = r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const d = K.documents.byName(p.doc);
  const s = d.slides[p.slide - 1];
  if (!p.rows || !p.cols) throw new Error('rows/cols required');
  const t = K.Table({ rowCount: p.rows, columnCount: p.cols });
  s.tables.push(t);
  const out = { created: true, rows: p.rows, cols: p.cols, cells: 0 };
  if (p.data) {
    const tbl = s.tables[0];
    let n = 0;
    for (let r = 0; r < p.data.length && r < p.rows; r++) {
      for (let c = 0; c < p.data[r].length && c < p.cols; c++) {
        tbl.cells[r * p.cols + c].value = String(p.data[r][c]);
        n++;
      }
    }
    out.cells = n;
  }
  return JSON.stringify(out);
}
"""

JXA_STYLE = r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const d = K.documents.byName(p.doc);
  const s = d.slides[p.slide - 1];
  let item = null;
  const pool = (p.kind === 'shape') ? s.shapes : s.textItems;
  for (let i = 0; i < pool.length; i++) {
    try { if (String(pool[i].objectText()) === p.marker) { item = pool[i]; break; } } catch (e) {}
  }
  if (!item) throw new Error('未找到元素: ' + p.marker);
  const out = {};

  if (p.size !== undefined || p.color !== undefined || p.font !== undefined) {
    const paras = item.objectText.paragraphs;
    for (let i = 0; i < paras.length; i++) {
      if (p.size !== undefined) paras[i].size = p.size;
      if (p.color !== undefined) paras[i].color = p.color;
      if (p.font !== undefined) paras[i].font = p.font;
    }
    out.styled = paras.length;
  }
  if (p.spacing !== undefined) {
    try {
      const paras = item.objectText.paragraphs;
      for (let i = 0; i < paras.length; i++) paras[i].lineSpacing = p.spacing;
      out.spacing = true;
    } catch (e) { out.spacing = String(e.message); }
  }
  return JSON.stringify(out);
}
"""

JXA_INSPECT = r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const d = K.documents.byName(p.doc);
  const s = d.slides[p.slide - 1];
  const describe = (it, type, i) => {
    const pos = it.position();
    let text = '';
    try { text = it.objectText(); } catch (e) { text = ''; }
    return { type: type, index: i, x: pos.x, y: pos.y, w: it.width(), h: it.height(), text: String(text).slice(0, 60) };
  };
  const items = [];
  const pushIfReal = (it, type, i) => {
    const rec = describe(it, type, i);
    if (type === 'text' && !rec.text && rec.w === 0 && rec.h === 0) return; // 空白版式的幽灵占位符
    items.push(rec);
  };
  for (let i = 0; i < s.textItems.length; i++) pushIfReal(s.textItems[i], 'text', i);
  for (let i = 0; i < s.shapes.length; i++) items.push(describe(s.shapes[i], 'shape', i));
  for (let i = 0; i < s.images.length; i++) items.push(describe(s.images[i], 'image', i));
  const tables = s.tables.length;
  for (let i = 0; i < tables; i++) {
    const t = s.tables[i];
    const pos = t.position();
    items.push({ type: 'table', index: i, x: pos.x, y: pos.y, w: t.width(), h: t.height(), text: '' });
  }
  return JSON.stringify({ slide: p.slide, count: items.length, items: items, tables: tables });
}
"""


def _rgb(hex_color: str) -> list[int]:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    # Keynote 的颜色分量是 0–65535
    return [r * 257, g * 257, b * 257]


@dataclass
class Deck:
    """一个打开的 Keynote 文档。"""

    name: str
    doc: str = ""

    def __post_init__(self) -> None:
        self.doc = self.name

    # ── 文档 ───────────────────────────────────────────────
    @classmethod
    def create(cls, theme: str = "白色", width: int = 1920, height: int = 1080) -> "Deck":
        out = applescript(f'''
            tell application "Keynote"
              set d to make new document with properties {{document theme:theme {esc_text(theme)}}}
              set width of d to {width}
              set height of d to {height}
              return name of d
            end tell''')
        return cls(name=out.strip())

    def slide_count(self) -> int:
        return int(applescript(
            f'tell application "Keynote" to get count of slides of document {esc_text(self.doc)}'))

    # ── 页面 ───────────────────────────────────────────────
    def add_slide(self, master: str = "空白") -> int:
        """在末尾追加一页。用 AppleScript 的 at end，避免 iwork-mcp 覆盖已有页的 bug。"""
        n = self.slide_count() + 1
        applescript(f'''
            tell application "Keynote"
              tell document {esc_text(self.doc)}
                make new slide at end of it with properties {{base slide:master slide {esc_text(master)} of it}}
              end tell
              return count of slides of document {esc_text(self.doc)}
            end tell''')
        return n

    # ── 元素创建 ────────────────────────────────────────────
    def _create(self, kind: str, slide: int, **kw) -> dict:
        payload = {"doc": self.doc, "slide": slide, "kind": kind, **kw}
        return jxa(JXA_CREATE, payload)

    def add_text(self, slide: int, text: str, x: float, y: float, w: float, h: float,
                 size: float | None = None, color: str | None = None,
                 font: str | None = None) -> dict:
        """真正的文本框（不是占位符），支持精确坐标与排版。"""
        marker = text
        self._create("text", slide, text=marker)
        self._geometry("text item", slide, marker, x, y, w, h)
        if size or color or font:
            self._style("text", slide, marker, size=size, color=color, font=font)
        return {"index": 0, "kind": "text"}

    def add_shape(self, slide: int, text: str, x: float, y: float, w: float, h: float,
                  size: float | None = None, color: str | None = None) -> dict:
        marker = text
        self._create("shape", slide, text=marker)
        self._geometry("shape", slide, marker, x, y, w, h)
        if size or color:
            self._style("shape", slide, marker, size=size, color=color)
        return {"index": 0, "kind": "shape"}

    def add_image(self, slide: int, path: str, x: float = 0, y: float = 0,
                  w: float | None = None, h: float | None = None) -> dict:
        if not os.path.exists(path):
            raise FileNotFoundError(f"图片不存在：{path}")
        ap = os.path.abspath(path)
        info = self._create("image", slide, path=ap)
        # image 的 file name 属性不可靠（多图同名），且 push 追加到末尾，
        # 因此新图 = AppleScript 的第 count 个 image。
        self._geom_index("image", int(info.get("count", 1)), slide, x, y, w, h)
        return {"index": 0, "kind": "image"}

    def add_table(self, slide: int, data: list[list], x: float, y: float,
                  w: float, h: float) -> dict:
        """原生表格：建表 + 填数据走 JXA，几何走 AppleScript。"""
        rows = len(data)
        cols = max(len(r) for r in data) if data else 1
        r = jxa(JXA_TABLE, {"doc": self.doc, "slide": slide, "rows": rows,
                            "cols": cols, "data": data})
        applescript(f'''
            tell application "Keynote"
              tell document {esc_text(self.doc)}
                set s to slide {slide} of it
                set t to table 1 of s
                set width of t to {int(w)}
                set height of t to {int(h)}
                set position of t to {{{int(x)}, {int(y)}}}
              end tell
            end tell''')
        return {"rows": rows, "cols": cols, "cells": r.get("cells", 0)}

    def set_background(self, slide: int, path: str, w: float = 1920, h: float = 1080) -> dict:
        """整页背景图。必须在该页还没有其他元素（或在最早期）时调用，靠插入顺序保证在最底层。"""
        return self.add_image(slide, path, 0, 0, w, h)

    # ── 几何与样式 ──────────────────────────────────────────
    def _geometry(self, cls: str, slide: int, marker: str,
                  x: float, y: float, w: float | None, h: float | None) -> None:
        """按文本/文件名定位元素再设置几何，避免集合顺序漂移。

        JXA 与 AppleScript 对集合的枚举顺序不一致，且新建元素会插到最前，
        所以这里不依赖索引，改为按唯一标记匹配。
        """
        size_lines = []
        if w is not None:
            size_lines.append(f"set width of target to {int(w)}")
        if h is not None:
            size_lines.append(f"set height of target to {int(h)}")
        size_lines.append(f"set position of target to {{{int(x)}, {int(y)}}}")
        body = "\n      ".join(size_lines)

        key = "file name" if cls == "image" else "object text"
        applescript(f'''
            tell application "Keynote"
              tell document {esc_text(self.doc)}
                set s to slide {slide} of it
                set target to missing value
                repeat with itm in {cls}s of s
                  try
                    set nm to ({key} of itm as text)
                    if nm is {esc_text(marker)} or nm contains {esc_text(marker)} then
                      set target to itm
                      exit repeat
                    end if
                  end try
                end repeat
                if target is missing value then error "未找到目标元素：" & {esc_text(marker)}
                {body}
              end tell
            end tell''')

    def _geom_index(self, cls: str, one_based: int, slide: int,
                    x: float, y: float, w: float | None, h: float | None) -> None:
        lines = []
        if w is not None:
            lines.append(f"set width of {cls} {one_based} of s to {int(w)}")
        if h is not None:
            lines.append(f"set height of {cls} {one_based} of s to {int(h)}")
        lines.append(f"set position of {cls} {one_based} of s to {{{int(x)}, {int(y)}}}")
        body = "\n      ".join(lines)
        applescript(f'''
            tell application "Keynote"
              tell document {esc_text(self.doc)}
                set s to slide {slide} of it
                {body}
              end tell
            end tell''')

    def _style(self, kind: str, slide: int, marker: str,
               size: float | None = None, color: str | None = None,
               font: str | None = None) -> dict:
        payload = {"doc": self.doc, "slide": slide, "kind": kind, "marker": marker}
        if size is not None:
            payload["size"] = size
        if color:
            payload["color"] = _rgb(color)
        if font:
            payload["font"] = font
        return jxa(JXA_STYLE, payload)

    # ── 校验 ────────────────────────────────────────────────
    def inspect(self, slide: int) -> dict:
        return jxa(JXA_INSPECT, {"doc": self.doc, "slide": slide})

    def verify(self, slide: int, expect: int | None = None) -> dict:
        """读回页面元素，用于发现“静默失败”。"""
        info = self.inspect(slide)
        if expect is not None and info["count"] != expect:
            raise KeynoteError(
                f"校验失败：第 {slide} 页预期 {expect} 个元素，实际 {info['count']} 个")
        return info

    def close(self, save: bool = False) -> None:
        """关闭文档（默认不保存）。"""
        jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  try { K.documents.byName(p.doc).close({ saving: p.save ? 'yes' : 'no' }); } catch (e) {}
  return JSON.stringify({ closed: true });
}
""", {"doc": self.doc, "save": save})

    # ── 导出 ────────────────────────────────────────────────
    def export(self, path: str, fmt: str = "images") -> str:
        """fmt: images | PowerPoint | PDF。用 JXA 导出（AppleScript 路径在本版会报 -6）。"""
        target = os.path.abspath(path)
        mapping = {"images": "slide images", "pptx": "PowerPoint",
                   "powerpoint": "PowerPoint", "pdf": "PDF"}
        as_type = mapping.get(fmt.lower(), fmt)
        jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const d = K.documents.byName(p.doc);
  d.export({ to: Path(p.to), as: p.asType });
  return JSON.stringify({ exported: true, to: p.to });
}
""", {"doc": self.doc, "to": target, "asType": as_type})
        return target

    def save(self, path: str) -> str:
        target = os.path.abspath(path)
        jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  const d = K.documents.byName(p.doc);
  d.save({ in: Path(p.to) });
  return JSON.stringify({ saved: true, to: p.to });
}
""", {"doc": self.doc, "to": target})
        return target
