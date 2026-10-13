from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_KEYS = (
    "HOMEWORK_ASSISTANT", "HOMEWORK_VISION_PROVIDER", "HOMEWORK_VISION_BASE_URL", "HOMEWORK_VISION_MODEL",
    "HOMEWORK_VISION_API_KEY", "HOMEWORK_STUDENT_DAILY_LIMIT", "HOMEWORK_SCHOOL_HOURLY_LIMIT", "HOMEWORK_AI_CONCURRENCY",
)


def run_isolated(tmp_path, script: str, flag: bool = True) -> str:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'thelp.sqlite3'}", "PYTHONPATH": str(ROOT)}
    for key in ENV_KEYS:
        env.pop(key, None)
    if flag:
        env["HOMEWORK_ASSISTANT"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=env, text=True, capture_output=True, timeout=240
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout, result.stdout
    return result.stdout


COMMON = r'''
import json
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, update

import app_v924 as legacy
from app import app

replies = []


def sol(answer="7", expression="12-5"):
    return json.dumps({"method": "直接相减", "steps": [{"n": 1, "text": "12 减 5"}, {"n": 2, "text": "得到结果"}],
                       "answer": answer, "expression": expression, "knowledgePoint": "减法"}, ensure_ascii=False)


def fake_ai(db, u, feature, prompt, images=None, timeout=90, rate_check=None):
    db.add(legacy.AIUsageLog(school_id=u.school_id, user_id=u.id, feature=feature, provider="p", model="m", status="ok"))
    db.commit()
    return replies.pop(0)


legacy._ai_call = fake_ai
HELP = legacy.Base.metadata.tables["help_requests"]


def login_and_change(client, username, old_password, new_password):
    login = client.post("/login", json={"username": username, "password": old_password, "remember": False})
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    changed = client.post("/change-password", headers={"Authorization": f"Bearer {token}"},
                          json={"current_password": old_password, "new_password": new_password, "remember": False})
    assert changed.status_code == 200, changed.text
    return changed.json()["token"]


def setup(client):
    th = {"Authorization": "Bearer " + login_and_change(client, "teacher1", "123456", "Teacher1234")}
    sh = {"Authorization": "Bearer " + login_and_change(client, "student1", "123456", "Student1234")}
    session = client.get("/session", headers=sh).json()
    with legacy.SessionLocal() as db:
        school_id = db.get(legacy.User, session["userID"]).school_id
        row = legacy.ai_config_for(db, school_id, True)
        row.enabled = True; row.allow_student_data = True; row.provider = "openai_compatible"
        row.base_url = "https://api.deepseek.com"; row.model = "m"
        db.commit()
    return th, sh, session["userID"], school_id


def backdate():
    with legacy.SessionLocal() as db:
        db.execute(update(HELP).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.execute(update(legacy.AIUsageLog).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.commit()


def make_help(client, sh, text="小明有 12 个苹果，吃了 5 个，还剩几个？"):
    r = client.post("/student/homework/help", headers=sh, json={"questionText": text, "grade": 3})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def make_user(school_id, username, role, grade=None):
    with legacy.SessionLocal() as db:
        user = legacy.User(school_id=school_id, username=username, password_hash=legacy.hash_password("Passw0rd!x"),
                           name=username, role=role, grade=grade)
        db.add(user); db.flush()
        db.add(legacy.UserSecurity(user_id=user.id, must_change_password=False)); db.commit()
        return user.id


def token_of(client, username):
    r = client.post("/login", json={"username": username, "password": "Passw0rd!x", "remember": False})
    return {"Authorization": "Bearer " + r.json()["token"]}
'''


def test_routes_are_404_when_the_flag_is_off(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    assert client.get("/teacher/homework/help", headers=th).status_code == 404
    assert client.get("/teacher/homework/help/1", headers=th).status_code == 404
    assert client.post("/teacher/homework/help/1/resolve", headers=th, json={}).status_code == 404
    assert client.post("/student/homework/help/1/escalate", headers=sh, json={}).status_code == 404
print("OK")
''',
        flag=False,
    )


def test_student_asks_the_teacher_who_sees_the_question_and_the_ai_conversation(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    hid = make_help(client, sh)
    replies.append(sol())
    assert client.post(f"/student/homework/help/{hid}/solve", headers=sh).json()["state"] == "answered"

    # Nothing is escalated yet: the teacher's list is empty.
    assert client.get("/teacher/homework/help", headers=th).json() == {"items": [], "open": 0}

    # The student taps "求助老师" with a note.
    r = client.post(f"/student/homework/help/{hid}/escalate", headers=sh, json={"note": "第二步我看不懂"})
    assert r.status_code == 200 and r.json()["state"] == "escalated"
    again = client.post(f"/student/homework/help/{hid}/escalate", headers=sh, json={"note": "改一下"})
    assert again.json()["studentNote"] == "第二步我看不懂"      # asking twice changes nothing

    listing = client.get("/teacher/homework/help", headers=th).json()
    assert listing["open"] == 1 and len(listing["items"]) == 1
    item = listing["items"][0]
    assert item["id"] == hid and item["studentName"] == "小明" and item["grade"] == 3
    assert item["questionText"].startswith("小明有 12 个苹果") and item["studentNote"] == "第二步我看不懂"
    assert item["reason"] == "student_request" and item["state"] == "escalated" and item["waitMinutes"] >= 0

    detail = client.get(f"/teacher/homework/help/{hid}", headers=th).json()
    roles = [m["role"] for m in detail["conversation"]]
    assert roles == ["student", "ai", "student"]
    ai_text = detail["conversation"][1]["text"]
    assert "直接相减" in ai_text and "答案：7" in ai_text and "程序核对：通过" in ai_text
    assert detail["conversation"][2]["text"] == "第二步我看不懂"

    # The teacher handles it with a note; it moves from "open" to "resolved" and the student sees that.
    done = client.post(f"/teacher/homework/help/{hid}/resolve", headers=th, json={"note": "过来我给你讲"})
    assert done.status_code == 200 and done.json()["state"] == "resolved" and done.json()["resolvedAt"]
    assert client.get("/teacher/homework/help", headers=th).json()["open"] == 0
    assert [x["id"] for x in client.get("/teacher/homework/help?status=resolved", headers=th).json()["items"]] == [hid]
    assert client.get(f"/teacher/homework/help/{hid}", headers=th).json()["conversation"][-1] == {"role": "teacher", "text": "过来我给你讲"}
    assert client.get(f"/student/homework/help/{hid}", headers=sh).json()["state"] == "resolved"
    assert client.post(f"/teacher/homework/help/{hid}/resolve", headers=th, json={}).status_code == 409
print("OK")
''',
    )


def test_a_withheld_wrong_answer_reaches_the_teacher_with_both_attempts(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    hid = make_help(client, sh, text="12-5=?")
    replies.extend([sol(answer="8"), sol(answer="9")])
    body = client.post(f"/student/homework/help/{hid}/solve", headers=sh).json()
    assert body["state"] == "escalated" and body["solution"] is None            # the student sees no answer

    listing = client.get("/teacher/homework/help", headers=th).json()
    assert listing["open"] == 1 and listing["items"][0]["reason"] == "verify_mismatch"
    assert "没有通过核对" in listing["items"][0]["reasonLabel"]
    conv = client.get(f"/teacher/homework/help/{hid}", headers=th).json()["conversation"]
    assert [m["role"] for m in conv] == ["student", "ai", "ai"]
    assert "核对未通过" in conv[1]["text"] and "答案：8" in conv[1]["text"] and "答案：9" in conv[2]["text"]

    # A question that was never answered can also be sent to the teacher straight away.
    backdate()
    hid2 = make_help(client, sh, text="3+4=?")
    r = client.post(f"/student/homework/help/{hid2}/escalate", headers=sh, json={})
    assert r.json()["state"] == "escalated"
    conv2 = client.get(f"/teacher/homework/help/{hid2}", headers=th).json()["conversation"]
    assert [m["role"] for m in conv2] == ["student"]
print("OK")
''',
    )


def test_teachers_only_see_their_own_students_and_roles_are_enforced(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    hid = make_help(client, sh)
    client.post(f"/student/homework/help/{hid}/escalate", headers=sh, json={"note": "x"})

    # A second teacher with a class of their own does not see student1's request.
    t2 = make_user(school_id, "teacher2", "teacher")
    with legacy.SessionLocal() as db:
        cls = legacy.SchoolClass(school_id=school_id, name="二班", grade=3, teacher_id=t2)
        db.add(cls); db.commit()
    t2h = token_of(client, "teacher2")
    assert client.get("/teacher/homework/help", headers=t2h).json() == {"items": [], "open": 0}
    assert client.get(f"/teacher/homework/help/{hid}", headers=t2h).status_code == 404
    assert client.post(f"/teacher/homework/help/{hid}/resolve", headers=t2h, json={}).status_code == 404

    # Roles: students cannot use teacher endpoints, teachers cannot ask for help, anonymous gets 401/403.
    assert client.get("/teacher/homework/help", headers=sh).status_code == 403
    assert client.post(f"/teacher/homework/help/{hid}/resolve", headers=sh, json={}).status_code == 403
    assert client.post(f"/student/homework/help/{hid}/escalate", headers=th, json={}).status_code == 403
    assert client.get("/teacher/homework/help").status_code in (401, 403)

    # Another student cannot escalate someone else's question.
    make_user(school_id, "other9", "student", grade=3)
    oh = token_of(client, "other9")
    assert client.post(f"/student/homework/help/{hid}/escalate", headers=oh, json={}).status_code == 404

    # The teacher with the right class still sees it, and the original is untouched.
    assert client.get("/teacher/homework/help", headers=th).json()["open"] == 1
print("OK")
''',
    )


def test_help_requests_older_than_90_days_are_cleared_when_the_teacher_opens_the_list(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    old = make_help(client, sh, text="旧题")
    backdate()
    fresh = make_help(client, sh, text="新题")
    for hid in (old, fresh):
        client.post(f"/student/homework/help/{hid}/escalate", headers=sh, json={})
    with legacy.SessionLocal() as db:
        db.execute(update(HELP).where(HELP.c.id == old).values(created_at=datetime.utcnow() - timedelta(days=91)))
        db.execute(update(HELP).where(HELP.c.id == fresh).values(created_at=datetime.utcnow() - timedelta(days=89)))
        db.commit()
    listing = client.get("/teacher/homework/help?status=all", headers=th).json()
    assert [x["id"] for x in listing["items"]] == [fresh]
    with legacy.SessionLocal() as db:
        assert db.scalar(select(HELP.c.id).where(HELP.c.id == old)) is None
        assert db.scalar(select(HELP.c.id).where(HELP.c.id == fresh)) == fresh
print("OK")
''',
    )


def test_page_has_the_help_tab_and_the_ask_teacher_button():
    import app  # noqa: F401
    from changying.web.homework_assistant_pages import homework_page_html

    html = homework_page_html()
    assert "求助老师" in html and "求助列表" in html and "/teacher/homework/help" in html
    assert "innerHTML" not in html
