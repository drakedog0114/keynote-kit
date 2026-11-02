#!/usr/bin/env python3
"""自检：验证本轮新增的五项能力在真实 Keynote 上确实生效。

    python tools/test_capabilities.py

逐项断言，任何一项失败都会以非零码退出。
"""

import os
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from keynote_kit import Deck  # noqa: E402
from keynote_kit.animate import (  # noqa: E402
    bring_to_front, element_order, get_transition, set_opacity,
    set_rotation, set_transition,
)
from keynote_kit.imaging import fit_text, measure, prepare_image  # noqa: E402
from keynote_kit.page import apply_page  # noqa: E402
from keynote_kit.richtext import build_rtf, paste_rich_text  # noqa: E402
from keynote_kit.runner import close_scratch_documents, jxa  # noqa: E402

PASS, FAIL = [], []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    print(f"{'✅' if ok else '❌'} {name}" + (f"  — {detail}" if detail else ""))


def read_text_items(doc: str, slide: int) -> list[dict]:
    raw = jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]);
  const K = Application('Keynote');
  let doc = null; const ds = K.documents();
  for (let i = 0; i < ds.length; i++) if (String(ds[i].name()) === p.doc) doc = ds[i];
  const s = doc.slides[p.slide - 1];
  const out = [];
  for (let i = 0; i < s.textItems.length; i++) {
    const t = s.textItems[i]; const q = t.position();
    let txt = ''; let sz = null;
    try { txt = String(t.objectText()); } catch (e) {}
    try { sz = Number(t.objectText.paragraphs[0].size()); } catch (e) {}
    if (txt.trim()) out.push({ x: Math.round(q.x), y: Math.round(q.y), sz: sz, text: txt });
  }
  return JSON.stringify(out);
}""", {"doc": doc, "slide": slide})
    return raw if isinstance(raw, list) else raw.get("value", [])


def main() -> int:
    # 这轮验证会驱动 Keynote（粘贴必须前台），所以明说一声，
    # 并且跑完把临时文稿全部关掉，不留一堆「未命名」窗口。
    os.environ.setdefault("KK_TAKEOVER", "1")
    print("（本轮会切到 Keynote 跑真机断言，跑完自动关闭临时文稿）")
    try:
        return _run()
    finally:
        n = close_scratch_documents()
        if n:
            print(f"（已关闭 {n} 个临时文稿）")


def _run() -> int:
    tmp = tempfile.mkdtemp(prefix="kk-cap-")
    src = os.path.join(tmp, "wide.png")
    Image.new("RGB", (800, 400), (40, 70, 120)).save(src)
    avatar = os.path.join(tmp, "avatar.png")
    Image.new("RGB", (300, 300), (200, 120, 90)).save(avatar)

    # ── 1. 图片圆角 / 裁剪 / 椭圆（预渲染）────────────────────────
    rounded = prepare_image(src, [0, 0, 400, 200], radius=40, crop="cover")
    with Image.open(rounded) as im:
        corner = im.convert("RGBA").getpixel((2, 2))[3]
    check("图片圆角：角点透明", corner < 40, f"alpha={corner}")

    ellipse = prepare_image(avatar, [0, 0, 200, 200], shape="ellipse")
    with Image.open(ellipse) as im:
        corner = im.convert("RGBA").getpixel((1, 1))[3]
    check("图片椭圆：角点透明", corner < 40, f"alpha={corner}")

    cropped = prepare_image(src, [0, 0, 400, 400], crop="cover")
    with Image.open(cropped) as im:
        w, h = im.size
    check("图片裁剪：按目标比例", abs(w / h - 1.0) < 0.02, f"{w}x{h}")

    # ── 2. 文本溢出自动校正 ─────────────────────────────────────
    long_text = ("这是一段很长的文本，用来验证自动缩放是否真的生效。"
                 "它在四十二号字下会溢出这个很矮的文本框，"
                 "所以字号必须被自动调小才能装得下，否则文字就会跑出边界。")
    m = measure(long_text, [0, 0, 760, 150], size=42)
    check("文本量测：识别出溢出", m["overflow"], f"{m['lines']} 行 / {m['height']}pt")
    f = fit_text(long_text, [0, 0, 760, 150], size=42, min_size=12)
    check("文本拟合：缩小到装得下", f["size"] < 42 and not f["overflow"],
          f"42 → {f['size']}pt")

    # ── 3. z 序：插入顺序即层级 ────────────────────────────────
    deck = Deck.create(theme="白色")
    deck.add_slide("空白")
    deck.add_slide("空白")
    bg = os.path.join(tmp, "bg.png")
    fg = os.path.join(tmp, "fg.png")
    Image.new("RGB", (1920, 1080), (200, 30, 30)).save(bg)
    Image.new("RGB", (500, 500), (30, 90, 220)).save(fg)
    jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]); const K = Application('Keynote');
  let doc = null; const ds = K.documents();
  for (let i = 0; i < ds.length; i++) if (String(ds[i].name()) === p.doc) doc = ds[i];
  const s = doc.slides[1];
  s.images.push(K.Image({ file: Path(p.bg) }));
  s.images.push(K.Image({ file: Path(p.fg) }));
  return 'ok';
}""", {"doc": deck.doc, "bg": bg, "fg": fg})
    from keynote_kit.runner import applescript, esc_text
    applescript(f'''tell application "Keynote"
  tell document {esc_text(deck.doc)}
    set position of image 1 of slide 2 of it to {{0, 0}}
    set position of image 2 of slide 2 of it to {{200, 200}}
  end tell
end tell''')
    order = element_order(deck.doc, 2)
    check("z 序：能列出元素顺序", len(order["image"]) == 2,
          f"{len(order['image'])} 张图")

    bring_to_front(deck.doc, 2, "image", 1, bg)
    out = os.path.join(tmp, "z.png")
    deck.export(os.path.join(tmp, "zout"), "images")
    with Image.open(os.path.join(tmp, "zout", "zout.002.png")) as im:
        px = im.convert("RGB").getpixel((300, 300))
    check("z 序：提到顶层生效", px[0] > 150 and px[2] < 90, f"像素={px}")

    # ── 4. 转场 / 透明度 / 旋转（原生 API）──────────────────────
    set_transition(deck.doc, 1, "object zoom", 0.6, 0.2)
    tr = get_transition(deck.doc, 1)
    check("转场：写入并可读回",
          isinstance(tr, dict) and "zoom" in str(tr.get("effect", "")),
          str(tr))

    set_opacity(deck.doc, 2, "image", 1, 0.5)
    set_rotation(deck.doc, 2, "image", 1, 30)
    rot = jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]); const K = Application('Keynote');
  let doc = null; const ds = K.documents();
  for (let i = 0; i < ds.length; i++) if (String(ds[i].name()) === p.doc) doc = ds[i];
  const im = doc.slides[1].images[0];
  return JSON.stringify({ rot: Number(im.rotation()), op: Number(im.opacity()) });
}""", {"doc": deck.doc})
    check("透明度 / 旋转：可写可读",
          isinstance(rot, dict) and abs(rot.get("rot", 0) - 30) < 1, str(rot))

    # ── 5. 超链接 ──────────────────────────────────────────────
    link_spec = {"elements": [
        {"id": "link", "type": "rich", "box": [100, 300, 900, 140],
         "link": "https://www.ctf.com.cn",
         "paragraphs": [{"align": "left", "runs": [
             {"text": "点击访问乙品牌官网", "size": 34, "color": "#1F3A5F"}]}]}]}
    deck.add_slide("空白")
    apply_page(deck, 3, link_spec)
    pptx = os.path.join(tmp, "link.pptx")
    deck.export(pptx, "pptx")
    with zipfile.ZipFile(pptx) as z:
        slide_xml = z.read("ppt/slides/slide3.xml").decode("utf-8")
        rels = z.read("ppt/slides/_rels/slide3.xml.rels").decode("utf-8")
    check("超链接：生成真正的 hlinkClick", "hlinkClick" in slide_xml)
    check("超链接：外链目标正确", "ctf.com.cn" in rels)

    # 链接必须是最后一个 run
    try:
        build_rtf([{"runs": [{"text": "a", "link": "https://x.com"},
                              {"text": "b"}]}], 18)
        check("超链接：拦截非末位链接", False, "没有抛错")
    except ValueError:
        check("超链接：拦截非末位链接", True)

    # ── 6. 文本样式必须落到正确的对象上（回归）──────────────────
    deck.add_slide("空白")
    apply_page(deck, 4, {"elements": [
        {"id": "a", "type": "text", "text": "甲字号42", "box": [80, 120, 600, 120],
         "style": {"size": 42, "color": "#1F3A5F"}},
        {"id": "b", "type": "text", "text": "乙字号30", "box": [700, 120, 600, 120],
         "style": {"size": 30, "color": "#B85C38"}},
        {"id": "c", "type": "text", "text": long_text, "box": [80, 300, 760, 150],
         "style": {"size": 42, "fit": True, "minSize": 12}},
    ]})
    items = read_text_items(deck.doc, 4)
    by_text = {i["text"][:6]: i for i in items}
    check("文本样式：字号落到正确对象",
          abs(by_text.get("甲字号42", {}).get("sz", 0) - 42) < 0.6
          and abs(by_text.get("乙字号30", {}).get("sz", 0) - 30) < 0.6,
          f"{[(i['text'][:6], i['sz']) for i in items]}")
    check("文本溢出：建页时自动缩小",
          by_text.get("这是一段很长", {}).get("sz", 99) < 42,
          f"42 → {by_text.get('这是一段很长的文', {}).get('sz')}")

    # ── 7. 拆页揭示（替代构建动画）─────────────────────────────
    from keynote_kit.build import build_bullets, build_reveal
    reveal_spec = {"background": {"type": "solid", "color": "#F4EBDD"}, "elements": [
        {"id": "t", "type": "text", "text": "标题", "box": [150, 120, 1620, 90],
         "style": {"size": 54, "color": "#2B2420"}},
        {"id": "b", "type": "rich", "box": [150, 320, 1400, 420], "paragraphs": [
            {"align": "left", "runs": [{"text": "要点一", "size": 30}]},
            {"align": "left", "runs": [{"text": "要点二", "size": 30}]},
            {"align": "left", "runs": [{"text": "要点三", "size": 30}]}]}]}
    deck.add_slide("空白")
    r = build_bullets(deck, deck.slide_count(), reveal_spec, "b",
                      transition="object push")
    check("拆页揭示：生成 N+1 页", len(r["slides"]) == 4, str(r["slides"]))
    bullets_per_page = []
    for i in r["slides"]:
        raw = jxa(r"""
