"""Non-invasive UI polish for the legacy 长缨辅学 app.

The legacy monolith still owns the complete internal feature set. This module
only enhances the HTML shell returned from /classic: it injects a small brand
ribbon, workflow shortcuts, and conservative CSS tokens so the old interface
feels closer to the new workbench without touching database, auth, or business
logic.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from changying.web.paper_import_ui import (
    patch_classic_catalog_find_imported,
    patch_classic_catalog_photo_import,
    patch_classic_paper_import,
)

CLASSIC_UI_MARKER = "changying_classic_ui_v2"
CLASSIC_UI_PATHS = {"/classic"}

_LOCAL_DATE_PLUS_7 = "(d=>{d.setDate(d.getDate()+7);const p=n=>String(n).padStart(2,'0');return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())})(new Date())"
_LOCAL_DATE_PLUS_3 = "(d=>{d.setDate(d.getDate()+3);const p=n=>String(n).padStart(2,'0');return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())})(new Date())"


def patch_classic_paper_assignment_flow(html: str) -> str:
    """Add truthful difficulty guidance and recover from an empty unit question set."""

    if 'id="homeworkDifficulty"' in html:
        return html

    replacements = (
        (
            '<div><label>单元</label><input id="au" placeholder="留空=综合"></div>',
            '<div><label>单元</label><input id="au" placeholder="留空=综合"></div>'
            '<div><label>难度要求</label><select id="homeworkDifficulty">'
            '<option value="简单">简单</option><option value="中等" selected>中等</option>'
            '<option value="偏难">偏难</option></select>'
            '<small>难度会写入作业要求；题库暂不按难度自动筛题。</small></div>',
        ),
        (
            'unit=$("#au").value,mode=$("#am").value,instructions=$("#ai").value.trim();',
            'unit=$("#au").value,mode=$("#am").value,'
            'difficulty=$("#homeworkDifficulty").value,'
            'instructions=[$("#ai").value.trim(),"题目难度要求："+difficulty]'
            '.filter(Boolean).join("；");',
        ),
        (
            'const qs=(await api("/questions?"+params.toString())).filter(q=>(q.options||[]).length>=2&&q.questionType!=="non_choice");',
            'const eligible=rows=>(rows||[]).filter(q=>(q.options||[]).length>=2&&q.questionType!=="non_choice");'
            'let qs=eligible(await api("/questions?"+params.toString()));'
            'if(!qs.length&&unit){const broaderParams=new URLSearchParams(params);'
            'broaderParams.delete("unit");const broader=eligible(await api("/questions?"+broaderParams.toString()));'
            'if(broader.length&&confirm("本单元暂无可组卷题目，是否改用同教材其他单元的题目继续？"))qs=broader;}',
        ),
        (
            '没有符合条件的题目',
            '所选年级、学科和教材范围没有可用选择题；请调整教材/单元或先录入题目',
        ),
    )
    for before, after in replacements:
        if html.count(before) != 1:
            return html
        html = html.replace(before, after, 1)
    return html


def patch_classic_paper_submit_flow(html: str) -> str:
    """Make the Classic assignment submit action explicit, validated, and single-flight."""

    marker = "changying_feedback_335_submit_v1"
    if marker in html:
        return html
    start = html.find("function assignmentForm(classes){")
    end = html.find("async function fetchHomeworkMediaBlob", start)
    if start < 0 or end < 0:
        return html
    fragment = html[start:end]
    replacements = (
        (
            "function assignmentForm(classes){",
            "function assignmentForm(classes){/*" + marker + "*/",
        ),
        (
            '$("#saveAssignment").onclick=async()=>{try{',
            'let submitInFlight=false;$("#saveAssignment").onclick=async()=>{'
            'if(submitInFlight)return;const submitButton=$("#saveAssignment"),'
            'submitLabel=submitButton.textContent;submitInFlight=true;'
            'submitButton.disabled=true;submitButton.textContent="正在提交作业…";try{',
        ),
        (
            'const o=$("#ac").selectedOptions[0],grade=+o.dataset.grade,class_id=+o.value,studentCount=+o.dataset.count,subject=$("#as").value,textbook=$("#ab").value,unit=$("#au").value,mode=$("#am").value,',
            'const o=$("#ac").selectedOptions[0];if(!o)throw new Error("请选择要布置作业的班级");'
            'const assignmentTitle=$("#at").value.trim();if(!assignmentTitle)throw new Error("请填写作业名称");'
            'const grade=+o.dataset.grade,class_id=+o.value,studentCount=+o.dataset.count,'
            'subject=$("#as").value,textbook=$("#ab").value,unit=$("#au").value,mode=$("#am").value,',
        ),
        (
            '}catch(e){toast(e.message)}};',
            '}catch(e){toast("作业未布置："+(e.message||"请重试"))}'
            'finally{submitInFlight=false;if(document.body.contains(submitButton)){'
            'submitButton.disabled=false;submitButton.textContent=submitLabel}}};',
        ),
    )
    for before, after in replacements:
        if fragment.count(before) != 1:
            return html
        fragment = fragment.replace(before, after, 1)
    fragment = fragment.replace('title:$("#at").value', "title:assignmentTitle")
    return html[:start] + fragment + html[end:]

def patch_classic_mixed_question_types(html: str) -> str:
    """Compose assignment papers server-side with balanced question types.

    Feedback 刘麦迪 (2026-10-05) "题目全都是一个题型": the form kept only
    questions with options, dropping fill/calculation/short-answer questions.
    POST /teacher/papers/compose picks every online-gradable type.
    """

    marker = "changying_mixed_question_types_v1"
    if marker in html:
        return html
    replacements = (
        (
            '<div id="questionCountWrap"><label>在线题量</label><select id="an"><option>5</option><option>10</option><option>15</option><option>20</option></select></div>',
            '<div id="questionCountWrap"><label>在线题量</label><select id="an"><option>5</option><option selected>10</option><option>15</option><option>20</option></select>'
            '<label>题型搭配</label><select id="homeworkTypeMix"><option value="mixed" selected>多题型均衡（单选/判断/填空/计算/简答）</option>'
            '<option value="choice">仅选择题（单选/判断）</option></select>'
            '<small>多题型会从题库中按题型轮流抽题；题库缺少的题型可先用 AI 出题或导入试卷补充。</small></div>',
        ),
        (
            'const eligible=rows=>(rows||[]).filter(q=>(q.options||[]).length>=2&&q.questionType!=="non_choice");let qs=eligible(await api("/questions?"+params.toString()));if(!qs.length&&unit){const broaderParams=new URLSearchParams(params);broaderParams.delete("unit");const broader=eligible(await api("/questions?"+broaderParams.toString()));if(broader.length&&confirm("本单元暂无可组卷题目，是否改用同教材其他单元的题目继续？"))qs=broader;}const ids=photoQuestionId?[photoQuestionId]:[];ids.push(...qs.filter(q=>q.id!==photoQuestionId).sort(()=>Math.random()-.5).slice(0,Math.max(0,+$("#an").value-ids.length)).map(q=>q.id));if(!ids.length)throw new Error("所选年级、学科和教材范围没有可用选择题；请调整教材/单元或先录入题目");\n    const p=await api("/teacher/papers",{method:"POST",body:JSON.stringify({title:assignmentTitle,grade,subject,textbook,unit,question_ids:ids})});paper_id=p.id;',
            '/*' + marker + '*/const composeBody={title:assignmentTitle,grade,subject,textbook,unit,count:+$("#an").value,mix:$("#homeworkTypeMix").value,required_question_ids:photoQuestionId?[photoQuestionId]:[]};'
            'let p;try{p=await api("/teacher/papers/compose",{method:"POST",body:JSON.stringify(composeBody)})}'
            'catch(err){if(!unit||!/本单元暂无/.test(err.message||"")||!confirm("本单元暂无可在线判分的题目，是否改用同教材其他单元的题目继续？"))throw err;'
            'p=await api("/teacher/papers/compose",{method:"POST",body:JSON.stringify({...composeBody,broaden_unit:true})})}'
            'paper_id=p.id;composedTypeSummary=p.typeSummary||"";'
            'if(+p.questionIDs.length<+$("#an").value)composedTypeSummary+=(composedTypeSummary?"；":"")+"题库只有 "+p.questionIDs.length+" 道可用题";',
        ),
        (
            'let paper_id=null,photoQuestionId=null;',
            'let paper_id=null,photoQuestionId=null,composedTypeSummary="";',
        ),
        (
            'closeModal();toast("作业已布置");go("papers")',
            'closeModal();toast(composedTypeSummary?"作业已布置（"+composedTypeSummary+"）":"作业已布置");go("papers")',
        ),
    )
    for before, after in replacements:
        if html.count(before) != 1:
            return html
        html = html.replace(before, after, 1)
    return html


TOAST_IN_DIALOG_MARKER = "changying_toast_in_dialog_v1"


def patch_classic_toast_in_dialog(html: str) -> str:
    """Show the toast inside an open dialog: it is otherwise hidden behind it (feedback #370: "no prompt")."""

    before = 'function toast(msg){const t=$("#toast");'
    if TOAST_IN_DIALOG_MARKER in html or html.count(before) != 1:
        return html
    after = ('function toast(msg){/*' + TOAST_IN_DIALOG_MARKER + '*/const t=$("#toast"),dlg=$("#modal"),host=dlg&&dlg.open?dlg:document.body;'
             'if(t.parentNode!==host)host.appendChild(t);')
    return html.replace(before, after, 1)


def patch_classic_local_due_dates(html: str) -> str:
    """Keep assignment default dates in the browser/school local calendar day."""

    html = (
        html.replace(
            "new Date(Date.now()+7*86400000).toISOString().slice(0,10)",
            _LOCAL_DATE_PLUS_7,
        )
        .replace(
            "new Date(Date.now()+3*86400000).toISOString().slice(0,10)",
            _LOCAL_DATE_PLUS_3,
        )
    )
    return patch_classic_paper_assignment_flow(html)

CLASSIC_UI_SNIPPET = f"""
<style id="{CLASSIC_UI_MARKER}-style">
  :root{{
    --cy-brand:#3047ff;
    --cy-brand-soft:#eef2ff;
    --cy-green:#10a874;
    --cy-ink:#172033;
    --cy-muted:#68738a;
    --cy-line:#e6eaf3;
    --cy-warn:#f59e0b;
    --cy-radius:14px;
  }}
  body.cy-classic-enhanced{{
    background:linear-gradient(180deg,#f7f9ff 0%,#f4f7ff 44%,#f8fafc 100%) !important;
    color:var(--cy-ink);
    -webkit-font-smoothing:antialiased;
  }}
  .cy-classic-ribbon{{
    position:sticky;
    top:0;
    z-index:2147483000;
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:12px;
    padding:10px 14px;
    margin:0;
    background:rgba(255,255,255,.94);
    border-bottom:1px solid var(--cy-line);
    box-shadow:0 10px 28px rgba(23,32,51,.08);
    backdrop-filter:blur(12px);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  }}
  .cy-classic-ribbon__brand{{display:flex;align-items:center;gap:10px;min-width:0}}
  .cy-classic-ribbon__logo{{width:32px;height:32px;border-radius:11px;display:grid;place-items:center;background:linear-gradient(145deg,#3047ff,#6b7cff);color:#fff;font-weight:900}}
  .cy-classic-ribbon__text{{font-weight:900;color:var(--cy-ink);white-space:nowrap}}
  .cy-classic-ribbon__hint{{color:var(--cy-muted);font-size:12px;margin-left:6px}}
  .cy-classic-ribbon__actions{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
  .cy-classic-ribbon a,.cy-workflow-panel a{{text-decoration:none}}
  .cy-classic-btn,.cy-workflow-btn{{border:1px solid var(--cy-line);background:#fff;color:var(--cy-ink);padding:8px 11px;border-radius:999px;font-size:12px;font-weight:800;box-shadow:0 6px 18px rgba(23,32,51,.06);cursor:pointer}}
  .cy-classic-btn--primary,.cy-workflow-btn--primary{{background:var(--cy-brand);border-color:var(--cy-brand);color:#fff}}
  .cy-workflow-panel{{
    position:fixed;
    right:16px;
    bottom:18px;
    z-index:2147482500;
    width:min(310px,calc(100vw - 32px));
    padding:14px;
    border:1px solid rgba(230,234,243,.95);
    border-radius:20px;
    background:rgba(255,255,255,.94);
    box-shadow:0 18px 48px rgba(23,32,51,.16);
    backdrop-filter:blur(14px);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  }}
  .cy-workflow-panel__head{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px}}
  .cy-workflow-panel__title{{font-size:14px;font-weight:900;color:var(--cy-ink)}}
  .cy-workflow-panel__sub{{font-size:12px;color:var(--cy-muted);line-height:1.5}}
  .cy-workflow-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0}}
  .cy-workflow-btn{{border-radius:12px;text-align:center;box-shadow:none;padding:10px 8px;background:#f8faff}}
  .cy-workflow-steps{{display:grid;gap:6px;margin-top:10px}}
  .cy-workflow-step{{display:flex;gap:8px;align-items:center;font-size:12px;color:var(--cy-muted);padding:7px 8px;border-radius:12px;background:#f7f9ff;border:1px solid #edf1fb}}
  .cy-workflow-step b{{color:var(--cy-brand)}}
  .cy-panel-toggle{{font-size:12px;color:var(--cy-muted);background:transparent;border:0;cursor:pointer;padding:4px 2px}}
  .cy-toast{{
    position:fixed;
    left:50%;
    bottom:18px;
    z-index:2147483600;
    transform:translateX(-50%);
    background:#172033;
    color:#fff;
    padding:10px 14px;
    border-radius:999px;
    box-shadow:0 12px 30px rgba(23,32,51,.22);
    font-size:13px;
    opacity:0;
    pointer-events:none;
    transition:opacity .18s ease,transform .18s ease;
  }}
  .cy-toast.is-visible{{opacity:1;transform:translateX(-50%) translateY(-4px)}}
  body.cy-classic-enhanced button,
  body.cy-classic-enhanced .btn,
  body.cy-classic-enhanced input[type="button"],
  body.cy-classic-enhanced input[type="submit"]{{
    border-radius:12px;
    transition:transform .16s ease,box-shadow .16s ease,background .16s ease;
  }}
  body.cy-classic-enhanced button:hover,
  body.cy-classic-enhanced .btn:hover{{
    transform:translateY(-1px);
    box-shadow:0 10px 24px rgba(23,32,51,.12);
  }}
  body.cy-classic-enhanced input,
  body.cy-classic-enhanced select,
  body.cy-classic-enhanced textarea{{
    border-radius:12px;
    border-color:var(--cy-line);
  }}
  body.cy-classic-enhanced input:focus,
  body.cy-classic-enhanced select:focus,
  body.cy-classic-enhanced textarea:focus{{
    outline:2px solid rgba(48,71,255,.18);
    border-color:var(--cy-brand) !important;
  }}
  body.cy-classic-enhanced table{{
    border-radius:14px;
    overflow:hidden;
    background:#fff;
  }}
  body.cy-classic-enhanced th{{background:#f3f6ff !important;color:#34405a}}
  body.cy-classic-enhanced tr:hover td{{background:#f8faff}}
  body.cy-classic-enhanced .card,
  body.cy-classic-enhanced .panel,
  body.cy-classic-enhanced .box,
  body.cy-classic-enhanced section{{border-radius:var(--cy-radius)}}
  @media(max-width:880px){{
    .cy-workflow-panel{{left:10px;right:10px;bottom:10px;width:auto;padding:10px}}
    .cy-workflow-panel.is-collapsed .cy-workflow-grid,
    .cy-workflow-panel.is-collapsed .cy-workflow-steps,
    .cy-workflow-panel.is-collapsed .cy-workflow-panel__sub{{display:none}}
  }}
  @media(max-width:720px){{
    .cy-classic-ribbon{{align-items:flex-start;flex-direction:column}}
    .cy-classic-ribbon__hint{{display:block;margin-left:0;margin-top:2px}}
    .cy-classic-ribbon__actions{{width:100%}}
    .cy-classic-btn{{flex:1;text-align:center}}
  }}
</style>
<script id="{CLASSIC_UI_MARKER}-script">
(function(){{
  if(document.getElementById('{CLASSIC_UI_MARKER}-ribbon')) return;
  document.documentElement.classList.add('cy-classic-enhanced-root');

  function toast(message){{
    var el=document.getElementById('{CLASSIC_UI_MARKER}-toast');
    if(!el){{
      el=document.createElement('div');
      el.id='{CLASSIC_UI_MARKER}-toast';
      el.className='cy-toast';
      document.body.appendChild(el);
    }}
    el.textContent=message;
    el.classList.add('is-visible');
    clearTimeout(el._cyTimer);
    el._cyTimer=setTimeout(function(){{el.classList.remove('is-visible');}},2200);
  }}

  function norm(text){{return (text||'').replace(/\\s+/g,'').toLowerCase();}}
  function visible(el){{
    var style=window.getComputedStyle(el);
    return style.display!=='none' && style.visibility!=='hidden' && el.offsetParent!==null;
  }}
  function smartOpen(labels){{
    var terms=labels.map(norm);
    var items=Array.prototype.slice.call(document.querySelectorAll('a,button,[role="button"],[data-tab],[data-page]'));
    var best=null;
    for(var i=0;i<items.length;i++){{
      var el=items[i];
      if(!visible(el)) continue;
      var text=norm(el.innerText||el.textContent||el.getAttribute('aria-label')||el.getAttribute('title')||el.getAttribute('data-tab')||el.getAttribute('data-page'));
      if(!text) continue;
      if(terms.some(function(term){{return text.indexOf(term)>=0;}})){{best=el;break;}}
    }}
    if(best){{best.click();toast('已尝试打开：'+labels[0]);return;}}
    toast('当前页面未找到“'+labels[0]+'”入口，可先进入原教学系统首页查看。');
  }}

  function mount(){{
    if(document.getElementById('{CLASSIC_UI_MARKER}-ribbon')) return;
    document.body.classList.add('cy-classic-enhanced');

    var ribbon=document.createElement('div');
    ribbon.id='{CLASSIC_UI_MARKER}-ribbon';
    ribbon.className='cy-classic-ribbon';
    ribbon.innerHTML='<div class="cy-classic-ribbon__brand"><span class="cy-classic-ribbon__logo">长</span><span><span class="cy-classic-ribbon__text">长缨辅学教学系统</span><span class="cy-classic-ribbon__hint">小学教学功能继续可用</span></span></div><div class="cy-classic-ribbon__actions"><a class="cy-classic-btn cy-classic-btn--primary" href="/v1">长缨辅学 V1</a><a class="cy-classic-btn" href="/classic">原教学系统首页</a></div>';
    document.body.insertBefore(ribbon,document.body.firstChild);

    var panel=document.createElement('aside');
    panel.id='{CLASSIC_UI_MARKER}-workflow';
    panel.className='cy-workflow-panel';
    panel.innerHTML='<div class="cy-workflow-panel__head"><div><div class="cy-workflow-panel__title">今日教学快捷入口</div><div class="cy-workflow-panel__sub">按上课流程找功能：学生 → 题库/组卷 → 作业/成绩</div></div><button class="cy-panel-toggle" type="button" data-cy-collapse>收起</button></div><div class="cy-workflow-grid"><button class="cy-workflow-btn cy-workflow-btn--primary" type="button" data-cy-action="students">学生管理</button><button class="cy-workflow-btn" type="button" data-cy-action="classes">班级课程</button><button class="cy-workflow-btn" type="button" data-cy-action="questions">题库组卷</button><button class="cy-workflow-btn" type="button" data-cy-action="homework">今日作业</button><button class="cy-workflow-btn" type="button" data-cy-action="scores">成绩分析</button><button class="cy-workflow-btn" type="button" data-cy-action="points">积分奖励</button></div><div class="cy-workflow-steps"><div class="cy-workflow-step"><b>01</b><span>课前：确认学生、班级和今日任务</span></div><div class="cy-workflow-step"><b>02</b><span>课中：用题库、组卷和课堂积分组织课堂练习</span></div><div class="cy-workflow-step"><b>03</b><span>课后：看作业、错题和成绩反馈</span></div></div>';
    document.body.appendChild(panel);

    var actions={{
      students:['学生管理','学生','用户'],
      classes:['班级课程','班级','课程','课堂'],
      questions:['题库组卷','题库','组卷','试卷','题目'],
      homework:['今日作业','作业','提交','批改'],
      scores:['成绩分析','成绩','分析','报告'],
      points:['积分奖励','积分','奖励','兑换']
    }};
    panel.addEventListener('click',function(event){{
      var collapse=event.target.closest('[data-cy-collapse]');
      if(collapse){{
        panel.classList.toggle('is-collapsed');
        collapse.textContent=panel.classList.contains('is-collapsed')?'展开':'收起';
        return;
      }}
      var action=event.target.closest('[data-cy-action]');
      if(action) smartOpen(actions[action.getAttribute('data-cy-action')]||[]);
    }});
  }}
  if(document.readyState==='loading'){{document.addEventListener('DOMContentLoaded',mount);}}else{{mount();}}
}})();
</script>
"""


def is_classic_html_path(path: str) -> bool:
    """Return whether a request path should receive the classic UI enhancement."""
    return path in CLASSIC_UI_PATHS


def inject_classic_ui(html: str) -> str:
    """Inject the classic UI enhancement into an HTML document once."""
    html = patch_classic_paper_submit_flow(html)
    html = patch_classic_local_due_dates(html)
    html = patch_classic_mixed_question_types(html)
    html = patch_classic_paper_import(html)
    html = patch_classic_catalog_photo_import(html)
    html = patch_classic_catalog_find_imported(html)
    html = patch_classic_toast_in_dialog(html)
    if CLASSIC_UI_MARKER in html:
        return html
    if "</body>" in html:
        return html.replace("</body>", CLASSIC_UI_SNIPPET + "\n</body>", 1)
    return html + CLASSIC_UI_SNIPPET


async def _body_bytes(response: Response) -> bytes:
    chunks = []
    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
        if isinstance(chunk, str):
            chunk = chunk.encode(response.charset or "utf-8")
        chunks.append(chunk)
    return b"".join(chunks)


def install_classic_ui_patch(app: FastAPI) -> None:
    """Install a small HTML-only enhancement for the legacy /classic page."""
    if getattr(app.state, "classic_ui_patch_installed", False):
        return

    @app.middleware("http")
    async def classic_ui_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if request.method != "GET" or not is_classic_html_path(request.url.path):
            return response
        if response.status_code != 200:
            return response
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return response

        # GZipMiddleware may already have encoded the streaming body before this
        # late compatibility patch sees it. Treat encoded bodies as opaque: decoding
        # compressed bytes as UTF-8 corrupts the gzip stream and produces a blank page.
        content_encoding = response.headers.get("content-encoding", "").strip().lower()
        if content_encoding and content_encoding != "identity":
            return response

        raw = await _body_bytes(response)
        charset = response.charset or "utf-8"
        html = raw.decode(charset, errors="replace")
        enhanced = inject_classic_ui(html).encode(charset)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["X-Changying-Classic-UI"] = CLASSIC_UI_MARKER
        return Response(
            enhanced,
            status_code=response.status_code,
            headers=headers,
            media_type="text/html",
        )

    app.state.classic_ui_patch_installed = True


__all__ = [
    "CLASSIC_UI_MARKER",
    "CLASSIC_UI_PATHS",
    "inject_classic_ui",
    "patch_classic_local_due_dates",
    "install_classic_ui_patch",
    "is_classic_html_path",
]
