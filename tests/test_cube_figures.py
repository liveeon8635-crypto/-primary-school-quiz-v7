from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from changying.services import cube_figures as cf
from changying.web.cube_figures_js import CUBES_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cube_figure_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

DIR = {v: k for k, v in cf.DIRECTIONS.items()}


def test_views_follow_the_textbook_convention():
    h = [[2, 0], [1, 1]]                       # back row: a stack of 2 on the left; front row: 1 and 1
    assert cf.view(h, "front") == [[1, 0], [1, 1]]
    assert cf.view(h, "top") == [[1, 0], [1, 1]]
    # From the left the solid's front is on the viewer's right: back row (2 high) left, front row (1 high) right.
    assert cf.view(h, "left") == [[1, 0], [1, 1]]
    assert cf.view([[1], [2]], "left") == [[0, 1], [1, 1]]
    assert cf.view([[0, 1, 0], [1, 1, 1]], "top") == [[0, 1, 0], [1, 1, 1]]


def test_hidden_cubes_are_rejected():
    assert cf.all_visible([[1, 1], [1, 1]]) and cf.all_visible([[2, 1]])
    assert not cf.all_visible([[1, 1], [2, 2]])           # the taller front row hides the whole back row


@pytest.mark.parametrize("key", ["1-1", "1-2", "1-3", "1-4"])
@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_every_generated_question_has_exactly_one_right_option(key, level):
    qs = cf.generate(key, level, 5, 7)
    assert len(qs) == 5
    for q in qs:
        fig = q["figure"]
        assert cf.sanitize(fig) == fig and q["options"] == ["图A", "图B", "图C", "图D"] and 0 <= q["correct_index"] < 4
        solids = ([fig["solid"]] if "solid" in fig else []) + [p["solid"] for p in fig["panels"] if "solid" in p]
        assert all(cf.all_visible(s) for s in solids)
        options = [p for p in fig["panels"] if p["label"] in "ABCD"]
        assert [p["label"] for p in options] == ["A", "B", "C", "D"]
        kind = cf.NODE_KINDS[key]
        if kind == "view":
            d = DIR[re.search(r"从(前面|上面|左面)看", q["text"]).group(1)]
            hits = [i for i, p in enumerate(options) if p["view"] == cf.view(fig["solid"], d)]
        elif kind == "same_view":
            d = DIR[re.search(r"从(前面|上面|左面)看到的也是", q["text"]).group(1)]
            target = fig["panels"][0]["view"]
            hits = [i for i, p in enumerate(options) if cf.view(p["solid"], d) == target]
        else:
            given = {DIR[p["label"]]: p["view"] for p in fig["panels"] if p["label"] in DIR}
            assert len(given) == (2 if kind == "two_views" else 3)
            hits = [i for i, p in enumerate(options) if all(cf.view(p["solid"], d) == v for d, v in given.items())]
        assert hits == [q["correct_index"]], (key, level, q)
        assert q["explanation"].endswith(f"所以选 {'ABCD'[q['correct_index']]}。")


def test_sanitize_rejects_bad_figures():
    good = {"type": "cubes", "solid": [[1, 2]], "panels": [{"label": "A", "view": [[0, 1], [1, 1]]}]}
    assert cf.sanitize(good) == good
    for bad in ({"type": "cubes", "solid": [[5]]}, {"type": "cubes", "solid": [[1, "2"]]}, {"type": "cubes", "solid": [[1], [1, 1]]},
                {"type": "cubes", "solid": [[0]]}, {"type": "cubes", "panels": [{"label": "A", "view": [[2]]}]},
                {"type": "cubes", "panels": [{"label": "A"}]}, {"type": "cubes"}, {"type": "cubes", "solid": [[True]]},
                {"type": "cubes", "panels": [{"label": "A", "view": [[1]]}] * 8}):
        assert cf.sanitize(bad) == {}, bad


