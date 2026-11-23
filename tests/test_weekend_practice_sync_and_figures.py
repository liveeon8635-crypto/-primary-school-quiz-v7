"""Regression tests for Stage-4 practice open control and board/student figures."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("practice_sync_fig_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_stage4_open_control_and_question_figures_for_board_and_student(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r"""
from sqlalchemy import update
from changying.services.lesson_written import template_meta, written_templates
from changying.web.weekend_written import register_written_tables

picture = "data:image/jpeg;base64,/9j/2Q=="
MD = '''# 第12课：梯形与组合图形面积
## 本节目标
掌握梯形面积公式。
## 教学流程
讲解与随堂练习。
## 例题
1. 例1 已知梯形上底2厘米、下底4厘米、高3厘米，求面积。
【答案】9平方厘米。
## 课后练习
1. 第1题 寻找合适条件，计算涂色竖直直角梯形面积（左竖边6cm，右竖边10cm，水平高5cm）。
【答案】40平方厘米。
2. 第2题 亮亮做了一个V型槽放铅笔，第1层1根，顶层10根，一共多少根？
【答案】55根。
'''

with TestClient(app) as client:
    th, sh, sid, school = setup(client)
    imp = client.post(
        "/teacher/weekend/lessons/import/markdown",
        headers=th,
        data={"subject": "数学"},
        files={"files": ("lesson12.md", MD.encode("utf-8"), "text/markdown")},
    )
    assert imp.status_code == 200, imp.text
    lid = imp.json()["items"][0]["lessonId"]

    with legacy.SessionLocal() as db:
        tid = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        wt = register_written_tables(legacy)["questions"]
        rows = written_templates(db, wt, school, tid, lid)
        assert len(rows) == 2
        stems = [q.stem.split("\n\n")[-1].strip() for q in rows]
        # Question 1 has an uploaded figure on its written template;
        # Question 2 gets its initial diagram from approved stage-4 courseware stepFigures[0].
        meta0 = {**template_meta(rows[0]), "approved": True, "figure": {"type": "uploaded_image", "data_url": picture, "alt": "第1题梯形原图"}}
        meta1 = {**template_meta(rows[1]), "approved": True}
        db.execute(update(wt).where(wt.c.id == rows[0].id).values(hints_json=json.dumps(meta0, ensure_ascii=False)))
        db.execute(update(wt).where(wt.c.id == rows[1].id).values(hints_json=json.dumps(meta1, ensure_ascii=False)))
        # Ensure student is in teacher's class so student can view the session.
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school))
        cls.teacher_id = tid
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == sid))
        if link is None:
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid))
        else:
            link.class_id = cls.id
        db.commit()

    cw_pages = [
        {
            "stageNo": 4,
            "page": 1,
            "expectedPageText": stems[1],
            "kind": "steps",
            "params": {
                "problem": stems[1],
                "steps": ["找顶层和底层", "套用梯形面积公式"],
                "answer": "55根",
                "stepFigures": [
                    {"type": "uploaded_image", "data_url": picture, "alt": "V型槽初始题干图"},
                    {"type": "uploaded_image", "data_url": picture, "alt": "步骤1辅助图"},
                    {"type": "uploaded_image", "data_url": picture, "alt": "答案最终图"},
                ],
            },
            "writtenTask": False,
        }
    ]
    r_cw = client.post(f"/teacher/weekend/lessons/{lid}/courseware/prepared-import", headers=th, json={"dryRun": False, "pages": cw_pages})
    assert r_cw.status_code == 200, r_cw.text
    r_ap = client.post(f"/teacher/weekend/lessons/{lid}/courseware/approve", headers=th, json={"stageNo": 4, "page": 1})
    assert r_ap.status_code == 200, r_ap.text

    sess = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid})
    assert sess.status_code == 200, sess.text
    session_id = sess.json()["id"]
    base = f"/teacher/weekend/sessions/{session_id}"
    assert client.post(base + "/start", headers=th).status_code == 200
    assert client.post(base + "/goto", headers=th, json={"stage": 4}).status_code == 200

    # 1. Entering stage 4 reports currentOpen=False so control page renders the explicit Open button.
    st0 = client.get(base, headers=th).json()
    assert st0["answerRelease"]["currentQuestion"] == 1
    assert st0["answerRelease"]["currentOpen"] is False
    # Board shows question-1 figure during practice while keeping full solution courseware hidden.
    bd0 = client.get(base + "/board", headers=th).json()
    assert bd0.get("courseware") is None
    assert bd0.get("practiceFigure", {}).get("data_url") == picture

    # 2. Student cannot see question 1 before teacher clicks open.
    stu0 = client.get(f"/student/weekend/sessions/{session_id}/written", headers=sh).json()
    assert stu0["questions"] == []

    # 3. Teacher explicitly opens question 1 -> currentOpen=True and student sees question 1 WITH its figure.
    assert client.post(base + "/practice-question", headers=th, json={"question": 1}).status_code == 200
    st1 = client.get(base, headers=th).json()
    assert st1["answerRelease"]["currentOpen"] is True
    stu1 = client.get(f"/student/weekend/sessions/{session_id}/written", headers=sh).json()
    assert len(stu1["questions"]) == 1
    assert stu1["questions"][0]["figure"]["data_url"] == picture

    # 4. Teacher opens question 2 -> board & student get stepFigures[0] (question-only) without leaking answer/steps.
    assert client.post(base + "/practice-question", headers=th, json={"question": 2}).status_code == 200
    bd2 = client.get(base + "/board", headers=th).json()
    assert bd2.get("courseware") is None
    assert bd2.get("practiceFigure", {}).get("alt") == "V型槽初始题干图"
    assert "55根" not in json.dumps(bd2, ensure_ascii=False)
    stu2 = client.get(f"/student/weekend/sessions/{session_id}/written", headers=sh).json()
    assert len(stu2["questions"]) == 2
    assert stu2["questions"][1]["figure"]["alt"] == "V型槽初始题干图"
    assert "55根" not in json.dumps(stu2, ensure_ascii=False)

    # 5. Real HTML pages include the open button logic and figure renderers.
    control_html = client.get("/v1/weekend").text
    board_html = client.get("/v1/weekend-board").text
    student_html = client.get("/v1/weekend-practice").text
    assert "开放第 " in control_html and "renderQuestionFigure" in control_html
    assert "practiceFigure" in board_html and "renderQuestionFigure" in board_html
    assert "function cwFigure" in student_html and "renderQuestionFigure" in student_html
    assert "提交订正" in student_html
    print("OK")
