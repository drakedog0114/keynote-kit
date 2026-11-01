# 视觉能力：圆角裁剪、溢出校正、层级、转场、超链接

[English](visuals.md) · **简体中文**

本文全部能力都经过实测（`tools/test_capabilities.py`，14 项断言全过）。

## 一、图片圆角 / 裁剪（预渲染）

Keynote 的图片对象没有裁剪、蒙版、圆角 API，所以效果在插入前就烤进 PNG。

```python
{"type": "image", "path": "photo.jpg", "box": [60, 160, 700, 350],
 "style": {"radius": 40}}                    # 圆角
{"type": "image", "path": "photo.jpg", "box": [60, 160, 700, 350],
 "style": {"shape": "ellipse"}}               # 圆形头像
{"type": "image", "path": "photo.jpg", "box": [60, 160, 700, 350],
 "style": {"crop": "cover", "focus": [0.5, 0.3]}}   # 填满并按焦点裁切
{"type": "image", "path": "photo.jpg", "box": [60, 160, 700, 350],
 "style": {"crop": "contain"}}                # 缩放留白（信箱）
```

单独调用：

```python
from keynote_kit.imaging import prepare_image
path = prepare_image("photo.jpg", [0, 0, 700, 350], radius=40, crop="cover")
```

产物按内容哈希缓存在 `~/.cache/keynote-kit/imaged/`。

## 二、文本溢出自动校正

Keynote 同样没有 autoFit。做法是按真实字体度量量出文字占多高，再把字号调小到装得下。

```python
{"type": "text", "text": long_copy, "box": [80, 300, 760, 150],
 "style": {"size": 42, "fit": True, "minSize": 12}}
```

`fitMode`：
- `shrink`（默认）—— 缩小字号，框不变
- `grow` —— 先尝试放大，放不下再缩

单独调用：

```python
from keynote_kit.imaging import fit_text, measure
measure(text, box, size=42)                # {"lines", "height", "overflow", ...}
fit_text(text, box, size=42, min_size=12)   # {"size": 30.5, "overflow": False, ...}
```

行高按 `字号 × 1.25` 估算（可用 `lineSpacing` 调整）。

## 三、z 序

Keynote 没有 z-index，但有两个事实让它可用：

1. **插入顺序就是层级**——最后插入的在上层。
2. 图片可以重建（知道源文件路径），文字不行（Keynote 不把富文本结构还回来）。

```python
from keynote_kit.animate import element_order, bring_to_front

element_order(doc, slide)                          # 页面有什么、在哪个集合里
bring_to_front(doc, slide, "image", 1, "/path.png") # 删掉再插入
```

文字元素要调层级，直接按 spec 重建整页——**spec 里的元素顺序就是 z 序**。

检查器的 **排列** 标签页还有 `最后 / 最前 / 向后 / 向前` 按钮（文字也能用）和 `成组 / 取消成组`。
试过用 UI 自动化点它们，但检查器的辅助功能树枚举会超时，所以这一条**保留为手动两下点击**。

## 四、转场、透明度、旋转（原生）

这三个一直是 API 自带的，只是以前没用上。

```python
from keynote_kit.animate import set_transition, set_opacity, set_rotation

set_transition(doc, slide, "magic move", duration=0.6, delay=0.0)
set_opacity(doc, slide, "image", 1, 0.4)      # 我们这边用 0~1
set_rotation(doc, slide, "image", 1, 30)      # 角度，顺时针
```

12 种转场：`magic move`、`shimmer`、`sparkle`、`swing`、`object cube`、`object flip`、
`object pop`、`object push`、`object revolve`、`object zoom`、`perspective`、
`no transition effect`。

⚠️ Keynote 的 `opacity` 是 **0~100 百分比**，`set_opacity` 收 0~1 并自动换算。

## 五、超链接

没有超链接 API，但 RTF 的 `HYPERLINK` 域会被导入成真链接。

```python
{"type": "rich", "box": [100, 300, 900, 140], "link": "https://www.ctf.com.cn",
 "paragraphs": [{"align": "left", "runs": [
     {"text": "点击访问乙品牌官网", "size": 34, "color": "#1F3A5F"}]}]}
```

**关键约束：链接必须是该段最后一个 run。** Keynote 会**静默丢弃** `HYPERLINK` 域之后的文字。
`build_rtf` 现在会直接报错，而不是让文字凭空消失。

## 六、构建动画（只能走 UI）

「逐个出现 / 飞入 / 构建顺序」**完全没有 API**（sdef 里只有页面转场）。
唯一路径是驱动 UI：

```python
from keynote_kit.animations_ui import (
    canvas_geometry, select_element, copy_animation, paste_animation)

canvas_geometry()                       # 画布位置与缩放
select_element(doc, slide, "image", 1)  # 点击选中元素
copy_animation(doc)                     # 格式 → 拷贝动画
select_element(doc, slide, "image", 2)
paste_animation(doc)                    # 格式 → 粘贴动画
```

「点击选中」已验证有效（右侧检查器会随之打开）。施加效果依赖检查器的控件树，
所以这个模块是 **opt-in、实验性**的——它只如实报告做了什么，不会假装成功。

实用流程：手工给一个对象设一次动效，再用 `copy_animation` / `paste_animation`
把它铺到本页其他对象上。