def test_drawing_code_has_no_markup_injection_and_draws_every_cube():
    assert "innerHTML" not in CUBES_JS and "eval(" not in CUBES_JS
    fig = {"type": "cubes", "solid": [[1, 2], [1, 0]], "panels": [{"label": "A", "view": [[0, 1], [1, 1]]},
                                                               {"label": "<b>", "solid": [[1]]}]}
    script = CUBES_JS + "var g=cyCubeShapes(" + json.dumps(fig) + ");var s=cyCubeSvgString(" + json.dumps(fig) + ");" \
        "console.log(JSON.stringify({poly:g.items.filter(function(i){return i.t==='polygon'}).length," \
        "rect:g.items.filter(function(i){return i.t==='rect'}).length,w:g.w,h:g.h,esc:s.indexOf('&lt;b&gt;')>0&&s.indexOf('<b>')<0}))"
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    # 4 cubes in the main solid + 1 in panel B, three faces each; 3 view cells + 2 panel frames
    assert out["poly"] == 15 and out["rect"] == 5 and out["w"] > 0 and out["h"] > 0 and out["esc"] is True


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.commit()
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    assert d["visualNodes"]["1-1"] == "看组合体选视图" and "2-1" not in d["visualNodes"]
    base = f"/teacher/knowledge-maps/{mid}/nodes"
    assert client.post(base + "/2-1/visual", headers=th, json={"level": "basic", "count": 2}).status_code == 404
    assert client.post(base + "/1-1/visual", headers=sh, json={"level": "basic", "count": 2}).status_code == 403
    assert client.post(base + "/1-1/visual", headers=th, json={"level": "easy", "count": 2}).status_code == 400

    saved_ids = []
    for key in ("1-1", "1-2", "1-3", "1-4"):
        for level in ("basic", "medium"):
            got = client.post(base + f"/{key}/visual", headers=th, json={"level": level, "count": 2}).json()
            assert len(got["items"]) == 2 and got["level"] == level
            qs = [{**q, "text": q["text"] + "（老师改过）"} if i == 0 else q for i, q in enumerate(got["items"])]
            r = client.post(base + f"/{key}/visual/save", headers=th, json={"level": level, "revision": rev, "questions": qs})
            assert r.status_code == 200, r.text
            rev = r.json()["revision"]
            saved_ids += r.json()["saved"]
    bad = dict(got["items"][0]); bad["figure"] = {"type": "cubes", "solid": [[9]]}
    assert client.post(base + "/1-4/visual/save", headers=th, json={"level": "basic", "revision": rev, "questions": [bad]}).status_code == 400
    assert client.post(base + "/1-4/visual/save", headers=th, json={"level": "basic", "revision": rev - 1, "questions": got["items"]}).status_code == 409

    with legacy.SessionLocal() as db:
        rows = db.scalars(select(legacy.Question).where(legacy.Question.id.in_(saved_ids))).all()
        assert len(rows) == 16
        for q in rows:
            fig = json.loads(q.figure_json)
            assert fig["type"] == "cubes" and q.question_type == "single_choice" and json.loads(q.options_json) == ["图A", "图B", "图C", "图D"]
            assert q.textbook == "人教版" and q.unit == "观察简单组合体" and q.grade == 5
        assert {q.knowledge for q in rows} == {"从不同位置观察同一组合体", "从同一位置观察不同组合体", "根据三个方向的图形确定组合体",
                                               "根据三个方向的图形还原组合体"}
        assert sum("老师改过" in q.text for q in rows) == 8
    listed = client.get(base + "/1-1/questions", headers=th).json()["items"]
    assert len(listed) == 4 and all(x["note"] == "" for x in listed)      # cube pictures are fine for the diagnosis

    # The existing AI-save path keeps a cubes figure too (the legacy whitelist used to drop it).
    one = got["items"][0]
    kept = client.post("/ai/questions/save", headers=th, json={"questions": [{**one, "grade": 5, "subject": "数学", "textbook": "人教版",
        "semester": "上册", "unit": "观察简单组合体", "knowledge": "测试"}]}).json()["items"][0]
    assert kept["figure"]["type"] == "cubes" and kept["figure"]["panels"][0]["label"] in ("前面", "A", "图①")

    # Publish with U1 only learned; the pupil's diagnosis now picks picture questions and gets their figures.
    m = client.get(f"/teacher/knowledge-maps/{mid}", headers=th).json()["map"]
    for u in m["units"]:
        u["learned"] = u["key"] == "U1"
    rev = client.put(f"/teacher/knowledge-maps/{mid}", headers=th, json={"map": m, "revision": rev}).json()["revision"]
    client.post(f"/teacher/knowledge-maps/{mid}/publish", headers=th, json={"revision": rev})
    diag = client.post("/student/knowledge-map/diagnosis", headers=sh).json()
    assert diag["count"] >= 6 and all(q["figure"]["type"] == "cubes" for q in diag["questions"])
    assert "correctIndex" not in json.dumps(diag) and "explanation" not in json.dumps(diag)

    teacher_page = client.get("/v1/knowledge-map").text
    for t in ("cyCubeSvgNode(", "kmVisual(", "生成图形题", "/visual/save"):
        assert t in teacher_page, t
    assert "cyCubeSvgNode(" in client.get("/v1/my-knowledge-map").text
    for path in ("/classic?legacy=1&unified=1&page=assignments", "/classic?legacy=1&embedded=1"):   # pupils' homework pages
        classic = client.get(path).text
        assert "changying_cube_figures_v1" in classic and "wrap('renderQuestionFigure')" in classic, path
    v1 = client.get("/v1/workspace").text
    assert "return window.cyCubeSvgString(fig);" in v1 and "changying_cube_figures_v1" in v1
print("OK")
'''


def test_teacher_generates_saves_and_pupils_get_picture_questions(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})


CLASSIC_RENDER = r'''
const fs=require('fs');
const html=fs.readFileSync(process.argv[1],'utf8');
const scripts=[...html.matchAll(/<script id="changying_cube_figures_v1">([\s\S]*?)<\/script>/g)].map(m=>m[1]);
global.window=global;
global.renderQuestionFigure=function(fig){return 'old:'+fig.type};
eval(scripts[0]);
const a=renderQuestionFigure({type:'cubes',solid:[[1,1]]}), b=renderQuestionFigure({type:'geometry'});
console.log(JSON.stringify({cubes:a.indexOf('<svg')>=0&&a.indexOf('polygon')>0, other:b}));
'''


def test_classic_figure_function_is_wrapped_for_cubes(tmp_path):
    from changying.web.cube_figures_js import patch_cube_figures
    page = tmp_path / "classic.html"
    page.write_text(patch_cube_figures("<html><body></body></html>"), encoding="utf-8")
    out = subprocess.run(["node", "-e", CLASSIC_RENDER, str(page)], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == {"cubes": True, "other": "old:geometry"}
