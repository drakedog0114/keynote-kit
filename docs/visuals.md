# Visual capabilities: rounding, cropping, auto-fit, z-order, transitions, links

**English** · [简体中文](visuals.zh-CN.md)

Everything here was verified against Keynote 15.4 (`tools/test_capabilities.py`, 14 checks).

## 1. Image rounding / cropping — pre-rendered

Keynote has no crop, mask or corner-radius API for images, so the effect is baked into the
PNG before it is inserted.

```python
{"type": "image", "path": "photo.jpg", "box": [60, 160, 700, 350],
 "style": {"radius": 40}}                    # rounded corners
{"type": "image", "path": "photo.jpg", "box": [60, 160, 700, 350],
 "style": {"shape": "ellipse"}}               # circular avatar
{"type": "image", "path": "photo.jpg", "box": [60, 160, 700, 350],
 "style": {"crop": "cover", "focus": [0.5, 0.3]}}   # fill the box, crop around a focus
{"type": "image", "path": "photo.jpg", "box": [60, 160, 700, 350],
 "style": {"crop": "contain"}}                # fit inside, letterbox
```

Standalone:

```python
from keynote_kit.imaging import prepare_image
path = prepare_image("photo.jpg", [0, 0, 700, 350], radius=40, crop="cover")
```

Results are cached by content hash under `~/.cache/keynote-kit/imaged/`.

## 2. Text overflow auto-fit

Keynote has no autoFit property either. The text is measured with the real font metrics and
the font size is reduced until it fits.

```python
{"type": "text", "text": long_copy, "box": [80, 300, 760, 150],
 "style": {"size": 42, "fit": True, "minSize": 12}}
```

`fitMode`:
- `shrink` (default) — reduce the font size, keep the box
- `grow` — first try a larger size, then shrink

Standalone:

```python
from keynote_kit.imaging import fit_text, measure
measure(text, box, size=42)          # {"lines", "height", "overflow", ...}
fit_text(text, box, size=42, min_size=12)   # {"size": 30.5, "overflow": False, ...}
```

Line height uses `size × 1.25` by default (override with `lineSpacing`).

## 3. z-order

Keynote exposes no z-index. Two facts make it workable:

1. **Insertion order is the stacking order** — the element inserted last is on top.
2. Images can be re-created (their source path is known), text cannot be re-created
   (Keynote will not give the rich-text structure back).

```python
from keynote_kit.animate import element_order, bring_to_front

element_order(doc, slide)              # what is on the page, and in which collection
bring_to_front(doc, slide, "image", 1, "/path/to/image.png")   # delete + re-insert
```

For text elements, rebuild the page from its spec instead — the element order in the spec
*is* the z-order.

The inspector's **Arrange** tab also has `Front` / `Back` / `Forward` / `Backward` buttons
that work for text, and `Group` / `Ungroup`. Automating them was attempted but the
accessibility tree of the inspector is slow enough that enumeration times out, so they stay
a manual two-click operation.

## 4. Transitions, opacity, rotation — native

These were always in the API; they were simply never used.

```python
from keynote_kit.animate import set_transition, set_opacity, set_rotation

set_transition(doc, slide, "magic move", duration=0.6, delay=0.0)
set_opacity(doc, slide, "image", 1, 0.4)      # 0~1 on our side
set_rotation(doc, slide, "image", 1, 30)      # degrees, clockwise
```

Twelve transition effects exist: `magic move`, `shimmer`, `sparkle`, `swing`,
`object cube`, `object flip`, `object pop`, `object push`, `object revolve`,
`object zoom`, `perspective`, `no transition effect`.

Note: Keynote's `opacity` is a **0–100 percentage**; `set_opacity` takes 0–1 and converts.

## 5. Hyperlinks

There is no hyperlink API, but the RTF `HYPERLINK` field is imported as a real link.

```python
{"type": "rich", "box": [100, 300, 900, 140], "link": "https://www.ctf.com.cn",
 "paragraphs": [{"align": "left", "runs": [
     {"text": "点击访问乙品牌官网", "size": 34, "color": "#1F3A5F"}]}]}
```

**Key constraint: the link must be the last run of the paragraph.** Keynote silently drops
everything that follows a `HYPERLINK` field. `build_rtf` raises an error instead of letting
text disappear.

## 6. Build animations — UI only

"Appear / fly in / build order" has **no API at all** (the sdef only knows slide transitions).
The only route is driving the UI:

```python
from keynote_kit.animations_ui import canvas_geometry, select_element, copy_animation, paste_animation

canvas_geometry()                      # where the canvas is and the zoom level
select_element(doc, slide, "image", 1) # click the element to select it
copy_animation(doc)                    # 格式 → 拷贝动画
select_element(doc, slide, "image", 2)
paste_animation(doc)                   # 格式 → 粘贴动画
```

Selection by clicking is verified to work (the inspector opens on the selected object).
Applying an effect depends on the inspector's control tree, which is why this module is
**opt-in and experimental** — it reports what it did instead of pretending to succeed.

Practical workflow: set the animation once by hand, then use `copy_animation` /
`paste_animation` to spread it to the other objects on the slide.
