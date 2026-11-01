# Compressing a Keynote deck

**English** · [简体中文](compression.zh-CN.md)

Keynote has no "reduce file size" command and no scripting API for it. A `.key` file is a zip
package (`Data/` holds every image and movie), so the only way to shrink one is to rewrite its
media — which is easy to get catastrophically wrong.

`tools/compress_deck.py` does it safely.

```bash
# whole deck (video + images)
python tools/compress_deck.py 原稿.key -o 压缩版.key

# video only (safest, usually ~50% smaller)
python tools/compress_deck.py 原稿.key -o 压缩版.key --videos-only

# compress and verify page-by-page against the original
python tools/compress_deck.py 原稿.key -o 压缩版.key --verify 原稿.key
```

Requirements: Python 3.11+ (for `zipfile` `metadata_encoding`), `ffmpeg`, `Pillow`.

## The four traps

### 1. Non-ASCII filenames must be decoded as UTF-8

Keynote writes filenames as UTF-8 bytes **without setting the UTF-8 flag**. Python's default
`metadata_encoding` is `cp437`, so `姚欣悦-金牌导购….mp4` becomes mojibake; writing it back
re-encodes those mojibake characters as UTF-8 — **producing different bytes**. Keynote then cannot
find the asset, and the page silently renders without that image or video.

```python
zipfile.ZipFile(path, metadata_encoding="utf-8")   # required, Python 3.11+
```

Symptom: a handful of pages lose their content while the rest look fine. On a 59-page test deck this
hit 36 assets / 10 pages.

### 2. A PNG entry must contain PNG bytes

Keynote decodes by extension. If you write JPEG bytes into `image118-222.png`, the image simply
does not render.

Also: **do not quantise to palette mode** (`Image.convert("P")`). Keynote fails to render
palette PNGs from a rewritten package, even when the file is a valid PNG.

### 3. Videos need a muxer-friendly output extension

`ffmpeg -i x.qt out.qt` fails with "Invalid argument". Write to `.mp4` / `.mov`, then store the
bytes under the original entry name.

### 4. Rebuilding the zip is itself risky — always verify by rendering

A byte-identical rebuild is *not* guaranteed to render identically. The only acceptance test that
catches all of the above is: export both decks to PNGs and diff them page by page.

```bash
python tools/compress_deck.py 原稿.key -o 压缩版.key --verify 原稿.key
# 逐页比对 59 页，差异 0 页
```

A mean pixel difference above ~1.0 per page means something is wrong — open that page and look.

## What compresses well

| Asset | Settings | Typical result |
|---|---|---|
| Video 1080p → 720p, CRF 27, AAC 96k | `--video-max-edge 1280 --crf 27` | −90% |
| PNG screenshots, long edge 1920 | `--max-edge 1920` (keeps PNG) | −30~50% |
| JPEG photos, quality 92 | `--quality 92` | −40~60% |
| Small images | left untouched when re-encoding grows them | — |

Real case: 59-page deck, 566 assets, 450 MB → 95 MB (−79%) with **zero** page differences.

## What NOT to do

- Do not convert PNG → JPEG to save space (trap 2).
- Do not quantise PNGs to 256 colours (trap 2).
- Do not delete "unused" assets — Keynote's index references them by name and there is no reliable
  way to tell orphans from used files.
- Do not trust "the file opens" as verification — it always opens, it just loses content.

## Rollback

Always keep the original until the diff check passes. iCloud Drive keeps version history for `.key`
files, which is a second safety net.
