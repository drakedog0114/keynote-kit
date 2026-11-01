"""用 RTF + 剪贴板把「带对齐/字号/颜色的可编辑文本」写进 Keynote。

为什么需要它：Keynote 的 `alignment` 只对表格单元格开放，text item / paragraph 设对齐
都报 -1700；但把 RTF 放到剪贴板再 Cmd+V，Keynote 会新建一个**完全按 RTF 排版、
且可继续编辑**的文本框。这是目前唯一能同时拿到「可编辑」和「对齐/多样式」的路径。

代价：每个文本框约 1–2 秒（要走一次 UI 粘贴），比纯 AppleScript 慢。
"""

from __future__ import annotations

import os
import subprocess
import tempfile

from .runner import applescript, esc_text

ALIGN_CODE = {"left": "ql", "center": "qc", "right": "qr", "justify": "qj"}


def _rtf_escape(text: str) -> str:
    out = []
    for ch in text:
        o = ord(ch)
        if ch in "\\{}":
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\line ")
        elif o < 128:
            out.append(ch)
        else:
            out.append(f"\\u{o}?")
    return "".join(out)


def build_rtf(paragraphs: list[dict], default_size: float = 18) -> str:
    """paragraphs: [{align, runs:[{text,size,color,font,bold}]}] → RTF 字符串。"""
    fonts: dict[str, int] = {}
    colors: dict[str, int] = {}

    def font_id(name: str | None) -> str:
        name = name or "PingFangSC-Regular"
        if name not in fonts:
            fonts[name] = len(fonts)
        return f"\\f{fonts[name]}"

    def color_id(hexc: str | None) -> str:
        if not hexc:
            return ""
        hexc = hexc.lstrip("#").upper()
        if hexc not in colors:
            colors[hexc] = len(colors) + 1
        return f"\\cf{colors[hexc]}"

    body = []
    for para in paragraphs:
        align = ALIGN_CODE.get(para.get("align", "left"), "ql")
        chunks = [f"\\pard\\{align}\\sb0\\sa0"]
        for run in para.get("runs", []):
            size = round(float(run.get("size", default_size)) * 2)      # RTF 半磅
            chunks.append(f"{font_id(run.get('font'))}\\fs{size}{color_id(run.get('color'))}"
                          + ("\\b" if run.get("bold") else "")
                          + " " + _rtf_escape(run.get("text", "")) + "\\b0")
        body.append("".join(chunks) + "\\par")

    fonttbl = "".join(
        "{\\f%d\\fnil %s;}" % (i, _rtf_escape(name)) for name, i in fonts.items()
    ) or "{\\f0\\fnil Helvetica;}"
    colortbl = ";" + "".join(
        "\\red{r}\\green{g}\\blue{b};".format(
            r=int(h[0:2], 16), g=int(h[2:4], 16), b=int(h[4:6], 16))
        for h in colors) if colors else ";"
    return (
        "{\\rtf1\\ansi\\ansicpg1252\\deff0"
        "{\\fonttbl" + fonttbl + "}"
        "{\\colortbl" + colortbl + "}"
        + "".join(body) + "}"
    )


def paste_rich_text(doc: str, slide: int, paragraphs: list[dict], box: list[float],
                    default_size: float = 18, timeout: int = 60) -> dict:
    """把 RTF 粘成新文本框，并摆到指定位置。"""
    rtf = build_rtf(paragraphs, default_size)
    with tempfile.NamedTemporaryFile("w", suffix=".rtf", delete=False, encoding="ascii") as fh:
        fh.write(rtf)
        path = fh.name
    x, y, w, h = (int(round(v)) for v in box)
    try:
        applescript(f'''
tell application "Keynote"
  activate
  tell document {esc_text(doc)} to set current slide to slide {slide}
end tell
delay 0.12
set theRTF to (read (POSIX file "{path}") as «class RTF »)
set the clipboard to theRTF
tell application "Keynote" to activate
delay 0.1
tell application "System Events"
  keystroke "v" using command down
end tell
delay 0.3
tell application "Keynote"
  tell document {esc_text(doc)}
    set sel to selection
    if (count of sel) > 0 then
      set tgt to item 1 of sel
    else
      set tgt to text item (count of text items of slide {slide} of it) of slide {slide} of it
    end if
    set width of tgt to {w}
    set height of tgt to {h}
    set position of tgt to {{{x}, {y}}}
    set q to position of tgt
    return ((item 1 of q) as text) & "," & ((item 2 of q) as text)
  end tell
end tell''', timeout=timeout)
    finally:
        os.unlink(path)
    return {"box": [x, y, w, h], "pasted": True}