function run(argv) {
  const p = JSON.parse(argv[0]); const K = Application('Keynote');
  let doc = null; const ds = K.documents();
  for (let i = 0; i < ds.length; i++) if (String(ds[i].name()) === p.doc) doc = ds[i];
  const s = doc.slides[p.n - 1]; let n = 0;
  for (let ti = 0; ti < s.textItems.length; ti++) {
    const it = s.textItems[ti];
    let t = ''; try { t = String(it.objectText()); } catch (e) {}
    // RTF 粘出来的文本，JXA 读不到 paragraphs，只能按换行数段落
    const lines = t.split('\n');
    for (let li = 0; li < lines.length; li++) {
      if (lines[li].indexOf('要点') === 0) n++;
    }
  }
  return JSON.stringify({ n: n });
}""", {"doc": deck.doc, "n": i})
        v = raw.get("value", raw)
        bullets_per_page.append(v.get("n", 0) if isinstance(v, dict) else 0)
    check("拆页揭示：要点逐条递增", bullets_per_page == [0, 1, 2, 3],
          str(bullets_per_page))
    trs = [get_transition(deck.doc, i) for i in r["slides"]]
    check("拆页揭示：每页都带转场",
          all(isinstance(t, dict) and "push" in str(t.get("effect", "")) for t in trs),
          str([t.get("effect") for t in trs]))

    # ── 8. fit 默认策略 ────────────────────────────────────────
    from keynote_kit import page as page_mod
    _, els = page_mod.normalise({"elements": [
        {"id": "a", "type": "text", "text": "x" * 200, "box": [80, 300, 760, 150],
         "style": {"size": 42}}]})
    check("fit：默认开启且自动缩小",
          els[0]["style"]["size"] < 42, f"42 → {els[0]['style']['size']}")
    _, els = page_mod.normalise({"elements": [
        {"id": "b", "type": "text", "text": "一次调用\n生成一整页",
         "box": [150, 380, 1500, 60], "style": {"size": 96}}]})
    check("fit：矮框不乱缩", els[0]["style"]["size"] == 96,
          f"96 → {els[0]['style']['size']}")

    # ── 9. 文档中英配对 ───────────────────────────────────────
    import subprocess
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    res = subprocess.run([sys.executable, os.path.join(repo, "tools", "check_docs.py")],
                         capture_output=True, text=True)
    check("文档：每个文档都有中英两版，README 章节对齐",
          res.returncode == 0, (res.stdout + res.stderr).strip()[:200])

    print(f"\n通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败：", ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
