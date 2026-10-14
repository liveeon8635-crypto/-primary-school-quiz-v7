from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r"""
import json
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import select

import app_v924 as legacy
from app import app
import changying.web.v1_classroom_live_board as board


def token_for(db, user):
    sec = legacy.security_for(db, user)
    sec.must_change_password = False
    db.commit()
    return {"Authorization": "Bearer " + legacy.make_token(user, sec, False)}


with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        th = token_for(db, teacher)
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == teacher.school_id, legacy.SchoolClass.teacher_id == teacher.id))
        stu = legacy.User(school_id=teacher.school_id, username="lockstu", password_hash=legacy.hash_password("Abcdef12"), name="同学", role="student", grade=5)
        db.add(stu); db.flush()
        db.add(legacy.UserSecurity(user_id=stu.id, must_change_password=False, failed_login_count=0))
        db.add(legacy.ClassStudent(class_id=cls.id, student_id=stu.id))
        other = legacy.User(school_id=teacher.school_id, username="lock_other", password_hash=legacy.hash_password("Abcdef12"), name="另一位老师", role="teacher", grade=None)
        db.add(other); db.flush()
        db.add(legacy.UserSecurity(user_id=other.id, must_change_password=False, failed_login_count=0))
        q = legacy.Question(school_id=teacher.school_id, grade=5, subject="数学", textbook="人教版", semester="上册", unit="小数乘法", knowledge="小数乘法",
                            text="0.4×3 的结果是？", options_json=json.dumps(["0.12", "1.2", "12", "120"], ensure_ascii=False), correct_index=1,
                            explanation="1.2", question_type="single_choice", answer_json="{}", figure_json="{}", creator_id=teacher.id)
        db.add(q); db.flush()
        paper = legacy.Paper(school_id=teacher.school_id, title="源练习", grade=5, subject="数学", textbook="人教版", unit="小数乘法",
                             question_ids_json=json.dumps([q.id]), teacher_id=teacher.id)
        db.add(paper); db.flush()
        assignment = legacy.Assignment(school_id=teacher.school_id, title="课堂练习", class_id=cls.id, paper_id=paper.id, due_date="2026-09-30")
        db.add(assignment); db.flush()
        handouts = legacy.Base.metadata.tables["classroom_review_handouts"]
        db.execute(handouts.insert().values(school_id=teacher.school_id, assignment_id=assignment.id, class_id=cls.id, teacher_id=teacher.id, title="讲义",
                   selected_knowledge_json=json.dumps(["小数乘法"], ensure_ascii=False), selected_question_ids_json=json.dumps([q.id]), teacher_notes="",
                   content_text="讲解。", created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
        stok = token_for(db, db.get(legacy.User, stu.id)); otok = token_for(db, db.get(legacy.User, other.id))
        db.commit(); aid = assignment.id; school_id = teacher.school_id

    created = client.post(f"/teacher/assignments/{aid}/classroom-session", headers=th, json={}).json()
    sid = created["session"]["id"]; segid = created["segments"][0]["id"]
    client.post(f"/teacher/classroom-sessions/{sid}/state", headers=th, json={"status": "active"})
    client.post(f"/teacher/classroom-sessions/{sid}/segments/{segid}/start", headers=th)
    client.post(f"/teacher/classroom-sessions/{sid}/segments/{segid}/complete", headers=th)
    draft = client.post(f"/teacher/classroom-sessions/{sid}/segments/{segid}/quick-checks/draft", headers=th, json={"question_type": "single_choice", "use_ai": False}).json()
    cid = draft["id"]
    client.put(f"/teacher/classroom-sessions/{sid}/quick-checks/{cid}", headers=th, json={"question_text": "0.6×4 的结果是？", "options": ["0.24", "2.4", "24", "240"], "correct_index": 1, "explanation": "2.4"})

    lock_url = f"/teacher/classroom-sessions/{sid}/board-lock"
    live_url = f"/teacher/classroom-sessions/{sid}/live-board"

    # access control
    assert client.get(lock_url).status_code == 401
    assert client.post(lock_url, headers=stok, json={"mode": "freeze"}).status_code == 403
    assert client.post(lock_url, headers=otok, json={"mode": "freeze"}).status_code == 404          # someone else's lesson
    assert client.delete(lock_url, headers=otok).status_code == 404
    assert client.post(lock_url, headers=th, json={"mode": "banana"}).status_code == 400
    assert client.get(lock_url, headers=th).json() == {"locked": False, "mode": ""}
    assert client.get(live_url, headers=th).json().get("lock") is None

    # freeze while nothing is open: the board keeps showing "waiting" even after a check is opened
    st = client.post(lock_url, headers=th, json={"mode": "freeze"}).json()
    assert st["locked"] is True and st["mode"] == "freeze"
    assert client.post(f"/teacher/classroom-sessions/{sid}/quick-checks/{cid}/state", headers=th, json={"status": "open"}).status_code == 200
    frozen = client.get(live_url, headers=th).json()
    assert frozen["check"] is None and frozen["lock"]["mode"] == "freeze"                            # still the old frame
    assert client.get(lock_url, headers=th).json()["mode"] == "freeze"

    # unlock: the real state (the open check) is back
    assert client.delete(lock_url, headers=th).json() == {"locked": False, "mode": ""}
    live = client.get(live_url, headers=th).json()
    assert live["check"]["status"] == "open" and "lock" not in live

    # freeze now takes a fresh snapshot of the OPEN check, and keeps it
    client.post(lock_url, headers=th, json={"mode": "freeze"})
    snap = client.get(live_url, headers=th).json()
    assert snap["check"]["status"] == "open" and snap["check"]["questionText"] == "0.6×4 的结果是？" and snap["lock"]["mode"] == "freeze"
    client.post(f"/teacher/classroom-sessions/{sid}/quick-checks/{cid}/state", headers=th, json={"status": "closed"})
    assert client.get(live_url, headers=th).json()["check"]["status"] == "open"                      # closing it does not change the frozen screen

    # cover: no lesson content at all, even though a check exists
    client.post(lock_url, headers=th, json={"mode": "cover"})
    covered = client.get(live_url, headers=th).json()
    assert covered["lock"]["mode"] == "cover" and covered["check"] is None and "segment" not in covered
    assert "0.6×4" not in json.dumps(covered, ensure_ascii=False)

    # the lock lasts one lesson at most
    with board._BOARD_LOCK_GUARD:
        for key in list(board._BOARD_LOCKS):
            board._BOARD_LOCKS[key]["expires"] = 0
    assert client.get(lock_url, headers=th).json()["locked"] is False
    assert client.get(live_url, headers=th).json()["check"]["status"] == "closed"

    # the lock and unlock are in the audit trail
    with legacy.SessionLocal() as db:
        actions = [a for a in db.scalars(select(legacy.AuditLog.action).where(legacy.AuditLog.school_id == school_id)).all() if a.startswith("classroom.board")]
    assert actions.count("classroom.board.lock") == 3 and actions.count("classroom.board.unlock") == 1, actions
print("OK")
"""


def test_teacher_can_freeze_or_cover_the_big_screen_and_unlock_it(tmp_path):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'lock.sqlite3'}", "PYTHONPATH": str(ROOT)}
    result = subprocess.run([sys.executable, "-c", SCRIPT], cwd=ROOT, env=env, text=True, capture_output=True, timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout


def test_pages_carry_the_lock_controls_and_the_board_obeys_the_lock():
    import app  # noqa: F401  (applies the production V1 patches)
    from changying.web import v1 as v1_module
    from changying.web.v1_classroom_live_board import board_html

    html = v1_module.v1_html()
    for needle in ('id="cy-board-freeze"', 'id="cy-board-cover"', 'id="cy-board-unlock"', "/board-lock", "BroadcastChannel('cyBoard'+sid)"):
        assert needle in html, needle
    page = board_html(3)
    assert "课堂进行中，请稍候" in page and "lk.mode==='freeze'" in page and "BroadcastChannel('cyBoard'+SID)" in page
    # the board still never writes: it has no controls of its own for the lock
    assert page.count("<button") == 2 and "board-lock" not in page
