#!/usr/bin/env python3
"""逐页比对两组图（PNG），给出还原度。

    python tools/compare.py /tmp/ref /tmp/out
    python tools/compare.py /tmp/ref /tmp/out --min 90

相似度 = 100 - 逐像素平均绝对差 / 255。100 表示完全一致。

退出码：有页面低于 --min 时返回 1，方便接进 CI。
"""

from __future__ import annotations

import argparse
import os
import re
import sys


def load_dir(path: str) -> dict[int, str]:
    """目录里的 PNG 按文件名里的数字编号排序。"""
    out: dict[int, str] = {}
    for name in sorted(os.listdir(path)):
        if not name.lower().endswith(".png"):
            continue
        m = re.search(r"(\d+)", name)
        if not m:
            continue
        num = int(m.group(1))
        out.setdefault(num, os.path.join(path, name))
    return out


def similarity(a_path: str, b_path: str) -> float:
    from PIL import Image, ImageChops, ImageStat
    a = Image.open(a_path).convert("RGB")
    b = Image.open(b_path).convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size)
    diff = ImageChops.difference(a, b)
    mean = ImageStat.Stat(diff).mean[0]
    return round(100 * (1 - mean / 255), 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ref", help="参考图目录")
    ap.add_argument("out", help="候选图目录")
    ap.add_argument("--min", type=float, default=0.0, help="低于此相似度算失败")
    ap.add_argument("--top", type=int, default=5, help="列出最差的几页")
    args = ap.parse_args()

    ref, out = load_dir(args.ref), load_dir(args.out)
    common = sorted(set(ref) & set(out))
    if not common:
        print("两目录没有可比的页面")
        return 1

    rows = [(n, similarity(ref[n], out[n])) for n in common]
    vals = [v for _, v in rows]
    print(f"共比对 {len(rows)} 页")
    print(f"平均 {sum(vals)/len(vals):.1f}%  中位 {sorted(vals)[len(vals)//2]:.1f}%  "
          f"最低 {min(vals)}%  最高 {max(vals)}%")
    worst = sorted(rows, key=lambda r: r[1])[:args.top]
    print(f"最差的 {len(worst)} 页: " + ", ".join(f"P{n} {v}%" for n, v in worst))
    missing = sorted(set(ref) ^ set(out))
    if missing:
        print(f"只有一边有的页: {missing}")

    bad = [r for r in rows if r[1] < args.min]
    if bad:
        print(f"\n低于 {args.min}% 的页: " +
              ", ".join(f"P{n}({v}%)" for n, v in bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
