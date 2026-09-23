from fastapi.testclient import TestClient

from changying.production import app


def test_operator_console_renders_in_production():
    client = TestClient(app)
    response = client.get("/operator-console")

    assert response.status_code == 200
    assert "商业运营控制台" in response.text
    assert "COMMERCIAL_ADMIN_KEY" in response.text
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
