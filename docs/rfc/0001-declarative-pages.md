# RFC 0001 · 用「声明式页面」重做 keynote-kit 的编辑模型

状态：**草案（待评审）** · 2026-11-01 · 作者：Drakedog + DeepSeek Harness

---

## 1. 为什么要改

现在的 keynote-kit 是**命令式**的：41 个 MCP 工具，每个只干一件事（加文本、加形状、改样式、对齐……）。
这是照着 iwork-mcp 的形状抄的，而 iwork-mcp 本身又是照着 AppleScript 的原子动词抄的。

做完飞书 Slides 的对照测试后，问题很清楚了：

| 症状 | 根因 |
|---|---|
| 生成一页要 8–12 次调用，token 与时间都浪费 | 没有一个"整页"的原语 |
| 出错时不知道错在哪（`-1728`、`-1719`） | 错误没有上下文 |
| 写成功后内容可能丢（静默失败） | 没有事务 / 回读 |
| 同一页反复改会互相踩 | 没有版本或结构指纹 |
| 每个调用方都要自己算坐标和 z 序 | 没有布局层 |

飞书的 SML 恰好是**声明式**的：一页就是一段 XML，元素顺序即 z 序，样式是属性，
提交后有 `revision_id`。这套模型在工程上明显更稳。

**所以迭代方向不是"再加 10 个工具"，而是换一层抽象。**

---

## 2. 目标（可验收）

| 指标 | 现在 | 目标 |
|---|---|---|
| 生成一页 PPT 的调用次数 | 8–12 次 | **1 次**（`kk_page`） |
| 单页生成耗时 | 3–5 s | **< 1.5 s** |
| 静默失败率 | 有（图片路径错、索引错） | **0**（写后校验，失败即回滚） |
| MCP 工具数 | 41 | **≤ 14** |
| 错误信息 | `Keynote error -1728` | `NotFound: 第 3 页没有文本元素"标题"` |
| 页面背景 | 不支持 | 支持（仿真实现） |

---

## 3. 核心设计：把页面变成数据

### 3.1 Page Spec（新的一等公民）

```json
{
  "slide": 4,
  "background": { "type": "solid", "color": "#F7F5F0" },
  "elements": [
    { "type": "text", "id": "title", "text": "五类角色，权限逐层收敛",
      "box": [140, 110, 1640, 150],
      "style": { "size": 56, "font": "Songti SC Bold", "color": "#2B2420", "align": "left" } },

    { "type": "text", "id": "body", "text": "总部运营：…\n区域负责人：…",
      "box": [140, 300, 1640, 640],
      "style": { "size": 26, "color": "#2B2420", "lineSpacing": 1.35 } },

    { "type": "image", "id": "chart", "path": "/tmp/bar.png", "box": [110, 280, 860, 480] },

    { "type": "table", "id": "t1", "box": [150, 600, 1620, 420],
      "data": [["业务域", "承接"], ["准入", "全定制"]],
      "style": { "size": 16, "headerColor": "#1F3A5F" } }
  ]
}
```

**元素顺序 = z 序**（先插入的在下面），这一条直接抄飞书——它解决了 Keynote 没有 z 序 API 的问题：
既然只能靠插入顺序控制层级，那就把顺序变成规范。

### 3.2 一个工具做完整页

```
kk_page(doc, slide, spec)  →  { ok, slide, applied, verified, revision }
```

内部执行链（全部在一处完成，调用方看不见）：

```
1. 事务开始：快照当前页元素（类型/位置/文本）
2. 清空或保留（mode: replace | append）
3. 背景：渲染纯色/图片 PNG → 作为第一张图插入（保证在最底层）
4. 逐元素：JXA 创建 → AppleScript 定位 → JXA 样式（按内容匹配，不靠索引）
5. 回读校验：元素数量 + 每个元素的位置/尺寸在容差内
6. 不符 → 删除本次新增元素 → 抛错（回滚）
7. 计算页面指纹，写入 revision
```

### 3.3 样式模型统一（顺手修掉 format_shape）

现在 `format_shape` 会报 `-1728`，因为它在索引上找元素。新模型里：

- 所有样式通过一个 `apply_style(element, style)` 完成
- 元素定位一律**按内容匹配**（文本内容 / 文件 basename），不用索引
- 字体名做白名单校验（`Songti SC Bold` 合法、`SongtiSC-Bold` 非法），非法时给出建议值

