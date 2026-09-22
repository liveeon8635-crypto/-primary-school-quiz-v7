from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _included_paths(app, expected):
    return [
        child
        for route in app.routes
        for child in getattr(getattr(route, "original_router", route), "routes", [route])
        if getattr(child, "path", None) in expected
    ]


def test_learning_evidence_access_router_is_get_only_and_installed_once(monkeypatch):
    import changying.web.v1_learning_evidence_access as route_module

    app = FastAPI()
    user = SimpleNamespace(id=7, school_id=17, role="teacher")
    student = SimpleNamespace(id=23, name="测试学生")
    implementation = SimpleNamespace(
        app=app,
        current_user=lambda: user,
        get_db=lambda: object(),
    )
    monkeypatch.setattr(
        route_module,
        "_authorized_student",
        lambda implementation, db, actual_user, sid: student,
    )
    monkeypatch.setattr(
        route_module,
        "legacy_student_evidence",
        lambda implementation, db, student_id, school_id: [],
    )
    monkeypatch.setattr(
        route_module,
        "student_evidence_snapshot",
        lambda items: {"sampleCount": 0, "dimensions": []},
    )
    monkeypatch.setattr(
        route_module,
        "growth_profile_learning_evidence",
        lambda snapshot: {"sampleCount": 0, "dimensions": []},
    )
    monkeypatch.setattr(
        route_module,
        "learning_evidence_for_role",
        lambda evidence, role: {**evidence, "viewerRole": role},
    )

    route_module.install_v1_learning_evidence_access_routes(implementation)
    route_module.install_v1_learning_evidence_access_routes(implementation)

    expected = {"/v1/students/{sid}/learning-evidence"}
    matching = _included_paths(app, expected)
    assert {route.path for route in matching} == expected

    client = TestClient(app)
    response = client.get("/v1/students/23/learning-evidence")
    assert response.status_code == 200
    assert response.json() == {
        "sampleCount": 0,
        "dimensions": [],
        "viewerRole": "teacher",
    }
    assert client.post("/v1/students/23/learning-evidence").status_code == 405


def test_evidence_coverage_router_is_get_only_and_installed_once(monkeypatch):
    import changying.web.v22_evidence_coverage as route_module

    app = FastAPI()
    user = SimpleNamespace(id=7, school_id=17, role="teacher")
    implementation = SimpleNamespace(
        app=app,
        current_user=lambda: user,
        get_db=lambda: object(),
    )
    monkeypatch.setattr(
        route_module,
        "teacher_evidence_coverage",
        lambda implementation, db, actual_user, class_id=None: {
            "classID": class_id,
            "viewerRole": actual_user.role,
            "automaticDiagnosis": False,
        },
    )

    route_module.install_v22_evidence_coverage_routes(implementation)
    route_module.install_v22_evidence_coverage_routes(implementation)

    expected = {"/v2/teacher/evidence-coverage"}
    matching = _included_paths(app, expected)
    assert {route.path for route in matching} == expected

    client = TestClient(app)
    response = client.get("/v2/teacher/evidence-coverage?class_id=9")
    assert response.status_code == 200
    assert response.json() == {
        "classID": 9,
        "viewerRole": "teacher",
        "automaticDiagnosis": False,
    }
    assert client.post("/v2/teacher/evidence-coverage").status_code == 405


def test_stage_evidence_router_is_get_only_and_installed_once(monkeypatch):
    import changying.web.v27_stage_evidence_comparison as route_module

    app = FastAPI()
    user = SimpleNamespace(id=7, school_id=17, role="teacher")
    student = SimpleNamespace(id=23, name="测试学生")
    implementation = SimpleNamespace(
        app=app,
        current_user=lambda: user,
        get_db=lambda: object(),
    )
    monkeypatch.setattr(
        route_module,
        "_authorized_student",
        lambda implementation, db, actual_user, sid: student,
    )
    monkeypatch.setattr(
        route_module,
        "stage_evidence_comparison",
        lambda implementation, db, actual_student, school_id, viewer_role: {
            "student": {"id": int(actual_student.id)},
            "schoolID": school_id,
            "viewerRole": viewer_role,
            "comparison": {"automaticMasteryJudgment": False},
        },
    )

    route_module.install_v27_stage_evidence_routes(implementation)
    route_module.install_v27_stage_evidence_routes(implementation)

    expected = {"/v2/students/{sid}/stage-evidence-comparison"}
    matching = _included_paths(app, expected)
    assert {route.path for route in matching} == expected

    client = TestClient(app)
    response = client.get("/v2/students/23/stage-evidence-comparison")
    assert response.status_code == 200
    assert response.json() == {
        "student": {"id": 23},
        "schoolID": 17,
        "viewerRole": "teacher",
        "comparison": {"automaticMasteryJudgment": False},
    }
    assert client.post("/v2/students/23/stage-evidence-comparison").status_code == 405
