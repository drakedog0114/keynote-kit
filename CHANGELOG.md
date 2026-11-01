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

### Fixed (workarounds for Keynote scripting defects)
- Element geometry now applied via AppleScript after creation, because JXA position
  setters are silently discarded.
- Element lookup by text content instead of collection index, because JXA and AppleScript
  enumerate the same collection in different orders.
- Images located by insertion count, because Keynote reports the same `file name` for
  multiple images.
- Creation routed through JXA class constructors, because `make new image/table/movie`
  fail with `-10000` in Keynote 15.x.
- Export routed through JXA, because the AppleScript export path fails with `-6`.
