"""Isolated, read-only visual acceptance page for weekend lesson 10 example 16.

Start only with: uvicorn preview_calendar:app --host 0.0.0.0 --port $PORT
Never imports the production app, opens its database, or accesses live lesson data.
This is a representative fixture rendered with the project's actual courseware JS.
"""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from changying.web.weekend_courseware_pages import COURSEWARE_JS
from changying.web.weekend_courseware import _repair_courseware_visual

app = FastAPI(title="长缨辅学 · 课件验收预览", docs_url=None, redoc_url=None, openapi_url=None)

_CASES = [
    {"kind": "steps", "params": {
        "title": "例题11 · 顺推与逆推", "problem": "输入数a，先除以0.5，再加b，输出是多少？",
        "steps": ["观察流程图，找出输入和输出的位置。", "先试着描述每个运算框做了什么。", "写出第一个运算后的式子，再完成第二步。", "从输出反推一次，检验你的式子。"],
        "answer": "2a+b", "figure": {"type": "flow", "boxes": ["输入 a", "÷ 0.5", "+ b", "输出"], "branches": []}}},
    {"kind": "steps", "params": {
        "title": "例题13 · 中点问题", "problem": "B是线段AD上的动点，C、E分别是BD、AB的中点，EC是否会变化？",
        "steps": ["观察A、E、B、C、D的相对位置。", "分别找出AB和BD的中点，写出对应长度关系。", "B移动时，哪些线段长度会一起变化？", "把关系合并，检验EC与AD有什么联系。"],
        "answer": "EC始终等于AD的一半", "figure": {"type": "segment", "points": [
            {"name": "A", "at": 0}, {"name": "E", "at": 4}, {"name": "B", "at": 8},
            {"name": "C", "at": 10}, {"name": "D", "at": 12}], "marks": []}}},
    {"kind": "steps", "params": _repair_courseware_visual(
        {"title": "例题16 · 月历框形辨析",
         "problem": "月历中行间相差7。A一行四格；B 2×2格；C竖列三格写成x−20、x−10、x；D十字形周边写成x−8、x−7、x−6、x+6、x+7、x+8。哪一种错误？",
         "answer": "C：竖向三格应为x−14、x−7、x",
         "steps": ["观察月历", "比较不同框形", "用x表达日期", "独立判断"], "figure": {}},
        "月历框形辨析：哪一种错误？") }
]

@app.get("/health")
def health():
    return {"status": "ok", "preview": True}


@app.get("/", response_class=HTMLResponse)
def calendar_preview():
    payload = json.dumps(_CASES, ensure_ascii=False)
    # Keep the injected data as executable-safe JavaScript literals.
    payload = payload.replace("<", "\\u003c")
    javascript = COURSEWARE_JS.replace("</", "<\\/")
    return HTMLResponse(
        """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>长缨辅学 · 数学例题交互对比验收 V2</title>
<style>
body{font-family:system-ui,-apple-system,"Microsoft YaHei",sans-serif;margin:0;background:#eef3f9;color:#102238}
main{max-width:1030px;margin:30px auto;padding:0 16px}
header{background:#173e75;color:white;padding:20px 24px;border-radius:14px}
header h1{font-size:22px;margin:0 0 5px}header p{font-size:13px;opacity:.9;margin:0}
.tabs{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0 8px}.tabs button{border:2px solid #b9cce3;background:white;border-radius:10px;padding:12px 18px;cursor:pointer;font-weight:700}.tabs button.active{border-color:#2563eb;background:#dbeafe;color:#153c78}.lead{background:#e6f3ff;border-left:4px solid #2563eb;padding:12px 14px;margin:14px 0;border-radius:8px}.version{background:#c6f6d5;color:#164a2a;font-weight:800;border-radius:20px;padding:4px 12px;display:inline-block}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}
.toolbar button{border:1px solid #92a9c7;background:#fff;color:#163c70;border-radius:8px;padding:10px 16px;cursor:pointer}
.toolbar button:focus-visible{outline:3px solid #2563eb}
#stage{background:white;border-radius:14px;border:1px solid #dbe4f0;padding:16px}
footer{margin:20px 0 50px;color:#59677b;font-size:13px}
</style></head><body><main>
<header><span class="version">V2 · 多例题对照</span><h1>第十次数学课 · 交互课件一致性验收</h1>
<p>例题11、13、16统一操作节奏 · PR #1038 的图示代码 · 代表性测试样例（非正式历史课件数据）</p></header>
<div class="tabs" id="cases"></div><div class="lead">统一操作：选择例题 → 观察图示 → 上一步 / 下一步 → 对照学生与教师视角。各题保留自己的数学图形。</div>
<div class="toolbar" id="toolbar"></div><section id="stage" aria-live="polite"></section>
<footer>此页面使用项目真实课件渲染代码与示例数据，不是正式课堂或完整登录流程；未连接正式数据库。</footer>
<script>
function el(tag,attrs){var e=document.createElement(tag);attrs=attrs||{};
Object.keys(attrs).forEach(function(k){if(k==="text")e.textContent=attrs[k];else if(k==="style")e.setAttribute("style",attrs[k]);
else if(k==="class")e.className=attrs[k];else if(k==="onclick")e.onclick=attrs[k];else e.setAttribute(k,attrs[k])});
for(var i=2;i<arguments.length;i++){if(arguments[i]!=null)e.appendChild(arguments[i])}return e}
""" + javascript + """
var cases=""" + payload + """;
var active=2,c=cases[active];
var state={step:0,showAnswer:false,calendarChoice:"A",calendarFeedback:false},teacher=false;
var controls=document.getElementById("toolbar"),stage=document.getElementById("stage"),tabs=document.getElementById("cases");
function addButton(label,fn){var b=el("button",{type:"button",text:label});b.onclick=fn;controls.appendChild(b)}
function draw(){controls.textContent="";tabs.textContent="";state.previewMode=!teacher;
cases.forEach(function(item,i){var b=el("button",{type:"button",text:item.params.title});if(i===active)b.className="active";b.onclick=function(){active=i;c=cases[i];state={step:0,showAnswer:false,calendarChoice:"A",calendarFeedback:false};teacher=false;draw()};tabs.appendChild(b)});
addButton(teacher?"切换学生视角":"切换教师视角",function(){teacher=!teacher;draw()});
addButton("上一步",function(){state.step=Math.max(0,state.step-1);draw()});
addButton("下一步",function(){state.step=Math.min(c.params.steps.length,state.step+1);draw()});
if(teacher)addButton(state.showAnswer?"隐藏答案":"显示答案",function(){state.showAnswer=!state.showAnswer;draw()});
addButton("重来",function(){state.step=0;state.showAnswer=false;state.calendarChoice="A";state.calendarFeedback=false;draw()});
state._calendarOnChange=draw;
cwRender(stage,c,state,false,teacher);
}
draw();
</script></main></body></html>"""
    )
