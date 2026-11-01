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
