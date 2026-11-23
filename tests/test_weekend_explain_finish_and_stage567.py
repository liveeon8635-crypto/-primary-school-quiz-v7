"""Regression tests for explain finish/evaluation/points and Stage 5-7 student sync."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("explain_stage567_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_explain_finish_evaluation_and_stage567_student_sync(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r"""
with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(
            school_id=school_id,
            program_id=p.id,
            subject="数学",
            lesson_no=96,
            title="梯形复盘与收口",
            core_target="掌握梯形面积并完成互查",
            closure_training="1. 互查演练：核查高是否垂直。\n2. 课后任务：完成错题订正。",
        )
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
    assert client.post(f"{student}/{q1}", headers=sh, data={"text": "40平方厘米"}).status_code == 200

    # Move to stage 5 and invite student to explain.
    assert client.post(base + "/goto", headers=th, json={"stage": 5}).status_code == 200
    inv = client.post(base + "/explain", headers=th, json={"tutorId": student_id, "questionId": q1, "questionType": "written"})
    assert inv.status_code == 200, inv.text
    bd_during = client.get(base + "/board", headers=th).json()
    assert any("同学来讲" in line for line in bd_during["content"])

    # Student declines -> board hides prompt; then student accepts -> board shows prompt again.
    dec = client.post("/student/weekend/explain/respond", headers=sh, json={"sessionId": sid, "questionId": q1, "questionType": "written", "decision": "decline"})
    assert dec.status_code == 200, dec.text
    assert not any("同学来讲" in line for line in client.get(base + "/board", headers=th).json()["content"])
    acc = client.post("/student/weekend/explain/respond", headers=sh, json={"sessionId": sid, "questionId": q1, "questionType": "written", "decision": "accept"})
    assert acc.status_code == 200, acc.text
    assert any("同学来讲" in line for line in client.get(base + "/board", headers=th).json()["content"])

    # Finish explanation with rating & comment -> board clears invitation, teacher & student see review + points, and settle-preview includes the points.
    fin = client.post(
        base + "/explain/finish",
        headers=th,
        json={"tutorId": student_id, "questionId": q1, "questionType": "written", "rating": "clear", "comment": "步骤完整，表达清楚"},
    )
    assert fin.status_code == 200, fin.text
    assert fin.json()["finished"] is True
    assert fin.json()["review"]["points"] == 2
    assert fin.json()["review"]["label"] == "思路清晰"

    bd_after = client.get(base + "/board", headers=th).json()
    assert not any("同学来讲" in line for line in bd_after["content"])

    stu_exp = client.get("/student/weekend/explain", headers=sh).json()["items"]
    assert len(stu_exp) == 1
    assert stu_exp[0]["explainReview"]["finished"] is True
    assert stu_exp[0]["explainReview"]["points"] == 2
    assert stu_exp[0]["explainReview"]["comment"] == "步骤完整，表达清楚"
    assert stu_exp[0]["explainResponse"]["decision"] == "accept"

    sug = client.get(base + "/peer-suggest", headers=th).json()["questions"]
    assert sug[0]["submitted"][0]["explainReview"]["finished"] is True

    # Settle preview must include teacher-evaluated explain points in tutor parts and why.tutor.explained!
    pre = client.get(base + "/settle-preview", headers=th).json()
    me = next(x for x in pre["items"] if x["studentId"] == student_id)
    assert me["parts"]["tutor"] >= 2 and me["total"] >= 2
    assert me["why"]["tutor"]["explained"][0]["points"] == 2
    assert me["why"]["tutor"]["explained"][0]["label"] == "思路清晰"

    # Stage 5, 6, 7 student sync returns distinct stage content and Stage 7 homeworkUrl.
    c5 = client.get("/student/weekend/current", headers=sh).json()
    assert c5["stage"] == 5 and "练习复盘" in c5["message"]
    assert client.post(base + "/goto", headers=th, json={"stage": 6}).status_code == 200
    c6 = client.get("/student/weekend/current", headers=sh).json()
    assert c6["stage"] == 6 and c6["message"] != c5["message"] and bool(c6.get("stageContent"))
    assert client.post(base + "/goto", headers=th, json={"stage": 7}).status_code == 200
    c7 = client.get("/student/weekend/current", headers=sh).json()
    assert c7["stage"] == 7 and c7.get("homeworkUrl") == "/v1"
    assert any("互查演练" in x for x in c7.get("stageContent") or [])

    # Real HTML checks.
    control_html = client.get("/v1/weekend").text
    practice_html = client.get("/v1/weekend-practice").text
    assert "/explain/finish" in control_html
    assert "按学生作答生成并布置个性化课后练习" in control_html
    assert "前往首页“作业”查看专属课后练习" in practice_html
    assert "本次讲题已完成" in practice_html
    assert "lastExplainSignature" in practice_html
    assert "我来讲（同意）" in practice_html and "暂不讲解（拒绝）" in practice_html
    print("OK")
""",
        {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    )
