"""把 PPTX 拆解成 keynote-kit 的 page spec（用于「1:1 复刻」实验）。

    python tools/pptx_to_spec.py deck.pptx --out /tmp/px/specs [--slides 1-10]

坐标系：PPTX 的 EMU 除以 12700 就是 Keynote 的点（1920×1080 画布）。
输出：
    <out>/slide-01.json ...   每页一个 spec
    <out>/media/*.png|jpg|mp4 提取出来的图片与视频
    <out>/report.json         拆解报告（无法表达的东西列在这里）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN

EMU_PER_PT = 12700


def pt(v) -> float:
    return round(v / EMU_PER_PT, 1) if v is not None else 0.0


def color_hex(fmt) -> str | None:
    """从 fill / font 的 color format 拿 #RRGGBB。"""
    try:
        if fmt.type is None:
            return None
        rgb = fmt.fore_color.rgb
        return f"#{rgb}"
    except Exception:
        return None


def alignment_of(para) -> str:
    m = {PP_ALIGN.LEFT: "left", PP_ALIGN.CENTER: "center",
         PP_ALIGN.RIGHT: "right", PP_ALIGN.JUSTIFY: "justify"}
    return m.get(para.alignment, "left")


def run_style(run) -> dict:
    st = {}
    if run.font.size:
        st["size"] = round(run.font.size.pt, 1)
    if run.font.name:
        st["font"] = run.font.name
    hexc = color_hex(run.font.color)
    if hexc:
        st["color"] = hexc
    if run.font.bold:
        st["bold"] = True
    return st


def walk(shapes, transform=(0, 0, 1, 1), depth=0):
    """展开分组，把子元素坐标换算到画布坐标。"""
    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP and depth < 4:
            try:
                gx, gy, gw, gh = sh.left, sh.top, sh.width, sh.height
                cx, cy, cw, ch = sh.child_offset_x, sh.child_offset_y, sh.child_extents.cx, sh.child_extents.cy
                sx = (gw / cw) if cw else 1
                sy = (gh / ch) if ch else 1
                ox, oy, _, _ = transform
                yield from walk(sh.shapes, (ox + gx - cx * sx, oy + gy - cy * sy, sx, sy), depth + 1)
            except Exception:
                yield from walk(sh.shapes, transform, depth + 1)
            continue
        yield sh, transform


def extract_media(shape, outdir: str) -> str | None:
    """把图片/视频落盘，按内容哈希去重。"""
    try:
        blob = shape.image.blob
        ext = shape.image.ext
    except Exception:
        try:
            blob = shape.media  # 占位，走 rId 解析
            return None
        except Exception:
            return None
    os.makedirs(outdir, exist_ok=True)
    digest = hashlib.sha1(blob).hexdigest()[:12]
    path = os.path.join(outdir, f"{digest}.{ext}")
    if not os.path.exists(path):
        with open(path, "wb") as fh:
            fh.write(blob)
    return path


def _chain_props(para, run):
    """按 rPr → pPr/defRPr → lstStyle/lvl1/defRPr 的顺序找属性。"""
    from pptx.oxml.ns import qn
    chain = []
    el = run._r.find(qn("a:rPr")) if run is not None else None
    if el is not None:
        chain.append(el)
    p_el = para._p
    ppr = p_el.find(qn("a:pPr"))
    if ppr is not None:
        d = ppr.find(qn("a:defRPr"))
        if d is not None:
            chain.append(d)
    txBody = p_el.getparent()
    lst = txBody.find(qn("a:lstStyle"))
    if lst is not None:
        lvl = lst.find(qn("a:lvl1pPr"))
        if lvl is not None:
            d = lvl.find(qn("a:defRPr"))
            if d is not None:
                chain.append(d)
    return chain


