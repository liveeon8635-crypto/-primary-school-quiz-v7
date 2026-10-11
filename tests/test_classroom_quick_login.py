from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_isolated(tmp_path, script: str, *, flag: bool) -> None:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'quick-login.sqlite3'}",
        "PYTHONPATH": str(ROOT),
    }
    env.pop("CLASSROOM_QUICK_LOGIN", None)
    if flag:
        env["CLASSROOM_QUICK_LOGIN"] = "1"
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


SETUP = r'''
import json
from datetime import datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select, update

import app_v924 as legacy
from app import app


def token_for(db, user):
    sec = legacy.security_for(db, user)
    sec.must_change_password = False
    db.commit()
    return {"Authorization": "Bearer " + legacy.make_token(user, sec, False)}


def make_student(db, teacher, cls, n, must_change=False):
    u = legacy.User(school_id=teacher.school_id, username=f"qs{n:02d}",
                    password_hash=legacy.hash_password("Abcdef12"),
                    name=f"测试姓名{n:02d}", role="student", grade=5)
    db.add(u); db.flush()
    db.add(legacy.UserSecurity(user_id=u.id, must_change_password=must_change, failed_login_count=0))
    db.add(legacy.ClassStudent(class_id=cls.id, student_id=u.id))
    return u


def build_session(client, db_ctx):
    """Returns (teacher headers, outsider headers, student ids, session id)."""
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        th = token_for(db, teacher)
        cls = db.scalar(select(legacy.SchoolClass).where(
            legacy.SchoolClass.school_id == teacher.school_id,
            legacy.SchoolClass.teacher_id == teacher.id))
        # Demo students are in this class already; archive them so seats are deterministic.
        for row in db.scalars(select(legacy.ClassStudent).where(legacy.ClassStudent.class_id == cls.id)).all():
            db.delete(row)
        db.flush()
        students = [make_student(db, teacher, cls, i) for i in range(1, 5)]
        locked = make_student(db, teacher, cls, 5, must_change=True)
        other = legacy.User(school_id=teacher.school_id, username="other_t",
                            password_hash=legacy.hash_password("Abcdef12"), name="另一位老师",
                            role="teacher", grade=None)
        db.add(other); db.flush()
        db.add(legacy.UserSecurity(user_id=other.id, must_change_password=False, failed_login_count=0))
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
            title="讲义", selected_knowledge_json=json.dumps(["小数乘法"], ensure_ascii=False),
            selected_question_ids_json=json.dumps([q.id]), teacher_notes="", content_text="x",
            created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
        out = token_for(db, db.get(legacy.User, other.id))
        ids = [s.id for s in students] + [locked.id]
        db.commit()
        aid = a.id
    created = client.post(f"/teacher/assignments/{aid}/classroom-session", headers=th, json={}).json()
    sid = created["session"]["id"]
    return th, out, ids, sid
'''


