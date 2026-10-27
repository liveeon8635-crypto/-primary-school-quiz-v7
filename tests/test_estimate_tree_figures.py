from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from changying.services import area_figures as af
from changying.services import grid_figures as gf
from changying.services import tree_figures as tf
from changying.services import visual_questions as vq
from changying.web.cube_figures_js import CUBES_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("estimate_tree_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def shoelace(pts):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_irregular_area_is_counted_by_the_half_square_rule(level):
    qs = af.generate("6-5", level, 6, 21)
    assert len(qs) == 6
    for q in qs:
        fig = q["figure"]
        assert gf.sanitize(fig) == fig and fig["shapes"][0]["smooth"] is True
        pts = fig["shapes"][0]["points"]
        full, part, unsure = af.count_cells(pts, fig["width"], fig["height"])
        values = [float(o.split()[0]) for o in q["options"]]
        right = values[q["correct_index"]]
        assert right == full + part / 2 and len(set(values)) == 4
        # Reading a few grazed squares differently cannot land on another option.
        assert all(abs(v - right) >= unsure + 1.5 for i, v in enumerate(values) if i != q["correct_index"])
        # The estimate is close to the real area inside the drawn curve.
        assert abs(right - shoelace(af.curve(pts, 60))) <= 4
        assert f"满格的有 {full} 个，不满整格的有 {part} 个" in q["explanation"]


def test_curves_may_pass_through_square_middles_but_polygons_stay_on_grid_points():
    shape = {"points": [[1.5, 1.5], [4.5, 1.5], [3.5, 4.5]], "tone": "a", "label": ""}
    fig = {"type": "gridshape", "width": 8, "height": 6, "shapes": [{**shape, "smooth": True}]}
    assert gf.sanitize(fig) == fig
    assert gf.sanitize({**fig, "shapes": [shape]}) == {}
    assert gf.sanitize({**fig, "shapes": [{**shape, "smooth": True, "points": [[1.25, 1], [4, 1], [3, 4]]}]}) == {}


def test_dots_and_roads_are_checked():
    base = {"type": "gridshape", "width": 12, "height": 6, "hideGrid": True, "dots": [[0, 2], [1, 2]],
            "marks": [{"from": [0, 2], "to": [4, 2], "text": "20 米", "style": "seg"}]}
    assert gf.sanitize(base) == base
    assert gf.sanitize({**base, "dots": [[13, 2]]}) == {}
    assert gf.sanitize({**base, "dots": [[0, 2]] * 41}) == {}
    assert gf.sanitize({**base, "dots": [], "marks": []}) == {}          # nothing to draw


NUMS = re.compile(r"\d+")


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_tree_answers_follow_the_gap_rules(level):
    qs = tf.generate("8-6", level, 12, 5)
    assert len(qs) == 12
    modes = set()
    for q in qs:
        fig, text = q["figure"], q["text"]
        assert gf.sanitize(fig) == fig
        mode = "loop" if ("四周" in text or "一周" in text) else next(m for m, t in tf.MODE_TEXT.items() if t in text)
        modes.add(mode)
        got = float(q["answer"]) if q["question_type"] == "fill_blank" else float(q["options"][q["correct_index"]].split()[0])
        if "四周" in text:                                  # rectangle bed: perimeter ÷ gap
            a, b, d = map(int, NUMS.findall(text)[:3])
            assert got == 2 * (a + b) / d == len(fig["dots"])
        elif "一共种了" in text or "一共栽了" in text:          # length from the number of trees
            d, trees = map(int, NUMS.findall(text)[:2])
            assert got == (trees - {"both": 1, "one": 0, "none": -1, "loop": 0}[mode]) * d
        else:
            length, d = map(int, NUMS.findall(text)[:2])
            assert got == tf.count(mode, length // d)
            if level == "basic":
                assert got == len(fig["dots"])              # small cases are drawn tree by tree
        if level != "basic":                                # the small case drawn agrees with its own caption
            assert str(len(fig["dots"])) in fig["title"]
    assert len(modes) >= 3


def test_dispatcher_serves_6_5_and_8_6():
    assert "估计" in vq.NODE_LABELS["6-5"] and "植树" in vq.NODE_LABELS["8-6"]
    for key in ("6-5", "8-6"):
        assert vq.generate(key, "medium", 2, 3)[0]["figure"]["type"] == "gridshape"


def test_browser_draws_curves_trees_and_roads():
    curve = {"type": "gridshape", "width": 8, "height": 6, "shapes": [{"points": [[1.5, 1.5], [4.5, 1.5], [3.5, 4.5]], "tone": "a", "label": "", "smooth": True}]}
    road = {"type": "gridshape", "width": 12, "height": 6, "hideGrid": True, "title": "先看简单的情况：4 个间隔，两端都种，种 5 棵",
            "dots": [[x, 2] for x in range(5)],
            "marks": [{"from": [0, 2], "to": [4, 2], "text": "20 米", "style": "seg"}, {"from": [0, 2], "to": [1, 2], "text": "5 米", "style": "dim"}]}
    script = CUBES_JS + "var out=[" + json.dumps(curve) + "," + json.dumps(road) + "].map(function(f){var g=cyFigureShapes(f);" \
        "return {w:g.w,paths:g.items.filter(function(i){return i.t==='path'}).map(function(i){return i.a.d}),"\
        "dots:g.items.filter(function(i){return i.t==='circle'}).length,texts:g.items.filter(function(i){return i.t==='text'}).map(function(i){return i.s})}});" \
        "console.log(JSON.stringify(out))"
    c, r = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert len(c["paths"]) == 1 and c["paths"][0].count("C") == 3 and c["paths"][0].endswith("Z")
    assert r["dots"] == 5 and r["texts"] == [road["title"], "20 米", "5 米"]
    assert r["w"] >= len(road["title"]) * 14                 # the caption is not cut off


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    assert "6-5" in d["visualNodes"] and "8-6" in d["visualNodes"]
    base = f"/teacher/knowledge-maps/{mid}/nodes"
    saved = {}
    for key in ("6-5", "8-6"):
        for level in ("basic", "hard"):
            got = client.post(base + f"/{key}/visual", headers=th, json={"level": level, "count": 2}).json()
            r = client.post(base + f"/{key}/visual/save", headers=th, json={"level": level, "revision": rev, "questions": got["items"]})
            assert r.status_code == 200, r.text
            rev = r.json()["revision"]
            for qid, q in zip(r.json()["saved"], got["items"]):
                saved[qid] = (key, q)
    with legacy.SessionLocal() as db:
        rows = {q.id: q for q in db.scalars(select(legacy.Question).where(legacy.Question.id.in_(list(saved))))}
    assert len(rows) == 8
    for qid, (key, q) in saved.items():
        row, fig = rows[qid], json.loads(rows[qid].figure_json)
        assert fig == q["figure"]                         # curves keep their x.5 points, trees and roads survive saving
        assert row.unit == ("多边形的面积" if key == "6-5" else "复习与关联")
        if row.question_type == "fill_blank":
            assert json.loads(row.answer_json)["answer"] == q["answer"]
        else:
            assert row.correct_index == q["correct_index"]
print("OK")
'''


def test_teacher_saves_estimate_and_tree_questions(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})
