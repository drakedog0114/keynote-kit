"""keynote-kit MCP server（stdio）。

自带全部 Keynote 能力，不依赖 iwork-mcp：

    python -m keynote_kit.mcp_server

客户端配置（Claude Desktop / Claude Code / Codex / Cursor 等）：

    {
      "mcpServers": {
        "keynote-kit": {
          "command": "python3",
          "args": ["-m", "keynote_kit.mcp_server"]
        }
      }
    }

协议：MCP stdio，逐行 JSON-RPC 2.0，无第三方依赖。
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable

from . import __version__
from . import charts, diagrams, ops
from . import page as page_mod
from .deck import Deck
from .runner import KeynoteError

TOOLS: dict[str, dict] = {}


def tool(name: str, description: str, schema: dict | None = None):
    def wrap(fn: Callable[[dict], Any]):
        TOOLS[name] = {
            "name": name,
            "description": description,
            "inputSchema": schema or {"type": "object", "properties": {}, "additionalProperties": False},
            "handler": fn,
        }
        return fn
    return wrap


def S(**props) -> dict:
    required = [k for k, v in props.items() if v.pop("_required", False)] if props else []
    return {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}


def P(type_: str, desc: str, required: bool = False, **extra):
    p = {"type": type_, "description": desc}
    if required:
        p["_required"] = True
    p.update(extra)
    return p


DOC = P("string", "文档名称（Keynote 里的文稿名，不是路径）", True)
SLIDE = P("integer", "页码（从 1 开始）", True)


# ─────────────── 文档 ───────────────
@tool("kk_page", "【推荐】用一份 page spec 生成整页：元素顺序即 z 序，写完自动回读校验，不符则回滚",
      S(doc=DOC,
        slide=P("integer", "第几页（1 起）", True),
        spec=P("object", "页面描述：{background?, elements:[{id?,type(text|card|image|table|shape),box:[x,y,w,h],text?,path?,data?,style?}]}。card 支持 style.fill/radius/border 与 text.{title,body,align,valign}", True),
        mode=P("string", "replace（清空重建，默认）或 append（追加）")))
def _page(a):
    d = Deck(a["doc"])
    return page_mod.apply_page(d, a["slide"], a["spec"], a.get("mode", "replace"))


@tool("kk_page_validate", "只校验 page spec 是否合法，不写入 Keynote",
      S(spec=P("object", "页面描述", True)))
def _page_validate(a):
    bg, elements = page_mod.normalise(a["spec"])
    return {"ok": True, "elements": len(elements), "background": bool(bg),
            "types": sorted({e["type"] for e in elements})}


@tool("kk_extract_page", "把一页读成 page spec（可再喂给 kk_page 重建）",
      S(doc=DOC, slide=P("integer", "第几页（1 起）", True),
        background=P("string", "可选，给 spec 补一个纯色背景，如 #F4EBDD")))
def _extract_page(a):
    d = Deck(a["doc"])
    return page_mod.extract_page(d, a["slide"], with_background=a.get("background"))


@tool("kk_list_documents", "列出当前打开的所有 Keynote 文稿")
def _list_docs(_):
    return {"documents": ops.list_documents()}


@tool("kk_create_document", "新建演示文稿",
      S(theme=P("string", "主题名，默认「白色」；「乳色纸」是米色纸张底"),
        width=P("integer", "画布宽，默认 1920"),
        height=P("integer", "画布高，默认 1080")))
def _create(a):
    d = Deck.create(theme=a.get("theme", "白色"),
                    width=a.get("width", 1920), height=a.get("height", 1080))
    return {"document": d.name, "slides": d.slide_count()}


@tool("kk_open_document", "打开磁盘上的 .key 文件", S(path=P("string", "绝对路径", True)))
def _open(a):
    return ops.open_document(a["path"])


@tool("kk_close_document", "关闭文稿（默认不保存）", S(doc=DOC, save=P("boolean", "是否保存")))
def _close(a):
    Deck(a["doc"]).close(save=bool(a.get("save")))
    return {"closed": a["doc"]}


@tool("kk_save_document", "另存为 .key", S(doc=DOC, path=P("string", "输出路径", True)))
def _save(a):
    return {"saved": Deck(a["doc"]).save(a["path"])}


@tool("kk_export", "导出为逐页 PNG / PowerPoint",
      S(doc=DOC, path=P("string", "输出路径", True),
        format=P("string", "images | PowerPoint", True, enum=["images", "PowerPoint"])))
def _export(a):
    return {"exported": Deck(a["doc"]).export(a["path"], a["format"])}


@tool("kk_export_pdf", "导出 PDF（用逐页 PNG 合成，绕开 Keynote 原生导出的空白页问题）",
      S(doc=DOC, path=P("string", "输出路径", True)))
def _export_pdf(a):
    return {"exported": Deck(a["doc"]).export_pdf(a["path"])}


@tool("kk_list_themes", "列出可用主题")
def _themes(_):
    return {"themes": ops.list_themes()}


@tool("kk_set_theme", "切换主题（这是唯一可脚本化的统一底图手段）",
      S(doc=DOC, theme=P("string", "主题名", True)))
def _set_theme(a):
    return ops.set_theme(Deck(a["doc"]), a["theme"])


@tool("kk_list_layouts", "列出母版版式", S(doc=DOC))
def _layouts(a):
    return {"layouts": ops.list_layouts(Deck(a["doc"]))}


# ─────────────── 页面 ───────────────
@tool("kk_add_slide", "在末尾追加一页",
      S(doc=DOC, master=P("string", "母版版式名，默认「空白」")))
def _add_slide(a):
    d = Deck(a["doc"])
    return {"slide": d.add_slide(a.get("master", "空白")), "total": d.slide_count()}


@tool("kk_list_slides", "列出所有页（标题 / 是否跳过）", S(doc=DOC))
def _list_slides(a):
    return {"slides": ops.list_slides(Deck(a["doc"]))}


@tool("kk_get_slide", "读取某页的标题 / 正文 / 备注 / 元素数", S(doc=DOC, slide=SLIDE))
def _get_slide(a):
    return ops.get_slide_content(Deck(a["doc"]), a["slide"])


@tool("kk_inspect_slide", "列出一页上所有元素的类型、坐标与尺寸（用于校验）",
      S(doc=DOC, slide=SLIDE))
def _inspect(a):
    return Deck(a["doc"]).inspect(a["slide"])


@tool("kk_delete_slide", "删除一页", S(doc=DOC, slide=SLIDE))
def _delete(a):
    d = Deck(a["doc"])
    return {"remaining": d.remove_slide(a["slide"])}


@tool("kk_duplicate_slide", "复制一页", S(doc=DOC, slide=SLIDE))
def _duplicate(a):
    d = Deck(a["doc"])
    return {"total": d.duplicate_slide(a["slide"])}


@tool("kk_move_slide", "移动页面位置", S(doc=DOC, source=P("integer", "原页码", True),
                                target=P("integer", "目标页码", True)))
def _move(a):
    return ops.move_slide(Deck(a["doc"]), a["source"], a["target"])


@tool("kk_skip_slide", "设置某页放映时跳过",
      S(doc=DOC, slide=SLIDE, skipped=P("boolean", "true=跳过")))
def _skip(a):
    return ops.skip_slide(Deck(a["doc"]), a["slide"], bool(a.get("skipped", True)))


@tool("kk_set_layout", "切换某页的母版版式",
      S(doc=DOC, slide=SLIDE, layout=P("string", "版式名", True)))
def _set_layout(a):
    return ops.set_layout(Deck(a["doc"]), a["slide"], a["layout"])


@tool("kk_set_title", "设置标题占位符文本", S(doc=DOC, slide=SLIDE, title=P("string", "标题", True)))
def _set_title(a):
    return ops.set_title(Deck(a["doc"]), a["slide"], a["title"])


@tool("kk_set_body", "设置正文占位符文本（换行分段）",
      S(doc=DOC, slide=SLIDE, body=P("string", "正文", True)))
def _set_body(a):
    return ops.set_body(Deck(a["doc"]), a["slide"], a["body"])


@tool("kk_set_notes", "设置演讲者备注", S(doc=DOC, slide=SLIDE, notes=P("string", "备注", True)))
def _set_notes(a):
    return Deck(a["doc"]).set_notes(a["slide"], a["notes"])


# ─────────────── 内容 ───────────────
@tool("kk_add_text", "插入真文本框（坐标 / 字号 / 颜色 / 字体可控）",
      S(doc=DOC, slide=SLIDE, text=P("string", "文本", True),
        x=P("number", "左上角 X", True), y=P("number", "左上角 Y", True),
        w=P("number", "宽度", True), h=P("number", "高度", True),
        size=P("number", "字号"), color=P("string", "颜色 #RRGGBB"),
        font=P("string", "PostScript 字体名，如 Songti SC Bold / PingFangSC-Semibold")))
def _add_text(a):
    return Deck(a["doc"]).add_text(a["slide"], a["text"], a["x"], a["y"], a["w"], a["h"],
                                   size=a.get("size"), color=a.get("color"), font=a.get("font"))


@tool("kk_add_shape", "插入形状（填充色跟随主题）",
      S(doc=DOC, slide=SLIDE, text=P("string", "形状内文字"),
        x=P("number", "X", True), y=P("number", "Y", True),
        w=P("number", "宽", True), h=P("number", "高", True),
        size=P("number", "字号"), color=P("string", "文字颜色 #RRGGBB")))
def _add_shape(a):
    return Deck(a["doc"]).add_shape(a["slide"], a.get("text", ""), a["x"], a["y"], a["w"], a["h"],
                                    size=a.get("size"), color=a.get("color"))


@tool("kk_add_image", "插入图片（支持透明 PNG；也可当整页背景）",
      S(doc=DOC, slide=SLIDE, path=P("string", "图片绝对路径", True),
        x=P("number", "X"), y=P("number", "Y"),
        w=P("number", "宽"), h=P("number", "高")))
def _add_image(a):
    return Deck(a["doc"]).add_image(a["slide"], a["path"], a.get("x", 0), a.get("y", 0),
                                    a.get("w"), a.get("h"))


@tool("kk_set_background", "给某页铺整页背景图（需在该页还没有其他元素时调用）",
      S(doc=DOC, slide=SLIDE, path=P("string", "图片路径", True),
        w=P("number", "宽，默认 1920"), h=P("number", "高，默认 1080")))
def _set_bg(a):
    return Deck(a["doc"]).set_background(a["slide"], a["path"],
                                         a.get("w", 1920), a.get("h", 1080))


@tool("kk_add_line", "插入直线",
      S(doc=DOC, slide=SLIDE,
        x1=P("number", "起点 X", True), y1=P("number", "起点 Y", True),
        x2=P("number", "终点 X", True), y2=P("number", "终点 Y", True)))
def _add_line(a):
    return Deck(a["doc"]).add_line(a["slide"], a["x1"], a["y1"], a["x2"], a["y2"])


@tool("kk_position_item", "移动 / 缩放某个元素",
      S(doc=DOC, slide=SLIDE, kind=P("string", "shape | image | text", True,
                                     enum=["shape", "image", "text"]),
        index=P("integer", "元素索引（0 开始）", True),
        x=P("number", "X", True), y=P("number", "Y", True),
        w=P("number", "宽"), h=P("number", "高")))
def _position(a):
    return ops.position_item(Deck(a["doc"]), a["slide"], a["kind"], a["index"],
                             a["x"], a["y"], a.get("w"), a.get("h"))


@tool("kk_align_items", "对齐多个元素",
      S(doc=DOC, slide=SLIDE, kind=P("string", "shape | image | text", True),
        indexes=P("array", "元素索引数组", True, items={"type": "integer"}),
        alignment=P("string", "left|right|top|bottom|center|middle", True)))
def _align(a):
    return ops.align_items(Deck(a["doc"]), a["slide"], a["kind"], a["indexes"], a["alignment"])


@tool("kk_distribute_items", "均匀分布多个元素",
      S(doc=DOC, slide=SLIDE, kind=P("string", "shape | image | text", True),
        indexes=P("array", "元素索引数组", True, items={"type": "integer"}),
        direction=P("string", "horizontal | vertical")))
def _distribute(a):
    return ops.distribute_items(Deck(a["doc"]), a["slide"], a["kind"], a["indexes"],
                                a.get("direction", "horizontal"))


@tool("kk_get_shape_info", "读取形状的位置 / 尺寸 / 文本 / 字号", S(doc=DOC, slide=SLIDE,
                                                       index=P("integer", "形状索引", True)))
def _shape_info(a):
    return ops.get_shape_info(Deck(a["doc"]), a["slide"], a["index"])


@tool("kk_format_shape", "设置形状文字样式",
      S(doc=DOC, slide=SLIDE, index=P("integer", "形状索引", True),
        size=P("number", "字号"), color=P("string", "颜色 #RRGGBB"),
        font=P("string", "PostScript 字体名"), alignment=P("string", "left|center|right")))
def _format_shape(a):
    return ops.format_shape(Deck(a["doc"]), a["slide"], a["index"], size=a.get("size"),
                            color=a.get("color"), font=a.get("font"), alignment=a.get("alignment"))


# ─────────────── 表格 ───────────────
@tool("kk_add_table", "插入原生表格",
      S(doc=DOC, slide=SLIDE, data=P("array", "二维数组", True),
        x=P("number", "X", True), y=P("number", "Y", True),
        w=P("number", "宽", True), h=P("number", "高", True)))
def _add_table(a):
    return Deck(a["doc"]).add_table(a["slide"], a["data"], a["x"], a["y"], a["w"], a["h"])


@tool("kk_read_table", "读取表格内容", S(doc=DOC, slide=SLIDE, index=P("integer", "表格索引，默认 0")))
def _read_table(a):
    return ops.read_table(Deck(a["doc"]), a["slide"], a.get("index", 0))


@tool("kk_write_table", "写入表格单元格",
      S(doc=DOC, slide=SLIDE, data=P("array", "二维数组", True),
        index=P("integer", "表格索引，默认 0")))
def _write_table(a):
    return ops.write_table(Deck(a["doc"]), a["slide"], a["data"], a.get("index", 0))


# ─────────────── 图表 / 信息图 ───────────────
@tool("kk_add_chart", "生成图表并插入（Keynote 无 chart API，这里用 matplotlib 出透明 PNG）",
      S(doc=DOC, slide=SLIDE,
        kind=P("string", "bar | line | donut", True, enum=["bar", "line", "donut"]),
        labels=P("array", "X 轴标签", True, items={"type": "string"}),
        values=P("array", "柱状 / 环形用的数值"),
        series=P("object", "折线用的多系列 {名称: [数值...]}"),
        title=P("string", "图表标题"),
        x=P("number", "X", True), y=P("number", "Y", True),
        w=P("number", "宽", True), h=P("number", "高", True)))
def _add_chart(a):
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    kind = a["kind"]
    if kind == "bar":
        path = charts.bar_chart(a["labels"], a["values"], title=a.get("title", ""), path=tmp)
    elif kind == "line":
        path = charts.line_chart(a["labels"], a["series"] or {}, title=a.get("title", ""), path=tmp)
    else:
        path = charts.donut_chart(a["labels"], a["values"], title=a.get("title", ""), path=tmp)
    Deck(a["doc"]).add_image(a["slide"], path, a["x"], a["y"], a["w"], a["h"])
    return {"rendered": path, "kind": kind}


@tool("kk_add_diagram", "生成信息图并插入（泳道图 / 层级图 / 集成图）",
      S(doc=DOC, slide=SLIDE,
        kind=P("string", "swimlane | hierarchy | integration", True,
               enum=["swimlane", "hierarchy", "integration"]),
        spec=P("object", "图形数据，字段见 docs/diagrams.md / docs/diagrams.zh-CN.md", True),
        x=P("number", "X"), y=P("number", "Y"),
        w=P("number", "宽"), h=P("number", "高")))
def _add_diagram(a):
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    spec = dict(a["spec"])
    spec["out"] = tmp
    kind = a["kind"]
    if kind == "swimlane":
        spec.setdefault("stages", [])
        spec["lanes"] = [tuple(x) for x in spec.get("lanes", [])]
        if "highlight" in spec:
            spec["highlight"] = {tuple(x) for x in spec["highlight"]}
        diagrams.swimlane(**spec)
    elif kind == "hierarchy":
        spec["rows"] = [tuple(x) for x in spec.get("rows", [])]
        spec["cards"] = [tuple(x) for x in spec.get("cards", [])]
        diagrams.hierarchy(**spec)
    else:
        spec["lanes"] = [(n, [tuple(f) for f in flows]) for n, flows in spec.get("lanes", [])]
        diagrams.integration(**spec)
    Deck(a["doc"]).add_image(a["slide"], tmp, a.get("x", 0), a.get("y", 0),
                             a.get("w", 1920), a.get("h", 1080))
    return {"rendered": tmp, "kind": kind}


# ─────────────── 放映与校验 ───────────────
@tool("kk_start_slideshow", "开始放映", S(doc=DOC))
def _start(a):
    return ops.start_slideshow(Deck(a["doc"]))


@tool("kk_stop_slideshow", "停止放映")
def _stop(_):
    return ops.stop_slideshow(Deck(""))


@tool("kk_verify", "读回页面并校验元素数量（防止 Keynote 静默失败）",
      S(doc=DOC, slide=SLIDE, expect=P("integer", "期望元素数")))
def _verify(a):
    return Deck(a["doc"]).verify(a["slide"], a.get("expect"))


@tool("kk_server_info", "服务器版本与能力概览")
def _info(_):
    return {"name": "keynote-kit", "version": __version__, "tools": len(TOOLS),
            "capabilities": ["documents", "slides", "text", "shapes", "images",
                             "tables", "charts", "diagrams", "layout", "notes",
                             "export (png/pptx/pdf)", "slideshow"]}


# ─────────────── 协议层 ───────────────
def _reply(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _handle(msg: dict) -> dict | None:
    method = msg.get("method")
    mid = msg.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": msg.get("params", {}).get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "keynote-kit", "version": __version__},
        }}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": [
            {k: v for k, v in t.items() if k != "handler"} for t in TOOLS.values()]}}
    if method == "tools/call":
        params = msg.get("params", {})
        name = params.get("name")
        args = params.get("arguments") or {}
        entry = TOOLS.get(name)
        if not entry:
            return {"jsonrpc": "2.0", "id": mid,
                    "error": {"code": -32602, "message": f"unknown tool: {name}"}}
        try:
            # 清除 schema 里的内部标记
            result = entry["handler"](args)
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "isError": False}}
        except KeynoteError as exc:
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": f"KeynoteError: {exc}"}], "isError": True}}
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                "isError": True}}
    if mid is not None:
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def main() -> int:
    print(f"keynote-kit MCP server v{__version__} · {len(TOOLS)} tools", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = _handle(msg)
        if response is not None:
            _reply(response)
    return 0


if __name__ == "__main__":
    sys.exit(main())