def test_quick_login_end_to_end_rules(tmp_path):
    run_isolated(
        tmp_path,
        SETUP
        + r'''
with TestClient(app) as client:
    th, outsider, ids, sid = build_session(client, None)
    base = f"/teacher/classroom-sessions/{sid}/join-code"

    # Not started yet -> no code can be created.
    assert client.post(base, headers=th).status_code == 400
    assert client.post(f"/teacher/classroom-sessions/{sid}/state", headers=th, json={"status": "active"}).status_code == 200

    # Access control for the teacher endpoints.
    assert client.get(base).status_code == 401
    assert client.get(base, headers=outsider).status_code == 404

    made = client.post(base, headers=th)
    assert made.status_code == 200, made.text
    info = made.json()
    code = info["code"]
    assert len(code) == 6 and code.isdigit()
    assert [s["seat"] for s in info["seats"]] == [1, 2, 3, 4, 5]
    assert info["seats"][0]["studentName"] == "测试姓名01"           # teacher sees the mapping
    assert info["seats"][4]["needsPassword"] is True

    # (privacy) the student-facing lookup has numbers only.
    look = client.post("/classroom-join/lookup", json={"code": code})
    assert look.status_code == 200, look.text
    body = look.json()
    assert [s["seat"] for s in body["seats"]] == [1, 2, 3, 4, 5]
    assert all(set(s) == {"seat", "taken", "needsPassword"} for s in body["seats"])
    assert "测试姓名" not in look.text and "qs0" not in look.text and "studentID" not in look.text

    # Login on device A, seat 1.
    A, Bdev = "device-aaaaaaaa", "device-bbbbbbbb"
    login = client.post("/classroom-join/login", json={"code": code, "seat": 1, "device_id": A})
    assert login.status_code == 200, login.text
    data = login.json()
    assert data["role"] == "student" and data["userID"] == ids[0] and data["mustChangePassword"] is False
    auth = {"Authorization": "Bearer " + data["token"]}
    # The token works through the normal auth chain (including the must-change-password gate).
    assert client.get("/session", headers=auth).status_code == 200
    assert client.get("/student/classroom-quick-checks", headers=auth).status_code == 200
    # It expires with the code, not 12 hours later.
    claims = jwt.decode(data["token"], legacy.JWT_SECRET, algorithms=[legacy.JWT_ALG])
    assert abs(claims["exp"] - (datetime.utcnow() + timedelta(minutes=180)).timestamp()) < 120

    # (c) the seat is taken: a second device is refused, the same device may resume.
    busy = client.post("/classroom-join/login", json={"code": code, "seat": 1, "device_id": Bdev})
    assert busy.status_code == 409, busy.text
    resume = client.post("/classroom-join/login", json={"code": code, "seat": 1, "device_id": A})
    assert resume.status_code == 200
    # Resuming issues a fresh claim: the earlier token is superseded, the new one works.
    assert client.get("/session", headers=auth).status_code == 401
    auth = {"Authorization": "Bearer " + resume.json()["token"]}
    assert client.get("/session", headers=auth).status_code == 200
    assert client.post("/classroom-join/lookup", json={"code": code}).json()["seats"][0]["taken"] is True
    # Another seat on device B is fine.
    assert client.post("/classroom-join/login", json={"code": code, "seat": 2, "device_id": Bdev}).status_code == 200

    # Students who still have an initial password are not let in (existing gate is not bypassed).
    locked = client.post("/classroom-join/login", json={"code": code, "seat": 5, "device_id": "device-cccccccc"})
    assert locked.status_code == 403 and "密码" in locked.text
    assert client.post("/classroom-join/login", json={"code": code, "seat": 99, "device_id": A}).status_code == 404

    # Logout releases the seat; then device B can take it.
    out = client.post("/classroom-join/logout", headers=auth)
    assert out.status_code == 200 and out.json()["released"] >= 1
    # (revocation) the token issued before logout is dead immediately, not 3 hours later.
    revoked = client.get("/session", headers=auth)
    assert revoked.status_code == 401 and "已失效" in revoked.text, revoked.text
    second = client.post("/classroom-join/login", json={"code": code, "seat": 1, "device_id": Bdev})
    assert second.status_code == 200
    auth_b = {"Authorization": "Bearer " + second.json()["token"]}
    assert client.get("/session", headers=auth_b).status_code == 200
    # Taking the same seat again must not revive the old token (per-claim nonce).
    assert client.get("/session", headers=auth).status_code == 401
    # Teacher can force-release a seat -> that student's token stops working at once.
    rel = client.post(f"{base}/seats/1/release", headers=th)
    assert rel.status_code == 200 and rel.json()["seats"][0]["taken"] is False
    assert client.get("/session", headers=auth_b).status_code == 401
    third = client.post("/classroom-join/login", json={"code": code, "seat": 1, "device_id": A})
    assert third.status_code == 200
    auth = {"Authorization": "Bearer " + third.json()["token"]}
    assert client.get("/session", headers=auth).status_code == 200
    # Regenerating the code (new class code) revokes tokens issued under the old one.
    assert client.post(base, headers=th).status_code == 200
    assert client.get("/session", headers=auth).status_code == 401
    code = client.get(base, headers=th).json()["code"]
    again = client.post("/classroom-join/login", json={"code": code, "seat": 1, "device_id": A})
    assert again.status_code == 200
    auth = {"Authorization": "Bearer " + again.json()["token"]}

    # Students cannot use the teacher endpoints.
    assert client.get(base, headers=auth).status_code == 403

    # (b) expiry: past expiry -> lookup and login fail.
    with legacy.SessionLocal() as db:
        codes = legacy.Base.metadata.tables["classroom_join_codes"]
        db.execute(update(codes).values(expires_at=datetime.utcnow() - timedelta(minutes=1)))
        db.commit()
    assert client.post("/classroom-join/lookup", json={"code": code}).status_code == 404
    assert client.post("/classroom-join/login", json={"code": code, "seat": 3, "device_id": A}).status_code == 404

    # A new code works; finishing the class (下课) invalidates it; revoking invalidates it.
    code2 = client.post(base, headers=th).json()["code"]
    assert client.post("/classroom-join/lookup", json={"code": code2}).status_code == 200
    assert client.delete(base, headers=th).status_code == 200
    assert client.post("/classroom-join/lookup", json={"code": code2}).status_code == 404
    code3 = client.post(base, headers=th).json()["code"]
    segid = client.get(f"/teacher/classroom-sessions/{sid}", headers=th).json()["segments"][0]["id"]
    assert client.post(f"/teacher/classroom-sessions/{sid}/segments/{segid}/start", headers=th).status_code == 200
    assert client.post(f"/teacher/classroom-sessions/{sid}/segments/{segid}/complete", headers=th).status_code == 200
    live_login = client.post("/classroom-join/login", json={"code": code3, "seat": 2, "device_id": A})
    assert live_login.status_code == 200
    live_auth = {"Authorization": "Bearer " + live_login.json()["token"]}
    assert client.get("/session", headers=live_auth).status_code == 200
    assert client.post(f"/teacher/classroom-sessions/{sid}/state", headers=th, json={"status": "completed"}).status_code == 200
    assert client.post("/classroom-join/lookup", json={"code": code3}).status_code == 404
    # Finishing the class also kills tokens that were already issued.
    assert client.get("/session", headers=live_auth).status_code == 401
    print("OK")
''',
        flag=True,
    )