### 3.4 背景：用"底层图"仿真

Keynote 没有页面背景 API，但**插入顺序 = 层级**，所以：

```
background(solid #F7F5F0) → 生成 1×1 或 8×8 的 PNG（按色值缓存）→ 拉伸到整页 → 第一个插入
```

这让 keynote-kit 第一次具备"每页独立背景"的能力——和飞书对齐。
缓存放在 `~/.cache/keynote-kit/bg/<hex>.png`，避免重复 IO。

### 3.5 错误语义化

| Keynote 原始错误 | 映射 | 附带信息 |
|---|---|---|
| `-1728` 不能获取对象 | `NotFound` | 文档名 / 页码 / 元素 id |
| `-1719` 无效的索引 | `IndexOutOfRange` | 页码 / 元素数 / 请求索引 |
| `-10000` 处理程序失败 | `VerbUnsupported` | 该动词在 15.x 已损坏，给出替代写法 |
| `-1700` 不能转换类型 | `Coercion` | 通常是字体名或枚举值写错，给出合法候选 |
| 文件不存在 | `MissingAsset` | 路径 + 是否相对路径 |

---

## 4. 工具面收敛：41 → 12

| 新工具 | 取代 | 说明 |
|---|---|---|
| `kk_page` | add_text/add_shape/add_image/add_table/set_background/align… | **主力**，整页声明式 |
| `kk_inspect` | inspect_slide / list_slides | 读回结构 |
| `kk_doc` | create/open/close/save/list | 文档生命周期 |
| `kk_theme` | list_themes / set_theme / list_layouts | 主题与版式 |
| `kk_export` | export / export_pdf | 导出（含 PNG 合成 PDF） |
| `kk_compress` | tools/compress_deck.py | 体积压缩（已有，收进 MCP） |
| `kk_verify` | verify | 结构校验 |
| `kk_chart` | add_chart | 出图（matplotlib） |
| `kk_diagram` | add_diagram | 泳道/层级/集成图 |
| `kk_slideshow` | start/stop | 放映 |
| `kk_revision` | — | 页面指纹与乐观锁 |
| `kk_info` | server_info | 版本与能力 |

旧的 41 个工具**保留但标记 deprecated**，一个版本后移除。

---

## 5. 分阶段落地

### P0 · 地基（预计 1.5 天）

1. `PageSpec` 数据模型 + JSON Schema 校验
2. `apply_page()` 事务实现（含回滚）
3. 样式统一走 `apply_style()`，修掉 `format_shape`
4. `kk_page` 工具 + 回读校验
5. 单元测试：10 个 page spec 快照对比

**验收**：用 `kk_page` 重建某宠物品牌 v3 的 15 页，逐页与现有版本像素比对，差异 < 1.0。

### P1 · 背景与错误（1 天）

6. 背景仿真 + 色彩缓存
7. 错误语义化 + 字体白名单校验
8. `kk_revision` 结构指纹

### P2 · 工具面收敛（1 天）

9. 12 个工具上线，41 个标记 deprecated
10. CLI 增加 `keynote-kit page --spec page.json`
11. 文档重写（README + mcp-server.md 以 `kk_page` 为主线）

### P3 · 对齐飞书的能力补位（按需）

12. 图表数据 → PNG 的缓存（同数据不重复渲染）
13. 页面模板（`layout: "cover" | "cards" | "table" | "chart"`）——高级封装，内部仍编译成 elements

---

## 6. 风险与不做的事

| 风险 | 应对 |
|---|---|
| Keynote 的 `-10000` 类错误可能让 App 卡死 | 事务前先 `verify` 文档存活；连续 2 次超时即中止并提示重启 |
| 全文匹配定位在同页重复文本时会歧义 | spec 里强制 `id` 唯一；同文本追加序号后缀 |
| 背景图会让文件变大 | 纯色背景用 8×8 PNG，几乎零成本 |
| 声明式模型掩盖了 Keynote 的坑 | 每个 spec 元素对应一份"操作履历"，出问题能打印实际执行序列 |

**明确不做**：

- 不做"像素级还原飞书 SML"——Keynote 没有 chart/背景/单元格底色，硬做只会更难维护
- 不引入模板引擎（Jinja 之类）——JSON spec 已经够表达，模板语言会让 agent 更难用对
- 不追求 1:1 兼容 iwork-mcp 的调用约定——那套是历史包袱

