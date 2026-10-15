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
    assert r["submitted"] is True and r["hintUsed"] == 3 and "correctIndex" not in r and "explanation" not in r and "correct" not in r
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
    assert r["submitted"] is True and r["hintUsed"] == 1 and "correct" not in r

    # progress: completion counts correct answers; hint use is visible to the teacher
    p = client.get(base + "/progress", headers=th).json()
    me = [i for i in p["items"] if i["studentId"] == sid][0]
    assert me["answered"] == 2 and me["correct"] == 1 and me["completionRate"] == 50 and me["hintMax"] == 3 and me["hintAvg"] == 2.0

    # Question and answer decks are controlled independently; reading/turning question pages never publishes.
    client.post(base + "/goto", headers=th, json={"stage": 4})
    shown = client.get(base + "/board", headers=th).json()
    assert not shown['answersPublished'] and shown['deck']['total'] == 2
    assert '1/2+1/4=?' in shown['content'][-1] and '解析：' not in str(shown)
    turned = client.post(base+'/slide', headers=th, json={'delta':1}).json()
    assert not turned['answersPublished'] and turned['deck']['index'] == 1
    assert '1/3+1/3=?' in turned['content'][-1]
    submitted = client.get('/student/weekend/current', headers=sh).json()
    assert all('correctIndex' not in q and 'correct' not in q and 'explanation' not in q for q in submitted['questions'])
    assert client.post(base+'/publish-answers', headers=sh, json={'question':1}).status_code == 403
    revealed = client.post(base+'/publish-answers', headers=th, json={'question':1}).json()
    assert not revealed['answersPublished'] and revealed['answerRelease']['published'] == 1 and revealed['deck']['index'] == 0
    assert '正确答案：B. 3/4' in revealed['content'][-1] and '通分再加' in revealed['content'][-1]
    board = client.get(base+'/board', headers=th).json()
    assert board['content'] == revealed['content']
    assert client.get('/student/weekend/current', headers=sh).json()['canSubmit'] is True
    assert client.post('/student/weekend/answer', headers=sh, json={'sessionId':s,'questionId':a,'selected':0}).status_code == 409
    assert client.post('/student/weekend/hint', headers=sh, json={'sessionId':s,'questionId':a}).status_code == 409
    next_page = client.post(base+'/slide', headers=th, json={'delta':1}).json()
    assert '正确答案：' not in next_page['content'][-1]
    assert '正确答案：A. 2/3' in client.post(base+'/publish-answers', headers=th, json={'question':2}).json()['content'][-1]
    assert client.get('/student/weekend/current', headers=sh).json()['canSubmit'] is False
    assert client.post(base+'/publish-answers', headers=th, json={'question':1}).json()['deck']['index'] == 1  # idempotent
    client.post(base+'/cover', headers=th, json={'covered':True})
    assert client.get(base+'/board', headers=th).json()['content'] == []
    client.post(base+'/cover', headers=th, json={'covered':False})

    # outside the practice stage students can neither ask for hints nor answer
    client.post(base + "/goto", headers=th, json={"stage": 5})
    assert client.post("/student/weekend/answer", headers=sh, json={"sessionId": s, "questionId": a, "selected": 0}).status_code == 409
    assert client.get("/teacher/weekend/sessions/%d/progress" % s, headers=sh).status_code == 403
    print("OK")
