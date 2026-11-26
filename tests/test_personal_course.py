"""One-click course for a personal workspace.

A solo teacher has no 教学方案 concept, yet 周末课备课 refuses to load without one.
/start offers two buttons (数学 / 语文) that build a default 18-lesson course, so
the teacher reaches 备课 without learning school vocabulary.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COMMERCIAL_KEY = "personal-course-commercial-key-0123456789"
PASSWORD = "Teacher1234"
CHANGED = "Teacher5678"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("course") / "app.sqlite3"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ["ENABLE_DEMO_SEED"] = "0"
    os.environ.setdefault("JWT_SECRET", "course-page-jwt-secret-0123456789abcdef")
    import app as app_module
    import app_v924 as legacy

    legacy.COMMERCIAL_ADMIN_KEY = COMMERCIAL_KEY
    with TestClient(app_module.app) as c:
        yield c


def _workspace(client):
    tag = uuid.uuid4().hex[:8]
    code = f"course-{tag}"
    r = client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={
            "school_name": f"课程工作室{tag}",
            "school_code": code,
            "admin_name": "李老师",
            "admin_username": code,
            "admin_password": PASSWORD,
            "individual": True,
        },
    )
    assert r.status_code == 200, r.text[:300]
    data = client.post("/login", json={"username": code, "password": PASSWORD}).json()
    headers = {"Authorization": "Bearer " + data["token"]}
    if data.get("mustChangePassword"):
        assert client.post("/change-password", json={"current_password": PASSWORD, "new_password": CHANGED}, headers=headers).status_code == 200
        data = client.post("/login", json={"username": code, "password": CHANGED}).json()
        headers = {"Authorization": "Bearer " + data["token"]}
    return headers


def test_start_offers_course_buttons_then_builds_one(client):
    headers = _workspace(client)
    page = client.get("/start", headers=headers).text
    assert 'action="/start/program"' in page
    assert 'value="数学"' in page and 'value="语文"' in page

    r = client.post("/start/program", headers=headers, data={"subject": "数学"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/start"

    page = client.get("/start", headers=headers).text
    assert "已有课程方案（18 节课）" in page
    assert "数学（已建）" in page
    assert 'value="语文"' in page
    assert 'value="英语"' in page

    # 备课页 now has a program to work with.
    assert client.get("/v1/weekend-plan", headers=headers).status_code == 200

    # Pressing again must not duplicate lessons.
    r = client.post("/start/program", headers=headers, data={"subject": "数学"}, follow_redirects=False)
    assert r.status_code == 303
    assert "已有课程方案（18 节课）" in client.get("/start", headers=headers).text

    # Custom subject and custom lesson count (e.g. 英语 12 节, 科学 6 节)
    r = client.post("/start/program", headers=headers, data={"subject": "英语", "lessons": "12"}, follow_redirects=False)
    assert r.status_code == 303
    page = client.get("/start", headers=headers).text
    assert "已有课程方案（30 节课）" in page

    eng_rows = client.get("/teacher/weekend/schedule?subject=英语", headers=headers).json()["items"]
    assert len(eng_rows) == 12

    subjects = client.get("/teacher/weekend/subjects", headers=headers).json()["subjects"]
    assert "数学" in subjects and "英语" in subjects

    # Appending lessons dynamically via weekend plan API
    added = client.post("/teacher/weekend/lessons/add", headers=headers, json={"subject": "英语", "count": 2})
    assert added.status_code == 200, added.text[:300]
    assert added.json()["totalLessons"] == 14
    assert len(client.get("/teacher/weekend/schedule?subject=英语", headers=headers).json()["items"]) == 14

    # Custom subject via weekend plan API + custom script parse check
    sci = client.post("/teacher/weekend/lessons/add", headers=headers, json={"subject": "科学", "count": 5})
    assert sci.status_code == 200
    assert len(client.get("/teacher/weekend/schedule?subject=科学", headers=headers).json()["items"]) == 5
    import script_check
    custom_js = client.get("/v1/weekend-plan-custom.js")
    assert custom_js.status_code == 200
    script_check.assert_parses(custom_js.text)


def test_one_click_course_is_not_reported_as_already_prepared(client):
    """The one-click lessons carry a hint ("在上课时填写…"), not a plan.

    If the hint counts as a plan, all 18 lessons show 有教案 before the teacher
    imported anything, and importing asks to overwrite content that is not there.
    """
    headers = _workspace(client)
    r = client.post("/start/program", headers=headers, data={"subject": "数学"}, follow_redirects=False)
    assert r.status_code == 303

    rows = client.get("/teacher/weekend/schedule?subject=数学", headers=headers).json()["items"]
    assert len(rows) == 18
    assert not any(row["hasPlan"] for row in rows), [x["lessonNo"] for x in rows if x["hasPlan"]]


def test_school_teacher_cannot_build_a_personal_course(client):
    tag = uuid.uuid4().hex[:8]
    code = f"orgc-{tag}"
    client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={"school_name": f"机构{tag}", "school_code": code, "admin_name": "王管理", "admin_username": code, "admin_password": PASSWORD, "plan_code": "school_basic"},
    )
    data = client.post("/login", json={"username": code, "password": PASSWORD}).json()
    headers = {"Authorization": "Bearer " + data["token"]}
    if data.get("mustChangePassword"):
        client.post("/change-password", json={"current_password": PASSWORD, "new_password": CHANGED}, headers=headers)
        data = client.post("/login", json={"username": code, "password": CHANGED}).json()
        headers = {"Authorization": "Bearer " + data["token"]}

    r = client.post("/start/program", headers=headers, data={"subject": "数学"}, follow_redirects=False)
    assert r.status_code == 403

    # Invalid subjects or out-of-range lesson counts are rejected before anything is written.
    personal = _workspace(client)
    assert client.post("/start/program", headers=personal, data={"subject": "   "}, follow_redirects=False).status_code == 400
    assert client.post("/start/program", headers=personal, data={"subject": "数学", "lessons": "0"}, follow_redirects=False).status_code == 400
    assert client.post("/start/program", headers=personal, data={"subject": "数学", "lessons": "99"}, follow_redirects=False).status_code == 400
