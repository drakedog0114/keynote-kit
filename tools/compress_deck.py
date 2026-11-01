#!/usr/bin/env python3
"""压缩 Keynote 文稿体积：重编码视频 + 重采样图片，保持版面不变。

    python tools/compress_deck.py 原稿.key -o 压缩版.key
    python tools/compress_deck.py 原稿.key -o 压缩版.key --videos-only
    python tools/compress_deck.py 原稿.key -o 压缩版.key --verify 原稿.key

**为什么需要这个脚本**：Keynote 没有提供"减少文件大小"的接口，而直接改写
`.key`（zip 包）有两个足以毁掉文稿的坑，脚本已全部规避：

1. **中文文件名必须按 UTF-8 解码**（`metadata_encoding="utf-8"`）。
   Keynote 写入的是 UTF-8 字节但没打标志位，Python 默认按 cp437 解码，再写回时
   字节就变了 —— 结果 Keynote 找不到这些素材，页面上的图/视频直接消失。
2. **PNG 必须输出 PNG，不能改成 JPEG，也不能量化成调色板模式**。
   Keynote 按扩展名解码，扩展名与内容不符会跳过；调色板模式 PNG 同样渲染不出来。

`--verify` 会把两份文稿都导出成逐页 PNG 逐页比对，任何一页平均像素差超过阈值
就报出来。这是唯一可靠的验收方式 —— 只看文件能不能打开是不够的。
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

MIN_PY = (3, 11)   # zipfile metadata_encoding 需要 3.11+

IMAGE_EXT = (".png", ".jpg", ".jpeg")
VIDEO_EXT = (".mp4", ".mov", ".qt", ".m4v")


# ────────────────────────── 视频 ──────────────────────────
def probe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:format=duration",
         "-of", "json", path],
        capture_output=True, text=True, check=False)
    try:
        data = json.loads(out.stdout or "{}")
        st = (data.get("streams") or [{}])[0]
        return {"w": st.get("width", 0), "h": st.get("height", 0),
                "dur": float(data.get("format", {}).get("duration", 0) or 0)}
    except Exception:  # noqa: BLE001
        return {"w": 0, "h": 0, "dur": 0}


def reencode_video(src: str, dst: str, max_edge: int, crf: int) -> None:
    scale = (f"scale='if(gt(iw,ih),min({max_edge},iw),-2)'"
             f":'if(gt(iw,ih),-2,min({max_edge},ih))'")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
           "-vf", scale, "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
           "-movflags", "+faststart", dst]
    subprocess.run(cmd, check=True)


# ────────────────────────── 图片 ──────────────────────────
def normalise(im):
    """统一到 8bit RGB/RGBA —— 绝不输出调色板模式。"""
    if im.mode in ("P", "PA"):
        im = im.convert("RGBA" if (im.mode == "PA" or "transparency" in im.info) else "RGB")
    if im.mode.startswith("I;16") or im.mode == "I":
        im = im.convert("I").point(lambda v: v / 256).convert("L")
    if im.mode == "L":
        im = im.convert("RGB")
    if im.mode == "CMYK":
        im = im.convert("RGB")
    return im


def reencode_image(data: bytes, name: str, max_edge: int, quality: int) -> bytes:
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    ext = os.path.splitext(name)[1].lower()
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:  # noqa: BLE001  不是图片就原样返回
        return data
    im = normalise(im)
    w, h = im.size
    if max(w, h) > max_edge:
        k = max_edge / max(w, h)
        im = im.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS)

    buf = io.BytesIO()
    if ext == ".png":
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        im.save(buf, "PNG", optimize=True)
    else:
        im.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True, subsampling=0)
    out = buf.getvalue()
    return out if len(out) < len(data) * 0.95 else data


# ────────────────────────── 主流程 ──────────────────────────
def compress(src: str, dst: str, *, max_edge: int = 1920, quality: int = 92,
             video_max_edge: int = 1280, crf: int = 27,
             videos_only: bool = False, quiet: bool = False) -> dict:
    stats = {"video": 0, "png": 0, "jpeg": 0, "keep": 0, "saved_video": 0, "saved_image": 0}
    zin = zipfile.ZipFile(src, metadata_encoding="utf-8")   # ← 关键：别用默认 cp437
    tmp = tempfile.mkdtemp(prefix="keynote-compress-")
    try:
        # 先把视频抽出来重编码，按"条目名后缀"回填（中文名也能对上）
        video_map: dict[str, str] = {}
        for item in zin.infolist():
            name = item.filename
            if not name.lower().endswith(VIDEO_EXT):
                continue
            raw = zin.read(name)
            ext = os.path.splitext(name)[1].lower()
            mux_ext = ".mov" if ext in (".qt", ".mov") else ".mp4"   # ffmpeg 需要认识的扩展名
            base = os.path.join(tmp, f"v{len(video_map)}")
            work = base + ext
            with open(work, "wb") as fh:
                fh.write(raw)
            out = base + "-out" + mux_ext
            try:
                reencode_video(work, out, video_max_edge, crf)
            except subprocess.CalledProcessError:
                continue
            if os.path.exists(out) and os.path.getsize(out) < len(raw) * 0.95:
                video_map[name] = out

        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
            for item in zin.infolist():
                name = item.filename
                data = zin.read(name)
                lower = name.lower()
                if name in video_map:
                    data = open(video_map[name], "rb").read()
                    stats["video"] += 1
                    stats["saved_video"] += zin.getinfo(name).file_size - len(data)
                elif lower.endswith(IMAGE_EXT) and not videos_only:
                    before = len(data)
                    data = reencode_image(data, name, max_edge, quality)
                    stats["saved_image"] += before - len(data)
                    if len(data) == before:
                        stats["keep"] += 1
                    else:
                        stats["png" if lower.endswith(".png") else "jpeg"] += 1
                zi = zipfile.ZipInfo(name, date_time=item.date_time)
                zi.compress_type = item.compress_type
                zout.writestr(zi, data)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    stats["size_before"] = os.path.getsize(src)
    stats["size_after"] = os.path.getsize(dst)
    if not quiet:
        print(f"视频 {stats['video']} 个 · PNG {stats['png']} · JPEG {stats['jpeg']} · 保留 {stats['keep']}")
        print(f"体积 {stats['size_before']/1048576:.0f}MB → {stats['size_after']/1048576:.0f}MB "
              f"({(1 - stats['size_after']/stats['size_before'])*100:.0f}% 减少)")
    return stats


def verify(orig: str, new: str, threshold: float = 1.0) -> int:
    """把两份文稿逐页导出成 PNG 比对，返回差异页数。"""
    from PIL import Image, ImageChops, ImageStat

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from keynote_kit import Deck
    from keynote_kit.runner import KeynoteError

    def open_name(path: str) -> str:
        """Keynote 的文稿名有时带 .key 后缀，有时不带，这里兼容两种。"""
        base = os.path.basename(path)
        stem = os.path.splitext(base)[0]
        from keynote_kit import ops
        names = [d["name"] for d in ops.list_documents()]
        for cand in (stem, base):
            if cand in names:
                return cand
        raise KeynoteError(f"文稿未打开：{base}（当前已打开：{', '.join(names)}）")

    dirs = {}
    for label, path in (("orig", orig), ("new", new)):
        d = os.path.join(tempfile.mkdtemp(prefix=f"kn-verify-{label}-"), "pv")
        deck = Deck(open_name(path))
        deck.export(d, "images")
        dirs[label] = d

    files = sorted(f for f in os.listdir(dirs["orig"]) if f.endswith(".png"))
    bad = []
    for f in files:
        g = os.path.join(dirs["new"], f.replace("pv", "pv", 1))
        if not os.path.exists(g):
            bad.append((f, 999))
            continue
        a = Image.open(os.path.join(dirs["orig"], f)).convert("RGB")
        b = Image.open(g).convert("RGB")
        if a.size != b.size:
            b = b.resize(a.size)
        diff = ImageStat.Stat(ImageChops.difference(a, b)).mean[0]
        if diff > threshold:
            bad.append((f, round(diff, 2)))

    print(f"逐页比对 {len(files)} 页，差异 {len(bad)} 页")
    for f, d in bad:
        print(f"  {f}  平均像素差 {d}")
    return len(bad)


def main() -> int:
    ap = argparse.ArgumentParser(description="压缩 Keynote 文稿体积")
    ap.add_argument("src")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--max-edge", type=int, default=1920, help="图片长边上限（默认 1920）")
    ap.add_argument("--quality", type=int, default=92, help="JPEG 质量（默认 92）")
    ap.add_argument("--video-max-edge", type=int, default=1280, help="视频长边上限（默认 1280）")
    ap.add_argument("--crf", type=int, default=27, help="x264 CRF（默认 27）")
    ap.add_argument("--videos-only", action="store_true", help="只压视频，不动图片")
    ap.add_argument("--verify", metavar="ORIGINAL", help="压缩后与原稿逐页比对")
    args = ap.parse_args()

    if sys.version_info < MIN_PY:
        print(f"需要 Python {MIN_PY[0]}.{MIN_PY[1]}+（zipfile 的 metadata_encoding 参数）", file=sys.stderr)
        return 2
    if not shutil.which("ffmpeg"):
        print("需要 ffmpeg：brew install ffmpeg", file=sys.stderr)
        return 2

    compress(args.src, args.out, max_edge=args.max_edge, quality=args.quality,
             video_max_edge=args.video_max_edge, crf=args.crf, videos_only=args.videos_only)

    if args.verify:
        bad = verify(args.verify, args.out)
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