''',
    )


def test_peer_help_followup_and_settlement(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
FOLLOW = json.dumps({"stem": "2/4 约分后是？", "options": ["1/2", "1/3", "2/3"], "correctIndex": 0, "explanation": "同除 2"}, ensure_ascii=False)
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=97, title="约分")
        db.add(l); db.flush()
        q = legacy.TeachingQuestion(school_id=school_id, program_id=p.id, lesson_id=l.id, stage="lesson", subject="数学", level="C", knowledge="约分",
                                    stem="4/8 约分？", options_json=json.dumps(["1/2", "1/4"]), correct_index=0)
        db.add(q); db.commit(); lid, qid = l.id, q.id
        teacher_id = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id)); cls.teacher_id = teacher_id
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == sid))
        if link is None: db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid))
        else: link.class_id = cls.id
        # a second pupil in the same class: the "strong" one
        strong = legacy.User(school_id=school_id, username="strong1", password_hash=legacy.hash_password("x"), name="小强", role="student", grade=3)
        db.add(strong); db.flush(); db.add(legacy.ClassStudent(class_id=cls.id, student_id=strong.id)); db.commit(); strong_id = strong.id

    s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()["id"]
    base = f"/teacher/weekend/sessions/{s}"
    client.post(base + "/start", headers=th); client.post(base + "/goto", headers=th, json={"stage": 4})
    with legacy.SessionLocal() as db:
        t = legacy.Base.metadata.tables["weekend_answers"]
        from sqlalchemy import insert
        from datetime import datetime
        db.execute(insert(t).values(school_id=school_id, session_id=s, student_id=strong_id, question_id=qid, selected=0, correct=True, max_hint=0, created_at=datetime.utcnow()))
        db.execute(insert(t).values(school_id=school_id, session_id=s, student_id=sid, question_id=qid, selected=1, correct=False, max_hint=2, created_at=datetime.utcnow()))
        db.commit()

    sug = client.get(base + "/peer-suggest", headers=th).json()
    assert sug["mode"] == "peer" and len(sug["questions"]) == 1
    sq = sug["questions"][0]
    assert sq["questionId"] == qid and [x["studentId"] for x in sq["right"]] == [strong_id] and [x["studentId"] for x in sq["wrong"]] == [sid]
    assert client.get(base + "/peer-suggest", headers=sh).status_code == 403          # students never see who is "strong"

    # pairing rules
    bad = client.post(base + "/peer-help", headers=th, json={"tutorId": sid, "tuteeId": strong_id, "questionId": qid})
    assert bad.status_code == 400                                                        # the tutor must have it right
    replies.append(FOLLOW)
    ok = client.post(base + "/peer-help", headers=th, json={"tutorId": strong_id, "tuteeId": sid, "questionId": qid}).json()
    assert ok["followup"] is True
    assert client.post(base + "/peer-help", headers=th, json={"tutorId": strong_id, "tuteeId": sid, "questionId": qid}).status_code == 409

    # the tutee sees a follow-up question (no answer in it) and answers it
    f = client.get("/student/weekend/followup", headers=sh).json()
    assert f["active"] and f["stem"] == "2/4 约分后是？" and "correctIndex" not in f
    r = client.post("/student/weekend/followup", headers=sh, json={"peerHelpId": f["peerHelpId"], "selected": 0}).json()
    assert r["correct"] is True
    assert client.post("/student/weekend/followup", headers=sh, json={"peerHelpId": f["peerHelpId"], "selected": 0}).status_code == 409
    assert client.get("/student/weekend/followup", headers=sh).json() == {"active": False}

    # preview writes nothing; settle writes once, to the points ledger, with reasons
    assert client.get(base + "/settle-preview", headers=th).json()["pendingFollowups"] == 0     # the follow-up above was answered
    pv = client.get(base + "/settle-preview", headers=th).json()
    assert pv["settled"] is False
    by = {i["studentId"]: i for i in pv["items"]}
    assert by[strong_id]["parts"]["tutor"] == 2 and by[strong_id]["parts"]["completion"] == 2       # 100% completion, tutee learned
    assert by[sid]["parts"]["progress"] == 0 and "首次课" in by[sid]["why"]["progress"]["reason"]    # first lesson: no baseline
    assert pv["teamPoints"] == 0                                                                    # first lesson: no previous rate
    with legacy.SessionLocal() as db:
        assert db.scalar(select(legacy.PointLedger.id).where(legacy.PointLedger.category.like("weekend_%"))) is None
    done = client.post(base + "/settle", headers=th).json()
    assert done["settled"] is True
    assert client.post(base + "/settle", headers=th).status_code == 409
    with legacy.SessionLocal() as db:
        rows = db.scalars(select(legacy.PointLedger).where(legacy.PointLedger.category.like("weekend_%"))).all()
        assert sorted((r.student_id, r.category, r.points) for r in rows) == sorted([(strong_id, "weekend_tutor", 2), (strong_id, "weekend_completion", 2)])
        assert all(r.source == "classroom" and r.related_id == s for r in rows)

    # AI failure on pairing: no follow-up, the teacher records the result by hand
    s2 = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()["id"]
    b2 = f"/teacher/weekend/sessions/{s2}"
    client.post(b2 + "/start", headers=th)
    with legacy.SessionLocal() as db:
        t = legacy.Base.metadata.tables["weekend_answers"]
        db.execute(insert(t).values(school_id=school_id, session_id=s2, student_id=strong_id, question_id=qid, selected=0, correct=True, max_hint=0, created_at=datetime.utcnow()))
        db.execute(insert(t).values(school_id=school_id, session_id=s2, student_id=sid, question_id=qid, selected=1, correct=False, max_hint=3, created_at=datetime.utcnow()))
        db.commit()
    replies.append("not json")
    p2 = client.post(b2 + "/peer-help", headers=th, json={"tutorId": strong_id, "tuteeId": sid, "questionId": qid}).json()
    assert p2["followup"] is False
    assert client.post(f"/teacher/weekend/peer-help/{p2['id']}/result", headers=th, json={"correct": True}).json()["followupCorrect"] is True
    pv2 = client.get(b2 + "/settle-preview", headers=th).json()
    assert pv2["prevPostRate"] is not None and pv2["items"]
    print("OK")
''',
    )


