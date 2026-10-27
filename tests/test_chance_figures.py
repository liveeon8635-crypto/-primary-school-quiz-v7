from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from changying.services import chance_figures as ch
from changying.services import visual_questions as vq
from changying.web.cube_figures_js import CUBES_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("chance_figure_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

NAME = {v: k for k, v in ch.COLORS.items()}


def counts_of(fig):
    if fig["kind"] == "spinner":
        out = {}
        for c in fig["sectors"]:
            out[c] = out.get(c, 0) + 1
        return out
    return {r["color"]: r["count"] for r in fig["balls" if fig["kind"] == "box" else "rows"]}


def holds(statement, counts):
    total = sum(counts.values())
    m = re.fullmatch(r"摸到(.)球的可能性比(.)球大", statement)
    if m:
        return counts.get(NAME[m.group(1)], 0) > counts.get(NAME[m.group(2)], 0)
    word, color = re.fullmatch(r"(一定|可能|不可能)摸到(.)球", statement).groups()
    n = counts.get(NAME[color], 0)
    return {"一定": n == total, "可能": n > 0, "不可能": n == 0}[word]


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_exactly_one_statement_is_true(level):
    qs = ch.generate("7-1", level, 8, 3)
    assert len(qs) == 8
    for q in qs:
        assert ch.sanitize(q["figure"]) == q["figure"] and q["figure"]["kind"] == "box"
        counts = counts_of(q["figure"])
        assert [i for i, o in enumerate(q["options"]) if holds(o, counts)] == [q["correct_index"]], q


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_most_and_least_likely_colours(level):
    qs = ch.generate("7-2", level, 8, 5)
    assert len(qs) == 8
    kinds = set()
    for q in qs:
        fig = q["figure"]
        assert ch.sanitize(fig) == fig
        kinds.add(fig["kind"])
        counts = counts_of(fig)
        if q["question_type"] == "fill_blank":                    # put in more of the rarest colour
            color = NAME[re.search(r"个(.)球，摸到", q["text"]).group(1)]
            more = int(q["answer"])
            others = max(n for c, n in counts.items() if c != color)
            assert counts[color] + more > others >= counts[color] + more - 1
            continue
        pick = max if "最大" in q["text"] else min
        best = pick(counts, key=counts.get)
        assert list(counts.values()).count(counts[best]) == 1
        assert q["options"][q["correct_index"]] == ch.COLORS[best] + "色"
    if level == "medium":
        assert kinds == {"box", "spinner"}


@pytest.mark.parametrize("level", ["basic", "medium", "hard"])
def test_guess_from_drawing_results(level):
    qs = ch.generate("7-3", level, 8, 7)
    assert len(qs) == 8
    for q in qs:
        fig = q["figure"]
        assert ch.sanitize(fig) == fig and fig["kind"] == "tally"
        counts = counts_of(fig)
        trials = sum(counts.values())
        assert f"摸 {trials} 次" in fig["title"]
        if level == "basic":
            top = max(counts, key=counts.get)
            assert q["options"][q["correct_index"]] == ch.COLORS[top] + "色"
            continue
        # Each option is a box of 10 balls; the right one is clearly the closest to the share of each colour drawn.
        def gap(option):
            box = {NAME[c]: int(n) for c, n in re.findall(r"(.)球 (\d+) 个", option)}
            assert sum(box.values()) == 10
            return sum(abs(box[c] - counts[c] * 10 / trials) for c in counts)
        gaps = [gap(o) for o in q["options"]]
        right = gaps[q["correct_index"]]
        assert all(g >= right + 1 for i, g in enumerate(gaps) if i != q["correct_index"]), (gaps, q)


def test_review_8_5_mixes_the_three_kinds():
    qs = vq.generate("8-5", "medium", 6, 2)
    assert len(qs) == 6 and "可能性" in vq.NODE_LABELS["8-5"]
    assert {q["figure"]["kind"] for q in qs} >= {"box", "tally"}
    assert {"7-1", "7-2", "7-3", "8-5"} <= set(vq.NODE_KINDS) and "chance" in vq.FIGURE_TYPES


def test_chance_figures_are_checked():
    good = {"type": "chance", "kind": "box", "balls": [{"color": "red", "count": 3}, {"color": "white", "count": 2}]}
    assert ch.sanitize(good) == good
    for bad in ({"kind": "jar"}, {"balls": [{"color": "pink", "count": 3}]}, {"balls": [{"color": "red", "count": 21}]},
                {"balls": [{"color": "red", "count": 2}, {"color": "red", "count": 1}]}, {"balls": [{"color": "red", "count": 0}]}):
        assert ch.sanitize({**good, **bad}) == {}, bad
    assert ch.sanitize({"type": "chance", "kind": "spinner", "sectors": ["red"]}) == {}
    assert ch.sanitize({"type": "chance", "kind": "spinner", "sectors": ["red", "blue"] * 7}) == {}
    assert vq.sanitize(good) == good


def test_browser_draws_box_spinner_and_results():
    figs = [{"type": "chance", "kind": "box", "balls": [{"color": "red", "count": 3}, {"color": "yellow", "count": 2}]},
            {"type": "chance", "kind": "spinner", "sectors": ["red", "blue", "red", "yellow"]},
            {"type": "chance", "kind": "tally", "rows": [{"color": "red", "count": 12}, {"color": "blue", "count": 8}], "title": "摸 20 次的结果"}]
    script = CUBES_JS + "console.log(JSON.stringify(" + json.dumps(figs) + ".map(function(f){var g=cyFigureShapes(f);" \
        "return {drawn:cyIsDrawnFigure(f),balls:g.items.filter(function(i){return i.t==='circle'}).length," \
        "sectors:g.items.filter(function(i){return i.t==='path'&&/ A/.test(i.a.d)}).length,bars:g.items.filter(function(i){return i.t==='rect'}).length," \
        "texts:g.items.filter(function(i){return i.t==='text'}).map(function(i){return i.s})}})))"
    box, spin, tally = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert box["drawn"] and box["balls"] == 5 and box["texts"] == ["红", "红", "红", "黄", "黄"]
    assert spin["sectors"] == 4 and spin["texts"] == ["红", "蓝", "红", "黄"]
    assert tally["bars"] == 2 and tally["texts"] == ["摸 20 次的结果", "红", "12 次", "蓝", "8 次"]


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.commit()
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    base = f"/teacher/knowledge-maps/{mid}/nodes"
    answers = {}
    for key in ("7-1", "7-2", "7-3"):
        for level in ("basic", "hard"):
            got = client.post(base + f"/{key}/visual", headers=th, json={"level": level, "count": 2}).json()
            r = client.post(base + f"/{key}/visual/save", headers=th, json={"level": level, "revision": rev, "questions": got["items"]})
            assert r.status_code == 200, r.text
            rev = r.json()["revision"]
            answers.update(zip(r.json()["saved"], got["items"]))
    with legacy.SessionLocal() as db:
        rows = {q.id: q for q in db.scalars(select(legacy.Question).where(legacy.Question.id.in_(list(answers))))}
    assert len(rows) == 12 and {r.unit for r in rows.values()} == {"可能性"}
    assert all(json.loads(rows[i].figure_json) == q["figure"] for i, q in answers.items())
    # Pupils who have learned the unit meet the pictures in the diagnosis and are graded.
    m = client.get(f"/teacher/knowledge-maps/{mid}", headers=th).json()["map"]
    for u in m["units"]:
        u["learned"] = u["key"] == "U7"
    rev = client.put(f"/teacher/knowledge-maps/{mid}", headers=th, json={"map": m, "revision": rev}).json()["revision"]
    client.post(f"/teacher/knowledge-maps/{mid}/publish", headers=th, json={"revision": rev})
    diag = client.post("/student/knowledge-map/diagnosis", headers=sh).json()
    assert diag["count"] >= 6 and all(q["figure"]["type"] == "chance" for q in diag["questions"])
    sub = [{"question_id": q["id"], "text_answer": answers[q["id"]]["answer"]} if answers[q["id"]]["question_type"] == "fill_blank"
           else {"question_id": q["id"], "selected_index": answers[q["id"]]["correct_index"]} for q in diag["questions"]]
    res = client.post("/student/knowledge-map/diagnosis/submit", headers=sh, json={"answers": sub}).json()
    assert res["correct"] == res["total"] == diag["count"]
print("OK")
'''


def test_teacher_saves_chance_questions_and_pupils_are_graded(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})
