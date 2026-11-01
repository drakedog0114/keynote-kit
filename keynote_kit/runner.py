"""底层执行器：统一封装 JXA 与 AppleScript，返回结构化结果。"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

DEFAULT_TIMEOUT = 90


class KeynoteError(RuntimeError):
    """Keynote 脚本执行失败。"""


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
