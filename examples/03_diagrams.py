"""信息图示例：泳道图 / 层级图 / 集成图，渲染后插入 Keynote。

    python examples/03_diagrams.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from keynote_kit import Deck, diagrams

Path = pathlib.Path
OUT = Path("out")
OUT.mkdir(exist_ok=True)

flow = diagrams.swimlane(
    stages=["① 扫码绑定", "② 入驻认证", "③ 审核与资质", "④ 看价选品", "⑤ 下单支付"],
    lanes=[
        ("采购商 / 员工", ["扫码进店", "上传执照", "", "看专属价", "现付 / 记账"]),
        ("区域负责人", ["发展合伙人", "收集资料", "初审", "调价申请", "代客下单"]),
        ("总部运营", ["配置区域", "配置模板", "审核打标签", "配采购价", "审核退款"]),
        ("系统 / SAP", ["绑定归属", "OCR + 工商核验", "资质商品映射", "注入采购价", "订单同步 SAP"]),
    ],
    highlight={(0, 3), (0, 4), (3, 3)},
    title="端到端：一次采购的全链路",
    subtitle="四条泳道 · 五个阶段 · 高亮为定制点",
    out=str(OUT / "flow.png"),
)

org = diagrams.hierarchy(
    rows=[
        ("总部运营", "审核资料 · 维护商品与采购价 · 处理异常"),
        ("区域负责人", "区域 = 网店 / 分销员组"),
        ("合伙人", "分销员承接 · 发展采购商 · 佣金"),
        ("采购商 / 员工", "B2B 多员工账号 · 数据互通"),
    ],
    cards=[
        ("定制", "B2B 准入 / 多员工 / 专属采购价"),
        ("标品 + 适配", "区域划分 / 分销员 / 佣金"),
        ("标品复用", "商品浏览 / 交易 / 售后"),
    ],
    title="五类角色，权限逐层收敛",
    subtitle="组织层级：总部 → 区域 → 合伙人 → 采购商",
    out=str(OUT / "org.png"),
)

sap = diagrams.integration(
    lanes=[
        ("商品", [("ERP → 平台", "主数据增量同步（SKU / 规格 / 分类）", False),
                  ("平台 → ERP", "映射异常回执，不静默建重复商品", False)]),
        ("库存", [("ERP → 平台", "可售库存基准", False),
                  ("平台自维护", "下单预占 · 取消释放 · 定时对账", True)]),
        ("订单", [("平台 → ERP", "支付成功幂等推送", False),
                  ("ERP → 平台", "发货回传 · 退款双向对账", True)]),
    ],
    title="SAP 对接：三通一幂等",
    subtitle="零售平台侧只保证接口幂等；SAP 能力不追问、不承担",
    left_label="SAP",
    right_label="零售平台连锁商城",
    footer="兜底：失败重试 · 告警 · 人工补偿入口；日常对账覆盖遗漏与重复",
    out=str(OUT / "integration.png"),
)

deck = Deck.create(theme="乳色纸")
for path in (org, flow, sap):
    slide = deck.add_slide("空白")
    deck.add_image(slide, path, 0, 0, 1920, 1080)

deck.export(str(OUT / "diagrams"), "images")
print("导出 →", OUT / "diagrams")
