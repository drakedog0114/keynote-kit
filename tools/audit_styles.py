#!/usr/bin/env python3
"""审计 .key 稿里的文本样式，定位「样式落错对象」之类的历史问题。

    python tools/audit_styles.py 稿名.key [稿名2.key ...]
    python tools/audit_styles.py --doc "已打开的文稿名"

检查项：

1. **多段同号**：一个文本框里有多段，但所有段落字号一样
   —— 这是样式落错对象的典型症状（不同段本来该有不同层级）。
2. **零尺寸元素**：宽或高为 0 的文本框（多半是母版占位符残留）。
3. **超框风险**：按字号和框宽估算，文字高度明显超过框高。
4. **空文本**：有框但没有内容的文本框。

退出码：发现问题返回 1，方便接进 CI。
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keynote_kit.runner import jxa  # noqa: E402

READ = r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  let doc = null; const ds = K.documents();
  for (let i = 0; i < ds.length; i++) if (String(ds[i].name()) === p.doc) doc = ds[i];
  if (!doc) return JSON.stringify({ error: 'document not open: ' + p.doc });
  const pages = [];
  for (let si = 0; si < doc.slides.length; si++) {
    const s = doc.slides[si];
    const items = [];
    for (let ti = 0; ti < s.textItems.length; ti++) {
      const t = s.textItems[ti];
      let txt = ''; try { txt = String(t.objectText()); } catch (e) {}
      const q = t.position();
      const rec = {
        index: ti, x: Math.round(q.x), y: Math.round(q.y),
        w: Math.round(t.width()), h: Math.round(t.height()),
        text: txt, paras: []
      };
      try {
        const ps = t.objectText.paragraphs;
        for (let pi = 0; pi < ps.length; pi++) {
          let sz = null, col = null;
          try { sz = Number(ps[pi].size()); } catch (e) {}
          try { const c = ps[pi].color(); col = [c[0], c[1], c[2]]; } catch (e) {}
          rec.paras.push({ size: sz, color: col });
        }
      } catch (e) {}
      items.push(rec);
    }
    pages.push({ slide: si + 1, items: items });
  }
  return JSON.stringify(pages);
}
"""


def audit(doc_name: str) -> dict:
    raw = jxa(READ, {"doc": doc_name})
    if isinstance(raw, dict) and "error" in raw:
        raise SystemExit(raw["error"])
    pages = raw if isinstance(raw, list) else raw.get("value", [])

    findings = {"multi_para_same_size": [], "zero_size": [], "empty": [], "overflow": []}
    for page in pages:
        for it in page["items"]:
            sizes = [p["size"] for p in it["paras"] if p["size"] is not None]
            if len(it["paras"]) > 1 and len(sizes) > 1 and len(set(sizes)) == 1:
                findings["multi_para_same_size"].append(
                    {"slide": page["slide"], "index": it["index"], "size": sizes[0],
                     "paras": len(it["paras"]), "text": it["text"][:40].replace("\n", " / ")})
            if (it["w"] == 0 or it["h"] == 0) and it["text"].strip():
                findings["zero_size"].append(
                    {"slide": page["slide"], "index": it["index"], "text": it["text"][:30]})
            if not it["text"].strip() and it["w"] > 0:
                findings["empty"].append(
                    {"slide": page["slide"], "index": it["index"],
                     "w": it["w"], "h": it["h"]})
            # 超框估算：行数 * 字号 * 1.25 > 框高 * 1.35
            if sizes and it["w"] > 40 and it["h"] > 10:
                size = max(sizes)
                approx_chars = max(1, int(it["w"] / max(6.0, size * 0.95)))
                lines = 0
                for para in it["text"].split("\n"):
                    lines += max(1, -(-len(para) // approx_chars))
                need = lines * size * 1.25
                if need > it["h"] * 1.35:
                    findings["overflow"].append(
                        {"slide": page["slide"], "index": it["index"], "size": size,
                         "need": round(need), "box_h": it["h"],
                         "text": it["text"][:40].replace("\n", " / ")})
    return findings


def open_deck(path: str) -> str:
    """用 Keynote 打开 .key，返回文稿名。"""
    from keynote_kit.runner import applescript
    name = os.path.basename(path)
    if name.endswith(".key"):
        name = name[:-4]
    applescript(f'tell application "Keynote" to open POSIX file "{os.path.abspath(path)}"')
    return name


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    doc_mode = "--doc" in sys.argv
    total = 0
    for arg in args:
        doc = arg if doc_mode else open_deck(arg)
        try:
            f = audit(doc)
        except SystemExit as e:
            print(f"❌ {doc}: {e}")
            total += 1
            continue
        n = sum(len(v) for v in f.values())
        total += n
        print(f"\n=== {doc} ===")
        for key, label in [("multi_para_same_size", "多段同号（疑似样式落错）"),
                           ("zero_size", "零尺寸元素"),
                           ("empty", "空文本框"),
                           ("overflow", "疑似超框")]:
            items = f[key]
            print(f"  {label}: {len(items)}")
            for it in items[:8]:
                print("    ", json.dumps(it, ensure_ascii=False))
            if len(items) > 8:
                print(f"     …还有 {len(items) - 8} 条")
    print(f"\n合计问题 {total} 条")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
