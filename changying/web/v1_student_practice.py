"""Student-specific automatic tests and knowledge-module practice for V1.

The feature deliberately reuses the existing Question -> Paper -> Assignment ->
AssignmentRecipient pipeline.  It adds no schema and keeps every generated
activity attached to the student's existing long-term record.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import json
from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from changying.services.builtin_question_bank import (
    built_in_subjects,
    built_in_textbooks,
    ensure_built_in_questions,
    potential_question_catalog,
)
from changying.web import v1 as v1_module


V1_STUDENT_PRACTICE_MARKER = "changying_v1_student_practice_v1"


class StudentPracticeCreateBody(BaseModel):
    grade: int
    subject: str
    textbook: str = ""
    kind: str = "comprehensive"
    knowledge: str = ""
    question_count: int = 10
    due_date: str = ""
    class_id: int | None = None


def _is_online_question(row: Any) -> bool:
    try:
        options = json.loads(row.options_json or "[]")
    except Exception:
        return False
    return bool(
        isinstance(options, list)
        and len(options) >= 2
        and int(row.correct_index) >= 0
        and int(row.correct_index) < len(options)
    )


def select_student_practice_questions(
    rows: list[Any],
    *,
    kind: str,
    knowledge: str = "",
    count: int = 10,
    textbook: str = "",
) -> list[Any]:
    """Choose deterministic, valid quiz questions for one student activity.

    Comprehensive tests round-robin across knowledge modules so one large module
    cannot crowd out the rest.  Module practice keeps the exact knowledge key.
    """

    limit = max(1, min(int(count or 10), 50))
    selected_textbook = (textbook or "").strip()
    eligible = [row for row in rows if _is_online_question(row)]
    if selected_textbook:
        eligible = [
            row
            for row in eligible
            if str(row.textbook or "").strip() == selected_textbook
        ]
    eligible.sort(key=lambda row: int(row.id))

    if kind == "module":
        key = (knowledge or "").strip()
        if not key:
            return []
        return [row for row in eligible if (row.knowledge or "").strip() == key][:limit]

    if kind != "comprehensive":
        return []

    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in eligible:
        key = (row.knowledge or row.unit or "综合").strip() or "综合"
        grouped[key].append(row)

    chosen: list[Any] = []
    keys = sorted(grouped)
    offset = 0
    while len(chosen) < limit:
        added = False
        for key in keys:
            bucket = grouped[key]
            if offset < len(bucket):
                chosen.append(bucket[offset])
                added = True
                if len(chosen) >= limit:
                    break
        if not added:
            break
        offset += 1
    return chosen


def _practice_patch_html() -> str:
    return r'''
<style id="changying_v1_student_practice_v1-style">
.cy-student-practice-launch{margin-top:14px;border:1px solid rgba(255,255,255,.55);background:#fff;color:#173c78;border-radius:12px;padding:10px 13px;font-weight:900}
.cy-practice-layer{position:fixed;inset:0;z-index:96;background:rgba(15,23,42,.42);display:flex;align-items:flex-end;justify-content:center;padding:18px}
.cy-practice-sheet{width:min(760px,100%);max-height:min(90dvh,920px);overflow:auto;background:#f7f9fc;border-radius:24px;padding:18px;box-shadow:0 30px 90px rgba(15,23,42,.3)}
.cy-practice-head{position:sticky;top:-18px;z-index:2;display:flex;justify-content:space-between;gap:12px;align-items:center;background:rgba(247,249,252,.96);padding:18px 0 12px}
.cy-practice-head h2{margin:0}.cy-practice-close{border:1px solid #d8e0ec;background:#fff;border-radius:12px;padding:9px 12px;font-weight:800}
.cy-practice-note{padding:11px 12px;border-radius:12px;background:#eef6ff;border:1px solid #d4e7ff;color:#285078;font-size:12px;line-height:1.6}
.cy-practice-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}
.cy-practice-field{display:grid;gap:6px}.cy-practice-field label{font-size:12px;font-weight:800}
.cy-practice-field input,.cy-practice-field select{width:100%;border:1px solid #cfd7e5;border-radius:11px;background:#fff;padding:10px 11px;font:inherit}
.cy-practice-submit{width:100%;margin-top:14px;border:0;background:#173c78;color:#fff;border-radius:12px;padding:12px;font-weight:900}
.cy-practice-ok{margin-top:12px;padding:12px;border-radius:12px;background:#ecfdf3;color:#166534;border:1px solid #bbf7d0}
.cy-practice-error{margin-top:12px;padding:12px;border-radius:12px;background:#fff1f1;color:#991b1b;border:1px solid #fecaca}
@media(max-width:720px){.cy-practice-layer{padding:0}.cy-practice-sheet{max-height:92dvh;border-radius:24px 24px 0 0;padding:16px 14px calc(28px + env(safe-area-inset-bottom))}.cy-practice-grid{grid-template-columns:1fr}}
</style>
<script id="changying_v1_student_practice_v1-script">
(()=>{
 if(window.__cyStudentPracticeInstalled)return;window.__cyStudentPracticeInstalled=true;
 const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
 const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
 async function api(url,opt={}){const t=token();if(!t||t==='demo')throw new Error('演示会话不会写入真实教学数据');const headers={Authorization:'Bearer '+t,...(opt.headers||{})};if(opt.body&&!headers['Content-Type'])headers['Content-Type']='application/json';const r=await fetch(url,{...opt,headers,cache:'no-store'});if(!r.ok){let msg='操作失败 '+r.status;try{const d=await r.json();msg=d.detail||d.message||msg}catch{}throw new Error(msg)}return r.status===204?null:await r.json()}
 function close(){document.getElementById('cy-practice-layer')?.remove();document.body.style.overflow=''}
 function dueDefault(){return new Date(Date.now()+7*86400000).toISOString().slice(0,10)}
 async function loadOptions(sid,grade,subject,textbook){const p=new URLSearchParams();if(grade)p.set('grade',grade);if(subject)p.set('subject',subject);if(textbook)p.set('textbook',textbook);return api('/teacher/students/'+sid+'/practice-options?'+p.toString())}
 function optionRows(values,current){return values.map(v=>'<option value="'+esc(v)+'" '+(String(v)===String(current)?'selected':'')+'>'+esc(v)+'</option>').join('')}
 function renderForm(layer,data){
   const body=layer.querySelector('#cy-practice-body');const student=data.student||{};const grade=data.selectedGrade||student.grade||5;const subject=data.selectedSubject||data.subjects?.[0]||'数学';const textbooks=data.textbooks||[];const textbook=data.selectedTextbook||textbooks[0]||'';
   const modules=data.modules||[];const classes=data.classes||[];
   body.innerHTML='<div class="cy-practice-note">综合测试和知识模块练习都会严格按所选教材版本筛题，不会混用不同版本。当前年级科目可用约 '+esc(data.availableQuestionCount||0)+' 题'+(textbook?'（教材版本：'+esc(textbook)+'）':'')+'；系统标准题只会在你确认添加时补入现有题库。</div>'+
   '<form id="cy-practice-form"><div class="cy-practice-grid">'+
   '<div class="cy-practice-field"><label>学生</label><input value="'+esc(student.name||'学生')+'" disabled></div>'+
   '<div class="cy-practice-field"><label>教学班级</label><select id="cy-p-class">'+classes.map(c=>'<option value="'+c.id+'" '+(Number(c.id)===Number(data.defaultClassID)?'selected':'')+'>'+esc(c.name)+' · '+esc(c.grade)+'年级</option>').join('')+'</select></div>'+
   '<div class="cy-practice-field"><label>年级</label><select id="cy-p-grade">'+[1,2,3,4,5,6].map(g=>'<option value="'+g+'" '+(Number(g)===Number(grade)?'selected':'')+'>'+g+'年级</option>').join('')+'</select></div>'+
   '<div class="cy-practice-field"><label>科目</label><select id="cy-p-subject">'+optionRows(data.subjects||[],subject)+'</select></div>'+
   '<div class="cy-practice-field"><label>教材版本</label><select id="cy-p-textbook">'+optionRows(textbooks,textbook)+'</select></div>'+
   '<div class="cy-practice-field"><label>内容类型</label><select id="cy-p-kind"><option value="comprehensive">该科目综合测试</option><option value="module">知识模块练习</option></select></div>'+
   '<div class="cy-practice-field" id="cy-p-module-wrap" style="display:none"><label>知识模块</label><select id="cy-p-module">'+modules.map(m=>'<option value="'+esc(m.knowledge)+'">'+esc((m.unit?m.unit+' · ':'')+m.knowledge+'（'+m.count+'题）')+'</option>').join('')+'</select></div>'+
   '<div class="cy-practice-field"><label>题数</label><input id="cy-p-count" type="number" min="1" max="50" value="20"></div>'+
   '<div class="cy-practice-field"><label>截止日期</label><input id="cy-p-due" type="date" value="'+dueDefault()+'"></div>'+
   '</div><button class="cy-practice-submit" type="submit">自动添加给学生</button><div id="cy-practice-result"></div></form>';
   const kind=body.querySelector('#cy-p-kind'),moduleWrap=body.querySelector('#cy-p-module-wrap'),moduleEl=body.querySelector('#cy-p-module'),countEl=body.querySelector('#cy-p-count'),resultBox=body.querySelector('#cy-practice-result');
   const clearResult=()=>{resultBox.innerHTML=''};
   const syncCount=()=>{moduleWrap.style.display=kind.value==='module'?'grid':'none';const selected=modules.find(m=>m.knowledge===moduleEl?.value);const available=kind.value==='module'?Number(selected?.count||0):Number(data.availableQuestionCount||0);const max=Math.max(1,Math.min(50,available||50));countEl.max=String(max);const current=Number(countEl.value)||0;if(current<1||current>max)countEl.value=String(Math.min(kind.value==='module'?10:20,max));clearResult()};
   kind.onchange=syncCount;if(moduleEl)moduleEl.onchange=syncCount;countEl.oninput=clearResult;body.querySelector('#cy-p-due').onchange=clearResult;body.querySelector('#cy-p-class').onchange=clearResult;syncCount();
   async function refreshOptions(){try{const next=await loadOptions(student.id,body.querySelector('#cy-p-grade').value,body.querySelector('#cy-p-subject').value,body.querySelector('#cy-p-textbook')?.value||'');renderForm(layer,next)}catch(err){resultBox.innerHTML='<div class="cy-practice-error">'+esc(err.message)+'</div>'}}
   body.querySelector('#cy-p-grade').onchange=async()=>{try{const next=await loadOptions(student.id,body.querySelector('#cy-p-grade').value,'','');renderForm(layer,next)}catch(err){body.querySelector('#cy-practice-result').innerHTML='<div class="cy-practice-error">'+esc(err.message)+'</div>'}};
   body.querySelector('#cy-p-subject').onchange=async()=>{try{const next=await loadOptions(student.id,body.querySelector('#cy-p-grade').value,body.querySelector('#cy-p-subject').value,'');renderForm(layer,next)}catch(err){resultBox.innerHTML='<div class="cy-practice-error">'+esc(err.message)+'</div>'}};
   body.querySelector('#cy-p-textbook').onchange=refreshOptions;
   body.querySelector('#cy-practice-form').onsubmit=async e=>{e.preventDefault();const btn=e.submitter;btn.disabled=true;btn.textContent='正在自动组卷…';const result=body.querySelector('#cy-practice-result');try{const payload={grade:Number(body.querySelector('#cy-p-grade').value),subject:body.querySelector('#cy-p-subject').value,textbook:body.querySelector('#cy-p-textbook').value,kind:kind.value,knowledge:kind.value==='module'?(body.querySelector('#cy-p-module')?.value||''):'',question_count:Number(body.querySelector('#cy-p-count').value)||10,due_date:body.querySelector('#cy-p-due').value,class_id:Number(body.querySelector('#cy-p-class').value)||null};const created=await api('/teacher/students/'+student.id+'/auto-practice',{method:'POST',body:JSON.stringify(payload)});result.innerHTML='<div class="cy-practice-ok"><b>已添加：</b>'+esc(created.assignment?.title||'测试/练习')+' · '+esc(created.questionCount)+'题。学生完成后，成绩和知识点作答会继续进入现有学习记录。<br><button type="button" class="cy-practice-close" id="cy-practice-refresh" style="margin-top:9px">返回学生档案</button></div>';body.querySelector('#cy-practice-refresh').onclick=()=>location.reload()}catch(err){result.innerHTML='<div class="cy-practice-error">'+esc(err.message)+'</div>'}finally{btn.disabled=false;btn.textContent='自动添加给学生'}};
 }
 async function open(sid){close();const layer=document.createElement('div');layer.id='cy-practice-layer';layer.className='cy-practice-layer';layer.innerHTML='<section class="cy-practice-sheet"><div class="cy-practice-head"><div><h2>添加测试 / 练习</h2><small style="color:#667085">按学生、年级和科目自动从现有题库组卷</small></div><button class="cy-practice-close" type="button">关闭</button></div><div id="cy-practice-body">正在读取题库与学生信息…</div></section>';document.body.appendChild(layer);document.body.style.overflow='hidden';layer.querySelector('.cy-practice-close').onclick=close;layer.onclick=e=>{if(e.target===layer)close()};try{renderForm(layer,await loadOptions(sid,'','',''))}catch(err){layer.querySelector('#cy-practice-body').innerHTML='<div class="cy-practice-error">'+esc(err.message)+'</div>'}}
 let checking=false;
 async function mount(){if(checking||!location.pathname.includes('/v1/student'))return;const sid=Number(new URLSearchParams(location.search).get('id')||0);const head=document.querySelector('.student-head');if(!sid||!head||head.querySelector('.cy-student-practice-launch'))return;checking=true;try{const s=await api('/session');if(s.role!=='teacher')return;const b=document.createElement('button');b.type='button';b.className='cy-student-practice-launch';b.textContent='＋ 添加测试 / 练习';b.onclick=()=>open(sid);head.appendChild(b)}catch(_){}finally{checking=false}}
 const observer=new MutationObserver(()=>mount());observer.observe(document.documentElement,{subtree:true,childList:true});window.addEventListener('popstate',mount);setTimeout(mount,0);
})();
</script>
'''


def patch_v1_student_practice_html(html: str) -> str:
    if V1_STUDENT_PRACTICE_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 student practice patch: closing body marker not found")
    return html.replace("</body>", _practice_patch_html() + "\n</body>", 1)


def install_v1_student_practice_patch() -> None:
    if getattr(v1_module, "_student_practice_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_student_practice_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._student_practice_patch_installed = True


def install_v1_student_practice_routes(implementation: Any) -> None:
    app = implementation.app
    if getattr(app.state, "v1_student_practice_routes_installed", False):
        return

    User = implementation.User
    Question = implementation.Question
    Paper = implementation.Paper
    Assignment = implementation.Assignment
    AssignmentSubmissionSetting = implementation.AssignmentSubmissionSetting
    SchoolClass = implementation.SchoolClass
    ClassStudent = implementation.ClassStudent
    current_user = implementation.current_user
    get_db = implementation.get_db
    Session = implementation.Session

    def teacher_student_context(db, user, sid: int) -> tuple[Any, list[Any]]:
        implementation.need(user, "teacher")
        student = db.scalar(
            select(User).where(
                User.id == sid,
                User.school_id == user.school_id,
                User.role == "student",
                User.active == True,
            )
        )
        if not student:
            raise HTTPException(404, "学生不存在或已归档")
        classes = list(
            db.scalars(
                select(SchoolClass)
                .join(ClassStudent, ClassStudent.class_id == SchoolClass.id)
                .where(
                    ClassStudent.student_id == sid,
                    SchoolClass.school_id == user.school_id,
                    SchoolClass.teacher_id == user.id,
                )
                .order_by(SchoolClass.id.desc())
            ).all()
        )
        if not classes:
            raise HTTPException(403, "该学生不在你的在读班级")
        return student, classes

    @app.get("/teacher/students/{sid}/practice-options")
    def student_practice_options(
        sid: int,
        grade: int | None = None,
        subject: str | None = None,
        textbook: str | None = None,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        student, classes = teacher_student_context(db, u, sid)
        selected_grade = int(grade or student.grade or classes[0].grade or 5)
        if selected_grade not in range(1, 7):
            raise HTTPException(400, "年级必须为1-6")

        subjects = list(
            db.scalars(
                select(Question.subject)
                .where(
                    Question.school_id == u.school_id,
                    Question.grade == selected_grade,
                )
                .distinct()
                .order_by(Question.subject)
            ).all()
        )
        subjects = [str(x).strip() for x in subjects if str(x or "").strip()]
        subjects = sorted(set(subjects) | set(built_in_subjects(selected_grade)))
        selected_subject = (subject or "").strip()
        if not selected_subject or selected_subject not in subjects:
            selected_subject = subjects[0] if subjects else ""

        textbooks: list[str] = []
        selected_textbook = ""
        if selected_subject:
            textbooks = list(
                db.scalars(
                    select(Question.textbook)
                    .where(
                        Question.school_id == u.school_id,
                        Question.grade == selected_grade,
                        Question.subject == selected_subject,
                    )
                    .distinct()
                    .order_by(Question.textbook)
                ).all()
            )
            textbooks = [
                str(x).strip()
                for x in textbooks
                if str(x or "").strip()
            ]
            textbooks = sorted(
                set(textbooks)
                | set(built_in_textbooks(selected_grade, selected_subject))
            )
            selected_textbook = (textbook or "").strip()
            if not selected_textbook or selected_textbook not in textbooks:
                selected_textbook = textbooks[0] if textbooks else ""

        modules: list[dict[str, Any]] = []
        available_count = 0
        if selected_subject and selected_textbook:
            rows = list(
                db.scalars(
                    select(Question)
                    .where(
                        Question.school_id == u.school_id,
                        Question.grade == selected_grade,
                        Question.subject == selected_subject,
                        Question.textbook == selected_textbook,
                    )
                    .order_by(Question.unit, Question.knowledge, Question.id)
                ).all()
            )
            modules, available_count = potential_question_catalog(
                rows,
                grade=selected_grade,
                subject=selected_subject,
                textbook=selected_textbook,
            )

        default_class = next(
            (c for c in classes if int(c.grade or 0) == int(student.grade or 0)),
            classes[0],
        )
        return {
            "student": {"id": student.id, "name": student.name, "grade": student.grade},
            "classes": [
                {"id": c.id, "name": c.name, "grade": c.grade}
                for c in classes
            ],
            "defaultClassID": default_class.id,
            "selectedGrade": selected_grade,
            "subjects": subjects,
            "selectedSubject": selected_subject,
            "textbooks": textbooks,
            "selectedTextbook": selected_textbook,
            "modules": modules,
            "availableQuestionCount": available_count,
        }

    @app.post("/teacher/students/{sid}/auto-practice")
    def create_student_practice(
        sid: int,
        body: StudentPracticeCreateBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        student, classes = teacher_student_context(db, u, sid)
        if body.grade not in range(1, 7):
            raise HTTPException(400, "年级必须为1-6")
        subject = (body.subject or "").strip()
        if not subject:
            raise HTTPException(400, "请选择科目")
        textbook = (body.textbook or "").strip()
        if not textbook:
            raise HTTPException(400, "请选择教材版本")
        kind = (body.kind or "comprehensive").strip().lower()
        if kind not in {"comprehensive", "module"}:
            raise HTTPException(400, "内容类型无效")
        count = max(1, min(int(body.question_count or 10), 50))

        class_row = None
        if body.class_id:
            class_row = next((c for c in classes if c.id == body.class_id), None)
            if not class_row:
                raise HTTPException(403, "所选班级不属于该学生或当前教师")
        else:
            class_row = next(
                (c for c in classes if int(c.grade or 0) == int(student.grade or 0)),
                classes[0],
            )

        ensure_built_in_questions(
            db,
            Question,
            school_id=u.school_id,
            creator_id=u.id,
            grade=body.grade,
            subject=subject,
            textbook=textbook,
        )
        rows = list(
            db.scalars(
                select(Question)
                .where(
                    Question.school_id == u.school_id,
                    Question.grade == body.grade,
                    Question.subject == subject,
                    Question.textbook == textbook,
                )
                .order_by(Question.id)
            ).all()
        )
        chosen = select_student_practice_questions(
            rows,
            kind=kind,
            knowledge=body.knowledge,
            count=count,
            textbook=textbook,
        )
        if not chosen:
            if kind == "module":
                raise HTTPException(400, "当前题库没有该知识模块可用于在线练习的题目")
            raise HTTPException(400, "当前题库没有该年级科目可用于综合测试的题目")

        if kind == "module":
            knowledge = (body.knowledge or "").strip()
            title = f"{body.grade}年级{subject}（{textbook}）· {knowledge}专项练习"
            unit = knowledge
            source = "student_module_practice"
        else:
            title = f"{body.grade}年级{subject}（{textbook}）综合测试"
            unit = "综合"
            source = "student_comprehensive_test"

        due_date = (body.due_date or "").strip() or (
            datetime.utcnow() + timedelta(days=7)
        ).date().isoformat()
        question_ids = [int(q.id) for q in chosen]
        paper = Paper(
            school_id=u.school_id,
            title=title[:160],
            grade=body.grade,
            subject=subject[:30],
            textbook=textbook[:80],
            unit=unit[:100],
            question_ids_json=json.dumps(question_ids),
            teacher_id=u.id,
        )
        db.add(paper)
        db.flush()
        assignment = Assignment(
            school_id=u.school_id,
            title=title[:160],
            class_id=class_row.id,
            paper_id=paper.id,
            due_date=due_date,
        )
        db.add(assignment)
        db.flush()
        db.add(
            AssignmentSubmissionSetting(
                school_id=u.school_id,
                assignment_id=assignment.id,
                mode="quiz",
                instructions=(
                    "完成后用于更新当前学生的学科与知识点学习记录。"
                    if kind == "comprehensive"
                    else "完成该知识模块练习，并根据结果继续安排针对性巩固。"
                ),
            )
        )
        implementation.ensure_recipient(
            db,
            assignment,
            student.id,
            source,
        )
        covered = sorted(
            {
                (q.knowledge or q.unit or "综合").strip() or "综合"
                for q in chosen
            }
        )
        implementation.audit(
            db,
            u,
            "student.practice.create",
            (
                f"student={student.id}:assignment={assignment.id}:"
                f"kind={kind}:grade={body.grade}:subject={subject}:"
                f"textbook={textbook}:"
                f"questions={len(question_ids)}"
            ),
        )
        db.commit()
        db.refresh(assignment)
        return {
            "ok": True,
            "student": {"id": student.id, "name": student.name},
            "assignment": implementation.aj(db, assignment),
            "paper": implementation.pj(paper),
            "kind": kind,
            "textbook": textbook,
            "questionCount": len(question_ids),
            "knowledgeCovered": covered,
            "recipientCount": 1,
        }

    app.state.v1_student_practice_routes_installed = True


__all__ = [
    "StudentPracticeCreateBody",
    "V1_STUDENT_PRACTICE_MARKER",
    "install_v1_student_practice_patch",
    "install_v1_student_practice_routes",
    "patch_v1_student_practice_html",
    "select_student_practice_questions",
]
