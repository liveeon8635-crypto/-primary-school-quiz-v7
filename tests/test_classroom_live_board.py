from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from changying.web import v1 as v1_module
from changying.web.v1_classroom_live_board import (
    LIVE_BOARD_POLL_MS,
    V1_CLASSROOM_LIVE_BOARD_MARKER,
    board_html,
    patch_v1_classroom_live_board_html,
)

ROOT = Path(__file__).resolve().parents[1]


def test_teacher_execution_page_links_to_the_board():
    import app  # noqa: F401  (applies the production V1 patches)

    html = v1_module.v1_html()
    assert V1_CLASSROOM_LIVE_BOARD_MARKER in html
    assert 'id="cy-session-board" href="/v1/classroom-board/\'+sid+\'" target="_blank" data-cy-open-window="1">打开大屏</a>' in html
    # The window opener stages the existing one-time auth handoff before opening the tab.
    assert "a[data-cy-open-window]" in html and "/v1/auth-handoff'" in html and "w.opener=null" in html
    assert "'/v1/transition','/v1/classroom-execution'].includes(path)" in html  # login returns here
    # Teacher-only handout panel on the execution page.
    assert "(window.__cyHandoutPanel?window.__cyHandoutPanel():'')" in html
    assert "window.__cyHandoutPanel=function" in html and "/handout'" in html
    assert patch_v1_classroom_live_board_html(html) == html


def test_board_page_is_a_data_free_read_only_shell():
    page = board_html(7)
    assert "var SID=7" in page and "POLL=2500" in page and LIVE_BOARD_POLL_MS == 2500
    # Only GET polling of the aggregate endpoint; nothing writes.
    # The only POST is the existing one-time auth handoff consume (no data is written).
    assert page.count("method:'POST'") == 1 and "/v1/auth-handoff/consume" in page
    for verb in ("PUT", "PATCH", "DELETE"):
        assert f"method:'{verb}'" not in page
    assert "<form" not in page and "<input" not in page
    # Only two display toggles (client-side), no data-changing controls.
    assert page.count("<button") == 2 and 'id="tg-live"' in page and 'id="tg-handout"' in page
    assert "/teacher/classroom-sessions/'+SID+'/live-board" in page
    assert "orientation:portrait" in page and "clamp(20px,2.6vw,44px)" in page
    # No student identity fields are rendered anywhere in the page script.
    for forbidden in ("studentName", "studentID", "username", "responses"):
        assert forbidden not in page


def test_live_board_is_teacher_only_aggregate_and_matches_database(tmp_path):
    db_path = tmp_path / "live-board.sqlite3"
    script = r"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app_v924 as legacy
from app import app


def token_for(db, user):
    sec = legacy.security_for(db, user)
    sec.must_change_password = False
    db.commit()
    return {"Authorization": "Bearer " + legacy.make_token(user, sec, False)}


