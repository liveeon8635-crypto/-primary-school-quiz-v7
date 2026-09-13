from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200


def test_homepage_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "长缨辅学" in response.text


def test_manifest_is_valid_json():
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")
    payload = response.json()
    assert payload["name"] == "长缨辅学"
    assert payload["start_url"] == "/?source=pwa"
    assert any(icon.get("sizes") == "192x192" for icon in payload.get("icons", []))
