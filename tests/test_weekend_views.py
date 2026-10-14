from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

from changying.services.weekend_stages import STAGES, remaining_seconds, stage_content

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hw_solve_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules["hw_solve_helpers"] = helpers
spec.loader.exec_module(helpers)


def test_template_is_120_minutes_in_seven_stages():
    assert len(STAGES) == 7 and sum(s["minutes"] for s in STAGES) == 120


def test_remaining_seconds_counts_down_and_goes_negative_on_overtime():
    t0 = datetime(2026, 1, 1, 9, 0, 0)
    assert remaining_seconds(10, 0, t0, t0 + timedelta(minutes=4)) == 360
    assert remaining_seconds(10, 5, t0, t0 + timedelta(minutes=4)) == 660
    assert remaining_seconds(10, 0, t0, t0 + timedelta(minutes=12)) == -120
    assert remaining_seconds(10, 0, None, t0) == 600


def test_stage_content_comes_from_the_lesson_plan():
    lesson = {"title": "分数", "core_target": "理解分数", "teacher_plan": "先讲定义", "ppt_json": '["封面","定义"]',
              "examples_json": '[{"title":"例1","answer":"1/2"}]', "closure_training": "做练习册 P12"}
    assert stage_content(2, lesson)[:2] == ["理解分数", "先讲定义"]
    assert stage_content(3, lesson) == ["例1 1/2"]
    assert stage_content(7, lesson) == ["做练习册 P12"]


def test_session_flow_timer_cover_and_isolation(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=99, title="分数初步",
                                  core_target="理解分数", examples_json=json.dumps(["例1：1/2"], ensure_ascii=False))
        db.add(l); db.commit(); lid = l.id

    assert client.get("/v1/weekend").status_code == 200 and client.get("/v1/weekend-board").status_code == 200
    assert client.get("/teacher/weekend/lessons", headers=sh).status_code == 403

    d = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()
    s = d["id"]; base = f"/teacher/weekend/sessions/{s}"
    assert d["status"] == "planned" and d["content"] == [] and len(d["stages"]) == 7
    assert client.post(base + "/next", headers=th).status_code == 409        # not started

    d = client.post(base + "/start", headers=th).json()
    assert d["status"] == "running" and d["currentStage"] == 1 and 590 <= d["remainingSeconds"] <= 600
    d = client.post(base + "/next", headers=th).json()
    assert d["currentStage"] == 2 and d["content"][0] == "理解分数"
    d = client.post(base + "/goto", headers=th, json={"stage": 3}).json()
    assert d["stageName"] == "例题讲解" and d["content"] == ["例1：1/2"]
    d = client.post(base + "/extend", headers=th, json={"minutes": 5}).json()
    assert 29 * 60 <= d["remainingSeconds"] <= 30 * 60
    assert client.post(base + "/goto", headers=th, json={"stage": 9}).status_code == 400

    # cover hides the content from the board but not from the control panel's stage state
    board = client.post(base + "/cover", headers=th, json={"covered": True}).json()
    assert board["covered"] is True
    assert client.get(base + "/board", headers=th).json()["content"] == []
    client.post(base + "/cover", headers=th, json={"covered": False})
    assert client.get(base + "/board", headers=th).json()["content"] == ["例1：1/2"]

    # timeline: every visited stage is logged
    d = client.get(base, headers=th).json()
    assert [x["visited"] for x in d["stages"]] == [True, True, True, False, False, False, False]
    assert d["stages"][2]["extendMin"] == 5

    d = client.post(base + "/goto", headers=th, json={"stage": 7}).json()
    d = client.post(base + "/next", headers=th).json()                         # past the last stage -> finish
    assert d["status"] == "finished" and d["remainingSeconds"] is None
    assert client.post(base + "/next", headers=th).status_code == 409

    # another teacher cannot see it
    from sqlalchemy import update
    with legacy.SessionLocal() as db:
        db.execute(update(legacy.Base.metadata.tables["weekend_sessions"]).where(legacy.Base.metadata.tables["weekend_sessions"].c.id == s).values(teacher_id=999999))
        db.commit()
    assert client.get(base, headers=th).status_code == 404
    print("OK")
''',
    )
