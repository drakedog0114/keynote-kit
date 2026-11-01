# MCP 服务参考

[English](mcp-server.md) · **简体中文**

`keynote-kit` 自带**完整**的 Keynote MCP 服务。你**不需要**再装 iwork-mcp、AppleScript 封装或任何
其他 MCP —— 下面每个能力都在本仓库里实现。

```bash
python -m keynote_kit.mcp_server      # stdio 传输
```

* 传输方式：stdio，逐行 JSON-RPC 2.0
* 依赖：`Pillow`（信息图）、`matplotlib`（图表），两者都是可选；不装只是少了对应两个工具
* 工具数：**41**

## 客户端配置

### Claude Desktop

```json
{
  "mcpServers": {
    "keynote-kit": {
      "command": "python3",
      "args": ["-m", "keynote_kit.mcp_server"]
    }
  }
}
```

如果装在虚拟环境里，把 `command` 指向那个解释器：

```json
{
  "mcpServers": {
    "keynote-kit": {
      "command": "/Users/you/.venv/bin/python",
      "args": ["-m", "keynote_kit.mcp_server"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add keynote-kit -- python3 -m keynote_kit.mcp_server
```

### Codex / Cursor / 其他 MCP 客户端

结构一致：`command` 填 Python 解释器，`args` 填 `["-m", "keynote_kit.mcp_server"]`。

## 工具清单

### 文档
| 工具 | 用途 |
|---|---|
| `kk_list_documents` | 列出已打开文稿 |
| `kk_create_document` | 新建（`theme` / `width` / `height`） |
| `kk_open_document` | 按路径打开 `.key` |
| `kk_close_document` | 关闭（可选保存） |
| `kk_save_document` | 另存为 |
| `kk_export` | 导出逐页 PNG 或 PowerPoint |
| `kk_export_pdf` | 可靠的 PDF（PNG 合成） |
| `kk_list_themes` / `kk_set_theme` | 主题列举与切换 |
| `kk_list_layouts` | 文稿的母版版式 |

### 页面
| 工具 | 用途 |
|---|---|
| `kk_add_slide` | 用任意母版追加一页 |
| `kk_list_slides` | 页码、标题、跳过状态 |
| `kk_get_slide` | 标题 / 正文 / 备注 / 元素数 |
| `kk_inspect_slide` | 列出所有元素的类型、坐标、尺寸 |
| `kk_delete_slide` / `kk_duplicate_slide` / `kk_move_slide` | 页面管理 |
| `kk_skip_slide` | 放映时跳过 |
| `kk_set_layout` | 更换母版版式 |
| `kk_set_title` / `kk_set_body` | 占位符文本 |
| `kk_set_notes` | 演讲者备注 |

### 内容
| 工具 | 用途 |
|---|---|
| `kk_add_text` | 真文本框，坐标 + 字号 + 颜色 + 字体 |
| `kk_add_shape` | 主题填充形状 + 标签 |
| `kk_add_image` | 插入图片（支持 alpha） |
| `kk_set_background` | 整页背景图 |
| `kk_add_line` | 直线 |
| `kk_position_item` | 移动 / 缩放形状、图片、文本 |
| `kk_align_items` / `kk_distribute_items` | 排版辅助 |
| `kk_get_shape_info` / `kk_format_shape` | 读 / 改形状文字样式 |

### 表格
| 工具 | 用途 |
|---|---|
| `kk_add_table` | 原生表格（含数据与几何） |
| `kk_read_table` | 读回单元格 |
| `kk_write_table` | 写入单元格 |

> 单元格**样式** Keynote 完全没有开放（`cell` 只有 `value` / `formula`），所以没有
> `format_table`。需要彩色表格请用图表或图片。

### 图表与信息图
| 工具 | 用途 |
|---|---|
| `kk_add_chart` | 柱状 / 折线 / 环形，matplotlib 渲染 |
| `kk_add_diagram` | 泳道图 / 层级图 / 集成图 |

### 放映与自检
| 工具 | 用途 |
|---|---|
| `kk_start_slideshow` / `kk_stop_slideshow` | 放映控制 |
| `kk_verify` | 读回页面并校验元素数 |
| `kk_server_info` | 版本与能力概览 |

## 为什么需要 `kk_verify`

Keynote 会静默忽略某些写入（见 [踩坑手册](gotchas.zh-CN.md)）。MCP 客户端看不到幻灯片，
所以一个只返回 `{"ok": true}` 却不校验的工具比没有更危险。任何写操作之后，
只要版面重要，就调一次 `kk_inspect_slide` 或 `kk_verify`。

## 从 iwork-mcp 迁移

| iwork-mcp | keynote-kit |
|---|---|
| `keynote_create_presentation` | `kk_create_document` |
| `keynote_add_slide` | `kk_add_slide` |
| `keynote_add_image_to_slide` | `kk_add_image` |
| `keynote_add_table_to_slide` | `kk_add_table` |
| `keynote_set_slide_title/body` | `kk_set_title` / `kk_set_body` |
| `keynote_export_presentation` | `kk_export` / `kk_export_pdf` |
| `keynote_format_shape` | `kk_format_shape`（这里是好的） |
| `keynote_clean_up_slide` / `super_resolution` / `remove_background` | 无法脚本化，只能在 Creator Studio 界面里用 |

其余都有一一对应，除了这三个 AI 功能，iwork-mcp 没有 keynote-kit 覆盖不了的能力。