def test_unanswered_questions_count_as_not_done(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
from datetime import datetime
from sqlalchemy import insert
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=96, title="三题")
        db.add(l); db.flush()
        ids = []
        for i in range(3):
            q = legacy.TeachingQuestion(school_id=school_id, program_id=p.id, lesson_id=l.id, stage="lesson", subject="数学", level="C", knowledge="k",
                                        stem=f"q{i}", options_json=json.dumps(["a", "b"]), correct_index=0)
            db.add(q); db.flush(); ids.append(q.id)
        teacher_id = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id)); cls.teacher_id = teacher_id
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == sid))
        if link is None: db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid))
        else: link.class_id = cls.id
        db.commit(); lid = l.id
    s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()["id"]
    base = f"/teacher/weekend/sessions/{s}"
    client.post(base + "/start", headers=th)
    with legacy.SessionLocal() as db:
        t = legacy.Base.metadata.tables["weekend_answers"]
        db.execute(insert(t).values(school_id=school_id, session_id=s, student_id=sid, question_id=ids[0], selected=0, correct=True, max_hint=0, created_at=datetime.utcnow()))
        db.commit()
    pv = client.get(base + "/settle-preview", headers=th).json()
    assert pv["preRate"] == 33.3 and pv["items"][0]["parts"]["completion"] == 0           # 1 of 3 done: no completion bonus
    assert client.get(base + "/peer-suggest", headers=th).json()["mode"] != "challenge"     # not "everyone is all-correct"
    print("OK")
