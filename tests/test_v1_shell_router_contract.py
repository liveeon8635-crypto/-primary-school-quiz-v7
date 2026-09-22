from fastapi import FastAPI
from fastapi.testclient import TestClient

from changying.web.v1 import V1_PATHS, install_v1_routes
from changying.web.v1_unified_tools import V1_UNIFIED_TOOL_PATH, install_v1_unified_tool_route


def _route_methods(app: FastAPI, expected: set[str]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for route in app.routes:
        for child in getattr(getattr(route, "original_router", route), "routes", [route]):
            path = getattr(child, "path", None)
            if path in expected:
                found[path] = set(child.methods or [])
    return found


def test_v1_shell_and_unified_tool_routes_are_get_only_and_idempotent():
    app = FastAPI()

    install_v1_routes(app)
    install_v1_routes(app)
    install_v1_unified_tool_route(app)
    install_v1_unified_tool_route(app)

    expected = set(V1_PATHS) | {"/v1/version", V1_UNIFIED_TOOL_PATH}
    routes = _route_methods(app, expected)

    assert set(routes) == expected
    assert all(methods == {"GET"} for methods in routes.values())

    client = TestClient(app)
    for path in V1_PATHS:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["X-Changying-V1"]
    assert client.get("/v1/version").status_code == 200
    tool = client.get(V1_UNIFIED_TOOL_PATH)
    assert tool.status_code == 200
    assert "统一功能工作区" in tool.text

    assert client.post("/v1").status_code == 405
    assert client.post("/v1/version").status_code == 405
    assert client.post(V1_UNIFIED_TOOL_PATH).status_code == 405
