# Using keynote-kit with MCP

`keynote-kit` is a library and CLI, not an MCP server. That is deliberate: it lets you call Keynote
from any runtime (Python, shell, a workflow engine, an agent) without a protocol hop. If you do want
MCP, the two options below are both one file of code.

## Option A — call keynote-kit from an MCP server you control

Given an existing MCP server (Node or Python), expose keynote-kit as a tool:

```python
# inside your MCP server
import json
from keynote_kit import Deck
from keynote_kit.deck import _rgb  # not needed for the simple path

@server.tool()
def keynote_add_text(doc: str, slide: int, text: str, x: int, y: int,
                     w: int, h: int, size: int = 32, color: str = "#1F2329") -> str:
    d = Deck(doc)
    d.add_text(slide, text, x, y, w, h, size=size, color=color)
    return json.dumps(d.verify(slide), ensure_ascii=False)
```

The important part is `verify()`: MCP clients cannot see the slide, so a silent failure is
indistinguishable from success unless the tool reports element counts.

## Option B — wrap the CLI

The CLI emits JSON on stdout and a non-zero exit code on failure, which is enough for most
tool-calling harnesses:

```bash
python -m keynote_kit.cli text --doc "未命名" --slide 2 --text "标题" \
    --x 150 --y 300 --w 1500 --h 120 --size 84 --color "#2B2420"
# {"index": 0, "kind": "text"}
```

## Co-existing with iwork-mcp

Both can drive the same document; they use the same underlying `osascript` bridge and take turns
safely as long as calls are sequential. A pragmatic split:

| Task | Use |
|---|---|
| Listing documents, themes, master layouts | iwork-mcp (`keynote_list_*`) |
| Slide transitions, presenter notes | iwork-mcp |
| Text boxes, shapes, tables with geometry | **keynote-kit** |
| Charts, diagrams | **keynote-kit** |
| Export PNG sequence | either (keynote-kit uses the working JXA path) |

Two rules when mixing:

1. **Never** run `make new movie` (iwork-mcp will not do this either) — it wedges Keynote.
2. After any iwork-mcp write, re-read the page with `keynote-kit` `verify()` — several of its tools
   return success without inserting anything (see `docs/capabilities.md`, rows 24–25).

## Driver scripts in `scripts/`

`scripts/mcp_client.mjs` and `scripts/mcp_batch.mjs` are minimal stdio MCP clients. They exist
because most MCP servers assume a chat client; these let you drive one from a shell:

```bash
node scripts/mcp_client.mjs list
node scripts/mcp_client.mjs describe keynote_add_table_to_slide
node scripts/mcp_client.mjs call keynote_add_slide '{"documentName":"未命名","masterSlideName":"空白"}'
node scripts/mcp_batch.mjs plan.json     # many calls in one server process
```

Point `SERVER` at your server's entry file before use.
