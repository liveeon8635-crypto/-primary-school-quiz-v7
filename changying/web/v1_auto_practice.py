"""Teacher workflow for per-student automatic tests and knowledge practice."""

from __future__ import annotations

from datetime import date, timedelta
from types import ModuleType

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from changying.services.auto_practice import question_catalog, select_auto_practice_questions
from changying.web import v1 as v1_module


V1_AUTO_PRACTICE_MARKER = "changying_v1_auto_practice_v1"


class AutoPracticeCreate(BaseModel):
    grade: int
    subject: str
    mode: str = "comprehensive"
    knowledge: str = ""
    count: int = 10
    due_date: str = ""


def _managed_student_context(implementation: ModuleType, db, user, sid: int):
    implementation.need(user, "teacher")
    student = db.scalar(
        implementation.select(implementation.User).where(
            implementation.User.id == sid,
            implementation.User.school_id == user.school_id,
            implementation.User.role == "student",
            implementation.User.active == True,
        )
    )
    if student is None:
        raise HTTPException(404, "学生不存在或已停用")

    school_class = db.scalar(
        implementation.select(implementation.SchoolClass)
        .join(
            implementation.ClassStudent,
            implementation.ClassStudent.class_id == implementation.SchoolClass.id,
        )
        .where(
            implementation.ClassStudent.student_id == sid,
            implementation.SchoolClass.school_id == user.school_id,
            implementation.SchoolClass.teacher_id == user.id,
        )
        .order_by(implementation.SchoolClass.id.desc())
        .limit(1)
    )
    if school_class is None:
        raise HTTPException(403, "该学生不在你管理的班级中")
    return student, school_class