''',
    )


def test_archive_briefs_parent_and_term_summary(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
from datetime import datetime
from sqlalchemy import insert
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=95, title="通分")
        db.add(l); db.flush()
        qs = []
        for i in range(2):
            q = legacy.TeachingQuestion(school_id=school_id, program_id=p.id, lesson_id=l.id, stage="lesson", subject="数学", level="C", knowledge="通分",
                                        stem=f"q{i}", options_json=json.dumps(["a", "b"]), correct_index=0)
            db.add(q); db.flush(); qs.append(q.id)
        teacher_id = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id)); cls.teacher_id = teacher_id
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == sid))
        if link is None: db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid))
        else: link.class_id = cls.id
        parent = legacy.User(school_id=school_id, username="parent95", password_hash=legacy.hash_password("Parent1234"), name="家长", role="parent")
        other = legacy.User(school_id=school_id, username="parent96", password_hash=legacy.hash_password("Parent1234"), name="别的家长", role="parent")
        db.add_all([parent, other]); db.flush()
        db.add(legacy.ParentStudent(parent_id=parent.id, student_id=sid)); db.commit(); lid = l.id
    s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()["id"]
    base = f"/teacher/weekend/sessions/{s}"
    client.post(base + "/start", headers=th); client.post(base + "/next", headers=th)
    with legacy.SessionLocal() as db:
        t = legacy.Base.metadata.tables["weekend_answers"]
        db.execute(insert(t).values(school_id=school_id, session_id=s, student_id=sid, question_id=qs[0], selected=0, correct=True, max_hint=1, created_at=datetime.utcnow()))
        db.execute(insert(t).values(school_id=school_id, session_id=s, student_id=sid, question_id=qs[1], selected=1, correct=False, max_hint=0, created_at=datetime.utcnow()))
        db.commit()
    client.post(base + "/finish", headers=th)

    a = client.get(base + "/archive", headers=th).json()
    assert a["status"] == "finished" and a["attendance"] == {"present": 1, "total": 1} and [x["stage"] for x in a["timeline"]] == [1, 2]
    me = a["students"][0]
    assert me["correct"] == 1 and me["total"] == 2 and me["wrongKnowledge"] == ["通分"] and me["hintAvg"] == 1.0
    assert client.get(base + "/archive", headers=sh).status_code == 403

    d = client.get(base + "/briefs", headers=th).json()["items"][0]
    assert "1/2" in d["text"] and "通分" in d["text"] and d["published"] is False
    assert "排名" not in d["text"] and "第" not in d["text"].split("：")[-1]          # never a ranking

    # a parent sees nothing until the teacher publishes; only the linked parent ever sees it
    def parent_headers(user):
        return {"Authorization": "Bearer " + login_and_change(client, user, "Parent1234", "Parent5678")}
    ph, oh = parent_headers("parent95"), parent_headers("parent96")
    r0 = client.get(f"/parent/children/{sid}/weekend-briefs", headers=ph); assert r0.status_code == 200, (r0.status_code, r0.text)
    assert r0.json()["items"] == []
    edited = "老师改过的一段话"
    assert client.post(base + "/briefs/publish", headers=th, json={"texts": {str(sid): edited}}).json() == {"published": 1}
    got = client.get(f"/parent/children/{sid}/weekend-briefs", headers=ph).json()
    assert got["items"][0]["text"] == edited and got["childName"]
    assert client.get(f"/parent/children/{sid}/weekend-briefs", headers=oh).status_code == 404
    assert client.get(f"/parent/children/{sid}/weekend-briefs", headers=sh).status_code == 403

    ts = client.get("/teacher/weekend/term-summary?subject=数学", headers=th).json()
    assert ts["lessons"] == 1 and ts["students"][0]["attended"] == 1 and ts["students"][0]["trend"][0]["completionRate"] == 50
    print("OK")
''',
    )


