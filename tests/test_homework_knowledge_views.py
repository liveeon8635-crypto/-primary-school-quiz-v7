from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hw_solve_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules["hw_solve_helpers"] = helpers
spec.loader.exec_module(helpers)


def test_flags_open_until_a_later_submission_clears_the_knowledge_point(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
from datetime import datetime, timedelta
from sqlalchemy import update

KP = "测试知识点甲"
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    HELP = legacy.Base.metadata.tables["help_requests"]

    def new_questions(n, knowledge):
        with legacy.SessionLocal() as db:
            ids = []
            for i in range(n):
                q = legacy.Question(school_id=school_id, grade=3, subject="数学", knowledge=knowledge, text=f"{knowledge}-{i}",
                                    options_json=json.dumps(["a", "b"]), correct_index=0)
                db.add(q); db.flush(); ids.append(q.id)
            db.commit()
            return ids

    def submit(ids, correct_flags, when):
        with legacy.SessionLocal() as db:
            answers = [{"question_id": q, "selected_index": 0, "correct": ok} for q, ok in zip(ids, correct_flags)]
            db.add(legacy.Submission(school_id=school_id, student_id=sid, title="综合测试", score=0, correct=sum(correct_flags),
                                     total=len(ids), answers_json=json.dumps(answers), submitted_at=when))
            db.commit()

    def flags():
        r = client.get("/student/homework/knowledge", headers=sh); assert r.status_code == 200, r.text
        return r.json()

    ids = new_questions(4, KP)
    ask = datetime.utcnow()
    hid = make_help(client, sh)
    replies.append(sol(kp=KP))
    assert client.post(f"/student/homework/help/{hid}/solve", headers=sh).status_code == 200

    data = flags()
    assert data["rule"] == {"minQuestions": 3, "passPercent": 80} and data["open"] == 1 and data["assists"] == 1
    assert data["flags"][0]["knowledge"] == KP and data["flags"][0]["state"] == "open" and data["flags"][0]["count"] == 1

    # A submission from BEFORE the AI help never clears it.
    submit(ids[:3], [True] * 3, ask - timedelta(days=1))
    assert flags()["flags"][0]["state"] == "open"
    # Later, but too few questions on the knowledge point (2 < 3): still open.
    submit(ids[:2], [True, True], datetime.utcnow() + timedelta(minutes=1))
    assert flags()["flags"][0]["state"] == "open"
    # Later, enough questions but below the pass line (2 of 3 = 67% < 80%): still open.
    submit(ids[:3], [True, True, False], datetime.utcnow() + timedelta(minutes=2))
    assert flags()["flags"][0]["state"] == "open"
    # Later, 3 of 3: cleared, with the date it was cleared.
    submit(ids[:3], [True, True, True], datetime.utcnow() + timedelta(minutes=3))
    cleared = flags()["flags"][0]
    assert cleared["state"] == "cleared" and cleared["clearedAt"] and flags()["open"] == 0

    # Needing AI help on it AGAIN re-opens the flag until yet another later submission passes.
    with legacy.SessionLocal() as db:
        db.execute(update(HELP).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.execute(update(legacy.AIUsageLog).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.commit()
    hid2 = make_help(client, sh, text="3+4=?")
    replies.append(sol(answer="7", expression="3+4", steps=("3 加 4",), kp=KP))
    client.post(f"/student/homework/help/{hid2}/solve", headers=sh)
    KN = legacy.Base.metadata.tables["homework_ai_knowledge"]
    with legacy.SessionLocal() as db:        # the test's earlier submissions were stamped in the future; put this help after them
        db.execute(update(KN).where(KN.c.help_id == hid2).values(created_at=datetime.utcnow() + timedelta(minutes=20)))
        db.commit()
    future_submit_time = datetime.utcnow() + timedelta(minutes=30)
    again = flags()["flags"][0]
    assert again["count"] == 2 and again["state"] == "open"
    submit(ids[:4], [True] * 4, future_submit_time)
    assert flags()["flags"][0]["state"] == "cleared"
print("OK")
''',
    )


def test_each_role_sees_only_what_it_may(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
KP = "测试知识点乙"
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    ph = {"Authorization": "Bearer " + login_and_change(client, "parent1", "123456", "Parent1234")}
    with legacy.SessionLocal() as db:
        db.add(legacy.Question(school_id=school_id, grade=3, subject="数学", knowledge=KP, text="q", options_json="[]", correct_index=0))
        db.commit()
    hid = make_help(client, sh, text="我的秘密题目文字")
    replies.append(sol(kp=KP))
    client.post(f"/student/homework/help/{hid}/solve", headers=sh)

    # student: own flags and own question history
    hist = client.get("/student/homework/history", headers=sh).json()
    assert hist["items"][0]["questionText"] == "我的秘密题目文字" and hist["items"][0]["knowledge"] == KP and hist["retentionDays"] == 90
    assert client.get("/student/homework/knowledge", headers=th).status_code == 403          # a teacher is not a student

    # parent: the linked child's knowledge points only - never the child's questions
    child = client.get(f"/parent/children/{sid}/homework-knowledge", headers=ph)
    assert child.status_code == 200 and child.json()["flags"][0]["knowledge"] == KP and child.json()["unmatched"] == []
    assert "我的秘密题目文字" not in child.text and "questionText" not in child.text
    assert client.get("/parent/children/999999/homework-knowledge", headers=ph).status_code == 404
    other = client.get(f"/parent/children/{sid + 50}/homework-knowledge", headers=ph)
    assert other.status_code == 404
    assert client.get(f"/parent/children/{sid}/homework-knowledge", headers=sh).status_code == 403   # a student is not a parent

    # teacher: students of their own classes, with the full question and the AI's result
    summary = client.get("/teacher/homework/knowledge-summary", headers=th).json()
    assert summary["students"][0]["studentId"] == sid and summary["students"][0]["open"] == 1
    assists = client.get("/teacher/homework/ai-assists", headers=th).json()["items"]
    assert assists[0]["questionText"] == "我的秘密题目文字" and assists[0]["knowledge"] == KP and assists[0]["stateLabel"] == "AI 已讲解"
    assert client.get(f"/teacher/homework/ai-assists?studentId={sid}", headers=th).status_code == 200
    assert client.get("/teacher/homework/ai-assists?studentId=999999", headers=th).status_code == 403
    assert client.get("/teacher/homework/ai-assists", headers=sh).status_code == 403          # a student is not a teacher
print("OK")
''',
    )


def test_pages_show_the_record_read_only_in_the_existing_screens():
    from changying.web.homework_assistant_pages import homework_page_html
    from changying.web.v1_classic_unified_top import inject_v1_classic_unified

    page = homework_page_html()
    assert "function knowledgeCard(" in page and "function knowledgeView(" in page and "knowledge:'AI 辅助记录'" in page
    assert "innerHTML" not in page and "eval(" not in page
    classic = inject_v1_classic_unified("<html><head></head><body><div id=page></div></body></html>")
    band = classic.split("cy-hw-know", 1)[1].split("setInterval(ensure,1300)", 1)[0]
    assert "/student/homework/knowledge" in band and "/homework-knowledge" in band
    assert "innerHTML" not in band and "POST" not in band and "PUT" not in band and "DELETE" not in band   # read-only
