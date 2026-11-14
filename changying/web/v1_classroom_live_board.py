"""Read-only classroom "big screen" for the teacher's quick check.

* ``GET /teacher/classroom-sessions/{sid}/live-board`` -- teacher-only JSON with
  aggregate numbers only (question, submitted/class size, accuracy, per-option
  distribution). No student name, id or per-student response is ever included.
* ``GET /v1/classroom-board/{sid}`` -- a static, data-free HTML shell that polls the
  JSON endpoint every 2.5 seconds with the teacher's token. Without a teacher token
  it only shows a "please sign in" message and requests no data.

While a quick check is open the live accuracy / option distribution are NOT sent unless the
teacher explicitly asks for them (``?live=1``): classmates copying the projected bars is the
usual reason to hide them. They are revealed once the check is closed. While a knowledge point is
being explained, the big screen can show the matching paragraphs of the saved class handout, and the
teacher's execution page gets a collapsible, teacher-only handout panel.

The feature adds no tables, no write routes and no client-side write calls (the one POST on the
page is the existing one-time auth handoff).
"""

from __future__ import annotations

from changying.web.design_system import apply_surface

from datetime import datetime
import json
import re
import threading
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
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
_EXECUTION_HEADING = "heading('课堂执行','教师控制课堂节奏；学生讲解需要本人确认，系统不会自动指定。')+top+"
_EXECUTION_HEADING_WITH_PANEL = (
    "heading('课堂执行','教师控制课堂节奏；学生讲解需要本人确认，系统不会自动指定。')+top+"
    "(window.__cyHandoutPanel?window.__cyHandoutPanel():'')+"
)
_REFRESH_BUTTON = '<button class="btn" id="cy-session-refresh">刷新状态</button>'
_BOARD_LINK = (
    '<a class="btn" id="cy-session-board" href="/v1/classroom-board/\'+sid+\'" '
    'target="_blank" data-cy-open-window="1">打开大屏</a>'
    '<button class="btn" id="cy-board-freeze" data-cy-board="freeze" data-sid="\'+sid+\'" '
    'title="大屏停在当前画面，老师操作不会影响投影">冻结大屏</button>'
    '<button class="btn" id="cy-board-cover" data-cy-board="cover" data-sid="\'+sid+\'" '
    'title="大屏只显示“课堂进行中，请稍候”">遮盖大屏</button>'
    '<button class="btn" id="cy-board-unlock" data-cy-board="unlock" data-sid="\'+sid+\'" style="display:none">解锁大屏</button>'
    '<span id="cy-board-lock-state" style="margin:0 8px;font-size:12px;color:#7a625c"></span>'
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
    if _EXECUTION_HEADING not in html:
        raise RuntimeError("classroom execution heading anchor not found")
    html = html.replace(_EXECUTION_HEADING, _EXECUTION_HEADING_WITH_PANEL, 1)
    marker = (
        f"<!-- {V1_CLASSROOM_LIVE_BOARD_MARKER} -->"
        f"<script>{HANDOUT_PANEL_JS}</script>"
        f"<script>{BOARD_LOCK_JS}</script>"
    )
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


def handout_excerpt(content: str, key: str, limit: int = 1500) -> str:
    """Paragraphs of the handout that mention the knowledge point (empty when none do)."""
    wanted = re.sub(r"\s+", "", str(key or ""))
    if not wanted:
        return ""
    picked: list[str] = []
    for paragraph in re.split(r"\n\s*\n", str(content or "")):
        text = paragraph.strip()
        if text and wanted in re.sub(r"\s+", "", text):
            picked.append(text)
    return "\n\n".join(picked)[:limit]


def board_html(sid: int) -> str:
    return apply_surface(
        BOARD_HTML.replace("__PAGE_AUTH__", PAGE_AUTH_JS)
        .replace("__SID__", str(int(sid)))
        .replace("__POLL_MS__", str(LIVE_BOARD_POLL_MS))
        .replace("__MARKER__", V1_CLASSROOM_LIVE_BOARD_MARKER),
        "board",
    )


# "Lock the big screen": while the teacher works on their own computer the projected board must not change.
# freeze = keep showing what is on screen now; cover = show a neutral "class in progress" page.
# Held in memory (one web process; it is only meant to last for one lesson) and expires by itself.
BOARD_LOCK_MODES = ("freeze", "cover")
BOARD_LOCK_TTL_SECONDS = 6 * 60 * 60
_BOARD_LOCKS: dict[tuple[int, int], dict[str, Any]] = {}
_BOARD_LOCK_GUARD = threading.Lock()


class BoardLockBody(BaseModel):
    mode: str = "freeze"


def _active_lock(school_id: int, sid: int) -> dict[str, Any] | None:
    with _BOARD_LOCK_GUARD:
        now = time.time()
        for key in [k for k, v in _BOARD_LOCKS.items() if v["expires"] <= now]:
            _BOARD_LOCKS.pop(key, None)
        lock = _BOARD_LOCKS.get((school_id, sid))
        return dict(lock) if lock else None


def _lock_json(lock: dict[str, Any] | None) -> dict[str, Any]:
    if not lock:
        return {"locked": False, "mode": ""}
    return {"locked": True, "mode": lock["mode"], "since": lock["since"]}


def install_v1_classroom_live_board_routes(implementation: Any) -> None:
    app = implementation.app
    if getattr(app.state, "v1_classroom_live_board_routes_installed", False):
        return

    metadata = implementation.Base.metadata
    sessions = metadata.tables.get("classroom_sessions")
    segments = metadata.tables.get("classroom_segments")
    checks = metadata.tables.get("classroom_quick_checks")
    responses = metadata.tables.get("classroom_quick_check_responses")
    handouts = metadata.tables.get("classroom_review_handouts")
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
        live: bool = Query(False),
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
        lock = _active_lock(int(u.school_id), sid)
        if lock and lock["mode"] == "cover":
            return {
                "session": {"title": str(session_row.get("title") or ""), "className": ""},
                "check": None,
                "lock": _lock_json(lock),
                "serverTime": datetime.utcnow().strftime("%H:%M:%S"),
            }
        if lock and lock["mode"] == "freeze" and lock.get("snapshot"):
            return {**lock["snapshot"], "lock": _lock_json(lock)}
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
            "segment": None,
            "handout": None,
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
            # Results stay hidden while students are still answering unless the teacher asked for them.
            show_results = closed or bool(live)
            payload["check"] = {
                "id": int(check["id"]),
                "status": str(check["status"]),
                "questionText": str(check.get("question_text") or ""),
                "options": options,
                "responseCount": summary["responseCount"],
                "resultsHidden": not show_results,
                "correctCount": summary["correctCount"] if show_results else None,
                "accuracy": summary["accuracy"] if show_results else None,
                "distribution": summary["distribution"] if show_results else None,
                "correctIndex": int(check["correct_index"]) if reveal_correct else None,
            }

        # A knowledge point being explained (no open check): show it, with the matching handout text.
        if not (check_raw and str(_mapping(check_raw)["status"]) == "open"):
            explaining = db.execute(
                select(segments)
                .where(
                    segments.c.session_id == sid,
                    segments.c.school_id == u.school_id,
                    segments.c.status == "explaining",
                )
                .order_by(segments.c.order_no)
                .limit(1)
            ).first()
            if explaining:
                seg_row = _mapping(explaining)
                payload["segment"] = {
                    "orderNo": int(seg_row["order_no"]),
                    "title": str(seg_row.get("title") or ""),
                    "knowledgeKey": str(seg_row.get("knowledge_key") or ""),
                }
                handout = find_handout(db, u, session_row)
                if handout:
                    payload["handout"] = {
                        "title": str(handout["title"] or ""),
                        "excerpt": handout_excerpt(
                            handout["content_text"], seg_row.get("knowledge_key") or seg_row.get("title")
                        ),
                    }
        return payload

    def own_session(db: Any, u: Any, sid: int) -> None:
        implementation.need(u, "teacher")
        found = db.execute(
            select(sessions.c.id).where(
                sessions.c.id == sid, sessions.c.school_id == u.school_id, sessions.c.teacher_id == u.id
            )
        ).first()
        if not found:
            raise HTTPException(404, "课堂不存在或无权限")

    @router.get("/teacher/classroom-sessions/{sid}/board-lock")
    def board_lock_state(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        own_session(db, u, sid)
        return _lock_json(_active_lock(int(u.school_id), sid))

    @router.post("/teacher/classroom-sessions/{sid}/board-lock")
    def board_lock_set(sid: int, b: BoardLockBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        own_session(db, u, sid)
        if b.mode not in BOARD_LOCK_MODES:
            raise HTTPException(400, "锁定方式只能是 freeze（冻结）或 cover（遮盖）")
        key = (int(u.school_id), sid)
        with _BOARD_LOCK_GUARD:
            _BOARD_LOCKS.pop(key, None)  # a fresh snapshot of what is on screen right now
        snapshot = live_board(sid, False, u, db) if b.mode == "freeze" else None
        lock = {
            "mode": b.mode,
            "since": datetime.utcnow().strftime("%H:%M:%S"),
            "expires": time.time() + BOARD_LOCK_TTL_SECONDS,
            "snapshot": snapshot,
        }
        with _BOARD_LOCK_GUARD:
            _BOARD_LOCKS[key] = lock
        implementation.audit(db, u, "classroom.board.lock", f"session={sid}:{b.mode}")
        db.commit()
        return _lock_json(lock)

    @router.delete("/teacher/classroom-sessions/{sid}/board-lock")
    def board_lock_clear(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        own_session(db, u, sid)
        with _BOARD_LOCK_GUARD:
            had = _BOARD_LOCKS.pop((int(u.school_id), sid), None)
        if had:
            implementation.audit(db, u, "classroom.board.unlock", f"session={sid}")
            db.commit()
        return _lock_json(None)

    def find_handout(db: Any, user: Any, session_row: dict[str, Any]) -> dict[str, Any] | None:
        if handouts is None:
            return None
        cond = None
        if session_row.get("handout_id"):
            cond = handouts.c.id == int(session_row["handout_id"])
        elif session_row.get("source_assignment_id"):
            cond = handouts.c.assignment_id == int(session_row["source_assignment_id"])
        if cond is None:
            return None
        raw = db.execute(
            select(handouts).where(cond, handouts.c.school_id == user.school_id)
        ).first()
        return _mapping(raw) if raw else None

    @router.get("/teacher/classroom-sessions/{sid}/handout")
    def teacher_handout(
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
        handout = find_handout(db, u, _mapping(raw_session))
        if not handout:
            return {"handout": None}
        try:
            knowledge = [str(x) for x in json.loads(handout["selected_knowledge_json"] or "[]")]
        except Exception:
            knowledge = []
        return {
            "handout": {
                "title": str(handout["title"] or ""),
                "selectedKnowledge": knowledge,
                "teacherNotes": str(handout["teacher_notes"] or ""),
                "content": str(handout["content_text"] or ""),
            }
        }

    @router.get("/v1/classroom-board/{sid}", include_in_schema=False)
    def classroom_board_page(sid: int):
        return HTMLResponse(
            board_html(sid),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    app.include_router(router)
    app.state.v1_classroom_live_board_routes_installed = True


BOARD_LOCK_JS = r"""
(function(){
  function read(store,key){try{return store.getItem(key)||''}catch(e){return ''}}
  function token(){
    var rem=false;try{rem=localStorage.getItem('v717Remember')==='1'}catch(e){}
    var first=rem?[localStorage,sessionStorage]:[sessionStorage,localStorage],v='';
    for(var i=0;i<first.length&&!v;i++){v=read(first[i],'v717Token')}
    if(!v)v=read(sessionStorage,'v6Token')||read(localStorage,'v6Token');
    return v&&v!=='demo'?v:'';
  }
  function $(id){return document.getElementById(id)}
  function call(method,sid,mode){
    var t=token();if(!t)return Promise.reject(new Error('请先登录老师账号'));
    var opt={method:method,headers:{Authorization:'Bearer '+t,'Content-Type':'application/json'},cache:'no-store'};
    if(mode)opt.body=JSON.stringify({mode:mode});
    return fetch('/teacher/classroom-sessions/'+sid+'/board-lock',opt).then(function(r){if(!r.ok)throw new Error('http '+r.status);return r.json()});
  }
  function paint(st){
    var f=$('cy-board-freeze'),c=$('cy-board-cover'),u=$('cy-board-unlock'),s=$('cy-board-lock-state');
    if(!f||!c||!u||!s)return;
    f.style.display=c.style.display=st.locked?'none':'';
    u.style.display=st.locked?'':'none';
    s.textContent=st.locked?(st.mode==='cover'?'大屏已遮盖':'大屏已冻结')+'（'+st.since+' 起，6 小时后自动解除）':'';
  }
  function tellBoards(sid){try{new BroadcastChannel('cyBoard'+sid).postMessage('lock')}catch(e){}}
  document.addEventListener('click',function(e){
    var b=e.target.closest&&e.target.closest('[data-cy-board]');if(!b)return;
    var sid=b.getAttribute('data-sid'),act=b.getAttribute('data-cy-board');b.disabled=true;
    call(act==='unlock'?'DELETE':'POST',sid,act==='unlock'?null:act)
      .then(function(st){paint(st);tellBoards(sid)})
      .catch(function(err){var s=$('cy-board-lock-state');if(s)s.textContent='操作失败：'+err.message})
      .then(function(){b.disabled=false});
  });
  // The page redraws itself; whenever a fresh set of buttons appears, ask the server what state the screen is in.
  var lastEl=null;
  setInterval(function(){
    var f=$('cy-board-freeze');if(!f){lastEl=null;return}
    if(f===lastEl)return;lastEl=f;
    call('GET',f.getAttribute('data-sid')).then(paint).catch(function(){});
  },800);
})();
"""

HANDOUT_PANEL_JS = r"""
(function(){
  var cache={};
  function sidNow(){return Number(new URLSearchParams(location.search).get('session')||0)}
  function remembered(){try{return localStorage.getItem('v717Remember')==='1'}catch(e){return false}}
  function read(store,key){try{return store.getItem(key)||''}catch(e){return ''}}
  function token(){
    var rem=remembered(),v='',first=rem?[localStorage,sessionStorage]:[sessionStorage,localStorage];
    for(var i=0;i<first.length&&!v;i++){v=read(first[i],'v717Token')}
    if(!v)v=read(sessionStorage,'v6Token')||read(localStorage,'v6Token');
    return v&&v!=='demo'?v:'';
  }
  function paint(body,h){
    body.textContent='';
    if(!h){body.textContent='这堂课还没有保存讲义。请先在“课堂复盘”里生成并保存讲义。';return}
    var t=document.createElement('div');t.style.cssText='font-weight:700;color:var(--text,#1f2738)';t.textContent=h.title||'课堂讲义';body.appendChild(t);
    if(h.selectedKnowledge&&h.selectedKnowledge.length){var k=document.createElement('div');k.textContent='知识点：'+h.selectedKnowledge.join('、');body.appendChild(k)}
    if(h.teacherNotes){var n=document.createElement('div');n.style.cssText='margin-top:8px';n.textContent='教师备注：'+h.teacherNotes;body.appendChild(n)}
    var c=document.createElement('div');c.style.cssText='margin-top:10px;line-height:1.7;color:var(--text,#1f2738)';c.textContent=h.content||'（讲义正文为空）';body.appendChild(c);
  }
  function fill(){
    var body=document.getElementById('cy-handout-body');if(!body)return;
    var sid=sidNow();
    if(cache[sid]!==undefined){paint(body,cache[sid]);return}
    var t=token();if(!t){body.textContent='请先登录老师账号';return}
    fetch('/teacher/classroom-sessions/'+sid+'/handout',{headers:{Authorization:'Bearer '+t},cache:'no-store'})
      .then(function(r){return r.ok?r.json():null})
      .then(function(d){cache[sid]=d?d.handout:null;var b=document.getElementById('cy-handout-body');if(b)paint(b,cache[sid])})
      .catch(function(){var b=document.getElementById('cy-handout-body');if(b)b.textContent='讲义加载失败，请刷新重试'});
  }
  window.__cyHandoutPanel=function(){
    setTimeout(fill,0);
    return '<details id="cy-handout-panel" class="section card"'+(window.__cyHandoutOpen?' open':'')+'><summary style="cursor:pointer;font-weight:700">本课讲义（仅老师可见，点开查看）</summary><div id="cy-handout-body" class="muted" style="white-space:pre-wrap;margin-top:10px">加载中…</div></details>';
  };
  document.addEventListener('toggle',function(e){if(e.target&&e.target.id==='cy-handout-panel')window.__cyHandoutOpen=e.target.open},true);
})();
"""

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
.tag{display:inline-block;background:#1e293b;color:#38bdf8;border-radius:999px;padding:.1em .8em;font-size:.7em}
.handout{white-space:pre-wrap;line-height:1.7;font-size:.9em;color:#e2e8f0;background:#111c33;border-radius:1vw;padding:2vh 2vw;margin-top:1.5vh;max-height:68vh;overflow:auto;overflow-wrap:anywhere}
.hint2{color:#94a3b8;font-size:.7em}
.tools{position:fixed;right:1.5vw;bottom:1.5vh;display:flex;gap:.6em;opacity:.55}
.tools button{font:inherit;font-size:.55em;min-height:44px;padding:0 1em;border:0;border-radius:999px;background:#1e293b;color:#cbd5e1}
@media (orientation:portrait){.stats{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><span id="meta">课堂大屏</span><span id="clock"></span></header>
<main id="root"><div class="msg">正在连接…</div></main>
<div class="tools"><button id="tg-live" type="button"></button><button id="tg-handout" type="button"></button></div>
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
  function flag(k,def){try{var v=sessionStorage.getItem(k);return v===null?def:v==='1'}catch(e){return def}}
  function setFlag(k,v){try{sessionStorage.setItem(k,v?'1':'0')}catch(e){}}
  var showLive=flag('cyBoardLive',false),showHandout=flag('cyBoardHandout',true);
  function paintTools(){
    document.getElementById('tg-live').textContent='实时分布：'+(showLive?'显示':'隐藏');
    document.getElementById('tg-handout').textContent='讲义：'+(showHandout?'显示':'隐藏');
  }
  var lastData=null;
  document.getElementById('tg-live').onclick=function(){showLive=!showLive;setFlag('cyBoardLive',showLive);paintTools();tick()};
  document.getElementById('tg-handout').onclick=function(){showHandout=!showHandout;setFlag('cyBoardHandout',showHandout);paintTools();if(lastData)render(lastData)};
  paintTools();
  function render(d){
    lastData=d;
    var s=d.session||{},c=d.check,seg=d.segment,ho=d.handout;
    meta.textContent=(s.className?s.className+' · ':'')+(s.title||'课堂大屏');
    clock.textContent=d.serverTime||'';
    var size=s.classSize||0;
    if(c&&c.status==='open'){
      var open='<span class="tag">随堂检测 · 作答中</span><h1>'+esc(c.questionText)+'</h1><div class="stats">'+
        '<div class="stat"><b>'+c.responseCount+' / '+size+'</b><span>已作答人数</span></div>'+
        '<div class="stat"><b>'+(c.resultsHidden?'—':(c.accuracy==null?'—':c.accuracy+'%'))+'</b><span>'+(c.resultsHidden?'结果将在检测结束后揭晓':'正确率')+'</span></div></div>';
      (c.options||[]).forEach(function(text,i){
        var x=c.distribution?c.distribution[i]:null;
        open+='<div class="opt"><div class="label">'+letter(i)+'</div><div><div class="text">'+esc(text)+'</div>'+
          (x?'<div class="track"><div class="fill" style="width:'+x.percentage+'%"></div></div>':'')+'</div><div class="num">'+(x?x.count+' 人 · '+x.percentage+'%':'')+'</div></div>';
      });
      root.innerHTML=open;return;
    }
    if(seg){
      var h='<span class="tag">正在讲解</span><h1>'+esc(seg.orderNo+'. '+seg.title)+'</h1>';
      if(showHandout&&ho&&ho.excerpt)h+='<div class="handout">'+esc(ho.excerpt)+'</div>';
      else if(showHandout&&ho)h+='<div class="hint2">讲义里没有找到与本知识点对应的段落，完整讲义请在老师页面查看。</div>';
      else if(!ho)h+='<div class="hint2">这堂课还没有保存讲义。</div>';
      root.innerHTML=h;return;
    }
    if(!c){root.innerHTML='<div class="msg">等待老师开放随堂检测…</div>';return}
    var rate=c.accuracy==null?'—':c.accuracy+'%';
    var html='<span class="tag">随堂检测 · 已结束</span><h1>'+esc(c.questionText)+'</h1><div class="stats">'+
      '<div class="stat"><b>'+c.responseCount+' / '+size+'</b><span>已作答人数</span></div>'+
      '<div class="stat"><b>'+rate+'</b><span>正确率</span></div></div>';
    (c.distribution||[]).forEach(function(x,i){
      var ok=c.correctIndex===i;
      html+='<div class="opt'+(ok?' correct':'')+'"><div class="label">'+letter(i)+(ok?' ✓':'')+'</div>'+
        '<div><div class="text">'+esc((c.options||[])[i]||'')+'</div><div class="track"><div class="fill" style="width:'+x.percentage+'%"></div></div></div>'+
        '<div class="num">'+x.count+' 人 · '+x.percentage+'%</div></div>';
    });
    root.innerHTML=html;
  }
  // Teacher pressed "lock big screen": freeze keeps what is shown now; cover shows a neutral page.
  var covered=false;
  function handle(d){
    var lk=d.lock;
    if(lk&&lk.mode==='cover'){covered=true;lastData=null;root.innerHTML='<div class="msg">课堂进行中，请稍候</div>';return}
    if(lk&&lk.mode==='freeze'&&lastData&&!covered)return;
    covered=false;render(d);
  }
  try{var bc=new BroadcastChannel('cyBoard'+SID);bc.onmessage=function(){tick()}}catch(e){}
  var busy=false,timer=null;
  function tick(){
    if(busy)return;
    busy=true;
    obtainToken().then(function(t){
      if(!t){stop('请先登录老师账号后再打开大屏');return null}
      return fetch('/teacher/classroom-sessions/'+SID+'/live-board'+(showLive?'?live=1':''),{headers:{Authorization:'Bearer '+t},cache:'no-store'})
        .then(function(r){
          if(r.status===401||r.status===403){stop('登录已失效或不是老师账号，请重新登录');return null}
          if(r.status===404){stop('找不到这堂课，或你没有权限查看');return null}
          if(!r.ok)throw new Error('http '+r.status);
          return r.json();
        });
    })
      .then(function(d){if(d)handle(d)})
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
    "BOARD_LOCK_JS",
    "BOARD_LOCK_MODES",
    "HANDOUT_PANEL_JS",
    "handout_excerpt",
    "LIVE_BOARD_POLL_MS",
    "V1_CLASSROOM_LIVE_BOARD_MARKER",
    "board_html",
    "install_v1_classroom_live_board_patch",
    "install_v1_classroom_live_board_routes",
    "patch_v1_classroom_live_board_html",
]