def test_schedule_shift_ai_lesson_draft_and_question_approval(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
DRAFT = json.dumps({
    "title": "分数的约分", "coreTarget": "会约分", "teacherPlan": "先复习公因数，再约分", "ppt": ["封面", "公因数", "约分"], "examples": ["例1：12/18 约分得 2/3"],
    "closureTraining": "练习册 P30",
    "questions": [
        {"stem": "6/9 约分后是？", "options": ["2/3", "3/4", "1/2"], "correctIndex": 0, "explanation": "同除 3", "knowledge": "约分"},
        {"stem": "坏题没有答案", "options": ["a"], "correctIndex": 5},
        {"stem": "8/12 约分后是？", "options": ["2/3", "1/2", "3/4"], "correctIndex": 0, "explanation": "同除 4", "knowledge": "约分"},
    ]}, ensure_ascii=False)
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    assert client.get("/v1/weekend-plan").status_code == 200
    assert client.get("/teacher/weekend/schedule", headers=sh).status_code == 403
    assert client.get("/teacher/weekend/schedule?subject=英语", headers=th).status_code == 400

    s = client.get("/teacher/weekend/schedule?subject=数学", headers=th).json()
    assert len(s["items"]) == 18
    # the school's seeded template lessons are blank: they must not show up as "has a plan"
    assert s["items"][0]["lessonId"] is not None and s["items"][0]["hasPlan"] is False

    # save the school's progress, then the school postpones everything from lesson 3 by two weeks
    rows = [{"lessonNo": 1, "schoolWeek": 1, "schoolUnit": "分数的意义", "plannedDate": "2026-09-05"},
            {"lessonNo": 3, "schoolWeek": 3, "schoolUnit": "约分", "plannedDate": "2026-09-19"},
            {"lessonNo": 4, "schoolWeek": 4, "schoolUnit": "通分", "plannedDate": "not a date"}]
    saved = client.put("/teacher/weekend/schedule", headers=th, json={"subject": "数学", "rows": rows}).json()["items"]
    assert saved[3]["plannedDate"] == "" and saved[2]["schoolUnit"] == "约分"                        # an invalid date is dropped, not stored
    assert client.put("/teacher/weekend/schedule", headers=th, json={"subject": "数学", "rows": [{"lessonNo": 19}]}).status_code == 400
    assert client.post("/teacher/weekend/schedule/shift", headers=th, json={"subject": "数学", "fromLessonNo": 3, "weeks": 2}).json() == {"moved": 2}
    after = client.get("/teacher/weekend/schedule?subject=数学", headers=th).json()["items"]
    assert (after[0]["schoolWeek"], after[0]["plannedDate"]) == (1, "2026-09-05")                       # before the shift: untouched
    assert (after[2]["schoolWeek"], after[2]["plannedDate"]) == (5, "2026-10-03")

    # AI reads a pasted progress table; nothing is saved by this call
    replies.append(json.dumps({"rows": [{"schoolWeek": 1, "schoolUnit": "单元一"}, {"schoolWeek": "x", "schoolUnit": "单元二"}]}, ensure_ascii=False))
    parsed = client.post("/teacher/weekend/schedule/parse", headers=th, json={"subject": "数学", "text": "第1周 单元一"}).json()
    assert parsed["rows"][1] == {"lessonNo": 2, "schoolWeek": None, "schoolUnit": "单元二"}
    assert client.get("/teacher/weekend/schedule?subject=数学", headers=th).json()["items"][1]["schoolUnit"] == ""
    replies.append("garbage")
    assert client.post("/teacher/weekend/schedule/parse", headers=th, json={"subject": "数学", "text": "x"}).status_code == 502

    # AI lesson draft: lesson unpublished, only valid questions kept, all inactive until approved
    replies.append(DRAFT)
    dr = client.post("/teacher/weekend/lessons/draft", headers=th, json={"subject": "数学", "lessonNo": 17}); assert dr.status_code == 200, dr.text
    d = dr.json()
    lid = d["lessonId"]
    assert d["status"]["hasPlan"] and d["status"]["approvedQuestions"] == 0 and d["status"]["draftQuestions"] == 2
    assert "第 17 次课" in prompts[-1]
    with legacy.SessionLocal() as db:
        l = db.get(legacy.TeachingLesson, lid)
        assert l.published is False and l.title == "分数的约分" and l.lesson_no == 17
    assert client.post("/teacher/weekend/lessons/draft", headers=th, json={"subject": "数学", "lessonNo": 17}).status_code == 409      # no silent overwrite
    qs = client.get(f"/teacher/weekend/lessons/{lid}/questions", headers=th).json()["items"]
    assert [q["active"] for q in qs] == [False, False]

    # students never get a draft question; approving makes it usable; an approved question cannot be removed here
    ids = [q["id"] for q in qs]
    st = client.post(f"/teacher/weekend/lessons/{lid}/questions", headers=th, json={"approve": [ids[0]], "remove": [ids[1]]}).json()
    assert st["approvedQuestions"] == 1 and st["draftQuestions"] == 0
    st = client.post(f"/teacher/weekend/lessons/{lid}/questions", headers=th, json={"remove": [ids[0]]}).json()
    assert st["approvedQuestions"] == 1

    # a lesson that already has a plan (e.g. the school's seeded 教学方案) can get questions only, without touching the plan
    replies.append(json.dumps({"questions": [{"stem": "新题？", "options": ["a", "b", "c"], "correctIndex": 1, "explanation": "x", "knowledge": "约分"}]}, ensure_ascii=False))
    before = client.get(f"/teacher/weekend/lessons/{lid}", headers=th).json()
    oq = client.post("/teacher/weekend/lessons/draft", headers=th, json={"subject": "数学", "lessonNo": 17, "onlyQuestions": True})
    assert oq.status_code == 200 and oq.json()["status"]["draftQuestions"] == 1 and oq.json()["status"]["approvedQuestions"] == 1
    assert client.get(f"/teacher/weekend/lessons/{lid}", headers=th).json() == before
    assert client.post("/teacher/weekend/lessons/draft", headers=th, json={"subject": "数学", "lessonNo": 16 + 2, "onlyQuestions": True}).status_code == 404

    # editing the plan text
    ed = client.put(f"/teacher/weekend/lessons/{lid}", headers=th, json={"title": "约分", "coreTarget": "x", "teacherPlan": "y", "examples": ["e1"], "ppt": ["p1", "p2"]})
    assert ed.status_code == 200 and client.get(f"/teacher/weekend/lessons/{lid}", headers=th).json()["ppt"] == ["p1", "p2"]

    # what to prepare next: lesson 1 and 2 have no plan yet, so lesson 1 is next
    nxt = {x["subject"]: x for x in client.get("/teacher/weekend/next", headers=th).json()["items"]}
    assert nxt["数学"]["lessonNo"] == 1 and nxt["语文"]["subject"] == "语文"      # nothing taught yet: start from lesson 1
    print("OK")
''',
    )


def test_import_own_lesson_plan_docx_pptx(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
import io, zipfile

def office(kind, parts):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        for name, xml in parts.items():
            z.writestr(name, xml)
    return buf.getvalue()

DOCX = office("docx", {"word/document.xml": "<w:document><w:body>"
    "<w:p><w:r><w:t>第三课 分数的约分</w:t></w:r></w:p>"
    "<w:p><w:r><w:t>目标：会把分数约成最简分数，理解公因数</w:t></w:r></w:p>"
    "<w:p><w:r><w:t>例1：12/18 约分得 2/3（同除以 6）</w:t></w:r></w:p></w:body></w:document>"})
PPTX = office("pptx", {"ppt/slides/slide2.xml": "<p:sld><a:t>公因数</a:t><a:t>12和18的公因数有1、2、3、6</a:t></p:sld>",
                       "ppt/slides/slide1.xml": "<p:sld><a:t>约分 封面</a:t></p:sld>",
                       "ppt/slides/slide10.xml": "<p:sld><a:t>小结</a:t></p:sld>"})
AI = json.dumps({"title": "分数的约分", "coreTarget": "会约分", "teacherPlan": "先讲公因数再约分", "ppt": ["AI给的页标题"], "examples": ["例1：12/18 约分得 2/3"],
                 "closureTraining": "练习册 P30",
                 "questions": [{"stem": "6/9 约分后是？", "options": ["2/3", "3/4", "1/2"], "correctIndex": 0, "explanation": "同除 3", "knowledge": "约分"},
                               {"stem": "坏题", "options": ["a"], "correctIndex": 9}]}, ensure_ascii=False)

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    def imp(name, data, no=17, force="0", subject="数学", text=""):
        files = {"file": (name, data, "application/octet-stream")} if data is not None else None
        return client.post("/teacher/weekend/lessons/import", headers=th, data={"subject": subject, "lessonNo": str(no), "force": force, "text": text}, files=files)

    assert client.post("/teacher/weekend/lessons/import", headers=sh, data={"subject": "数学", "lessonNo": "17"}).status_code == 403
    assert imp("x.exe", b"abc").status_code == 400                                   # unsupported type
    assert imp("x.docx", b"not a zip").status_code == 400                            # damaged Office file
    assert imp("x.txt", b"too short").status_code == 400                             # nothing to read
    replies.append("garbage")
    assert imp("plan.docx", DOCX).status_code == 502                                 # AI could not tidy it: nothing saved
    assert client.get("/teacher/weekend/schedule?subject=数学", headers=th).json()["items"][16]["lessonId"] is None

    # .docx: the lesson is created from the teacher's own text; AI only structures it; the questions found are drafts
    replies.append(AI)
    r = imp("plan.docx", DOCX)
    assert r.status_code == 200, r.text
    d = r.json(); lid = d["lessonId"]
    assert "第三课 分数的约分" in prompts[-1] and "不要编造" in prompts[-1]          # the file's own text is what the AI sees
    assert d["status"]["hasPlan"] and d["status"]["draftQuestions"] == 1 and d["status"]["approvedQuestions"] == 0 and d["questionsFound"] == 1
    assert client.get(f"/teacher/weekend/lessons/{lid}", headers=th).json()["title"] == "分数的约分"

    # an existing real plan is not silently overwritten
    assert imp("plan.docx", DOCX).status_code == 409

    # .pptx: the teacher's own slides, in numeric order, become the big-screen pages (not the AI's guesses)
    replies.append(AI)
    r = imp("slides.pptx", PPTX, force="1")
    assert r.status_code == 200 and r.json()["slides"] == 3
    assert client.get(f"/teacher/weekend/lessons/{lid}", headers=th).json()["ppt"] == ["约分 封面", "公因数 12和18的公因数有1、2、3、6", "小结"]

    # pasted text works without a file
    replies.append(AI)
    assert imp(None, None, no=16, text="第十六课 通分。目标：会通分。例1：1/2 和 1/3 通分得 3/6 和 2/6，需要找最小公倍数。").status_code == 200
    print("OK")
''',
    )


