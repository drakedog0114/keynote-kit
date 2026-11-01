#!/usr/bin/env python3
"""能力探测：新建一份临时文档，逐项验证 Keynote 脚本能力并打印结果表。

    python tools/probe_capabilities.py

产出的表格可以直接贴进 docs/capabilities.md。所有操作都在临时文档里完成，
结束时关闭且不保存，不会影响你正在编辑的文稿。
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from keynote_kit import Deck
from keynote_kit.runner import applescript, jxa

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, fn):
    try:
        detail = fn() or ""
        RESULTS.append((name, True, str(detail)[:70]))
    except Exception as exc:  # noqa: BLE001
        RESULTS.append((name, False, f"{type(exc).__name__}: {exc}"[:70]))


def main() -> int:
    deck = Deck.create(theme="白色")
    print(f"探测文档：{deck.name}\n")
    try:
        check("创建文档", lambda: deck.name)

        slide = deck.add_slide("空白")
        check("追加页面", lambda: f"slide={slide}")

        check("文本框 + 坐标", lambda: deck.add_text(slide, "probe", 120, 200, 600, 80,
                                                size=40, color="#1F2329"))
        check("形状 + 坐标", lambda: deck.add_shape(slide, "chip", 120, 400, 240, 90))
        check("线条", lambda: deck.add_line(slide, 100, 600, 800, 600))
        check("表格", lambda: deck.add_table(slide, [["a", "b"], ["1", "2"]], 120, 700, 700, 160))
        check("读回元素", lambda: f"count={deck.verify(slide)['count']}")

        check("插入图片", lambda: deck.add_image(slide, _png(), 900, 200, 300, 300))
        check("图片不存在应报错", lambda: _expect_error(
            lambda: deck.add_image(slide, "/tmp/does-not-exist.png")))

        check("导出 PNG 序列", lambda: deck.export("out/probe-images", "images"))
        check("保存 .key", lambda: deck.save("out/probe.key"))
        check("导出 PPTX", lambda: deck.export("out/probe.pptx", "PowerPoint"))
        check("导出 PDF（预期失败）", lambda: deck.export("out/probe.pdf", "PDF"))
    finally:
        deck.close()

    width = max(len(name) for name, _, _ in RESULTS) + 2
    print(f"{'能力'.ljust(width)} 结果   详情")
    print("-" * (width + 40))
    for name, ok, detail in RESULTS:
        print(f"{name.ljust(width)} {'✅' if ok else '❌'}    {detail}")
    failed = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} 通过")
    return 0


def _png() -> str:
    from pathlib import Path
    from PIL import Image

    Path("out").mkdir(exist_ok=True)
    p = "out/probe.png"
    Image.new("RGB", (600, 600), (31, 58, 95)).save(p)
    return p


def _expect_error(fn):
    try:
        fn()
    except Exception:  # noqa: BLE001
        return "raised as expected"
    raise AssertionError("预期抛异常但没有")


if __name__ == "__main__":
    sys.exit(main())
