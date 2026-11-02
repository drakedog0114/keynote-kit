# Keynote 脚本踩坑手册

[English](gotchas.md) · **简体中文**

以下每一条都在 macOS 27.0.1 + Keynote Creator Studio 15.4 上复现过，
`keynote_kit` 内部已全部规避。

## 1. `make new image` / `make new table` / `make new movie` 全部失效

```applescript
make new image at end of s with properties {file:someFile}  --> error -10000
```

**解法**：用 JXA 的类构造器创建对象，再 `push` 进集合。

```javascript
const img = K.Image({file: Path("/tmp/a.png")});
slide.images.push(img);
```

视频尤其要注意：`make new movie` 不只是失败，它会**把 Keynote 卡死**（之后 AppleEvents 全部
`-1712` 超时，只能强杀进程）。

## 2. JXA 的 position setter 会被静默丢弃

```javascript
const t = K.TextItem({objectText: "hi"});
slide.textItems.push(t);
t.position = [120, 300];        // 不报错，也不生效
```

**解法**：JXA 创建，AppleScript 定位。

```applescript
set position of text item 1 of s to {120, 300}
set width of text item 1 of s to 700
```

顺序很重要：先设 `width`/`height`，**最后**设 `position`；否则盒子在定位后又被撑开，`y` 会漂移。

## 3. JXA 与 AppleScript 对同一集合的枚举顺序不同

`slide.textItems[0]` 不一定等于 AppleScript 的 `text item 1`，新建元素在两边也不落在同一位置。
任何基于索引的代码，只要页面上超过一个元素就会错位。

**解法**：按内容定位。

```applescript
repeat with itm in text items of s
  if (object text of itm as text) is "MARKER" then
    set target to itm
    exit repeat
  end if
end repeat
```

## 4. 图片的 `file name` 不可靠

一页上有多张图时，`image N file name` 会返回同一个值，无法用来匹配。

**解法**：`push` 是追加，所以新图是**最后一个** —— 用 `image (count of images)` 定位。

## 5. 空白版式里有"幽灵占位符"

用 `空白` 母版新建的页面，仍然带有两个 `0×0`、文本为空的文本项。它们会打乱所有索引，
让 `-1719 无效的索引` 随机出现。

**解法**：遍历元素时过滤掉"文本为空且尺寸为 0"的项。

## 6. Creator Studio 版本的原生导出不可靠

```applescript
export document 1 to file "/tmp/out.pdf" as PDF  --> error -6
```

- PDF：基本不可用。iwork-mcp 退回 Quick Look，但只渲染 1 页。
- 图片 / PowerPoint：走 **JXA** 可以，走 AppleScript 不行。

**解法**：一律用 JXA 导出；PDF 用逐页 PNG 再合成（`Deck.export_pdf()`）。

## 7. 母版（slide layout）是只读的

`slide layout` 虽然继承自 `slide`，但不可写：

```javascript
master.images.push(img)   // --> "cannot convert type" (-17000)
```

所以**没有任何脚本方式**能设置母版背景或单页背景填充。可选方案只有两个：
换主题（唯一受支持的"统一底图"手段），或在建页的第一时间插入整页背景图（靠顺序压在最底层）。

## 8. 改画布尺寸不会重排占位符

把 4:3 文档改成 1920 宽之后，占位符仍保留 1024 基准的坐标，整体偏左。重新套用版式也无效。

**解法**：手动重排每个占位符，或者干脆不用占位符（keynote-kit 的选择）。

## 9. 形状填充色没有接口

`shape` 只有 `opacity`，没有 `fill color`。需要彩色底块时用带 alpha 的 PNG 贴图——
顺带还能拿到圆角和描边。

## 10. 字体名必须是 PostScript 名，而且报错很晚

`SongtiSC-Bold` 会抛 `-1700`。本机可用的写法：
`Songti SC Bold`、`STSongti-SC-Regular`、`PingFangSC-Semibold`、`HiraginoSansGB-W6`。
非法字体名是在**样式阶段**才失败，元素已经建好了，所以务必校验。

## 11. 导出可能"成功"但什么都没写

`export` 可以在不抛异常的情况下不产出任何文件；PDF 甚至会产出页数正确但**页面空白**的文件。

**解法**：每次导出后校验产物存在且非空（`keynote_kit` 会抛 `KeynoteError`）。
PDF 不要信任原生路径，用 `Deck.export_pdf()`。

## 12. PowerPoint 的枚举名是 `Microsoft PowerPoint`

```javascript
d.export({ to: Path(p), as: "PowerPoint" })              // -1700 无法转换
K.export(d, { to: Path(p), as: "Microsoft PowerPoint" })  // 正常
```

