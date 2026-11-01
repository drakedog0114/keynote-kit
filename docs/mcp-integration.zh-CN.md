# 把 keynote-kit 接进 MCP

keynote-kit 是**库和命令行**，不是 MCP 服务器。这是有意为之：它让你能从任何运行时
（Python、shell、工作流引擎、agent）直接驱动 Keynote，不必多走一层协议。
但如果你确实要 MCP，下面两种方式都只需要几行代码。

## 方案 A —— 在你自己的 MCP 服务器里调用 keynote-kit

给定一个现成的 MCP 服务器（Node 或 Python），把 keynote-kit 暴露成一个工具：

```python
# 在你的 MCP 服务器里
import json
from keynote_kit import Deck

@server.tool()
def keynote_add_text(doc: str, slide: int, text: str, x: int, y: int,
                     w: int, h: int, size: int = 32, color: str = "#1F2329") -> str:
    d = Deck(doc)
    d.add_text(slide, text, x, y, w, h, size=size, color=color)
    return json.dumps(d.verify(slide), ensure_ascii=False)
```

关键在 `verify()`：MCP 客户端**看不见**幻灯片，所以静默失败和成功长得一模一样，
除非工具把元素数量报出来。

## 方案 B —— 包一层命令行

命令行输出 JSON，失败时返回非零退出码，对绝大多数调用工具的框架已经够用：

```bash
python -m keynote_kit.cli text --doc "未命名" --slide 2 --text "标题" \
    --x 150 --y 300 --w 1500 --h 120 --size 84 --color "#2B2420"
# {"index": 0, "kind": "text"}
```

## 与 iwork-mcp 共存

两者可以驱动同一个文稿：它们走的是同一套 `osascript` 桥，只要**串行调用**就不会打架。
一个实用的分工：

| 任务 | 用谁 |
|---|---|
| 列文稿、主题、母版 | iwork-mcp（`keynote_list_*`） |
| 幻灯片转场、演讲者备注 | iwork-mcp |
| 带几何的文本框、形状、表格 | **keynote-kit** |
| 图表、信息图 | **keynote-kit** |
| 导出 PNG 序列 | 都行（keynote-kit 走的是能用的 JXA 路径） |

混用时两条规矩：

1. **永远不要**跑 `make new movie`（iwork-mcp 也不会跑）——它会把 Keynote 卡死。
2. iwork-mcp 写完之后，用 keynote-kit 的 `verify()` **重新读一遍**页面——
   它的好几个工具会返回「成功」但其实什么都没插进去
   （见 `docs/capabilities.zh-CN.md` 第 24–25 行）。

## `scripts/` 里的驱动脚本

`scripts/mcp_client.mjs` 和 `scripts/mcp_batch.mjs` 是极简的 stdio MCP 客户端。
之所以写它们，是因为大多数 MCP 服务器都假设自己有聊天客户端，
这两个让你能从 shell 里驱动一个：

```bash
node scripts/mcp_client.mjs list
node scripts/mcp_client.mjs describe keynote_add_table_to_slide
node scripts/mcp_client.mjs call keynote_add_slide '{"documentName":"未命名","masterSlideName":"空白"}'
node scripts/mcp_batch.mjs plan.json     # 在同一个服务器进程里跑一批调用
```

用之前把 `SERVER` 指向你的服务器入口文件。
