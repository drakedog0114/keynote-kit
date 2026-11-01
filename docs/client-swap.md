# Turning an existing deck into a new client's deck

**English** · [简体中文](client-swap.zh-CN.md)

Most proposal decks are re-used: the structure and storyline stay, the client name, the numbers
and the proof points change. This is the workflow for that job — it keeps the original layout,
typography and media, and does **not** rebuild the deck.

Measured on a real 59-page deck: brand swap + 96 text rewrites + 3 image replacements ≈ 20 minutes.

## 1. Get an editable Keynote file

Keynote's own PowerPoint importer beats any reconstruction:

```bash
# open the .pptx with Keynote (13 s for a 434 MB / 59-page deck)
osascript -e 'tell application "Keynote" to open POSIX file "/path/deck.pptx"'
```

| Approach | Time | Fidelity | Video |
|---|---|---|---|
| Keynote native import | **13 s** | **96.5 %** mean pixel similarity, worst page 90 % | 8/8 preserved |
| Rebuilding shape-by-shape from scratch | 30+ min | 60 % | not supported |

Remaining 3.5 % is font substitution (e.g. `微软雅黑` missing on macOS) — structure, images,
colour blocks and backgrounds line up exactly.

Do **not** rebuild a deck to change its client. Rebuild only when the goal is a new design.

## 2. Rewrite the wording, keep the formatting

```bash
python tools/replace_text.py "deck name" --map rules.json --dry-run   # preview
python tools/replace_text.py "deck name" --map rules.json
```

`rules.json`:

```json
{"replace": [["甲珠宝", "乙珠宝"], ["传统手作", "新工坊"]],
 "regex":   [["月\\s*4-5\\s*千万", "月 1.2 亿"]]}
```

**Why a tool and not `set object text`**: assigning the whole text item flattens paragraph
styles — a 118 pt title and a 66 pt subtitle collapse to one size. The tool snapshots each
paragraph's size / font / colour first, applies the replacement, then restores them per
paragraph. Alignment is never touched, so centred and right-aligned text survives.

Order matters: put longer phrases before their substrings (`甲珠宝` before `甲品牌`).

## 3. Replace brand imagery

Text inside images (logos baked into photos, app screenshots, flow diagrams) is **not** reachable
by text replacement. Three options, in order of preference:

| Situation | Do this |
|---|---|
| Screenshot / phone UI | Regenerate a mock with the new brand and drop it into the same box |
| Photo with a baked-in logo | Replace the whole image (or ask the client for a clean shot) |
| Diagram with baked-in labels | Rebuild it natively — see §4 |

Procedure that keeps the layout stable:

1. Record each image's `x, y, w, h` **before** deleting anything.
2. Delete from the highest index down (indexes shift after every delete).
3. Insert the new images, then re-assert the recorded geometry — and remember the brand mark
   you overlay on every page is itself an image at index N, so re-check the list before
   addressing `image 4`.

Note that Keynote enumerates images in creation order and the brand mark counts as one of them;
that is the single most common way to move the wrong picture.

## 4. Rebuild the pages whose body is a full-bleed image

Some pages are one big picture containing all the content. If its wording is client-specific,
rebuild the page as native elements so it stays editable:

```python
apply_page(deck, page_no, {"elements": [
    {"type": "card", "box": [34, 196, 356, 44], "style": {"fill": "#1F3A5F"},
     "text": {"title": "触点层 · 流量入口", "titleSize": 17, "titleColor": "#FFFFFF"}},
    ...
]}, mode="append")   # append keeps the page's existing title
```

Then delete the old image. Keep the original image's dimensions as the layout guide.

## 5. Verify

```bash
# 1) no occurrences of the old brand left
#    (scan every text item of every slide, including presenter notes)
# 2) export every page and look at the image-heavy ones
python -c "from keynote_kit import Deck; Deck('deck name').export('/tmp/pv','images')"
```

Checklist:

- [ ] old brand string: 0 hits in text items **and** presenter notes
- [ ] number consistency: a fan count on one card must match the total on another
- [ ] videos still present (native import keeps them; deleting images can hit a movie)
- [ ] pages whose body was an image: either rebuilt or explicitly listed as pending
- [ ] brand mark present on every page and not stretched

## 6. What NOT to do

- Do not rewrite pronouns/number scales with a blanket regex — check each hit.
- Do not promise a pixel-perfect clone of third-party product screenshots; regenerate them.
- Do not delete a page's background image while its text layer assumes the dark palette.
- Do not assume the logo you generated is the client's official VI — flag it as a placeholder.
