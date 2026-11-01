"""端到端：6 页，覆盖全部元素类型，测时间与稳定性。"""
import sys, time
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from keynote_kit import Deck
from keynote_kit.page import apply_page

P, INK, MID, NAVY = "#F4EBDD", "#2B2420", "#6E6259", "#1F3A5F"

def card(x, y, w, h, title, body, fill="#FFFFFF", tcol=INK, bcol=MID, border=None):
    st = {"fill": fill, "radius": 26}
    if border: st.update({"border": border, "borderWidth": 2})
    return {"type": "card", "box": [x, y, w, h], "style": st,
            "text": {"title": title, "body": body, "titleSize": 28, "bodySize": 16,
                     "titleColor": tcol, "bodyColor": bcol, "padding": 34, "gap": 14, "valign": "center"}}

pages = [
 {"background": {"type":"solid","color":P}, "elements":[
   {"id":"k","type":"text","text":"END-TO-END · 6 PAGES","box":[150,300,1600,50],"style":{"size":22,"color":MID}},
   {"id":"t","type":"text","text":"声明式\n建完整稿","box":[150,370,1500,320],"style":{"size":96,"font":"Songti SC Bold","color":INK}},
   {"id":"s","type":"text","text":"text · card · chart · diagram · image · table","box":[150,760,1600,50],"style":{"size":26,"color":NAVY}}]},
 {"background": {"type":"solid","color":P}, "elements":[
   {"id":"t","type":"text","text":"四种元素一页装下","box":[150,90,1620,90],"style":{"size":48,"font":"Songti SC Bold","color":INK}},
   card(150,220,500,340,"卡片","圆角、填充、内嵌文字一次搞定。","#FFFFFF"),
   card(710,220,500,340,"深色卡","反色文字 + 深色底，无需额外处理。",NAVY,"#FFFFFF","#C9D2E0"),
   {"id":"ch","type":"chart","box":[150,600,1060,400],"chart":{"kind":"bar","labels":["A","B","C"],"values":[18,26,22],"title":"模块工作量"}},
   card(1270,600,500,200,"状态","全部类型已覆盖。","#FFFFFF",border="#D9CFBE")]},
 {"background": {"type":"solid","color":P}, "elements":[
   {"id":"t","type":"text","text":"表格页","box":[150,90,1620,90],"style":{"size":48,"font":"Songti SC Bold","color":INK}},
   {"id":"tb","type":"table","box":[150,230,1620,420],"data":[
     ["能力","改造前","改造后"],["单页调用","8–12 次","1 次"],["背景","无","可用"],
     ["校验","无","回读+回滚"],["元素类型","4 种","6 种"]]}]},
 {"background": {"type":"solid","color":P}, "elements":[
   {"id":"dg","type":"diagram","box":[130,110,1660,900],"diagram":{
     "kind":"swimlane","title":"流程页","subtitle":"泳道 · 三阶段",
     "stages":["① 扫码","② 入驻","③ 下单"],
     "lanes":[["采购商",["扫门店码","上传执照","选品下单"]],["系统",["绑定门店","资质校验","注入价格"]]],
     "highlight":[[1,2]]}}]},
 {"background": {"type":"solid","color":P}, "elements":[
   {"id":"t","type":"text","text":"三卡总结","box":[150,90,1620,90],"style":{"size":48,"font":"Songti SC Bold","color":INK}},
   card(150,230,500,600,"一次调用","整页一个 spec，元素顺序即 z 序。"),
   card(710,230,500,600,"写完即校验","位置偏差 >20pt 直接回滚。",NAVY,"#FFFFFF","#C9D2E0"),
   card(1270,230,500,600,"可反向","kk_extract_page 把页面读回 spec。","#FFFFFF")]},
 {"background": {"type":"solid","color":P}, "elements":[
   {"id":"t","type":"text","text":"「描述结果，\n而不是步骤。」","box":[150,380,1600,300],"style":{"size":84,"font":"Songti SC Bold","color":INK}},
   {"id":"s","type":"text","text":"keynote-kit / declarative pages","box":[150,720,1200,50],"style":{"size":24,"color":MID}}]},
]

d = Deck.create(theme="乳色纸")
for _ in range(len(pages)):
    d.add_slide("空白")
t_all = time.time(); times = []
for i, spec in enumerate(pages, start=1):
    t0 = time.time(); r = apply_page(d, i, spec); dt = time.time() - t0
    times.append(dt); print(f"P{i} {r['elements']:>2} 元素 {dt:.2f}s")
print(f"\n总计 {time.time()-t_all:.1f}s | 平均 {sum(times)/len(times):.2f}s/页")
d.save(__import__("os").path.expanduser("~/Desktop/声明式端到端-6页.key"))
d.export("/tmp/e2e", "images")
print("saved")
