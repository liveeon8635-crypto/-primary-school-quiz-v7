from fastapi import FastAPI
from fastapi.testclient import TestClient

from changying.web.health_revision import install_health_revision_route, render_git_commit


def test_render_git_commit_accepts_exact_sha_only():
    sha = "A" * 40
    assert render_git_commit({"RENDER_GIT_COMMIT": sha}) == sha.lower()
    assert render_git_commit({"RENDER_GIT_COMMIT": "abc123"}) is None
    assert render_git_commit({}) is None


def test_health_revision_exposes_runtime_commit(monkeypatch):
    sha = "1" * 40
    monkeypatch.setenv("RENDER_GIT_COMMIT", sha)
    app = FastAPI()
    install_health_revision_route(app)
    client = TestClient(app)

    response = client.get("/health/revision")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": sha}


def test_health_revision_is_safe_when_render_commit_missing(monkeypatch):
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    app = FastAPI()
    install_health_revision_route(app)
    install_health_revision_route(app)
    client = TestClient(app)

    response = client.get("/health/revision")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": None}
