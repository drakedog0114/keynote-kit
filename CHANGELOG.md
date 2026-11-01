# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Planned
- MCP server wrapper (stdio) so any MCP client can call keynote-kit directly
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
