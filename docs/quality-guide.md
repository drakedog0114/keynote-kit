# Output quality guide (editability first)

The goal has shifted: **editability + typographic precision** first, throughput second.
Below is the decision table for "which element, when" under that priority.

## Decision table

| What you are making | Use | Editable | Why |
|---|---|---|---|
| Cover title, section title | `text` + `slot:"title"` | ✅ | Inherits the master's size / font / position |
| Body paragraphs, bullet lists | `text` + `slot:"body"` | ✅ | Inherits bullets, left alignment, paragraph spacing |
| A text block at a custom position | `text` (bare text box) | ✅ | But **alignment can only be centred** — Keynote does not expose it |
| Coloured cards, panel containers | `card` | ❌ (text is rasterised) | Keynote shapes have no fill API |
| Data charts | `chart` | ❌ | Rendered with matplotlib |
| Flow diagrams / swimlanes | `diagram` | ❌ | Same |
| Screenshots, photos | `image` | ❌ | They are images to begin with |
| Structured data | `table` | ✅ | Native table, cells stay editable |

## Three hard rules

1. **Use a slot whenever you can.** A bare text box cannot be aligned
   (`alignment` is only exposed for table cells; text items and paragraphs both
   return -1700), so it centres by default and long paragraphs look bad.
2. **Do not clear a slot page, and do not insert a full-page background.**
   Placeholders sit at the very bottom of the layer stack, so any full-page image
   inserted later covers them. Leave the background to the master.
3. **Cards are decoration only.** They bake the text into a PNG, so the client
   cannot edit the copy. Anything whose wording may change belongs in a slot.

## Verified negative results (do not try these again)

| Attempted | Result |
|---|---|
| `set alignment of text item` / `paragraph` | -1700, type conversion fails |
| Assigning RTF straight to `object text` | -1700, rich text does not accept RTF data |
| RTF via clipboard + Cmd+V | Pastes, but the landing spot is unpredictable (it overwrites the current placeholder) |
| `duplicate text item` to copy a placeholder | -1700 / shape error, unsupported |
| `make new text item` | -10000, the verb is broken |

Conclusion: **Keynote gives you exactly two themed text styles (title / body)**. To get
more left-aligned editable text blocks you have to put extra placeholders in the master
(a custom layout) — the scripting side cannot invent them.

## Pre-delivery checklist

- [ ] Is all body copy inside slots (rather than bare centred text)?
- [ ] Are images stretched? `apply_page` fixes the height proportionally, but a box that is
      too narrow still crops
- [ ] Do charts bleed to the edge? After trimming transparency the content really fills the box
- [ ] Does the card copy need to be edited in Keynote? If yes, use a slot instead
- [ ] Look at the exported PNGs page by page — do not just check that the file opens

## And for decks you did not author

Do **not** rebuild a designed deck. Import it (seconds, ~95 % fidelity), then change its
**content** with `tools/replace_text.py`, which preserves every paragraph's size, font and
colour. See [client-swap.md](client-swap.md).

Two things to check before trusting a fidelity number:

- **Fonts.** If the deck's fonts are not installed, both Keynote and a reference renderer
  substitute different fallbacks, so the comparison measures the fallbacks, not the design.
- **Auto-shape fills.** A rebuild cannot read them back, so dark panels come out white —
  another reason to import instead of rebuild.
