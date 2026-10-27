from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from changying.services import grid_figures as gf
from changying.services import visual_questions as vq
from changying.web.cube_figures_js import CUBES_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("grid_figure_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

DIRS = {"右": (1, 0), "左": (-1, 0), "上": (0, 1), "下": (0, -1)}


def key(pts):
    return frozenset(map(tuple, pts))


def test_moves_are_exact():
    L = [[0, 0], [2, 0], [2, 1], [1, 1], [1, 3], [0, 3]]
    assert gf.translate(L, 3, -1)[0] == [3, -1]
    assert gf.rotate([[1, 0]], [0, 0], True, 90) == [[0, -1]] and gf.rotate([[1, 0]], [0, 0], False, 90) == [[0, 1]]
    assert gf.rotate([[1, 0]], [0, 0], True, 180) == [[-1, 0]]
    assert gf.reflect([[3, 2]], ("x", 5)) == [[7, 2]] and gf.reflect([[3, 2]], ("y", 4)) == [[3, 6]]
    # The base shapes have no symmetry: every turn and mirror image differs.
    for s in gf.SHAPES:
        images = [key(gf.rotate(s, [0, 0], True, a)) for a in (0, 90, 180, 270)]
        images += [key(gf.reflect(gf.rotate(s, [0, 0], True, a), ("x", 0))) for a in (0, 90, 180, 270)]
        norm = {frozenset((x - min(p[0] for p in i), y - min(p[1] for p in i)) for x, y in i) for i in images}
        assert len(norm) == 8


def _expected(q):
    fig, text = q["figure"], q["text"]
    a = next(s["points"] for s in fig["shapes"] if s["label"] == "A")
    if "对称轴" in text:
        (x1, y1), (x2, y2) = fig["axis"]
        return gf.reflect(a, ("x", x1) if x1 == x2 else ("y", y1))
    m = re.search(r"向(右|左|上|下)平移 (\d+) 格，得到", text)
    if m:
        d = DIRS[m.group(1)]
        return gf.translate(a, d[0] * int(m.group(2)), d[1] * int(m.group(2)))
    if "绕点 O" in text and "后得到" in text:
        cw = "逆时针" not in text
        angle = 180 if "180°" in text else 90
        return gf.rotate(a, fig["center"], cw, angle)
    raise AssertionError(text)


def _how_ok(q, option):
    fig = q["figure"]
    a = next(s["points"] for s in fig["shapes"] if s["label"] == "A")
    b = next(s["points"] for s in fig["shapes"] if s["label"] == "B")
    m = re.match(r"向(右|左|上|下)平移 (\d+) 格", option)
    if m:
        d, n = DIRS[m.group(1)], int(m.group(2))
        return key(gf.translate(a, d[0] * n, d[1] * n)) == key(b)
    if option == "绕点 O 旋转 180°":
        return key(gf.rotate(a, fig["center"], True, 180)) == key(b)
    m = re.match(r"绕点 O (顺时针|逆时针)旋转 (\d+)°", option)
    if m and int(m.group(2)) % 90 == 0:
        return key(gf.rotate(a, fig["center"], m.group(1) == "顺时针", int(m.group(2)))) == key(b)
    return False


@pytest.mark.parametrize("node", ["4-1", "4-2", "4-3"])
@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_every_generated_question_has_exactly_one_right_option(node, level):
    qs = gf.generate(node, level, 6, 11)
    assert len(qs) == 6
    for q in qs:
        fig = q["figure"]
        assert gf.sanitize(fig) == fig
        for s in fig.get("shapes", []) + [s for p in fig.get("panels", []) for s in p["shapes"]]:
            assert all(0 <= x <= fig["width"] and 0 <= y <= fig["height"] for x, y in s["points"])
        if "怎样" in q["text"]:
            hits = [i for i, o in enumerate(q["options"]) if _how_ok(q, o)]
        else:
            want = key(_expected(q))
            assert q["options"] == ["图A", "图B", "图C", "图D"]
            hits = [i for i, p in enumerate(fig["panels"]) if key(next(s["points"] for s in p["shapes"] if s["tone"] == "b")) == want]
        assert hits == [q["correct_index"]], q
        assert q["explanation"].endswith(f"所以选 {'ABCD'[q['correct_index']]}。")


def test_sanitize_rejects_bad_figures():
    good = {"type": "gridshape", "width": 10, "height": 8, "shapes": [{"points": [[0, 0], [1, 0], [0, 1]], "tone": "a", "label": "A"}],
            "axis": [[5, 0], [5, 8]], "center": [1, 1]}
    assert gf.sanitize(good) == good and vq.sanitize(good) == good
    for bad in ({**good, "width": 20}, {**good, "axis": [[5, 0], [5, 0]]}, {**good, "center": [11, 1]},
                {**good, "shapes": [{"points": [[0, 0], [1, 0]], "tone": "a"}]}, {**good, "shapes": [{"points": [[0, 0], [1, 0], [0, 9]]}]},
                {**good, "shapes": [{"points": [[0, 0], [1, 0], [0, 1]], "tone": "red"}]}, {"type": "gridshape", "width": 10, "height": 8}):
        assert gf.sanitize(bad) == {}, bad
    assert vq.sanitize({"type": "geometry"}) == {}


def test_both_families_share_one_entry_point():
    assert set(vq.NODE_KINDS) == {"1-1", "1-2", "1-3", "1-4", "8-3", "4-1", "4-2", "4-3"}
    assert vq.FIGURE_TYPES == {"cubes", "gridshape"}
    assert vq.generate("4-2", "basic", 2, 1)[0]["figure"]["type"] == "gridshape"
    assert vq.generate("1-1", "basic", 1, 1)[0]["figure"]["type"] == "cubes"
    with pytest.raises(ValueError):
        vq.generate("2-1", "basic", 1, 1)


def test_grid_drawing_counts_and_escapes():
    fig = {"type": "gridshape", "width": 4, "height": 3, "shapes": [{"points": [[0, 0], [1, 0], [0, 1]], "tone": "a", "label": "<A>"}],
           "axis": [[2, 0], [2, 3]], "center": [1, 1],
           "panels": [{"label": "图A", "shapes": [{"points": [[0, 0], [1, 0], [0, 1]], "tone": "ghost", "label": ""}]}]}
    script = CUBES_JS + "var g=cyFigureShapes(" + json.dumps(fig) + ");var s=cyCubeSvgString(" + json.dumps(fig) + ");" \
        "console.log(JSON.stringify({poly:g.items.filter(function(i){return i.t==='polygon'}).length," \
        "lines:g.items.filter(function(i){return i.t==='line'}).length,circle:g.items.filter(function(i){return i.t==='circle'}).length," \
        "drawn:cyIsDrawnFigure(" + json.dumps(fig) + ")&&!cyIsDrawnFigure({type:'geometry'}),esc:s.indexOf('&lt;A&gt;')>0&&s.indexOf('<A>')<0}))"
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    # main: 5+4 grid lines + axis; panel: 5+4 grid lines; one polygon each; one centre point
    assert out == {"poly": 2, "lines": 19, "circle": 1, "drawn": True, "esc": True}


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.commit()
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    assert d["visualNodes"]["4-3"].startswith("旋转") and d["visualNodes"]["1-1"] == "看组合体选视图"
    base = f"/teacher/knowledge-maps/{mid}/nodes"
    saved = []
    for key in ("4-1", "4-2", "4-3"):
        for level in ("basic", "medium"):
            got = client.post(base + f"/{key}/visual", headers=th, json={"level": level, "count": 2}).json()
            assert len(got["items"]) == 2 and all(q["figure"]["type"] == "gridshape" for q in got["items"])
            r = client.post(base + f"/{key}/visual/save", headers=th, json={"level": level, "revision": rev, "questions": got["items"]})
            assert r.status_code == 200, r.text
            rev, saved = r.json()["revision"], saved + r.json()["saved"]
    with legacy.SessionLocal() as db:
        rows = db.scalars(select(legacy.Question).where(legacy.Question.id.in_(saved))).all()
        assert len(rows) == 12 and all(json.loads(q.figure_json)["type"] == "gridshape" for q in rows)
        assert {q.unit for q in rows} == {"图形的运动"} and {q.knowledge for q in rows} == {"轴对称", "平移", "旋转"}
    assert all(x["note"] == "" for x in client.get(base + "/4-3/questions", headers=th).json()["items"])
    m = client.get(f"/teacher/knowledge-maps/{mid}", headers=th).json()["map"]
    for u in m["units"]:
        u["learned"] = u["key"] == "U4"
    rev = client.put(f"/teacher/knowledge-maps/{mid}", headers=th, json={"map": m, "revision": rev}).json()["revision"]
    client.post(f"/teacher/knowledge-maps/{mid}/publish", headers=th, json={"revision": rev})
    diag = client.post("/student/knowledge-map/diagnosis", headers=sh).json()
    assert diag["count"] >= 6 and {q["figure"]["type"] for q in diag["questions"]} == {"gridshape"}
    assert "cyIsDrawnFigure(" in client.get("/v1/knowledge-map").text
    assert "cyIsDrawnFigure(fig)" in client.get("/classic?legacy=1&unified=1&page=assignments").text
    assert "window.cyIsDrawnFigure(fig)" in client.get("/v1/workspace").text
print("OK")
'''


def test_teacher_saves_grid_questions_and_pupils_get_them(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})