""",
        {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    )


def test_teacher_revise_unlocks_student_revision_in_stage4_and_stage5(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r"""
with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=95, title="梯形订正闭环")
        db.add(l); db.flush(); lid = l.id
        tid = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id))
        cls.teacher_id = tid
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == student_id))
        if link is None:
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=student_id))
        else:
            link.class_id = cls.id
        db.commit()
    sid = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()["id"]
    base = f"/teacher/weekend/sessions/{sid}"
    student = f"/student/weekend/sessions/{sid}/written"
    q1 = client.post(base + "/written/questions", headers=th, json={"stem": "第1题 求梯形面积", "reference": "40平方厘米"}).json()["id"]
    assert client.post(base + "/start", headers=th).status_code == 200
    assert client.post(base + "/goto", headers=th, json={"stage": 4}).status_code == 200
    assert client.post(base + "/practice-question", headers=th, json={"question": 1}).status_code == 200

    # Student submits wrong answer, teacher publishes answer -> locked while still pending.
    s1 = client.post(f"{student}/{q1}", headers=sh, data={"text": "1"})
    assert s1.status_code == 200, s1.text
    sub_id = s1.json()["submission"]["id"]
    assert client.post(base + "/publish-answers", headers=th, json={"question": 1}).status_code == 200
    locked = client.get(student, headers=sh).json()
    assert locked["questions"][0]["canSubmit"] is False
    assert locked["questions"][0]["canRevise"] is False
    assert client.post(f"{student}/{q1}", headers=sh, data={"text": "偷改", "revision": 1}).status_code == 409

    # Teacher grades as 'revise' -> student can revise even after answer release in Stage 4.
    rev = client.post(base + "/written/review-batch", headers=th, json={"items": [{"id": sub_id, "revision": 1, "result": "revise", "comment": "请用梯形面积公式重算"}]})
    assert rev.status_code == 200, rev.text
    st4 = client.get(student, headers=sh).json()
    assert st4["canSubmit"] is True
    assert st4["questions"][0]["canSubmit"] is True
    assert st4["questions"][0]["canRevise"] is True

    # Moving to Stage 5 (练习复盘) still allows student to submit revision.
    assert client.post(base + "/goto", headers=th, json={"stage": 5}).status_code == 200
    st5 = client.get(student, headers=sh).json()
    assert st5["canSubmit"] is True
    assert st5["questions"][0]["canSubmit"] is True
    assert st5["questions"][0]["canRevise"] is True
    cur_rev = st5["questions"][0]["submission"]["revision"]
    s2 = client.post(f"{student}/{q1}", headers=sh, data={"text": "(6+10)*5/2=40平方厘米", "revision": cur_rev})
    assert s2.status_code == 200, s2.text
    assert s2.json()["attempts"] == 2
    assert s2.json()["result"] == "pending"

    # After submitting revision (now pending again), cannot keep editing until teacher reviews again.
    after = client.get(student, headers=sh).json()
    assert after["questions"][0]["canSubmit"] is False
    assert after["questions"][0]["canRevise"] is False
    print("OK")
""",
        {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    )