def test_big_screen_pages_through_the_teachers_own_slides(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=94, title="翻页", core_target="目标",
                                  ppt_json=json.dumps(["第一页：封面", "第二页：公因数", "第三页：小结"], ensure_ascii=False),
                                  examples_json=json.dumps(["例1", "例2"], ensure_ascii=False))
        db.add(l); db.commit(); lid = l.id
    s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()["id"]
    base = f"/teacher/weekend/sessions/{s}"
    assert client.post(base + "/slide", headers=th, json={"delta": 1}).status_code == 409        # not started
    client.post(base + "/start", headers=th); client.post(base + "/next", headers=th)             # stage 2: slides
    d = client.get(base + "/board", headers=th).json()
    assert d["deck"] == {"total": 3, "index": 0} and d["content"] == ["第一页：封面"]
    d = client.post(base + "/slide", headers=th, json={"delta": 1}).json()
    assert d["deck"]["index"] == 1 and d["content"] == ["第二页：公因数"]
    assert client.get(base + "/board", headers=th).json()["content"] == ["第二页：公因数"]        # the big screen follows
    d = client.post(base + "/slide", headers=th, json={"delta": 5}).json()
    assert d["deck"]["index"] == 2                                                                # clamped to the last page
    d = client.post(base + "/slide", headers=th, json={"index": 0}).json()
    assert d["deck"]["index"] == 0
    # stage 3 pages through the worked examples, starting from the first; going back to stage 2 starts over too
    d = client.post(base + "/next", headers=th).json()
    assert d["deck"] == {"total": 2, "index": 0} and d["content"] == ["例1"]
    client.post(base + "/slide", headers=th, json={"delta": 1})
    assert client.get(base + "/board", headers=th).json()["content"] == ["例2"]
    client.post(base + "/next", headers=th)                                                       # stage 4: no deck
    assert "deck" not in client.get(base + "/board", headers=th).json()
    assert client.post(base + "/slide", headers=th, json={"delta": 1}).status_code == 409
    print("OK")
