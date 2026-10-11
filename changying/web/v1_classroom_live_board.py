"""Read-only classroom "big screen" for the teacher's quick check.

* ``GET /teacher/classroom-sessions/{sid}/live-board`` -- teacher-only JSON with
  aggregate numbers only (question, submitted/class size, accuracy, per-option
  distribution). No student name, id or per-student response is ever included.
* ``GET /v1/classroom-board/{sid}`` -- a static, data-free HTML shell that polls the
  JSON endpoint every 2.5 seconds with the teacher's token. Without a teacher token
  it only shows a "please sign in" message and requests no data.

The feature adds no tables, no write routes and no client-side write calls.
"""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from changying.services.classroom_quick_check import quick_check_summary
from changying.web.classroom_window_handoff import PAGE_AUTH_JS, with_open_window_script
from changying.web import v1 as v1_module

V1_CLASSROOM_LIVE_BOARD_MARKER = "changying_v1_classroom_live_board_v1"
LIVE_BOARD_POLL_MS = 2500

_RETURN_PATHS = "['/v1/workspace','/v1/student','/v1/history','/v1/transition'].includes(path)"
_RETURN_PATHS_WITH_EXECUTION = (
    "['/v1/workspace','/v1/student','/v1/history','/v1/transition','/v1/classroom-execution'].includes(path)"
)
_REFRESH_BUTTON = '<button class="btn" id="cy-session-refresh">刷新状态</button>'
_BOARD_LINK = (
    '<a class="btn" id="cy-session-board" href="/v1/classroom-board/\'+sid+\'" '
    'target="_blank" data-cy-open-window="1">打开大屏</a>'
)


def patch_v1_classroom_live_board_html(html: str) -> str:
    """Add an "open big screen" link next to the teacher's refresh button."""
    if V1_CLASSROOM_LIVE_BOARD_MARKER in html:
        return html
    if _REFRESH_BUTTON not in html:
        raise RuntimeError("classroom execution refresh button anchor not found")
    html = html.replace(_REFRESH_BUTTON, _BOARD_LINK + _REFRESH_BUTTON, 1)
    # After a fresh login V1 only returns to a few whitelisted pages; add the classroom page so the
    # "go log in" link on the big screen brings the teacher back where they were.
    if _RETURN_PATHS not in html:
        raise RuntimeError("V1 identity return path anchor not found")
    html = html.replace(_RETURN_PATHS, _RETURN_PATHS_WITH_EXECUTION, 1)
    marker = f"<!-- {V1_CLASSROOM_LIVE_BOARD_MARKER} -->"
    html = html.replace("</body>", marker + "</body>", 1) if "</body>" in html else html + marker
    return with_open_window_script(html)


