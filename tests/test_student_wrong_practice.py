from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_isolated(tmp_path, script: str) -> None:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'wrong-practice.sqlite3'}",
        "PYTHONPATH": str(ROOT),
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout, result.stdout


COMMON = r'''
import json

from fastapi.testclient import TestClient

import app_v924 as legacy
from app import app


def login_and_change(client, username, old_password, new_password):
    login = client.post("/login", json={"username": username, "password": old_password, "remember": False})
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    changed = client.post(
        "/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": old_password, "new_password": new_password, "remember": False},
    )
    assert changed.status_code == 200, changed.text
    return changed.json()["token"]


def answers_for(pid, right):
    with legacy.SessionLocal() as db:
        paper = db.get(legacy.Paper, pid)
        qids = json.loads(paper.question_ids_json)
        out = []
        for qid in qids:
            q = db.get(legacy.Question, qid)
            qt = legacy.question_type_of(q)
            if qt in {"single_choice", "true_false"}:
                opts = json.loads(q.options_json)
                idx = int(q.correct_index) if right else (int(q.correct_index) + 1) % len(opts)
                out.append({"question_id": qid, "selected_index": idx})
            else:
                meta = legacy.question_answer_meta(q)
                out.append({"question_id": qid, "text_answer": meta["answer"] if right else "__wrong__"})
        return qids, out


def seed_wrong_records(client, th, sh, sid):
    classes = client.get("/teacher/classes", headers=th).json()
    options = client.get(
        f"/teacher/students/{sid}/practice-options",
        params={"grade": 5, "subject": "数学", "textbook": "人教版"},
        headers=th,
    ).json()
    knowledge = options["modules"][0]["knowledge"]
    created = client.post(
        f"/teacher/students/{sid}/auto-practice",
        headers=th,
        json={"grade": 5, "subject": "数学", "textbook": "人教版", "kind": "module",
              "knowledge": knowledge, "question_count": 4, "due_date": "2026-09-30",
              "class_id": classes[0]["id"]},
    )
    assert created.status_code == 200, created.text
    aid = created.json()["assignment"]["id"]
    pid = created.json()["paper"]["id"]
    qids, wrong = answers_for(pid, right=False)
    submitted = client.post(f"/student/assignments/{aid}/submit", headers=sh, json={"answers": wrong})
    assert submitted.status_code == 200, submitted.text
    return knowledge


def no_ai(*args, **kwargs):
    raise AssertionError("student wrong-question practice must not call a large model")


legacy._ai_call = no_ai
'''


