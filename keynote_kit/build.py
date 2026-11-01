"""用「转场 + 拆页」替代构建动画。

Keynote 的构建动画（逐个出现、飞入）**没有 API**，只能点 UI，脆弱。
但汇报稿真正要的其实是「讲到哪里，页面上才多出哪一块」。

这个模块用**原生可靠**的方式实现同样的效果：把一页拆成若干页，
每页比上一页多露一点，最后一页露全，页间用转场连接。

    from keynote_kit.build import build_reveal
    build_reveal(deck, slide=4, spec=SPEC, steps=["标题", "第一块", "第二块", "全貌"])

得到的�� 4 页 + 4 个转场，播放时看起来就是「一段段长出来」。
"""

from __future__ import annotations

import copy

from .animate import set_transition
from .page import apply_page


def build_reveal(deck, slide: int, spec: dict, steps: list[str] | None = None,
                 transition: str = "object push", duration: float = 0.5,
                 delay: float = 0.0, keep_original: bool = True) -> dict:
    """把一页拆成一组「逐步揭示」的页。

    spec      完整页面的 spec
    steps     每一步露出的元素 id 列表（累积）。默认按 spec 里的元素顺序，
              一步一个元素；给 "groups": [[...ids], [...]] 可自定义分组。
    keep_original 保留原页（作为「全貌」对照）。False 则原页被替换。
    """
    elements = spec.get("elements", [])
    ids = [el.get("id") for el in elements]
    if not ids:
        raise ValueError("spec 里没有元素")

    if steps is None:
        groups = [[i] for i in ids]
    elif steps and isinstance(steps[0], list):
        groups = [list(g) for g in steps]
    else:
        groups = [[s] for s in steps]

    # 每一步累计露出的元素
    revealed: list[list[str]] = []
    acc: list[str] = []
    for g in groups:
        for gid in g:
            if gid not in acc:
                acc.append(gid)
        revealed.append(list(acc))

    unknown = [g for g in acc if g not in ids]
    if unknown:
        raise ValueError(f"spec 里没有这些元素 id：{unknown}")

    start = slide
    made = []
    for step_i, show in enumerate(revealed):
        page_spec = copy.deepcopy(spec)
        page_spec["elements"] = [copy.deepcopy(el) for el in elements
                                 if el.get("id") in show]
        page_spec.pop("transition", None)
        target = start + step_i
        while deck.slide_count() < target:
            deck.add_slide("空白")
        apply_page(deck, target, page_spec, mode="replace")
        set_transition(deck.doc, target, transition, duration, delay)
        made.append(target)

    # 原页：如果保留，放到最后作为「全貌」；否则直接删掉
    if keep_original:
        last = made[-1] + 1
        while deck.slide_count() < last:
            deck.add_slide("空白")
        apply_page(deck, last, spec, mode="replace")
        set_transition(deck.doc, last, transition, duration, delay)
        made.append(last)
    else:
        # 把原页内容搬到最后一页，再删掉原页
        last = made[-1]
        apply_page(deck, last, spec, mode="replace")
        try:
            deck.remove_slide(start)
            made = [m - 1 for m in made]
        except Exception:  # noqa: BLE001
            pass

    return {"from_slide": start, "slides": made, "steps": len(revealed),
            "transition": transition, "revealed": revealed}


def build_bullets(deck, slide: int, spec: dict, bullet_element: str,
                  transition: str = "object push", duration: float = 0.4,
                  delay: float = 0.0, keep_original: bool = False) -> dict:
    """最常见的用法：一张大标题 + 一组要点，逐条出现。

    生成 N+1 页：第 1 页只有标题，之后每页多一条要点。
    spec 里的 bullet_element 可以是 rich（多段）或 text（按 \n 分行）。
    """
    elements = spec.get("elements", [])
    target = next((el for el in elements if el.get("id") == bullet_element), None)
    if target is None:
        raise ValueError(f"spec 里没有元素 {bullet_element}")

    # 拆出要点行
    lines: list[str] = []
    if target.get("type") == "rich":
        for para in target.get("paragraphs", []):
            text = "".join(r.get("text", "") for r in para.get("runs", []))
            if text.strip():
                lines.append(text)
    else:
        lines = [ln for ln in str(target.get("text", "")).split("\n") if ln.strip()]
    if not lines:
        raise ValueError(f"元素 {bullet_element} 里没有可拆分的文字")

    def with_bullets(n: int) -> dict:
        """复制 spec，并把要点元素改成前 n 条。"""
        page_spec = copy.deepcopy(spec)
        page_spec.pop("transition", None)
        out = []
        for el in page_spec["elements"]:
            el = copy.deepcopy(el)
            if el.get("id") == bullet_element:
                if n <= 0:
                    continue                      # 第一页完全不显示要点
                if el.get("type") == "rich":
                    kept, cnt = [], 0
                    for para in el.get("paragraphs", []):
                        text = "".join(r.get("text", "") for r in para.get("runs", []))
                        if text.strip():
                            if cnt < n:
                                kept.append(para)
                            cnt += 1
                        else:
                            kept.append(para)
                    el["paragraphs"] = kept
                else:
                    el["text"] = "\n".join(lines[:n])
            out.append(el)
        page_spec["elements"] = out
        return page_spec

    start = slide
    made = []
    for n in range(len(lines) + 1):
        target_page = start + n
        while deck.slide_count() < target_page:
            deck.add_slide("空白")
        apply_page(deck, target_page, with_bullets(n), mode="replace")
        set_transition(deck.doc, target_page, transition, duration, delay)
        made.append(target_page)

    if keep_original:
        last = made[-1] + 1
        while deck.slide_count() < last:
            deck.add_slide("空白")
        apply_page(deck, last, spec, mode="replace")
        set_transition(deck.doc, last, transition, duration, delay)
        made.append(last)

    return {"from_slide": start, "slides": made, "bullets": len(lines),
            "transition": transition}
