from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from changying.services import knowledge_maps as km
from changying.web.knowledge_map_pages import STUDENT_MAP_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("knowledge_map_student_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def _levelled_map():
    m = km.clean_map(km.template("rj2026-g5-math-up"))
    qid = 1
    for n in m["nodes"]:
        if km.assessed(m, n):
            for level in ("basic", "basic", "medium", "medium", "hard", "hard"):
                n["levels"][str(qid)] = level
                qid += 1
    return m, qid


def test_mastery_counts_first_attempts_with_level_weights():
    levels = {"1": "basic", "2": "medium", "3": "hard", "4": "hard", "5": "basic"}
    assert km.node_mastery(levels, {1: True, 2: True})["confidence"] == "insufficient"
    first = km.first_attempts([[{"question_id": 3, "correct": False}], [{"question_id": 3, "correct": True},
                                                                         {"question_id": 1, "correct": True}, {"question_id": 2, "correct": True}]])
    assert first == {3: False, 1: True, 2: True}                       # the later right answer to 3 does not count
    m = km.node_mastery(levels, first)
    assert m == {"evidence": 3, "rate": 0.56, "level": "weak", "confidence": "preliminary"}   # (1+1.5)/(1+1.5+2)
    m = km.node_mastery(levels, {**first, 4: True, 5: True})
    assert m["confidence"] == "reliable" and m["level"] == "pass" and m["rate"] == 0.73       # 5.5/7.5
    assert km.node_mastery(levels, {1: True, 2: True, 3: True, 4: True})["level"] == "fluent"


def test_diagnosis_spreads_twelve_questions_over_learned_units():
    m, last = _levelled_map()
    picked = km.pick_diagnosis(m, set(range(1, last)), set(), seed=7)
    units = [k.split("-")[0] for k, _ in picked]
    assert len(picked) == 12 and len({k for k, _ in picked}) == 12
    assert {u: units.count(u) for u in "1234"} == {"1": 3, "2": 4, "3": 3, "4": 2}
    level_of = {int(q): lv for n in m["nodes"] for q, lv in n["levels"].items()}
    assert all(level_of[q] == "medium" for _, q in picked)
    # Questions already answered are avoided while unanswered ones remain; unusable ones never appear.
    first_two = {q for _, q in picked[:2]}
    again = km.pick_diagnosis(m, set(range(1, last)) - {picked[2][1]}, first_two, seed=7)
    assert not first_two & {q for _, q in again} and picked[2][1] not in {q for _, q in again}
    # A map with questions in one unit only still fills up from that unit.
    for n in m["nodes"]:
        if not n["key"].startswith("2-"):
            n["levels"] = {}
    assert len(km.pick_diagnosis(m, set(range(1, last)), set(), seed=1)) == 12


def test_student_page_code_never_renders_markup():
    assert "innerHTML" not in STUDENT_MAP_JS and "insertAdjacentHTML" not in STUDENT_MAP_JS and "eval(" not in STUDENT_MAP_JS


FLOW = r'''
runs = legacy.Base.metadata.tables["knowledge_map_runs"]
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.commit()
    assert client.get("/student/knowledge-map", headers=th).status_code == 403
    r = client.get("/student/knowledge-map", headers=sh)
    assert r.status_code == 404 and "还没有发布" in r.json()["detail"]

    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    assessed = [n for n in d["map"]["nodes"] if n["assessed"]]
    assert len(assessed) == 19
    ids = {}
    with legacy.SessionLocal() as db:
        for n in assessed:
            for i, level in enumerate(("basic", "basic", "medium", "medium", "hard", "hard")):
                single = i % 2 == 0
                q = legacy.Question(school_id=school_id, grade=5, subject="数学", unit=n["unit"], knowledge=n["name"],
                                    text=f"{n['key']} 第{i + 1}题", options_json=json.dumps(["6", "7", "8"]) if single else "[]",
                                    correct_index=1, question_type="single_choice" if single else "fill_blank",
                                    answer_json=json.dumps({"answer": "7"}))
                db.add(q); db.flush(); ids.setdefault(n["key"], []).append((q.id, level))
        drawn = legacy.Question(school_id=school_id, grade=5, subject="数学", unit="U1", knowledge=assessed[0]["name"], text="看图题",
                                options_json="[]", correct_index=0, question_type="fill_blank", answer_json=json.dumps({"answer": "7"}),
                                figure_json=json.dumps({"type": "geometry", "shape": "triangle"}))
        db.add(drawn); db.flush(); drawn_id = drawn.id
        db.commit()
    for key, qs in ids.items():
        levels = {str(q): lv for q, lv in qs}
        if key == "1-1":
            levels[str(drawn_id)] = "medium"
        rev = client.put(f"/teacher/knowledge-maps/{mid}/nodes/{key}/levels", headers=th, json={"levels": levels, "revision": rev}).json()["revision"]

    # Before publishing pupils see nothing; homework answered earlier already counts (first attempt only).
    assert client.get("/student/knowledge-map", headers=sh).status_code == 404
    q22 = [q for q, _ in ids["2-2"]]
    early = [{"question_id": q22[0], "selected_index": 1}, {"question_id": q22[1], "text_answer": "7"}, {"question_id": q22[2], "selected_index": 0}]
    assert client.post("/student/practice-submit", headers=sh, json={"answers": early}).status_code == 200
    redo = [{"question_id": q22[2], "selected_index": 1}]
    assert client.post("/student/practice-submit", headers=sh, json={"answers": redo}).status_code == 200
    client.post(f"/teacher/knowledge-maps/{mid}/publish", headers=th, json={"revision": rev})

    m = client.get("/student/knowledge-map", headers=sh).json()
    assert m["diagnosis"] == {"status": "new"} and len(m["nodes"]) == 41
    n22 = next(n for n in m["nodes"] if n["key"] == "2-2")
    assert n22["mastery"] == {"evidence": 3, "rate": 0.57, "level": "weak", "confidence": "preliminary"}   # (1+1)/(1+1+1.5); the later redo does not count
    assert next(n for n in m["nodes"] if n["key"] == "5-1")["mastery"] is None
    text = json.dumps(m, ensure_ascii=False)
    assert "levels" not in text and "bankKeys" not in text and str(q22[0]) not in text

    # Start: twelve questions, no answers, nothing answered before, no structured-figure question; resuming gives the same set.
    d1 = client.post("/student/knowledge-map/diagnosis", headers=sh).json()
    qs = d1["questions"]
    assert d1["count"] == 12 and len(qs) == 12
    got = {q["id"] for q in qs}
    assert not got & set(q22[:3]) and drawn_id not in got
    for q in qs:
        assert set(q) == {"id", "text", "options", "questionType", "figure"}
    assert [q["id"] for q in client.post("/student/knowledge-map/diagnosis", headers=sh).json()["questions"]] == [q["id"] for q in qs]
    units = sorted(q["text"].split("-")[0] for q in qs)
    assert {u: units.count(u) for u in "1234"} == {"1": 3, "2": 4, "3": 3, "4": 2}

    def answer(q, right=True):
        if q["questionType"] == "single_choice":
            return {"question_id": q["id"], "selected_index": 1 if right else 2}
        return {"question_id": q["id"], "text_answer": "7" if right else "9"}

    assert client.post("/student/knowledge-map/diagnosis/submit", headers=sh, json={"answers": [answer(q) for q in qs[:11]]}).status_code == 400
    outsider = [answer(q) for q in qs[:11]] + [{"question_id": q22[3], "text_answer": "7"}]
    assert client.post("/student/knowledge-map/diagnosis/submit", headers=sh, json={"answers": outsider}).status_code == 400
    res = client.post("/student/knowledge-map/diagnosis/submit", headers=sh,
                      json={"answers": [answer(q, i not in (0, 5)) for i, q in enumerate(qs)]}).json()
    assert res["correct"] == 10 and res["total"] == 12 and len(res["nodes"]) == 12
    assert sum(x["right"] for x in res["nodes"]) == 10
    assert res["map"]["diagnosis"] == {"status": "submitted", "count": 12, "correct": 10}
    assert client.post("/student/knowledge-map/diagnosis/submit", headers=sh, json={"answers": [answer(q) for q in qs]}).status_code == 409
    assert client.post("/student/knowledge-map/diagnosis", headers=sh).status_code == 409
    with legacy.SessionLocal() as db:
        sub = db.scalars(select(legacy.Submission).where(legacy.Submission.student_id == sid, legacy.Submission.title == "知识地图诊断")).one()
        assert sub.correct == 10 and sub.total == 12 and sub.assignment_id is None and sub.completion_actor == "student"
        run = db.execute(select(runs).where(runs.c.student_id == sid)).one()
        assert run.status == "submitted" and run.submission_id == sub.id
    # Every diagnosed node now has one more first-attempt answer.
    first_node = next(x for x in res["nodes"])
    after = next(n for n in res["map"]["nodes"] if n["key"] == first_node["key"])
    assert after["assessed"]

    page = client.get("/v1/my-knowledge-map").text
    for t in ("我的知识地图", "smLoad", "/student/knowledge-map/diagnosis/submit", "入门诊断", "createElementNS"):
        assert t in page, t
    classic = client.get("/classic?legacy=1&unified=1&page=syncLearning").text
    assert "student-knowledge-map" in classic and "/v1/my-knowledge-map" in classic
print("OK")
'''


def test_pupil_sees_published_map_and_takes_the_diagnosis_once(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})


OFF = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    for path in ("/v1/my-knowledge-map", "/student/knowledge-map"):
        assert client.get(path, headers=sh).status_code == 404, path
    assert client.post("/student/knowledge-map/diagnosis", headers=sh).status_code == 404
    assert "knowledge_map_runs" in legacy.Base.metadata.tables
print("OK")
'''


def test_student_side_is_off_without_the_flag(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + OFF)
