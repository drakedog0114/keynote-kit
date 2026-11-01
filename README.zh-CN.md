# keynote-kit

> 用 Python 精确驱动 Apple Keynote：精确排版、原生表格、图表与信息图。

[English](README.md) · **简体中文**

---

## 为什么做这个

Keynote 的脚本接口（AppleScript / JXA）比看上去薄得多。我们对 iwork-mcp 0.8.8 + Keynote Creator
Studio 15.4 做了 25 项能力测试，反复出现三类问题：

| 现象 | 根因 |
|---|---|
| 形状、表格忽略 `x`/`y`，全部堆在 `(0, 0)` | JXA 的 position setter 被静默丢弃 |
| `format_shape` 报 `-1728` | 封装层的文档查找不稳定 |
| 图片路径不存在却返回 `added: true` | 写入后没有校验 |
| `make new image` / `make new table` / `make new movie` 报 `-10000` | 15.x 里这几个动词已损坏 |

`keynote-kit` 绕过了这些问题，并补上了接口层从来没有的能力：**排版控制、带位置的原生表格、
图表渲染、整页信息图**。

## 能力一览

| 模块 | 能力 |
|---|---|
| 文档 | 按主题与自定义画布尺寸创建；接管已打开文档 |
| 页面 | 用任意母版追加（安全追加，不会覆盖相邻页） |
| 文本 | 真正的文本框，坐标 / 字号 / 颜色 / 字体可控 |
| 形状 | 主题填充的形状 + 可设样式标签 |
| 图片 | 支持透明 PNG、大图、整页背景 |
| 表格 | 原生可编辑表格，建表、填充、定位、定尺寸 |
| 图表 | matplotlib 渲染柱状 / 折线 / 环形，透明背景 |
| 信息图 | 泳道图、层级图、双端集成图 |
| 安全 | `verify()` 回读页面，静默失败立刻暴露 |
| 导出 | 逐页 PNG、PowerPoint、PDF、`.key` |

## 环境要求

- macOS 14+，已安装 Keynote（在 macOS 27.0.1 + Keynote Creator Studio 15.4 上验证）
- Python 3.10+
- `Pillow`（图片 / 信息图）、`matplotlib`（图表）
- 终端需被允许控制 Keynote：系统设置 → 隐私与安全性 → 自动化

## 安装

```bash
git clone https://github.com/drakedog0114/keynote-kit.git
cd keynote-kit
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
```

## 快速开始

```python
from keynote_kit import Deck, charts

deck = Deck.create(theme="乳色纸")          # 默认 1920×1080
slide = deck.add_slide("空白")

deck.add_text(slide, "标题文字", 150, 300, 1500, 120,
              size=84, color="#2B2420", font="Songti SC Bold")
deck.add_table(slide, [["业务域", "承接方式"], ["准入", "全定制"]], 150, 600, 1600, 240)
deck.add_image(slide, charts.bar_chart(["准入", "价格"], [18, 26], path="bar.png"), 150, 300, 800, 450)

deck.verify(slide, expect=3)                # 数量不符会抛异常
deck.export("./out/images", "images")
deck.save("./out/deck.key")
```

### 命令行

```bash
python -m keynote_kit.cli new --theme 乳色纸
python -m keynote_kit.cli slide --doc 未命名 --master 空白
python -m keynote_kit.cli text --doc 未命名 --slide 2 --text "标题" \
    --x 150 --y 300 --w 1500 --h 120 --size 84 --color "#2B2420"
python -m keynote_kit.cli export --doc 未命名 --fmt images --out ./out
```

所有子命令输出 JSON，便于 shell 或其他 agent 直接消费。

## 效果

![封面](docs/assets/demo-cover.png)
![卡片](docs/assets/demo-cards.png)
![图表](docs/assets/demo-charts.png)

*以上页面均由 `examples/02_demo_deck.py` 生成。*

## 声明式建页（首选）

`kk_page` 接受一份声明式页面 spec——元素按顺序就是 z 序，页面带背景，
建完还会回读校验（对不上就回滚）：

```python
from keynote_kit import Deck
from keynote_kit.page import apply_page

deck = Deck.create(theme="乳色纸")
slide = deck.add_slide("空白")
apply_page(deck, slide, {
    "background": {"type": "solid", "color": "#F4EBDD"},
    "elements": [
        {"id": "t", "type": "text", "text": "三卡", "box": [150, 110, 1620, 110],
         "style": {"size": 54, "font": "Songti SC Bold"}},
        {"id": "c", "type": "card", "box": [150, 290, 500, 400],
         "style": {"fill": "#FFFFFF", "radius": 26},
         "text": {"title": "整页 Spec", "body": "一页一个 JSON", "valign": "center"}},
        {"id": "ch", "type": "chart", "box": [710, 290, 900, 400],
         "chart": {"kind": "bar", "labels": ["A", "B"], "values": [18, 26]}},
    ],
})
```

元素类型：`text` · `card` · `chart` · `diagram` · `image` · `table`。
`kk_extract_page` 可以把一页读回成 spec。

