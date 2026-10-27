from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("courseware_template_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_saved_courseware_template_applies_to_another_lesson(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        first = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=21, title="第一课", core_target="目标一")
        second = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=22, title="第二课", core_target="目标二")
        chinese = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="语文", lesson_no=23, title="语文课", core_target="目标三")
        db.add_all([first, second, chinese]); db.flush()
        first_id, second_id, chinese_id = first.id, second.id, chinese.id
        db.commit()

    base = f"/teacher/weekend/lessons/{first_id}/courseware"
    params = {"steps": ["先看例题要求", "再按步骤算"], "answer": "7"}
    r = client.put(base, headers=th, json={"stageNo": 3, "kind": "steps", "params": params})
    assert r.status_code == 200, r.text

    # Saving needs a real page item and a logged-in teacher.
    assert client.post(f"/teacher/weekend/lessons/{second_id}/courseware/save-as-template", headers=th,
                       json={"stageNo": 3}).status_code == 404
    assert client.post(base + "/save-as-template", headers=sh, json={"stageNo": 3}).status_code == 403
    saved = client.post(base + "/save-as-template", headers=th, json={"stageNo": 3, "name": "两步讲解模板"})
    assert saved.status_code == 200, saved.text
    tid = saved.json()["templateId"]
    assert saved.json()["name"] == "两步讲解模板" and saved.json()["kind"] == "steps"

    listed = client.get("/teacher/weekend/courseware/templates?subject=数学", headers=th).json()["items"]
    assert [t["name"] for t in listed] == ["两步讲解模板"]
    assert listed[0]["kind"] == "steps" and listed[0]["subject"] == "数学"
    assert client.get("/teacher/weekend/courseware/templates", headers=sh).status_code == 403
    # Another subject's template list does not leak this one.
    assert client.get("/teacher/weekend/courseware/templates?subject=语文", headers=th).json()["items"] == []

    # Applying copies the parameters into another lesson as a draft (still needs approval).
    applied = client.post(f"/teacher/weekend/lessons/{second_id}/courseware/from-template", headers=th,
                          json={"stageNo": 3, "templateId": tid})
    assert applied.status_code == 200, applied.text
    items = applied.json()["items"]
    assert len(items) == 1 and items[0]["kind"] == "steps" and items[0]["status"] == "draft"
    assert items[0]["params"]["steps"] == params["steps"] and items[0]["params"]["answer"] == "7"

    # The template is not usable across subjects, and unknown ids are refused.
    wrong = client.post(f"/teacher/weekend/lessons/{chinese_id}/courseware/from-template", headers=th,
                        json={"stageNo": 3, "templateId": tid})
    assert wrong.status_code == 400 and "学科" in wrong.json()["detail"]
    assert client.post(f"/teacher/weekend/lessons/{second_id}/courseware/from-template", headers=th,
                       json={"stageNo": 3, "templateId": 999999}).status_code == 404
print('OK')
''')
