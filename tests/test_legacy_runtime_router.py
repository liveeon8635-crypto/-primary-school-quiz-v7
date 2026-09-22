from fastapi.testclient import TestClient

import app_v924 as legacy


PROBE_PATHS = (
    "/probe-v1070",
    "/probe-v1063",
    "/probe-v1062",
    "/probe-v1061",
    "/probe-v1060",
    "/probe-v1050",
    "/probe-v1040",
    "/probe-v1030",
    "/probe-v1020",
    "/probe-v1010",
    "/probe-v1000",
    "/probe-v926",
    "/probe-v925",
    "/probe-v924",
    "/probe-v923",
    "/probe-v922",
    "/probe-v921",
    "/probe-v920",
    "/probe-v910",
    "/probe-v900",
    "/probe-v890",
    "/probe-v880",
    "/probe-v874",
    "/probe-v873",
    "/probe-v872",
    "/probe-v871",
    "/probe-v870",
    "/probe-v863",
    "/probe-v862",
    "/probe-v861",
    "/probe-v860",
    "/probe-v843",
    "/probe-v842",
    "/probe-v841",
    "/probe-v840",
    "/probe-v831",
    "/probe-v820",
    "/probe-v810",
    "/probe-v790",
    "/probe-v740",
    "/probe-v730",
)


def _matching_route_objects(path: str):
    found = {}
    for route in legacy.app.routes:
        for child in getattr(getattr(route, "original_router", route), "routes", [route]):
            if getattr(child, "path", None) == path:
                found[id(child)] = child
    return list(found.values())


def test_legacy_runtime_router_keeps_get_only_route_contracts():
    expected = ("/version", "/release", *PROBE_PATHS)
    for path in expected:
        matching = _matching_route_objects(path)
        assert len(matching) == 1, (path, matching)
        assert set(matching[0].methods or []) == {"GET"}, path


def test_legacy_runtime_router_keeps_public_responses():
    client = TestClient(legacy.app)

    version = client.get("/version")
    assert version.status_code == 200
    assert version.json()["version"] == legacy.APP_VERSION
    assert version.json()["status"] == "ok"

    release = client.get("/release")
    assert release.status_code == 200
    assert release.json()["product"] == "长缨辅学"
    assert release.json()["version"] == legacy.APP_VERSION

    for path in PROBE_PATHS:
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
        body = response.json()
        assert body["ok"] is True, (path, body)

    for path in ("/version", "/release", "/probe-v1070", "/probe-v730"):
        assert client.post(path).status_code == 405, path
