from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_new_school_gets_point_rules_during_operator_creation_not_later_restart(tmp_path):
    db_path = tmp_path / "school-bootstrap.sqlite3"
    script = r'''
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app import app
import app_v924 as legacy

with TestClient(app) as client:
    response = client.post(
        "/operator/schools",
        headers={"X-Commercial-Key": "bootstrap-commercial-key-0123456789"},
        json={
            "school_name": "正式客户学校",
            "school_code": "customer-001",
            "admin_name": "客户管理员",
            "admin_username": "customer-admin",
            "admin_password": "Customer1234",
            "plan_code": "school_basic",
            "status": "trial",
        },
    )
    assert response.status_code == 200, response.text
    school_id = response.json()["school"]["schoolID"]

    with legacy.SessionLocal() as db:
        count = db.scalar(
            select(func.count()).select_from(legacy.PointRule).where(
                legacy.PointRule.school_id == school_id
            )
        )
        assert count == len(legacy.DEFAULT_POINT_RULES)

        # A legacy compatibility pass with production-style create_missing=False
        # must not mutate a newly created empty school.
        empty = legacy.School(name="无隐式模板学校", code="no-implicit-rules")
        db.add(empty)
        db.commit()
        db.refresh(empty)
        legacy.v750_seed_point_rules(db, create_missing=False)
        after = db.scalar(
            select(func.count()).select_from(legacy.PointRule).where(
                legacy.PointRule.school_id == empty.id
            )
        )
        assert after == 0
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "bootstrap-jwt-secret-0123456789abcdef0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "bootstrap-commercial-key-0123456789",
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
        timeout=150,
        check=False,
    )

    assert result.returncode == 0, (
        "school bootstrap subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