### 可编辑文字：写进母版占位符

裸文本框继承不了主题的对齐、项目符号和段间距。用带占位符的母版、按 slot 寻址，
文字既保持**可编辑**，又拿到主题的排版：

```python
deck.add_slide("标题与项目符号")          # 带标题 + 正文占位符的母版
apply_page(deck, 1, {"elements": [
    {"type": "text", "slot": "title", "text": "标题", "box": [150, 90, 1620, 100]},
    {"type": "text", "slot": "body", "text": "第一点\n第二点", "box": [150, 260, 760, 420]},
]})
```

slot 页会跳过 `clear`，也跳过背景图（占位符在 z 序最底部，整页图会盖住它们）。
`card` 只用来做纯装饰的色块。

设计、实测与已知限制见 [docs/rfc/0001-declarative-pages.md](docs/rfc/0001-declarative-pages.md)。

## 视觉打磨

Keynote 没有裁剪、autoFit、z-index、超链接这些接口，所以这些要么本地算好，
要么预渲染成 PNG 再插进去。

```python
{"type": "image", "path": "photo.jpg", "box": [60, 160, 700, 350],
 "style": {"radius": 40, "crop": "cover"}}     # 圆角 + 裁剪
{"type": "text", "text": long_copy, "box": [80, 300, 760, 150],
 "style": {"size": 42}}                        # 自动防溢出，默认就是开的
{"type": "rich", "box": [100, 300, 900, 140], "link": "https://example.com",
 "paragraphs": [{"align": "left", "runs": [{"text": "链接", "size": 24}]}]}
```

```python
from keynote_kit.animate import set_transition, set_opacity, bring_to_front
set_transition(doc, slide, "magic move", duration=0.6)
set_opacity(doc, slide, "image", 1, 0.4)
bring_to_front(doc, slide, "image", 1, "/path/to/image.png")
```

`style.fit` 有三种取值：`"auto"`（默认，只在真会出框时才缩）、`True`（强制缩到装得下）、
`False`（不干预）。默认不是 `True`，因为 Keynote 文本框不裁切，很多标题就是**故意**
放在比文字矮的框里，一律缩会把版式毁掉。

### 用「拆页 + 转场」替代构建动画

「逐个出现 / 飞入」**完全没有 API**。可靠的做法是把一页拆成几页，
每页比上一页多露一点，页间用转场连起来：

```python
from keynote_kit.build import build_bullets, build_reveal

build_bullets(deck, slide=4, spec=SPEC, bullet_element="b")   # 标题 + 3 条要点 → 4 页
build_reveal(deck, slide=4, spec=SPEC,
             groups=[["title"], ["title", "chart"], ["title", "chart", "card"]])
```

全程原生 Keynote，不碰 UI 自动化。

## 客户换稿（把 A 客户的方案变成 B 客户）

方案稿反复复用——结构不变，换客户、换数字。**走导入，不要重建。**
实测一份 22 页真实稿（74 个组合形状、122 个自动图形）：

| 路线 | 耗时 | 与源文件的相似度 |
|---|---|---|
| **原生导入** | **4 秒** | **95.4%** |
| spec 重建 | 596 秒 | 89.5%（最低页 49.9%） |

两个维度原生导入都赢。重建会丢掉自动图形的填充色（深色面板变白板）、自由曲线，
以及组合形状的变换。所以真实稿只换**内容**，不动几何。

```bash
# 1) 原生导入（434 MB / 59 页的稿子 13 秒，96.5% 像素还原度，视频全保留）
osascript -e 'tell application "Keynote" to open POSIX file "/path/deck.pptx"'

# 2) 改措辞，格式不动
python tools/replace_text.py "文稿名" --map rules.json --dry-run
python tools/replace_text.py "文稿名" --map rules.json

# 3) 逐页导出，重点看图片多的页
```

`replace_text.py` 会先记录每一段的字号 / 字体 / 颜色，替换后再还原——
直接整体赋值 `object text` 会把 118pt 标题和 66pt 副标题压成同一个字号。
**烤进图片里的品牌名**（截图、流程图）文本替换够不着，只能重做。

完整清单见 [docs/client-swap.zh-CN.md](docs/client-swap.zh-CN.md)。

### 先查字体，再谈还原度

缺字体会给任何一次转换设上限：Keynote **和**参考渲染器都会静默换成替代字体，
而两边的替代字体还不一样——于是像素比对量到的是「两个替代字体之差」，不是设计。

```bash
unzip -o deck.pptx -d /tmp/x
grep -oh 'typeface="[^"]*"' /tmp/x/ppt/slides/*.xml | sort | uniq -c | sort -rn
```

`HarmonyOS Sans SC` 免费且 Apache-2.0 协议（<https://github.com/huawei-fonts/HarmonyOS-Sans>），
压缩包走 Git LFS，要从 `media.githubusercontent.com/media/<owner>/<repo>/<ref>/<path>` 取。

### 审计与比对现有文稿

```bash
python tools/audit_styles.py ~/Desktop/deck.key          # 样式问题体检
python tools/compare.py /tmp/ref /tmp/out --min 90        # 逐页相似度，可接 CI
```

