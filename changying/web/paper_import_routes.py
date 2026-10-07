"""Paper import routes (导入试卷 / 真题).

POST /teacher/papers/import/parse  -> AI transcription for teacher review (no writes
                                      besides the AI usage log)
POST /teacher/papers/import/save   -> saves the reviewed questions as a paper and,
                                      optionally, assigns it to one of the teacher's classes
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from changying.services.paper_composition import distribution_text, type_distribution
from changying.services.paper_import import (
    MAX_IMAGES,
    MAX_IMPORT_QUESTIONS,
    PaperImportError,
    build_import_prompt,
    clean_images,
    clean_import_rows,
    decode_upload,
    extract_paper_upload,
    import_summary,
    storage_fields,
    validate_question,
)


class PaperImportScope(BaseModel):
    grade: int = 5
    subject: str = "数学"
    textbook: str = ""
    semester: str = "上册"
    unit: str = ""


class PaperImportParseBody(PaperImportScope):
    text: str = ""
    file_name: str = ""
    file_base64: str = ""
    images: list[str] = []


class PaperImportSaveBody(PaperImportScope):
    title: str = ""
    questions: list[dict[str, Any]]
    class_id: Optional[int] = None
    due_date: str = ""
    instructions: str = ""
    # False: 教材题库 "拍照/导入新增题目" (feedback #337) saves questions only.
    create_paper: bool = True


def _check_scope(b: PaperImportScope) -> None:
    if b.grade < 1 or b.grade > 9:
        raise HTTPException(400, "年级须为 1-9")
    if not str(b.subject or "").strip():
        raise HTTPException(400, "请选择学科")


def install_paper_import_routes(implementation: Any) -> None:
    app = implementation.app
    if getattr(app.state, "paper_import_routes_installed", False):
        return
    router = APIRouter()
    current_user = implementation.current_user
    get_db = implementation.get_db

    @router.post("/teacher/papers/import/parse")
    def parse_paper(b: PaperImportParseBody, u: Any = Depends(current_user), db: Any = Depends(get_db)) -> dict[str, Any]:
        implementation.need(u, "admin", "teacher")
        _check_scope(b)
        try:
            text = str(b.text or "")
            images = clean_images(b.images)
            if b.file_base64:
                file_text, scans = extract_paper_upload(b.file_name, decode_upload(b.file_base64),
                                                        max_images=MAX_IMAGES - len(images))
                text = (text + "\n" + file_text).strip()
                images += scans
        except PaperImportError as exc:
            raise HTTPException(400, str(exc)) from exc
        if not text.strip() and not images:
            raise HTTPException(400, "请粘贴试卷文字、上传文件或拍照后再导入")
        prompt = build_import_prompt(grade=b.grade, subject=b.subject, textbook=b.textbook, semester=b.semester,
                                     unit=b.unit, text=text[:30000], has_images=bool(images))
        raw = implementation._ai_json(implementation._ai_call(db, u, "paper_import", prompt, images=images, timeout=150))
        try:
            result = clean_import_rows(raw, subject=b.subject)
        except PaperImportError as exc:
            raise HTTPException(502, str(exc)) from exc
        if not result["items"]:
            raise HTTPException(502, "没有识别出可用的题目；请检查试卷内容是否清晰完整后重试")
        # Figures are cut out in the browser (no imaging library on the server), so
        # send back only the photos/scans that a figure region points into.
        for item in result["items"]:
            region = item.get("figureRegion")
            if region and region["image"] >= len(images):
                item.pop("figureRegion")
        used = sorted({item["figureRegion"]["image"] for item in result["items"] if item.get("figureRegion")})
        result["sourceImages"] = {str(i): images[i] for i in used}
        summary = import_summary(result["items"])
        implementation.audit(db, u, "paper.import.parse", f"{b.grade}:{b.subject}:{b.unit}:items={summary['total']}:ai_answers={summary['aiAnswers']}:needs_answer={summary['needsAnswer']}:skipped={len(result['skipped'])}")
        db.commit()
        notes = []
        if summary["aiAnswers"]:
            notes.append(f"{summary['aiAnswers']} 道题的答案由 AI 解答，请逐题核对")
        if summary["figures"]:
            notes.append(f"{summary['figures']} 道题已从原卷裁出插图，请核对插图是否完整")
        if summary["needsAnswer"]:
            notes.append(f"{summary['needsAnswer']} 道题缺少答案，需补全后才能保存")
        if result["skipped"]:
            notes.append(f"{len(result['skipped'])} 道题没有录入（看不清，或插图无法从原卷裁出）" if images else
                         f"{len(result['skipped'])} 道题没有录入（看不清或需要原卷插图；带图的题请改用拍照或扫描版 PDF 导入，可连图一起录入）")
        return {**result, "summary": summary, "reviewRequired": True,
                "notice": "；".join(notes) or "已按试卷答案录入，请核对后保存"}

    @router.post("/teacher/papers/import/save")
    def save_paper(b: PaperImportSaveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)) -> dict[str, Any]:
        implementation.need(u, "admin", "teacher")
        _check_scope(b)
        if b.create_paper and u.role != "teacher":
            raise HTTPException(403, "只有教师可以保存试卷或布置作业；管理员可保存到题库")
        if not b.create_paper and b.class_id is not None:
            raise HTTPException(400, "只保存到题库时不能同时布置作业")
        title = (b.title or "").strip()[:160]
        if b.create_paper and not title:
            raise HTTPException(400, "请填写试卷名称")
        if not b.questions or len(b.questions) > MAX_IMPORT_QUESTIONS:
            raise HTTPException(400, f"每份试卷保存 1-{MAX_IMPORT_QUESTIONS} 道题")
        cls = None
        if b.class_id is not None:
            cls = db.scalar(select(implementation.SchoolClass).where(
                implementation.SchoolClass.id == b.class_id, implementation.SchoolClass.school_id == u.school_id,
                implementation.SchoolClass.teacher_id == u.id))
            if not cls:
                raise HTTPException(404, "班级不存在或无权限")
        validated = []
        for index, raw in enumerate(b.questions, start=1):
            item, problem = validate_question(raw, subject=b.subject, require_answer=True)
            if item is None:
                raise HTTPException(400, f"第 {index} 题：{problem or '格式无效'}，请补全后再保存")
            validated.append(item)
        Question = implementation.Question
        ids, types = [], {}
        for item in validated:
            row = Question(school_id=u.school_id, grade=b.grade, subject=b.subject[:30], textbook=(b.textbook or "")[:80],
                           semester=(b.semester or "上册")[:20], unit=(b.unit or "导入试卷")[:100], knowledge=item["knowledge"][:120],
                           text=item["text"], creator_id=u.id, **storage_fields(item))
            db.add(row)
            db.flush()
            ids.append(int(row.id))
            types[int(row.id)] = item["question_type"]
        distribution = type_distribution(types, ids)
        if not b.create_paper:
            implementation.audit(db, u, "question.import.save", f"questions={len(ids)}:types={json.dumps(distribution, ensure_ascii=False)}")
            db.commit()
            return {"savedCount": len(ids), "questionIDs": ids, "typeDistribution": distribution, "typeSummary": distribution_text(distribution)}
        paper = implementation.Paper(school_id=u.school_id, title=title, grade=b.grade, subject=b.subject[:30],
                                     textbook=(b.textbook or "")[:80], unit=(b.unit or "")[:100],
                                     question_ids_json=json.dumps(ids), teacher_id=u.id)
        db.add(paper)
        db.flush()
        assignment = None
        if cls is not None:
            has_open = "non_choice" in distribution
            due = (b.due_date or (datetime.now(implementation.SCHOOL_TZ).date() + timedelta(days=7)).isoformat())[:20]
            assignment = implementation.Assignment(school_id=u.school_id, title=title, class_id=cls.id, paper_id=paper.id, due_date=due)
            db.add(assignment)
            db.flush()
            default_note = ("含教师审核主观题：请在作业本/答题纸完成后拍照上传，教师审核评分。" if has_open
                            else "导入试卷：在线完成并由服务器判分。")
            db.add(implementation.AssignmentSubmissionSetting(school_id=u.school_id, assignment_id=assignment.id,
                                                             mode="media" if has_open else "quiz",
                                                             instructions=(b.instructions or default_note)[:2000]))
            User, ClassStudent = implementation.User, implementation.ClassStudent
            student_ids = db.scalars(select(ClassStudent.student_id).join(User, User.id == ClassStudent.student_id).where(
                ClassStudent.class_id == cls.id, User.school_id == u.school_id, User.role == "student", User.active == True)).all()  # noqa: E712
            for sid in student_ids:
                implementation.ensure_recipient(db, assignment, sid, "paper_import")
        implementation.audit(db, u, "paper.import.save", f"paper={paper.id}:questions={len(ids)}:types={json.dumps(distribution, ensure_ascii=False)}:assignment={assignment.id if assignment else ''}")
        db.commit()
        db.refresh(paper)
        out = {**implementation.pj(paper), "typeDistribution": distribution, "typeSummary": distribution_text(distribution)}
        if assignment is not None:
            db.refresh(assignment)
            out["assignment"] = implementation.aj(db, assignment)
        return out

    app.include_router(router)
    app.state.paper_import_routes_installed = True
