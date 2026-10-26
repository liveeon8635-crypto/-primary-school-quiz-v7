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
    classes = client.get(f"/teacher/knowledge-maps/{mid}/classes", headers=th).json()["items"]
    assert classes and client.get(f"/teacher/knowledge-maps/{mid}/classes", headers=sh).status_code == 403
    r = client.get(f"/teacher/knowledge-maps/{mid}/classes/{classes[0]['id']}", headers=th)
    assert r.status_code == 409 and "发布" in r.json()["detail"]
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
    # Twelve answers judge units, not single nodes: 第二单元 pools the diagnosis with the earlier homework.
    units = {u["key"]: u["mastery"] for u in res["map"]["units"]}
    assert units["U5"] is None and units["U1"]["evidence"] == 3 and units["U1"]["level"] is not None
    assert units["U2"]["evidence"] == 7 and units["U2"]["confidence"] == "reliable"

    # The teacher's class view uses the same first-attempt rules as the pupil's map.
    mine = None
    for c in classes:
        view = client.get(f"/teacher/knowledge-maps/{mid}/classes/{c['id']}", headers=th).json()
        mine = next((st for st in view["students"] if st["id"] == sid), None)
        if mine:
            break
    assert mine is not None
    assert mine["diagnosis"] == {"status": "submitted", "count": 12, "correct": 10}
    assert mine["units"] == {u["key"]: u["mastery"] for u in res["map"]["units"]}
    assert mine["nodes"]["2-2"] == next(n for n in res["map"]["nodes"] if n["key"] == "2-2")["mastery"]
    assert [u["key"] for u in view["units"]] == ["U1", "U2", "U3", "U4"] and len(view["nodes"]) == 19
    for key, c in view["tally"].items():
        assert sum(c.values()) == len(view["students"]), key
    assert view["tally"]["2-2"]["weak"] >= 1
    assert client.get(f"/teacher/knowledge-maps/{mid}/classes/999999", headers=th).status_code == 404

    # One click: consolidation homework for a weak pupil from the node's levelled questions the pupil never answered.
    rbase = f"/teacher/knowledge-maps/{mid}/classes/{view['classId']}/reinforce"
    assert client.post(rbase, headers=th, json={"nodeKey": "2-2", "studentIds": [999999], "count": 4}).status_code == 400
    assert client.post(rbase, headers=th, json={"nodeKey": "5-1", "studentIds": [sid], "count": 4}).status_code == 404
    answered = set()
    with legacy.SessionLocal() as db:
        for raw in db.scalars(select(legacy.Submission.answers_json).where(legacy.Submission.student_id == sid)):
            answered |= {int(a["question_id"]) for a in json.loads(raw)}
    before = mine["nodes"]["2-2"]["evidence"]
    r = client.post(rbase, headers=th, json={"nodeKey": "2-2", "studentIds": [sid], "count": 4}).json()
    one = r["results"][0]
    assert one["ok"] and r["node"]["name"] == "小数乘小数"
    with legacy.SessionLocal() as db:
        a = db.get(legacy.Assignment, one["assignmentId"])
        paper_ids = json.loads(db.get(legacy.Paper, a.paper_id).question_ids_json)
        qrows = {q.id: q for q in db.scalars(select(legacy.Question).where(legacy.Question.id.in_(paper_ids)))}
    remaining = [q for q, _ in ids["2-2"] if q not in answered]
    assert paper_ids == remaining[:4] and one["questionCount"] == len(paper_ids) and not set(paper_ids) & answered
    assert a.title == "知识地图巩固 · 小数乘小数"
    again = client.post(rbase, headers=th, json={"nodeKey": "2-2", "studentIds": [sid], "count": 4}).json()["results"][0]
    assert not again["ok"] and "未完成" in again["reason"]
    # The pupil does it as normal homework; each answer is a first attempt and the map moves.
    sub = [{"question_id": q, "selected_index": 1} if qrows[q].question_type == "single_choice" else {"question_id": q, "text_answer": "7"}
           for q in paper_ids]
    assert client.post(f"/student/assignments/{one['assignmentId']}/submit", headers=sh, json={"answers": sub}).status_code == 200
    m2 = client.get("/student/knowledge-map", headers=sh).json()
    assert next(n for n in m2["nodes"] if n["key"] == "2-2")["mastery"]["evidence"] == before + len(paper_ids)
    done = client.post(rbase, headers=th, json={"nodeKey": "2-2", "studentIds": [sid], "count": 4}).json()["results"][0]
    assert not done["ok"] and "补题" in done["reason"]

    # The teacher's own judgement per pupil and unit, compared with the map (units with too little evidence do not count).
    vb = f"/teacher/knowledge-maps/{mid}/classes/{view['classId']}"
    v = client.get(vb, headers=th).json()
    assert v["agreement"] == {"rated": 0, "compared": 0, "agreed": 0, "threshold": 0.8, "rate": None, "passed": False}
    me = next(st for st in v["students"] if st["id"] == sid)
    u1, u2 = me["units"]["U1"]["level"], me["units"]["U2"]["level"]
    assert u1 and u2 and me["units"]["U4"]["level"] is None
    other = next(x for x in ("weak", "pass", "fluent") if x != u2)
    for bad in ({"studentId": sid, "unitKey": "U5", "level": "weak"}, {"studentId": sid, "unitKey": "U1", "level": "good"},
                {"studentId": 999999, "unitKey": "U1", "level": "weak"}):
        assert client.put(vb + "/ratings", headers=th, json={"ratings": [bad]}).status_code == 400, bad
    assert client.put(vb + "/ratings", headers=sh, json={"ratings": []}).status_code == 403
    v = client.put(vb + "/ratings", headers=th, json={"ratings": [
        {"studentId": sid, "unitKey": "U1", "level": u1}, {"studentId": sid, "unitKey": "U2", "level": other},
        {"studentId": sid, "unitKey": "U4", "level": "weak"}]}).json()
    assert v["agreement"] == {"rated": 3, "compared": 2, "agreed": 1, "threshold": 0.8, "rate": 0.5, "passed": False}
    assert next(st for st in v["students"] if st["id"] == sid)["ratings"] == {"U1": u1, "U2": other, "U4": "weak"}
    v = client.put(vb + "/ratings", headers=th, json={"ratings": [{"studentId": sid, "unitKey": "U2", "level": u2}]}).json()
    assert v["agreement"]["agreed"] == 2 and v["agreement"]["rate"] == 1.0 and v["agreement"]["passed"] is True
    v = client.put(vb + "/ratings", headers=th, json={"ratings": [{"studentId": sid, "unitKey": "U4", "level": None}]}).json()
    assert v["agreement"]["rated"] == 2
    with legacy.SessionLocal() as db:
        kr = legacy.Base.metadata.tables["knowledge_map_ratings"]
        assert db.execute(select(kr.c.unit_key, kr.c.level).where(kr.c.student_id == sid).order_by(kr.c.unit_key)).all() == [("U1", u1), ("U2", u2)]
    assert "保存我的判断" in client.get("/v1/knowledge-map").text
    assert "查看全班掌握情况" in client.get("/v1/knowledge-map").text

    page = client.get("/v1/my-knowledge-map").text
    for t in ("我的知识地图", "smLoad", "/student/knowledge-map/diagnosis/submit", "入门诊断", "createElementNS"):
        assert t in page, t
    classic = client.get("/classic?legacy=1&unified=1&page=syncLearning").text
    assert "student-knowledge-map" in classic and "/v1/my-knowledge-map" in classic
print("OK")
'''


def test_pupil_takes_the_diagnosis_once_and_the_teacher_sees_the_class(tmp_path):
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
