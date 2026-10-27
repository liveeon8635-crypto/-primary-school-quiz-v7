from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from changying.services import chance_figures as ch
from changying.services import grid_figures as gf
from changying.services import number_figures as nf
from changying.services import visual_questions as vq
from changying.web.cube_figures_js import CUBES_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("number_figure_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def size(shape):
    xs, ys = [p[0] for p in shape["points"]], [p[1] for p in shape["points"]]
    return max(xs) - min(xs), max(ys) - min(ys)


def right_answer(q):
    return q["answer"] if q["question_type"] == "fill_blank" else q["options"][q["correct_index"]]


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_decimal_area_model_matches_the_shading(level):
    for q in nf.generate("8-1", level, 6, 4):
        fig = q["figure"]
        assert gf.sanitize(fig) == fig and (fig["width"], fig["height"]) == (10, 10)
        w, h = size(fig["shapes"][1])
        assert [m["text"] for m in fig["marks"]] == [f"0.{w}", f"0.{h}"]       # labels agree with the drawing
        got = right_answer(q)
        if level == "medium":
            assert got == f"0.{w} × 0.{h}"
        else:
            assert float(got) == w * h / 100
        assert len(set(q["options"])) == len(q["options"])


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_letter_expressions_follow_the_bars(level):
    hows = set()
    for q in nf.generate("8-2", level, 9, 6):
        fig = q["figure"]
        assert gf.sanitize(fig) == fig
        top, bottom = [s for s in fig["shapes"] if s["tone"] == "a"], [s for s in fig["shapes"] if s["tone"] == "b"]
        x = size(top[0])[0]
        assert fig["marks"][0]["text"] == "x" and abs(fig["marks"][0]["to"][0] - fig["marks"][0]["from"][0]) == x
        drawn = sum(size(s)[0] for s in bottom)
        if len(bottom) > 1:
            k = len(bottom)
            hows.add("times")
            assert drawn == k * x
            rule = lambda v: k * v                                   # noqa: E731
            expr = f"{k}x"
        else:
            a = int(fig["marks"][1]["text"])
            hows.add("more" if drawn > x else "less")
            assert abs(drawn - x) == a
            rule = (lambda v: v + a) if drawn > x else (lambda v: v - a)  # noqa: E731
            expr = f"x + {a}" if drawn > x else f"x − {a}"
        if q["question_type"] == "fill_blank":
            total = int(re.search(r"一共有 (\d+) 个", q["text"]).group(1))
            v = int(q["answer"])
            assert v + rule(v) == total
        else:
            assert right_answer(q) == expr
    assert hows == {"more", "less", "times"}


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_hectares_from_a_field_drawn_to_scale(level):
    for q in nf.generate("6-7", level, 6, 8):
        fig = q["figure"]
        assert gf.sanitize(fig) == fig and fig["hideGrid"] is True
        w, h = size(fig["shapes"][0])
        (a, ua), (b, ub) = [re.fullmatch(r"([\d.]+) (m|km)", m["text"]).groups() for m in fig["marks"]]
        assert ua == ub
        per = float(a) / w
        assert per == pytest.approx(float(b) / h)                     # both sides use one scale
        m2 = float(a) * float(b) * (1_000_000 if ua == "km" else 1)
        got = right_answer(q)
        assert float(got.split()[0]) == pytest.approx(m2 / 10000) and (q["question_type"] == "fill_blank" or got.endswith("公顷"))


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_two_dice(level):
    assert [ch.ways(s) for s in range(2, 13)] == [1, 2, 3, 4, 5, 6, 5, 4, 3, 2, 1]
    for q in ch.generate("7-4", level, 6, 2):
        fig = q["figure"]
        assert ch.sanitize(fig) == fig and fig["kind"] == "dice"
        assert fig.get("table", False) == (level != "basic")
        got, text = right_answer(q), q["text"]
        if "不可能" in text:
            assert not 2 <= int(got) <= 12 and all(2 <= int(o) <= 12 for o in q["options"] if o != got)
        elif "最大是" in text:
            assert got == "12"
        elif "最小是" in text:
            assert got == "2"
        elif "可能性最大" in text:
            assert got == "7"
        else:
            total = int(re.search(r"之和是 (\d+)", text).group(1))
            assert int(got) == sum(1 for a in range(1, 7) for b in range(1, 7) if a + b == total)


def test_dice_figures_are_checked():
    good = {"type": "chance", "kind": "dice", "faces": [3, 6], "table": True}
    assert ch.sanitize(good) == good
    for bad in ({"faces": [0, 3]}, {"faces": [7, 1]}, {"faces": [2]}, {"faces": "12"}):
        assert ch.sanitize({**good, **bad}) == {}, bad
    assert "table" not in ch.sanitize({**good, "table": "yes"})


def test_dispatcher_serves_the_last_points():
    for key in ("2-2", "5-1", "6-7", "7-4", "8-1", "8-2"):
        assert key in vq.NODE_KINDS and vq.NODE_LABELS[key]
    assert vq.generate("7-4", "medium", 1, 1)[0]["figure"]["type"] == "chance"


def test_browser_draws_dice_and_leaves_room_for_grid_labels():
    dice = {"type": "chance", "kind": "dice", "faces": [1, 6], "table": True}
    grid = nf.generate("8-1", "basic", 1, 4)[0]["figure"]
    script = CUBES_JS + "var d=cyFigureShapes(" + json.dumps(dice) + "),g=cyFigureShapes(" + json.dumps(grid) + ");" \
        "console.log(JSON.stringify({pips:d.items.filter(function(i){return i.t==='circle'}).length," \
        "sums:d.items.filter(function(i){return i.t==='text'&&/^\\d+$/.test(i.s)}).length," \
        "minx:Math.min.apply(null,g.items.filter(function(i){return i.t==='text'}).map(function(i){return i.a.x}))}))"
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out["pips"] == 7 and out["sums"] == 12 + 36                     # headers 1–6 twice and the 36 sums
    assert out["minx"] > 0                                                 # the side label is not cut off


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    base = f"/teacher/knowledge-maps/{mid}/nodes"
    units = {"6-7": "多边形的面积", "7-4": "可能性", "8-1": "复习与关联", "8-2": "复习与关联"}
    saved = {}
    for key in units:
        for level in ("basic", "hard"):
            got = client.post(base + f"/{key}/visual", headers=th, json={"level": level, "count": 2}).json()
            r = client.post(base + f"/{key}/visual/save", headers=th, json={"level": level, "revision": rev, "questions": got["items"]})
            assert r.status_code == 200, r.text
            rev = r.json()["revision"]
            for qid, q in zip(r.json()["saved"], got["items"]):
                saved[qid] = (key, q)
    with legacy.SessionLocal() as db:
        rows = {q.id: q for q in db.scalars(select(legacy.Question).where(legacy.Question.id.in_(list(saved))))}
    assert len(rows) == 16
    for qid, (key, q) in saved.items():
        row = rows[qid]
        assert row.unit == units[key] and json.loads(row.figure_json) == q["figure"]
        if row.question_type == "fill_blank":
            assert json.loads(row.answer_json)["answer"] == q["answer"]
        else:
            assert row.correct_index == q["correct_index"]
print("OK")
'''


def test_teacher_saves_the_last_picture_questions(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})