def install_v1_auto_practice_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v1_auto_practice_routes_installed", False):
        return

    @app.get("/teacher/students/{sid}/auto-practice/options", include_in_schema=False)
    def auto_practice_options(
        sid: int,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        student, school_class = _managed_student_context(implementation, db, user, sid)
        rows = db.scalars(
            implementation.select(implementation.Question)
            .where(implementation.Question.school_id == user.school_id)
            .order_by(
                implementation.Question.grade,
                implementation.Question.subject,
                implementation.Question.knowledge,
                implementation.Question.id,
            )
        ).all()
        return {
            "student": {
                "id": student.id,
                "name": student.name,
                "grade": student.grade,
                "classID": school_class.id,
                "className": school_class.name,
            },
            "catalog": [row for row in question_catalog(rows) if row.get("subject")],
        }

    @app.post("/teacher/students/{sid}/auto-practice", include_in_schema=False)
    def create_auto_practice(
        sid: int,
        body: AutoPracticeCreate,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        student, school_class = _managed_student_context(implementation, db, user, sid)
        grade = int(body.grade)
        if grade not in range(1, 7):
            raise HTTPException(400, "年级必须为1-6")
        subject = (body.subject or "").strip()
        if not subject:
            raise HTTPException(400, "请选择科目")
        mode = (body.mode or "").strip().lower()
        if mode not in {"comprehensive", "knowledge"}:
            raise HTTPException(400, "练习类型无效")
        knowledge = (body.knowledge or "").strip()
        if mode == "knowledge" and not knowledge:
            raise HTTPException(400, "请选择知识模块")
        count = max(1, min(int(body.count or 1), 30))

        rows = db.scalars(
            implementation.select(implementation.Question)
            .where(
                implementation.Question.school_id == user.school_id,
                implementation.Question.grade == grade,
                implementation.Question.subject == subject,
            )
            .order_by(implementation.Question.id)
        ).all()
        selected = select_auto_practice_questions(
            rows, mode=mode, count=count, knowledge=knowledge
        )
        if not selected:
            if mode == "knowledge":
                raise HTTPException(400, "当前题库没有该知识模块可用在线题目")
            raise HTTPException(400, "当前题库没有该年级科目的可用在线题目")

        due_date = (body.due_date or "").strip()
        if not due_date:
            due_date = (date.today() + timedelta(days=7)).isoformat()
        try:
            date.fromisoformat(due_date)
        except ValueError as exc:
            raise HTTPException(400, "截止日期格式无效") from exc

        title = (
            f"{grade}年级{subject}综合测试"
            if mode == "comprehensive"
            else f"{grade}年级{subject}·{knowledge}练习"
        )
        module_names = sorted(
            {
                str(row.knowledge or "").strip()
                for row in selected
                if str(row.knowledge or "").strip()
            }
        )
        textbooks = {
            str(row.textbook or "").strip()
            for row in selected
            if str(row.textbook or "").strip()
        }
        textbook = next(iter(textbooks)) if len(textbooks) == 1 else ""

        paper = implementation.Paper(
            school_id=user.school_id,
            title=title[:160],
            grade=grade,
            subject=subject[:30],
            textbook=textbook[:80],
            unit=("综合测试" if mode == "comprehensive" else knowledge)[:100],
            question_ids_json=implementation.json.dumps([int(row.id) for row in selected]),
            teacher_id=user.id,
        )
        db.add(paper)
        db.flush()

        assignment = implementation.Assignment(
            school_id=user.school_id,
            title=title[:160],
            class_id=school_class.id,
            paper_id=paper.id,
            due_date=due_date,
        )
        db.add(assignment)
        db.flush()

        instructions = (
            f"完成{grade}年级{subject}综合测试，用于了解当前知识掌握情况。"
            if mode == "comprehensive"
            else f"完成{subject}“{knowledge}”知识模块练习。"
        )
        db.add(
            implementation.AssignmentSubmissionSetting(
                school_id=user.school_id,
                assignment_id=assignment.id,
                mode="quiz",
                instructions=instructions[:2000],
            )
        )
        implementation.ensure_recipient(
            db, assignment, student.id, "teacher_auto_practice"
        )
        implementation.audit(
            db,
            user,
            "student_auto_practice.create",
            (
                f"assignment={assignment.id}:student={student.id}:grade={grade}:"
                f"subject={subject}:mode={mode}:knowledge={knowledge}:questions={len(selected)}"
            ),
        )
        db.commit()
        db.refresh(assignment)
        return {
            "ok": True,
            "assignment": implementation.aj(db, assignment),
            "paperID": paper.id,
            "studentID": student.id,
            "studentName": student.name,
            "mode": mode,
            "knowledge": knowledge,
            "questionCount": len(selected),
            "knowledgeModules": module_names,
        }

    app.state.v1_auto_practice_routes_installed = True


_AUTO_PRACTICE_STYLE = """
<style id="changying_v1_auto_practice_v1-style">
.cy-auto-layer{position:fixed;inset:0;z-index:95;background:rgba(15,23,42,.44);display:flex;align-items:flex-end;justify-content:center;padding:18px}
.cy-auto-sheet{width:min(720px,100%);max-height:min(90dvh,900px);overflow:auto;background:#f7f9fc;border:1px solid #dfe6f0;border-radius:24px;padding:18px;box-shadow:0 30px 90px rgba(15,23,42,.3)}
.cy-auto-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.cy-auto-head h2{margin:0 0 4px}.cy-auto-head p{margin:0;color:#667085;font-size:13px}
.cy-auto-close{border:1px solid #d8e0ec;background:#fff;border-radius:11px;padding:8px 11px;font-weight:800}
.cy-auto-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:11px;margin-top:14px}.cy-auto-field{display:grid;gap:6px}.cy-auto-field label{font-size:12px;font-weight:800}
.cy-auto-field input,.cy-auto-field select{width:100%;border:1px solid #cfd7e5;border-radius:11px;background:#fff;padding:10px 11px;font:inherit}
.cy-auto-note{margin-top:13px;padding:11px 12px;border-radius:12px;background:#eef6ff;border:1px solid #d4e7ff;color:#285078;font-size:12px;line-height:1.65}.cy-auto-submit{width:100%;margin-top:14px}
@media(max-width:720px){.cy-auto-layer{padding:0}.cy-auto-sheet{border-radius:24px 24px 0 0;padding:17px 14px calc(28px + env(safe-area-inset-bottom))}.cy-auto-grid{grid-template-columns:1fr}}
</style>
"""

_AUTO_PRACTICE_JS = r"""
async function openAutoPractice(studentID,studentName,defaultGrade){
  var data;
  try{data=await api('/teacher/students/'+studentID+'/auto-practice/options')}
  catch(err){toast(err.message||'无法读取测试题库');return}
  var catalog=Array.isArray(data.catalog)?data.catalog:[];
  if(!catalog.length){toast('当前题库没有可用于在线测试的题目');return}
  var old=document.getElementById('cy-auto-layer');if(old)old.remove();
  var layer=document.createElement('div');layer.id='cy-auto-layer';layer.className='cy-auto-layer';
  var grades=Array.from(new Set(catalog.map(function(x){return Number(x.grade)}).filter(Boolean))).sort(function(a,b){return a-b});
  var initial=grades.includes(Number(defaultGrade))?Number(defaultGrade):grades[0];
  layer.innerHTML='<section class="cy-auto-sheet" role="dialog" aria-modal="true"><div class="cy-auto-head"><div><h2>自动添加测试 / 练习</h2><p>'+esc(studentName)+' · 从现有题库自动组卷，只布置给该学生</p></div><button class="cy-auto-close" type="button">关闭</button></div><div class="cy-auto-note">综合测试尽量跨多个知识模块取题，用于反馈学科整体掌握情况；知识模块练习只使用指定模块题目。</div><div class="cy-auto-grid"><div class="cy-auto-field"><label>年级</label><select id="cy-auto-grade"></select></div><div class="cy-auto-field"><label>科目</label><select id="cy-auto-subject"></select></div><div class="cy-auto-field"><label>内容类型</label><select id="cy-auto-mode"><option value="comprehensive">该科目综合测试</option><option value="knowledge">知识模块练习</option></select></div><div class="cy-auto-field" id="cy-auto-knowledge-wrap"><label>知识模块</label><select id="cy-auto-knowledge"></select></div><div class="cy-auto-field"><label>题数</label><input id="cy-auto-count" type="number" min="1" max="30" value="10"></div><div class="cy-auto-field"><label>截止日期</label><input id="cy-auto-due" type="date"></div></div><div id="cy-auto-availability" class="cy-auto-note"></div><button id="cy-auto-submit" class="btn primary cy-auto-submit" type="button">自动添加</button></section>';
  document.body.appendChild(layer);document.body.style.overflow='hidden';
  var close=function(){layer.remove();document.body.style.overflow=''};
  layer.querySelector('.cy-auto-close').onclick=close;layer.onclick=function(e){if(e.target===layer)close()};
  var gradeEl=layer.querySelector('#cy-auto-grade'),subjectEl=layer.querySelector('#cy-auto-subject'),modeEl=layer.querySelector('#cy-auto-mode'),knowledgeEl=layer.querySelector('#cy-auto-knowledge'),knowledgeWrap=layer.querySelector('#cy-auto-knowledge-wrap'),countEl=layer.querySelector('#cy-auto-count'),availability=layer.querySelector('#cy-auto-availability');
  gradeEl.innerHTML=grades.map(function(g){return '<option value="'+g+'" '+(g===initial?'selected':'')+'>'+g+'年级</option>'}).join('');
  layer.querySelector('#cy-auto-due').value=new Date(Date.now()+7*86400000).toISOString().slice(0,10);
  var currentEntry=function(){return catalog.find(function(x){return Number(x.grade)===Number(gradeEl.value)&&x.subject===subjectEl.value})};
  var renderKnowledge=function(){var entry=currentEntry()||{},modules=entry.modules||[];knowledgeEl.innerHTML=modules.map(function(x){return '<option value="'+esc(x.name)+'">'+esc(x.name)+' · '+x.questionCount+'题</option>'}).join('')||'<option value="">暂无知识模块</option>';knowledgeWrap.style.display=modeEl.value==='knowledge'?'grid':'none';var available=modeEl.value==='knowledge'?((modules.find(function(x){return x.name===knowledgeEl.value})||{}).questionCount||0):(entry.questionCount||0);availability.textContent='当前可用 '+available+' 题'+(modeEl.value==='comprehensive'&&modules.length?' · 覆盖 '+modules.length+' 个知识模块':'')};
  var renderSubjects=function(){var g=Number(gradeEl.value),entries=catalog.filter(function(x){return Number(x.grade)===g});subjectEl.innerHTML=entries.map(function(x){return '<option value="'+esc(x.subject)+'">'+esc(x.subject)+' · '+x.questionCount+'题</option>'}).join('');renderKnowledge()};
  gradeEl.onchange=renderSubjects;subjectEl.onchange=renderKnowledge;modeEl.onchange=function(){countEl.value=modeEl.value==='knowledge'?'6':'10';renderKnowledge()};knowledgeEl.onchange=renderKnowledge;renderSubjects();
  layer.querySelector('#cy-auto-submit').onclick=async function(){var btn=layer.querySelector('#cy-auto-submit');btn.disabled=true;btn.textContent='正在自动组卷…';try{var payload={grade:Number(gradeEl.value),subject:subjectEl.value,mode:modeEl.value,knowledge:modeEl.value==='knowledge'?knowledgeEl.value:'',count:Number(countEl.value)||1,due_date:layer.querySelector('#cy-auto-due').value};var result=await api('/teacher/students/'+studentID+'/auto-practice',{method:'POST',body:JSON.stringify(payload)});close();toast('已添加 '+result.questionCount+' 题：'+((result.assignment||{}).title||'测试/练习'));await studentPage()}catch(err){toast(err.message||'自动添加失败');btn.disabled=false;btn.textContent='自动添加'}};
}
"""

_FUNCTION_ANCHOR = "    async function studentPage(){"
_BIND_ANCHOR = (
    "screen.innerHTML=shell(content,'students');bindNav();"
    "document.getElementById('transitionLink').onclick="
    "()=>navigate('/v1/transition?id='+id);"
)


def patch_v1_auto_practice_html(html: str) -> str:
    if V1_AUTO_PRACTICE_MARKER in html:
        return html
    if _FUNCTION_ANCHOR not in html:
        raise RuntimeError("V1 auto practice patch: student function anchor not found")
    if _BIND_ANCHOR not in html:
        raise RuntimeError("V1 auto practice patch: student bind anchor not found")

    html = html.replace(
        _FUNCTION_ANCHOR,
        _AUTO_PRACTICE_JS + "\n" + _FUNCTION_ANCHOR,
        1,
    )
    bind = (
        _BIND_ANCHOR
        + "if(session.role==='teacher'&&!session.demo){"
        + "const meta=document.querySelector('.student-meta');"
        + "if(meta){const b=document.createElement('button');"
        + "b.className='btn';b.id='cyAutoPracticeBtn';b.type='button';"
        + "b.textContent='自动添加测试/练习';"
        + "b.onclick=()=>openAutoPractice(id,s.name||'学生',s.grade||5);"
        + "meta.appendChild(b)}}"
    )
    html = html.replace(_BIND_ANCHOR, bind, 1)
    html = html.replace("</head>", _AUTO_PRACTICE_STYLE + "\n</head>", 1)
    return html.replace(
        "</body>",
        "<!-- " + V1_AUTO_PRACTICE_MARKER + " --></body>",
        1,
    )


def install_v1_auto_practice(implementation: ModuleType) -> None:
    if not getattr(v1_module, "_auto_practice_patch_installed", False):
        original = v1_module.v1_html

        def patched_v1_html() -> str:
            return patch_v1_auto_practice_html(original())

        v1_module.v1_html = patched_v1_html
        v1_module._auto_practice_patch_installed = True
    install_v1_auto_practice_routes(implementation)


__all__ = [
    "V1_AUTO_PRACTICE_MARKER",
    "install_v1_auto_practice",
    "patch_v1_auto_practice_html",
]