''',
    )


def test_ask_a_pupil_to_explain_big_screen_and_student_card(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
from datetime import datetime
from sqlalchemy import insert
FOLLOW = json.dumps({"stem": "类似小题？", "options": ["x", "y"], "correctIndex": 1, "explanation": "e"}, ensure_ascii=False)
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=93, title="讲解", core_target="目标")
        db.add(l); db.flush()
        q = legacy.TeachingQuestion(school_id=school_id, program_id=p.id, lesson_id=l.id, stage="lesson", subject="数学", level="C", knowledge="k",
                                    stem="4/8 约分？", options_json=json.dumps(["1/2", "1/4"]), correct_index=0, explanation="同除 4")
        db.add(q); db.flush(); qid = q.id
        teacher_id = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id)); cls.teacher_id = teacher_id
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == sid))
        if link is None: db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid))
        else: link.class_id = cls.id
        ids = {}
        for name, uname in (("小强", "e_strong"), ("小乙", "e_b")):
            u2 = legacy.User(school_id=school_id, username=uname, password_hash=legacy.hash_password("x"), name=name, role="student", grade=3)
            db.add(u2); db.flush(); db.add(legacy.ClassStudent(class_id=cls.id, student_id=u2.id)); ids[name] = u2.id
        s_name = db.get(legacy.User, sid); s_name.name = "小明"
        db.commit(); lid = l.id
    s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()["id"]
    base = f"/teacher/weekend/sessions/{s}"
    client.post(base + "/start", headers=th); client.post(base + "/goto", headers=th, json={"stage": 5})
    with legacy.SessionLocal() as db:
        t = legacy.Base.metadata.tables["weekend_answers"]
        for stu, sel, ok in ((ids["小强"], 0, True), (sid, 1, False), (ids["小乙"], 1, False)):
            db.execute(insert(t).values(school_id=school_id, session_id=s, student_id=stu, question_id=qid, selected=sel, correct=ok, max_hint=0, created_at=datetime.utcnow()))
        db.commit()

    # question-first: the pupils who got it right are the ones that can be asked; no "strong/weak" labels, no rates
    sug = client.get(base + "/peer-suggest", headers=th).json()
    q0 = sug["questions"][0]
    assert [x["name"] for x in q0["right"]] == ["小强"] and sorted(x["name"] for x in q0["wrong"]) == ["小乙", "小明"]
    assert "completionRate" not in json.dumps(sug)

    # must be someone who got it right; a pupil who got it wrong cannot be asked
    assert client.post(base + "/explain", headers=th, json={"tutorId": sid, "questionId": qid}).status_code == 400
    replies.append(FOLLOW)
    r = client.post(base + "/explain", headers=th, json={"tutorId": ids["小强"], "questionId": qid}).json()
    assert r["tutees"] == 2 and r["followup"] is True and "小强" in r["message"] and len([c for c in calls if c["feature"] == "weekend_followup"]) == 1   # one AI call for both pupils
    assert client.post(base + "/explain", headers=th, json={"tutorId": ids["小强"], "questionId": qid}).status_code == 409

    # the big screen names the pupil asked to explain and the question, never the ones who got it wrong
    board = client.get(base + "/board", headers=th).json()["content"]
    assert "请 小强 同学来讲：4/8 约分？" in board and not any("小明" in x or "小乙" in x for x in board)

    # the asked pupil's page shows the question, the right answer and the explanation; classmates see nothing
    assert client.get("/student/weekend/explain", headers=sh).json() == {"items": []}             # 小明 was not asked
    strong_h = {"Authorization": "Bearer " + login_and_change(client, "e_strong", "x", "Strong1234")}
    card = client.get("/student/weekend/explain", headers=strong_h).json()["items"]
    assert len(card) == 1 and card[0]["stem"] == "4/8 约分？" and card[0]["correctIndex"] == 0 and card[0]["explanation"] == "同除 4"
    # both pupils who got it wrong get the same follow-up
    assert client.get("/student/weekend/followup", headers=sh).json()["active"] is True
    print("OK")
''',
    )

