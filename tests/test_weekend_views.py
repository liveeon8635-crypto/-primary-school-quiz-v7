from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

from changying.services.weekend_stages import STAGES, remaining_seconds, stage_content

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hw_solve_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules["hw_solve_helpers"] = helpers
spec.loader.exec_module(helpers)


def test_template_is_120_minutes_in_seven_stages():
    assert len(STAGES) == 7 and sum(s["minutes"] for s in STAGES) == 120


def test_remaining_seconds_counts_down_and_goes_negative_on_overtime():
    t0 = datetime(2026, 1, 1, 9, 0, 0)
    assert remaining_seconds(10, 0, t0, t0 + timedelta(minutes=4)) == 360
    assert remaining_seconds(10, 5, t0, t0 + timedelta(minutes=4)) == 660
    assert remaining_seconds(10, 0, t0, t0 + timedelta(minutes=12)) == -120
    assert remaining_seconds(10, 0, None, t0) == 600


def test_stage_content_comes_from_the_lesson_plan():
    lesson = {"title": "分数", "core_target": "理解分数", "teacher_plan": "先讲定义", "ppt_json": '["封面","定义"]',
              "examples_json": '[{"title":"例1","answer":"1/2"}]', "closure_training": "做练习册 P12"}
    assert stage_content(2, lesson)[:2] == ["理解分数", "先讲定义"]
    assert stage_content(3, lesson) == ["例1 1/2"]
    assert stage_content(7, lesson) == ["做练习册 P12"]


def test_session_flow_timer_cover_and_isolation(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=99, title="分数初步",
                                  core_target="理解分数", examples_json=json.dumps(["例1：1/2"], ensure_ascii=False))
        db.add(l); db.commit(); lid = l.id

    assert client.get("/v1/weekend").status_code == 200 and client.get("/v1/weekend-board").status_code == 200
    assert client.get("/teacher/weekend/lessons", headers=sh).status_code == 403

    d = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()
    s = d["id"]; base = f"/teacher/weekend/sessions/{s}"
    assert d["status"] == "planned" and d["content"] == [] and len(d["stages"]) == 7
    assert client.post(base + "/next", headers=th).status_code == 409        # not started

    d = client.post(base + "/start", headers=th).json()
    assert d["status"] == "running" and d["currentStage"] == 1 and 590 <= d["remainingSeconds"] <= 600
    d = client.post(base + "/next", headers=th).json()
    assert d["currentStage"] == 2 and d["content"][0] == "理解分数"
    d = client.post(base + "/goto", headers=th, json={"stage": 3}).json()
    assert d["stageName"] == "例题讲解" and d["content"] == ["例1：1/2"]
    d = client.post(base + "/extend", headers=th, json={"minutes": 5}).json()
    assert 29 * 60 <= d["remainingSeconds"] <= 30 * 60
    assert client.post(base + "/goto", headers=th, json={"stage": 9}).status_code == 400

    # cover hides the content from the board but not from the control panel's stage state
    board = client.post(base + "/cover", headers=th, json={"covered": True}).json()
    assert board["covered"] is True
    assert client.get(base + "/board", headers=th).json()["content"] == []
    client.post(base + "/cover", headers=th, json={"covered": False})
    assert client.get(base + "/board", headers=th).json()["content"] == ["例1：1/2"]

    # timeline: every visited stage is logged
    d = client.get(base, headers=th).json()
    assert [x["visited"] for x in d["stages"]] == [True, True, True, False, False, False, False]
    assert d["stages"][2]["extendMin"] == 5

    d = client.post(base + "/goto", headers=th, json={"stage": 7}).json()
    d = client.post(base + "/next", headers=th).json()                         # past the last stage -> finish
    assert d["status"] == "finished" and d["remainingSeconds"] is None
    assert client.post(base + "/next", headers=th).status_code == 409

    # another teacher cannot see it
    from sqlalchemy import update
    with legacy.SessionLocal() as db:
        db.execute(update(legacy.Base.metadata.tables["weekend_sessions"]).where(legacy.Base.metadata.tables["weekend_sessions"].c.id == s).values(teacher_id=999999))
        db.commit()
    assert client.get(base, headers=th).status_code == 404
    print("OK")
