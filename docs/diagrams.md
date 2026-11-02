# Diagram specs

**English** · [简体中文](diagrams.zh-CN.md)

`kk_add_diagram` (and `keynote_kit.diagrams`) render three layout types to a transparent
1920×1080 PNG. Each tool call costs one image insertion.

## swimlane

| field | type | notes |
|---|---|---|
| `stages` | `string[]` | column headers |
| `lanes` | `[name, string[]][]` | one row per actor; items align with `stages`; `""` leaves a gap |
| `highlight` | `[row, col][]` | cells to emphasise |
| `title` / `subtitle` / `kicker` | `string` | header block |
| `out` | `string` | output path (filled by the server) |

```json
{
  "stages": ["① 扫码", "② 入驻", "③ 下单"],
  "lanes": [
    ["采购商", ["扫码", "传执照", "下单"]],
    ["系统", ["绑定", "校验", "注入价格"]]
  ],
  "highlight": [[0, 2]],
  "title": "端到端流程"
}
```

## hierarchy

| field | type | notes |
|---|---|---|
| `rows` | `[name, desc][]` | top-down levels, first row is emphasised |
| `cards` | `[tag, desc][]` | right-hand annotation cards |
| `title` / `subtitle` | `string` | header block |

## integration

| field | type | notes |
|---|---|---|
| `lanes` | `[name, [direction, desc, both][]][]` | two-system flows per domain |
| `left_label` / `right_label` | `string` | endpoint labels |
| `footer` | `string` | bottom note |
| `title` / `subtitle` | `string` | header block |

`direction` is free text containing an arrow, e.g. `"ERP → 平台"`; the renderer uses it to pick
the arrow direction and colour. `both: true` draws a double-headed arrow.

## Palette

`keynote_kit.diagrams.PAPER` matches the Keynote `乳色纸` (cream paper) theme;
`BLUE` matches the default `白色` theme. Pass `palette=` to any renderer to switch.
