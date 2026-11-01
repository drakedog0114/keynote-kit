"""在 .key 稿里按语义批量替换文字，并保持原格式。

    python tools/replace_text.py 稿.key --map rules.json [--dry-run]

原理：Keynote 的 `set object text` 会把整段样式压平，所以替换后要按段落把
字号/字体/颜色还原回去（JXA 逐段设置）。对齐方式不动，因此右对齐/居中不会丢。

rules.json:
    {"replace": [["甲珠宝", "乙珠宝"], ["甲品牌", "乙品牌"]],
     "regex":   [["月核销\\s*(\\d+)\\s*万", "月核销 1.2 亿"]]}
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keynote_kit import Deck                       # noqa: E402
from keynote_kit.runner import applescript, esc_text, jxa  # noqa: E402

READ = r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  let doc = null; const ds = K.documents();
  for (let i = 0; i < ds.length; i++) if (String(ds[i].name()) === p.doc) doc = ds[i];
  if (!doc) return JSON.stringify({ error: 'not open' });
  const out = [];
  for (let si = 0; si < doc.slides.length; si++) {
    const s = doc.slides[si];
    for (let ti = 0; ti < s.textItems.length; ti++) {
      const t = s.textItems[ti];
      let txt = ''; try { txt = String(t.objectText()); } catch (e) {}
      if (!txt.trim()) continue;
      const style = [];
      try {
        const ps = t.objectText.paragraphs;
        for (let pi = 0; pi < ps.length; pi++) {
          const rec = { size: null, font: null };
          try { rec.size = Number(ps[pi].size()); } catch (e) {}
          try { rec.font = String(ps[pi].font()); } catch (e) {}
          style.push(rec);
        }
      } catch (e) {}
      out.push({ slide: si + 1, index: ti, text: txt, style: style });
    }
  }
  return JSON.stringify(out);
}
"""

RESTORE = r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  let doc = null; const ds = K.documents();
  for (let i = 0; i < ds.length; i++) if (String(ds[i].name()) === p.doc) doc = ds[i];
  const s = doc.slides[p.slide - 1];
  const t = s.textItems[p.index];
  const ps = t.objectText.paragraphs;
  const want = p.paragraphs;
  for (let i = 0; i < ps.length && i < want.length; i++) {
    const w = want[i];
    try { if (w.size !== null) ps[i].size = w.size; } catch (e) {}
    try { if (w.font) ps[i].font = w.font; } catch (e) {}
    try { if (w.color) ps[i].color = w.color; } catch (e) {}
  }
  return JSON.stringify({ ok: true });
}
"""


def transform(text: str, rules: dict) -> str:
    for old, new in rules.get("replace", []):
        text = text.replace(old, new)
    for pattern, repl in rules.get("regex", []):
        import re
        text = re.sub(pattern, repl, text)
    return text


def run(deck_name: str, rules: dict, dry_run: bool = False) -> dict:
    raw = jxa(READ, {"doc": deck_name})
    items = raw if isinstance(raw, list) else raw.get("value", [])
    if isinstance(items, dict) and "error" in items:
        raise SystemExit(items["error"])

    changed = []
    for item in items:
        new_text = transform(item["text"], rules)
        if new_text == item["text"]:
            continue
        changed.append((item, new_text))

    if dry_run:
        for item, new_text in changed[:40]:
            print(f"P{item['slide']}#{item['index']} {item['text'][:40]!r}\n    → {new_text[:40]!r}")
        return {"changed": len(changed), "dry_run": True}

    for item, new_text in changed:
        joined = new_text
        applescript(f'''
tell application "Keynote"
  tell document {esc_text(deck_name)}
    set object text of text item {item["index"] + 1} of slide {item["slide"]} of it to {esc_text(joined)}
  end tell
end tell''')
        if item.get("style"):
            jxa(RESTORE, {"doc": deck_name, "slide": item["slide"], "index": item["index"],
                          "paragraphs": item["style"]})
    return {"changed": len(changed), "scanned": len(items)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck", help="已打开的文稿名（不含路径）")
    ap.add_argument("--map", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    rules = json.load(open(args.map, encoding="utf-8"))
    print(json.dumps(run(args.deck, rules, args.dry_run), ensure_ascii=False))


if __name__ == "__main__":
    main()
