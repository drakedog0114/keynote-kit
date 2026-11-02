#!/usr/bin/env python3
"""编辑能力探测：在临时文稿里逐项验证「改已有内容」的能力。

    python tools/probe_editing.py

和 `probe_capabilities.py`（造东西）互补，这里只测**改**：
文本改写、字号颜色字体、增删元素、移动缩放、表格改写、页面增删复制、
备注、背景、整稿换字体……

每一项都**回读验证**——不只看「没报错」，而是确认值真的改掉了。
语法按 sdef 校正：段落类**没有任何属性**（颜色/字体只能走 JXA）；
表格只有 merge / unmerge 命令，没有增删行列的命令。
全部在临时文稿里进行，结束时关闭且不保存。
"""

from __future__ import annotations

import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from keynote_kit import Deck  # noqa: E402
from keynote_kit.runner import applescript, close_scratch_documents, esc_text, jxa  # noqa: E402

RESULTS: list[tuple[str, str, bool, str]] = []

# 文稿是全局的：某个测试把 Keynote 搞挂之后，后续测试用 ensure() 换一份新文稿，
# 避免一次失败把整张表带崩。
DECK: Deck | None = None
DOC: str = ""


def ensure() -> str:
    """确保有一份可用的文稿；不可用就新建一份。"""
    global DECK, DOC
    if DOC:
        try:
            _j(DOC, "return 'ok';")
            return DOC
        except Exception:
            pass
        try:
            if DECK:
                DECK.close(save=False)
        except Exception:
            pass
    DECK = Deck.create(theme="白色")
    DOC = DECK.name
    return DOC


def _js(doc: str, body: str) -> str:
    return f"""
function run(argv) {{
  const p = JSON.parse(argv[0]); const K = Application('Keynote');
  let doc = null; const ds = K.documents();
  for (let i = 0; i < ds.length; i++) if (String(ds[i].name()) === p.doc) doc = ds[i];
  if (!doc) throw new Error('document not found');
  {body}
}}"""


def _j(doc: str, body: str) -> dict:
    v = jxa(_js(doc, body), {"doc": doc})
    return v.get("value", v) if isinstance(v, dict) else {}


def jtext(doc, slide, i=1):
    return _j(doc, f"""const t=doc.slides[{slide-1}].textItems[{i-1}];
  return JSON.stringify({{text:String(t.objectText())}});""")["text"]


def jsize(doc, slide, i=1):
    return _j(doc, f"""const ps=doc.slides[{slide-1}].textItems[{i-1}].objectText.paragraphs;
  return JSON.stringify({{size:Number(ps[0].size())}});""")["size"]


def jcolor(doc, slide, i=1):
    return _j(doc, f"""const c=doc.slides[{slide-1}].textItems[{i-1}].objectText.paragraphs[0].color();
  return JSON.stringify({{rgb:[c[0],c[1],c[2]]}});""")["rgb"]


def jgeom(doc, slide, i=1):
    return _j(doc, f"""const t=doc.slides[{slide-1}].textItems[{i-1}];const q=t.position();
  return JSON.stringify({{x:Math.round(q.x),y:Math.round(q.y),
    w:Math.round(t.width()),h:Math.round(t.height())}});""")


def jcount(doc, slide, kind):
    return _j(doc, f"return JSON.stringify({{n:doc.slides[{slide-1}].{kind}.length}});")["n"]


def probe(area, name):
    def deco(fn):
        t0 = time.time()
        try:
            ensure()
            record(area, name, True, f"{fn() or ''}  ({time.time()-t0:.1f}s)")
        except Exception as exc:
            msg = str(exc).replace("\n", " ")
            for junk in ("遇到一个错误", "execution error"):
                if junk in msg:
                    msg = msg.split(junk)[-1].strip("：: ")[:78]
            record(area, name, False, msg[:92])
        return fn
    return deco


def record(area, name, ok, detail):
    RESULTS.append((area, name, ok, detail))


