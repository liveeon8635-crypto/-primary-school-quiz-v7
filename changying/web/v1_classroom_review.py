"""Teacher classroom-practice review and handout workflow for V1."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, select

from changying.services.assignments import teacher_assignment_rows
from changying.services.classroom_review import (
    build_anonymized_handout_prompt,
    build_deterministic_interaction_handout_summary,
    classroom_interaction_summary,
    classroom_review_summary,
)
from changying.web import v1 as v1_module


V1_CLASSROOM_REVIEW_MARKER = "changying_v1_classroom_review_v1"


class HandoutGenerateBody(BaseModel):
    selected_knowledge: list[str] = []
    selected_question_ids: list[int] = []
    teacher_notes: str = ""


class HandoutSaveBody(BaseModel):
    title: str = ""
    content: str
    selected_knowledge: list[str] = []
    selected_question_ids: list[int] = []
    teacher_notes: str = ""


def register_classroom_review_table(implementation: Any) -> Table:
    metadata = implementation.Base.metadata
    if "classroom_review_handouts" in metadata.tables:
        return metadata.tables["classroom_review_handouts"]
    return Table(
        "classroom_review_handouts",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("school_id", Integer, nullable=False, index=True),
        Column("assignment_id", Integer, nullable=False, index=True),
        Column("class_id", Integer, nullable=False, index=True),
        Column("teacher_id", Integer, nullable=False, index=True),
        Column("title", String(220), nullable=False, default=""),
        Column("selected_knowledge_json", Text, nullable=False, default="[]"),
        Column("selected_question_ids_json", Text, nullable=False, default="[]"),
        Column("teacher_notes", Text, nullable=False, default=""),
        Column("content_text", Text, nullable=False, default=""),
        Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
        Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
        UniqueConstraint(
            "school_id",
            "assignment_id",
            name="uq_classroom_review_handout_assignment",
        ),
    )


def _json_list(raw: Any) -> list[Any]:
    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _draft_payload(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    data = row._mapping if hasattr(row, "_mapping") else row
    return {
        "id": int(data["id"]),
        "assignmentID": int(data["assignment_id"]),
        "title": str(data["title"] or ""),
        "selectedKnowledge": [
            str(x) for x in _json_list(data["selected_knowledge_json"])
        ],
        "selectedQuestionIDs": [
            int(x) for x in _json_list(data["selected_question_ids_json"])
        ],
        "teacherNotes": str(data["teacher_notes"] or ""),
        "content": str(data["content_text"] or ""),
        "createdAt": data["created_at"].isoformat(timespec="minutes") if data["created_at"] else "",
        "updatedAt": data["updated_at"].isoformat(timespec="minutes") if data["updated_at"] else "",
    }


def patch_v1_classroom_review_html(html: str) -> str:
    if V1_CLASSROOM_REVIEW_MARKER in html:
        return html

    html = html.replace(
        "['晚托','周末课','当前学生','今日/本周教学','作业与错题','学习进度','待办事项']",
        "['晚托','周末课','当前学生','今日/本周教学','课堂复盘','作业与错题','学习进度','待办事项']",
    ).replace(
        "['今日课表','我的班级','教学进度','学生','备课','作业','批改/订正','测验','教学评价','待办']",
        "['今日课表','我的班级','教学进度','学生','备课','作业','批改/订正','测验','课堂复盘','教学评价','待办']",
    )
    old_handler = "document.querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>toast(b.dataset.feature+'：V1 入口已预留'));"
    new_handler = "document.querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>{if(b.dataset.feature==='课堂复盘')navigate('/v1/classroom-review');else toast(b.dataset.feature+'：V1 入口已预留')});"
    if old_handler not in html:
        raise RuntimeError("V1 workspace feature handler not found")
    html = html.replace(old_handler, new_handler, 1)

    anchor = "    function v1QuestionTypeLabel(q){"
    if anchor not in html:
        raise RuntimeError("V1 question label anchor not found")

    page = r'''
    async function classroomReviewPage(){
      if(session.role!=='teacher'){toast('课堂复盘仅教师可用');navigate('/v1/workspace');return}
      let assignments=[];
      try{assignments=await api('/teacher/classroom-reviews/assignments')}catch(err){screen.innerHTML=shell(heading('课堂练习复盘','读取失败')+'<div class="notice error">'+esc(err.message)+'</div>','workspace');bindNav();return}
      const query=new URLSearchParams(location.search),requested=Number(query.get('assignment')||0);
      let current=requested||Number(assignments[0]?.id||0),summary=null;
      const load=async(aid)=>{current=Number(aid);summary=await api('/teacher/assignments/'+current+'/class-review');renderReview()};
      const selector=()=>'<select id="cy-review-assignment" style="min-width:min(100%,420px)">'+assignments.map(a=>'<option value="'+a.id+'" '+(Number(a.id)===current?'selected':'')+'>'+esc(a.className+' · '+a.title+' · '+a.completedCount+'/'+a.recipientCount)+'</option>').join('')+'</select>';
      const draftEditor=(draft)=>{
        if(!draft)return '<div class="notice">尚未生成讲义。请先选择需要讲解的知识点或典型错题，再由教师决定是否生成。</div>';
        return '<div class="field"><label>讲义标题</label><input id="cy-handout-title" value="'+esc(draft.title||'')+'"></div><div class="field"><label>讲义正文（教师可直接修改）</label><textarea id="cy-handout-content" rows="18">'+esc(draft.content||'')+'</textarea></div><button class="btn primary" id="cy-handout-save">保存教师修改</button><span class="muted" style="margin-left:10px">最近保存：'+esc(draft.updatedAt||'')+'</span>';
      };
      const renderReview=()=>{
        if(!summary){screen.innerHTML=shell(heading('课堂练习复盘','把同一堂课的练习结果汇总成教师可判断的数据。')+'<section class="card">'+selector()+'</section>','workspace');bindNav();document.getElementById('cy-review-assignment').onchange=e=>load(e.target.value);return}
        const k=summary.knowledgeStats||[],errors=summary.commonErrors||[],students=summary.students||[],draft=summary.handoutDraft,interaction=summary.classroomInteraction||null,openSession=summary.openClassroomSession||null;
        const completedAt=interaction?.session?.completedAt||'',draftUpdatedAt=draft?.updatedAt||'',draftStale=!!(draft&&completedAt&&draftUpdatedAt&&draftUpdatedAt<completedAt);
        const summaryMissing=!!(draft&&interaction?.session?.status==='completed'&&(interaction.quickCheckRoundCount||0)>0&&!String(draft.content||'').includes('互动课堂过程摘要（系统记录）'));
        const generateLabel=draftStale?'重新生成本堂课讲义草稿':(summaryMissing?'重新生成并补全互动摘要':'由教师确认并生成讲义草稿');
        const staleNotice=draftStale?'<div class="notice error"><b>旧草稿 · 建议重新生成</b><br>现有草稿保存于 '+esc(draftUpdatedAt)+'，早于本堂互动课堂完成时间 '+esc(completedAt)+'；重新生成后才会纳入本堂随堂检测、补讲轨迹与学生讲解评价。</div>':(summaryMissing?'<div class="notice error"><b>讲义需补全互动摘要</b><br>当前讲义已经晚于课堂完成时间，但仍缺少系统固定的互动过程摘要；重新生成后会明确保留各轮正确率、补讲决策、学生讲解评价与教师明确加分。</div>':'');
        const kRows=k.map((x,i)=>'<label class="row" style="cursor:pointer"><input type="checkbox" class="cy-review-k" value="'+esc(x.knowledge)+'" '+(x.accuracy<80?'checked':'')+'><span class="row-main"><b>'+esc(x.knowledge)+'</b><small>答题 '+x.answered+' 次 · 涉及 '+x.studentCount+' 人</small></span><span class="tag">'+x.accuracy+'% · '+esc(x.reviewPriority)+'</span></label>').join('')||'<div class="empty">暂无已完成练习数据</div>';
        const eRows=errors.map(x=>'<label class="row" style="cursor:pointer"><input type="checkbox" class="cy-review-q" value="'+x.questionID+'" '+(x.wrongRate>=30?'checked':'')+'><span class="row-main"><b>'+esc(x.knowledge)+' · 错误率 '+x.wrongRate+'%</b><small>'+esc(x.problem)+'</small><small>常见错误：'+esc((x.wrongAnswerDistribution||[]).map(v=>v.answer+'×'+v.count).join('；')||'—')+'</small></span></label>').join('')||'<div class="empty">暂无共性错题</div>';
        const sRows=students.map(x=>'<div class="row"><span class="row-main"><b>'+esc(x.studentName)+'</b><small>'+(x.completed?'已完成 · '+esc(x.submittedAt||''):'未完成')+'</small></span><span class="tag">'+(x.score===null?'—':x.score+'分')+'</span></div>').join('');
        const modeNames={teacher:'教师讲解',student:'学生讲解',co_teach:'师生共讲',discussion:'讨论',skipped:'暂不讲解'};
        const decisionNames={reteach:'继续讲解',complete:'确认完成'};
        const interactionRows=interaction?(interaction.segments||[]).map(x=>{
          const rounds=(x.quickCheckRounds||[]).map(r=>'第'+r.round+'轮 '+r.responseCount+'人 · '+(r.accuracy===null?'—':r.accuracy+'%')+(r.decision?' · '+(decisionNames[r.decision]||r.decision):'')).join(' → ');
          const review=x.presentationReviewCount?('学生讲解 '+x.presentationCount+' 次 · 评价均值 准确 '+(x.presentationAverages?.accuracy??'—')+'/5、清晰 '+(x.presentationAverages?.clarity??'—')+'/5、互动 '+(x.presentationAverages?.interaction??'—')+'/5 · 教师明确加分 '+x.teacherGrantedPoints+' 分'):(x.presentationCount?('学生讲解 '+x.presentationCount+' 次 · 尚无教师评价'):'');
          return '<div class="row"><span class="row-main"><b>'+esc(x.knowledge||x.title||'知识点')+'</b><small>'+esc(modeNames[x.mode]||x.mode||'')+(rounds?' · '+esc(rounds):'')+'</small>'+(review?'<small>'+esc(review)+'</small>':'')+'</span><span class="tag">'+(x.reteachCount||0)+' 次补讲</span></div>';
        }).join(''):'';
        const interactionBlock=interaction?('<section class="section card"><h2>互动课堂反馈</h2><p class="muted">检测、补讲轨迹与讲解评价只用于本堂课复盘和讲义草稿，不会自动改写长期知识掌握记录。</p><div class="notice">课堂状态：'+esc(interaction.session?.status||'')+' · 随堂检测 '+(interaction.quickCheckRoundCount||0)+' 轮 · 补讲 '+(interaction.reteachCount||0)+' 次 · 学生讲解 '+(interaction.presentationCount||0)+' 次 · 教师明确加分 '+(interaction.teacherGrantedPoints||0)+' 分</div><div class="list">'+(interactionRows||'<div class="empty">暂无互动课堂数据</div>')+'</div></section>'):'';
        const content=heading('课堂练习复盘','先看班级事实，再由教师决定讲什么、是否生成讲义。','<button class="btn" id="cy-review-back">返回当前教学</button>')+
          '<section class="card"><div class="field"><label>选择本堂课练习</label>'+selector()+'</div><div class="notice">'+esc(summary.dataNotice||'')+'</div></section>'+
          '<section class="section grid cols-4"><div class="card kpi"><span>接收学生</span><strong>'+summary.recipientCount+'</strong></div><div class="card kpi"><span>已完成</span><strong>'+summary.completedCount+'</strong><small>'+summary.completionRate+'%</small></div><div class="card kpi"><span>平均分</span><strong>'+(summary.averageScore??'—')+'</strong><small>仅统计已完成</small></div><div class="card kpi"><span>题量</span><strong>'+esc(summary.paper?.questionCount??'—')+'</strong></div></section>'+
          '<section class="section grid cols-2"><div class="card"><h2>知识点掌握情况（本次练习）</h2><p class="muted">勾选需要进入讲义的知识点；系统建议仅供教师判断。</p><div class="list">'+kRows+'</div></div><div class="card"><h2>典型共性错误</h2><p class="muted">勾选值得课堂讲解的典型题；不会把学生姓名送入 AI。</p><div class="list">'+eRows+'</div></div></section>'+
          interactionBlock+
          '<section class="section card"><h2>学生完成情况</h2><p class="muted">此处仅教师可见；生成讲义时会自动匿名化，不发送姓名、账号、ID或个人排名。</p><div class="list">'+sRows+'</div></section>'+
          '<section class="section card"><h2>教师讲义决策</h2>'+staleNotice+'<div class="field"><label>教师补充（可选）</label><textarea id="cy-review-notes" rows="3" placeholder="例如：重点讲清方法，不展开排名；增加一道变式题">'+esc(draft?.teacherNotes||'')+'</textarea></div><button class="btn primary" id="cy-handout-generate" '+(summary.handoutReady?'':'disabled')+'>'+generateLabel+'</button><span class="muted" style="margin-left:10px">不会自动发布给学生</span></section>'+
          '<section class="section card"><h2>课堂练习情况讲义草稿</h2>'+staleNotice+'<div id="cy-handout-editor">'+draftEditor(draft)+'</div></section>';
        screen.innerHTML=shell(content,'workspace');bindNav();
        document.getElementById('cy-review-back').onclick=()=>navigate('/v1/workspace');
        document.getElementById('cy-review-assignment').onchange=e=>load(e.target.value);
        const bindSave=()=>{
          const save=document.getElementById('cy-handout-save');if(!save)return;
          save.onclick=async()=>{save.disabled=true;try{const payload={title:document.getElementById('cy-handout-title').value,content:document.getElementById('cy-handout-content').value,selected_knowledge:[...document.querySelectorAll('.cy-review-k:checked')].map(x=>x.value),selected_question_ids:[...document.querySelectorAll('.cy-review-q:checked')].map(x=>Number(x.value)),teacher_notes:document.getElementById('cy-review-notes').value};const r=await api('/teacher/assignments/'+current+'/class-review/handout',{method:'PUT',body:JSON.stringify(payload)});summary.handoutDraft=r.handoutDraft;toast('讲义修改已保存');renderReview()}catch(err){toast(err.message);save.disabled=false}};
        };bindSave();
        document.getElementById('cy-handout-generate').onclick=async e=>{const btn=e.currentTarget,selectedKnowledge=[...document.querySelectorAll('.cy-review-k:checked')].map(x=>x.value),selectedQuestions=[...document.querySelectorAll('.cy-review-q:checked')].map(x=>Number(x.value));if(!selectedKnowledge.length&&!selectedQuestions.length){toast('请先选择至少一个知识点或典型错题');return}btn.disabled=true;btn.textContent='正在生成讲义草稿…';try{const r=await api('/teacher/assignments/'+current+'/class-review/handout-generate',{method:'POST',timeoutMs:90000,body:JSON.stringify({selected_knowledge:selectedKnowledge,selected_question_ids:selectedQuestions,teacher_notes:document.getElementById('cy-review-notes').value})});summary.handoutDraft=r.handoutDraft;toast('讲义草稿已生成，请教师审核修改');renderReview()}catch(err){toast(err.message);btn.disabled=false;btn.textContent=generateLabel}};
      };
      if(!assignments.length){screen.innerHTML=shell(heading('课堂练习复盘','暂无可复盘的课堂练习')+'<div class="empty">先布置一份班级练习，学生提交后这里会自动汇总。</div>','workspace');bindNav();return}
      await load(current);
    }

'''
    html = html.replace(anchor, page + anchor, 1)

    old_dispatch = "if(path.includes('/student'))await studentPage();"
    new_dispatch = "if(path.includes('/classroom-review'))await classroomReviewPage();else if(path.includes('/student'))await studentPage();"
    if old_dispatch not in html:
        raise RuntimeError("V1 route dispatch anchor not found")
    html = html.replace(old_dispatch, new_dispatch, 1)

    return html.replace(
        "</head>",
        f'<meta name="{V1_CLASSROOM_REVIEW_MARKER}" content="1"></head>',
        1,
    )


def install_v1_classroom_review_patch() -> None:
    if getattr(v1_module, "_classroom_review_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_classroom_review_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._classroom_review_patch_installed = True


def install_v1_classroom_review_routes(implementation: Any) -> None:
    app = implementation.app
    if getattr(app.state, "v1_classroom_review_routes_installed", False):
        return

    table = register_classroom_review_table(implementation)
    Assignment = implementation.Assignment
    AssignmentRecipient = implementation.AssignmentRecipient
    Submission = implementation.Submission
    Question = implementation.Question
    Paper = implementation.Paper
    SchoolClass = implementation.SchoolClass
    current_user = implementation.current_user
    get_db = implementation.get_db

    def teacher_assignment_context(db: Any, user: Any, aid: int):
        implementation.need(user, "teacher")
        assignment = implementation.teacher_assignment_for(
            db, user.school_id, user.id, aid
        )
        if not assignment:
            raise HTTPException(404, "课堂练习不存在或无权限")
        class_row = db.scalar(
            select(SchoolClass).where(
                SchoolClass.id == assignment.class_id,
                SchoolClass.school_id == user.school_id,
                SchoolClass.teacher_id == user.id,
            )
        )
        paper = db.scalar(
            select(Paper).where(
                Paper.id == assignment.paper_id,
                Paper.school_id == user.school_id,
            )
        )
        if not class_row or not paper:
            raise HTTPException(400, "课堂练习缺少班级或试卷数据")
        return assignment, class_row, paper

    def review_summary(db: Any, user: Any, aid: int) -> dict[str, Any]:
        assignment, class_row, paper = teacher_assignment_context(db, user, aid)
        recipients = implementation.recipient_students(db, assignment)
        recipient_ids = [int(x.id) for x in recipients]
        submissions = (
            list(
                db.scalars(
                    select(Submission).where(
                        Submission.school_id == user.school_id,
                        Submission.assignment_id == aid,
                        Submission.student_id.in_(recipient_ids),
                    )
                ).all()
            )
            if recipient_ids
            else []
        )
        try:
            qids = [int(x) for x in json.loads(paper.question_ids_json or "[]")]
        except Exception:
            qids = []
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
        result = classroom_review_summary(
            assignment=assignment,
            class_row=class_row,
            paper=paper,
            recipients=recipients,
            submissions=submissions,
            questions=questions,
        )

        metadata = implementation.Base.metadata
        session_table = metadata.tables.get("classroom_sessions")
        segment_table = metadata.tables.get("classroom_segments")
        check_table = metadata.tables.get("classroom_quick_checks")
        response_table = metadata.tables.get("classroom_quick_check_responses")
        turn_table = metadata.tables.get("classroom_presenter_turns")
        presentation_review_table = metadata.tables.get("classroom_presentation_reviews")
        result["classroomInteraction"] = None
        result["openClassroomSession"] = None
        if all(
            table is not None
            for table in (
                session_table,
                segment_table,
                check_table,
                response_table,
                turn_table,
                presentation_review_table,
            )
        ):
            open_session_row = db.execute(
                select(session_table)
                .where(
                    session_table.c.school_id == user.school_id,
                    session_table.c.teacher_id == user.id,
                    session_table.c.source_assignment_id == aid,
                    session_table.c.status.in_(["planned", "active", "paused"]),
                )
                .order_by(session_table.c.id.desc())
            ).first()
            if open_session_row is not None:
                open_map = open_session_row._mapping
                result["openClassroomSession"] = {
                    "id": int(open_map["id"]),
                    "status": str(open_map["status"] or ""),
                    "title": str(open_map["title"] or ""),
                    "startedAt": (
                        open_map["started_at"].isoformat(timespec="minutes")
                        if open_map["started_at"]
                        else ""
                    ),
                }

            session_row = db.execute(
                select(session_table)
                .where(
                    session_table.c.school_id == user.school_id,
                    session_table.c.teacher_id == user.id,
                    session_table.c.source_assignment_id == aid,
                    session_table.c.status == "completed",
                )
                .order_by(session_table.c.completed_at.desc(), session_table.c.id.desc())
            ).first()
            if session_row is None:
                session_row = db.execute(
                    select(session_table)
                    .where(
                        session_table.c.school_id == user.school_id,
                        session_table.c.teacher_id == user.id,
                        session_table.c.source_assignment_id == aid,
                        session_table.c.status != "cancelled",
                    )
                    .order_by(session_table.c.id.desc())
                ).first()
            if session_row is not None:
                session_id = int(session_row._mapping["id"])
                segment_rows = list(
                    db.execute(
                        select(segment_table)
                        .where(
                            segment_table.c.school_id == user.school_id,
                            segment_table.c.session_id == session_id,
                        )
                        .order_by(segment_table.c.order_no, segment_table.c.id)
                    ).all()
                )
                check_rows = list(
                    db.execute(
                        select(check_table).where(
                            check_table.c.school_id == user.school_id,
                            check_table.c.session_id == session_id,
                        )
                    ).all()
                )
                response_rows = list(
                    db.execute(
                        select(response_table).where(
                            response_table.c.school_id == user.school_id,
                            response_table.c.session_id == session_id,
                        )
                    ).all()
                )
                turn_rows = list(
                    db.execute(
                        select(turn_table).where(
                            turn_table.c.school_id == user.school_id,
                            turn_table.c.session_id == session_id,
                        )
                    ).all()
                )
                presentation_review_rows = list(
                    db.execute(
                        select(presentation_review_table).where(
                            presentation_review_table.c.school_id == user.school_id,
                            presentation_review_table.c.session_id == session_id,
                        )
                    ).all()
                )
                result["classroomInteraction"] = classroom_interaction_summary(
                    session=session_row,
                    segments=segment_rows,
                    quick_checks=check_rows,
                    responses=response_rows,
                    presenter_turns=turn_rows,
                    presentation_reviews=presentation_review_rows,
                )
        draft = db.execute(
            select(table).where(
                table.c.school_id == user.school_id,
                table.c.assignment_id == aid,
            )
        ).first()
        result["handoutDraft"] = _draft_payload(draft)
        return result

    def save_draft(
        db: Any,
        user: Any,
        summary: dict[str, Any],
        *,
        title: str,
        content: str,
        selected_knowledge: list[str],
        selected_question_ids: list[int],
        teacher_notes: str,
    ) -> dict[str, Any]:
        assignment_id = int(summary["assignment"]["id"])
        now = datetime.utcnow()
        values = {
            "school_id": user.school_id,
            "assignment_id": assignment_id,
            "class_id": int(summary["class"]["id"]),
            "teacher_id": user.id,
            "title": title[:220],
            "selected_knowledge_json": json.dumps(
                list(dict.fromkeys(selected_knowledge))[:20],
                ensure_ascii=False,
            ),
            "selected_question_ids_json": json.dumps(
                list(dict.fromkeys(int(x) for x in selected_question_ids if int(x) > 0))[:30]
            ),
            "teacher_notes": teacher_notes[:3000],
            "content_text": content[:50000],
            "updated_at": now,
        }
        current = db.execute(
            select(table.c.id).where(
                table.c.school_id == user.school_id,
                table.c.assignment_id == assignment_id,
            )
        ).first()
        if current:
            db.execute(
                table.update()
                .where(table.c.id == int(current[0]))
                .values(**values)
            )
        else:
            db.execute(table.insert().values(**values, created_at=now))
        db.flush()
        row = db.execute(
            select(table).where(
                table.c.school_id == user.school_id,
                table.c.assignment_id == assignment_id,
            )
        ).first()
        return _draft_payload(row) or {}

    @app.get("/teacher/classroom-reviews/assignments")
    def classroom_review_assignments(
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        implementation.need(u, "teacher")
        assignments = teacher_assignment_rows(
            db,
            assignment_model=Assignment,
            class_model=SchoolClass,
            school_id=u.school_id,
            teacher_id=u.id,
        )[:40]
        out = []
        for assignment in assignments:
            class_row = db.get(SchoolClass, assignment.class_id)
            paper = db.get(Paper, assignment.paper_id)
            recipients = implementation.recipient_students(db, assignment)
            ids = [int(x.id) for x in recipients]
            completed = (
                int(
                    db.scalar(
                        select(implementation.func.count())
                        .select_from(Submission)
                        .where(
                            Submission.school_id == u.school_id,
                            Submission.assignment_id == assignment.id,
                            Submission.student_id.in_(ids),
                        )
                    )
                    or 0
                )
                if ids
                else 0
            )
            out.append(
                {
                    "id": int(assignment.id),
                    "title": str(assignment.title or ""),
                    "classID": int(assignment.class_id),
                    "className": str(class_row.name if class_row else ""),
                    "grade": int(class_row.grade if class_row else 0),
                    "subject": str(paper.subject if paper else ""),
                    "textbook": str(paper.textbook if paper else ""),
                    "unit": str(paper.unit if paper else ""),
                    "recipientCount": len(recipients),
                    "completedCount": completed,
                    "createdAt": implementation.school_local_iso(
                        assignment.created_at
                    ),
                }
            )
        return out

    @app.get("/teacher/assignments/{aid}/class-review")
    def classroom_review(
        aid: int,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        return review_summary(db, u, aid)

    @app.post("/teacher/assignments/{aid}/class-review/handout-generate")
    def generate_classroom_handout(
        aid: int,
        body: HandoutGenerateBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        summary = review_summary(db, u, aid)
        if not summary["handoutReady"]:
            raise HTTPException(400, "至少需要一名学生完成练习后才能生成课堂讲义")
        selected_knowledge = [
            str(x).strip()
            for x in body.selected_knowledge
            if str(x).strip()
        ][:20]
        selected_question_ids = [
            int(x)
            for x in body.selected_question_ids
            if int(x) > 0
        ][:30]
        if not selected_knowledge and not selected_question_ids:
            raise HTTPException(400, "请先选择至少一个知识点或典型错题")

        cfg = implementation.ai_config_for(db, u.school_id, False)
        if not cfg or not cfg.allow_student_data:
            raise HTTPException(
                403,
                "管理员尚未允许将匿名化学生学习统计发送给已配置的 AI 服务商",
            )
        prompt = build_anonymized_handout_prompt(
            summary,
            selected_knowledge=selected_knowledge,
            selected_question_ids=selected_question_ids,
            teacher_notes=body.teacher_notes[:3000],
        )
        content = str(
            implementation._ai_call(
                db,
                u,
                "class_review_handout",
                prompt,
                timeout=120,
            )
            or ""
        ).strip()
        if not content:
            raise HTTPException(502, "AI 未返回有效讲义内容")
        interaction_summary = build_deterministic_interaction_handout_summary(
            summary,
            selected_knowledge=selected_knowledge,
        )
        if interaction_summary:
            content = content.rstrip() + "\n\n" + interaction_summary
        title = (
            f"{summary['class']['name']} · {summary['assignment']['title']} "
            "课堂练习复盘讲义"
        )
        draft = save_draft(
            db,
            u,
            summary,
            title=title,
            content=content,
            selected_knowledge=selected_knowledge,
            selected_question_ids=selected_question_ids,
            teacher_notes=body.teacher_notes,
        )
        implementation.audit(
            db,
            u,
            "class.review.handout.generate",
            f"assignment={aid}:knowledge={len(selected_knowledge)}:questions={len(selected_question_ids)}",
        )
        db.commit()
        return {
            "ok": True,
            "handoutDraft": draft,
            "reviewRequired": True,
            "notice": "讲义仅为教师草稿，尚未发布给学生；请审核修改后再使用。",
        }

    @app.put("/teacher/assignments/{aid}/class-review/handout")
    def save_classroom_handout(
        aid: int,
        body: HandoutSaveBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        summary = review_summary(db, u, aid)
        content = body.content.strip()
        if not content:
            raise HTTPException(400, "讲义正文不能为空")
        title = body.title.strip() or (
            f"{summary['class']['name']} · {summary['assignment']['title']} "
            "课堂练习复盘讲义"
        )
        draft = save_draft(
            db,
            u,
            summary,
            title=title,
            content=content,
            selected_knowledge=body.selected_knowledge,
            selected_question_ids=body.selected_question_ids,
            teacher_notes=body.teacher_notes,
        )
        implementation.audit(
            db,
            u,
            "class.review.handout.save",
            f"assignment={aid}:chars={len(content)}",
        )
        db.commit()
        return {"ok": True, "handoutDraft": draft}

    @app.get("/v1/classroom-review", include_in_schema=False)
    def classroom_review_page():
        return HTMLResponse(
            v1_module.v1_html(),
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "X-Changying-V1": V1_CLASSROOM_REVIEW_MARKER,
            },
        )

    app.state.v1_classroom_review_routes_installed = True


__all__ = [
    "HandoutGenerateBody",
    "HandoutSaveBody",
    "V1_CLASSROOM_REVIEW_MARKER",
    "install_v1_classroom_review_patch",
    "install_v1_classroom_review_routes",
    "patch_v1_classroom_review_html",
    "register_classroom_review_table",
]
