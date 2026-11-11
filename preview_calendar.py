"""Isolated, read-only visual acceptance page for weekend lesson 10 example 16.

Start only with: uvicorn preview_calendar:app --host 0.0.0.0 --port $PORT
Never imports the production app, opens its database, or accesses live lesson data.
This is a representative fixture rendered with the project's actual courseware JS.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from changying.web.weekend_courseware_pages import COURSEWARE_JS

app = FastAPI(title="长缨辅学 · 课件验收预览", docs_url=None, redoc_url=None, openapi_url=None)

_CASES = json.loads((Path(__file__).parent / "tests" / "fixtures" / "weekend_lesson10_23_teacher_pdf.json").read_text("utf-8"))

@app.get("/health")
def health():
    return {"status": "ok", "preview": True, "version": "V3", "examples": len(_CASES)}


@app.get("/", response_class=HTMLResponse)
def calendar_preview():
    payload = json.dumps([{"kind": "steps", "params": item} for item in _CASES], ensure_ascii=False)
    # Keep the injected data as executable-safe JavaScript literals.
    payload = payload.replace("<", "\\u003c")
    javascript = COURSEWARE_JS.replace("</", "<\\/")
    return HTMLResponse(
        """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>长缨辅学 · 23题真实教案课件验收 V3</title>
