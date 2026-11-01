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
