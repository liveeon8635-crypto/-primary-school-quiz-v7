"""Offline entry: the retired /sw.js is replaced by a small, data-safe fallback.

These tests go through the real application entry (``app.py`` -> ``changying.production``)
so that the wiring in ``changying/compat/legacy.py`` is exercised, not just the helpers.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from changying.web.offline_capability import (
    OFFLINE_PRACTICE_PATH,
    OFFLINE_SW_JS,
    OFFLINE_SW_PATH,
    V1_OFFLINE_MARKER,
    install_offline_capability,
    patch_v1_offline_capability,
)

ROOT = Path(__file__).resolve().parents[1]


def test_offline_worker_is_es5_and_only_falls_back_to_the_practice_page():
    body = OFFLINE_SW_JS

    assert "addEventListener('install'" in body
    assert "addEventListener('activate'" in body
    assert "addEventListener('fetch'" in body
    assert f"'{OFFLINE_PRACTICE_PATH}'" in body
    # Only page navigations may be answered from the cache.
    assert "request.mode === 'navigate'" in body
    # No ES6 syntax: iOS 12 Safari runs this file as-is.
    assert "=>" not in body
    assert " const " not in body
    assert " let " not in body


def test_practice_page_is_self_contained():
    from changying.web.offline_capability import OFFLINE_PRACTICE_HTML

    page = OFFLINE_PRACTICE_HTML
    assert "离线练习" in page
    assert "0.4 × 3" in page
    # No network access of any kind on the offline page.
    assert "fetch(" not in page
    assert "XMLHttpRequest" not in page
    assert "/api/" not in page


def test_v1_patch_is_idempotent_and_needs_a_body_marker():
    html = "<html><body><div id='screen'></div></body></html>"
    patched = patch_v1_offline_capability(html)

    assert V1_OFFLINE_MARKER in patched
    assert "navigator.serviceWorker.register('/offline-sw.js'" in patched
    assert patch_v1_offline_capability(patched) == patched

    with pytest.raises(RuntimeError):
        patch_v1_offline_capability("<html></html>")


def test_install_registers_both_routes_once():
    implementation = SimpleNamespace(app=FastAPI())

    assert install_offline_capability(implementation) is True
    assert install_offline_capability(implementation) is True

    client = TestClient(implementation.app)
    worker = client.get(OFFLINE_SW_PATH)
    assert worker.status_code == 200
    assert worker.headers["x-changying-sw"] == "offline-v1"
    assert worker.headers["cache-control"] == "no-cache"
    assert worker.headers["service-worker-allowed"] == "/"

    page = client.get(OFFLINE_PRACTICE_PATH)
    assert page.status_code == 200
    assert page.headers["x-changying-offline"] == "offline-v1"
    assert "离线练习" in page.text


def test_real_app_serves_offline_entry_and_registers_the_worker(tmp_path):
    script = r'''
from fastapi.testclient import TestClient

from app import app
from changying.web import v1 as v1_module

client = TestClient(app)
worker = client.get("/offline-sw.js")
assert worker.status_code == 200, worker.status_code
assert worker.headers["x-changying-sw"] == "offline-v1", worker.headers
page = client.get("/offline-practice")
assert page.status_code == 200, page.status_code
assert "离线练习" in page.text
shell = v1_module.v1_html()
assert "changying_v1_offline_capability_v1" in shell
assert "register('/offline-sw.js'" in shell
print("OK")
'''
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'offline.sqlite3'}",
        "PYTHONPATH": str(ROOT),
    }
    env.setdefault("ENABLE_DEMO_SEED", "0")

    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=env, text=True, capture_output=True, timeout=240
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
