from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_retired_service_worker_endpoint_stays_valid(tmp_path):
    db_path = tmp_path / "retired-sw.sqlite3"
    script = r'''
from fastapi.testclient import TestClient
from app import app

with TestClient(app) as client:
    response = client.get("/sw.js?v=843")
    assert response.status_code == 200, response.text
    assert "self.registration.unregister()" in response.text
    assert "changying-fuxue-" in response.text
    assert "no-store" in response.headers.get("cache-control", "")
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "retired-sw-jwt-secret-0123456789abcdef0123456789abcdef",
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
        "retired service-worker subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
