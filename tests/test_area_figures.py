from __future__ import annotations

import importlib.util
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

from changying.services import area_figures as af
from changying.services import grid_figures as gf
from changying.services import visual_questions as vq
from changying.web.cube_figures_js import CUBES_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("area_figure_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def shoelace(pts):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def cm(text):
    m = re.match(r"([\d.]+) cm$", text)
    return float(m.group(1)) if m else None


@pytest.mark.parametrize("node", ["6-1", "6-2", "6-3", "6-4"])
@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_answers_match_the_drawn_shape(node, level):
    qs = af.generate(node, level, 6, 13)
    assert len(qs) == 6
    for q in qs:
        fig = q["figure"]
        assert gf.sanitize(fig) == fig
        pts = fig["shapes"][0]["points"]
        area, height = shoelace(pts), max(p[1] for p in pts) - min(p[1] for p in pts)
        if q["question_type"] == "fill_blank":
            got = float(q["answer"])
            assert got == (height if "高是" in q["text"] else area), q
            assert q["explanation"].endswith(f"答案是 {q['answer']}。")
        else:
            values = [float(o.split()[0]) for o in q["options"]]
            assert len(set(values)) == 4 and values[q["correct_index"]] == area, q
        if level == "basic":
            assert "marks" not in fig and not fig.get("hideGrid") and fig["title"] == "每个小方格表示 1 平方厘米"
            continue
        assert fig["hideGrid"] is True
        heights = [cm(m["text"]) for m in fig["marks"] if m["style"] == "height" and cm(m["text"]) is not None]
        for m in fig["marks"]:
            v = cm(m["text"])
            (x1, y1), (x2, y2) = m["from"], m["to"]
            if m["style"] == "height":
                assert x1 == x2 and (v is None or v == abs(y2 - y1))          # 高 is upright and to scale ("?" when asked)
            elif x1 == x2 or y1 == y2:
                assert v == abs(x2 - x1) + abs(y2 - y1), (m, q)              # bases and edges are to scale
            else:
                assert heights and v > max(heights), (m, q)                  # a slanted side is longer than the height


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_lattice_polygons_follow_picks_theorem(level):
    qs = af.generate("6-6", level, 6, 5)
    assert len(qs) == 6
    for q in qs:
        pts = q["figure"]["shapes"][0]["points"]
        assert len(pts) >= (3 if level == "basic" else 4) and gf.sanitize(q["figure"]) == q["figure"]
        assert float(q["answer"]) == shoelace(pts)
        inner, border = map(int, re.search(r"内部有 (\d+) 个格点，边上有 (\d+) 个格点", q["explanation"]).groups())
        assert inner + border / 2 - 1 == shoelace(pts)


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_review_8_4_mixes_moves_and_areas(level):
    qs = vq.generate("8-4", level, 7, 3)
    assert len(qs) == 7
    texts = " ".join(q["text"] for q in qs)
    assert "面积" in texts and any(w in texts for w in ("平移", "旋转", "对称轴"))
    assert all(gf.sanitize(q["figure"]) == q["figure"] for q in qs)


def test_marks_and_plain_drawings_are_checked():
    base = {"type": "gridshape", "width": 12, "height": 8, "hideGrid": True,
            "shapes": [{"points": [[1, 1], [6, 1], [3, 4]], "tone": "a", "label": ""}],
            "marks": [{"from": [1, 1], "to": [6, 1], "text": "5 cm", "style": "dim"}, {"from": [3, 4], "to": [3, 1], "text": "3 cm", "style": "height"}]}
    assert gf.sanitize(base) == base
    for bad in ({"style": "arrow"}, {"to": [1, 1]}, {"text": ""}, {"to": [20, 1]}):
        mark = {**base["marks"][0], **bad}
        assert gf.sanitize({**base, "marks": [mark]}) == {}, bad
    assert gf.sanitize({**base, "marks": base["marks"] * 4}) == {}
    assert "hideGrid" not in gf.sanitize({**base, "hideGrid": "yes"})


def test_every_area_point_is_served_by_the_dispatcher():
    for key in ("6-1", "6-2", "6-3", "6-4", "6-6"):
        assert key in vq.NODE_KINDS and "面积" in vq.NODE_LABELS[key]
        assert vq.generate(key, "medium", 1, 2)[0]["figure"]["type"] == "gridshape"
    assert "面积" in vq.NODE_LABELS["8-4"] and "平移" in vq.NODE_LABELS["4-4"]


def test_plain_drawing_has_no_squares_and_draws_measurements():
    fig = {"type": "gridshape", "width": 12, "height": 8, "hideGrid": True,
           "shapes": [{"points": [[1, 1], [6, 1], [3, 4]], "tone": "a", "label": ""}],
           "marks": [{"from": [1, 1], "to": [6, 1], "text": "5 cm", "style": "dim"}, {"from": [3, 4], "to": [3, 1], "text": "3 cm", "style": "height"}]}
    script = CUBES_JS + "var g=cyFigureShapes(" + json.dumps(fig) + ");" \
        "console.log(JSON.stringify({lines:g.items.filter(function(i){return i.t==='line'}).length," \
        "dashed:g.items.filter(function(i){return i.t==='line'&&i.a['stroke-dasharray']}).length," \
        "corner:g.items.filter(function(i){return i.t==='polyline'}).length," \
        "texts:g.items.filter(function(i){return i.t==='text'}).map(function(i){return i.s})}))"
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    # no grid lines: 3 lines for the dimension (line + two ticks) + the dashed height; one right-angle mark
    assert out == {"lines": 4, "dashed": 1, "corner": 1, "texts": ["5 cm", "3 cm"]}


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.commit()
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    assert "面积" in d["visualNodes"]["6-3"]
    base = f"/teacher/knowledge-maps/{mid}/nodes"
    answers = {}
    for key in ("6-1", "6-2", "6-3", "6-4"):
        for level in ("basic", "medium"):
            got = client.post(base + f"/{key}/visual", headers=th, json={"level": level, "count": 2}).json()
            r = client.post(base + f"/{key}/visual/save", headers=th, json={"level": level, "revision": rev, "questions": got["items"]})
            assert r.status_code == 200, r.text
            rev = r.json()["revision"]
            for qid, q in zip(r.json()["saved"], got["items"]):
                answers[qid] = q
    with legacy.SessionLocal() as db:
        rows = {q.id: q for q in db.scalars(select(legacy.Question).where(legacy.Question.id.in_(list(answers))))}
    assert len(rows) == 16
    kinds = {rows[i].question_type for i in rows}
    assert kinds == {"fill_blank", "single_choice"}
    for qid, q in answers.items():
        r = rows[qid]
        assert r.unit == "多边形的面积" and json.loads(r.figure_json)["type"] == "gridshape"
        if r.question_type == "fill_blank":
            assert json.loads(r.answer_json)["answer"] == q["answer"] and json.loads(r.options_json) == []
        else:
            assert r.correct_index == q["correct_index"]
    # Pupils answer the picture questions in the diagnosis; numbers typed in are graded by the existing engine.
    m = client.get(f"/teacher/knowledge-maps/{mid}", headers=th).json()["map"]
    for u in m["units"]:
        u["learned"] = u["key"] == "U6"
    rev = client.put(f"/teacher/knowledge-maps/{mid}", headers=th, json={"map": m, "revision": rev}).json()["revision"]
    client.post(f"/teacher/knowledge-maps/{mid}/publish", headers=th, json={"revision": rev})
    diag = client.post("/student/knowledge-map/diagnosis", headers=sh).json()
    assert diag["count"] >= 6 and all(q["figure"]["type"] == "gridshape" for q in diag["questions"])
    assert all("answer" not in q and "correctIndex" not in q for q in diag["questions"])
    sub = []
    for q in diag["questions"]:
        src = answers[q["id"]]
        sub.append({"question_id": q["id"], "text_answer": src["answer"]} if src["question_type"] == "fill_blank"
                   else {"question_id": q["id"], "selected_index": src["correct_index"]})
    res = client.post("/student/knowledge-map/diagnosis/submit", headers=sh, json={"answers": sub}).json()
    assert res["correct"] == res["total"] == diag["count"]
print("OK")
'''


def test_teacher_saves_area_questions_and_pupils_are_graded(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})
