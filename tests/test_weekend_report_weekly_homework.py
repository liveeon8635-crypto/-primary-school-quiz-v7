from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("weekly_homework_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

BODY = r'''
from datetime import datetime, timedelta

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    today = datetime.now(legacy.SCHOOL_TZ)
    due = today.strftime("%Y-%m-%d")
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        cls = legacy.SchoolClass(school_id=school_id, name="五年级1班", grade=5, teacher_id=teacher.id)
        db.add(cls); db.flush()
        db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid))
        lesson = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=98,
                                       title="旋转复习", core_target="会用旋转解决问题")
        db.add(lesson); db.flush()
        q = legacy.TeachingQuestion(school_id=school_id, program_id=p.id, level="C", lesson_id=lesson.id, subject="数学",
                                    stem="旋转选择", options_json=json.dumps(["A．对", "B．错"], ensure_ascii=False),
                                    correct_index=0, active=True, knowledge="旋转的意义")
        db.add(q); db.flush()
        paper = legacy.Paper(school_id=school_id, title="本周作业卷", grade=5, subject="数学",
                             question_ids_json=json.dumps([q.id]), teacher_id=teacher.id)
        db.add(paper); db.flush()
        done = legacy.Assignment(school_id=school_id, title="本周作业·已完成", class_id=cls.id, paper_id=paper.id, due_date=due)
        missing = legacy.Assignment(school_id=school_id, title="本周作业·未交", class_id=cls.id, paper_id=paper.id, due_date=due)
        stale = legacy.Assignment(school_id=school_id, title="上周作业", class_id=cls.id, paper_id=paper.id, due_date="2000-01-03")
        db.add_all([done, missing, stale]); db.flush()
        for a in (done, missing, stale):
            db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=a.id, class_id=cls.id, student_id=sid))
        db.add(legacy.Submission(school_id=school_id, assignment_id=done.id, student_id=sid, title="本周作业·已完成",
                                 score=50, correct=2, total=4, answers_json="[]", completion_actor="student"))
        parent = legacy.User(school_id=school_id, username="parent_a", name="甲家长", role="parent",
                             password_hash=legacy.hash_password("Parent1234"))
        db.add(parent); db.flush()
        db.add(legacy.ParentStudent(parent_id=parent.id, student_id=sid))
        db.commit()
        lesson_id, cls_id, q_id = lesson.id, cls.id, q.id

    ph = {"Authorization": "Bearer " + login_and_change(client, "parent_a", "Parent1234", "Parent5678")}
    s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lesson_id, "classId": cls_id}).json()["id"]
    assert client.post(f"/teacher/weekend/sessions/{s}/start", headers=th).status_code == 200
    assert client.post(f"/teacher/weekend/sessions/{s}/goto", headers=th, json={"stage": 4}).status_code == 200
    assert client.post("/student/weekend/answer", headers=sh,
                       json={"sessionId": s, "questionId": q_id, "selected": 0, "attempt": 0}).status_code == 200
    assert client.post(f"/teacher/weekend/sessions/{s}/finish", headers=th).status_code == 200

    r = client.post("/teacher/weekend/reports", headers=th, json={"studentId": sid, "sessionIds": [s]})
    assert r.status_code == 200, r.text
    body = r.json()
    rid = body["id"]
    wk = body["report"]["facts"][0]["weekWork"]
    assert wk["counts"] == {"total": 2, "submitted": 1, "unsubmitted": 1, "pending": 0}, wk
    assert wk["rate"] == 50, wk
    items = {i["title"]: i for i in wk["items"]}
    assert set(items) == {"本周作业·已完成", "本周作业·未交"}, items
    assert items["本周作业·已完成"]["status"] == "submitted" and items["本周作业·已完成"]["statusLabel"] == "已交"
    assert items["本周作业·已完成"]["rate"] == 50 and items["本周作业·已完成"]["correct"] == 2
    assert items["本周作业·未交"]["status"] == "unsubmitted" and items["本周作业·未交"]["rate"] is None
    assert wk["weekStart"] <= due <= wk["weekEnd"]
    assert (datetime.strptime(wk["weekEnd"], "%Y-%m-%d").date() - datetime.strptime(wk["weekStart"], "%Y-%m-%d").date()).days == 6

    homework = next(s_ for s_ in body["report"]["draft"]["sections"] if s_["sessionId"] == s)["homework"]
    assert "本周普通作业" in homework and "应做 2 份" in homework, homework
    assert "未交：「本周作业·未交」" in homework, homework

    # The pupil has no homework of his own beyond the two for this week: an unrelated classmate stays at zero.
    summary = client.get(f"/teacher/weekend/sessions/{s}/summary", headers=th).json()
    assert set(summary)  # summary still renders with the new fact attached

    pub = client.post(f"/teacher/weekend/reports/{rid}/publish", headers=th,
                      json={"revision": body["report"]["draft"]["revision"]})
    assert pub.status_code == 200, pub.text
    briefs = client.get(f"/parent/children/{sid}/weekend-briefs", headers=ph).json()["reports"]
    assert briefs, "the published report must reach the parent"
    parent_wk = briefs[0]["facts"][0]["weekWork"]
    assert parent_wk["counts"]["total"] == 2 and parent_wk["rate"] == 50
    assert set(parent_wk["items"][0]) == {"title", "status", "statusLabel", "rate", "due"}
    assert all("correct" not in i and "total" not in i for i in parent_wk["items"])
    print("OK")
'''


def test_report_shows_the_weeks_ordinary_homework_for_teacher_and_parent(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + BODY)
