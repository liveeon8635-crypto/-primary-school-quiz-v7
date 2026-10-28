from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from changying.services import exam_prep as ep

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exam_prep_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

MAP = {"units": [{"key": "U1"}, {"key": "U2"}],
       "nodes": [{"key": "1-1", "unit": "U1", "kind": "core", "enabled": True},
                 {"key": "1-2", "unit": "U1", "kind": "display", "enabled": True},
                 {"key": "1-3", "unit": "U1", "kind": "optional", "enabled": False},
                 {"key": "2-1", "unit": "U2", "kind": "core", "enabled": True}]}


def test_scope_keeps_question_bearing_points_of_the_chosen_units():
    assert [n["key"] for n in ep.scope_nodes(MAP, ["U1"])] == ["1-1"]
    assert [n["key"] for n in ep.scope_nodes(MAP, ["U1", "U2"])] == ["1-1", "2-1"]


def test_compose_spreads_over_points_and_cycles_levels():
    nodes = ep.scope_nodes(MAP, ["U1", "U2"])
    pools = {"1-1": [(1, "basic"), (2, "medium"), (3, "hard"), (4, "medium"), (9, "basic")],
             "2-1": [(5, "medium"), (6, "basic"), (9, "medium")]}           # 9 sits under both points: used once
    plan = ep.compose(nodes, pools, 6)
    assert [k for k, _ in plan] == ["1-1", "2-1", "1-1", "2-1", "1-1", "2-1"]
    assert plan[0] == ("1-1", 2) and plan[1] == ("2-1", 5)                # medium first
    assert plan[2] == ("1-1", 1) and plan[3] == ("2-1", 6)                # then basic
    qids = [q for _, q in plan]
    assert len(set(qids)) == len(qids)
    assert len(ep.compose(nodes, pools, 40)) == 7                          # stops when every pool is used up


