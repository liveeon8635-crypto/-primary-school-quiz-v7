"""Live classroom Phase C: teacher-controlled quick checks and immediate feedback."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text, UniqueConstraint, select

from changying.services.classroom_execution import segment_status_for_mode
from changying.services.classroom_quick_check import (
    clean_ai_quick_check,
    normalize_quick_check_type,
    quick_check_prompt,
    quick_check_summary,
)
from changying.web import v1 as v1_module


V1_CLASSROOM_QUICK_CHECK_MARKER = "changying_v1_classroom_quick_check_c_v1"


class QuickCheckDraftBody(BaseModel):
    question_type: str = "single_choice"
    notes: str = ""
    use_ai: bool = True


class QuickCheckEditBody(BaseModel):
    question_text: str = ""
    options: list[str] = Field(default_factory=list)
    correct_index: int = 0
    explanation: str = ""


class QuickCheckStateBody(BaseModel):
    status: str


class QuickCheckResponseBody(BaseModel):
    selected_index: int


class QuickCheckDecisionBody(BaseModel):
    decision: str


def register_classroom_quick_check_tables(implementation: Any) -> dict[str, Table]:
    metadata = implementation.Base.metadata
    checks = metadata.tables.get("classroom_quick_checks")
    if checks is None:
        checks = Table(
            "classroom_quick_checks",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("segment_id", Integer, nullable=False, index=True),
            Column("created_by", Integer, nullable=False, index=True),
            Column("question_type", String(30), nullable=False, default="single_choice"),
            Column("question_text", Text, nullable=False, default=""),
            Column("options_json", Text, nullable=False, default="[]"),
            Column("correct_index", Integer, nullable=False, default=0),
            Column("explanation", Text, nullable=False, default=""),
            Column("status", String(20), nullable=False, default="draft", index=True),
            Column("decision", String(20), nullable=False, default=""),
            Column("opened_at", DateTime, nullable=True),
            Column("closed_at", DateTime, nullable=True),
            Column("decided_at", DateTime, nullable=True),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
            Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
        )

    responses = metadata.tables.get("classroom_quick_check_responses")
    if responses is None:
        responses = Table(
            "classroom_quick_check_responses",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("check_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("segment_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("selected_index", Integer, nullable=False),
            Column("is_correct", Boolean, nullable=False),
            Column("submitted_at", DateTime, nullable=False, default=datetime.utcnow),
            Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint("check_id", "student_id", name="uq_classroom_quick_check_student"),
        )
    return {"checks": checks, "responses": responses}


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


def patch_v1_classroom_quick_check_html(html: str) -> str:
    if V1_CLASSROOM_QUICK_CHECK_MARKER in html:
        return html

    title_anchor = "const title=isSchool?'学校教学工作台':'培训机构教学工作台';"
    if title_anchor not in html:
        raise RuntimeError("quick-check workspace title anchor not found")
    html = html.replace(
        title_anchor,
        "if(session.role==='student'&&!tasks.includes('随堂检测'))tasks.unshift('随堂检测');" + title_anchor,
        1,
    )

    handler = "document.querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>{if(b.dataset.feature==='课堂复盘')navigate('/v1/classroom-review');else if(b.dataset.feature==='课堂互动')navigate('/v1/classroom-invitations');else toast(b.dataset.feature+'：V1 入口已预留')});"
    if handler not in html:
        raise RuntimeError("quick-check workspace handler anchor not found")
    html = html.replace(
        handler,
        "document.querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>{if(b.dataset.feature==='课堂复盘')navigate('/v1/classroom-review');else if(b.dataset.feature==='课堂互动')navigate('/v1/classroom-invitations');else if(b.dataset.feature==='随堂检测')navigate('/v1/classroom-quick-checks');else toast(b.dataset.feature+'：V1 入口已预留')});",
        1,
    )

    reload_anchor = "const reload=async()=>{data=await api('/teacher/classroom-sessions/'+sid);renderExec()};"
    if reload_anchor not in html:
        raise RuntimeError("quick-check classroom reload anchor not found")
    html = html.replace(
        reload_anchor,
        "const reload=async()=>{const pair=await Promise.all([api('/teacher/classroom-sessions/'+sid),api('/teacher/classroom-sessions/'+sid+'/quick-checks')]);data=pair[0];data.quickChecks=pair[1]||[];renderExec()};",
        1,
    )

    call_anchor = "const call=async(path,body)=>{await api(path,{method:'POST',body:JSON.stringify(body||{})});await reload()};"
    if call_anchor not in html:
        raise RuntimeError("quick-check classroom call anchor not found")
    helper = r'''
      const quickCheckBlock=(seg,s)=>{
        const rows=(data.quickChecks||[]).filter(x=>Number(x.segmentID)===Number(seg.id));
        const q=rows.length?rows[0]:null;
        if(!q){
          if(s.status!=='active'||!['completed','reviewed'].includes(seg.status))return '';
          return '<div class="notice" style="margin-top:10px"><b>随堂检测</b><p class="muted">由教师决定是否发起；学生结果只作为本堂课反馈，不自动加分或写入长期掌握证据。</p><div style="display:flex;gap:8px;flex-wrap:wrap"><select class="cy-q-type" data-seg="'+seg.id+'"><option value="single_choice">单选题</option><option value="true_false">判断题</option></select><button class="btn primary cy-q-generate" data-seg="'+seg.id+'">AI生成草稿</button><button class="btn cy-q-manual" data-seg="'+seg.id+'">手工建立草稿</button></div></div>';
        }
        const opts=q.options||[],stats=q.stats||{},letters=['A','B','C','D'];
        const statText=stats.responseCount===0?'暂无学生提交':('已提交 '+stats.responseCount+' 人 · 正确 '+stats.correctCount+' 人 · 正确率 '+(stats.accuracy===null?'—':stats.accuracy+'%'));
        if(q.status==='draft'){
          const inputs=opts.map((x,i)=>'<div class="field"><label>选项 '+(q.questionType==='true_false'?(i===0?'正确':'错误'):(letters[i]||i+1))+'</label><input class="cy-q-opt" data-check="'+q.id+'" data-index="'+i+'" value="'+esc(x||'')+'" '+(q.questionType==='true_false'?'readonly':'')+'></div>').join('');
          return '<div class="notice" style="margin-top:10px"><b>随堂检测草稿 · 尚未向学生开放</b><div class="field"><label>题干</label><textarea class="cy-q-text" data-check="'+q.id+'" rows="2">'+esc(q.questionText||'')+'</textarea></div>'+inputs+'<div class="field"><label>正确答案</label><select class="cy-q-correct" data-check="'+q.id+'">'+opts.map((_,i)=>'<option value="'+i+'" '+(i===q.correctIndex?'selected':'')+'>'+esc(q.questionType==='true_false'?(i===0?'正确':'错误'):(letters[i]||String(i+1)))+'</option>').join('')+'</select></div><div class="field"><label>解析</label><textarea class="cy-q-explain" data-check="'+q.id+'" rows="2">'+esc(q.explanation||'')+'</textarea></div><div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn cy-q-save" data-check="'+q.id+'">保存草稿</button><button class="btn primary cy-q-open" data-check="'+q.id+'">教师确认并开始检测</button></div></div>';
        }
        if(q.status==='open'){
          return '<div class="notice" style="margin-top:10px"><b>随堂检测进行中</b><p>'+esc(q.questionText)+'</p><div class="list">'+opts.map((x,i)=>'<div class="row"><span class="row-main"><b>'+esc((letters[i]||String(i+1))+'. '+x)+'</b></span><span class="tag">'+((stats.distribution||[])[i]?.count||0)+'人</span></div>').join('')+'</div><p class="muted">'+esc(statText)+'</p><button class="btn primary cy-q-close" data-check="'+q.id+'">结束检测并查看反馈</button></div>';
        }
        const answer=opts[q.correctIndex]||'';
        const decision=q.decision?('<span class="tag">教师决定：'+(q.decision==='reteach'?'继续讲解':'确认完成')+'</span>'):'';
        const actions=!q.decision&&seg.status==='reviewed'?'<div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn primary cy-q-decision" data-check="'+q.id+'" data-decision="complete">本知识点确认完成</button><button class="btn cy-q-decision" data-check="'+q.id+'" data-decision="reteach">根据反馈继续讲解</button></div>':'';
        const again=q.decision==='complete'&&seg.status==='completed'&&s.status==='active'?'<div style="margin-top:8px"><select class="cy-q-type" data-seg="'+seg.id+'"><option value="single_choice">单选题</option><option value="true_false">判断题</option></select> <button class="btn cy-q-generate" data-seg="'+seg.id+'">再生成一轮检测</button></div>':'';
        return '<div class="notice" style="margin-top:10px"><b>随堂检测已结束</b><p>'+esc(q.questionText)+'</p><p>'+esc(statText)+'</p><p>正确答案：'+esc(answer)+'</p>'+(q.explanation?'<p class="muted">解析：'+esc(q.explanation)+'</p>':'')+decision+actions+again+'</div>';
      };
'''
    html = html.replace(call_anchor, call_anchor + helper, 1)

    card_anchor = "<div id=\"cy-candidates-'+seg.id+'\"></div>'+reveal+'</section>';"
    if card_anchor not in html:
        raise RuntimeError("quick-check classroom card anchor not found")
    html = html.replace(
        card_anchor,
        "<div id=\"cy-candidates-'+seg.id+'\"></div>'+reveal+quickCheckBlock(seg,s)+'</section>';",
        1,
    )

    html = html.replace(
        "Phase C 接入即时检测后才真正向学生端展示。",
        "关闭随堂检测后，按教师勾选项向学生展示。",
        1,
    )
    html = html.replace(
        "本阶段只负责课堂状态与讲解者确认；随堂检验、讲解评价和互动积分将在下一阶段接入。",
        "讲解后可由教师主动发起随堂检测；检测只形成课堂反馈，不自动加分或写入知识掌握。",
        1,
    )

    bind_anchor = "      };\n      await reload();\n    }\n\n    async function classroomInvitationsPage(){"
    if bind_anchor not in html:
        raise RuntimeError("quick-check classroom binding anchor not found")
    bindings = r'''
        document.querySelectorAll('.cy-q-generate').forEach(b=>b.onclick=async()=>{const seg=b.dataset.seg,type=document.querySelector('.cy-q-type[data-seg="'+seg+'"]')?.value||'single_choice';b.disabled=true;try{await api('/teacher/classroom-sessions/'+sid+'/segments/'+seg+'/quick-checks/draft',{method:'POST',body:JSON.stringify({question_type:type,use_ai:true}),timeoutMs:90000});toast('随堂检测草稿已生成，请教师审核');await reload()}catch(e){toast(e.message);b.disabled=false}});
        document.querySelectorAll('.cy-q-manual').forEach(b=>b.onclick=async()=>{const seg=b.dataset.seg,type=document.querySelector('.cy-q-type[data-seg="'+seg+'"]')?.value||'single_choice';b.disabled=true;try{await api('/teacher/classroom-sessions/'+sid+'/segments/'+seg+'/quick-checks/draft',{method:'POST',body:JSON.stringify({question_type:type,use_ai:false})});toast('已建立手工草稿，请编辑后再开放');await reload()}catch(e){toast(e.message);b.disabled=false}});
        document.querySelectorAll('.cy-q-save').forEach(b=>b.onclick=async()=>{const id=b.dataset.check,q=(data.quickChecks||[]).find(x=>String(x.id)===String(id));const text=document.querySelector('.cy-q-text[data-check="'+id+'"]').value,opts=[...document.querySelectorAll('.cy-q-opt[data-check="'+id+'"]')].sort((a,b)=>Number(a.dataset.index)-Number(b.dataset.index)).map(x=>x.value),correct=Number(document.querySelector('.cy-q-correct[data-check="'+id+'"]').value),explain=document.querySelector('.cy-q-explain[data-check="'+id+'"]').value;try{await api('/teacher/classroom-sessions/'+sid+'/quick-checks/'+id,{method:'PUT',body:JSON.stringify({question_text:text,options:opts,correct_index:correct,explanation:explain})});toast('随堂检测草稿已保存');await reload()}catch(e){toast(e.message)}});
        document.querySelectorAll('.cy-q-open').forEach(b=>b.onclick=async()=>{if(!confirm('确认现在向本班学生开放这道随堂检测？'))return;try{await api('/teacher/classroom-sessions/'+sid+'/quick-checks/'+b.dataset.check+'/state',{method:'POST',body:JSON.stringify({status:'open'})});toast('随堂检测已开放');await reload()}catch(e){toast(e.message)}});
        document.querySelectorAll('.cy-q-close').forEach(b=>b.onclick=async()=>{try{await api('/teacher/classroom-sessions/'+sid+'/quick-checks/'+b.dataset.check+'/state',{method:'POST',body:JSON.stringify({status:'closed'})});toast('随堂检测已结束，请根据反馈决定是否继续讲解');await reload()}catch(e){toast(e.message)}});
        document.querySelectorAll('.cy-q-decision').forEach(b=>b.onclick=async()=>{try{await api('/teacher/classroom-sessions/'+sid+'/quick-checks/'+b.dataset.check+'/decision',{method:'POST',body:JSON.stringify({decision:b.dataset.decision})});toast(b.dataset.decision==='reteach'?'已返回讲解流程':'该知识点已确认完成');await reload()}catch(e){toast(e.message)}});
'''
    html = html.replace(
        bind_anchor,
        bindings + "\n      };\n      await reload();\n    }\n\n    async function classroomInvitationsPage(){",
        1,
    )

    student_anchor = "    function v1QuestionTypeLabel(q){"
    if student_anchor not in html:
        raise RuntimeError("quick-check student page anchor not found")
    student_page = r'''
    async function classroomQuickChecksPage(){
      if(session.role!=='student'){toast('随堂检测仅学生可见');navigate('/v1/workspace');return}
      let rows=[];
      try{rows=await api('/student/classroom-quick-checks')}catch(err){screen.innerHTML=shell(heading('随堂检测','读取失败')+'<div class="notice error">'+esc(err.message)+'</div>','workspace');bindNav();return}
      const letters=['A','B','C','D'];
      const cards=rows.map(q=>{
        const opts=q.options||[],answer=q.correctIndex===null?null:(opts[q.correctIndex]||'');
        const open=q.status==='open';
        const choice=open?'<div class="list">'+opts.map((x,i)=>'<label class="row" style="cursor:pointer"><input type="radio" name="cy-q-'+q.id+'" value="'+i+'" '+(q.myResponse&&q.myResponse.selectedIndex===i?'checked':'')+'><span class="row-main"><b>'+esc((letters[i]||String(i+1))+'. '+x)+'</b></span></label>').join('')+'</div><button class="btn primary cy-q-submit" data-id="'+q.id+'">'+(q.myResponse?'修改答案':'提交答案')+'</button>':'';
        let reveal='';
        if(!open){
          if(q.revealDistribution&&q.stats)reveal+='<div class="notice">本班提交 '+q.stats.responseCount+' 人 · 正确率 '+(q.stats.accuracy===null?'—':q.stats.accuracy+'%')+'<br>'+((q.stats.distribution||[]).map((x,i)=>(letters[i]||String(i+1))+': '+x.count+'人').join('；'))+'</div>';
          if(q.revealCorrectAnswer&&answer!==null)reveal+='<p><b>正确答案：</b>'+esc(answer)+'</p>';
          if(q.revealExplanation&&q.explanation)reveal+='<p class="muted"><b>解析：</b>'+esc(q.explanation)+'</p>';
        }
        const mine=q.myResponse?'<p class="muted">你已提交：'+esc(opts[q.myResponse.selectedIndex]||'')+(q.myResponse.isCorrect===null?'':(' · '+(q.myResponse.isCorrect?'正确':'需要再想一想')))+'</p>':'<p class="muted">尚未提交</p>';
        return '<section class="card"><div class="section-head"><div><h3>'+esc(q.knowledgeKey)+'</h3><p>'+esc(q.className+' · '+q.sessionTitle)+'</p></div><span class="tag">'+(open?'作答中':'已结束')+'</span></div><p><b>'+esc(q.questionText)+'</b></p>'+choice+mine+reveal+'<div class="notice">本次答案只用于当前课堂反馈，不会自动加分，也不会自动改写你的长期知识掌握记录。</div></section>';
      }).join('')||'<div class="empty">当前没有进行中的随堂检测。</div>';
      screen.innerHTML=shell(heading('随堂检测','教师发起后在这里即时作答；检测结束前可以修改答案。')+'<section class="section">'+cards+'</section>','workspace');bindNav();
      document.querySelectorAll('.cy-q-submit').forEach(b=>b.onclick=async()=>{const picked=document.querySelector('input[name="cy-q-'+b.dataset.id+'"]:checked');if(!picked){toast('请先选择答案');return}try{await api('/student/classroom-quick-checks/'+b.dataset.id+'/respond',{method:'POST',body:JSON.stringify({selected_index:Number(picked.value)})});toast('答案已提交');await classroomQuickChecksPage()}catch(e){toast(e.message)}});
    }

'''
    html = html.replace(student_anchor, student_page + student_anchor, 1)

    dispatch = "if(path.includes('/classroom-execution'))await classroomExecutionPage();else if(path.includes('/classroom-invitations'))await classroomInvitationsPage();else if(path.includes('/classroom-review'))await classroomReviewPage();else if(path.includes('/student'))await studentPage();"
    if dispatch not in html:
        raise RuntimeError("quick-check route dispatch anchor not found")
    html = html.replace(
        dispatch,
        "if(path.includes('/classroom-execution'))await classroomExecutionPage();else if(path.includes('/classroom-quick-checks'))await classroomQuickChecksPage();else if(path.includes('/classroom-invitations'))await classroomInvitationsPage();else if(path.includes('/classroom-review'))await classroomReviewPage();else if(path.includes('/student'))await studentPage();",
        1,
    )

    return html.replace(
        "</head>",
        '<meta name="' + V1_CLASSROOM_QUICK_CHECK_MARKER + '" content="1"></head>',
        1,
    )


def install_v1_classroom_quick_check_patch() -> None:
    if getattr(v1_module, "_classroom_quick_check_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_classroom_quick_check_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._classroom_quick_check_patch_installed = True


def install_v1_classroom_quick_check_routes(implementation: Any) -> None:
    app = implementation.app
    if getattr(app.state, "v1_classroom_quick_check_routes_installed", False):
        return

    tables = register_classroom_quick_check_tables(implementation)
    checks = tables["checks"]
    responses = tables["responses"]
    metadata = implementation.Base.metadata
    sessions = metadata.tables.get("classroom_sessions")
    segments = metadata.tables.get("classroom_segments")
    events = metadata.tables.get("classroom_events")
    if sessions is None or segments is None or events is None:
        raise RuntimeError("classroom execution tables must be registered before quick checks")

    SchoolClass = implementation.SchoolClass
    ClassStudent = implementation.ClassStudent
    User = implementation.User
    current_user = implementation.current_user
    get_db = implementation.get_db

    def append_event(
        db: Any,
        user: Any,
        session_id: int,
        event_type: str,
        *,
        segment_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
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

    def teacher_session(db: Any, user: Any, sid: int) -> dict[str, Any]:
        implementation.need(user, "teacher")
        raw = db.execute(
            select(sessions).where(
                sessions.c.id == sid,
                sessions.c.school_id == user.school_id,
                sessions.c.teacher_id == user.id,
            )
        ).first()
        if not raw:
            raise HTTPException(404, "课堂执行记录不存在或无权限")
        return _mapping(raw)

    def segment_row(db: Any, user: Any, sid: int, segid: int) -> dict[str, Any]:
        teacher_session(db, user, sid)
        raw = db.execute(
            select(segments).where(
                segments.c.id == segid,
                segments.c.session_id == sid,
                segments.c.school_id == user.school_id,
            )
        ).first()
        if not raw:
            raise HTTPException(404, "课堂知识点不存在")
        return _mapping(raw)

    def check_row(db: Any, user: Any, sid: int, qid: int) -> dict[str, Any]:
        teacher_session(db, user, sid)
        raw = db.execute(
            select(checks).where(
                checks.c.id == qid,
                checks.c.session_id == sid,
                checks.c.school_id == user.school_id,
            )
        ).first()
        if not raw:
            raise HTTPException(404, "随堂检测不存在")
        return _mapping(raw)

    def class_name(db: Any, school_id: int, class_id: int) -> str:
        row = db.scalar(
            select(SchoolClass).where(
                SchoolClass.id == class_id,
                SchoolClass.school_id == school_id,
            )
        )
        return str(getattr(row, "name", "") or "") if row else ""

    def response_rows(db: Any, qid: int) -> list[dict[str, Any]]:
        rows = db.execute(
            select(responses)
            .where(responses.c.check_id == qid)
            .order_by(responses.c.id)
        ).all()
        return [_mapping(row) for row in rows]

    def stats_for(db: Any, row: dict[str, Any]) -> dict[str, Any]:
        options = _json_list(row.get("options_json"))
        base = quick_check_summary(response_rows(db, int(row["id"])), option_count=len(options))
        return base

    def teacher_payload(db: Any, row: dict[str, Any]) -> dict[str, Any]:
        options = [str(x) for x in _json_list(row.get("options_json"))]
        raw_responses = response_rows(db, int(row["id"]))
        students = {}
        ids = [int(x["student_id"]) for x in raw_responses]
        if ids:
            for student in db.scalars(
                select(User).where(
                    User.school_id == row["school_id"],
                    User.id.in_(ids),
                    User.role == "student",
                )
            ).all():
                students[int(student.id)] = str(student.name or "")
        details = [
            {
                "studentID": int(item["student_id"]),
                "studentName": students.get(int(item["student_id"]), ""),
                "selectedIndex": int(item["selected_index"]),
                "isCorrect": bool(item["is_correct"]),
                "submittedAt": _iso(item["submitted_at"]),
            }
            for item in raw_responses
        ]
        return {
            "id": int(row["id"]),
            "sessionID": int(row["session_id"]),
            "segmentID": int(row["segment_id"]),
            "questionType": str(row["question_type"]),
            "questionText": str(row["question_text"] or ""),
            "options": options,
            "correctIndex": int(row["correct_index"]),
            "explanation": str(row["explanation"] or ""),
            "status": str(row["status"]),
            "decision": str(row["decision"] or ""),
            "openedAt": _iso(row["opened_at"]),
            "closedAt": _iso(row["closed_at"]),
            "stats": quick_check_summary(raw_responses, option_count=len(options)),
            "responses": details,
        }

    def validate_draft(row: dict[str, Any], *, text: str, options: list[str], correct_index: int) -> tuple[str, list[str], int]:
        qtype = normalize_quick_check_type(row["question_type"])
        question_text = str(text or "").strip()
        if not question_text:
            raise HTTPException(400, "请先填写随堂检测题干")
        cleaned = [str(x or "").strip()[:1000] for x in options]
        if qtype == "true_false":
            cleaned = ["正确", "错误"]
        if qtype == "single_choice" and (len(cleaned) != 4 or any(not x for x in cleaned)):
            raise HTTPException(400, "单选题必须填写4个完整选项")
        if qtype == "true_false" and len(cleaned) != 2:
            raise HTTPException(400, "判断题选项必须为正确/错误")
        if int(correct_index) not in range(len(cleaned)):
            raise HTTPException(400, "正确答案索引无效")
        return question_text[:5000], cleaned, int(correct_index)

    @app.get("/teacher/classroom-sessions/{sid}/quick-checks")
    def list_teacher_quick_checks(
        sid: int,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        teacher_session(db, u, sid)
        rows = db.execute(
            select(checks)
            .where(
                checks.c.session_id == sid,
                checks.c.school_id == u.school_id,
            )
            .order_by(checks.c.id.desc())
        ).all()
        return [teacher_payload(db, _mapping(row)) for row in rows]

    @app.post("/teacher/classroom-sessions/{sid}/segments/{segid}/quick-checks/draft")
    def create_quick_check_draft(
        sid: int,
        segid: int,
        body: QuickCheckDraftBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        s = teacher_session(db, u, sid)
        seg = segment_row(db, u, sid, segid)
        if str(s["status"]) not in {"active", "paused"}:
            raise HTTPException(400, "课堂未开始或已经结束，不能建立随堂检测")
        if str(seg["status"]) not in {"completed", "reviewed"}:
            raise HTTPException(400, "请先完成本知识点讲解，再建立随堂检测")
        qtype = normalize_quick_check_type(body.question_type)

        active = db.execute(
            select(checks).where(
                checks.c.school_id == u.school_id,
                checks.c.session_id == sid,
                checks.c.segment_id == segid,
                checks.c.status.in_(["draft", "open"]),
            )
        ).first()
        if active:
            existing = _mapping(active)
            if str(existing["status"]) == "open":
                raise HTTPException(400, "当前知识点已有进行中的随堂检测")
            target_id = int(existing["id"])
        else:
            target_id = 0

        question_text = ""
        options = ["", "", "", ""] if qtype == "single_choice" else ["正确", "错误"]
        correct_index = 0
        explanation = ""

        if body.use_ai:
            class_row = db.scalar(
                select(SchoolClass).where(
                    SchoolClass.id == s["class_id"],
                    SchoolClass.school_id == u.school_id,
                )
            )
            sibling_knowledge = [
                str(value or "").strip()
                for value in db.scalars(
                    select(segments.c.knowledge_key)
                    .where(
                        segments.c.session_id == sid,
                        segments.c.school_id == u.school_id,
                        segments.c.id != segid,
                    )
                    .order_by(segments.c.order_no)
                ).all()
                if str(value or "").strip()
            ]
            prompt = quick_check_prompt(
                grade=int(getattr(class_row, "grade", 5) or 5),
                subject=str(s.get("subject") or ""),
                textbook=str(s.get("textbook") or ""),
                knowledge=str(seg.get("knowledge_key") or ""),
                qtype=qtype,
                notes=body.notes[:1000],
                excluded_knowledge=sibling_knowledge,
            )
            raw = implementation._ai_json(
                implementation._ai_call(
                    db,
                    u,
                    "classroom_quick_check_draft",
                    prompt,
                    timeout=90,
                )
            )
            cleaned = clean_ai_quick_check(
                raw,
                requested_type=qtype,
                knowledge=str(seg.get("knowledge_key") or ""),
            )
            if not cleaned:
                raise HTTPException(502, "AI 未生成符合随堂检测要求的有效题目，请重试或使用手工草稿")
            question_text = cleaned["question_text"]
            options = cleaned["options"]
            correct_index = cleaned["correct_index"]
            explanation = cleaned["explanation"]

        now = datetime.utcnow()
        values = {
            "school_id": u.school_id,
            "session_id": sid,
            "segment_id": segid,
            "created_by": u.id,
            "question_type": qtype,
            "question_text": question_text,
            "options_json": json.dumps(options, ensure_ascii=False),
            "correct_index": correct_index,
            "explanation": explanation,
            "status": "draft",
            "decision": "",
            "opened_at": None,
            "closed_at": None,
            "decided_at": None,
            "updated_at": now,
        }
        if target_id:
            db.execute(checks.update().where(checks.c.id == target_id).values(**values))
            qid = target_id
        else:
            qid = db.execute(
                checks.insert().values(**values, created_at=now).returning(checks.c.id)
            ).scalar_one()
        append_event(
            db,
            u,
            sid,
            "quick_check.draft_created",
            segment_id=segid,
            payload={"checkID": int(qid), "questionType": qtype, "source": "ai" if body.use_ai else "manual"},
        )
        implementation.audit(
            db,
            u,
            "classroom.quick_check.draft",
            f"session={sid};segment={segid};check={qid};source={'ai' if body.use_ai else 'manual'}",
        )
        db.commit()
        row = check_row(db, u, sid, int(qid))
        return teacher_payload(db, row)

    @app.put("/teacher/classroom-sessions/{sid}/quick-checks/{qid}")
    def edit_quick_check(
        sid: int,
        qid: int,
        body: QuickCheckEditBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        row = check_row(db, u, sid, qid)
        if str(row["status"]) != "draft":
            raise HTTPException(400, "只有草稿状态的随堂检测可以编辑")
        text, options, correct_index = validate_draft(
            row,
            text=body.question_text,
            options=body.options,
            correct_index=body.correct_index,
        )
        db.execute(
            checks.update()
            .where(checks.c.id == qid)
            .values(
                question_text=text,
                options_json=json.dumps(options, ensure_ascii=False),
                correct_index=correct_index,
                explanation=body.explanation.strip()[:5000],
                updated_at=datetime.utcnow(),
            )
        )
        implementation.audit(db, u, "classroom.quick_check.edit", f"session={sid};check={qid}")
        db.commit()
        return teacher_payload(db, check_row(db, u, sid, qid))

    @app.post("/teacher/classroom-sessions/{sid}/quick-checks/{qid}/state")
    def set_quick_check_state(
        sid: int,
        qid: int,
        body: QuickCheckStateBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        s = teacher_session(db, u, sid)
        row = check_row(db, u, sid, qid)
        seg = segment_row(db, u, sid, int(row["segment_id"]))
        target = body.status.strip()
        if target == "open":
            if str(s["status"]) != "active":
                raise HTTPException(400, "只有课堂进行中才能开放随堂检测")
            if str(row["status"]) != "draft":
                raise HTTPException(400, "只有草稿可以开始检测")
            if str(seg["status"]) not in {"completed", "reviewed"}:
                raise HTTPException(400, "请先结束知识点讲解")
            text, options, correct_index = validate_draft(
                row,
                text=str(row["question_text"] or ""),
                options=[str(x) for x in _json_list(row["options_json"])],
                correct_index=int(row["correct_index"]),
            )
            db.execute(
                checks.update()
                .where(checks.c.id == qid)
                .values(
                    question_text=text,
                    options_json=json.dumps(options, ensure_ascii=False),
                    correct_index=correct_index,
                    status="open",
                    opened_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            db.execute(
                segments.update()
                .where(segments.c.id == int(row["segment_id"]))
                .values(status="checking", updated_at=datetime.utcnow())
            )
            append_event(
                db,
                u,
                sid,
                "quick_check.opened",
                segment_id=int(row["segment_id"]),
                payload={"checkID": qid},
            )
        elif target == "closed":
            if str(row["status"]) != "open":
                raise HTTPException(400, "只有进行中的随堂检测可以结束")
            summary = stats_for(db, row)
            db.execute(
                checks.update()
                .where(checks.c.id == qid)
                .values(status="closed", closed_at=datetime.utcnow(), updated_at=datetime.utcnow())
            )
            db.execute(
                segments.update()
                .where(segments.c.id == int(row["segment_id"]))
                .values(status="reviewed", updated_at=datetime.utcnow())
            )
            append_event(
                db,
                u,
                sid,
                "quick_check.closed",
                segment_id=int(row["segment_id"]),
                payload={
                    "checkID": qid,
                    "responseCount": summary["responseCount"],
                    "accuracy": summary["accuracy"],
                },
            )
        else:
            raise HTTPException(400, "随堂检测状态只支持 open 或 closed")
        implementation.audit(db, u, "classroom.quick_check.state", f"session={sid};check={qid};status={target}")
        db.commit()
        return teacher_payload(db, check_row(db, u, sid, qid))

    @app.post("/teacher/classroom-sessions/{sid}/quick-checks/{qid}/decision")
    def decide_after_quick_check(
        sid: int,
        qid: int,
        body: QuickCheckDecisionBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        s = teacher_session(db, u, sid)
        row = check_row(db, u, sid, qid)
        seg = segment_row(db, u, sid, int(row["segment_id"]))
        if str(s["status"]) != "active":
            raise HTTPException(400, "课堂未处于进行中，不能做随堂检测后的课堂决策")
        if str(row["status"]) != "closed" or str(seg["status"]) != "reviewed":
            raise HTTPException(400, "请先结束随堂检测，再由教师做课堂决策")
        if str(row.get("decision") or ""):
            raise HTTPException(400, "本轮随堂检测已经完成教师决策")
        decision = body.decision.strip()
        if decision not in {"complete", "reteach"}:
            raise HTTPException(400, "教师决策只能是确认完成或继续讲解")
        if decision == "complete":
            next_status = "completed"
        else:
            try:
                next_status = segment_status_for_mode(str(seg["mode"]))
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            if next_status == "completed":
                raise HTTPException(400, "暂不讲解模式不能进入继续讲解")
        db.execute(
            checks.update()
            .where(checks.c.id == qid)
            .values(decision=decision, decided_at=datetime.utcnow(), updated_at=datetime.utcnow())
        )
        db.execute(
            segments.update()
            .where(segments.c.id == int(row["segment_id"]))
            .values(status=next_status, updated_at=datetime.utcnow())
        )
        append_event(
            db,
            u,
            sid,
            "quick_check.decision",
            segment_id=int(row["segment_id"]),
            payload={"checkID": qid, "decision": decision, "nextStatus": next_status},
        )
        implementation.audit(
            db,
            u,
            "classroom.quick_check.decision",
            f"session={sid};check={qid};decision={decision}",
        )
        db.commit()
        return {
            "ok": True,
            "decision": decision,
            "segmentStatus": next_status,
            "quickCheck": teacher_payload(db, check_row(db, u, sid, qid)),
        }

    @app.get("/student/classroom-quick-checks")
    def student_quick_checks(
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        implementation.need(u, "student")
        memberships = list(
            db.scalars(
                select(ClassStudent).where(ClassStudent.student_id == u.id)
            ).all()
        )
        class_ids = [int(x.class_id) for x in memberships]
        if not class_ids:
            return []
        session_rows = db.execute(
            select(sessions).where(
                sessions.c.school_id == u.school_id,
                sessions.c.class_id.in_(class_ids),
                sessions.c.status.in_(["active", "paused"]),
            )
        ).all()
        session_map = {int(_mapping(x)["id"]): _mapping(x) for x in session_rows}
        if not session_map:
            return []
        check_rows = db.execute(
            select(checks)
            .where(
                checks.c.school_id == u.school_id,
                checks.c.session_id.in_(list(session_map)),
                checks.c.status.in_(["open", "closed"]),
            )
            .order_by(checks.c.id.desc())
        ).all()
        out = []
        for raw in check_rows:
            row = _mapping(raw)
            session_data = session_map.get(int(row["session_id"]))
            if not session_data:
                continue
            seg_raw = db.execute(
                select(segments).where(
                    segments.c.id == row["segment_id"],
                    segments.c.session_id == row["session_id"],
                    segments.c.school_id == u.school_id,
                )
            ).first()
            if not seg_raw:
                continue
            seg = _mapping(seg_raw)
            options = [str(x) for x in _json_list(row["options_json"])]
            my_raw = db.execute(
                select(responses).where(
                    responses.c.check_id == row["id"],
                    responses.c.student_id == u.id,
                    responses.c.school_id == u.school_id,
                )
            ).first()
            mine = _mapping(my_raw) if my_raw else {}
            closed = str(row["status"]) == "closed"
            reveal_correct = bool(seg.get("reveal_correct_answer")) and closed
            reveal_distribution = bool(seg.get("reveal_distribution")) and closed
            reveal_explanation = bool(seg.get("reveal_explanation")) and closed
            my_response = None
            if mine:
                my_response = {
                    "selectedIndex": int(mine["selected_index"]),
                    "isCorrect": bool(mine["is_correct"]) if reveal_correct else None,
                    "submittedAt": _iso(mine["submitted_at"]),
                }
            out.append(
                {
                    "id": int(row["id"]),
                    "sessionID": int(row["session_id"]),
                    "segmentID": int(row["segment_id"]),
                    "sessionTitle": str(session_data.get("title") or ""),
                    "className": class_name(db, u.school_id, int(session_data["class_id"])),
                    "knowledgeKey": str(seg.get("knowledge_key") or ""),
                    "questionType": str(row["question_type"]),
                    "questionText": str(row["question_text"] or ""),
                    "options": options,
                    "status": str(row["status"]),
                    "myResponse": my_response,
                    "revealDistribution": reveal_distribution,
                    "revealCorrectAnswer": reveal_correct,
                    "revealExplanation": reveal_explanation,
                    "correctIndex": int(row["correct_index"]) if reveal_correct else None,
                    "explanation": str(row["explanation"] or "") if reveal_explanation else "",
                    "stats": stats_for(db, row) if reveal_distribution else None,
                }
            )
        return out

    @app.post("/student/classroom-quick-checks/{qid}/respond")
    def respond_quick_check(
        qid: int,
        body: QuickCheckResponseBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        implementation.need(u, "student")
        raw = db.execute(
            select(checks).where(
                checks.c.id == qid,
                checks.c.school_id == u.school_id,
                checks.c.status == "open",
            )
        ).first()
        if not raw:
            raise HTTPException(404, "随堂检测不存在、尚未开放或已经结束")
        row = _mapping(raw)
        session_raw = db.execute(
            select(sessions).where(
                sessions.c.id == row["session_id"],
                sessions.c.school_id == u.school_id,
                sessions.c.status == "active",
            )
        ).first()
        if not session_raw:
            raise HTTPException(400, "课堂当前未处于可作答状态")
        session_data = _mapping(session_raw)
        membership = db.scalar(
            select(ClassStudent).where(
                ClassStudent.class_id == session_data["class_id"],
                ClassStudent.student_id == u.id,
            )
        )
        if not membership:
            raise HTTPException(403, "你不在本次课堂班级中")
        options = _json_list(row["options_json"])
        selected_index = int(body.selected_index)
        if selected_index not in range(len(options)):
            raise HTTPException(400, "答案选项无效")
        is_correct = selected_index == int(row["correct_index"])
        existing = db.execute(
            select(responses).where(
                responses.c.check_id == qid,
                responses.c.student_id == u.id,
                responses.c.school_id == u.school_id,
            )
        ).first()
        now = datetime.utcnow()
        if existing:
            db.execute(
                responses.update()
                .where(responses.c.id == _mapping(existing)["id"])
                .values(
                    selected_index=selected_index,
                    is_correct=is_correct,
                    updated_at=now,
                )
            )
        else:
            db.execute(
                responses.insert().values(
                    school_id=u.school_id,
                    check_id=qid,
                    session_id=row["session_id"],
                    segment_id=row["segment_id"],
                    student_id=u.id,
                    selected_index=selected_index,
                    is_correct=is_correct,
                    submitted_at=now,
                    updated_at=now,
                )
            )
        append_event(
            db,
            u,
            int(row["session_id"]),
            "quick_check.response_submitted",
            segment_id=int(row["segment_id"]),
            payload={"checkID": qid},
        )
        implementation.audit(
            db,
            u,
            "classroom.quick_check.respond",
            f"check={qid};student={u.id}",
        )
        db.commit()
        return {"ok": True, "submitted": True}

    def v1_response() -> HTMLResponse:
        return HTMLResponse(
            v1_module.v1_html(),
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "X-Changying-V1": V1_CLASSROOM_QUICK_CHECK_MARKER,
            },
        )

    app.add_api_route(
        "/v1/classroom-quick-checks",
        v1_response,
        methods=["GET"],
        include_in_schema=False,
    )
    app.state.v1_classroom_quick_check_routes_installed = True


__all__ = [
    "QuickCheckDecisionBody",
    "QuickCheckDraftBody",
    "QuickCheckEditBody",
    "QuickCheckResponseBody",
    "QuickCheckStateBody",
    "V1_CLASSROOM_QUICK_CHECK_MARKER",
    "install_v1_classroom_quick_check_patch",
    "install_v1_classroom_quick_check_routes",
    "patch_v1_classroom_quick_check_html",
    "register_classroom_quick_check_tables",
]
