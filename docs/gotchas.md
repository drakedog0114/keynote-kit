# Keynote scripting traps

Every entry was reproduced on macOS 27.0.1 + Keynote Creator Studio 15.4.
Each one is worked around inside `keynote_kit`.

## 1. `make new image` / `make new table` / `make new movie` are broken

```applescript
make new image at end of s with properties {file:someFile}  --> error -10000
```

**Workaround**: build the object with the JXA class constructor and `push` it into the collection.

```javascript
const img = K.Image({file: Path("/tmp/a.png")});
slide.images.push(img);
```

For movies this is also the *only* safe path — `make new movie` does not merely fail, it **hangs
Keynote permanently** (AppleEvents then time out with `-1712` until the app is force-quit).

## 2. JXA position setters are silently discarded

```javascript
const t = K.TextItem({objectText: "hi"});
slide.textItems.push(t);
t.position = [120, 300];        // no error, no effect
```

**Workaround**: create with JXA, place with AppleScript.

```applescript
set position of text item 1 of s to {120, 300}
set width of text item 1 of s to 700
```

Order matters: set `width` / `height` **before** `position`, otherwise the box grows after being
placed and the final `y` drifts by the height delta.

## 3. JXA and AppleScript enumerate collections in different orders

`slide.textItems[0]` in JXA is not necessarily `text item 1` in AppleScript, and newly created
items do not land at a predictable index across both APIs. Any index-based code breaks as soon as
a page has more than one element.

**Workaround**: address elements by content.

```applescript
repeat with itm in text items of s
  if (object text of itm as text) is "MARKER" then
    set target to itm
    exit repeat
  end if
end repeat
```

`keynote_kit` uses the element's text as the marker for text boxes and shapes.

## 4. `file name` is unusable for images

With several images on a slide, `image N file name` returns the same value for all of them, so
matching by filename is unreliable.

**Workaround**: `push` appends, so the newly inserted image is the *last* one —
address it as `image (count of images)`.

## 5. Empty layouts contain phantom placeholders

A slide created from the `空白` / `Blank` master still reports two text items with `0×0` size and
empty text. They shift every index and make `-1719 invalid index` errors appear at random.

**Workaround**: filter items with empty text **and** zero size when inspecting.

## 6. Native export fails on Creator Studio builds

```applescript
export document 1 to file "/tmp/out.pdf" as PDF  --> error -6
```

- PDF: effectively broken. iwork-mcp falls back to Quick Look, which only renders one page.
- Images / PowerPoint: work through **JXA** (`doc.export({to, as})`), fail through AppleScript.

**Workaround**: export via JXA; for PDF, render per-slide PNGs and assemble externally.

## 7. Master slides are read-only

`slide layout` inherits from `slide` but cannot be mutated:

```javascript
master.images.push(img)   // --> "cannot convert type" (-17000)
```

So there is **no scriptable way to set a master background or a per-slide background fill**.
Options: switch the document theme (the only supported background change), or insert a full-bleed
image at the moment the slide is created (before any other element) so it sits at the bottom.

## 8. Changing canvas size does not reflow placeholders

After `width = 1920` on a 4:3 document, placeholders keep their 1024-based coordinates and are no
longer centred. Re-applying the master layout does not fix it either.

**Workaround**: reposition every placeholder manually, or avoid placeholders entirely (what
`keynote_kit` does).

## 9. Shape fill colour is not exposed

There is no `fill color` on `shape`; only `opacity`. Colourful panels must be inserted as images
(PNG with alpha), which also gives rounded corners and borders for free.

## 10. Font names are PostScript names, and wrong ones fail late

`SongtiSC-Bold` raises `-1700`. Working names observed on this system:
`Songti SC Bold`, `STSongti-SC-Regular`, `PingFangSC-Semibold`, `HiraginoSansGB-W6`.
An invalid name fails at *style* time, after the element was created — hence always verify.

## 11. Export silently produces nothing — or blank pages

`export` can return without raising while writing no file at all. And when PDF export *does*
succeed, it can produce a file with the right page count but **blank pages**.

**Workaround**: after every export, assert the artefact exists and is non-trivial
(`keynote_kit` does this and raises `KeynoteError`). For PDF, do not trust the native path —
`Deck.export_pdf()` renders per-slide PNGs and assembles them with Pillow.

## 12. The PowerPoint enum is `Microsoft PowerPoint`

```javascript
d.export({ to: Path(p), as: "PowerPoint" })            // -1700 cannot convert
K.export(d, { to: Path(p), as: "Microsoft PowerPoint" }) // works
```

Also note the call form: `app.export(doc, {...})` is more reliable than `doc.export({...})`.

## 13. A new document always ships with one template slide

`make new document` creates a slide using the theme's default layout. Deleting the last remaining
slide simply recreates it. Add your content pages first, then `remove_slide(1)`.
