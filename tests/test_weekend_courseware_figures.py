from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from changying.services import weekend_courseware as cw
from changying.web.weekend_courseware_pages import COURSEWARE_JS, COURSEWARE_PLAN_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("weekend_courseware_figure_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_figures_are_data_checked_before_they_are_drawn():
    seg = cw.clean_figure({"type": "segment", "points": [{"name": "D", "at": 10}, {"name": "A", "at": 0}, {"name": "B", "at": 6}],
                           "marks": [{"from": "A", "to": "D", "label": "L"}]})
    assert [p["name"] for p in seg["points"]] == ["A", "B", "D"] and seg["marks"] == [{"from": "A", "to": "D", "label": "L"}]
    flow = cw.clean_figure({"type": "flow", "boxes": ["输入 n"], "branches": [{"when": "n 是单数", "boxes": ["2n + 4"]},
                                                                               {"when": "n 是双数", "boxes": ["n² + 2"]}]})
    assert flow["boxes"] == ["输入 n"] and [b["when"] for b in flow["branches"]] == ["n 是单数", "n 是双数"]
    shape = cw.clean_figure({"type": "shape", "shape": "rectangle", "labels": {"top": "a cm", "left": "b cm", "colour": "red"}})
    assert shape == {"type": "shape", "shape": "rectangle", "labels": {"top": "a cm", "left": "b cm"}}
    assert cw.clean_figure({"type": "table", "rows": [["n", "1", "2"], ["结果", "6", "8"]]})["rows"][1] == ["结果", "6", "8"]
    assert cw.clean_figure({}) == {} and cw.clean_figure(None) == {}
    for bad in ({"type": "image", "src": "x"}, {"type": "segment", "points": [{"name": "A", "at": 0}]},
                {"type": "segment", "points": [{"name": "A", "at": 0}, {"name": "A", "at": 3}]},
                {"type": "segment", "points": [{"name": "A", "at": 0}, {"name": "B", "at": 3}], "marks": [{"from": "A", "to": "Z", "label": "x"}]},
                {"type": "flow", "boxes": ["只有一个"]}, {"type": "flow", "boxes": ["输入"], "branches": [{"when": "单数", "boxes": ["+1"]}]},
                {"type": "shape", "shape": "circle"}, {"type": "table", "rows": [["a", "b"], ["c"]]}):
        with pytest.raises(ValueError):
            cw.clean_figure(bad)
    steps = cw.clean_steps({"steps": ["a", "b"], "answer": "1", "figure": {"type": "table", "rows": [["1", "2"], ["3", "4"]]}})
    assert steps["figure"]["type"] == "table" and cw.public_params("steps", steps)["figure"] == steps["figure"]


def test_page_code_draws_figures_without_markup_and_answers_on_the_row():
    for t in ("function cwFigure(", "cwFigureText", "createSVGRect"):
        assert t in COURSEWARE_JS, t
    assert "innerHTML" not in COURSEWARE_JS and "innerHTML" not in COURSEWARE_PLAN_JS
    for t in ("生成中…", "notes[String(x.page)]", "正在处理另一页", "figType", "线段和点", "计算程序图"):
        assert t in COURSEWARE_PLAN_JS, t


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    examples = [{"title": "例题13 | 中点问题", "question": "点B是线段AD上的一个动点，点C、E分别是线段BD、AB的中点，线段EC的长度会变化吗？", "answer": "不变，EC=AD的一半"},
                {"title": "例题11 | 顺推与逆推", "question": "输入一个数→除以0.5→加b→输出。输入数a时，输出的数是（ ）。", "answer": "2a+b"}]
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        math = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=95, title="分层综合提升",
                                     core_target="整体思想", teacher_plan="讲例题", examples_json=json.dumps(examples, ensure_ascii=False))
        db.add(math); db.commit(); mid = math.id
    base = f"/teacher/weekend/lessons/{mid}/courseware"
    seg = {"type": "segment", "points": [{"name": "A", "at": 0}, {"name": "E", "at": 3}, {"name": "B", "at": 6}, {"name": "C", "at": 8},
                                          {"name": "D", "at": 10}], "marks": [{"from": "A", "to": "D", "label": "L"}]}
    replies.append(json.dumps({"template": "steps", "title": "中点问题", "problem": "线段EC的长度会变化吗？", "steps": ["EB=AB的一半", "BC=BD的一半", "EC=AD的一半"],
                               "answer": "不变", "figure": seg}, ensure_ascii=False))
    d = client.post(base + "/generate", headers=th, json={"stageNo": 3, "page": 0}).json()
    item = next(i for i in d["items"] if i["page"] == 0)
    assert item["kind"] == "steps" and item["params"]["figure"]["type"] == "segment" and d["notice"] == ""
    assert '"type":"segment"' in prompts[-1] and '"type":"flow"' in prompts[-1] and "只画已知条件" in prompts[-1]
    # A figure that fails the checks is dropped; the worked example itself is kept, and the teacher is told.
    replies.append(json.dumps({"template": "steps", "title": "程序", "steps": ["a÷0.5=2a", "再加b"], "answer": "2a+b",
                               "figure": {"type": "flow", "boxes": ["只有一个框"]}}, ensure_ascii=False))
    d = client.post(base + "/generate", headers=th, json={"stageNo": 3, "page": 1}).json()
    item = next(i for i in d["items"] if i["page"] == 1)
    assert item["params"]["figure"] == {} and "图示没有通过校验" in d["notice"]
    # The teacher draws it in the editor (PUT): checked the same way.
    flow = {"type": "flow", "boxes": ["输入 a", "÷ 0.5", "+ b", "输出"]}
    bad = client.put(base, headers=th, json={"stageNo": 3, "page": 1, "kind": "steps", "params": {**item["params"], "figure": {"type": "flow", "boxes": []}}})
    assert bad.status_code == 400 and "程序图" in bad.json()["detail"]
    d = client.put(base, headers=th, json={"stageNo": 3, "page": 1, "kind": "steps", "params": {**item["params"], "figure": flow}}).json()
    assert next(i for i in d["items"] if i["page"] == 1)["params"]["figure"]["boxes"] == flow["boxes"]
    # Approved, the figure reaches the big screen with the page.
    for i in (0, 1):
        assert client.post(base + "/approve", headers=th, json={"stageNo": 3, "page": i}).status_code == 200
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        cls = legacy.SchoolClass(school_id=school_id, name="周末五年级", grade=5, teacher_id=teacher.id); db.add(cls); db.flush()
        db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid)); db.commit(); cls_id = cls.id
    s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": mid, "classId": cls_id}).json()["id"]
    client.post(f"/teacher/weekend/sessions/{s}/start", headers=th); client.post(f"/teacher/weekend/sessions/{s}/goto", headers=th, json={"stage": 3})
    board = client.get(f"/teacher/weekend/sessions/{s}/board", headers=th).json()
    assert board["courseware"]["params"]["figure"]["points"][1]["name"] == "E" and "reference" not in board["courseware"]["params"]
    assert "cwFigure" in client.get("/v1/weekend-board").text and "figType" in client.get("/v1/weekend-plan").text
print("OK")
'''


def test_worked_example_figure_from_ai_to_the_big_screen(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW)