def test_student_can_start_same_knowledge_practice_and_mastery_follows_existing_rule(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th = {"Authorization": "Bearer " + login_and_change(client, "teacher1", "123456", "Teacher1234")}
    sh = {"Authorization": "Bearer " + login_and_change(client, "student1", "123456", "Student1234")}
    sid = client.get("/session", headers=sh).json()["userID"]
    knowledge = seed_wrong_records(client, th, sh, sid)

    book = client.get("/student/wrong-questions", headers=sh).json()
    assert book["activeCount"] >= 1
    item = book["items"][0]
    assert item["status"] == "active" and item["questionID"]
    wid, source_qid = item["id"], item["questionID"]

    started = client.post(f"/student/wrong-questions/{wid}/practice", headers=sh)
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["reused"] is False and 1 <= body["questionCount"] <= 5
    aid, pid = body["assignmentID"], body["paperID"]

    # Re-clicking while the practice is unfinished reuses it (no duplicates).
    again = client.post(f"/student/wrong-questions/{wid}/practice", headers=sh).json()
    assert again["reused"] is True and again["assignmentID"] == aid

    # The student receives public questions only (no answer key), never the original one.
    public = client.get(f"/papers/{pid}/questions", headers=sh).json()
    assert public and all("correctIndex" not in q and "answer" not in q for q in public)
    assert source_qid not in [q["id"] for q in public]

    # Same knowledge point only.
    with legacy.SessionLocal() as db:
        for q in public:
            row = db.get(legacy.Question, q["id"])
            assert (row.knowledge or row.unit) == (db.get(legacy.Question, source_qid).knowledge or db.get(legacy.Question, source_qid).unit)

    # It shows up as a normal assignment for the student.
    assert aid in [a["id"] for a in client.get("/student/assignments", headers=sh).json()]

    # Round 1: all correct -> one confirmation, still active (existing 2-confirmation rule).
    _, right = answers_for(pid, right=True)
    done = client.post(f"/student/assignments/{aid}/submit", headers=sh, json={"answers": right})
    assert done.status_code == 200 and done.json()["score"] == 100
    with legacy.SessionLocal() as db:
        row = db.get(legacy.WrongQuestionRecord, wid)
        assert row.status == "active" and row.reinforcement_count == 1

    # Round 2: a new practice; all correct again -> mastered.
    second = client.post(f"/student/wrong-questions/{wid}/practice", headers=sh).json()
    assert second["reused"] is False and second["assignmentID"] != aid
    _, right2 = answers_for(second["paperID"], right=True)
    done2 = client.post(f"/student/assignments/{second['assignmentID']}/submit", headers=sh, json={"answers": right2})
    assert done2.status_code == 200
    with legacy.SessionLocal() as db:
        row = db.get(legacy.WrongQuestionRecord, wid)
        assert row.status == "mastered" and row.mastered_at is not None
    mastered = client.post(f"/student/wrong-questions/{wid}/practice", headers=sh)
    assert mastered.status_code == 400
    print("OK")
''',
    )


def test_wrong_answer_in_practice_resets_progress_and_access_is_scoped(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th = {"Authorization": "Bearer " + login_and_change(client, "teacher1", "123456", "Teacher1234")}
    sh = {"Authorization": "Bearer " + login_and_change(client, "student1", "123456", "Student1234")}
    sid = client.get("/session", headers=sh).json()["userID"]
    seed_wrong_records(client, th, sh, sid)
    item = client.get("/student/wrong-questions", headers=sh).json()["items"][0]
    wid = item["id"]

    started = client.post(f"/student/wrong-questions/{wid}/practice", headers=sh).json()
    _, right = answers_for(started["paperID"], right=True)
    client.post(f"/student/assignments/{started['assignmentID']}/submit", headers=sh, json={"answers": right})
    with legacy.SessionLocal() as db:
        assert db.get(legacy.WrongQuestionRecord, wid).reinforcement_count == 1

    second = client.post(f"/student/wrong-questions/{wid}/practice", headers=sh).json()
    _, wrong = answers_for(second["paperID"], right=False)
    res = client.post(f"/student/assignments/{second['assignmentID']}/submit", headers=sh, json={"answers": wrong})
    assert res.status_code == 200 and res.json()["score"] == 0
    with legacy.SessionLocal() as db:
        row = db.get(legacy.WrongQuestionRecord, wid)
        assert row.status == "active" and row.reinforcement_count == 0 and row.mastered_at is None

    # Teachers cannot use the student endpoint; unknown ids are 404; other students cannot touch it.
    assert client.post(f"/student/wrong-questions/{wid}/practice", headers=th).status_code == 403
    assert client.post("/student/wrong-questions/999999/practice", headers=sh).status_code == 404
    anon = client.post(f"/student/wrong-questions/{wid}/practice")
    assert anon.status_code in (401, 403)

    # Teacher-side reinforcement routes are unchanged.
    teacher_view = client.get(f"/teacher/students/{sid}/wrong-questions", headers=th)
    assert teacher_view.status_code == 200 and teacher_view.json()["items"]
    print("OK")
''',
    )


def test_wrong_book_page_gets_practice_button_and_handler():
    import app_v924 as legacy
    from changying.web.student_wrong_practice import (
        STUDENT_WRONG_PRACTICE_MARKER,
        patch_wrongbook_html,
    )
    import app  # noqa: F401  (applies the production patches)

    html = legacy.INDEX_HTML
    assert STUDENT_WRONG_PRACTICE_MARKER in html
    start = html.index("async function wrongbook(){")
    end = html.index("async function analytics(){", start)
    page = html[start:end]
    assert 'data-rewid="${x.id}"' in page
    assert '"/student/wrong-questions/"+b.dataset.rewid+"/practice"' in page
    assert "startAssignment(r.assignmentID)" in page
    assert patch_wrongbook_html(html) == html  # idempotent


def test_daily_cap_limits_self_started_practice_rounds(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
from changying.web import student_wrong_practice as swp

with TestClient(app) as client:
    th = {"Authorization": "Bearer " + login_and_change(client, "teacher1", "123456", "Teacher1234")}
    sh = {"Authorization": "Bearer " + login_and_change(client, "student1", "123456", "Student1234")}
    sid = client.get("/session", headers=sh).json()["userID"]
    seed_wrong_records(client, th, sh, sid)
    items = client.get("/student/wrong-questions", headers=sh).json()["items"]
    assert len(items) >= 2
    swp.MAX_NEW_PRACTICES_PER_DAY = 2
    first = client.post(f"/student/wrong-questions/{items[0]['id']}/practice", headers=sh)
    second = client.post(f"/student/wrong-questions/{items[1]['id']}/practice", headers=sh)
    assert first.status_code == 200 and second.status_code == 200
    third = client.post(f"/student/wrong-questions/{items[2]['id']}/practice", headers=sh)
    assert third.status_code == 429, third.text
    # Re-opening an unfinished practice is not a new round and stays allowed.
    reopened = client.post(f"/student/wrong-questions/{items[0]['id']}/practice", headers=sh)
    assert reopened.status_code == 200 and reopened.json()["reused"] is True
    print("OK")
''',
    )
