# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-11-01

Declarative page compiler, in-place client swap, safe deck compression.

### Added
- `kk_page` / `kk_page_validate` / `kk_extract_page`: build or read a whole slide from one spec,
  with read-back verification and rollback on mismatch.
- Element types `card` (rounded fill + embedded text rendered to PNG), `chart` (bar/line/donut),
  `diagram` (swimlane/hierarchy/integration), `rich` (RTF, keeps per-paragraph alignment).
- Master-placeholder slots: `{"type": "text", "slot": "title"|"body"}` writes into the theme
  placeholder so text stays editable **and** inherits alignment, bullets and spacing.
- `keynote_kit/richtext.py`: RTF → clipboard → paste, the only known way to get editable text
  with arbitrary alignment in Keynote.
- `tools/replace_text.py`: semantic find/replace across a deck that preserves per-paragraph
  size / font / colour (Keynote flattens styles if you assign the whole text item).
- `tools/pptx_to_spec.py`: decompose a PPTX (master decorations, tiled background, pictures,
  tables, nested groups, inherited run styles) into page specs.
- `tools/compress_deck.py`: shrink `.key` files by re-encoding media, verified page-by-page.
- Docs: `client-swap.md` / `client-swap.zh-CN.md` (turn a deck into another client's deck),
  `compression.*`, `quality-guide.zh-CN.md`, `rfc/0001-declarative-pages.md`.

### Changed
- 15 element-level tools are marked `deprecated` (kept callable for one release); new work should
  go through `kk_page`.

### Fixed
- Deck rewrite no longer corrupts assets: `.key` filenames are UTF-8 bytes without the flag, so
  `zipfile` must use `metadata_encoding="utf-8"`; `.png` entries must stay PNG, and palette-mode
  PNGs do not render after a rewrite.

## [0.3.0] - 2026-11-02

Visual polish: rounding, auto-fit, z-order, transitions, hyperlinks — plus a styling bug fix.

### Added
- `keynote_kit/imaging.py`: image rounding / ellipse / crop (pre-rendered PNG) and text
  measurement + auto-fit. Keynotes has no crop or autoFit API, so both are computed locally.
  Wired into `kk_page` as `style.radius` / `style.shape` / `style.crop` / `style.fit`.
- `keynote_kit/animate.py`: slide transitions (12 effects, native), element opacity and
  rotation (native), element order inspection and bring-to-front.
- `keynote_kit/animations_ui.py`: opt-in UI automation for build animations
  (canvas geometry → click to select → 格式 → 拷贝/粘贴动画).
- Hyperlinks: the RTF `HYPERLINK` field is imported by Keynote as a real link, exposed as
  `link` on `rich` elements.
- New MCP tools: `kk_set_transition`, `kk_get_transition`, `kk_set_element_style`,
  `kk_prepare_image`, `kk_fit_text`, `kk_element_order`, `kk_bring_to_front` (51 total).
- `tools/test_capabilities.py`: self-check with 14 assertions against a live Keynote.
- Docs: `visuals.md` / `visuals.zh-CN.md`.

### Fixed
- **Text styling was applied to the wrong object.** `slide.textItems[length - 1]` is not the
  element just pushed — JXA enumerates the theme's placeholder text items after the pushed
  ones, so styles landed on a placeholder. Text elements on the same slide all ended up with
  the same (default) size. Now the style is applied to the local reference.
- `set_opacity` takes 0–1 and converts to Keynote's 0–100 percentage (setting `0.4`
  directly made the element invisible).
- `build_rtf` rejects a hyperlink that is not the last run of its paragraph — Keynote
  silently drops everything after a `HYPERLINK` field.

## [0.4.0] - 2026-11-02

Reveal-by-splitting instead of build animations, safer auto-fit, and a card-text fix.

### Added
- `keynote_kit/build.py`: `build_reveal()` and `build_bullets()` split one page into a
  sequence of pages that reveal progressively, connected by transitions. This is the
  reliable replacement for build animations, which have no API at all.
- New MCP tools `kk_build_reveal` and `kk_build_bullets` (53 tools total).
- `tools/audit_styles.py`: audits a deck for style problems — uniform multi-paragraph text
  (the signature of the styling bug), zero-size elements, empty boxes and overflow risk.
- `examples/05_end_to_end.py`: the six-page end-to-end demo, moved into the repo so it is
  reproducible.

### Changed
- **Text auto-fit is now on by default** with `fit: "auto"`: it only shrinks when the text
  would fall off the canvas or overflow a multi-line box by >25 %. A deliberately tight box
  (e.g. a 96 pt title in a 60 pt box) is left alone, because Keynote text boxes never clip.
  `fit: true` forces shrinking, `fit: false` disables it.
- The two demo decks on the Desktop were regenerated: every styled text element in them had
  been stuck at the theme default (46 pt) by the styling bug fixed in 0.3.0.

