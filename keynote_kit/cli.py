"""命令行入口：让任何语言 / 任何工具用 shell 调用 Keynote。

    python -m keynote_kit.cli new --theme 乳色纸
    python -m keynote_kit.cli slide --doc 未命名 --master 空白
    python -m keynote_kit.cli text  --doc 未命名 --slide 2 --text "标题" \
        --x 150 --y 300 --w 1500 --h 120 --size 84 --color "#2B2420"
    python -m keynote_kit.cli export --doc 未命名 --fmt images --out ./out
"""

from __future__ import annotations

import argparse
import json
import sys

from .deck import Deck


def _deck(name: str) -> Deck:
    return Deck(name)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="keynote-kit", description="Keynote 自动化命令行")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="新建演示文稿")
    n.add_argument("--theme", default="白色")
    n.add_argument("--width", type=int, default=1920)
    n.add_argument("--height", type=int, default=1080)

    s = sub.add_parser("slide", help="追加一页")
    s.add_argument("--doc", required=True)
    s.add_argument("--master", default="空白")

    t = sub.add_parser("text", help="插入文本框")
    t.add_argument("--doc", required=True)
    t.add_argument("--slide", type=int, required=True)
    t.add_argument("--text", required=True)
    for k in ("x", "y", "w", "h"):
        t.add_argument(f"--{k}", type=float, required=True)
    t.add_argument("--size", type=float)
    t.add_argument("--color")
    t.add_argument("--font")

    sh = sub.add_parser("shape", help="插入形状")
    sh.add_argument("--doc", required=True)
    sh.add_argument("--slide", type=int, required=True)
    sh.add_argument("--text", default="")
    for k in ("x", "y", "w", "h"):
        sh.add_argument(f"--{k}", type=float, required=True)
    sh.add_argument("--size", type=float)
    sh.add_argument("--color")

    im = sub.add_parser("image", help="插入图片 / 背景图")
    im.add_argument("--doc", required=True)
    im.add_argument("--slide", type=int, required=True)
    im.add_argument("--path", required=True)
    im.add_argument("--x", type=float, default=0)
    im.add_argument("--y", type=float, default=0)
    im.add_argument("--w", type=float)
    im.add_argument("--h", type=float)

    tb = sub.add_parser("table", help="插入原生表格")
    tb.add_argument("--doc", required=True)
    tb.add_argument("--slide", type=int, required=True)
    tb.add_argument("--data", required=True, help="二维数组的 JSON 字符串")
    for k in ("x", "y", "w", "h"):
        tb.add_argument(f"--{k}", type=float, required=True)

    v = sub.add_parser("verify", help="读回页面元素并校验数量")
    v.add_argument("--doc", required=True)
    v.add_argument("--slide", type=int, required=True)
    v.add_argument("--expect", type=int)

    e = sub.add_parser("export", help="导出")
    e.add_argument("--doc", required=True)
    e.add_argument("--fmt", default="images", choices=["images", "PowerPoint", "PDF"])
    e.add_argument("--out", required=True)

    sv = sub.add_parser("save", help="保存 .key")
    sv.add_argument("--doc", required=True)
    sv.add_argument("--out", required=True)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "new":
        d = Deck.create(theme=args.theme, width=args.width, height=args.height)
        print(json.dumps({"doc": d.name}, ensure_ascii=False))
        return 0

    d = _deck(args.doc)

    if args.cmd == "slide":
        print(json.dumps({"slide": d.add_slide(args.master)}, ensure_ascii=False))
    elif args.cmd == "text":
        print(json.dumps(d.add_text(args.slide, args.text, args.x, args.y, args.w, args.h,
                                    size=args.size, color=args.color, font=args.font),
                         ensure_ascii=False))
    elif args.cmd == "shape":
        print(json.dumps(d.add_shape(args.slide, args.text, args.x, args.y, args.w, args.h,
                                     size=args.size, color=args.color), ensure_ascii=False))
    elif args.cmd == "image":
        print(json.dumps(d.add_image(args.slide, args.path, args.x, args.y, args.w, args.h),
                         ensure_ascii=False))
    elif args.cmd == "table":
        data = json.loads(args.data)
        print(json.dumps(d.add_table(args.slide, data, args.x, args.y, args.w, args.h),
                         ensure_ascii=False))
    elif args.cmd == "verify":
        print(json.dumps(d.verify(args.slide, args.expect), ensure_ascii=False))
    elif args.cmd == "export":
        print(json.dumps({"exported": d.export(args.out, args.fmt)}, ensure_ascii=False))
    elif args.cmd == "save":
        print(json.dumps({"saved": d.save(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
