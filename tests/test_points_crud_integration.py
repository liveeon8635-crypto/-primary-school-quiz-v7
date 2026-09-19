from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_classroom_points_record_read_and_undo_roundtrip(tmp_path):
    db_path = tmp_path / "points-crud.sqlite3"
    script = r'''
from fastapi.testclient import TestClient
from sqlalchemy import select

import app_v924 as legacy
from app import app


def headers_for(db, username):
    user = db.scalar(legacy.select(legacy.User).where(legacy.User.username == username))
    assert user is not None
    security = legacy.security_for(db, user)
    security.must_change_password = False
    db.commit()
    return {"Authorization": "Bearer " + legacy.make_token(user, security, False)}


with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        teacher_headers = headers_for(db, "teacher1")
        student_headers = headers_for(db, "student1")

    classes = client.get("/teacher/classes", headers=teacher_headers)
    assert classes.status_code == 200, classes.text
    klass = next(row for row in classes.json() if row["studentCount"] >= 1)

    class_points = client.get(
        f"/teacher/points/classes/{klass['id']}",
        headers=teacher_headers,
    )
    assert class_points.status_code == 200, class_points.text
    student = class_points.json()["students"][0]
    sid = student["id"]
    baseline = student["balance"]

    recorded = client.post(
        "/teacher/points/record",
        headers=teacher_headers,
        json={
            "student_ids": [sid],
            "class_id": klass["id"],
            "points": 5,
            "category": "activity",
            "reason": "C1课堂表现测试",
            "note": "仅用于隔离数据库回归测试",
        },
    )
    assert recorded.status_code == 200, recorded.text
    body = recorded.json()
    assert body["count"] == 1
    assert body["points"] == 5
    record = body["records"][0]
    lid = record["id"]
    assert record["studentID"] == sid
    assert record["points"] == 5
    assert record["source"] == "classroom"

    recent = client.get(
        "/teacher/points/recent",
        headers=teacher_headers,
        params={"class_id": klass["id"], "limit": 20},
    )
    assert recent.status_code == 200, recent.text
    assert any(row["id"] == lid and row["points"] == 5 for row in recent.json())

    student_points = client.get("/student/points", headers=student_headers)
    assert student_points.status_code == 200, student_points.text
    assert student_points.json()["summary"]["balance"] == baseline + 5
    assert any(row["id"] == lid for row in student_points.json()["ledger"])

    undone = client.post(
        f"/teacher/points/ledger/{lid}/undo",
        headers=teacher_headers,
    )
    assert undone.status_code == 200, undone.text
    reversal = undone.json()["record"]
    assert reversal["points"] == -5
    assert reversal["source"] == "reversal"

    after = client.get("/student/points", headers=student_headers)
    assert after.status_code == 200, after.text
    assert after.json()["summary"]["balance"] == baseline

    duplicate_undo = client.post(
        f"/teacher/points/ledger/{lid}/undo",
        headers=teacher_headers,
    )
    assert duplicate_undo.status_code == 400, duplicate_undo.text

    with legacy.SessionLocal() as db:
        original = db.get(legacy.PointLedger, lid)
        reversal_row = db.scalar(
            select(legacy.PointLedger).where(
                legacy.PointLedger.reversal_of_id == lid
            )
        )
        assert original is not None and original.reversed is True
        assert reversal_row is not None
        assert reversal_row.points == -5
        assert reversal_row.source == "reversal"
        assert reversal_row.student_id == sid
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "points-test-only-signing-material-0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "points-test-only-operator-material-012345",
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

    assert result.returncode == 0, (
        "isolated points CRUD subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