def test_wrong_codes_are_rate_limited(tmp_path):
    run_isolated(
        tmp_path,
        SETUP
        + r'''
with TestClient(app) as client:
    th, outsider, ids, sid = build_session(client, None)
    client.post(f"/teacher/classroom-sessions/{sid}/state", headers=th, json={"status": "active"})
    real = client.post(f"/teacher/classroom-sessions/{sid}/join-code", headers=th).json()["code"]
    wrong = "000000" if real != "000000" else "111111"
    statuses = [client.post("/classroom-join/lookup", json={"code": wrong}).status_code for _ in range(25)]
    assert statuses[:20] == [404] * 20, statuses
    assert 429 in statuses[20:], statuses
    # Once limited, even the right code is refused for this client until the window passes.
    assert client.post("/classroom-join/lookup", json={"code": real}).status_code == 429
    print("OK")
''',
        flag=True,
    )


def test_pages_and_exit_button_are_tablet_ready_and_inert_until_quick_login(tmp_path):
    run_isolated(
        tmp_path,
        SETUP
        + r'''
from changying.web import v1 as v1_module

with TestClient(app) as client:
    join = client.get("/join")
    assert join.status_code == 200
    html = join.text
    assert "user-scalable=no" in html and "maximum-scale=1" in html and "touch-action:manipulation" in html
    assert "gesturestart" in html                       # iOS pinch-zoom block
    assert "orientation:landscape" in html
    assert "min-height:3.4em" in html                   # large touch targets
    assert "测试姓名" not in html
    v1html = v1_module.v1_html()
    assert "changying_classroom_quick_login_v1" in v1html
    assert 'id="cy-session-join-code"' in v1html
    # The exit button only mounts when the quick-login marker is present, and wipes storage + cookies.
    assert "sessionStorage.getItem('cyQuickJoin')!=='1'" in v1html
    assert "localStorage.clear()" in v1html and "sessionStorage.clear()" in v1html
    assert "document.cookie" in v1html and "/classroom-join/logout" in v1html
    assert "user-scalable=no" in v1html and "label.row{min-height:64px" in v1html
    teacher_page = client.get("/v1/classroom-join-code/1").text
    assert "测试姓名" not in teacher_page and "var SID=1" in teacher_page
    print("OK")
''',
        flag=True,
    )


def test_feature_flag_off_changes_nothing(tmp_path):
    run_isolated(
        tmp_path,
        SETUP
        + r'''
from changying.web import v1 as v1_module

assert "classroom_join_codes" not in legacy.Base.metadata.tables
assert "classroom_seat_sessions" not in legacy.Base.metadata.tables
with TestClient(app) as client:
    for method, path in (("GET", "/join"), ("POST", "/classroom-join/lookup"),
                         ("POST", "/classroom-join/login"), ("POST", "/classroom-join/logout"),
                         ("GET", "/v1/classroom-join-code/1"),
                         ("GET", "/teacher/classroom-sessions/1/join-code")):
        r = client.request(method, path, json={})
        assert r.status_code in (404, 405), (path, r.status_code)
    assert "changying_classroom_quick_login_v1" not in v1_module.v1_html()
    assert 'id="cy-session-join-code"' not in v1_module.v1_html()
    # The normal username/password login is untouched.
    login = client.post("/login", json={"username": "teacher1", "password": "123456", "remember": False})
    assert login.status_code == 200 and login.json()["role"] == "teacher"
    bad = client.post("/login", json={"username": "teacher1", "password": "wrong", "remember": False})
    assert bad.status_code == 401
    print("OK")
''',
        flag=False,
    )