def resolve_run(para, run, issues):
    from pptx.oxml.ns import qn
    chain = _chain_props(para, run)
    size = color = font = None
    bold = False
    for node in chain:
        if size is None and node.get("sz"):
            size = round(int(node.get("sz")) / 100, 1)
        if not bold and node.get("b") == "1":
            bold = True
        if color is None:
            fill = node.find(qn("a:solidFill"))
            if fill is not None:
                clr = fill.find(qn("a:srgbClr"))
                if clr is not None:
                    color = "#" + clr.get("val")
        if font is None:
            latin = node.find(qn("a:latin"))
            if latin is not None and latin.get("typeface"):
                font = latin.get("typeface")
    return {"size": size or 18, "color": color, "font": font, "bold": bold}


def resolve_align(para, issues):
    from pptx.oxml.ns import qn
    ppr = para._p.find(qn("a:pPr"))
    if ppr is not None and ppr.get("algn"):
        return {"l": "left", "ctr": "center", "r": "right", "just": "justify"}.get(ppr.get("algn"), "left")
    txBody = para._p.getparent()
    lst = txBody.find(qn("a:lstStyle"))
    if lst is not None:
        lvl = lst.find(qn("a:lvl1pPr"))
        if lvl is not None and lvl.get("algn"):
            return {"l": "left", "ctr": "center", "r": "right", "just": "justify"}.get(lvl.get("algn"), "left")
    return "left"


def shape_to_element(sh, tr, outdir, issues):
    ox, oy, sx, sy = tr
    try:
        left, top = sh.left or 0, sh.top or 0
        width, height = sh.width or 0, sh.height or 0
    except Exception:
        return None
    box = [round((ox + left * sx) / EMU_PER_PT, 1), round((oy + top * sy) / EMU_PER_PT, 1),
           round(width * sx / EMU_PER_PT, 1), round(height * sy / EMU_PER_PT, 1)]

    if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
        path = extract_media(sh, outdir)
        if not path:
            issues["picture_failed"] += 1
            return None
        return {"type": "image", "box": box, "path": path}

    if sh.shape_type == MSO_SHAPE_TYPE.MEDIA:
        issues["media_unsupported"] += 1        # 视频：Keynote 侧无法用 API 建 movie
        return None

    if getattr(sh, "has_table", False) and sh.has_table:
        data = [[c.text.strip() for c in row.cells] for row in sh.table.rows]
        return {"type": "table", "box": box, "data": data}

    if sh.has_text_frame and sh.text_frame.text.strip():
        tf = sh.text_frame
        paragraphs = []
        for para in tf.paragraphs:
            if not para.text.strip():
                continue
            runs = []
            for run in para.runs:
                if not run.text:
                    continue
                st = resolve_run(para, run, issues)
                runs.append({"text": run.text, **st})
            if not runs:
                runs = [{"text": para.text, "size": 18, "color": None, "font": None, "bold": False}]
            align = resolve_align(para, issues)
            issues["align_" + align] += 1
            paragraphs.append({"align": align, "runs": runs})
        if not paragraphs:
            return None
        return {"type": "rich", "box": box, "paragraphs": paragraphs}

    if sh.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
        fill = color_hex(sh.fill) if getattr(sh, "fill", None) else None
        if fill:
            return {"type": "card", "box": box,
                    "style": {"fill": fill, "radius": 0}}
        issues["autoshape_nofill"] += 1
        return None

    issues["other_" + str(sh.shape_type)] += 1
    return None