### Fixed
- **Cards lost their text when a page also contained a `rich` element.** The sequential
  build path re-normalised already-normalised elements, which had stringified the card's
  structured `text` payload.

## [0.5.0] - 2026-11-02

Validated against a real 22-page client deck; the lessons are in the docs.

### Added
- `tools/compare.py`: page-by-page similarity between two sets of renders, with a
  `--min` threshold for CI.
- `tools/audit_styles.py`: finds style problems in an existing deck (uniform
  multi-paragraph text, zero-size elements, empty boxes, overflow risk).
- `examples/05_end_to_end.py`: the six-page end-to-end demo, now reproducible from the repo.
- Four new gotchas in both languages: missing fonts cap fidelity, JXA collection index
  ≠ the element just created, auto-shape fills cannot be read back, and a text box may
  legitimately be shorter than its text.

### Fixed
- **Cards lost their position when two cards had identical configuration.** They render
  to the same PNG file name, so name-based lookup matched the wrong element. Image-like
  elements are now located by creation order — `slide.images` enumerates in stacking
  order, which is the order they were pushed. Same root cause as the `textItems` index
  bug fixed in 0.3.0: a JXA collection index does not mean "the element just created".

### Measured on a real deck (22 pages, 74 groups, 122 auto shapes)

| route | time | similarity to source |
|---|---|---|
| native import | **4 s** | **95.4 %** |
| rebuild from spec | 596 s | 89.5 % (worst page 49.9 %) |

Native import wins on both axes, so **import real decks and adapt them with
`replace_text.py`** rather than rebuilding them. Rebuilding still drops auto-shape
fills, freeforms and group transforms.

### Note

Fidelity numbers above are measured against a render of the source **on a machine
without the deck's fonts**. The deck used `HarmonyOS Sans SC` (2180 runs), which was not
installed, so both renderers substituted different fallbacks — 95.4 % is a floor, not a
ceiling. Installing the font (`HarmonyOS Sans SC` is Apache-2.0) makes Keynote render the
design as intended.

## [Unreleased]

### Planned
- Animation / build support via UI automation (opt-in, requires Accessibility permission)
- Table cell fill colours once Keynote exposes them

## [0.1.0] — 2026-11-01

### Added
- `tools/compress_deck.py`: safe `.key` size reduction — video re-encode, image resampling,
  and page-by-page render verification (`--verify`). Documents the four package-rewrite traps
  (UTF-8 filename decoding, extension/content mismatch, palette PNGs, ffmpeg muxer extensions).
- Bilingual documentation: every core doc now ships an English and a Simplified Chinese
  version (`*.md` + `*.zh-CN.md`), including a new `docs/diagrams.md` data reference.
- **Complete MCP server** (`python -m keynote_kit.mcp_server`, 41 tools): documents, pages,
  text, shapes, images, tables, charts, diagrams, layout, notes, export, slideshow.
  No dependency on iwork-mcp.
- `ops` module: document/slide/table/layout helpers used by the server.
- `Deck` high-level API: create, add slides, text boxes, shapes, images, native tables,
  backgrounds, export (PNG / PowerPoint / PDF), save.
- `verify()` post-write checks to catch silent failures.
- `charts` module: bar, line and donut charts rendered with matplotlib on transparent
  backgrounds with CJK support.
- `diagrams` module: swimlane, hierarchy and integration layouts (1920×1080, transparent).
- `cli` module: JSON-emitting command line for shell / agent integration.
- `tools/probe_capabilities.py`: 25-point capability audit harness.
- `scripts/mcp_client.mjs` and `scripts/mcp_batch.mjs`: minimal MCP stdio drivers.
- Documentation: capability matrix, gotcha catalogue, MCP integration notes.

- `add_line()` — straight connectors via JXA `K.Line` (`make new line` is broken).
- `set_notes()` — per-slide speaker notes.
- `remove_slide()` / `duplicate_slide()`.
- `export_pdf()` — reliable PDF by composing per-slide PNGs.
- Export and save now **verify the artefact** and raise `KeynoteError` when Keynote
  silently writes nothing.

### Fixed (workarounds for Keynote scripting defects)
- Element geometry now applied via AppleScript after creation, because JXA position
  setters are silently discarded.
- Element lookup by text content instead of collection index, because JXA and AppleScript
  enumerate the same collection in different orders.
- Images located by insertion count, because Keynote reports the same `file name` for
  multiple images.
- Creation routed through JXA class constructors, because `make new image/table/movie`
  fail with `-10000` in Keynote 15.x.
- Export routed through JXA with the `Microsoft PowerPoint` enum (plain `PowerPoint` raises `-1700`).
- Native PDF export replaced by PNG composition: the native path either throws `-6` or writes
  blank pages.
