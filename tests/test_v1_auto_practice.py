from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_teacher_can_auto_assign_comprehensive_and_module_practice_to_one_student(tmp_path):
    db_path = tmp_path / "auto-practice.sqlite3"
    script = r"""
from fastapi.testclient import TestClient
from app import app


def login_and_change(client, username, old_password, new_password):
    login = client.post("/login", json={"username":username,"password":old_password,"remember":False})
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    changed = client.post(
        "/change-password",
        headers={"Authorization":f"Bearer {token}"},
        json={"current_password":old_password,"new_password":new_password,"remember":False},
    )
    assert changed.status_code == 200, changed.text
    return changed.json()["token"]


with TestClient(app) as client:
    teacher_token = login_and_change(client, "teacher1", "123456", "Teacher1234")
    student_token = login_and_change(client, "student1", "123456", "Student1234")
    th = {"Authorization":f"Bearer {teacher_token}"}
    sh = {"Authorization":f"Bearer {student_token}"}

    classes = client.get("/teacher/classes", headers=th)
    assert classes.status_code == 200, classes.text
    cid = classes.json()[0]["id"]
    students = client.get(f"/teacher/classes/{cid}/students", headers=th)
    assert students.status_code == 200, students.text
    sid = students.json()[0]["id"]

    extra = [
        ("计算基础", "8 + 7 = ?", ["14","15","16","17"], 1),
        ("计算基础", "16 - 9 = ?", ["5","6","7","8"], 2),
        ("图形认识", "正方形有几条边？", ["3","4","5","6"], 1),
    ]
    for knowledge, text, options, correct in extra:
        created = client.post(
            "/questions",
            headers=th,
            json={
                "grade":3,
                "subject":"数学",
                "textbook":"人教版",
                "semester":"上册",
                "unit":"综合测试",
                "knowledge":knowledge,
                "text":text,
                "options":options,
                "correct_index":correct,
                "explanation":"",
            },
        )
        assert created.status_code == 200, created.text

    options = client.get(f"/teacher/students/{sid}/auto-practice/options", headers=th)
    assert options.status_code == 200, options.text
    payload = options.json()
    math = next(x for x in payload["catalog"] if x["grade"] == 3 and x["subject"] == "数学")
    assert math["questionCount"] >= 4
    assert any(x["name"] == "计算基础" for x in math["modules"])

    comprehensive = client.post(
        f"/teacher/students/{sid}/auto-practice",
        headers=th,
        json={
            "grade":3,
            "subject":"数学",
            "mode":"comprehensive",
            "count":3,
            "due_date":"2026-09-30",
        },
    )
    assert comprehensive.status_code == 200, comprehensive.text
    cdata = comprehensive.json()
    assert cdata["studentID"] == sid
    assert cdata["questionCount"] == 3
    assert len(cdata["knowledgeModules"]) >= 2
    aid = cdata["assignment"]["id"]

    submissions = client.get(f"/teacher/assignments/{aid}/submissions", headers=th)
    assert submissions.status_code == 200, submissions.text
    assert [x["studentID"] for x in submissions.json()] == [sid]

    student_assignments = client.get("/student/assignments", headers=sh)
    assert student_assignments.status_code == 200, student_assignments.text
    assert any(x["id"] == aid for x in student_assignments.json())

    module = client.post(
        f"/teacher/students/{sid}/auto-practice",
        headers=th,
        json={
            "grade":3,
            "subject":"数学",
            "mode":"knowledge",
            "knowledge":"计算基础",
            "count":2,
            "due_date":"2026-09-30",
        },
    )
    assert module.status_code == 200, module.text
    mdata = module.json()
    assert mdata["questionCount"] == 2
    assert mdata["knowledge"] == "计算基础"
    assert mdata["knowledgeModules"] == ["计算基础"]

    unauth = client.get(f"/teacher/students/{sid}/auto-practice/options")
    assert unauth.status_code == 401
"""
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "integration-test-jwt-secret-0123456789abcdef0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "integration-test-commercial-key-0123456789",
            "ENABLE_DEMO_SEED": "1",
            "PYTHONPATH": str(ROOT),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_v1_student_page_exposes_teacher_auto_practice_entry():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert "changying_v1_auto_practice_v1" in html
    assert "自动添加测试/练习" in html
    assert "该科目综合测试" in html
    assert "知识模块练习" in html
    assert "/auto-practice/options" in html
    assert "session.role==='teacher'&&!session.demo" in html
