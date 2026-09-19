from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_commercial_order_payment_refund_and_void_roundtrip(tmp_path):
    db_path = tmp_path / "commercial-crud.sqlite3"
    script = r'''
from fastapi.testclient import TestClient
from sqlalchemy import select

import app_v924 as legacy
from app import app


operator_headers = {"X-Commercial-Key": "commercial-test-operator-key-0123456789"}

with TestClient(app) as client:
    denied = client.get("/operator/schools")
    assert denied.status_code == 403, denied.text

    schools = client.get("/operator/schools", headers=operator_headers)
    assert schools.status_code == 200, schools.text
    assert schools.json(), "expected seeded school"
    school_id = schools.json()[0]["schoolID"]

    created = client.post(
        f"/operator/schools/{school_id}/orders",
        headers=operator_headers,
        json={
            "title": "C1 商业订单回归测试",
            "order_type": "service",
            "plan_code": "school_standard",
            "amount_due_yuan": 100,
            "amount_paid_yuan": 20,
            "payment_method": "test",
            "payment_reference": "initial-test-payment",
            "note": "仅用于隔离数据库回归测试",
        },
    )
    assert created.status_code == 200, created.text
    order = created.json()["order"]
    oid = order["id"]
    assert order["amountDueYuan"] == 100
    assert order["amountPaidYuan"] == 20
    assert order["netPaidYuan"] == 20
    assert order["outstandingYuan"] == 80
    assert order["status"] == "partial"

    listed = client.get(
        f"/operator/schools/{school_id}/orders",
        headers=operator_headers,
    )
    assert listed.status_code == 200, listed.text
    assert any(row["id"] == oid for row in listed.json())

    paid = client.post(
        f"/operator/orders/{oid}/payments",
        headers=operator_headers,
        json={
            "amount_yuan": 80,
            "payment_method": "test",
            "payment_reference": "final-test-payment",
            "note": "补齐剩余应收",
        },
    )
    assert paid.status_code == 200, paid.text
    order = paid.json()["order"]
    assert order["status"] == "paid"
    assert order["netPaidYuan"] == 100
    assert order["outstandingYuan"] == 0

    overpay = client.post(
        f"/operator/orders/{oid}/payments",
        headers=operator_headers,
        json={"amount_yuan": 1},
    )
    assert overpay.status_code == 400, overpay.text

    refunded = client.post(
        f"/operator/orders/{oid}/refunds",
        headers=operator_headers,
        json={
            "amount_yuan": 100,
            "payment_method": "test",
            "payment_reference": "full-test-refund",
            "note": "完整退款回归测试",
        },
    )
    assert refunded.status_code == 200, refunded.text
    order = refunded.json()["order"]
    assert order["status"] == "refunded"
    assert order["amountRefundedYuan"] == 100
    assert order["netPaidYuan"] == 0

    voided = client.post(
        f"/operator/orders/{oid}/void",
        headers=operator_headers,
        json={"note": "退款完成后作废回归测试"},
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["order"]["status"] == "void"

    repeated_void = client.post(
        f"/operator/orders/{oid}/void",
        headers=operator_headers,
        json={"note": "重复作废"},
    )
    assert repeated_void.status_code == 200, repeated_void.text
    assert repeated_void.json()["order"]["status"] == "void"

    with legacy.SessionLocal() as db:
        order_row = db.get(legacy.CommercialOrder, oid)
        transactions = db.scalars(
            select(legacy.CommercialPayment).where(
                legacy.CommercialPayment.order_id == oid
            ).order_by(legacy.CommercialPayment.id)
        ).all()
        operations = db.scalars(
            select(legacy.CommercialOperationLog).where(
                legacy.CommercialOperationLog.school_id == school_id
            )
        ).all()
        assert order_row is not None and order_row.status == "void"
        assert [row.payment_type for row in transactions] == [
            "payment",
            "payment",
            "refund",
        ]
        assert [row.amount_cents for row in transactions] == [2000, 8000, 10000]
        actions = {row.action for row in operations}
        assert {"order_create", "order_payment", "order_refund", "order_void"} <= actions
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "commercial-test-signing-material-0123456789abcdef",
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
        "isolated commercial CRUD subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
