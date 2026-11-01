# Keynote 文稿压缩

[English](compression.md) · **简体中文**

Keynote 没有"减少文件大小"的命令，脚本层也没有接口。`.key` 本质是个 zip 包（`Data/` 里放着
所有图片和视频），所以想把体积降下来，只能重写包内媒体 —— 而这件事非常容易做坏。

`tools/compress_deck.py` 把这件事做对了。

```bash
# 整体压缩（视频 + 图片）
python tools/compress_deck.py 原稿.key -o 压缩版.key

# 只压视频（最稳，通常能省一半）
python tools/compress_deck.py 原稿.key -o 压缩版.key --videos-only

# 压完逐页与原文比对
python tools/compress_deck.py 原稿.key -o 压缩版.key --verify 原稿.key
```

依赖：Python 3.11+（`zipfile` 的 `metadata_encoding`）、`ffmpeg`、`Pillow`。

## 四个坑（按踩到顺序）

### 1. 中文文件名必须按 UTF-8 解码

Keynote 写入的是 UTF-8 字节，但**没打 UTF-8 标志位**。Python 默认按 `cp437` 解码，
`姚欣悦-金牌导购….mp4` 就变成乱码；写回时这些乱码字符被重新编码成 UTF-8 ——
**字节变了**。Keynote 于是找不到这个素材，那一页的图/视频直接消失。

```python
zipfile.ZipFile(path, metadata_encoding="utf-8")   # 必须，Python 3.11+
```

症状：个别页面内容消失，其余正常。59 页的实测稿里，这一条影响了 36 个素材、10 页。

### 2. `.png` 文件里必须是 PNG 字节

Keynote 按扩展名解码。把 JPEG 字节写进 `image118-222.png`，这张图就不会渲染。

另外：**不要量化成调色板模式**（`Image.convert("P")`）。即使文件本身是合法 PNG，
Keynote 也渲染不出重写后的调色板 PNG。

### 3. 视频输出必须用 ffmpeg 认识的扩展名

`ffmpeg -i x.qt out.qt` 会报 "Invalid argument"。先输出 `.mp4` / `.mov`，
再把字节写回原始条目名。

### 4. 重建 zip 本身就有风险 —— 必须靠"渲染比对"验收

一个字节都没改的重建，都不保证渲染结果一致。能覆盖以上所有问题的唯一验收方式是：
**把两份文稿都导出成逐页 PNG，逐页比对**。

```bash
python tools/compress_deck.py 原稿.key -o 压缩版.key --verify 原稿.key
# 逐页比对 59 页，差异 0 页
```

单页平均像素差超过 ~1.0 就说明有问题 —— 打开那一页人工看一眼。

## 什么值得压

| 素材 | 参数 | 典型效果 |
|---|---|---|
| 1080p 视频 → 720p，CRF 27，AAC 96k | `--video-max-edge 1280 --crf 27` | −90% |
| PNG 截图，长边 1920（仍存 PNG） | `--max-edge 1920` | −30~50% |
| JPEG 照片，质量 92 | `--quality 92` | −40~60% |
| 小图 | 重编码反而变大时保留原样 | — |

真实案例：59 页、566 个素材、450 MB → 95 MB（−79%），**逐页零差异**。

## 不要做的事

- 不要把 PNG 转成 JPEG 省空间（坑 2）。
- 不要给 PNG 做 256 色量化（坑 2）。
- 不要删除"看起来没用"的素材 —— Keynote 按文件名索引，无法可靠区分孤儿文件。
- 不要把"文件能打开"当作验收 —— 它永远能打开，只是内容丢了。

## 回滚

比对通过之前，务必保留原稿。iCloud 云盘的版本历史是第二道保险。