with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        th = token_for(db, teacher)
        cls = db.scalar(select(legacy.SchoolClass).where(
            legacy.SchoolClass.school_id == teacher.school_id,
            legacy.SchoolClass.teacher_id == teacher.id))
        students = []
        for i in range(1, 21):
            u = legacy.User(school_id=teacher.school_id, username=f"board{i:02d}",
                            password_hash=legacy.hash_password("Abcdef12"),
                            name=f"测试同学{i:02d}", role="student", grade=5)
            db.add(u); db.flush()
            db.add(legacy.UserSecurity(user_id=u.id, must_change_password=False, failed_login_count=0))
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=u.id))
            students.append(u.id)
        other_teacher = legacy.User(school_id=teacher.school_id, username="other_t",
                                    password_hash=legacy.hash_password("Abcdef12"),
                                    name="另一位老师", role="teacher", grade=None)
        db.add(other_teacher); db.flush()
        db.add(legacy.UserSecurity(user_id=other_teacher.id, must_change_password=False, failed_login_count=0))
        q = legacy.Question(school_id=teacher.school_id, grade=5, subject="数学", textbook="人教版",
                            semester="上册", unit="小数乘法", knowledge="小数乘法",
                            text="0.4×3 的结果是？",
                            options_json=json.dumps(["0.12", "1.2", "12", "120"], ensure_ascii=False),
                            correct_index=1, explanation="1.2", question_type="single_choice",
                            answer_json="{}", figure_json="{}", creator_id=teacher.id)
        db.add(q); db.flush()
        paper = legacy.Paper(school_id=teacher.school_id, title="源练习", grade=5, subject="数学",
                             textbook="人教版", unit="小数乘法", question_ids_json=json.dumps([q.id]),
                             teacher_id=teacher.id)
        db.add(paper); db.flush()
        assignment = legacy.Assignment(school_id=teacher.school_id, title="课堂练习", class_id=cls.id,
                                       paper_id=paper.id, due_date="2026-09-30")
        db.add(assignment); db.flush()
        handouts = legacy.Base.metadata.tables["classroom_review_handouts"]
        db.execute(handouts.insert().values(
            school_id=teacher.school_id, assignment_id=assignment.id, class_id=cls.id,
            teacher_id=teacher.id, title="讲义",
            selected_knowledge_json=json.dumps(["小数乘法"], ensure_ascii=False),
            selected_question_ids_json=json.dumps([q.id]), teacher_notes="",
            content_text="讲解。", created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
        student_tokens = {sid: token_for(db, db.get(legacy.User, sid)) for sid in students}
        outsider_token = token_for(db, db.get(legacy.User, other_teacher.id))
        db.commit()
        aid = assignment.id

    created = client.post(f"/teacher/assignments/{aid}/classroom-session", headers=th, json={}).json()
    sid = created["session"]["id"]; segid = created["segments"][0]["id"]
    assert client.post(f"/teacher/classroom-sessions/{sid}/state", headers=th, json={"status": "active"}).status_code == 200
    client.post(f"/teacher/classroom-sessions/{sid}/segments/{segid}/start", headers=th)
    client.post(f"/teacher/classroom-sessions/{sid}/segments/{segid}/complete", headers=th)
    draft = client.post(f"/teacher/classroom-sessions/{sid}/segments/{segid}/quick-checks/draft",
                        headers=th, json={"question_type": "single_choice", "use_ai": False}).json()
    cid = draft["id"]
    client.put(f"/teacher/classroom-sessions/{sid}/quick-checks/{cid}", headers=th, json={
        "question_text": "0.6×4 的结果是？", "options": ["0.24", "2.4", "24", "240"],
        "correct_index": 1, "explanation": "2.4"})

    board_url = f"/teacher/classroom-sessions/{sid}/live-board"

    # (b) access control: anonymous, student and a different teacher are all rejected.
    r1 = client.get(board_url); assert r1.status_code == 401, r1.status_code
    r2 = client.get(board_url, headers=student_tokens[students[0]]); assert r2.status_code == 403, (r2.status_code, r2.text)
    r3 = client.get(board_url, headers=outsider_token); assert r3.status_code == 404, (r3.status_code, r3.text)

    # Before anything is open the board waits.
    waiting = client.get(board_url, headers=th).json()
    assert waiting["check"] is None and waiting["session"]["classSize"] >= 20

    assert client.post(f"/teacher/classroom-sessions/{sid}/quick-checks/{cid}/state",
                       headers=th, json={"status": "open"}).status_code == 200

    # (a) 20 students answer at the same time: 12 correct (B), 5 pick A, 3 pick C.
    picks = {}
    for n, student_id in enumerate(students):
        picks[student_id] = 1 if n < 12 else (0 if n < 17 else 2)

    def answer(student_id):
        r = client.post(f"/student/classroom-quick-checks/{cid}/respond",
                        headers=student_tokens[student_id],
                        json={"selected_index": picks[student_id]})
        return r.status_code

    with ThreadPoolExecutor(max_workers=10) as pool:
        codes = list(pool.map(answer, students))
    assert codes == [200] * 20, codes

    # While the check is open the results are hidden by default (no copying from the projector).
    hidden = client.get(board_url, headers=th).json()["check"]
    assert hidden["status"] == "open" and hidden["responseCount"] == 20
    assert hidden["resultsHidden"] is True
    assert hidden["accuracy"] is None and hidden["distribution"] is None and hidden["correctCount"] is None

    board = client.get(board_url + "?live=1", headers=th)
    assert board.status_code == 200, board.text
    data = board.json()
    check = data["check"]

    # The numbers match an independent count straight from the database.
    with legacy.SessionLocal() as db:
        resp = legacy.Base.metadata.tables["classroom_quick_check_responses"]
        rows = db.execute(select(resp.c.selected_index, resp.c.is_correct).where(resp.c.check_id == cid)).all()
    assert len(rows) == 20
    assert check["responseCount"] == 20
    assert check["correctCount"] == sum(1 for r in rows if r[1]) == 12
    assert check["accuracy"] == 60
    by_option = {d["selectedIndex"]: d["count"] for d in check["distribution"]}
    assert by_option == {0: 5, 1: 12, 2: 3, 3: 0}
    assert check["status"] == "open" and check["correctIndex"] is None  # not revealed while open
    assert data["session"]["classSize"] >= 20

    # (c) no student personal information anywhere in the response.
    text = board.text
    assert "测试同学" not in text and "board0" not in text and "board1" not in text
    for key in ("studentName", "studentID", "username", "responses"):
        assert key not in text
    assert set(data) == {"session", "check", "segment", "handout", "serverTime"}
    assert set(data["session"]) == {"title", "className", "status", "classSize"}
    assert set(check) == {"id", "status", "questionText", "options", "responseCount", "resultsHidden",
                          "correctCount", "accuracy", "distribution", "correctIndex"}
    assert all(set(d) == {"selectedIndex", "count", "percentage"} for d in check["distribution"])

    # The page shell is data-free and has no write calls.
    page = client.get(f"/v1/classroom-board/{sid}")
    assert page.status_code == 200
    assert "0.6×4" not in page.text and "测试同学" not in page.text

    # The big screen endpoint is read-only: no write verbs are accepted.
    for verb in (client.post, client.put, client.delete, client.patch):
        assert verb(board_url, headers=th).status_code == 405
    with legacy.SessionLocal() as db:
        resp = legacy.Base.metadata.tables["classroom_quick_check_responses"]
        assert db.scalar(select(func.count()).select_from(resp).where(resp.c.check_id == cid)) == 20
    # Closing the check reveals the numbers without the live flag.
    assert client.post(f"/teacher/classroom-sessions/{sid}/quick-checks/{cid}/state",
                       headers=th, json={"status": "closed"}).status_code == 200
    closed = client.get(board_url, headers=th).json()["check"]
    assert closed["status"] == "closed" and closed["resultsHidden"] is False
    assert closed["accuracy"] == 60 and {d["selectedIndex"]: d["count"] for d in closed["distribution"]} == {0: 5, 1: 12, 2: 3, 3: 0}
    print("OK")
"""
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "PYTHONPATH": str(ROOT),
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout, result.stdout


def test_handout_panel_and_explaining_view(tmp_path):
    from changying.web.v1_classroom_live_board import handout_excerpt

    text = "总述\n\n小数乘法：先按整数算，再点小数点。\n\n应用题：注意单位。\n\n小数 乘法 的易错点：位数数错。"
    assert handout_excerpt(text, "小数乘法") == "小数乘法：先按整数算，再点小数点。\n\n小数 乘法 的易错点：位数数错。"
    assert handout_excerpt(text, "不存在的知识点") == "" and handout_excerpt(text, "") == ""
    assert len(handout_excerpt("小数乘法" + "字" * 5000, "小数乘法")) == 1500

    script = r"""
import json
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

import app_v924 as legacy
from app import app


def token_for(db, user):
    sec = legacy.security_for(db, user)
    sec.must_change_password = False
    db.commit()
    return {"Authorization": "Bearer " + legacy.make_token(user, sec, False)}


with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        student = db.scalar(select(legacy.User).where(legacy.User.username == "student1"))
        th = token_for(db, teacher)
        sh = token_for(db, student)
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.teacher_id == teacher.id))
        q = legacy.Question(school_id=teacher.school_id, grade=5, subject="数学", textbook="人教版",
                            semester="上册", unit="小数乘法", knowledge="小数乘法", text="0.4×3？",
                            options_json=json.dumps(["0.12", "1.2", "12", "120"], ensure_ascii=False),
                            correct_index=1, explanation="1.2", question_type="single_choice",
                            answer_json="{}", figure_json="{}", creator_id=teacher.id)
        db.add(q); db.flush()
        paper = legacy.Paper(school_id=teacher.school_id, title="源", grade=5, subject="数学",
                             textbook="人教版", unit="小数乘法", question_ids_json=json.dumps([q.id]),
                             teacher_id=teacher.id)
        db.add(paper); db.flush()
        a = legacy.Assignment(school_id=teacher.school_id, title="课堂", class_id=cls.id,
                              paper_id=paper.id, due_date="2026-09-30")
        db.add(a); db.flush()
        handouts = legacy.Base.metadata.tables["classroom_review_handouts"]
        db.execute(handouts.insert().values(
            school_id=teacher.school_id, assignment_id=a.id, class_id=cls.id, teacher_id=teacher.id,
            title="小数乘法复盘讲义", selected_knowledge_json=json.dumps(["小数乘法"], ensure_ascii=False),
            selected_question_ids_json=json.dumps([q.id]), teacher_notes="私人备注",
            content_text="总述\n\n小数乘法：先按整数算，再点小数点。\n\n应用题：注意单位。",
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
        db.commit()
        aid = a.id
    created = client.post(f"/teacher/assignments/{aid}/classroom-session", headers=th, json={}).json()
    sid = created["session"]["id"]; segid = created["segments"][0]["id"]

    # Teacher-only handout endpoint.
    url = f"/teacher/classroom-sessions/{sid}/handout"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=sh).status_code == 403
    got = client.get(url, headers=th).json()["handout"]
    assert got["title"] == "小数乘法复盘讲义" and "先按整数算" in got["content"]
    assert got["teacherNotes"] == "私人备注" and got["selectedKnowledge"] == ["小数乘法"]

    # Explaining view: segment + only the matching paragraph; the private notes never reach the board.
    client.post(f"/teacher/classroom-sessions/{sid}/state", headers=th, json={"status": "active"})
    assert client.get(f"/teacher/classroom-sessions/{sid}/live-board", headers=th).json()["segment"] is None
    assert client.post(f"/teacher/classroom-sessions/{sid}/segments/{segid}/start", headers=th).status_code == 200
    board = client.get(f"/teacher/classroom-sessions/{sid}/live-board", headers=th)
    data = board.json()
    assert data["segment"]["knowledgeKey"] == "小数乘法"
    assert data["handout"]["excerpt"] == "小数乘法：先按整数算，再点小数点。"
    assert "私人备注" not in board.text and "总述" not in board.text and "应用题" not in board.text
    print("OK")
"""
    import os
    import subprocess
    import sys

    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'handout.sqlite3'}", "PYTHONPATH": str(ROOT)}
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, text=True,
                            capture_output=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout, result.stdout
