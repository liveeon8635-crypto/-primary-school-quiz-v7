"""Tests for textbook-agnostic Math Star Map (built-in questions) and Strong Exam Sprints."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from changying.services import exam_sprints as es
from changying.services import math_builtin_map as mbm
from changying.web.math_arena_pages import SPRINTS_JS, STAR_MAP_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("math_arena_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_builtin_math_map_and_all_nodes_generate_gradable_questions():
    m = mbm.get_builtin_math_map(5)
    assert m["textbookAgnostic"] is True
    assert len(m["units"]) == 4
    assert len(m["nodes"]) == 24
    for node in m["nodes"]:
        qs = mbm.generate_node_questions(node["key"], count=5, seed=3)
        assert len(qs) == 5, f"node {node['key']} should generate 5 questions"
        for q in qs:
            pub = mbm.public_question(q)
            assert "answer" not in pub and "correctIndex" not in pub
            if q["questionType"] in ("single_choice", "true_false"):
                assert mbm.grade_builtin_question(q, selected_index=q["correctIndex"]) is True
                wrong_idx = (int(q["correctIndex"]) + 1) % len(q["options"])
                assert mbm.grade_builtin_question(q, selected_index=wrong_idx) is False
            else:
                assert mbm.grade_builtin_question(q, text_answer=q["answer"]) is True
                assert mbm.grade_builtin_question(q, text_answer="") is False


def test_node_light_state_machine():
    assert mbm.compute_node_light_state(attempts=0, correct=0)["state"] == "unexplored"
    assert mbm.compute_node_light_state(attempts=5, correct=2)["state"] == "exploring"
    lit = mbm.compute_node_light_state(attempts=5, correct=4, best_quiz_rate=0.8)
    assert lit["state"] == "lit" and lit["stars"] == 1
    mastered = mbm.compute_node_light_state(attempts=5, correct=5, best_quiz_rate=1.0, hard_correct=1)
    assert mastered["state"] == "mastered" and mastered["stars"] == 3
    repair = mbm.compute_node_light_state(attempts=5, correct=4, best_quiz_rate=0.8, needs_repair=True)
    assert repair["state"] == "exploring" and repair["needsRepair"] is True


def test_exam_sprint_composition_and_strict_tier_grading():
    qs = es.compose_sprint_questions("math-comprehensive", seed=5)
    assert len(qs) == 15
    assert len({q["questionType"] for q in qs}) == 7  # all 7 math question types covered

    # Perfect answers with 20% time left -> L4
    all_right = {
        q["id"]: (
            {"selected_index": q["correctIndex"]}
            if q["questionType"] in ("single_choice", "true_false")
            else {"text_answer": q["answer"]}
        )
        for q in qs
    }
    res_l4 = es.evaluate_sprint_attempt(questions=qs, answers_by_id=all_right, elapsed_sec=900, time_limit_sec=1200)
    assert res_l4["tier"]["code"] == "L4" and res_l4["scoreRate"] == 100 and res_l4["topLosses"] == []

    # Same answers but timed out -> capped at L1 (strict exam rule)
    res_late = es.evaluate_sprint_attempt(
        questions=qs, answers_by_id=all_right, elapsed_sec=1260, time_limit_sec=1200, auto_submitted=True
    )
    assert res_late["timedOut"] is True and res_late["tier"]["code"] == "L1"

    # Unanswered -> 0 marks, L0, topLosses populated
    res_empty = es.evaluate_sprint_attempt(questions=qs, answers_by_id={}, elapsed_sec=1200, time_limit_sec=1200, auto_submitted=True)
    assert res_empty["earnedMarks"] == 0 and res_empty["tier"]["code"] == "L0"
    assert len(res_empty["topLosses"]) == 3


def test_math_arena_pages_have_no_unsafe_dom_calls():
    for src in (STAR_MAP_JS, SPRINTS_JS):
        assert "innerHTML" not in src and "insertAdjacentHTML" not in src and "eval(" not in src


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.commit()

    # HTML pages render cleanly
    assert client.get("/v1/math-star-map").status_code == 200
    assert client.get("/v1/math-sprints").status_code == 200

    # Role guard: teacher gets 403
    assert client.get("/student/math-star-map", headers=th).status_code == 403
    assert client.get("/student/math-sprints", headers=th).status_code == 403

    # 1. Knowledge Map works out-of-the-box without teacher publishing or importing
    m = client.get("/student/math-star-map", headers=sh).json()
    assert m["textbookAgnostic"] is True and m["summary"]["totalNodes"] == 24 and m["summary"]["litNodes"] == 0

    # Start & pass built-in node quiz -> node lights up
    qres = client.post("/student/math-star-map/nodes/M1-1/quiz", headers=sh).json()
    assert qres["count"] == 5 and len(qres["questions"]) == 5
    with legacy.SessionLocal() as db:
        qrow = db.execute(legacy.Base.metadata.tables["math_node_quizzes"].select()).first()
        full_qs = json.loads(qrow.items_json)
    answers = [
        {"question_id": q["id"], "selected_index": q["correctIndex"]}
        if q["questionType"] in ("single_choice", "true_false")
        else {"question_id": q["id"], "text_answer": q["answer"]}
        for q in full_qs
    ]
    sub = client.post("/student/math-star-map/nodes/M1-1/quiz/submit", headers=sh, json={"quiz_id": qres["quizId"], "answers": answers}).json()
    assert sub["litUp"] is True and sub["correct"] == 5
    assert sub["light"]["state"] == "mastered" and sub["light"]["stars"] == 3
    assert sub["map"]["summary"]["litNodes"] == 1
    # Milestone points: first lit (+3) + first mastered (+5) = +8 in PointLedger
    assert sub["pointsAwarded"]["total"] == 8 and sub["points"]["balance"] == 8

    # Idempotency: re-taking M1-1 awards 0 duplicate milestone points
    qres_again = client.post("/student/math-star-map/nodes/M1-1/quiz", headers=sh).json()
    with legacy.SessionLocal() as db:
        qrow2 = db.execute(
            legacy.Base.metadata.tables["math_node_quizzes"].select().where(
                legacy.Base.metadata.tables["math_node_quizzes"].c.id == qres_again["quizId"]
            )
        ).first()
        full_qs2 = json.loads(qrow2.items_json)
    answers2 = [
        {"question_id": q["id"], "selected_index": q["correctIndex"]}
        if q["questionType"] in ("single_choice", "true_false")
        else {"question_id": q["id"], "text_answer": q["answer"]}
        for q in full_qs2
    ]
    sub2 = client.post("/student/math-star-map/nodes/M1-1/quiz/submit", headers=sh, json={"quiz_id": qres_again["quizId"], "answers": answers2}).json()
    assert sub2["pointsAwarded"]["total"] == 0 and sub2["points"]["balance"] == 8

    # 2. Exam Sprint works independently without finishing map first
    sprints = client.get("/student/math-sprints", headers=sh).json()
    assert len(sprints["items"]) == 6
    vis_started = client.post("/student/math-sprints/visual-geometry-boss/start", headers=sh).json()
    assert vis_started["questionCount"] == 10
    assert sum(1 for q in vis_started["questions"] if q.get("figure")) >= 5
    started = client.post("/student/math-sprints/calc-speed/start", headers=sh).json()
    assert started["questionCount"] == 10 and started["timeLimitSec"] == 600

    # Submit empty (simulated auto-submit timeout) -> L0 & marks lost nodes as needsRepair on map
    res_fail = client.post(
        f"/student/math-sprints/attempts/{started['attemptId']}/submit",
        headers=sh,
        json={"answers": [], "auto_submitted": True},
    ).json()
    assert res_fail["tier"]["code"] == "L0" and res_fail["autoSubmitted"] is True
    assert len(res_fail["topLosses"]) >= 1
    m_after_fail = client.get("/student/math-star-map", headers=sh).json()
    assert m_after_fail["summary"]["repairNodes"] >= 1

    # Second attempt: answer all right -> L4 & boosts map nodes
    started2 = client.post("/student/math-sprints/geometry-area/start", headers=sh).json()
    with legacy.SessionLocal() as db:
        srow = db.execute(
            legacy.Base.metadata.tables["math_sprint_attempts"].select().where(
                legacy.Base.metadata.tables["math_sprint_attempts"].c.id == started2["attemptId"]
            )
        ).first()
        sprint_qs = json.loads(srow.items_json)
    sprint_ans = [
        {"question_id": q["id"], "selected_index": q["correctIndex"]}
        if q["questionType"] in ("single_choice", "true_false")
        else {"question_id": q["id"], "text_answer": q["answer"]}
        for q in sprint_qs
    ]
    res_win = client.post(
        f"/student/math-sprints/attempts/{started2['attemptId']}/submit",
        headers=sh,
        json={"answers": sprint_ans, "auto_submitted": False},
    ).json()
    assert res_win["tier"]["code"] == "L4" and res_win["scoreRate"] == 100
    assert res_win["pointsAwarded"]["total"] > 0
    # Daily cap (30 points) is strictly enforced across map + sprints
    assert res_win["points"]["todayEarned"] <= 30 and res_win["points"]["balance"] <= 30
    assert len(res_win["mapChanges"]["litNodes"]) >= 3
    m_after_win = client.get("/student/math-star-map", headers=sh).json()
    assert m_after_win["summary"]["litNodes"] >= 4
    # PointService balance reflects PointLedger entries
    with legacy.SessionLocal() as db:
        ledger_sum = sum(r.points for r in db.query(legacy.PointLedger).filter(legacy.PointLedger.student_id == sid).all())
        assert ledger_sum == res_win["points"]["balance"]

    # Teacher overview returns consistent student litNodes, tier, and pointsBalance; student gets 403
    assert client.get("/teacher/math-arena/overview", headers=sh).status_code == 403
    t_ov = client.get("/teacher/math-arena/overview", headers=th).json()
    assert t_ov["totalNodes"] == 24 and t_ov["totalSprints"] == 6
    stu_row = next(x for x in t_ov["items"] if x["studentId"] == sid)
    assert stu_row["litNodes"] == m_after_win["summary"]["litNodes"]
    assert stu_row["pointsBalance"] == res_win["points"]["balance"]
    assert stu_row["bestTier"]["code"] == "L4"
print("OK")
'''


def test_math_arena_end_to_end_flow(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {})