<style>
body{font-family:system-ui,-apple-system,"Microsoft YaHei",sans-serif;margin:0;background:#eef3f9;color:#102238}
main{max-width:1030px;margin:30px auto;padding:0 16px}
header{background:#173e75;color:white;padding:20px 24px;border-radius:14px}
header h1{font-size:22px;margin:0 0 5px}header p{font-size:13px;opacity:.9;margin:0}
.grouphead{font-weight:700;color:#284768;font-size:14px;padding:9px 0 4px}.note{border-left:4px solid #db8b18;background:#fff7e6;padding:10px 14px;border-radius:7px;margin:12px 0;font-size:14px}
.meta{color:#455b75;margin:10px 0;font-size:13px}.extra{margin:14px auto;padding:14px;border:1px solid #d0d5dd;border-radius:12px;max-width:740px;background:#f7fbff}
.diagram-row{display:flex;justify-content:center;gap:4px;margin:8px}.geo{border:2px solid #3167ad;background:#dbeafe;display:flex;justify-content:center;align-items:center;font-weight:700;color:#18386d}.geo.small{background:#fef3c7;border-color:#b7791f}
.oct{width:33px;height:33px;background:#82c4df;clip-path:polygon(30% 0,70% 0,100% 30%,100% 70%,70% 100%,30% 100%,0 70%,0 30%);border:2px solid #27527f}.diag-title{text-align:center;font-weight:700;color:#315075}
#stepinfo{color:#475467;font-weight:600;align-self:center}
.tabs{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0 8px}.tabs button{border:2px solid #b9cce3;background:white;border-radius:10px;padding:12px 18px;cursor:pointer;font-weight:700}.tabs button.active{border-color:#2563eb;background:#dbeafe;color:#153c78}.lead{background:#e6f3ff;border-left:4px solid #2563eb;padding:12px 14px;margin:14px 0;border-radius:8px}.version{background:#c6f6d5;color:#164a2a;font-weight:800;border-radius:20px;padding:4px 12px;display:inline-block}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}
.toolbar button{border:1px solid #92a9c7;background:#fff;color:#163c70;border-radius:8px;padding:10px 16px;cursor:pointer}
.toolbar button:focus-visible{outline:3px solid #2563eb}
#stage{background:white;border-radius:14px;border:1px solid #dbe4f0;padding:16px}
footer{margin:20px 0 50px;color:#59677b;font-size:13px}
</style></head><body><main>
<header><span class="version">V3 · 教案原题23道</span><h1>数学第十次课 · 23道例题课件验收</h1>
<p>根据2026-11-07教师版PDF逐题整理 · 原题条件与参考答案可核对 · 独立测试，不连接正式学生数据</p></header>
<div class="lead">请按第1—23题切换检查：看题干与示意图 → 用“下一步”看引导 → 切教师视角核查答案。图示不会冒充缺失原图。</div>
<div class="grouphead">诊断与表示 · 第1—5题</div><div class="tabs" id="cases1"></div>
<div class="grouphead">解决问题 · 第6—11题</div><div class="tabs" id="cases2"></div>
<div class="grouphead">探秘百数表 · 第12—16题</div><div class="tabs" id="cases3"></div>
<div class="grouphead">整理复习 · 第17—21题</div><div class="tabs" id="cases4"></div>
<div class="grouphead">当堂检测 · 第22—23题</div><div class="tabs" id="cases5"></div>
<div class="toolbar" id="toolbar"></div><div id="meta" class="meta"></div><div id="special"></div><section id="stage" aria-live="polite"></section><div id="extra"></div>
<footer>此页面根据教师版PDF的23道真实题目制作，使用项目课件渲染代码；不是已审核的正式课件，也不等于学校原数据库中的保存版本。第9题原排列图缺失，应人工核对。</footer>
<script>
function el(tag,attrs){var e=document.createElement(tag);attrs=attrs||{};
Object.keys(attrs).forEach(function(k){if(k==="text")e.textContent=attrs[k];else if(k==="style")e.setAttribute("style",attrs[k]);
else if(k==="class")e.className=attrs[k];else if(k==="onclick")e.onclick=attrs[k];else e.setAttribute(k,attrs[k])});
for(var i=2;i<arguments.length;i++){if(arguments[i]!=null)e.appendChild(arguments[i])}return e}
""" + javascript + """
var cases=""" + payload + """;
var active=0,c=cases[active];
var state={step:0,showAnswer:false,calendarChoice:"A",calendarFeedback:false},teacher=false;
var controls=document.getElementById("toolbar"),stage=document.getElementById("stage"),meta=document.getElementById("meta"),extra=document.getElementById("extra"),special=document.getElementById("special");
var tabHolders=[1,2,3,4,5].map(function(n){return document.getElementById("cases"+n)});
function groupFor(n){return n<=5?0:n<=11?1:n<=16?2:n<=21?3:4}
function addButton(label,fn){var b=el("button",{type:"button",text:label});b.onclick=fn;controls.appendChild(b)}
function choose(i){active=i;c=cases[active];state={step:0,showAnswer:false,calendarChoice:"A",calendarFeedback:false};teacher=false;draw()}
function extraDiagram(){extra.textContent="";var n=c.params.number;
  if(n===20){var wrap=el("div",{class:"extra"}),title=el("div",{class:"diag-title",text:"原题拼图结构示意（上排2个大正方形，下排3个小正方形）"});wrap.appendChild(title);
    var top=el("div",{class:"diagram-row"}),bottom=el("div",{class:"diagram-row"});
    for(var a=0;a<2;a++)top.appendChild(el("div",{class:"geo",style:"width:126px;height:126px",text:"m"}));
    for(var b=0;b<3;b++)bottom.appendChild(el("div",{class:"geo small",style:"width:84px;height:84px",text:"n"}));
    wrap.appendChild(top);wrap.appendChild(bottom);wrap.appendChild(el("div",{style:"text-align:center;color:#475467;font-size:12px",text:"面积拼接比例示意：两大正方形总宽与三小正方形总宽相等；原图见PDF第8页"}));extra.appendChild(wrap);
  }
  if(n===9){var wrap2=el("div",{class:"extra"});wrap2.appendChild(el("div",{class:"diag-title",text:"数量示意（并非原八边形排列图）"}));
    [5,8].forEach(function(count,i){var row=el("div",{class:"diagram-row"});row.appendChild(el("b",{text:"第"+(i+1)+"幅：" }));for(var j=0;j<count;j++)row.appendChild(el("div",{class:"oct"}));wrap2.appendChild(row)});extra.appendChild(wrap2);
  }
}
function draw(){controls.textContent="";state.previewMode=!teacher;
  tabHolders.forEach(function(h){h.textContent=""});cases.forEach(function(item,i){var b=el("button",{type:"button",text:"第"+item.params.number+"题"});if(i===active)b.className="active";b.onclick=function(){choose(i)};tabHolders[groupFor(item.params.number)].appendChild(b)});
  addButton("上一题",function(){choose(Math.max(0,active-1))});
  addButton("下一题",function(){choose(Math.min(cases.length-1,active+1))});
  addButton(teacher?"切换学生视角":"切换教师视角",function(){teacher=!teacher;draw()});
  addButton("上一步",function(){state.step=Math.max(0,state.step-1);draw()});
  addButton("下一步",function(){state.step=Math.min(c.params.steps.length,state.step+1);draw()});
  if(teacher)addButton(state.showAnswer?"隐藏答案":"显示答案",function(){state.showAnswer=!state.showAnswer;draw()});
  addButton("重置本题",function(){state.step=0;state.showAnswer=false;state.calendarChoice="A";state.calendarFeedback=false;draw()});
  controls.appendChild(el("span",{id:"stepinfo",text:"当前第"+c.params.number+"/23题 · 已展开"+state.step+"/4步"}));
  meta.textContent="原PDF第 "+c.params.sourcePage+" 页 · "+(teacher?"教师视角（可核对参考答案）":"学生视角（不直接显示参考答案）");
  special.textContent="";if(c.params.notes)special.appendChild(el("div",{class:"note",text:"原题核对提醒："+c.params.notes}));
  state._calendarOnChange=draw;cwRender(stage,c,state,false,teacher);extraDiagram();
}
draw();
</script></main></body></html>"""
    )
