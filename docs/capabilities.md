# Capability matrix

**English** · [简体中文](capabilities.zh-CN.md)

Measured on **macOS 27.0.1 + Keynote Creator Studio 15.4** with
[iwork-mcp](https://github.com/reichenbach/iwork_mcp) 0.8.8 as the baseline.
Legend: ✅ works · ⚠️ works with a caveat · ❌ not possible

| # | Capability | Native AppleScript / JXA | iwork-mcp | keynote-kit |
|---|---|---|---|---|
| 1 | Create document with theme | ✅ | ✅ | ✅ |
| 2 | Custom canvas size | ✅ | ❌ | ✅ |
| 3 | Append slide at a position | ⚠️ overwrites neighbour | ❌ (`afterSlide` overwrites) | ✅ (append only) |
| 4 | Apply master layout | ✅ | ✅ | ✅ |
| 5 | Title / body via placeholders | ✅ | ✅ | — (uses text boxes) |
| 6 | **Text box with size / colour / font** | ⚠️ geometry only | ❌ `format_shape` → `-1728` | ✅ |
| 7 | Shape with exact coordinates | ⚠️ JXA position dropped | ⚠️ lands at (0,0) | ✅ |
| 8 | Shape fill colour | ❌ | ❌ | ❌ (theme only) |
| 9 | Image insertion (PNG alpha) | ✅ | ✅ | ✅ |
| 10 | Large image (4000×3000) | ✅ | ✅ | ✅ |
| 11 | **Per-slide background image** | ⚠️ no z-order API | ❌ | ✅ (insert order) |
| 12 | **Native table create + fill** | ❌ `make new table` `-10000` | ✅ | ✅ |
| 13 | Table geometry | ✅ | ❌ | ✅ |
| 14 | Table cell fill colour | ❌ | ❌ | ❌ |
| 15 | **Charts** | ❌ no `chart` class | ❌ | ✅ (matplotlib) |
| 16 | **Diagrams (swimlane / hierarchy)** | ❌ | ❌ | ✅ (Pillow) |
| 17 | Video insertion | ❌ `make new movie` hangs | ⚠️ via image-class trick | ⚠️ same trick |
| 17b | Straight lines | ❌ `make new line` fails | ✅ | ✅ (JXA `K.Line`) |
| 18 | Slide transitions | ✅ (enum constant) | ✅ | ❌ not wrapped (enum cannot be passed as string) |
| 19 | Speaker notes | ✅ | ✅ | ✅ |
| 20 | Duplicate / delete slide | ✅ | ✅ | ✅ |
| 20b | Move / skip slide | ✅ | ✅ | ❌ |
| 21 | Export PNG sequence | ✅ JXA | ✅ | ✅ (JXA) |
| 22 | Export PowerPoint | ✅ JXA (`Microsoft PowerPoint`) | ✅ | ✅ |
| 23 | Export PDF | ❌ `-6`, or **blank pages** when it "succeeds" | ⚠️ Quick Look, 1 page only | ✅ `export_pdf()` (PNG → assembled) |
| 24 | **Error on missing image** | n/a | ❌ returns `added: true` | ✅ raises |
| 25 | **Verify after write** | n/a | ❌ | ✅ `verify()` |
| 26 | Animations / builds | ❌ | ❌ (UI only) | ❌ |
| 27 | Image crop / mask | ❌ | ❌ | ❌ |
| 28 | Master slide background | ❌ read-only | ❌ | ❌ |

## Visual polish (verified 2026-11)

| Capability | Status | How |
|---|---|---|
| Image rounded corners / ellipse / crop | **works** (pre-rendered PNG) | `style.radius` / `style.shape` / `style.crop` |
| Text overflow auto-fit | **works** | `style.fit: true` (shrinks the font size) |
| z-order (bring to front) | **works** (images) | delete + re-insert; text needs a spec rebuild |
| Slide transitions | **works** (native, 12 effects) | `set_transition(doc, slide, "magic move")` |
| Opacity / rotation | **works** (native) | `set_opacity`, `set_rotation` |
| Hyperlinks | **works** (via RTF field) | `link` on a `rich` element |
| Build animations (appear / fly in) | **UI only** | `animations_ui` module, opt-in |

Details: [visuals.md](visuals.md). Self-check: `python tools/test_capabilities.py` (14 checks).

## Reading the table

- **Rows 6, 7, 11, 12, 13, 15, 16, 24, 25** are the reason this project exists.
- Rows 5–7 overlap: keynote-kit deliberately avoids placeholders and always emits real text boxes,
  because placeholder geometry does not reflow when the canvas size changes.
- Rows 21–23: export is the weakest area on Creator Studio builds. PowerPoint works through JXA
  **only** with the `Microsoft PowerPoint` enum; native PDF either throws `-6` or silently writes blank
  pages, so `export_pdf()` composes the PDF from per-slide PNGs instead.

## When to use what

| Task | Recommended |
|---|---|
| Bulk text / simple slides | `keynote-kit` (or any wrapper — the cost is the same) |
| Precise visual layout | `keynote-kit` — placeholders cannot do this |
| Data tables | `keynote-kit.add_table` |
| Charts and diagrams | render with `charts` / `diagrams`, insert as image |
| Animations, cropping, master backgrounds | Keynote UI, or wait for a native MCP |

## Validating a real deck

The fastest way to know whether a conversion is good is to render the source and the
result the same way and compare page by page:

```bash
# 1. reference: render the source PPTX
soffice --headless --convert-to pdf deck.pptx && pdftoppm -png -r 72 deck.pdf /tmp/ref
# 2. candidate: import into Keynote and export PNGs
python -c "from keynote_kit import Deck; Deck('deck').export('/tmp/out', 'images')"
# 3. compare
python tools/compare.py /tmp/ref /tmp/out
```

On a 22-page deck with 74 groups and 122 auto shapes:

| route | time | similarity to the source |
|---|---|---|
| native import | **4 s** | **95.4 %** |
| rebuild from spec | 596 s | 89.5 % (worst page 49.9 %) |

Native import wins on both axes — so **import real decks, do not rebuild them**.
Use the spec pipeline for pages you author yourself, and `replace_text.py` to adapt
content in an imported deck (it preserves every paragraph's size, font and colour).

## Editing capabilities

Creating pages is only half of it — the harder half is changing what already exists.
`tools/probe_editing.py` probes these against the real app and **reads the value back**
after every write.

| Operation | Status | Notes |
|---|---|---|
| Replace a text box's content | ✅ | paragraph size / font / colour survive |
| Add or remove a paragraph | ✅ | `set object text to a & return & b` |
| Move an element | ✅ | |
| Resize an element | ✅ | |
| Delete an element | ✅ | |
| Change paragraph size / colour / font | ✅ **JXA only** | the AppleScript `paragraph` class exposes *no* properties |
| Change table cell text | ✅ | |
| Merge / unmerge cells | ✅ | `merge (range "A1:B1" of table 1 of slide N of it)` |
| Add or delete table rows | ❌ | no such command in the sdef |
| Cell colour, row height | ❌ | |
| Duplicate a text box or image | ❌ | `Text items can not be copied. (-1717)` |
| Transitions, opacity, rotation | ✅ | rotation: shapes and images, not text boxes |
| Add / delete / duplicate slides | ✅ | |
| Speaker notes | ✅ | `presenter notes of slide N` |
| Switch master layout | ✅ | `base layout of slide N` |
| Hide the title placeholder | ✅ | `title showing of slide N` |
| Slide background fill | ❌ | read-only |
| Change the canvas size | ✅ | |
| Replace the font across a deck | ✅ | |
| Change a document's name | ✅ **JXA only** | AppleScript refuses |
| Paragraph alignment | ❌ | set it in the RTF at creation time |
| Build animations | ❌ | no API — use *progressive reveal* |

Two traps: the colour **setter** takes `0–65535` while the **getter** returns `0–1` floats;
and `slide.textItems[length - 1]` is not the element you just created — theme placeholders
enumerate after pushed items, so style the local reference.