另外调用形式也有讲究：`app.export(doc, {...})` 比 `doc.export({...})` 更稳。

## 13. 新文档天生带一页模板页

`make new document` 会用主题默认版式建一页。删掉最后剩下的那一页，Keynote 会自动再补一页。

**解法**：先把内容页都建好，最后再 `remove_slide(1)`。

## 文本样式必须作用在刚创建的那个对象上

`slide.textItems[slide.textItems.length - 1]` **不是**你刚 push 的那个元素——
JXA 枚举时，母版占位符排在 push 进去的元素之后，用下标取样式会静默套到占位符上。

```javascript
const ti = K.TextItem({ objectText: el.text });
slide.textItems.push(ti);
styleParas(ti, st);          // 用局部引用设样式，不要用集合下标
```

这是 `tools/test_capabilities.py` 查出来的：同页两个文本元素时，两个都变成了同一个默认字号。

## opacity 是百分比，不是小数

Keynote 的 `opacity` 属性取值 0~100。填 `0.4` 等于 0.4% 不透明（肉眼全白）。
`keynote_kit.animate.set_opacity` 收 0~1 并自动换算。

## Keynote 会丢弃 HYPERLINK 域之后的文字

粘贴 RTF 时，排在 `{\field ... HYPERLINK ...}` 之后的内容会被静默丢弃。
链接必须是**该段最后一个 run**。`build_rtf` 现在直接报错，不会让文字凭空消失。


## 四、缺字体会给 PPTX → Keynote 的还原度设天花板

字体是设计的一部分。跑 Keynote 的机器上没装这个字体时，**Keynote 和任何参考渲染器都会
静默替换成别的字体**，而两边的替代字体还不一样——于是像素比对量到的是「两个替代字体
的差异」，不是设计本身。

怎么查：

```bash
unzip -o deck.pptx -d /tmp/x
grep -oh 'typeface="[^"]*"' /tmp/x/ppt/slides/*.xml | sort | uniq -c | sort -rn
```

`HarmonyOS Sans SC` 免费且是 Apache-2.0 协议：
<https://github.com/huawei-fonts/HarmonyOS-Sans>
（压缩包走 Git LFS，要从 `media.githubusercontent.com/media/<owner>/<repo>/<ref>/<path>` 取）

## 五、JXA 集合下标 ≠ 「刚创建的那个元素」

两个 bug，同一个根因：

* `slide.textItems[slide.textItems.length - 1]` **不是**你刚 push 的那个文本框——
  母版占位符排在 push 进去的元素之后。改成对局部引用设样式。
* 两张配置相同的卡片会渲染出**同一个 PNG 文件名**，按文件名匹配就选错了元素，
  把它挪到了别的卡片的位置。

安全规则：

* **文本** → 按内容匹配，绝不按下标。
* **图片 / 卡片 / 图表** → 按**创建顺序**匹配。`slide.images` 的枚举顺序就是叠放顺序，
  也就是 push 的顺序，所以第 n 个创建的 = 池子里的第 n 个。

## 六、自动图形的填充色读不回来，重建会丢掉

重建出来的页面里，自动图形没有填充色——深色面板会变成白色。提取器会把它报成
`autoshape_nofill`。再加上不支持的自由曲线和被摊平的组合形状，
这就是**不建议重建设计稿**、建议原生导入的原因。

## 七、文字「装不下」是常态——文本框可以比文字矮

Keynote 的文本框不裁切，文字会往下溢出。很多稿子就是**故意**把 96pt 标题放在 60pt
的框里。一上来就用「文字是否装得进框」判断，会把它们全标成异常。
这正是 auto-fit 默认用 `"auto"` 的原因：只在文字会掉出画布、
或者溢出多行框超过 25% 时才动手。

## 九、驱动应用会占前台——但不该悄悄抢

RTF 粘贴是 Cmd+V 实现的，**只有 Keynote 在前台才有效**，没有后台粘贴这种接口。

所以 `keynote-kit` 默认**不抢前台**：

```python
from keynote_kit.runner import require_foreground
require_foreground()          # Keynote 不在前台 → 抛 ForegroundError，你的窗口一点没动
```

需要脚本自己接管时设 `KK_TAKEOVER=1`——验证脚本就是这么做的，
它们会先说明一声，跑完再把临时文稿全部关掉。

粘贴在发 Cmd+V 之前还会**再确认一次前台**，因为全屏应用可能在中途把焦点抢走；
抢走了就重新激活并重试，而不是把内容粘到别人的窗口里。
