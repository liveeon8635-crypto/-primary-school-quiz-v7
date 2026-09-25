from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ios_touch_icon_aliases_are_served(tmp_path):
    db_path = tmp_path / "ios-icons.sqlite3"
    script = r'''
from fastapi.testclient import TestClient
from app import app

with TestClient(app) as client:
    reference = client.get("/icon-180.png")
    assert reference.status_code == 200, reference.text
    for path in ("/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
        assert response.headers["content-type"].startswith("image/png")
        assert response.content == reference.content
'''

    env = os.environ.copy()
    env.update({
        "DATABASE_URL": f"sqlite:///{db_path}",
        "JWT_SECRET": "ios-icon-jwt-secret-0123456789abcdef0123456789abcdef",
        "ENABLE_DEMO_SEED": "1",
        "PYTHONPATH": str(ROOT),
    })
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
        "iOS touch icon subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
