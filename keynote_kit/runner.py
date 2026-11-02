"""底层执行器：统一封装 JXA 与 AppleScript，返回结构化结果。"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time

DEFAULT_TIMEOUT = 90


class KeynoteError(RuntimeError):
    """Keynote 脚本执行失败。"""


class ForegroundError(KeynoteError):
    """需要 Keynote 在前台，但当前前台是别的应用。

    粘贴（Cmd+V）这类操作只能在 Keynote 是前台应用时生效。
    与其默默把用户的窗口顶掉，不如先问清楚——除非调用方明确允许抢占。
    """


def frontmost_app() -> str:
    """当前前台应用的进程名。"""
    out, _err, _code = _run(
        ["osascript", "-e",
         'tell application "System Events" to return name of first application process '
         'whose frontmost is true'], timeout=15)
    return out.strip()


def activate_keynote() -> bool:
    """把 Keynote 切到前台。返回 True 表示确实切了（之前不在前台）。"""
    was = frontmost_app()
    if was == "Keynote":
        return False
    _run(["osascript", "-e", 'tell application "Keynote" to activate'], timeout=20)
    return True


def close_scratch_documents(prefix: str = "未命名") -> int:
    """关掉所有临时文稿（不保存），返回关掉的数量。

    验证脚本会开一堆文稿；跑完必须收干净，否则桌面上全是「未命名」窗口。
    """
    out, _err, _code = _run(["osascript", "-e", f"""
tell application "Keynote"
  set closed to 0
  set names to {{}}
  repeat with d in documents
    set n to name of d
    if n starts with "{prefix}" then set end of names to n
  end repeat
  repeat with n in names
    try
      close document (n as text) saving no
      set closed to closed + 1
    end try
  end repeat
  return closed
end tell"""], timeout=60)
    try:
        return int(out.strip())
    except ValueError:
        return 0


def require_foreground(allow_takeover: bool | None = None) -> None:
    """确保 Keynote 在前台。

    allow_takeover=None 时读环境变量 ``KK_TAKEOVER``：
    默认 ``0`` = 不抢占，找不到前台是 Keynote 就报错；
    设为 ``1`` = 允许抢占（脚本化批处理时用）。
    """
    if allow_takeover is None:
        allow_takeover = os.environ.get("KK_TAKEOVER", "0") == "1"
    if frontmost_app() == "Keynote":
        return
    if not allow_takeover:
        raise ForegroundError(
            "这一步需要 Keynote 在前台（剪贴板粘贴必须这样）。"
            "当前前台是别的应用，所以没有抢占你的窗口。\n"
            "两种办法：把 Keynote 切到前台再重跑，或者设 KK_TAKEOVER=1 允许脚本抢占。")
    activate_keynote()
    # 激活是异步的，给系统一点时间把焦点交过去
    for _ in range(15):
        time.sleep(0.2)
        if frontmost_app() == "Keynote":
            return
    raise ForegroundError("已经尝试把 Keynote 切到前台，但它没有拿到焦点（可能有全屏应用在抢）。")


def _run(argv: list[str], timeout: int) -> tuple[str, str, int]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise KeynoteError(f"脚本超时（{timeout}s）：{argv[0]}") from exc
    return p.stdout.strip(), p.stderr.strip(), p.returncode


def jxa(script: str, params: dict | None = None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """执行 JXA 脚本。脚本需定义 run(argv)，argv[0] 为 JSON 参数。"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(script)
        path = fh.name
    try:
        argv = ["osascript", "-l", "JavaScript", path]
        if params is not None:
            argv.append(json.dumps(params, ensure_ascii=False))
        out, err, code = _run(argv, timeout)
        if code != 0:
            raise KeynoteError(err or out or f"JXA 退出码 {code}")
        if not out:
            return {}
        # osascript 对 object 结果会再压一层 "=> {..}"；这里只取最后一段合法 JSON
        for candidate in (out, out.split("\n")[-1]):
            try:
                value = json.loads(candidate)
                return value if isinstance(value, dict) else {"value": value}
            except json.JSONDecodeError:
                continue
        return {"raw": out}
    finally:
        os.unlink(path)


def applescript(script: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """执行 AppleScript，返回 stdout。用于几何与结构操作（JXA 有些 setter 无效）。"""
    args = ["osascript", "-e", script]
    out, err, code = _run(args, timeout)
    if code != 0:
        raise KeynoteError(err or out or f"AppleScript 退出码 {code}")
    return out


def esc_text(text: str) -> str:
    """把文本安全嵌入 AppleScript 字符串字面量。"""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
