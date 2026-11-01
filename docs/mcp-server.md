# MCP server reference

**English** · [简体中文](mcp-server.zh-CN.md)

`keynote-kit` ships a **complete** MCP server for Keynote. You do **not** need iwork-mcp,
AppleScript wrappers, or any other MCP: every capability below is implemented in this repo.

```bash
python -m keynote_kit.mcp_server      # stdio transport
```

* Transport: stdio, newline-delimited JSON-RPC 2.0
* Dependencies: none beyond the ones `keynote-kit` already needs (`Pillow` for diagrams,
  `matplotlib` for charts; both optional if you skip those tools)
* Tools: **41**

## Client configuration

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

If you installed into a virtualenv, point `command` at that interpreter:

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

### Codex / Cursor / any MCP client

Same shape: `command` = your Python interpreter, `args` = `["-m", "keynote_kit.mcp_server"]`.

## Tool catalogue

### Documents
| Tool | Purpose |
|---|---|
| `kk_list_documents` | list open documents |
| `kk_create_document` | new deck (`theme`, `width`, `height`) |
| `kk_open_document` | open a `.key` by path |
| `kk_close_document` | close (optionally saving) |
| `kk_save_document` | Save As |
| `kk_export` | per-slide PNG or PowerPoint |
| `kk_export_pdf` | reliable PDF (PNG composition) |
| `kk_list_themes` / `kk_set_theme` | theme listing and switching |
| `kk_list_layouts` | master layouts of a document |

### Pages
| Tool | Purpose |
|---|---|
| `kk_add_slide` | append a slide with any master |
| `kk_list_slides` | page numbers, titles, skipped flags |
| `kk_get_slide` | title / body / notes / item count |
| `kk_inspect_slide` | every element with type, position, size |
| `kk_delete_slide` / `kk_duplicate_slide` / `kk_move_slide` | page management |
| `kk_skip_slide` | exclude a page from the show |
| `kk_set_layout` | change the master layout |
| `kk_set_title` / `kk_set_body` | placeholder text |
| `kk_set_notes` | speaker notes |

### Content
| Tool | Purpose |
|---|---|
| `kk_add_text` | real text box, position + size + colour + font |
| `kk_add_shape` | theme-filled shape with a label |
| `kk_add_image` | image (alpha supported) |
| `kk_set_background` | full-page background image |
| `kk_add_line` | straight connector |
| `kk_position_item` | move / resize shape, image or text |
| `kk_align_items` / `kk_distribute_items` | layout helpers |
| `kk_get_shape_info` / `kk_format_shape` | read / style shape text |

### Tables
| Tool | Purpose |
|---|---|
| `kk_add_table` | native table with data and geometry |
| `kk_read_table` | read cells back |
| `kk_write_table` | write cells |

> Cell **styling** is not exposed by Keynote at all (`cell` only has `value` / `formula`), so there
> is no `format_table` tool. Use charts or images when you need coloured cells.

### Charts & diagrams
| Tool | Purpose |
|---|---|
| `kk_add_chart` | bar / line / donut rendered with matplotlib |
| `kk_add_diagram` | swimlane / hierarchy / integration layout |

### Show & health
| Tool | Purpose |
|---|---|
| `kk_start_slideshow` / `kk_stop_slideshow` | presentation control |
| `kk_verify` | read a page back and assert element count |
| `kk_server_info` | version + capability summary |

## Why `kk_verify` matters

Keynote silently ignores some writes (see [gotchas.md](gotchas.md)). An MCP client cannot see the
slide, so a tool that returns `{"ok": true}` without checking is worse than useless. After any
write, call `kk_inspect_slide` or `kk_verify` when the layout matters.

## Migrating from iwork-mcp

| iwork-mcp | keynote-kit |
|---|---|
| `keynote_create_presentation` | `kk_create_document` |
| `keynote_add_slide` | `kk_add_slide` |
| `keynote_add_image_to_slide` | `kk_add_image` |
| `keynote_add_table_to_slide` | `kk_add_table` |
| `keynote_set_slide_title/body` | `kk_set_title` / `kk_set_body` |
| `keynote_export_presentation` | `kk_export` / `kk_export_pdf` |
| `keynote_format_shape` | `kk_format_shape` (works here) |
| `keynote_clean_up_slide` / `super_resolution` / `remove_background` | not scriptable — Creator Studio UI only |

Everything else has a direct equivalent; there is no capability left in iwork-mcp that
keynote-kit does not cover, apart from those three AI features.
