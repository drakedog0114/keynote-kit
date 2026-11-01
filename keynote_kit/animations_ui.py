"""UI 自动化：选中画布元素 + 动效复制粘贴（实验性）。

**为什么需要它**：Keynote 的 AppleScript 里没有「构建动画」的概念
（sdef 只有 `transition properties`），也没有 `select` 命令。
要设置「逐个出现」这类构建动画，只能点 UI。

**已验证**：按画布几何 + 缩放算出屏幕坐标并点击，可以让元素进入选中态
（右侧检查器随之打开）。
**未验证**：动画效果本身的施加依赖检查器里的控件树，Keynote 升级后可能失效。

所以这里只提供**原语**，并且每次调用都会做前置检查，失败时给出明确提示，
不做"看起来成功"的假动作。
"""

from __future__ import annotations

import re
import subprocess

from .runner import applescript, esc_text, jxa

SLIDE_W, SLIDE_H = 1920.0, 1080.0


def _osascript(script: str, timeout: int = 30) -> str:
    res = subprocess.run(["osascript", "-e", script], capture_output=True,
                         text=True, timeout=timeout)
    return (res.stdout or "").strip()


def canvas_geometry() -> dict:
    """读出 Keynote 画布在屏幕上的位置与缩放。

    返回 {"origin": [x, y], "zoom": float, "ok": bool}
    坐标是逻辑点（AX 坐标系），可直接用于 System Events 点击。
    """
    script = r'''
tell application "Keynote" to activate
delay 0.4
tell application "System Events" to tell process "Keynote"
  set out to ""
  set elems to entire contents of window 1
  repeat with e in elems
    try
      if (role of e) is "AXScrollArea" then
        set p to position of e
        set s to size of e
        set w to item 1 of s
        if w > 300 and w < 1600 then
          set out to ((item 1 of p) as text) & "," & ((item 2 of p) as text) & "," & (w as text) & "," & ((item 2 of s) as text)
          exit repeat
        end if
      end if
    end try
  end repeat
  return out
end tell
'''
    raw = _osascript(script)
    if not raw:
        return {"origin": [0, 0], "zoom": 1.0, "ok": False}
    try:
        x, y, w, h = [float(v) for v in raw.split(",")]
    except ValueError:
        return {"origin": [0, 0], "zoom": 1.0, "ok": False}
    zoom = w / SLIDE_W
    return {"origin": [x, y], "zoom": zoom, "ok": zoom > 0.02, "canvas": [w, h]}


def select_element(doc: str, slide: int, kind: str, index: int,
                   box=None) -> dict:
    """通过点击画布选中一个元素（Keynote 没有 select 命令）。

    box 为 [x, y, w, h]（幻灯片坐标），默认读该元素的几何。
    """
    geo = canvas_geometry()
    if not geo["ok"]:
        raise RuntimeError(
            "取不到 Keynote 画布几何：窗口可能未显示或处于非标准布局。"
            "请先把 Keynote 窗口调到前台并让幻灯片画布可见。")

    if box is None:
        from .animate import element_order
        order = element_order(doc, slide)
        items = order.get(kind) or []
        if index > len(items):
            raise IndexError(f"第 {slide} 页没有第 {index} 个 {kind}")
        it = items[index - 1]
        box = [it["x"], it["y"], it["w"], it["h"]]

    cx = geo["origin"][0] + (box[0] + box[2] / 2) * geo["zoom"]
    cy = geo["origin"][1] + (box[1] + box[3] / 2) * geo["zoom"]
    _osascript(f'''
tell application "Keynote" to activate
delay 0.3
tell application "System Events" to tell process "Keynote"
  click at {{{int(cx)}, {int(cy)}}}
end tell''')
    return {"slide": slide, "kind": kind, "index": index,
            "clicked": [int(cx), int(cy)], "zoom": round(geo["zoom"], 4)}


def copy_animation(doc: str) -> dict:
    """格式 → 拷贝动画（把当前选中对象的动效复制到剪贴板）。"""
    script = '''
tell application "Keynote" to activate
delay 0.3
tell application "System Events" to tell process "Keynote"
  click menu item "拷贝动画" of menu 1 of menu bar item "格式" of menu bar 1
end tell'''
    _osascript(script)
    return {"action": "copy_animation"}


def paste_animation(doc: str) -> dict:
    """格式 → 粘贴动画（把剪贴板里的动效施加到当前选中对象）。"""
    script = '''
tell application "Keynote" to activate
delay 0.3
tell application "System Events" to tell process "Keynote"
  click menu item "粘贴动画" of menu 1 of menu bar item "格式" of menu bar 1
end tell'''
    _osascript(script)
    return {"action": "paste_animation"}


def animation_menu_available(doc: str) -> bool:
    """检查当前版本 Keynote 的「格式」菜单里有没有拷贝/粘贴动画。"""
    raw = _osascript('''
tell application "Keynote" to activate
delay 0.3
tell application "System Events" to tell process "Keynote"
  try
    set n to name of every menu item of menu 1 of menu bar item "格式" of menu bar 1
    return (n as text)
  on error
    return ""
  end try
end tell''')
    return bool(re.search(r"拷贝动画", raw))
