import os

from fastapi.testclient import TestClient

from app import app
from changying.web import runtime_probe

client = TestClient(app)


def test_snapshot_describes_this_process():
    snapshot = runtime_probe.runtime_snapshot()

    assert snapshot["pid"] == os.getpid()
    assert isinstance(snapshot["uptimeSeconds"], int)
    assert snapshot["uptimeSeconds"] >= 0
    assert snapshot["startedAt"].endswith("Z")
    if "rssMB" in snapshot:
        assert snapshot["rssMB"] > 0


def test_runtime_probe_route_reports_uptime_so_a_restart_is_visible():
    body = client.get("/health/runtime").json()

    assert body["status"] == "ok"
    assert body["pid"] == os.getpid()
    assert body["uptimeSeconds"] >= 0


def test_runtime_probe_uptime_keeps_growing():
    first = client.get("/health/runtime").json()["uptimeSeconds"]
    second = client.get("/health/runtime").json()["uptimeSeconds"]

    assert second >= first


def test_fast_health_probe_is_still_the_render_readiness_path():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