`audit_styles.py` 会找出：多段同号（样式落错对象的特征）、零尺寸元素、空文本框、疑似超框。
`compare.py` 输出平均 / 中位 / 最低相似度，低于 `--min` 时返回非零退出码。

## 压缩已有文稿

Keynote 没有"减少文件大小"的接口。`tools/compress_deck.py` 重写包内媒体（视频重编码 + 图片重采样），
并通过"两份文稿逐页渲染比对"来验收。

```bash
python tools/compress_deck.py 原稿.key -o 压缩版.key --verify 原稿.key
# 逐页比对 59 页，差异 0 页     （真实 59 页稿：450 MB → 95 MB）
```

先读坑：见 [docs/compression.zh-CN.md](docs/compression.zh-CN.md)。

## MCP 服务

`keynote-kit` 自带**完整**的 MCP 服务，**不需要再装 iwork-mcp 或任何其他 MCP**。53 个工具覆盖
文档、页面、文本、形状、图片、表格、图表、信息图、版式、备注、导出与放映控制。

```bash
python -m keynote_kit.mcp_server
```

```json
{
  "mcpServers": {
    "keynote-kit": { "command": "python3", "args": ["-m", "keynote_kit.mcp_server"] }
  }
}
```

完整工具清单与各客户端配置：[docs/mcp-server.md](docs/mcp-server.md)。

## 文档

| 文档 | 中文 | English | 内容 |
|---|---|---|---|
| 能力矩阵 | [中文](docs/capabilities.zh-CN.md) | [EN](docs/capabilities.md) | 29 项：keynote-kit vs iwork-mcp vs 原生脚本 |
| 踩坑手册 | [中文](docs/gotchas.zh-CN.md) | [EN](docs/gotchas.md) | 17 个 Keynote 脚本缺陷与解法 |
| MCP 服务 | [中文](docs/mcp-server.zh-CN.md) | [EN](docs/mcp-server.md) | 53 个工具、客户端配置、迁移对照 |
| 信息图 | [中文](docs/diagrams.zh-CN.md) | [EN](docs/diagrams.md) | 泳道图 / 层级图 / 集成图的数据结构 |
| **文稿压缩** | [中文](docs/compression.zh-CN.md) | [EN](docs/compression.md) | 安全压缩 `.key`，以及四个必踩的坑 |
| **视觉打磨** | [中文](docs/visuals.zh-CN.md) | [EN](docs/visuals.md) | 圆角裁剪、文本自适应、z 序、转场、超链接 |
| **客户换稿** | [中文](docs/client-swap.zh-CN.md) | [EN](docs/client-swap.md) | 导入 → 改写 → 换品牌 → 验收的完整清单 |
| **质量指南** | [中文](docs/quality-guide.zh-CN.md) | [EN](docs/quality-guide.md) | 什么算「做得好」，以及怎么检查 |
| MCP 共存 | [中文](docs/mcp-integration.zh-CN.md) | [EN](docs/mcp-integration.md) | 与其他 MCP 服务器并用 |
| 示例 | — | [examples/](examples/) | 可直接运行的示例 |

## 已知限制

以下能力 Keynote 完全没有开放接口，只能靠 UI 自动化或等原生 MCP：

- 动画 / 构建效果（用「拆页 + 转场」代替，见上）
- 图片裁剪与遮罩（我们本地预渲染成 PNG 绕过去）
- 单页背景填充与母版编辑（`slide layout` 只读）
- 表格填充色（只能改单元格文字颜色）

## 项目结构

```
keynote_kit/
  runner.py      JXA + AppleScript 运行器，统一错误处理
  deck.py        Deck / 页面 / 元素 / 几何 / 样式 / 导出
  charts.py      matplotlib 图表（透明底、支持中文）
  diagrams.py    泳道图、层级图、集成图渲染器
  page.py        声明式整页 spec 的编译与校验
  imaging.py     图片圆角 / 椭圆 / 裁剪预渲染，文本度量
  animate.py     转场、透明度、旋转、z 序
  build.py       拆页揭示（替代构建动画）
  cli.py         输出 JSON 的命令行
examples/        可直接运行的示例
tools/           能力探测、文档体检、逐页比对、MCP 客户端
docs/            能力矩阵、踩坑手册、质量指南、MCP 集成说明
tests/           冒烟测试（需要 Keynote）
```

## 路线图

设计提案见 [docs/rfc/](docs/rfc/)。RFC 0001 引入了声明式页面 spec
（`kk_page`，0.2.0 发布）。仍待做：把工具面收敛到 ~12 个、
做一个 `clients/*.json` 模板方便重复换客户、以及为「正文就是一张图」的页面提供原生重建。

## 贡献

欢迎提 issue 和 PR——见 [CONTRIBUTING.md](CONTRIBUTING.md)。
如果你发现了新的 Keynote 脚本坑，请连同最小复现案例加进
[docs/gotchas.zh-CN.md](docs/gotchas.zh-CN.md)。

## 许可

[MIT](LICENSE)
