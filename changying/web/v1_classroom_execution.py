"""V1 live classroom execution: teacher state machine + presenter consent."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text, UniqueConstraint, func, select

from changying.services.classroom_execution import (
    can_start_segment,
    candidate_signals,
    candidate_sort_key,
    presenter_required,
    presenter_transition_allowed,
    segment_status_for_mode,
    session_transition_allowed,
    unique_knowledge_keys,
)
from changying.services.classroom_review import classroom_review_summary
from changying.web import v1 as v1_module


V1_CLASSROOM_EXECUTION_MARKER = "changying_v1_classroom_execution_ab_v1"


class SegmentModeBody(BaseModel):
    mode: str


class PresenterInviteBody(BaseModel):
    student_id: int
    presenter_type: str = "student"


class PresenterResponseBody(BaseModel):
    decision: str


class RevealPolicyBody(BaseModel):
    reveal_distribution: bool = False
    reveal_correct_answer: bool = False
    reveal_explanation: bool = False


def _json_list(raw: Any) -> list[Any]:
    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _row_data(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


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
            Column("source_assignment_id", Integer, nullable=False, index=True),
            Column("handout_id", Integer, nullable=False, index=True),
            Column("subject", String(80), nullable=False, default=""),
            Column("textbook", String(160), nullable=False, default=""),
            Column("title", String(220), nullable=False, default=""),
            Column("status", String(30), nullable=False, default="planned", index=True),
            Column("current_segment_id", Integer, nullable=True, index=True),
            Column("started_at", DateTime, nullable=True),
            Column("completed_at", DateTime, nullable=True),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
            Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint(
                "school_id",
                "source_assignment_id",
                name="uq_classroom_session_assignment",
            ),
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
            Column("mode", String(30), nullable=False, default="teacher", index=True),
            Column("status", String(40), nullable=False, default="planned", index=True),
            Column("baseline_accuracy", Integer, nullable=True),
            Column("postcheck_accuracy", Integer, nullable=True),
            Column("reveal_distribution", Boolean, nullable=False, default=False),
            Column("reveal_correct_answer", Boolean, nullable=False, default=False),
            Column("reveal_explanation", Boolean, nullable=False, default=False),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
            Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint(
                "session_id",
                "order_no",
                name="uq_classroom_segment_order",
            ),
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
            Column("student_id", Integer, nullable=True, index=True),
            Column("event_type", String(80), nullable=False, index=True),
            Column("detail_json", Text, nullable=False, default="{}"),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow, index=True),
        )

    return {"sessions": sessions, "segments": segments, "turns": turns, "events": events}


def patch_v1_classroom_execution_html(html: str) -> str:
    if V1_CLASSROOM_EXECUTION_MARKER in html:
        return html

    task_anchor = "const title=isSchool?'学校教学工作台':'培训机构教学工作台';"
    if task_anchor in html:
        html = html.replace(
            task_anchor,
            "if(session.role==='student'&&!tasks.includes('讲解邀请'))tasks.unshift('讲解邀请');"
            + task_anchor,
            1,
        )

    handler_old = "document.querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>{if(b.dataset.feature==='课堂复盘')navigate('/v1/classroom-review');else toast(b.dataset.feature+'：V1 入口已预留')});"
    handler_new = "document.querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>{if(b.dataset.feature==='课堂复盘')navigate('/v1/classroom-review');else if(b.dataset.feature==='讲解邀请')navigate('/v1/classroom-presenter');else toast(b.dataset.feature+'：V1 入口已预留')});"
    if handler_old in html:
        html = html.replace(handler_old, handler_new, 1)

    handout_section = "'<section class="section card"><h2>课堂练习情况讲义草稿</h2><div id="cy-handout-editor">'+draftEditor(draft)+'</div></section>';"
    if handout_section in html:
        html = html.replace(
            handout_section,
            "'<section class="section card"><h2>课堂练习情况讲义草稿</h2><div id="cy-handout-editor">'+draftEditor(draft)+'</div></section>'+"
            "(draft?'<section class="section card"><h2>课堂互动执行</h2><p class="muted">讲义确认后，可进入真实课堂状态机。学生讲解必须由学生本人确认。</p><button class="btn primary" id="cy-enter-classroom">进入课堂执行</button></section>':'');",
            1,
        )

    bind_anchor = "const bindSave=()=>{"
    if bind_anchor in html:
        html = html.replace(
            bind_anchor,
            "const enterClassroom=document.getElementById('cy-enter-classroom');"
            "if(enterClassroom)enterClassroom.onclick=async()=>{enterClassroom.disabled=true;"
            "try{const r=await api('/teacher/assignments/'+current+'/classroom-session',{method:'POST',body:'{}'});"
            "navigate('/v1/classroom-session?session='+r.session.id)}catch(err){toast(err.message);enterClassroom.disabled=false}};"
            + bind_anchor,
            1,
        )

    anchor = "    function v1QuestionTypeLabel(q){"
    if anchor not in html:
        raise RuntimeError("V1 classroom execution anchor not found")

    pages = r'''
    async function classroomSessionPage(){
      if(session.role!=='teacher'){toast('课堂执行仅教师可控制');navigate('/v1/workspace');return}
      const sid=Number(new URLSearchParams(location.search).get('session')||0);
      if(!sid){toast('缺少课堂会话');navigate('/v1/classroom-review');return}
      const load=async()=>await api('/teacher/classroom-sessions/'+sid);
      const act=async(path,body={})=>{try{await api(path,{method:'POST',body:JSON.stringify(body)});await renderPage()}catch(err){toast(err.message)}};
      const renderPage=async()=>{
        const data=await load(),s=data.session,segments=data.segments||[],events=data.events||[];
        const statusName={planned:'待开始',active:'进行中',paused:'已暂停',completed:'已完成',cancelled:'已取消'}[s.status]||s.status;
        const sessionBtns=(s.status==='planned'?'<button class="btn primary" id="cy-session-start">开始课堂</button>':s.status==='active'?'<button class="btn" id="cy-session-pause">暂停课堂</button>':s.status==='paused'?'<button class="btn primary" id="cy-session-resume">继续课堂</button>':'')+(s.status!=='completed'&&s.status!=='cancelled'?'<button class="btn" id="cy-session-complete">完成整堂课</button>':'');
        const segmentHtml=segments.map(seg=>{
          const turn=seg.presenterTurn||null,cands=seg.candidates||[];
          const modeOptions=[['teacher','教师讲解'],['student','学生讲解'],['co_teach','师生共讲'],['discussion','讨论'],['skipped','暂不讲解']].map(([v,n])=>'<option value="'+v+'" '+(seg.mode===v?'selected':'')+'>'+n+'</option>').join('');
          const candidateSelect=(seg.mode==='student'||seg.mode==='co_teach')?'<div class="field"><label>私密候选建议</label><select class="cy-candidate" data-seg="'+seg.id+'"><option value="">选择学生</option>'+cands.map(c=>'<option value="'+c.id+'">'+esc(c.name)+' · '+esc((c.signals||[]).join('；'))+'</option>').join('')+'</select></div><button class="btn cy-invite" data-seg="'+seg.id+'">发出讲解邀请</button>':'';
          const turnInfo=turn?'<div class="notice"><b>当前讲解邀请：</b>'+esc(turn.studentName||'')+' · '+esc({invited:'等待学生确认',accepted:'学生已同意',declined:'学生已拒绝',withdrawn:'已撤回',presenting:'正在讲解',completed:'讲解完成'}[turn.status]||turn.status)+'</div>':'';
          const canStart=(s.status==='active'&&['planned','selecting_presenter'].includes(seg.status)&&(!(seg.mode==='student'||seg.mode==='co_teach')||turn?.status==='accepted'));
          const controls='<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">'+(canStart?'<button class="btn primary cy-seg-start" data-seg="'+seg.id+'">开始本知识点</button>':'')+(seg.status==='explaining'?'<button class="btn primary cy-seg-complete" data-seg="'+seg.id+'">完成本知识点</button>':'')+'</div>';
          const reveal='<div class="notice"><b>结果展示控制（为随堂检验预留）：</b><label><input type="checkbox" class="cy-reveal" data-seg="'+seg.id+'" data-key="reveal_distribution" '+(seg.revealDistribution?'checked':'')+'> 班级分布</label>　<label><input type="checkbox" class="cy-reveal" data-seg="'+seg.id+'" data-key="reveal_correct_answer" '+(seg.revealCorrectAnswer?'checked':'')+'> 正确答案</label>　<label><input type="checkbox" class="cy-reveal" data-seg="'+seg.id+'" data-key="reveal_explanation" '+(seg.revealExplanation?'checked':'')+'> 解析</label></div>';
          return '<section class="card"><div class="section-head"><div><h2>'+seg.orderNo+'. '+esc(seg.knowledgeKey)+'</h2><p>原练习正确率：'+(seg.baselineAccuracy===null?'—':seg.baselineAccuracy+'%')+' · 状态：'+esc(seg.statusName)+'</p></div><select class="cy-mode" data-seg="'+seg.id+'" '+(seg.status==='explaining'||seg.status==='completed'?'disabled':'')+'>'+modeOptions+'</select></div>'+turnInfo+candidateSelect+controls+reveal+'</section>';
        }).join('');
        const timeline=events.slice().reverse().slice(0,30).map(e=>'<div class="row"><span class="row-main"><b>'+esc(e.label)+'</b><small>'+esc(e.createdAt||'')+'</small></span></div>').join('')||'<div class="empty">尚无课堂事件</div>';
        const content=heading('课堂互动执行',esc(s.title),'<button class="btn" id="cy-session-back">返回课堂复盘</button>')+
          '<section class="card"><div class="section-head"><div><h2>'+esc(s.className)+' · '+esc(s.subject)+'</h2><p>'+esc(s.textbook||'')+' · '+esc(statusName)+'</p></div><div>'+sessionBtns+'</div></div><div class="notice">教师控制课堂状态；学生讲解必须经过本人确认。当前版本先完成课堂状态机与讲解邀请，随堂检验/评分/互动积分将在下一阶段接入。</div></section>'+
          '<section class="section"><div class="section-head"><div><h2>知识点执行卡</h2><p>一个知识点一个状态，不把讲解表现直接写成知识掌握。</p></div></div><div class="list">'+segmentHtml+'</div></section>'+
          '<section class="section card"><h2>课堂事件时间线</h2><div class="list">'+timeline+'</div></section>';
        screen.innerHTML=shell(content,'workspace');bindNav();
        document.getElementById('cy-session-back').onclick=()=>navigate('/v1/classroom-review?assignment='+s.sourceAssignmentID);
        const start=document.getElementById('cy-session-start');if(start)start.onclick=()=>act('/teacher/classroom-sessions/'+sid+'/start');
        const pause=document.getElementById('cy-session-pause');if(pause)pause.onclick=()=>act('/teacher/classroom-sessions/'+sid+'/pause');
        const resume=document.getElementById('cy-session-resume');if(resume)resume.onclick=()=>act('/teacher/classroom-sessions/'+sid+'/resume');
        const complete=document.getElementById('cy-session-complete');if(complete)complete.onclick=()=>act('/teacher/classroom-sessions/'+sid+'/complete');
        document.querySelectorAll('.cy-mode').forEach(x=>x.onchange=()=>act('/teacher/classroom-segments/'+x.dataset.seg+'/mode',{mode:x.value}));
        document.querySelectorAll('.cy-invite').forEach(btn=>btn.onclick=()=>{const sel=document.querySelector('.cy-candidate[data-seg="'+btn.dataset.seg+'"]');if(!sel?.value){toast('请先选择学生');return}const seg=segments.find(x=>String(x.id)===String(btn.dataset.seg));act('/teacher/classroom-segments/'+btn.dataset.seg+'/invite',{student_id:Number(sel.value),presenter_type:seg?.mode==='co_teach'?'co_teach':'student'})});
        document.querySelectorAll('.cy-seg-start').forEach(btn=>btn.onclick=()=>act('/teacher/classroom-segments/'+btn.dataset.seg+'/start'));
        document.querySelectorAll('.cy-seg-complete').forEach(btn=>btn.onclick=()=>act('/teacher/classroom-segments/'+btn.dataset.seg+'/complete'));
        document.querySelectorAll('.cy-reveal').forEach(x=>x.onchange=async()=>{const seg=segments.find(v=>String(v.id)===String(x.dataset.seg));const body={reveal_distribution:seg.revealDistribution,reveal_correct_answer:seg.revealCorrectAnswer,reveal_explanation:seg.revealExplanation};body[x.dataset.key]=x.checked;await act('/teacher/classroom-segments/'+x.dataset.seg+'/reveal',body)});
      };await renderPage();
    }

    async function classroomPresenterPage(){
      if(session.role!=='student'){toast('讲解邀请仅学生本人可查看');navigate('/v1/workspace');return}
      let rows=[];try{rows=await api('/student/classroom-presenter-invitations')}catch(err){toast(err.message)}
      const cards=rows.map(r=>'<section class="card"><div class="section-head"><div><h2>'+esc(r.knowledgeKey)+'</h2><p>'+esc(r.className)+' · '+esc(r.sessionTitle)+'</p></div><span class="tag">'+esc({invited:'等待确认',accepted:'已同意',declined:'已拒绝',presenting:'正在讲解',completed:'已完成'}[r.status]||r.status)+'</span></div><p class="muted">讲解方式：'+esc(r.presenterType==='co_teach'?'师生共讲':'学生讲解')+'。是否参与由你本人决定。</p>'+(r.status==='invited'?'<div style="display:flex;gap:10px"><button class="btn primary cy-presenter-respond" data-id="'+r.id+'" data-decision="accept">同意讲解</button><button class="btn cy-presenter-respond" data-id="'+r.id+'" data-decision="decline">暂不参与</button></div>':'')+'</section>').join('')||'<div class="empty">目前没有需要你确认的讲解邀请。</div>';
      screen.innerHTML=shell(heading('课堂讲解邀请','教师可以邀请，但是否参与由你本人确认。','<button class="btn" id="cy-presenter-back">返回</button>')+'<div class="notice">这里不会显示其他学生的候选信息、排名或薄弱标签。</div><section class="section">'+cards+'</section>','workspace');bindNav();
      document.getElementById('cy-presenter-back').onclick=()=>navigate('/v1/workspace');
      document.querySelectorAll('.cy-presenter-respond').forEach(btn=>btn.onclick=async()=>{btn.disabled=true;try{await api('/student/classroom-presenter-invitations/'+btn.dataset.id+'/respond',{method:'POST',body:JSON.stringify({decision:btn.dataset.decision})});toast(btn.dataset.decision==='accept'?'已确认参与':'已确认暂不参与');await classroomPresenterPage()}catch(err){toast(err.message);btn.disabled=false}});
    }

'''
    html = html.replace(anchor, pages + anchor, 1)

    dispatch_old = "if(path.includes('/classroom-review'))await classroomReviewPage();else if(path.includes('/student'))await studentPage();"
    dispatch_new = "if(path.includes('/classroom-session'))await classroomSessionPage();else if(path.includes('/classroom-presenter'))await classroomPresenterPage();else if(path.includes('/classroom-review'))await classroomReviewPage();else if(path.includes('/student'))await studentPage();"
    if dispatch_old not in html:
        raise RuntimeError("V1 classroom execution dispatch anchor not found")
    html = html.replace(dispatch_old, dispatch_new, 1)

    return html.replace(
        "</head>",
        f'<meta name="{V1_CLASSROOM_EXECUTION_MARKER}" content="1"></head>',
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
    sessions,segments,turns,events = (
        tables["sessions"],tables["segments"],tables["turns"],tables["events"]
    )
    handouts = implementation.Base.metadata.tables.get("classroom_review_handouts")
    if handouts is None:
        raise RuntimeError("classroom_review_handouts must be registered first")

    Submission=implementation.Submission
    Question=implementation.Question
    Paper=implementation.Paper
    SchoolClass=implementation.SchoolClass
    LearningEvidenceEvent=implementation.LearningEvidenceEvent
    current_user=implementation.current_user
    get_db=implementation.get_db

    def event(db:Any,*,school_id:int,session_id:int,event_type:str,actor_id:int|None,
              segment_id:int|None=None,student_id:int|None=None,detail:dict[str,Any]|None=None)->None:
        db.execute(events.insert().values(
            school_id=school_id,session_id=session_id,segment_id=segment_id,
            actor_id=actor_id,student_id=student_id,event_type=event_type,
            detail_json=json.dumps(detail or {},ensure_ascii=False),created_at=datetime.utcnow(),
        ))

    def teacher_session_row(db:Any,user:Any,sid:int):
        implementation.need(user,"teacher")
        row=db.execute(select(sessions).where(
            sessions.c.id==sid,sessions.c.school_id==user.school_id,
            sessions.c.teacher_id==user.id,
        )).first()
        if not row: raise HTTPException(404,"课堂会话不存在或无权限")
        return row

    def teacher_segment_row(db:Any,user:Any,segid:int):
        implementation.need(user,"teacher")
        row=db.execute(select(segments).where(
            segments.c.id==segid,segments.c.school_id==user.school_id,
        )).first()
        if not row: raise HTTPException(404,"课堂知识点不存在")
        teacher_session_row(db,user,int(_row_data(row)["session_id"]))
        return row

    def latest_turn(db:Any,segid:int):
        return db.execute(select(turns).where(turns.c.segment_id==segid).order_by(turns.c.id.desc()).limit(1)).first()

    def candidate_rows(db:Any,user:Any,session_row:Any,segment_row:Any)->list[dict[str,Any]]:
        s=_row_data(session_row);seg=_row_data(segment_row)
        assignment=implementation.teacher_assignment_for(
            db,user.school_id,user.id,int(s["source_assignment_id"])
        )
        if not assignment: return []
        students=implementation.recipient_students(db,assignment)
        student_ids=[int(x.id) for x in students]
        paper=db.scalar(select(Paper).where(Paper.id==assignment.paper_id,Paper.school_id==user.school_id))
        qids=[int(x) for x in _json_list(getattr(paper,"question_ids_json","[]")) if str(x).isdigit()]
        qrows=list(db.scalars(select(Question).where(
            Question.school_id==user.school_id,Question.id.in_(qids)
        )).all()) if qids else []
        matching_qids={int(q.id) for q in qrows if str(getattr(q,"knowledge","") or "").strip()==str(seg["knowledge_key"])}
        source_correct:set[int]=set()
        if student_ids and matching_qids:
            submissions=db.scalars(select(Submission).where(
                Submission.school_id==user.school_id,
                Submission.assignment_id==assignment.id,
                Submission.student_id.in_(student_ids),
            )).all()
            for sub in submissions:
                for answer in _json_list(getattr(sub,"answers_json","[]")):
                    if isinstance(answer,dict) and int(answer.get("question_id") or 0) in matching_qids and answer.get("correct") is True:
                        source_correct.add(int(sub.student_id));break

        evidence_counts={sid:0 for sid in student_ids}
        if student_ids:
            rows=db.scalars(select(LearningEvidenceEvent).where(
                LearningEvidenceEvent.school_id==user.school_id,
                LearningEvidenceEvent.student_id.in_(student_ids),
                LearningEvidenceEvent.knowledge_key==str(seg["knowledge_key"]),
                LearningEvidenceEvent.success==True,
            )).all()
            for row in rows:
                evidence_counts[int(row.student_id)]=evidence_counts.get(int(row.student_id),0)+1

        prior_counts={sid:0 for sid in student_ids}
        if student_ids:
            rows=db.execute(
                select(turns.c.student_id,func.count(turns.c.id))
                .select_from(turns.join(segments,turns.c.segment_id==segments.c.id))
                .where(
                    turns.c.school_id==user.school_id,
                    turns.c.student_id.in_(student_ids),
                    turns.c.status=="completed",
                    segments.c.knowledge_key==str(seg["knowledge_key"]),
                ).group_by(turns.c.student_id)
            ).all()
            for sid,count in rows: prior_counts[int(sid)]=int(count)

        payload=[]
        for student in students:
            sid=int(student.id)
            item={
                "id":sid,"name":str(student.name or ""),
                "sourceExerciseCorrect":sid in source_correct,
                "priorSuccessEvidence":evidence_counts.get(sid,0),
                "priorPresentationCount":prior_counts.get(sid,0),
            }
            item["signals"]=candidate_signals(
                source_exercise_correct=item["sourceExerciseCorrect"],
                prior_success_evidence=item["priorSuccessEvidence"],
                prior_presentation_count=item["priorPresentationCount"],
            )
            payload.append(item)
        payload.sort(key=candidate_sort_key)
        return payload

    def presenter_payload(db:Any,row:Any)->dict[str,Any]|None:
        if not row:return None
        data=_row_data(row);student=db.get(implementation.User,int(data["student_id"]))
        return {
            "id":int(data["id"]),"studentID":int(data["student_id"]),
            "studentName":str(getattr(student,"name","") or ""),
            "presenterType":str(data["presenter_type"]),"status":str(data["status"]),
            "invitedAt":data["invited_at"].isoformat(timespec="minutes") if data["invited_at"] else "",
            "respondedAt":data["responded_at"].isoformat(timespec="minutes") if data["responded_at"] else "",
        }

    def session_payload(db:Any,user:Any,session_row:Any)->dict[str,Any]:
        data=_row_data(session_row);class_row=db.get(SchoolClass,int(data["class_id"]))
        segment_rows=db.execute(select(segments).where(
            segments.c.session_id==int(data["id"])
        ).order_by(segments.c.order_no)).all()
        out=[]
        for row in segment_rows:
            seg=_row_data(row);turn=latest_turn(db,int(seg["id"]))
            out.append({
                "id":int(seg["id"]),"knowledgeKey":str(seg["knowledge_key"]),
                "title":str(seg["title"] or ""),"orderNo":int(seg["order_no"]),
                "mode":str(seg["mode"]),"status":str(seg["status"]),
                "statusName":{"planned":"待执行","selecting_presenter":"选择讲解者","explaining":"讲解中","checking":"随堂检验","reviewed":"已复盘","completed":"已完成"}.get(str(seg["status"]),str(seg["status"])),
                "baselineAccuracy":seg["baseline_accuracy"],"postcheckAccuracy":seg["postcheck_accuracy"],
                "revealDistribution":bool(seg["reveal_distribution"]),
                "revealCorrectAnswer":bool(seg["reveal_correct_answer"]),
                "revealExplanation":bool(seg["reveal_explanation"]),
                "presenterTurn":presenter_payload(db,turn),
                "candidates":candidate_rows(db,user,session_row,row)
                    if str(seg["mode"]) in {"student","co_teach"} and str(seg["status"])!="completed" else [],
            })
        event_rows=db.execute(select(events).where(
            events.c.session_id==int(data["id"])
        ).order_by(events.c.id.desc()).limit(80)).all()
        labels={
            "session.created":"课堂执行已创建","session.started":"课堂开始",
            "session.paused":"课堂暂停","session.resumed":"课堂继续",
            "session.completed":"课堂完成","segment.mode_changed":"讲解方式已调整",
            "segment.started":"知识点讲解开始","segment.completed":"知识点讲解完成",
            "segment.skipped":"知识点暂不讲解","presenter.invited":"已发出学生讲解邀请",
            "presenter.accepted":"学生已同意讲解","presenter.declined":"学生暂不参与讲解",
            "explanation.started":"讲解开始","explanation.completed":"讲解完成",
            "results.policy_changed":"结果展示策略已调整",
        }
        return {
            "session":{
                "id":int(data["id"]),"classID":int(data["class_id"]),
                "className":str(getattr(class_row,"name","") or ""),
                "teacherID":int(data["teacher_id"]),
                "sourceAssignmentID":int(data["source_assignment_id"]),
                "handoutID":int(data["handout_id"]),
                "subject":str(data["subject"] or ""),"textbook":str(data["textbook"] or ""),
                "title":str(data["title"] or ""),"status":str(data["status"]),
                "currentSegmentID":data["current_segment_id"],
                "startedAt":data["started_at"].isoformat(timespec="minutes") if data["started_at"] else "",
                "completedAt":data["completed_at"].isoformat(timespec="minutes") if data["completed_at"] else "",
            },
            "segments":out,
            "events":[{
                "id":int(_row_data(row)["id"]),"type":str(_row_data(row)["event_type"]),
                "label":labels.get(str(_row_data(row)["event_type"]),str(_row_data(row)["event_type"])),
                "createdAt":_row_data(row)["created_at"].isoformat(timespec="minutes") if _row_data(row)["created_at"] else "",
            } for row in event_rows],
        }

    @app.post("/teacher/assignments/{aid}/classroom-session")
    def create_or_get_classroom_session(aid:int,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        implementation.need(u,"teacher")
        assignment=implementation.teacher_assignment_for(db,u.school_id,u.id,aid)
        if not assignment: raise HTTPException(404,"课堂练习不存在或无权限")
        current=db.execute(select(sessions).where(
            sessions.c.school_id==u.school_id,sessions.c.source_assignment_id==aid
        )).first()
        if current:return session_payload(db,u,current)

        handout=db.execute(select(handouts).where(
            handouts.c.school_id==u.school_id,handouts.c.assignment_id==aid,
            handouts.c.teacher_id==u.id,
        )).first()
        if not handout: raise HTTPException(400,"请先生成并保存课堂复盘讲义，再进入课堂执行")
        h=_row_data(handout)
        selected_knowledge=unique_knowledge_keys([str(x) for x in _json_list(h.get("selected_knowledge_json"))])
        selected_qids=[int(x) for x in _json_list(h.get("selected_question_ids_json")) if str(x).isdigit()]
        if selected_qids:
            qrows=db.scalars(select(Question).where(
                Question.school_id==u.school_id,Question.id.in_(selected_qids)
            )).all()
            selected_knowledge=unique_knowledge_keys([
                *selected_knowledge,*[str(q.knowledge or "") for q in qrows]
            ])
        if not selected_knowledge: raise HTTPException(400,"当前讲义没有可执行的知识点，请回到课堂复盘重新选择")

        class_row=db.get(SchoolClass,assignment.class_id);paper=db.get(Paper,assignment.paper_id)
        if not class_row or not paper: raise HTTPException(400,"课堂练习缺少班级或试卷数据")
        recipients=implementation.recipient_students(db,assignment);recipient_ids=[int(x.id) for x in recipients]
        submissions=list(db.scalars(select(Submission).where(
            Submission.school_id==u.school_id,Submission.assignment_id==aid,
            Submission.student_id.in_(recipient_ids),
        )).all()) if recipient_ids else []
        qids=[int(x) for x in _json_list(paper.question_ids_json) if str(x).isdigit()]
        questions=list(db.scalars(select(Question).where(
            Question.school_id==u.school_id,Question.id.in_(qids)
        )).all()) if qids else []
        review=classroom_review_summary(
            assignment=assignment,class_row=class_row,paper=paper,
            recipients=recipients,submissions=submissions,questions=questions,
        )
        baseline={str(x.get("knowledge") or ""):int(x.get("accuracy") or 0) for x in review.get("knowledgeStats",[])}

        now=datetime.utcnow()
        sid=int(db.execute(sessions.insert().values(
            school_id=u.school_id,class_id=assignment.class_id,teacher_id=u.id,
            source_assignment_id=aid,handout_id=int(h["id"]),
            subject=str(paper.subject or ""),textbook=str(paper.textbook or ""),
            title=f"{class_row.name} · {assignment.title} 课堂互动执行",
            status="planned",created_at=now,updated_at=now,
        ).returning(sessions.c.id)).scalar_one())
        for order_no,knowledge in enumerate(selected_knowledge,start=1):
            db.execute(segments.insert().values(
                school_id=u.school_id,session_id=sid,knowledge_key=knowledge,title=knowledge,
                order_no=order_no,mode="teacher",status="planned",
                baseline_accuracy=baseline.get(knowledge),
                reveal_distribution=False,reveal_correct_answer=False,reveal_explanation=False,
                created_at=now,updated_at=now,
            ))
        event(db,school_id=u.school_id,session_id=sid,event_type="session.created",
              actor_id=u.id,detail={"assignment_id":aid,"knowledge_count":len(selected_knowledge)})
        implementation.audit(db,u,"classroom.session.create",f"session={sid};assignment={aid};segments={len(selected_knowledge)}")
        db.commit()
        row=db.execute(select(sessions).where(sessions.c.id==sid)).first()
        return session_payload(db,u,row)

    @app.get("/teacher/classroom-sessions/{sid}")
    def get_classroom_session(sid:int,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        return session_payload(db,u,teacher_session_row(db,u,sid))

    def transition_session(db:Any,u:Any,sid:int,target:str,event_type:str):
        row=teacher_session_row(db,u,sid);data=_row_data(row)
        if not session_transition_allowed(str(data["status"]),target):
            raise HTTPException(400,f"课堂状态不能从 {data['status']} 切换为 {target}")
        values={"status":target,"updated_at":datetime.utcnow()}
        if target=="active" and not data["started_at"]:values["started_at"]=datetime.utcnow()
        if target=="completed":
            open_count=int(db.scalar(select(func.count()).select_from(segments).where(
                segments.c.session_id==sid,segments.c.status!="completed"
            )) or 0)
            if open_count>0:raise HTTPException(400,"还有未完成的知识点，不能结束整堂课")
            values["completed_at"]=datetime.utcnow();values["current_segment_id"]=None
        db.execute(sessions.update().where(sessions.c.id==sid).values(**values))
        event(db,school_id=u.school_id,session_id=sid,event_type=event_type,actor_id=u.id)
        implementation.audit(db,u,event_type,f"session={sid}")
        db.commit()
        return session_payload(db,u,db.execute(select(sessions).where(sessions.c.id==sid)).first())

    @app.post("/teacher/classroom-sessions/{sid}/start")
    def start_classroom_session(sid:int,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        return transition_session(db,u,sid,"active","session.started")

    @app.post("/teacher/classroom-sessions/{sid}/pause")
    def pause_classroom_session(sid:int,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        return transition_session(db,u,sid,"paused","session.paused")

    @app.post("/teacher/classroom-sessions/{sid}/resume")
    def resume_classroom_session(sid:int,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        return transition_session(db,u,sid,"active","session.resumed")

    @app.post("/teacher/classroom-sessions/{sid}/complete")
    def complete_classroom_session(sid:int,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        return transition_session(db,u,sid,"completed","session.completed")

    @app.post("/teacher/classroom-segments/{segid}/mode")
    def set_segment_mode(segid:int,body:SegmentModeBody,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        row=teacher_segment_row(db,u,segid);data=_row_data(row)
        if str(data["status"]) in {"explaining","checking","reviewed","completed"}:
            raise HTTPException(400,"当前知识点已开始执行，不能再修改讲解方式")
        try:status=segment_status_for_mode(body.mode.strip())
        except ValueError:raise HTTPException(400,"讲解方式无效")
        mode=body.mode.strip()
        db.execute(segments.update().where(segments.c.id==segid).values(
            mode=mode,status=status,updated_at=datetime.utcnow()
        ))
        event(db,school_id=u.school_id,session_id=int(data["session_id"]),segment_id=segid,
              event_type="segment.skipped" if mode=="skipped" else "segment.mode_changed",
              actor_id=u.id,detail={"mode":mode})
        implementation.audit(db,u,"classroom.segment.mode",f"segment={segid};mode={mode}")
        db.commit();return {"ok":True}

    @app.post("/teacher/classroom-segments/{segid}/reveal")
    def set_reveal_policy(segid:int,body:RevealPolicyBody,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        row=teacher_segment_row(db,u,segid);data=_row_data(row)
        db.execute(segments.update().where(segments.c.id==segid).values(
            reveal_distribution=body.reveal_distribution,
            reveal_correct_answer=body.reveal_correct_answer,
            reveal_explanation=body.reveal_explanation,updated_at=datetime.utcnow(),
        ))
        event(db,school_id=u.school_id,session_id=int(data["session_id"]),segment_id=segid,
              event_type="results.policy_changed",actor_id=u.id,detail=body.model_dump())
        db.commit();return {"ok":True}

    @app.post("/teacher/classroom-segments/{segid}/invite")
    def invite_presenter(segid:int,body:PresenterInviteBody,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        row=teacher_segment_row(db,u,segid);data=_row_data(row)
        session_row=teacher_session_row(db,u,int(data["session_id"]));s=_row_data(session_row)
        if str(s["status"])!="active":raise HTTPException(400,"请先开始课堂，再邀请学生讲解")
        if str(data["mode"]) not in {"student","co_teach"}:raise HTTPException(400,"当前知识点不是学生讲解或师生共讲模式")
        if body.presenter_type not in {"student","co_teach"}:raise HTTPException(400,"讲解者类型无效")
        allowed={int(x["id"]) for x in candidate_rows(db,u,session_row,row)}
        if int(body.student_id) not in allowed:raise HTTPException(400,"该学生不在当前班级/练习接收范围内")
        previous=latest_turn(db,segid)
        if previous and str(_row_data(previous)["status"]) in {"invited","accepted","presenting"}:
            raise HTTPException(400,"当前已有未结束的讲解邀请")
        now=datetime.utcnow()
        turn_id=int(db.execute(turns.insert().values(
            school_id=u.school_id,session_id=int(data["session_id"]),segment_id=segid,
            student_id=int(body.student_id),requested_by=u.id,
            presenter_type=body.presenter_type,status="invited",
            invited_at=now,created_at=now,
        ).returning(turns.c.id)).scalar_one())
        db.execute(segments.update().where(segments.c.id==segid).values(
            status="selecting_presenter",updated_at=now
        ))
        event(db,school_id=u.school_id,session_id=int(data["session_id"]),segment_id=segid,
              student_id=int(body.student_id),event_type="presenter.invited",
              actor_id=u.id,detail={"turn_id":turn_id,"presenter_type":body.presenter_type})
        implementation.audit(db,u,"classroom.presenter.invite",
                             f"session={data['session_id']};segment={segid};student={body.student_id}")
        db.commit();return {"ok":True,"turnID":turn_id}

    @app.get("/student/classroom-presenter-invitations")
    def student_presenter_invitations(u:Any=Depends(current_user),db:Any=Depends(get_db)):
        implementation.need(u,"student")
        rows=db.execute(
            select(turns,segments.c.knowledge_key,sessions.c.title,sessions.c.class_id)
            .select_from(turns.join(segments,turns.c.segment_id==segments.c.id)
                         .join(sessions,turns.c.session_id==sessions.c.id))
            .where(turns.c.school_id==u.school_id,turns.c.student_id==u.id,
                   turns.c.status.in_(["invited","accepted","presenting","completed"]))
            .order_by(turns.c.id.desc()).limit(50)
        ).all()
        out=[]
        for row in rows:
            m=row._mapping;class_row=db.get(SchoolClass,int(m["class_id"]))
            out.append({
                "id":int(m["id"]),"sessionID":int(m["session_id"]),
                "segmentID":int(m["segment_id"]),"knowledgeKey":str(m["knowledge_key"]),
                "sessionTitle":str(m["title"] or ""),"className":str(getattr(class_row,"name","") or ""),
                "presenterType":str(m["presenter_type"]),"status":str(m["status"]),
                "invitedAt":m["invited_at"].isoformat(timespec="minutes") if m["invited_at"] else "",
            })
        return out

    @app.post("/student/classroom-presenter-invitations/{turnid}/respond")
    def respond_presenter_invitation(turnid:int,body:PresenterResponseBody,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        implementation.need(u,"student")
        row=db.execute(select(turns).where(
            turns.c.id==turnid,turns.c.school_id==u.school_id,turns.c.student_id==u.id
        )).first()
        if not row:raise HTTPException(404,"讲解邀请不存在")
        data=_row_data(row);target={"accept":"accepted","decline":"declined"}.get(body.decision.strip())
        if not target or not presenter_transition_allowed(str(data["status"]),target):
            raise HTTPException(400,"当前邀请状态不能执行此操作")
        now=datetime.utcnow()
        db.execute(turns.update().where(turns.c.id==turnid).values(status=target,responded_at=now))
        event(db,school_id=u.school_id,session_id=int(data["session_id"]),segment_id=int(data["segment_id"]),
              student_id=u.id,event_type=f"presenter.{target}",actor_id=u.id,detail={"turn_id":turnid})
        implementation.audit(db,u,f"classroom.presenter.{target}",f"turn={turnid};session={data['session_id']}")
        db.commit();return {"ok":True,"status":target}

    @app.post("/teacher/classroom-segments/{segid}/start")
    def start_segment(segid:int,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        row=teacher_segment_row(db,u,segid);data=_row_data(row)
        session_row=teacher_session_row(db,u,int(data["session_id"]));s=_row_data(session_row)
        turn=latest_turn(db,segid);td=_row_data(turn) if turn else {}
        ok,reason=can_start_segment(
            session_status=str(s["status"]),segment_status=str(data["status"]),
            mode=str(data["mode"]),presenter_status=str(td.get("status") or "") or None,
        )
        if not ok:raise HTTPException(400,reason)
        now=datetime.utcnow();student_id=None
        if presenter_required(str(data["mode"])):
            student_id=int(td["student_id"])
            db.execute(turns.update().where(turns.c.id==int(td["id"])).values(
                status="presenting",started_at=now
            ))
        db.execute(segments.update().where(segments.c.id==segid).values(status="explaining",updated_at=now))
        db.execute(sessions.update().where(sessions.c.id==int(data["session_id"])).values(
            current_segment_id=segid,updated_at=now
        ))
        event(db,school_id=u.school_id,session_id=int(data["session_id"]),segment_id=segid,
              student_id=student_id,event_type="explanation.started",actor_id=u.id,
              detail={"mode":str(data["mode"])})
        implementation.audit(db,u,"classroom.segment.start",f"segment={segid};mode={data['mode']}")
        db.commit();return {"ok":True}

    @app.post("/teacher/classroom-segments/{segid}/complete")
    def complete_segment(segid:int,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        row=teacher_segment_row(db,u,segid);data=_row_data(row)
        if str(data["status"])!="explaining":raise HTTPException(400,"只有正在讲解的知识点可以完成")
        now=datetime.utcnow();turn=latest_turn(db,segid);completed_student_id=None
        if turn:
            td=_row_data(turn)
            if str(td["status"])=="presenting":
                completed_student_id=int(td["student_id"])
                db.execute(turns.update().where(turns.c.id==int(td["id"])).values(
                    status="completed",completed_at=now
                ))
        db.execute(segments.update().where(segments.c.id==segid).values(status="completed",updated_at=now))
        db.execute(sessions.update().where(sessions.c.id==int(data["session_id"])).values(
            current_segment_id=None,updated_at=now
        ))
        event(db,school_id=u.school_id,session_id=int(data["session_id"]),segment_id=segid,
              event_type="explanation.completed",actor_id=u.id,student_id=completed_student_id)
        event(db,school_id=u.school_id,session_id=int(data["session_id"]),segment_id=segid,
              event_type="segment.completed",actor_id=u.id)
        implementation.audit(db,u,"classroom.segment.complete",f"segment={segid}")
        db.commit();return {"ok":True}

    def v1_response():
        return HTMLResponse(
            v1_module.v1_html(),
            headers={"Cache-Control":"no-store, no-cache, must-revalidate, max-age=0",
                     "X-Changying-V1":V1_CLASSROOM_EXECUTION_MARKER},
        )

    app.add_api_route("/v1/classroom-session",v1_response,methods=["GET"],include_in_schema=False)
    app.add_api_route("/v1/classroom-presenter",v1_response,methods=["GET"],include_in_schema=False)
    app.state.v1_classroom_execution_routes_installed=True


__all__=[
    "PresenterInviteBody","PresenterResponseBody","RevealPolicyBody","SegmentModeBody",
    "V1_CLASSROOM_EXECUTION_MARKER","install_v1_classroom_execution_patch",
    "install_v1_classroom_execution_routes","patch_v1_classroom_execution_html",
    "register_classroom_execution_tables",
]
