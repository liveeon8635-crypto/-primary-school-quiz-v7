from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from changying.services.commercial_usage import billing_month_window


ROOT = Path(__file__).resolve().parents[1]


def test_billing_month_window_uses_school_local_calendar_month():
    window = billing_month_window("2035-02")
    assert window["key"] == "2035-02"
    assert window["startUtc"] == datetime(2035, 1, 31, 16, 0, 0)
    assert window["endUtc"] == datetime(2035, 2, 28, 16, 0, 0)
    assert window["startLocal"] == "2035-02-01 00:00"
    assert window["endLocalExclusive"] == "2035-03-01 00:00"


def test_operator_usage_metering_is_read_only_and_month_bound(tmp_path):
    db_path = tmp_path / "usage-metering.sqlite3"
    script = r'''
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app_v924 as legacy
from app import app


operator_headers = {"X-Commercial-Key": "commercial-test-operator-key-0123456789"}

with TestClient(app) as client:
    denied = client.get("/operator/usage-metering?month=2035-02")
    assert denied.status_code == 403, denied.text

    with legacy.SessionLocal() as db:
        school = db.scalars(select(legacy.School).order_by(legacy.School.id)).first()
        assert school is not None
        user = db.scalars(
            select(legacy.User)
            .where(legacy.User.school_id == school.id)
            .order_by(legacy.User.id)
        ).first()
        assert user is not None
        school_id = school.id
        db.add(
            legacy.AIUsageLog(
                school_id=school_id,
                user_id=user.id,
                feature="usage-metering-regression",
                provider="test-provider",
                model="test-model",
                status="ok",
                prompt_chars=120,
                output_chars=80,
                input_tokens=123,
                output_tokens=45,
                latency_ms=10,
                error="",
                created_at=datetime(2035, 2, 10, 4, 0, 0),
            )
        )
        db.commit()
        ai_rows_before = db.scalar(
            select(func.count()).select_from(legacy.AIUsageLog)
        )
        orders_before = db.scalar(
            select(func.count()).select_from(legacy.CommercialOrder)
        )
        payments_before = db.scalar(
            select(func.count()).select_from(legacy.CommercialPayment)
        )

    response = client.get(
        "/operator/usage-metering?month=2035-02",
        headers=operator_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["meterVersion"] == "usage-metering-v1"
    assert payload["period"]["month"] == "2035-02"
    row = next(x for x in payload["schools"] if x["schoolID"] == school_id)
    assert row["ai"]["calls"] == 1
    assert row["ai"]["successCalls"] == 1
    assert row["ai"]["failedCalls"] == 0
    assert row["ai"]["inputTokens"] == 123
    assert row["ai"]["outputTokens"] == 45
    assert row["ai"]["totalTokens"] == 168
    assert row["billing"] == {
        "measurementOnly": True,
        "autoCharge": False,
        "priceCalculated": False,
        "source": "existing-production-facts",
    }
    assert payload["billing"]["autoCharge"] is False
    assert payload["billing"]["priceCalculated"] is False
    assert "teachers" in row["scaleCurrent"]
    assert "submissions" in row["activity"]
    assert "currentBytes" in row["storage"]

    school_response = client.get(
        f"/operator/schools/{school_id}/usage-metering?month=2035-02",
        headers=operator_headers,
    )
    assert school_response.status_code == 200, school_response.text
    assert school_response.json()["ai"]["totalTokens"] == 168

    outside = client.get(
        f"/operator/schools/{school_id}/usage-metering?month=2035-03",
        headers=operator_headers,
    )
    assert outside.status_code == 200, outside.text
    assert outside.json()["ai"]["calls"] == 0
    assert outside.json()["ai"]["totalTokens"] == 0

    invalid = client.get(
        "/operator/usage-metering?month=2035-13",
        headers=operator_headers,
    )
    assert invalid.status_code == 400, invalid.text

    missing = client.get(
        "/operator/schools/999999/usage-metering?month=2035-02",
        headers=operator_headers,
    )
    assert missing.status_code == 404, missing.text

    with legacy.SessionLocal() as db:
        ai_rows_after = db.scalar(
            select(func.count()).select_from(legacy.AIUsageLog)
        )
        orders_after = db.scalar(
            select(func.count()).select_from(legacy.CommercialOrder)
        )
        payments_after = db.scalar(
            select(func.count()).select_from(legacy.CommercialPayment)
        )
        assert ai_rows_after == ai_rows_before
        assert orders_after == orders_before
        assert payments_after == payments_before
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "usage-metering-test-signing-material-0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "commercial-test-operator-key-0123456789",
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
        "isolated usage metering subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