---

## 7. 一个直观对比

同样是"三卡 + 标题"一页：

**现在（9 次调用）**
```
add_slide → add_text ×2 → add_image → position_item ×4 → align_items → verify
```

**改造后（1 次调用）**
```json
kk_page(doc, 3, {
  "elements": [
    {"type":"text","text":"三个补齐点","box":[150,120,1200,100],"style":{"size":56,"font":"Songti SC Bold"}},
    {"type":"image","path":"cards.png","box":[150,330,1560,340]},
    {"type":"text","text":"精确排版","box":[190,380,400,60],"style":{"size":38}},
    {"type":"text","text":"原生表格","box":[730,380,400,60],"style":{"size":38}},
    {"type":"text","text":"图表能力","box":[1270,380,400,60],"style":{"size":38}}
  ]
})
```

调用方只需要想"这页长什么样"，不需要想"先加什么后加什么"。

---

## 8. 待确认

1. 工具面从 41 收敛到 12，是否接受旧工具的破坏性变更？（建议：保留一个版本 + deprecated 警告）
2. 背景仿真用纯色图，是否够用？还是需要支持整页图片背景（已支持，但需要显式 path）
3. P0 的验收标准（用 `kk_page` 重建某宠物品牌 15 页并要求像素一致）是否合适？

---

## 9. 实测结果（P0 已落地，2026-11-01）

实现位置：`keynote_kit/page.py` + MCP 工具 `kk_page` / `kk_page_validate`。

### 9.1 达成的

| 项 | 结果 |
|---|---|
| 单页调用次数 | **1 次 `kk_page`**（原 8–12 次） |
| 写后校验 | 自动回读，位置偏差 > 20pt 即报错 |
| 回滚 | `mode=replace` 时校验失败会清空本页；spec 非法则不写入 |
| 每页背景 | **可用**（纯色 8×8/192×108 PNG 缓存 + 整页图，或直接给图片） |
| 元素顺序 = z 序 | 可用（先插背景，再按 spec 顺序） |
| 表格 | 可用（原生表格 + 单元格写入） |

### 9.2 实测耗时（12 页测试稿，含背景）

| 页型 | 元素数 | 耗时 |
|---|---|---|
| 封面（标题+副标题+背景） | 3–4 | 2.1–3.7 s |
| 三卡页 | 11 | 4.7–7.6 s |
| 表格页 | 3 | 2.0–5.3 s |

**每元素约 0.4–0.6 s**，与元素数近似线性。

### 9.3 没达成的（重要）

1. **1.5 s/页 的目标不现实**。瓶颈不是 AppleEvent 数量，而是 Keynote 对每个元素的
   版面重算：几何设值本身只 0.12 s/元素，但叠加创建+样式+回读后稳定在 0.4–0.6 s/元素。
   目标修正为：**≤6 元素 ≤2.5 s；每元素 ≤0.6 s**。
2. **工具面收敛（41→12）未做**，当前 43 个（新增 2 个），旧工具仍在。
3. **文本对齐不可设**：`alignment` 只有表格单元格支持，text item 报 -1700，
   新建文本会继承主题的默认对齐（居中）。
4. **形状没有填充色**：Keynote 没有 shape fill API，`type: "shape"` 目前只能当描边空盒，
   彩色卡片必须用 PNG（`charts` / `diagrams` 或预渲染）。

### 9.4 过程中确认的三个 Keynote 行为

- **JXA 设 `position` 静默失效**（返回 ok，读回 0,0），几何必须走 AppleScript。
- **JXA 与 AppleScript 看到的集合顺序不同**：JXA 认为新元素在末尾，AppleScript 里
  占位符可能排在后面。所以不能跨语言复用索引，只能在 AppleScript 内部匹配。
- **`object text of text items of s` 逐项读取很贵**（每项一次事件）；
  用 `as list` + 文本项分隔符一次取回，再在 Python 侧匹配，是唯一快且稳的路径。

### 9.5 下一步（P1）

1. 加 `type: "card"`：按颜色/圆角/尺寸渲染 PNG 卡片（补上 Keynote 没有填充色的缺口）
2. 文本对齐：尝试 paragraph 层属性或主题占位符，失败则记录为已知限制
3. 工具面收敛到 12 个，旧工具标记 deprecated
4. 用 `kk_page` 重建某宠物品牌 v3 的 15 页做回归
