#!/usr/bin/env python3
"""检查文档的中英配对，防止某一版悄悄落后。

    python tools/check_docs.py

检查两件事：

1. **配对**：`docs/` 下每个文档都要有 `.zh-CN.md` 对应版本，反之亦然；
   `README.md` 与 `README.zh-CN.md` 必须同时存在。
2. **章节对齐**：两个 README 的 `##` 级标题数量必须一致——
   中文版最容易少写新章节（比如漏掉「视觉打磨」「客户换稿」）。

退出码：有问题返回 1。
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")


def headings(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return [m.group(1).strip() for m in re.finditer(r"^##\s+(.+)$", text, re.M)]


# README 的章节对照表。中文版最容易少写新章节，所以这里显式列出对应关系，
# 检查时能直接报出「中文版缺哪一节」，而不是只报一个数量差。
README_SECTIONS = [
    ("Why this exists", "为什么做这个"),
    ("Features", "能力一览"),
    ("Requirements", "环境要求"),
    ("Install", "安装"),
    ("Quick start", "快速开始"),
    ("Gallery", "效果"),
    ("Building a page from a spec", "声明式建页（首选）"),
    ("Visual polish", "视觉打磨"),
    ("Re-using a deck for another client", "客户换稿（把 A 客户的方案变成 B 客户）"),
    ("Shrinking an existing deck", "压缩已有文稿"),
    ("MCP server", "MCP 服务"),
    ("Documentation", "文档"),
    ("Project layout", "项目结构"),
    ("Known limitations", "已知限制"),
    ("Roadmap", "路线图"),
    ("Contributing", "贡献"),
    ("License", "许可"),
]


def main() -> int:
    problems: list[str] = []

    # 1) 配对
    names = sorted(f for f in os.listdir(DOCS) if f.endswith(".md"))
    for name in names:
        if name.endswith(".zh-CN.md"):
            en = name[:-len(".zh-CN.md")] + ".md"
            if not os.path.exists(os.path.join(DOCS, en)):
                problems.append(f"docs/{name} 缺英文版（应为 docs/{en}）")
        else:
            zh = name[:-len(".md")] + ".zh-CN.md"
            if not os.path.exists(os.path.join(DOCS, zh)):
                problems.append(f"docs/{name} 缺中文版（应为 docs/{zh}）")

    # 2) README 都在
    readmes = {}
    for lang in ("README.md", "README.zh-CN.md"):
        path = os.path.join(ROOT, lang)
        if not os.path.exists(path):
            problems.append(f"缺少 {lang}")
        else:
            readmes[lang] = headings(path)

    # 3) README 章节对齐（按对照表逐节查）
    if len(readmes) == 2:
        en, zh = readmes["README.md"], readmes["README.zh-CN.md"]
        for en_name, zh_name in README_SECTIONS:
            if en_name not in en:
                problems.append(f"英文 README 缺章节「{en_name}」")
            if zh_name not in zh:
                problems.append(f"中文 README 缺章节「{zh_name}」（对应英文「{en_name}」）")
        extra_zh = [h for h in zh if h not in [z for _, z in README_SECTIONS]]
        if extra_zh:
            problems.append(f"中文 README 有对照表之外的章节，需人工确认：{extra_zh}")

    if problems:
        print("❌ 文档检查未通过：")
        for p in problems:
            print("   -", p)
        return 1

    print(f"✅ 文档配对完整（{len(names)} 个文件），README 章节对齐"
          f"（{len(readmes.get('README.md', []))} 个）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