def install_v1_classroom_live_board_patch() -> None:
    if getattr(v1_module, "_classroom_live_board_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_classroom_live_board_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._classroom_live_board_patch_installed = True


def _mapping(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def _options(raw: Any) -> list[str]:
    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    return [str(x) for x in value] if isinstance(value, list) else []


def board_html(sid: int) -> str:
    return (
        BOARD_HTML.replace("__PAGE_AUTH__", PAGE_AUTH_JS)
        .replace("__SID__", str(int(sid)))
        .replace("__POLL_MS__", str(LIVE_BOARD_POLL_MS))
        .replace("__MARKER__", V1_CLASSROOM_LIVE_BOARD_MARKER)
    )


def install_v1_classroom_live_board_routes(implementation: Any) -> None:
    app = implementation.app
    if getattr(app.state, "v1_classroom_live_board_routes_installed", False):
        return

    metadata = implementation.Base.metadata
    sessions = metadata.tables.get("classroom_sessions")
    segments = metadata.tables.get("classroom_segments")
    checks = metadata.tables.get("classroom_quick_checks")
    responses = metadata.tables.get("classroom_quick_check_responses")
    if None in (sessions, segments, checks, responses):
        raise RuntimeError("classroom tables must be registered before the live board")

    SchoolClass = implementation.SchoolClass
    ClassStudent = implementation.ClassStudent
    User = implementation.User
    current_user = implementation.current_user
    get_db = implementation.get_db
    router = APIRouter()

    @router.get("/teacher/classroom-sessions/{sid}/live-board")
    def live_board(
        sid: int,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        implementation.need(u, "teacher")
        raw_session = db.execute(
            select(sessions).where(
                sessions.c.id == sid,
                sessions.c.school_id == u.school_id,
                sessions.c.teacher_id == u.id,
            )
        ).first()
        if not raw_session:
            raise HTTPException(404, "课堂不存在或无权限")
        session_row = _mapping(raw_session)
        class_row = db.scalar(
            select(SchoolClass).where(
                SchoolClass.id == session_row["class_id"],
                SchoolClass.school_id == u.school_id,
            )
        )
        class_size = db.scalar(
            select(func.count())
            .select_from(ClassStudent)
            .join(User, User.id == ClassStudent.student_id)
            .where(
                ClassStudent.class_id == session_row["class_id"],
                User.school_id == u.school_id,
                User.role == "student",
                User.active == True,  # noqa: E712 - SQLAlchemy expression
            )
        ) or 0

        # The open check wins; otherwise show the most recent finished one.
        check_raw = db.execute(
            select(checks)
            .where(
                checks.c.session_id == sid,
                checks.c.school_id == u.school_id,
                checks.c.status.in_(["open", "closed"]),
            )
            .order_by(
                (checks.c.status == "open").desc(),
                checks.c.id.desc(),
            )
            .limit(1)
        ).first()

        payload: dict[str, Any] = {
            "session": {
                "title": str(session_row.get("title") or ""),
                "className": str(getattr(class_row, "name", "") or ""),
                "status": str(session_row.get("status") or ""),
                "classSize": int(class_size),
            },
            "check": None,
            "serverTime": datetime.utcnow().strftime("%H:%M:%S"),
        }
        if check_raw:
            check = _mapping(check_raw)
            options = _options(check.get("options_json"))
            rows = [
                _mapping(x)
                for x in db.execute(
                    select(responses).where(responses.c.check_id == check["id"])
                ).all()
            ]
            summary = quick_check_summary(rows, option_count=len(options))
            seg_raw = db.execute(
                select(segments).where(
                    segments.c.id == check["segment_id"],
                    segments.c.session_id == sid,
                    segments.c.school_id == u.school_id,
                )
            ).first()
            seg = _mapping(seg_raw) if seg_raw else {}
            closed = str(check["status"]) == "closed"
            reveal_correct = bool(seg.get("reveal_correct_answer")) and closed
            payload["check"] = {
                "id": int(check["id"]),
                "status": str(check["status"]),
                "questionText": str(check.get("question_text") or ""),
                "options": options,
                "responseCount": summary["responseCount"],
                "correctCount": summary["correctCount"],
                "accuracy": summary["accuracy"],
                "distribution": summary["distribution"],
                "correctIndex": int(check["correct_index"]) if reveal_correct else None,
            }
        return payload

    @router.get("/v1/classroom-board/{sid}", include_in_schema=False)
    def classroom_board_page(sid: int):
        return HTMLResponse(
            board_html(sid),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    app.include_router(router)
    app.state.v1_classroom_live_board_routes_installed = True


BOARD_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="__MARKER__" content="1">
<title>课堂大屏</title>
<style>
:root{--bg:#0f172a;--panel:#1e293b;--text:#f8fafc;--muted:#94a3b8;--bar:#38bdf8;--ok:#34d399;--warn:#fbbf24}
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;background:var(--bg);color:var(--text);
  font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif}
body{padding:2vh 3vw;font-size:clamp(20px,2.6vw,44px)}
header{display:flex;justify-content:space-between;align-items:baseline;gap:2vw;color:var(--muted);font-size:.75em}
h1{margin:1.2vh 0 2vh;font-size:1.5em;line-height:1.35;font-weight:700}
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:2vw;margin-bottom:2.5vh}
.stat{background:var(--panel);border-radius:1.2vw;padding:2vh 2vw}
.stat b{display:block;font-size:2.6em;line-height:1.1}
.stat span{color:var(--muted);font-size:.8em}
.opt{display:grid;grid-template-columns:3em 1fr 6em;align-items:center;gap:1.5vw;margin:1.3vh 0}
.opt .label{font-weight:700;font-size:1.1em}
.opt .text{font-size:.85em;color:var(--muted);margin-bottom:.4vh;overflow-wrap:anywhere}
.track{height:2.6vh;min-height:18px;background:var(--panel);border-radius:999px;overflow:hidden}
.fill{height:100%;background:var(--bar);width:0;transition:width .5s ease}
.opt.correct .fill{background:var(--ok)}
.opt .num{text-align:right;font-variant-numeric:tabular-nums}
.msg{margin-top:12vh;text-align:center;font-size:1.4em;color:var(--muted)}
.msg a{color:var(--bar)}
@media (orientation:portrait){.stats{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><span id="meta">课堂大屏</span><span id="clock"></span></header>
<main id="root"><div class="msg">正在连接…</div></main>
<script>
(function(){
  var SID=__SID__,POLL=__POLL_MS__,root=document.getElementById('root'),meta=document.getElementById('meta'),clock=document.getElementById('clock');
  // Stored token (remember-aware, same as the V1 shell) or the one-time handoff staged by "打开大屏".
__PAGE_AUTH__  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]})}
  function stop(text){
    clearInterval(timer);
    root.innerHTML='<div class="msg">'+esc(text)+'<br><br><a href="/v1/classroom-execution?session='+SID+'">前往老师登录（登录后回到课堂页，再点“打开大屏”）</a></div>';
  }
  function letter(i){return String.fromCharCode(65+i)}
  function render(d){
    var s=d.session||{},c=d.check;
    meta.textContent=(s.className?s.className+' · ':'')+(s.title||'课堂大屏');
    clock.textContent=d.serverTime||'';
    if(!c){root.innerHTML='<div class="msg">等待老师开放随堂检测…</div>';return}
    var size=s.classSize||0,rate=c.accuracy==null?'—':c.accuracy+'%';
    var html='<h1>'+esc(c.questionText)+'</h1><div class="stats">'+
      '<div class="stat"><b>'+c.responseCount+' / '+size+'</b><span>已作答人数'+(c.status==='open'?'（作答中）':'（已结束）')+'</span></div>'+
      '<div class="stat"><b>'+rate+'</b><span>正确率</span></div></div>';
    (c.distribution||[]).forEach(function(x,i){
      var ok=c.correctIndex===i;
      html+='<div class="opt'+(ok?' correct':'')+'"><div class="label">'+letter(i)+(ok?' ✓':'')+'</div>'+
        '<div><div class="text">'+esc((c.options||[])[i]||'')+'</div><div class="track"><div class="fill" style="width:'+x.percentage+'%"></div></div></div>'+
        '<div class="num">'+x.count+' 人 · '+x.percentage+'%</div></div>';
    });
    root.innerHTML=html;
  }
  var busy=false,timer=null;
  function tick(){
    if(busy)return;
    busy=true;
    obtainToken().then(function(t){
      if(!t){stop('请先登录老师账号后再打开大屏');return null}
      return fetch('/teacher/classroom-sessions/'+SID+'/live-board',{headers:{Authorization:'Bearer '+t},cache:'no-store'})
        .then(function(r){
          if(r.status===401||r.status===403){stop('登录已失效或不是老师账号，请重新登录');return null}
          if(r.status===404){stop('找不到这堂课，或你没有权限查看');return null}
          if(!r.ok)throw new Error('http '+r.status);
          return r.json();
        });
    })
      .then(function(d){if(d)render(d)})
      .catch(function(){clock.textContent='连接中断，正在重试…'})
      .then(function(){busy=false});
  }
  timer=setInterval(tick,POLL);tick();
})();
</script>
</body>
</html>
"""

__all__ = [
    "BOARD_HTML",
    "LIVE_BOARD_POLL_MS",
    "V1_CLASSROOM_LIVE_BOARD_MARKER",
    "board_html",
    "install_v1_classroom_live_board_patch",
    "install_v1_classroom_live_board_routes",
    "patch_v1_classroom_live_board_html",
]
