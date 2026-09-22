from types import SimpleNamespace

from changying.domain.teaching_cycle_read_model import _cycle_kind


def test_cycle_kind_maps_existing_terms_without_inference():
    assert _cycle_kind("秋季") == "term"
    assert _cycle_kind("春季") == "term"
    assert _cycle_kind("寒假") == "winter"
    assert _cycle_kind("暑期") == "summer"


def test_router_preserves_read_only_response_and_is_installed_once(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import changying.web.v1_teaching_cycle as route_module

    app = FastAPI()
    user = SimpleNamespace(school_id=17)
    needs = []
    monkeypatch.setattr(
        route_module,
        "teaching_cycle_rows",
        lambda implementation, db, school_id: [{"schoolID": school_id}],
    )
    implementation = SimpleNamespace(
        app=app,
        current_user=lambda: user,
        get_db=lambda: object(),
        need=lambda actual, *roles: needs.append((actual, roles)),
    )
    route_module.install_v1_teaching_cycle_routes(implementation)
    route_module.install_v1_teaching_cycle_routes(implementation)

    matching = [route for route in app.routes if getattr(route, 'path', None) == "/v1/teaching-cycles"]
    assert len(matching) == 1
    response = TestClient(app).get("/v1/teaching-cycles")
    assert response.status_code == 200
    assert response.json() == {
        "scope": "existing-teaching-program-facts",
        "storageNeutral": True,
        "cycles": [{"schoolID": 17}],
        "count": 1,
    }
    assert needs == [(user, ("teacher", "admin"))]
    assert TestClient(app).post("/v1/teaching-cycles").status_code == 405