def slide_bg(slide, outdir: str) -> dict | None:
    """背景可能是纯色，也可能是图片（常见于整套 deck 的深色底）。"""
    try:
        from pptx.oxml.ns import qn
        bg = slide._element.find(qn("p:cSld")).find(qn("p:bg"))
        if bg is None:
            return None
        pr = bg.find(qn("p:bgPr"))
        if pr is None:
            return None
        solid = pr.find(qn("a:solidFill"))
        if solid is not None:
            clr = solid.find(qn("a:srgbClr"))
            if clr is not None:
                return {"type": "solid", "color": "#" + clr.get("val")}
        blip = pr.find(qn("a:blipFill"))
        if blip is not None:
            node = blip.find(qn("a:blip"))
            rid = node.get(qn("r:embed"))
            blob = slide.part.related_part(rid).blob
            ext = slide.part.related_part(rid).partname.ext
            os.makedirs(outdir, exist_ok=True)
            digest = hashlib.sha1(blob).hexdigest()[:12]
            path = os.path.join(outdir, f"bg_{digest}.{ext}")
            if not os.path.exists(path):
                open(path, "wb").write(blob)
            return {"type": "image", "path": path}
    except Exception:
        pass
    return None


def slide_bg_color(slide) -> str | None:
    """取 p:bg 的纯色背景。"""
    try:
        from pptx.oxml.ns import qn
        bg = slide._element.find(qn("p:cSld")).find(qn("p:bg"))
        if bg is None:
            return None
        for tag in ("p:bgPr", "p:bgRef"):
            node = bg.find(qn(tag))
            if node is None:
                continue
            fill = node.find(qn("a:solidFill"))
            if fill is not None:
                clr = fill.find(qn("a:srgbClr"))
                if clr is not None:
                    return "#" + clr.get("val")
    except Exception:
        pass
    return None


def inherited_elements(slide, outdir, issues) -> list:
    """母版 / 版式上的装饰图片也要复刻（每页都有）。"""
    out = []
    try:
        for container in (slide.slide_layout.slide_master, slide.slide_layout):
            for sh, tr in walk(container.shapes):
                el = shape_to_element(sh, tr, outdir, issues)
                if el and el["type"] == "image":
                    el["id"] = f"lay{len(out)}"
                    out.append(el)
    except Exception:
        pass
    return out


def build(pptx_path: str, outdir: str, slides: range | None = None) -> dict:
    prs = Presentation(pptx_path)
    os.makedirs(outdir, exist_ok=True)
    media_dir = os.path.join(outdir, "media")
    report = {"slides": [], "issues": Counter()}

    for idx, slide in enumerate(prs.slides, start=1):
        if slides and idx not in slides:
            continue
        issues = Counter()
        elements = inherited_elements(slide, media_dir, issues)
        seen = set()
        elements = [e for e in elements
                    if not ((e.get("path"), tuple(e["box"])) in seen
                            or seen.add((e.get("path"), tuple(e["box"]))))]
        for sh, tr in walk(slide.shapes):
            el = shape_to_element(sh, tr, media_dir, issues)
            if el:
                el["id"] = f"e{len(elements)}"
                elements.append(el)
        report["issues"] += issues
        spec = {"elements": elements}
        bg = slide_bg(slide, media_dir) or None
        if bg:
            spec["background"] = bg
        with open(os.path.join(outdir, f"slide-{idx:02d}.json"), "w", encoding="utf-8") as fh:
            json.dump(spec, fh, ensure_ascii=False, indent=1)
        report["slides"].append({"n": idx, "elements": len(elements),
                                 "kinds": dict(Counter(e["type"] for e in elements)),
                                 "issues": dict(issues)})

    with open(os.path.join(outdir, "report.json"), "w", encoding="utf-8") as fh:
        json.dump({"issues": dict(report["issues"]), "slides": report["slides"]},
                  fh, ensure_ascii=False, indent=1)
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx")
    ap.add_argument("--out", required=True)
    ap.add_argument("--slides", default="", help="如 1-10")
    args = ap.parse_args()

    rng = None
    if args.slides:
        a, _, b = args.slides.partition("-")
        rng = range(int(a), int(b or a) + 1)

    rep = build(args.pptx, args.out, rng)
    print("pages:", len(rep["slides"]))
    print("issues:", dict(rep["issues"]))
    for s in rep["slides"][:6]:
        print(f"  P{s['n']:>2}: {s['elements']} 元素 {s['kinds']}")


if __name__ == "__main__":
    main()