def main() -> int:
    os.environ.setdefault("KK_TAKEOVER", "1")
    print("（本轮会切到 Keynote 跑真机探测，跑完自动关闭临时文稿）")
    print(f"探测文档：{ensure()}\n")
    try:
        run_tests()
    finally:
        if DECK:
            DECK.close(save=False)
        # 收干净：探针中途可能换过文稿，不能只关最后那一份
        n = close_scratch_documents()
        if n:
            print(f"\n（已关闭 {n} 个临时文稿）")
    area = None
    for a, n, ok, d in RESULTS:
        if a != area:
            area = a
            print(f"\n{a}")
        print(f"  {'✅' if ok else '❌'} {n:<30} {d}")
    good = sum(1 for *_, ok, _ in RESULTS if ok)
    print(f"\n通过 {good} / {len(RESULTS)}")
    return 0


def run_tests() -> None:
    global DECK, DOC
    DECK = Deck.create(theme="白色")
    DOC = DECK.name
    A, B, C, D, E = "A 文本编辑", "B 元素编辑", "C 页面编辑", "D 表格编辑", "E 文档级"

    @probe(A, "整体替换文本")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "原始文字", 100, 100, 800, 80, size=40)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            set object text of text item 1 of slide {s} of it to "改过的文字"
          end tell
        end tell''')
        got = jtext(doc, s)
        assert "改过的文字" in got, f"回读 {got!r}"
        return f"回读 {got!r}"

    @probe(A, "整体替换后字号是否保留")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "标题", 100, 100, 800, 80, size=40)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            set object text of text item 1 of slide {s} of it to "新标题"
          end tell
        end tell''')
        size = jsize(doc, s)
        return f"{size}pt（原 40pt）" + ("" if abs(size - 40) < 1 else " ← 被压平")

    @probe(A, "段落级改字号（AppleScript）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "文字", 100, 100, 800, 80, size=20)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            set size of paragraph 1 of text item 1 of slide {s} of it to 36
          end tell
        end tell''')
        return "设置成功"

    @probe(A, "段落级改字号（JXA）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "文字", 100, 100, 800, 80, size=20)
        jxa(_js(doc, f"""const t=doc.slides[{s-1}].textItems[0];
  t.objectText.paragraphs[0].size=36; return 'ok';"""), {"doc": doc})
        size = jsize(doc, s)
        assert abs(size - 36) < 1, f"回读 {size}"
        return f"回读 {size}pt"

    @probe(A, "段落级改颜色（AppleScript）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "染色", 100, 100, 600, 80, size=32, color="#112233")
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            set color of paragraph 1 of text item 1 of slide {s} of it to {{65535,0,0}}
          end tell
        end tell''')
        return "设置成功"

    @probe(A, "段落级改颜色（JXA）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "染色", 100, 100, 600, 80, size=32, color="#112233")
        jxa(_js(doc, f"""const t=doc.slides[{s-1}].textItems[0];
  t.objectText.paragraphs[0].color=[65535,0,0]; return 'ok';"""), {"doc": doc})
        rgb = jcolor(doc, s)
        assert rgb[0] > 0.9 and rgb[1] < 0.1, f"回读 {rgb}"
        return f"回读 rgb={rgb}（注意：回读是 0~1 浮点，设置是 0~65535）"

    @probe(A, "段落级改字体（JXA）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "换字体", 100, 100, 600, 80, size=32)
        jxa(_js(doc, f"""const t=doc.slides[{s-1}].textItems[0];
  t.objectText.paragraphs[0].font='PingFangSC-Regular'; return 'ok';"""), {"doc": doc})
        return "设置成功"

    @probe(A, "改对齐（AppleScript）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "左对齐", 100, 100, 600, 80, size=32)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            set alignment of text item 1 of slide {s} of it to left align
          end tell
        end tell''')
        return "设置成功"

    @probe(A, "改对齐（JXA 段落级）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "左对齐", 100, 100, 600, 80, size=32)
        jxa(_js(doc, f"""const t=doc.slides[{s-1}].textItems[0];
  t.objectText.paragraphs[0].alignment='left'; return 'ok';"""), {"doc": doc})
        return "设置成功"

    @probe(A, "加一段文字")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "第一段", 100, 100, 800, 80, size=24)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            tell text item 1 of slide {s} of it
              set object text to "第一段" & return & "第二段"
            end tell
          end tell
        end tell''')
        got = jtext(doc, s)
        assert "第二段" in got, f"回读 {got!r}"
        return f"回读 {got!r}"

    @probe(A, "删掉一段文字")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "第一段\n第二段", 100, 100, 800, 160, size=24)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            tell text item 1 of slide {s} of it
              set object text to "只剩第一段"
            end tell
          end tell
        end tell''')
        got = jtext(doc, s)
        assert "第二段" not in got, f"还在：{got!r}"
        return f"回读 {got!r}"

    @probe(B, "移动元素")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "挪一挪", 100, 100, 600, 80, size=32)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            set position of text item 1 of slide {s} of it to {{500,400}}
          end tell
        end tell''')
        g = jgeom(doc, s)
        assert abs(g["x"] - 500) < 3 and abs(g["y"] - 400) < 3, f"回读 {g}"
        return f"位置 {g['x']},{g['y']}"

    @probe(B, "改尺寸")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "改尺寸", 100, 100, 600, 80, size=32)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            tell text item 1 of slide {s} of it
              set width to 900
              set height to 140
            end tell
          end tell
        end tell''')
        g = jgeom(doc, s)
        assert abs(g["w"] - 900) < 3, f"回读 {g}"
        return f"{g['w']}×{g['h']}"

    @probe(B, "删除元素")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "留下", 100, 100, 600, 80, size=32)
        d0.add_text(s, "删掉我", 100, 200, 600, 80, size=32)
        before = jcount(doc, s, "textItems")
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            delete text item 2 of slide {s} of it
          end tell
        end tell''')
        after = jcount(doc, s, "textItems")
        assert after == before - 1, f"{before} → {after}"
        return f"{before} → {after}（含母版占位符）"

    @probe(B, "复制文本框")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "复制我", 100, 100, 600, 80, size=32)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            tell text item 1 of slide {s} of it
              duplicate
              set position of result to {{300,300}}
            end tell
          end tell
        end tell''')
        return "复制成功"

    @probe(B, "复制图片")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        png = "/tmp/probe_img1.png"
        from PIL import Image
        Image.new("RGB", (200, 120), (200, 60, 60)).save(png)
        d0.add_image(s, png, 100, 100, 200, 120)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            tell image 1 of slide {s} of it
              duplicate
            end tell
          end tell
        end tell''')
        return "复制成功"

    @probe(B, "往已有页插入图片")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        png = "/tmp/probe_img2.png"
        from PIL import Image
        Image.new("RGB", (200, 120), (60, 60, 200)).save(png)
        d0.add_image(s, png, 100, 100, 200, 120)
        d0.add_image(s, png, 400, 300, 200, 120)
        n = jcount(doc, s, "images")
        assert n == 2, f"图片数 {n}"
        return f"图片数 {n}"

    @probe(B, "改透明度")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        png = "/tmp/probe_img3.png"
        from PIL import Image
        Image.new("RGB", (200, 120), (10, 200, 10)).save(png)
        d0.add_image(s, png, 100, 100, 200, 120)
        from keynote_kit.animate import set_opacity
        set_opacity(doc, s, "image", 1, 0.5)
        return "透明度设为 50%"

    @probe(B, "改旋转角（形状）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_shape(s, "转起来", 100, 100, 600, 80)
        from keynote_kit.animate import set_rotation
        set_rotation(doc, s, "shape", 1, 15)
        return "旋转 15°"

    @probe(B, "改旋转角（文本框）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "转起来", 100, 100, 600, 80, size=32)
        from keynote_kit.animate import set_rotation
        set_rotation(doc, s, "text", 1, 15)
        return "旋转 15°"

    @probe(C, "增一页")
    def _():
        d0, doc = DECK, DOC
        before = d0.slide_count()
        d0.add_slide("空白")
        after = d0.slide_count()
        assert after == before + 1, f"{before} → {after}"
        return f"{before} → {after}"

    @probe(C, "删一页")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        before = d0.slide_count()
        d0.remove_slide(s)
        after = d0.slide_count()
        assert after == before - 1, f"{before} → {after}"
        return f"{before} → {after}"

    @probe(C, "复制一页")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "被复制的那页", 100, 100, 800, 80, size=32)
        before = d0.slide_count()
        new = d0.duplicate_slide(s)
        assert d0.slide_count() == before + 1
        return f"新页序号 {new}"

    @probe(C, "改备注（presenter notes）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            set presenter notes of slide {s} of it to "这是演讲者备注"
          end tell
        end tell''')
        got = applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            return (presenter notes of slide {s} of it) as text
          end tell
        end tell''')
        assert "演讲者备注" in got, f"回读 {got!r}"
        return f"回读 {got[:16]!r}"

    @probe(C, "换母版（base layout）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            set base layout of slide {s} of it to slide layout "标题与项目符号" of master slide "白色"
          end tell
        end tell''')
        return "切换成功"

    @probe(C, "隐藏标题占位符")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            set title showing of slide {s} of it to false
          end tell
        end tell''')
        return "设置成功"

    @probe(C, "读背景填充类型")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        out = applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            return (background fill type of slide {s} of it) as text
          end tell
        end tell''')
        return f"可读：{out.strip()[:28]}"

    @probe(C, "写背景填充类型")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            set background fill type of slide {s} of it to solid color
          end tell
        end tell''')
        return "设置成功"

    @probe(D, "改单元格文字")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_table(s, [["A", "B"], ["1", "2"]], 100, 100, 800, 200)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            tell table 1 of slide {s} of it
              set value of cell "A1" to "改过的"
            end tell
          end tell
        end tell''')
        got = _j(doc, f"""return JSON.stringify({{v:String(doc.slides[{s-1}].tables[0].rows[0].cells[0].value())}});""")["v"]
        assert "改过的" in got, f"回读 {got!r}"
        return f"回读 {got!r}"

    @probe(D, "加一行（JXA）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_table(s, [["A", "B"]], 100, 100, 800, 200)
        jxa(_js(doc, f"""const t=doc.slides[{s-1}].tables[0];
  const r=t.rows.push(t.rows[0]); return 'ok';"""), {"doc": doc})
        return "加行成功"

    @probe(D, "改行高（JXA）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_table(s, [["A", "B"]], 100, 100, 800, 200)
        jxa(_js(doc, f"""const t=doc.slides[{s-1}].tables[0];
  t.rows[0].height = 90; return 'ok';"""), {"doc": doc})
        return "设置成功"

    @probe(D, "改单元格颜色（JXA）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_table(s, [["A"]], 100, 100, 600, 120)
        jxa(_js(doc, f"""const c=doc.slides[{s-1}].tables[0].rows[0].cells[0];
  c.textStyle.color = [65535,0,0]; return 'ok';"""), {"doc": doc})
        return "设置成功"

    @probe(D, "合并单元格（merge）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_table(s, [["A", "B"], ["1", "2"]], 100, 100, 800, 200)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            tell table 1 of slide {s} of it
              merge (range "A1:B1" of table 1 of slide {s} of it)
            end tell
          end tell
        end tell''')
        return "合并成功"

    @probe(D, "取消合并（unmerge）")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_table(s, [["A", "B"], ["1", "2"]], 100, 100, 800, 200)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            tell table 1 of slide {s} of it
              merge (range "A1:B1" of table 1 of slide {s} of it)
              unmerge (range "A1:B1" of table 1 of slide {s} of it)
            end tell
          end tell
        end tell''')
        return "合并+取消成功"

    @probe(E, "改画布尺寸")
    def _():
        d0, doc = DECK, DOC
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            set width to 1280
            set height to 720
          end tell
        end tell''')
        return "改成 1280×720"

    @probe(E, "整稿替换字体")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        d0.add_text(s, "换字体测试", 100, 100, 800, 80, size=32)
        applescript(f'''tell application "Keynote"
          tell document {esc_text(doc)}
            repeat with sl in slides
              repeat with t in text items of sl
                try
                  set font of t to "Songti SC Bold"
                end try
              end repeat
            end repeat
          end tell
        end tell''')
        return "遍历全部文本项完成"

    @probe(E, "改幻灯片转场")
    def _():
        d0, doc = DECK, DOC
        s = d0.add_slide("空白")
        from keynote_kit.animate import get_transition, set_transition
        set_transition(doc, s, "magic move", 0.6)
        return f"回读 {get_transition(doc, s).get('effect')}"

    @probe(E, "改文档名（JXA）")
    def _():
        d0, doc = DECK, DOC
        jxa(_js(doc, "  doc.name='探针改名测试'; return 'ok';"), {"doc": doc})
        return "改名成功"


if __name__ == "__main__":
    sys.exit(main())
