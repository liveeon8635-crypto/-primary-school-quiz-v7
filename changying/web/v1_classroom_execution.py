"""Live classroom execution V1: teacher-controlled session + student presenter consent."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text, UniqueConstraint, func, select

from changying.services.classroom_execution import (
    can_complete_session,
    can_start_segment,
    candidate_signals,
    candidate_sort_key,
    presenter_required,
    presenter_transition_allowed,
    presenter_turn_is_open,
    segment_status_for_mode,
    session_transition_allowed,
    unique_knowledge_keys,
)
from changying.services.classroom_review import classroom_review_summary
from changying.web import v1 as v1_module


V1_CLASSROOM_EXECUTION_MARKER = "changying_v1_classroom_execution_ab_v1"


class ClassroomSessionOpenBody(BaseModel):
    force_new: bool = False


class SessionStateBody(BaseModel):
    status: str


class SegmentModeBody(BaseModel):
    mode: str


class SegmentRevealBody(BaseModel):
    reveal_distribution: bool = False
    reveal_correct_answer: bool = False
    reveal_explanation: bool = False


class PresenterInviteBody(BaseModel):
    student_id: int
    presenter_type: str = "student"
    note: str = ""


class PresenterStateBody(BaseModel):
    status: str


class PresenterResponseBody(BaseModel):
    response: str


def register_classroom_execution_tables(implementation: Any) -> dict[str, Table]:
    metadata = implementation.Base.metadata
    sessions = metadata.tables.get("classroom_sessions")
    if sessions is None:
        sessions = Table(
            "classroom_sessions",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("class_id", Integer, nullable=False, index=True),
            Column("teacher_id", Integer, nullable=False, index=True),
            Column("lesson_id", Integer, nullable=True, index=True),
            Column("source_assignment_id", Integer, nullable=True, index=True),
            Column("handout_id", Integer, nullable=True, index=True),
            Column("subject", String(80), nullable=False, default=""),
            Column("textbook", String(160), nullable=False, default=""),
            Column("title", String(220), nullable=False, default=""),
            Column("status", String(30), nullable=False, default="planned", index=True),
            Column("current_segment_id", Integer, nullable=True, index=True),
            Column("started_at", DateTime, nullable=True),
            Column("completed_at", DateTime, nullable=True),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
            Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
        )

    segments = metadata.tables.get("classroom_segments")
    if segments is None:
        segments = Table(
            "classroom_segments",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("knowledge_key", String(180), nullable=False, index=True),
            Column("title", String(220), nullable=False, default=""),
            Column("order_no", Integer, nullable=False, default=0),
            Column("mode", String(30), nullable=False, default="teacher"),
            Column("status", String(30), nullable=False, default="planned", index=True),
            Column("baseline_accuracy", Integer, nullable=True),
            Column("postcheck_accuracy", Integer, nullable=True),
            Column("reveal_distribution", Boolean, nullable=False, default=False),
            Column("reveal_correct_answer", Boolean, nullable=False, default=False),
            Column("reveal_explanation", Boolean, nullable=False, default=False),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
            Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint("session_id", "order_no", name="uq_classroom_segment_order"),
        )

    turns = metadata.tables.get("classroom_presenter_turns")
    if turns is None:
        turns = Table(
            "classroom_presenter_turns",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("segment_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("requested_by", Integer, nullable=False, index=True),
            Column("presenter_type", String(30), nullable=False, default="student"),
            Column("status", String(30), nullable=False, default="invited", index=True),
            Column("note", Text, nullable=False, default=""),
            Column("invited_at", DateTime, nullable=False, default=datetime.utcnow),
            Column("responded_at", DateTime, nullable=True),
            Column("started_at", DateTime, nullable=True),
            Column("completed_at", DateTime, nullable=True),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
        )

    events = metadata.tables.get("classroom_events")
    if events is None:
        events = Table(
            "classroom_events",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("segment_id", Integer, nullable=True, index=True),
            Column("actor_id", Integer, nullable=True, index=True),
            Column("actor_role", String(30), nullable=False, default=""),
            Column("event_type", String(80), nullable=False, index=True),
            Column("payload_json", Text, nullable=False, default="{}"),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow, index=True),
        )
    return {"sessions": sessions, "segments": segments, "turns": turns, "events": events}


def _mapping(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def _iso(value: Any) -> str:
    return value.isoformat(timespec="minutes") if value else ""


def _json_list(raw: Any) -> list[Any]:
    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _event_payload(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def patch_v1_classroom_execution_html(html: str) -> str:
    if V1_CLASSROOM_EXECUTION_MARKER in html:
        return html

    title_anchor = "const title=isSchool?'学校教学工作台':'培训机构教学工作台';"
    if title_anchor not in html:
        raise RuntimeError("V1 workspace title anchor not found")
    html = html.replace(
        title_anchor,
        "if(session.role==='student'&&!tasks.includes('课堂互动'))tasks.unshift('课堂互动');" + title_anchor,
        1,
    )

    handler = "document.querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>{if(b.dataset.feature==='课堂复盘')navigate('/v1/classroom-review');else toast(b.dataset.feature+'：V1 入口已预留')});"
    if handler not in html:
        raise RuntimeError("classroom review workspace handler not found")
    html = html.replace(
        handler,
        "document.querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>{if(b.dataset.feature==='课堂复盘')navigate('/v1/classroom-review');else if(b.dataset.feature==='课堂互动')navigate('/v1/classroom-invitations');else toast(b.dataset.feature+'：V1 入口已预留')});",
        1,
    )

    handout_sections = [
        (
            "'<section class=\"section card\"><h2>课堂练习情况讲义草稿</h2><div id=\"cy-handout-editor\">'+draftEditor(draft)+'</div></section>';",
            "'<section class=\"section card\"><h2>课堂练习情况讲义草稿</h2><div id=\"cy-handout-editor\">'+draftEditor(draft)+'</div>'+(draft?'<div style=\"margin-top:14px;display:flex;gap:8px;flex-wrap:wrap\"><button class=\"btn primary\" id=\"cy-enter-classroom\">进入课堂执行（最近课堂）</button>'+(interaction?.session?.status===\"completed\"?'<button class=\"btn\" id=\"cy-new-classroom\">新开一堂课</button>':'')+'<span class=\"muted\" style=\"margin-left:10px\">学生讲解必须本人确认；默认复用最近课堂，只有“新开一堂课”才创建新 session</span></div>':'')+'</section>';",
        ),
        (
            "'<section class=\"section card\"><h2>课堂练习情况讲义草稿</h2>'+staleNotice+'<div id=\"cy-handout-editor\">'+draftEditor(draft)+'</div></section>';",
            "'<section class=\"section card\"><h2>课堂练习情况讲义草稿</h2>'+staleNotice+'<div id=\"cy-handout-editor\">'+draftEditor(draft)+'</div>'+(draft?'<div style=\"margin-top:14px;display:flex;gap:8px;flex-wrap:wrap\"><button class=\"btn primary\" id=\"cy-enter-classroom\">进入课堂执行（最近课堂）</button>'+(interaction?.session?.status===\"completed\"?'<button class=\"btn\" id=\"cy-new-classroom\">新开一堂课</button>':'')+'<span class=\"muted\" style=\"margin-left:10px\">学生讲解必须本人确认；默认复用最近课堂，只有“新开一堂课”才创建新 session</span></div>':'')+'</section>';",
        ),
    ]
    for handout_section, replacement in handout_sections:
        if handout_section in html:
            html = html.replace(handout_section, replacement, 1)
            break
    else:
        raise RuntimeError("classroom handout section anchor not found")

    save_anchor = "};bindSave();"
    if save_anchor not in html:
        raise RuntimeError("classroom review save binding anchor not found")
    html = html.replace(
        save_anchor,
        "};bindSave();const enter=document.getElementById('cy-enter-classroom');if(enter)enter.onclick=async()=>{const recent=Number(interaction?.session?.id||0);if(recent){navigate('/v1/classroom-execution?session='+recent);return}enter.disabled=true;try{const r=await api('/teacher/assignments/'+current+'/classroom-session',{method:'POST',body:JSON.stringify({force_new:false})});navigate('/v1/classroom-execution?session='+r.session.id)}catch(err){toast(err.message);enter.disabled=false}};const newer=document.getElementById('cy-new-classroom');if(newer)newer.onclick=async()=>{newer.disabled=true;try{const r=await api('/teacher/assignments/'+current+'/classroom-session',{method:'POST',body:JSON.stringify({force_new:true})});navigate('/v1/classroom-execution?session='+r.session.id)}catch(err){toast(err.message);newer.disabled=false}};",
        1,
    )

    anchor = "    function v1QuestionTypeLabel(q){"
    if anchor not in html:
        raise RuntimeError("V1 classroom execution page anchor not found")

    page = r'''
    async function classroomExecutionPage(){
      if(session.role!=='teacher'){toast('课堂执行仅教师可控制');navigate('/v1/workspace');return}
      const sid=Number(new URLSearchParams(location.search).get('session')||0);
      if(!sid){toast('缺少课堂执行编号');navigate('/v1/classroom-review');return}
      let data=null;
      const reload=async()=>{data=await api('/teacher/classroom-sessions/'+sid);renderExec()};
      const stateName=s=>({planned:'待开始',active:'进行中',paused:'已暂停',completed:'已完成',cancelled:'已取消'})[s]||s;
      const segState=s=>({planned:'待讲解',selecting_presenter:'选择讲解者',explaining:'讲解中',checking:'随堂检验',reviewed:'待收口',completed:'已完成'})[s]||s;
      const modeName=m=>({teacher:'教师讲解',student:'学生讲解',co_teach:'师生共讲',discussion:'讨论',skipped:'暂不讲解'})[m]||m;
      const turnName=s=>({invited:'等待学生确认',accepted:'学生已同意',declined:'学生已婉拒',withdrawn:'邀请已撤回',presenting:'讲解中',completed:'讲解完成'})[s]||s;
      const call=async(path,body)=>{await api(path,{method:'POST',body:JSON.stringify(body||{})});await reload()};
      const renderExec=()=>{
        const s=data.session,segs=data.segments||[],events=data.events||[];
        const top='<section class="card"><div class="section-head"><div><h2>'+esc(s.title)+'</h2><p>'+esc(s.className+' · '+s.subject+' · '+(s.textbook||''))+'</p></div><span class="tag">'+esc(stateName(s.status))+'</span></div><div style="display:flex;gap:8px;flex-wrap:wrap">'+
          (s.status==='planned'?'<button class="btn primary" id="cy-session-start">开始课堂</button><button class="btn" id="cy-session-cancel">取消未开始课堂并返回复盘</button>':'')+
          (s.status==='active'?'<button class="btn" id="cy-session-pause">暂停课堂</button>':'')+
          (s.status==='paused'?'<button class="btn primary" id="cy-session-resume">继续课堂</button>':'')+
          (['active','paused'].includes(s.status)?'<button class="btn" id="cy-session-complete">完成本堂课</button>':'')+
          '<button class="btn" id="cy-session-back">返回课堂复盘</button></div></section>';
        const cards=segs.map(seg=>{
          const t=seg.presenterTurn;
          const modeOptions=['teacher','student','co_teach','discussion','skipped'].map(m=>'<option value="'+m+'" '+(seg.mode===m?'selected':'')+'>'+modeName(m)+'</option>').join('');
          let controls='<select class="cy-seg-mode" data-id="'+seg.id+'" '+(seg.status==='explaining'||seg.status==='completed'||s.status==='completed'?'disabled':'')+'>'+modeOptions+'</select>';
          if(['student','co_teach'].includes(seg.mode)&&seg.status!=='completed'){
            if(!t||['declined','withdrawn','completed'].includes(t.status)) controls+='<button class="btn cy-candidates" data-id="'+seg.id+'">选择/邀请学生</button>';
            else controls+='<span class="tag">'+esc(t.studentName)+' · '+esc(turnName(t.status))+'</span>';
            if(t&&t.status==='accepted'&&s.status==='active') controls+='<button class="btn primary cy-present-start" data-turn="'+t.id+'">开始学生讲解</button>';
            if(t&&t.status==='presenting') controls+='<button class="btn primary cy-seg-complete" data-id="'+seg.id+'">讲解完成并收口</button>';
          }else if(['teacher','discussion'].includes(seg.mode)&&seg.status!=='completed'){
            if(seg.status==='planned'&&s.status==='active') controls+='<button class="btn primary cy-seg-start" data-id="'+seg.id+'">开始'+modeName(seg.mode)+'</button>';
            if(seg.status==='explaining') controls+='<button class="btn primary cy-seg-complete" data-id="'+seg.id+'">完成本知识点</button>';
          }
          const reveal='<div class="notice"><b>展示控制（为随堂检验阶段保留）</b><br><label><input type="checkbox" class="cy-reveal" data-id="'+seg.id+'" data-key="reveal_distribution" '+(seg.revealDistribution?'checked':'')+'>展示班级统计</label>　<label><input type="checkbox" class="cy-reveal" data-id="'+seg.id+'" data-key="reveal_correct_answer" '+(seg.revealCorrectAnswer?'checked':'')+'>展示正确答案</label>　<label><input type="checkbox" class="cy-reveal" data-id="'+seg.id+'" data-key="reveal_explanation" '+(seg.revealExplanation?'checked':'')+'>展示讲解</label><br><span class="muted">默认全部关闭；Phase C 接入即时检测后才真正向学生端展示。</span></div>';
          return '<section class="card"><div class="section-head"><div><h3>'+esc(seg.orderNo+'. '+seg.title)+'</h3><p>'+esc(seg.knowledgeKey)+' · 讲解前本次练习正确率：'+(seg.baselineAccuracy===null?'—':seg.baselineAccuracy+'%')+'</p></div><span class="tag">'+esc(segState(seg.status))+'</span></div><div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">'+controls+'</div><div id="cy-candidates-'+seg.id+'"></div>'+reveal+'</section>';
        }).join('');
        const allDone=segs.length>0&&segs.every(x=>x.status==='completed');
        const finishCta=s.status==='active'&&allDone?'<section class="section card"><h2>本堂课知识点已全部完成</h2><p class="muted">确认结束后会直接进入课堂复盘；不会自动生成讲义、自动加分或写入长期知识掌握记录。</p><button class="btn primary" id="cy-session-complete-bottom">完成本堂课并进入课堂复盘</button></section>':'';
        const timeline=events.slice(0,30).map(e=>'<div class="row"><span class="row-main"><b>'+esc(e.eventType)+'</b><small>'+esc(e.createdAt)+' · '+esc(e.actorRole||'system')+'</small></span></div>').join('')||'<div class="empty">暂无课堂事件</div>';
        const content=heading('课堂执行','教师控制课堂节奏；学生讲解需要本人确认，系统不会自动指定。')+top+'<section class="section"><div class="section-head"><div><h2>知识点执行卡</h2><p>本阶段只负责课堂状态与讲解者确认；随堂检验、讲解评价和互动积分将在下一阶段接入。</p></div></div><div class="grid">'+cards+'</div></section>'+finishCta+'<section class="section card"><h2>课堂事件时间线</h2><div class="list">'+timeline+'</div></section>';
        screen.innerHTML=shell(content,'workspace');bindNav();
        const by=id=>document.getElementById(id);
        if(by('cy-session-start'))by('cy-session-start').onclick=()=>call('/teacher/classroom-sessions/'+sid+'/state',{status:'active'});
        if(by('cy-session-cancel'))by('cy-session-cancel').onclick=async()=>{const btn=by('cy-session-cancel');btn.disabled=true;try{await api('/teacher/classroom-sessions/'+sid+'/state',{method:'POST',body:JSON.stringify({status:'cancelled'})});navigate('/v1/classroom-review?assignment='+s.sourceAssignmentID)}catch(e){toast(e.message);btn.disabled=false}};
        if(by('cy-session-pause'))by('cy-session-pause').onclick=()=>call('/teacher/classroom-sessions/'+sid+'/state',{status:'paused'});
        if(by('cy-session-resume'))by('cy-session-resume').onclick=()=>call('/teacher/classroom-sessions/'+sid+'/state',{status:'active'});
        const finishSession=async btn=>{btn.disabled=true;try{await api('/teacher/classroom-sessions/'+sid+'/state',{method:'POST',body:JSON.stringify({status:'completed'})});navigate('/v1/classroom-review?assignment='+s.sourceAssignmentID)}catch(e){toast(e.message);btn.disabled=false}};
        [by('cy-session-complete'),by('cy-session-complete-bottom')].filter(Boolean).forEach(btn=>btn.onclick=()=>finishSession(btn));
        by('cy-session-back').onclick=()=>navigate('/v1/classroom-review?assignment='+s.sourceAssignmentID);
        document.querySelectorAll('.cy-seg-mode').forEach(el=>el.onchange=()=>call('/teacher/classroom-sessions/'+sid+'/segments/'+el.dataset.id+'/mode',{mode:el.value}).catch(e=>toast(e.message)));
        document.querySelectorAll('.cy-seg-start').forEach(el=>el.onclick=()=>call('/teacher/classroom-sessions/'+sid+'/segments/'+el.dataset.id+'/start',{}).catch(e=>toast(e.message)));
        document.querySelectorAll('.cy-seg-complete').forEach(el=>el.onclick=()=>call('/teacher/classroom-sessions/'+sid+'/segments/'+el.dataset.id+'/complete',{}).catch(e=>toast(e.message)));
        document.querySelectorAll('.cy-present-start').forEach(el=>el.onclick=()=>call('/teacher/classroom-sessions/'+sid+'/presenter-turns/'+el.dataset.turn+'/state',{status:'presenting'}).catch(e=>toast(e.message)));
        document.querySelectorAll('.cy-candidates').forEach(el=>el.onclick=async()=>{const segid=el.dataset.id,box=by('cy-candidates-'+segid);el.disabled=true;try{const rows=await api('/teacher/classroom-sessions/'+sid+'/segments/'+segid+'/candidates');box.innerHTML='<div class="card" style="margin-top:10px"><p class="muted">候选信息只对教师可见，不是公开排名，也不会自动指定学生。</p><select id="cy-candidate-select-'+segid+'">'+rows.map(x=>'<option value="'+x.id+'">'+esc(x.name+' · '+(x.signals||[]).join('；'))+'</option>').join('')+'</select><div class="field"><label>邀请说明（可选）</label><input id="cy-candidate-note-'+segid+'" placeholder="例如：愿意给大家讲一下你的思路吗？"></div><button class="btn primary" id="cy-invite-'+segid+'">发送讲解邀请</button></div>';by('cy-invite-'+segid).onclick=()=>call('/teacher/classroom-sessions/'+sid+'/segments/'+segid+'/invite',{student_id:Number(by('cy-candidate-select-'+segid).value),presenter_type:(data.segments.find(x=>String(x.id)===String(segid))?.mode||'student'),note:by('cy-candidate-note-'+segid).value}).catch(e=>toast(e.message))}catch(err){toast(err.message);el.disabled=false}});
        document.querySelectorAll('.cy-reveal').forEach(el=>el.onchange=async()=>{const segid=el.dataset.id,seg=data.segments.find(x=>String(x.id)===String(segid));const body={reveal_distribution:seg.revealDistribution,reveal_correct_answer:seg.revealCorrectAnswer,reveal_explanation:seg.revealExplanation};body[el.dataset.key]=el.checked;try{await api('/teacher/classroom-sessions/'+sid+'/segments/'+segid+'/reveal',{method:'POST',body:JSON.stringify(body)});await reload()}catch(err){toast(err.message)}});
      };
      await reload();
    }

    async function classroomInvitationsPage(){
      if(session.role!=='student'){toast('课堂互动邀请仅学生可见');navigate('/v1/workspace');return}
      let rows=[];
      try{rows=await api('/student/classroom-invitations')}catch(err){screen.innerHTML=shell(heading('课堂互动','读取失败')+'<div class="notice error">'+esc(err.message)+'</div>','workspace');bindNav();return}
      const cards=rows.map(x=>'<section class="card"><div class="section-head"><div><h3>'+esc(x.knowledgeKey)+'</h3><p>'+esc(x.className+' · '+x.sessionTitle)+'</p></div><span class="tag">'+esc(turnNameStudent(x.status))+'</span></div><p>'+esc(x.note||'教师邀请你讲解这个知识点。你可以自主选择接受或婉拒。')+'</p>'+(x.status==='invited'?'<div style="display:flex;gap:8px"><button class="btn primary cy-accept" data-id="'+x.id+'">接受邀请</button><button class="btn cy-decline" data-id="'+x.id+'">暂不参与</button></div>':'')+'<div class="notice">你的选择只用于本次课堂安排；婉拒不会扣分，也不会被记录为知识掌握不足。</div></section>').join('')||'<div class="empty">当前没有需要你确认的课堂讲解邀请。</div>';
      screen.innerHTML=shell(heading('课堂互动','学生可以自主确认是否参与知识点讲解。')+'<section class="section">'+cards+'</section>','workspace');bindNav();
      document.querySelectorAll('.cy-accept').forEach(b=>b.onclick=async()=>{try{await api('/student/classroom-invitations/'+b.dataset.id+'/respond',{method:'POST',body:JSON.stringify({response:'accepted'})});toast('已接受讲解邀请');await classroomInvitationsPage()}catch(e){toast(e.message)}});
      document.querySelectorAll('.cy-decline').forEach(b=>b.onclick=async()=>{try{await api('/student/classroom-invitations/'+b.dataset.id+'/respond',{method:'POST',body:JSON.stringify({response:'declined'})});toast('已婉拒，本次不会扣分');await classroomInvitationsPage()}catch(e){toast(e.message)}});
    }
    function turnNameStudent(s){return ({invited:'待确认',accepted:'已接受 · 等待教师开始',presenting:'讲解中'})[s]||s}

'''
    html = html.replace(anchor, page + anchor, 1)

    dispatch = "if(path.includes('/classroom-review'))await classroomReviewPage();else if(path.includes('/student'))await studentPage();"
    if dispatch not in html:
        raise RuntimeError("classroom review route dispatch anchor not found")
    html = html.replace(
        dispatch,
        "if(path.includes('/classroom-execution'))await classroomExecutionPage();else if(path.includes('/classroom-invitations'))await classroomInvitationsPage();else if(path.includes('/classroom-review'))await classroomReviewPage();else if(path.includes('/student'))await studentPage();",
        1,
    )

    return html.replace(
        "</head>",
        '<meta name="' + V1_CLASSROOM_EXECUTION_MARKER + '" content="1"></head>',
        1,
    )


def install_v1_classroom_execution_patch() -> None:
    if getattr(v1_module, "_classroom_execution_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_classroom_execution_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._classroom_execution_patch_installed = True


def install_v1_classroom_execution_routes(implementation: Any) -> None:
    app = implementation.app
    if getattr(app.state, "v1_classroom_execution_routes_installed", False):
        return

    tables = register_classroom_execution_tables(implementation)
    sessions = tables["sessions"]
    segments = tables["segments"]
    turns = tables["turns"]
    events = tables["events"]
    handouts = implementation.Base.metadata.tables.get("classroom_review_handouts")
    if handouts is None:
        raise RuntimeError("classroom_review_handouts must be registered before classroom execution")

    Assignment = implementation.Assignment
    Submission = implementation.Submission
    Question = implementation.Question
    Paper = implementation.Paper
    SchoolClass = implementation.SchoolClass
    ClassStudent = implementation.ClassStudent
    User = implementation.User
    LearningEvidenceEvent = implementation.LearningEvidenceEvent
    current_user = implementation.current_user
    get_db = implementation.get_db

    def append_event(db: Any, user: Any, session_id: int, event_type: str, *, segment_id: int | None = None, payload: dict[str, Any] | None = None) -> None:
        db.execute(
            events.insert().values(
                school_id=user.school_id,
                session_id=session_id,
                segment_id=segment_id,
                actor_id=user.id,
                actor_role=str(getattr(user, "role", "") or ""),
                event_type=event_type[:80],
                payload_json=json.dumps(payload or {}, ensure_ascii=False),
                created_at=datetime.utcnow(),
            )
        )

    def teacher_session_row(db: Any, user: Any, sid: int) -> dict[str, Any]:
        implementation.need(user, "teacher")
        row = db.execute(
            select(sessions).where(
                sessions.c.id == sid,
                sessions.c.school_id == user.school_id,
                sessions.c.teacher_id == user.id,
            )
        ).first()
        if not row:
            raise HTTPException(404, "课堂执行记录不存在或无权限")
        return _mapping(row)

    def session_segment_row(db: Any, user: Any, sid: int, segid: int) -> dict[str, Any]:
        teacher_session_row(db, user, sid)
        row = db.execute(
            select(segments).where(
                segments.c.id == segid,
                segments.c.session_id == sid,
                segments.c.school_id == user.school_id,
            )
        ).first()
        if not row:
            raise HTTPException(404, "课堂知识点不存在")
        return _mapping(row)

    def current_turn(db: Any, sid: int, segid: int) -> dict[str, Any] | None:
        rows = db.execute(
            select(turns)
            .where(turns.c.session_id == sid, turns.c.segment_id == segid)
            .order_by(turns.c.id.desc())
        ).all()
        for row in rows:
            data = _mapping(row)
            if presenter_turn_is_open(data["status"]):
                return data
        return _mapping(rows[0]) if rows else None

    def student_name(db: Any, school_id: int, student_id: int) -> str:
        row = db.scalar(
            select(User).where(
                User.id == student_id,
                User.school_id == school_id,
                User.role == "student",
            )
        )
        return str(getattr(row, "name", "") or "") if row else ""

    def session_payload(db: Any, user: Any, sid: int) -> dict[str, Any]:
        s = teacher_session_row(db, user, sid)
        class_row = db.scalar(
            select(SchoolClass).where(
                SchoolClass.id == s["class_id"],
                SchoolClass.school_id == user.school_id,
            )
        )
        seg_rows = db.execute(
            select(segments)
            .where(segments.c.session_id == sid, segments.c.school_id == user.school_id)
            .order_by(segments.c.order_no, segments.c.id)
        ).all()
        seg_payload = []
        for raw in seg_rows:
            seg = _mapping(raw)
            turn = current_turn(db, sid, int(seg["id"]))
            turn_payload = None
            if turn:
                turn_payload = {
                    "id": int(turn["id"]),
                    "studentID": int(turn["student_id"]),
                    "studentName": student_name(db, user.school_id, int(turn["student_id"])),
                    "presenterType": str(turn["presenter_type"]),
                    "status": str(turn["status"]),
                    "note": str(turn["note"] or ""),
                    "invitedAt": _iso(turn["invited_at"]),
                    "respondedAt": _iso(turn["responded_at"]),
                    "startedAt": _iso(turn["started_at"]),
                    "completedAt": _iso(turn["completed_at"]),
                }
            seg_payload.append(
                {
                    "id": int(seg["id"]),
                    "knowledgeKey": str(seg["knowledge_key"]),
                    "title": str(seg["title"]),
                    "orderNo": int(seg["order_no"]),
                    "mode": str(seg["mode"]),
                    "status": str(seg["status"]),
                    "baselineAccuracy": seg["baseline_accuracy"],
                    "postcheckAccuracy": seg["postcheck_accuracy"],
                    "revealDistribution": bool(seg["reveal_distribution"]),
                    "revealCorrectAnswer": bool(seg["reveal_correct_answer"]),
                    "revealExplanation": bool(seg["reveal_explanation"]),
                    "presenterTurn": turn_payload,
                }
            )
        event_rows = db.execute(
            select(events)
            .where(events.c.session_id == sid, events.c.school_id == user.school_id)
            .order_by(events.c.id.desc())
            .limit(100)
        ).all()
        return {
            "session": {
                "id": int(s["id"]),
                "classID": int(s["class_id"]),
                "className": str(getattr(class_row, "name", "") or ""),
                "teacherID": int(s["teacher_id"]),
                "sourceAssignmentID": s["source_assignment_id"],
                "handoutID": s["handout_id"],
                "subject": str(s["subject"] or ""),
                "textbook": str(s["textbook"] or ""),
                "title": str(s["title"] or ""),
                "status": str(s["status"]),
                "currentSegmentID": s["current_segment_id"],
                "startedAt": _iso(s["started_at"]),
                "completedAt": _iso(s["completed_at"]),
            },
            "segments": seg_payload,
            "events": [
                {
                    "id": int(_mapping(raw)["id"]),
                    "segmentID": _mapping(raw)["segment_id"],
                    "actorID": _mapping(raw)["actor_id"],
                    "actorRole": str(_mapping(raw)["actor_role"] or ""),
                    "eventType": str(_mapping(raw)["event_type"]),
                    "payload": _event_payload(_mapping(raw)["payload_json"]),
                    "createdAt": _iso(_mapping(raw)["created_at"]),
                }
                for raw in event_rows
            ],
        }

    def review_context(db: Any, user: Any, assignment: Any, paper: Any) -> dict[str, Any]:
        recipients = implementation.recipient_students(db, assignment)
        ids = [int(x.id) for x in recipients]
        submissions = (
            list(
                db.scalars(
                    select(Submission).where(
                        Submission.school_id == user.school_id,
                        Submission.assignment_id == assignment.id,
                        Submission.student_id.in_(ids),
                    )
                ).all()
            )
            if ids
            else []
        )
        qids = [int(x) for x in _json_list(paper.question_ids_json) if str(x).isdigit()]
        questions = (
            list(
                db.scalars(
                    select(Question).where(
                        Question.school_id == user.school_id,
                        Question.id.in_(qids),
                    )
                ).all()
            )
            if qids
            else []
        )
        class_row = db.scalar(
            select(SchoolClass).where(
                SchoolClass.id == assignment.class_id,
                SchoolClass.school_id == user.school_id,
                SchoolClass.teacher_id == user.id,
            )
        )
        if not class_row:
            raise HTTPException(404, "班级不存在或无权限")
        return classroom_review_summary(
            assignment=assignment,
            class_row=class_row,
            paper=paper,
            recipients=recipients,
            submissions=submissions,
            questions=questions,
        )

    @app.post("/teacher/assignments/{aid}/classroom-session")
    def create_classroom_session(
        aid: int,
        body: ClassroomSessionOpenBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        implementation.need(u, "teacher")
        assignment = implementation.teacher_assignment_for(db, u.school_id, u.id, aid)
        if not assignment:
            raise HTTPException(404, "课堂练习不存在或无权限")
        paper = db.scalar(select(Paper).where(Paper.id == assignment.paper_id, Paper.school_id == u.school_id))
        if not paper:
            raise HTTPException(400, "课堂练习缺少试卷信息")
        handout_row = db.execute(
            select(handouts).where(
                handouts.c.school_id == u.school_id,
                handouts.c.assignment_id == aid,
                handouts.c.teacher_id == u.id,
            )
        ).first()
        if not handout_row:
            raise HTTPException(400, "请先由教师生成并保存课堂复盘讲义")
        handout = _mapping(handout_row)

        open_session = db.execute(
            select(sessions)
            .where(
                sessions.c.school_id == u.school_id,
                sessions.c.teacher_id == u.id,
                sessions.c.source_assignment_id == aid,
                sessions.c.status.in_(["planned", "active", "paused"]),
            )
            .order_by(sessions.c.id.desc())
        ).first()
        if open_session:
            return {
                "created": False,
                "reused": True,
                **session_payload(db, u, int(_mapping(open_session)["id"])),
            }

        latest_session = db.execute(
            select(sessions)
            .where(
                sessions.c.school_id == u.school_id,
                sessions.c.teacher_id == u.id,
                sessions.c.source_assignment_id == aid,
            )
            .order_by(sessions.c.id.desc())
        ).first()
        if latest_session and not body.force_new:
            return {
                "created": False,
                "reused": True,
                **session_payload(db, u, int(_mapping(latest_session)["id"])),
            }

        selected = unique_knowledge_keys(_json_list(handout["selected_knowledge_json"]))
        if not selected:
            qids = [int(x) for x in _json_list(handout["selected_question_ids_json"]) if int(x) > 0]
            if qids:
                qrows = db.scalars(select(Question).where(Question.school_id == u.school_id, Question.id.in_(qids))).all()
                selected = unique_knowledge_keys([str(getattr(x, "knowledge", "") or "") for x in qrows])
        if not selected:
            raise HTTPException(400, "讲义中没有可执行的知识点，请先在课堂复盘中选择讲解内容")

        review = review_context(db, u, assignment, paper)
        baseline = {str(x.get("knowledge") or ""): int(x.get("accuracy") or 0) for x in review.get("knowledgeStats", [])}
        now = datetime.utcnow()
        sid = int(
            db.execute(
                sessions.insert()
                .values(
                    school_id=u.school_id,
                    class_id=assignment.class_id,
                    teacher_id=u.id,
                    source_assignment_id=aid,
                    handout_id=int(handout["id"]),
                    subject=str(paper.subject or ""),
                    textbook=str(paper.textbook or ""),
                    title=f"{assignment.title} · 课堂执行",
                    status="planned",
                    created_at=now,
                    updated_at=now,
                )
                .returning(sessions.c.id)
            ).scalar_one()
        )
        for order_no, knowledge in enumerate(selected, start=1):
            db.execute(
                segments.insert().values(
                    school_id=u.school_id,
                    session_id=sid,
                    knowledge_key=knowledge,
                    title=knowledge,
                    order_no=order_no,
                    mode="teacher",
                    status="planned",
                    baseline_accuracy=baseline.get(knowledge),
                    created_at=now,
                    updated_at=now,
                )
            )
        append_event(
            db,
            u,
            sid,
            "session.created",
            payload={
                "sourceAssignmentID": aid,
                "handoutID": int(handout["id"]),
                "segmentCount": len(selected),
                "explicitNew": bool(body.force_new),
            },
        )
        implementation.audit(
            db,
            u,
            "classroom.session.create",
            f"session={sid};assignment={aid};segments={len(selected)};force_new={int(bool(body.force_new))}",
        )
        db.commit()
        return {"created": True, **session_payload(db, u, sid)}

    @app.get("/teacher/classroom-sessions/{sid}")
    def get_classroom_session(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        return session_payload(db, u, sid)

    @app.post("/teacher/classroom-sessions/{sid}/state")
    def set_classroom_session_state(sid: int, body: SessionStateBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        s = teacher_session_row(db, u, sid)
        target = body.status.strip()
        if not session_transition_allowed(str(s["status"]), target):
            raise HTTPException(400, f"课堂状态不能从 {s['status']} 切换到 {target}")
        if target == "completed":
            seg_states = [str(x) for x in db.scalars(select(segments.c.status).where(segments.c.session_id == sid, segments.c.school_id == u.school_id)).all()]
            if not can_complete_session(seg_states):
                raise HTTPException(400, "仍有知识点未完成，不能结束本堂课")
        values = {"status": target, "updated_at": datetime.utcnow()}
        if target == "active" and not s["started_at"]:
            values["started_at"] = datetime.utcnow()
        if target in {"completed", "cancelled"}:
            values["completed_at"] = datetime.utcnow()
            values["current_segment_id"] = None
        db.execute(sessions.update().where(sessions.c.id == sid).values(**values))
        append_event(db, u, sid, f"session.{target}")
        implementation.audit(db, u, "classroom.session.state", f"session={sid};{s['status']}->{target}")
        db.commit()
        return session_payload(db, u, sid)

    @app.post("/teacher/classroom-sessions/{sid}/segments/{segid}/mode")
    def set_classroom_segment_mode(sid: int, segid: int, body: SegmentModeBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        s = teacher_session_row(db, u, sid)
        seg = session_segment_row(db, u, sid, segid)
        if s["status"] in {"completed", "cancelled"}:
            raise HTTPException(400, "已结束课堂不能修改知识点")
        if seg["status"] in {"explaining", "completed"}:
            raise HTTPException(400, "当前知识点已经开始或完成，不能切换讲解方式")
        open_turn = current_turn(db, sid, segid)
        if open_turn and presenter_turn_is_open(open_turn["status"]):
            raise HTTPException(400, "当前已有待处理的学生讲解邀请，请先完成或撤回")
        try:
            status = segment_status_for_mode(body.mode.strip())
        except ValueError:
            raise HTTPException(400, "无效的课堂讲解方式")
        db.execute(segments.update().where(segments.c.id == segid).values(mode=body.mode.strip(), status=status, updated_at=datetime.utcnow()))
        append_event(db, u, sid, "segment.mode_selected", segment_id=segid, payload={"mode": body.mode.strip()})
        if body.mode.strip() == "skipped":
            append_event(db, u, sid, "segment.skipped", segment_id=segid)
        db.commit()
        return session_payload(db, u, sid)

    @app.post("/teacher/classroom-sessions/{sid}/segments/{segid}/reveal")
    def set_classroom_segment_reveal(sid: int, segid: int, body: SegmentRevealBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher_session_row(db, u, sid)
        session_segment_row(db, u, sid, segid)
        db.execute(
            segments.update()
            .where(segments.c.id == segid)
            .values(
                reveal_distribution=body.reveal_distribution,
                reveal_correct_answer=body.reveal_correct_answer,
                reveal_explanation=body.reveal_explanation,
                updated_at=datetime.utcnow(),
            )
        )
        append_event(db, u, sid, "segment.reveal_policy_changed", segment_id=segid, payload={"distribution": body.reveal_distribution, "correctAnswer": body.reveal_correct_answer, "explanation": body.reveal_explanation})
        db.commit()
        return session_payload(db, u, sid)

    @app.post("/teacher/classroom-sessions/{sid}/segments/{segid}/start")
    def start_classroom_segment(sid: int, segid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        s = teacher_session_row(db, u, sid)
        seg = session_segment_row(db, u, sid, segid)
        turn = current_turn(db, sid, segid)
        presenter_status = str(turn["status"]) if turn else None
        ok, message = can_start_segment(session_status=str(s["status"]), segment_status=str(seg["status"]), mode=str(seg["mode"]), presenter_status=presenter_status)
        if not ok:
            raise HTTPException(400, message)
        if presenter_required(str(seg["mode"])) and turn:
            if not presenter_transition_allowed(str(turn["status"]), "presenting"):
                raise HTTPException(400, "当前学生邀请状态不能开始讲解")
            db.execute(turns.update().where(turns.c.id == int(turn["id"])).values(status="presenting", started_at=datetime.utcnow()))
            append_event(db, u, sid, "presenter.started", segment_id=segid, payload={"turnID": int(turn["id"]), "studentID": int(turn["student_id"])})
        db.execute(segments.update().where(segments.c.id == segid).values(status="explaining", updated_at=datetime.utcnow()))
        db.execute(sessions.update().where(sessions.c.id == sid).values(current_segment_id=segid, updated_at=datetime.utcnow()))
        append_event(db, u, sid, "explanation.started", segment_id=segid, payload={"mode": seg["mode"]})
        db.commit()
        return session_payload(db, u, sid)

    @app.post("/teacher/classroom-sessions/{sid}/segments/{segid}/complete")
    def complete_classroom_segment(sid: int, segid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        s = teacher_session_row(db, u, sid)
        if str(s["status"]) != "active":
            raise HTTPException(400, "课堂暂停或结束时不能完成知识点")
        seg = session_segment_row(db, u, sid, segid)
        if str(seg["status"]) != "explaining":
            raise HTTPException(400, "只有正在讲解的知识点才能完成")
        turn = current_turn(db, sid, segid)
        if presenter_required(str(seg["mode"])):
            if not turn or str(turn["status"]) != "presenting":
                raise HTTPException(400, "学生讲解尚未开始，不能完成")
            db.execute(turns.update().where(turns.c.id == int(turn["id"])).values(status="completed", completed_at=datetime.utcnow()))
            append_event(db, u, sid, "presenter.completed", segment_id=segid, payload={"turnID": int(turn["id"]), "studentID": int(turn["student_id"])})
        db.execute(segments.update().where(segments.c.id == segid).values(status="completed", updated_at=datetime.utcnow()))
        db.execute(sessions.update().where(sessions.c.id == sid).values(current_segment_id=None, updated_at=datetime.utcnow()))
        append_event(db, u, sid, "explanation.completed", segment_id=segid, payload={"mode": seg["mode"]})
        append_event(db, u, sid, "segment.completed", segment_id=segid)
        db.commit()
        return session_payload(db, u, sid)

    @app.get("/teacher/classroom-sessions/{sid}/segments/{segid}/candidates")
    def classroom_presenter_candidates(sid: int, segid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        s = teacher_session_row(db, u, sid)
        seg = session_segment_row(db, u, sid, segid)
        students = list(
            db.scalars(
                select(User)
                .join(ClassStudent, ClassStudent.student_id == User.id)
                .where(
                    ClassStudent.class_id == s["class_id"],
                    User.school_id == u.school_id,
                    User.role == "student",
                    User.active == True,
                )
                .order_by(User.name, User.id)
            ).all()
        )
        source_correct: dict[int, bool] = {int(x.id): False for x in students}
        aid = s["source_assignment_id"]
        if aid:
            assignment = db.scalar(select(Assignment).where(Assignment.id == aid, Assignment.school_id == u.school_id))
            paper = db.scalar(select(Paper).where(Paper.id == assignment.paper_id, Paper.school_id == u.school_id)) if assignment else None
            qids = [int(x) for x in _json_list(getattr(paper, "question_ids_json", "[]"))] if paper else []
            qrows = list(db.scalars(select(Question).where(Question.school_id == u.school_id, Question.id.in_(qids))).all()) if qids else []
            relevant = {int(q.id) for q in qrows if str(getattr(q, "knowledge", "") or "").strip() == str(seg["knowledge_key"])}
            if relevant:
                submissions = db.scalars(select(Submission).where(Submission.school_id == u.school_id, Submission.assignment_id == aid, Submission.student_id.in_([int(x.id) for x in students]))).all()
                for sub in submissions:
                    for answer in _json_list(getattr(sub, "answers_json", "[]")):
                        if isinstance(answer, dict) and int(answer.get("question_id") or 0) in relevant and answer.get("correct") is True:
                            source_correct[int(sub.student_id)] = True

        result = []
        for student in students:
            prior_success = int(
                db.scalar(
                    select(func.count())
                    .select_from(LearningEvidenceEvent)
                    .where(
                        LearningEvidenceEvent.school_id == u.school_id,
                        LearningEvidenceEvent.student_id == student.id,
                        LearningEvidenceEvent.knowledge_key == str(seg["knowledge_key"]),
                        LearningEvidenceEvent.success == True,
                    )
                )
                or 0
            )
            prior_presentations = int(
                db.scalar(
                    select(func.count())
                    .select_from(turns.join(segments, turns.c.segment_id == segments.c.id))
                    .where(
                        turns.c.school_id == u.school_id,
                        turns.c.student_id == student.id,
                        turns.c.status == "completed",
                        segments.c.knowledge_key == str(seg["knowledge_key"]),
                    )
                )
                or 0
            )
            row = {
                "id": int(student.id),
                "name": str(student.name or ""),
                "sourceExerciseCorrect": bool(source_correct.get(int(student.id))),
                "priorSuccessEvidence": prior_success,
                "priorPresentationCount": prior_presentations,
            }
            row["signals"] = candidate_signals(
                source_exercise_correct=row["sourceExerciseCorrect"],
                prior_success_evidence=prior_success,
                prior_presentation_count=prior_presentations,
            )
            result.append(row)
        result.sort(key=candidate_sort_key)
        return result

    @app.post("/teacher/classroom-sessions/{sid}/segments/{segid}/invite")
    def invite_classroom_presenter(sid: int, segid: int, body: PresenterInviteBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        s = teacher_session_row(db, u, sid)
        seg = session_segment_row(db, u, sid, segid)
        if str(s["status"]) != "active":
            raise HTTPException(400, "请先开始课堂，再邀请学生讲解")
        if str(seg["mode"]) not in {"student", "co_teach"}:
            raise HTTPException(400, "当前知识点不是学生讲解或师生共讲模式")
        if str(seg["status"]) != "selecting_presenter":
            raise HTTPException(400, "当前知识点状态不能发送讲解邀请")
        if body.presenter_type not in {"student", "co_teach"} or str(seg["mode"]) != body.presenter_type:
            raise HTTPException(400, "邀请类型必须与当前知识点讲解方式一致")
        open_turn = current_turn(db, sid, segid)
        if open_turn and presenter_turn_is_open(open_turn["status"]):
            raise HTTPException(400, "当前已有待处理的学生讲解邀请")
        student = db.scalar(
            select(User)
            .join(ClassStudent, ClassStudent.student_id == User.id)
            .where(
                User.id == body.student_id,
                User.school_id == u.school_id,
                User.role == "student",
                User.active == True,
                ClassStudent.class_id == s["class_id"],
            )
        )
        if not student:
            raise HTTPException(404, "该学生不在当前班级或不可用")
        now = datetime.utcnow()
        tid = db.execute(
            turns.insert()
            .values(
                school_id=u.school_id,
                session_id=sid,
                segment_id=segid,
                student_id=student.id,
                requested_by=u.id,
                presenter_type=body.presenter_type,
                status="invited",
                note=body.note.strip()[:1000],
                invited_at=now,
                created_at=now,
            )
            .returning(turns.c.id)
        ).scalar_one()
        append_event(db, u, sid, "presenter.invited", segment_id=segid, payload={"turnID": int(tid), "studentID": int(student.id), "presenterType": body.presenter_type})
        implementation.audit(db, u, "classroom.presenter.invite", f"session={sid};segment={segid};student={student.id}")
        db.commit()
        return session_payload(db, u, sid)

    @app.post("/teacher/classroom-sessions/{sid}/presenter-turns/{tid}/state")
    def teacher_presenter_state(sid: int, tid: int, body: PresenterStateBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        s = teacher_session_row(db, u, sid)
        raw = db.execute(select(turns).where(turns.c.id == tid, turns.c.session_id == sid, turns.c.school_id == u.school_id)).first()
        if not raw:
            raise HTTPException(404, "讲解邀请不存在")
        turn = _mapping(raw)
        target = body.status.strip()
        if target not in {"withdrawn", "presenting"}:
            raise HTTPException(400, "教师端仅可撤回邀请或开始已确认的学生讲解")
        if target == "presenting" and str(s["status"]) != "active":
            raise HTTPException(400, "课堂未处于进行中，不能开始学生讲解")
        if not presenter_transition_allowed(str(turn["status"]), target):
            raise HTTPException(400, f"当前邀请状态不能切换为 {target}")
        values = {"status": target}
        if target == "presenting":
            values["started_at"] = datetime.utcnow()
            db.execute(segments.update().where(segments.c.id == int(turn["segment_id"])).values(status="explaining", updated_at=datetime.utcnow()))
            db.execute(sessions.update().where(sessions.c.id == sid).values(current_segment_id=int(turn["segment_id"]), updated_at=datetime.utcnow()))
        db.execute(turns.update().where(turns.c.id == tid).values(**values))
        append_event(db, u, sid, "presenter." + target, segment_id=int(turn["segment_id"]), payload={"turnID": tid, "studentID": int(turn["student_id"])})
        if target == "presenting":
            append_event(db, u, sid, "explanation.started", segment_id=int(turn["segment_id"]), payload={"mode": turn["presenter_type"]})
        db.commit()
        return session_payload(db, u, sid)

    @app.get("/student/classroom-invitations")
    def student_classroom_invitations(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        implementation.need(u, "student")
        rows = db.execute(
            select(
                turns,
                sessions.c.title.label("session_title"),
                sessions.c.status.label("session_status"),
                sessions.c.class_id.label("class_id"),
                segments.c.knowledge_key.label("knowledge_key"),
            )
            .select_from(turns.join(sessions, turns.c.session_id == sessions.c.id).join(segments, turns.c.segment_id == segments.c.id))
            .where(
                turns.c.school_id == u.school_id,
                turns.c.student_id == u.id,
                turns.c.status.in_(["invited", "accepted", "presenting"]),
                sessions.c.status.in_(["active", "paused"]),
            )
            .order_by(turns.c.id.desc())
        ).all()
        out = []
        for raw in rows:
            data = _mapping(raw)
            class_row = db.scalar(select(SchoolClass).where(SchoolClass.id == data["class_id"], SchoolClass.school_id == u.school_id))
            out.append(
                {
                    "id": int(data["id"]),
                    "sessionID": int(data["session_id"]),
                    "segmentID": int(data["segment_id"]),
                    "sessionTitle": str(data["session_title"] or ""),
                    "sessionStatus": str(data["session_status"]),
                    "className": str(getattr(class_row, "name", "") or ""),
                    "knowledgeKey": str(data["knowledge_key"] or ""),
                    "presenterType": str(data["presenter_type"]),
                    "status": str(data["status"]),
                    "note": str(data["note"] or ""),
                    "invitedAt": _iso(data["invited_at"]),
                }
            )
        return out

    @app.post("/student/classroom-invitations/{tid}/respond")
    def respond_classroom_invitation(tid: int, body: PresenterResponseBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        implementation.need(u, "student")
        raw = db.execute(select(turns).where(turns.c.id == tid, turns.c.school_id == u.school_id, turns.c.student_id == u.id)).first()
        if not raw:
            raise HTTPException(404, "课堂讲解邀请不存在")
        turn = _mapping(raw)
        target = body.response.strip()
        if target not in {"accepted", "declined"}:
            raise HTTPException(400, "只能选择接受或婉拒")
        if not presenter_transition_allowed(str(turn["status"]), target):
            raise HTTPException(400, "该邀请已经处理，不能重复提交")
        session_row = db.execute(select(sessions).where(sessions.c.id == int(turn["session_id"]), sessions.c.school_id == u.school_id)).first()
        if not session_row or str(_mapping(session_row)["status"]) not in {"active", "paused"}:
            raise HTTPException(400, "本次课堂已经结束或不可响应")
        db.execute(turns.update().where(turns.c.id == tid).values(status=target, responded_at=datetime.utcnow()))
        append_event(db, u, int(turn["session_id"]), "presenter." + target, segment_id=int(turn["segment_id"]), payload={"turnID": tid, "studentID": int(u.id)})
        implementation.audit(db, u, "classroom.presenter.respond", f"turn={tid};response={target}")
        db.commit()
        return {"ok": True, "status": target}

    def v1_response() -> HTMLResponse:
        return HTMLResponse(
            v1_module.v1_html(),
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "X-Changying-V1": V1_CLASSROOM_EXECUTION_MARKER,
            },
        )

    app.add_api_route("/v1/classroom-execution", v1_response, methods=["GET"], include_in_schema=False)
    app.add_api_route("/v1/classroom-invitations", v1_response, methods=["GET"], include_in_schema=False)
    app.state.v1_classroom_execution_routes_installed = True


__all__ = [
    "PresenterInviteBody",
    "PresenterResponseBody",
    "PresenterStateBody",
    "SegmentModeBody",
    "SegmentRevealBody",
    "SessionStateBody",
    "V1_CLASSROOM_EXECUTION_MARKER",
    "install_v1_classroom_execution_patch",
    "install_v1_classroom_execution_routes",
    "patch_v1_classroom_execution_html",
    "register_classroom_execution_tables",
]