''',
    )


def test_practice_hints_answers_and_progress(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
HINTS = json.dumps({"levels": ["想想分母表示什么", "先把两个分数通分", "通分后相加得 3/4，选 B"]}, ensure_ascii=False)
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=98, title="通分")
        db.add(l); db.flush()
        q1 = legacy.TeachingQuestion(school_id=school_id, program_id=p.id, lesson_id=l.id, stage="lesson", subject="数学", level="C", knowledge="通分",
                                     stem="1/2+1/4=?", options_json=json.dumps(["1/6", "3/4", "2/6"]), correct_index=1, explanation="通分再加")
        q2 = legacy.TeachingQuestion(school_id=school_id, program_id=p.id, lesson_id=l.id, stage="lesson", subject="数学", level="C", knowledge="通分",
                                     stem="1/3+1/3=?", options_json=json.dumps(["2/3", "2/6"]), correct_index=0, explanation="同分母")
        db.add_all([q1, q2]); db.commit(); lid, a, b = l.id, q1.id, q2.id
        teacher_id = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id))
        cls.teacher_id = teacher_id; db.commit()
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == sid))
        if link is None:
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid)); db.commit()
        else:
            link.class_id = cls.id; db.commit()

    s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()["id"]
    base = f"/teacher/weekend/sessions/{s}"
    assert client.get("/v1/weekend-practice").status_code == 200

    # nothing running -> student sees a message, not questions
    assert client.get("/student/weekend/current", headers=sh).json() == {"active": False, "message": "现在没有正在上的课"}
    client.post(base + "/start", headers=th)
    cur = client.get("/student/weekend/current", headers=sh).json()
    assert cur["active"] and cur["practice"] is False and "questions" not in cur
    assert client.post("/student/weekend/hint", headers=sh, json={"sessionId": s, "questionId": a}).status_code == 409

    # teacher drafts hints; students cannot see drafts as approved, but 'approve' makes them official
    qs = client.get(base + "/questions", headers=th).json()["items"]
    assert [x["hintStatus"] for x in qs] == ["none", "none"] and qs[0]["levelNames"] == ["思考方向", "第一步", "完整讲解"]
    replies.append(HINTS)
    g = client.post("/teacher/weekend/hints/generate", headers=th, json={"questionId": a}).json()
    assert g["hintStatus"] == "draft" and len(g["hints"]) == 3 and calls[-1]["feature"] == "weekend_hint"
    assert client.put(f"/teacher/weekend/hints/{a}", headers=th, json={"levels": ["x", "y", ""], "approve": True}).status_code == 400
    assert client.put(f"/teacher/weekend/hints/{a}", headers=th, json={"levels": g["hints"], "approve": True}).json()["hintStatus"] == "approved"

    client.post(base + "/goto", headers=th, json={"stage": 4})
    cur = client.get("/student/weekend/current", headers=sh).json()
    assert cur["practice"] and [x["id"] for x in cur["questions"]] == [a, b] and "correctIndex" not in cur["questions"][0]

    # three hint levels, in order, then no more; the third is only reachable after the first two
    h = [client.post("/student/weekend/hint", headers=sh, json={"sessionId": s, "questionId": a}).json() for _ in range(3)]
    assert [x["level"] for x in h] == [1, 2, 3] and h[0]["text"] == "想想分母表示什么" and h[2]["last"] is True
    assert client.post("/student/weekend/hint", headers=sh, json={"sessionId": s, "questionId": a}).status_code == 409
    assert client.get("/student/weekend/current", headers=sh).json()["questions"][0]["hintTexts"][1] == "先把两个分数通分"

    # one recorded attempt per question; hint level is stored with the answer
    r = client.post("/student/weekend/answer", headers=sh, json={"sessionId": s, "questionId": a, "selected": 1}).json()
    assert r["correct"] is True and r["hintUsed"] == 3 and r["explanation"] == "通分再加"
    assert client.post("/student/weekend/answer", headers=sh, json={"sessionId": s, "questionId": a, "selected": 0}).status_code == 409
    assert client.post("/student/weekend/answer", headers=sh, json={"sessionId": s, "questionId": b, "selected": 7}).status_code == 400

    # a question without approved hints: AI writes them on the spot ("auto"); an AI failure records nothing
    replies.append("not json")
    assert client.post("/student/weekend/hint", headers=sh, json={"sessionId": s, "questionId": b}).status_code == 502
    replies.append(HINTS)
    first = client.post("/student/weekend/hint", headers=sh, json={"sessionId": s, "questionId": b}).json()
    assert first["level"] == 1
    assert client.get(base + "/questions", headers=th).json()["items"][1]["hintStatus"] == "auto"
    r = client.post("/student/weekend/answer", headers=sh, json={"sessionId": s, "questionId": b, "selected": 1}).json()
    assert r["correct"] is False and r["hintUsed"] == 1

    # progress: completion counts correct answers; hint use is visible to the teacher
    p = client.get(base + "/progress", headers=th).json()
    me = [i for i in p["items"] if i["studentId"] == sid][0]
    assert me["answered"] == 2 and me["correct"] == 1 and me["completionRate"] == 50 and me["hintMax"] == 3 and me["hintAvg"] == 2.0

    # the big screen shows the question stems (no options, no answers) during 随堂练习
    client.post(base + "/goto", headers=th, json={"stage": 4})
    shown = client.get(base + "/board", headers=th).json()["content"]
    assert shown[-2:] == ["1. 1/2+1/4=?", "2. 1/3+1/3=?"] and not any("3/4" in x for x in shown)

    # outside the practice stage students can neither ask for hints nor answer
    client.post(base + "/goto", headers=th, json={"stage": 5})
    assert client.post("/student/weekend/answer", headers=sh, json={"sessionId": s, "questionId": a, "selected": 0}).status_code == 409
    assert client.get("/teacher/weekend/sessions/%d/progress" % s, headers=sh).status_code == 403
    print("OK")
''',
    )