def test_losses_and_the_three_points_to_work_on():
    plan = [("a", 1), ("a", 2), ("b", 3), ("b", 4), ("c", 5), ("d", 6), ("d", 7), ("d", 8)]
    answers = {1: True, 2: False, 3: False, 4: False, 5: False, 6: False, 7: True}      # 8 left unanswered
    per = ep.losses(plan, answers)
    assert per == {"a": {"asked": 2, "lost": 1}, "b": {"asked": 2, "lost": 2}, "c": {"asked": 1, "lost": 1},
                   "d": {"asked": 3, "lost": 2}}
    # Most questions lost first; tie broken by the share lost (b 2/2 before d 2/3); then c (1/1) before a (1/2).
    assert ep.top_losses(per, ["a", "b", "c", "d"]) == ["b", "d", "c"]
    assert ep.score(plan, answers) == 25
    assert ep.top_losses(ep.losses(plan, {q: True for _, q in plan}), list("abcd")) == []
    assert ep.class_points(plan, [answers, {q: True for _, q in plan}])["d"] == {"asked": 6, "lost": 2}


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.commit()
    assert client.get("/v1/exam-prep").status_code == 200
    assert "href='/v1/exam-prep'" in client.get("/v1/workspace").text      # entry shown with the knowledge map
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    base = f"/teacher/knowledge-maps/{mid}/nodes"
    items = {}
    for key in ("6-1", "6-2", "6-3", "6-4"):
        for level in ("basic", "medium"):
            got = client.post(base + f"/{key}/visual", headers=th, json={"level": level, "count": 2}).json()
            r = client.post(base + f"/{key}/visual/save", headers=th, json={"level": level, "revision": rev, "questions": got["items"]}).json()
            rev = r["revision"]
            for qid, q in zip(r["saved"], got["items"]):
                items[qid] = (key, q)
    lst = client.get("/teacher/exam-goals", headers=th).json()
    assert lst["items"] == [] and lst["maps"] == []                      # nothing until the map is published
    client.post(f"/teacher/knowledge-maps/{mid}/publish", headers=th, json={"revision": rev})
    lst = client.get("/teacher/exam-goals", headers=th).json()
    cid = lst["classes"][0]["id"]
    assert lst["maps"][0]["id"] == mid
    goal = {"mapId": mid, "classId": cid, "title": "期末", "examDate": "2027-01-15", "unitKeys": ["U6"]}
    assert client.post("/teacher/exam-goals", headers=th, json={**goal, "unitKeys": ["U99"]}).status_code == 400
    assert client.post("/teacher/exam-goals", headers=th, json={**goal, "examDate": "2027-02-30"}).status_code == 400
    assert client.post("/teacher/exam-goals", headers=sh, json=goal).status_code == 403
    g = client.post("/teacher/exam-goals", headers=th, json=goal).json()
    assert [u["key"] for u in g["units"]] == ["U6"] and {p["key"] for p in g["points"]} >= {"6-1", "6-2", "6-3", "6-4"}
    # The mock paper: every saved question, spread over the four points, sent to the class as homework.
    r = client.post(f"/teacher/exam-goals/{g['id']}/mock", headers=th, json={"count": 16, "timeLimit": 45})
    assert r.status_code == 200, r.text
    mock = r.json()
    assert mock["questionCount"] == 16 and mock["recipients"] == 1 and not mock["short"]
    with legacy.SessionLocal() as db:
        a = db.get(legacy.Assignment, mock["assignmentId"])
        qids = json.loads(db.get(legacy.Paper, a.paper_id).question_ids_json)
        setting = db.scalar(select(legacy.AssignmentSubmissionSetting).where(legacy.AssignmentSubmissionSetting.assignment_id == a.id))
    assert set(qids) == set(items) and a.class_id == cid and "45 分钟" in setting.instructions
    assert [items[q][0] for q in qids[:4]] == ["6-1", "6-2", "6-3", "6-4"]
    # Before anyone hands in: the pupil is listed as not handed in.
    an = client.get(f"/teacher/exam-goals/{g['id']}/papers/{mock['id']}/analysis", headers=th).json()
    assert an["handedIn"] == 0 and an["pupils"][0]["handedIn"] is False
    # The pupil gets 6-1 and 6-2 right, all of 6-4 and half of 6-3 wrong.
    wrong_63 = [q for q in qids if items[q][0] == "6-3"][:2]
    sub = []
    for q in qids:
        key, item = items[q]
        bad = key == "6-4" or q in wrong_63
        if item["question_type"] == "fill_blank":
            sub.append({"question_id": q, "text_answer": "99999" if bad else item["answer"]})
        else:
            sub.append({"question_id": q, "selected_index": (item["correct_index"] + 1) % 4 if bad else item["correct_index"]})
    assert client.post(f"/student/assignments/{mock['assignmentId']}/submit", headers=sh, json={"answers": sub}).status_code == 200
    an = client.get(f"/teacher/exam-goals/{g['id']}/papers/{mock['id']}/analysis", headers=th).json()
    me = an["pupils"][0]
    assert an["handedIn"] == 1 and me["score"] == round(100 * 10 / 16)
    assert [f["key"] for f in me["focus"]] == ["6-4", "6-3"] and me["focus"][0]["lost"] == 4 and me["focus"][1]["lost"] == 2
    assert [p["key"] for p in an["points"]][:2] == ["6-4", "6-3"] and an["points"][0]["rate"] == 100
    detail = client.get(f"/teacher/exam-goals/{g['id']}", headers=th).json()
    assert detail["papers"][0]["handedIn"] == 1 and detail["papers"][0]["questionCount"] == 16
    # Another teacher's goal is out of reach; the feature hides behind the knowledge-map flag.
    assert client.get("/teacher/exam-goals/999", headers=th).status_code == 404
    os.environ["KNOWLEDGE_MAP"] = "0"
    assert client.get("/teacher/exam-goals", headers=th).status_code == 404
    assert client.get("/v1/exam-prep").status_code == 404
print("OK")
'''


def test_mock_paper_and_lost_points_through_the_routes(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})

