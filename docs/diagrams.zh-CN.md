# 信息图数据结构

[English](diagrams.md) · **简体中文**

`kk_add_diagram`（以及 `keynote_kit.diagrams`）支持三种版式，输出 1920×1080 透明 PNG，
每次调用相当于插入一张图片。

## swimlane（泳道图）

| 字段 | 类型 | 说明 |
|---|---|---|
| `stages` | `string[]` | 列标题（阶段） |
| `lanes` | `[名称, string[]][]` | 每行一个角色；数组与 `stages` 对齐，`""` 表示空格 |
| `highlight` | `[行, 列][]` | 高亮单元格 |
| `title` / `subtitle` / `kicker` | `string` | 页眉文字 |
| `out` | `string` | 输出路径（服务端自动填） |

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

## hierarchy（层级图）

| 字段 | 类型 | 说明 |
|---|---|---|
| `rows` | `[名称, 说明][]` | 自上而下的层级，第一行会被强调 |
| `cards` | `[标签, 说明][]` | 右侧注解卡 |
| `title` / `subtitle` | `string` | 页眉文字 |

## integration（集成图）

| 字段 | 类型 | 说明 |
|---|---|---|
| `lanes` | `[名称, [方向, 说明, 是否双向][]][]` | 每个域的双端流向 |
| `left_label` / `right_label` | `string` | 两端标签 |
| `footer` | `string` | 底部说明 |
| `title` / `subtitle` | `string` | 页眉文字 |

`方向` 是含箭头的自由文本，例如 `"SAP → 零售平台"`；渲染器据此决定箭头方向与颜色，
`是否双向` 为 `true` 时画双向箭头。

## 配色

`keynote_kit.diagrams.PAPER` 对应 Keynote 的 `乳色纸`（米纸）主题，
`BLUE` 对应默认的 `白色` 主题。任何渲染函数都接受 `palette=` 参数切换。
