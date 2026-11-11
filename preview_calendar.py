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

_FIXTURE = _repair_courseware_visual(
    {
        "title": "例题16 · 月历框形辨析",
        "problem": "月历框形辨析：哪一种错误？",
        "answer": "C（竖向相邻日期应相差7，而不是10）",
        "steps": ["观察月历", "比较框形", "尝试用x表达", "独立判断"],
        "figure": {},
    },
    "月历框形辨析：哪一种错误？",
)


@app.get("/health")
def health():
    return {"status": "ok", "preview": True}


@app.get("/", response_class=HTMLResponse)
def calendar_preview():
    payload = json.dumps({"kind": "steps", "params": _FIXTURE}, ensure_ascii=False)
    # Keep the injected data as executable-safe JavaScript literals.
    payload = payload.replace("<", "\\u003c")
    javascript = COURSEWARE_JS.replace("</", "<\\/")
    return HTMLResponse(
        """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>长缨辅学 · 例题16验收预览</title>
<style>
body{font-family:system-ui,-apple-system,"Microsoft YaHei",sans-serif;margin:0;background:#eef3f9;color:#102238}
main{max-width:1030px;margin:30px auto;padding:0 16px}
header{background:#173e75;color:white;padding:20px 24px;border-radius:14px}
header h1{font-size:22px;margin:0 0 5px}header p{font-size:13px;opacity:.9;margin:0}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}
.toolbar button{border:1px solid #92a9c7;background:#fff;color:#163c70;border-radius:8px;padding:10px 16px;cursor:pointer}
.toolbar button:focus-visible{outline:3px solid #2563eb}
#stage{background:white;border-radius:14px;border:1px solid #dbe4f0;padding:16px}
footer{margin:20px 0 50px;color:#59677b;font-size:13px}
</style></head><body><main>
<header><h1>长缨辅学 · 周末第十次数学课 · 例题16</h1>
<p>独立的课件界面验收 · 来源：PR #1038 功能分支 · 示例数据，无真实学生信息</p></header>
<div class="toolbar" id="toolbar"></div><section id="stage" aria-live="polite"></section>
<footer>此页面使用项目真实课件渲染代码与示例数据，不是正式课堂或完整登录流程；未连接正式数据库。</footer>
<script>
function el(tag,attrs){var e=document.createElement(tag);attrs=attrs||{};
Object.keys(attrs).forEach(function(k){if(k==="text")e.textContent=attrs[k];else if(k==="style")e.setAttribute("style",attrs[k]);
else if(k==="class")e.className=attrs[k];else if(k==="onclick")e.onclick=attrs[k];else e.setAttribute(k,attrs[k])});
for(var i=2;i<arguments.length;i++){if(arguments[i]!=null)e.appendChild(arguments[i])}return e}
""" + javascript + """
var c=""" + payload + """;
var state={step:0,showAnswer:false,calendarChoice:"A",calendarFeedback:false},teacher=false;
var controls=document.getElementById("toolbar"),stage=document.getElementById("stage");
function addButton(label,fn){var b=el("button",{type:"button",text:label});b.onclick=fn;controls.appendChild(b)}
function draw(){controls.textContent="";state.previewMode=!teacher;
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
