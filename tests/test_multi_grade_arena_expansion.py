"""End-to-end tests for Grade 3, 4, 5, 6 expansion across Math, English, and Chinese Star Maps & Exam Sprints,
including Age-Tier UX profiles (G3 guided, G4 bridge, G5-G6 mastery), grade isolation, shared subject daily point caps,
and teacher/parent multi-grade workflows."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from changying.services import arena_grade_profiles as agp
from changying.services import chinese_builtin_map as cbm
from changying.services import chinese_exam_sprints as ces
from changying.services import english_builtin_map as ebm
from changying.services import english_exam_sprints as ees
from changying.services import exam_sprints as mes
from changying.services import math_builtin_map as mbm

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("multi_grade_arena_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_age_interaction_profiles_and_grade_relations():
    p3 = agp.get_age_interaction_profile(3)
    p4 = agp.get_age_interaction_profile(4)
    p5 = agp.get_age_interaction_profile(5)
    p6 = agp.get_age_interaction_profile(6)

    assert p3["tier"] == "g3_guided" and p3["stemReadAloud"] is True and p3["mathKeypad"] == "full"
    assert p3["spellAssist"] == "tile_or_first_letter" and p3["chineseAssistTiles"] is True
    assert p3["perQuestionSec"] == 25 and p3["maxPlays"] == 3 and p3["writingMinChars"] == 35

    assert p4["tier"] == "g4_bridge" and p4["stemReadAloud"] is True and p4["mathKeypad"] == "compact"
    assert p4["spellAssist"] == "first_letter_hint" and p4["perQuestionSec"] == 22 and p4["writingMinChars"] == 50

    assert p5["tier"] == "g56_mastery" and p5["mathKeypad"] == "none" and p5["spellAssist"] == "strict_keyboard"
    assert p6["tier"] == "g56_mastery" and p6["writingMinChars"] == 85

    avail = agp.build_available_grades(active_grade=3, student_grade=5)
    by_g = {x["grade"]: x for x in avail}
    assert by_g[3]["relation"] == "review" and by_g[3]["relationLabel"] == "查漏补缺" and by_g[3]["active"] is True
    assert by_g[4]["relation"] == "review"
    assert by_g[5]["relation"] == "current" and by_g[5]["relationLabel"] == "本年级" and by_g[5]["isCurrentGrade"] is True
    assert by_g[6]["relation"] == "advance" and by_g[6]["relationLabel"] == "超前探索"


def test_all_math_grades_3_4_5_6_maps_and_sprints():
    expected_counts = {3: 16, 4: 16, 5: 24, 6: 16}
    for g, node_cnt in expected_counts.items():
        m = mbm.get_builtin_math_map(g)
        assert m["grade"] == g and len(m["units"]) == 4 and len(m["nodes"]) == node_cnt
        for node in m["nodes"]:
            qs = mbm.generate_node_questions(node["key"], count=5, seed=2)
            assert len(qs) == 5, f"Math G{g} node {node['key']} failed to generate 5 questions"
            for q in qs:
                pub = mbm.public_question(q)
                assert pub["grade"] == g and "answer" not in pub
                if q["questionType"] in ("single_choice", "true_false"):
                    assert mbm.grade_builtin_question(q, selected_index=q["correctIndex"]) is True
                else:
                    assert mbm.grade_builtin_question(q, text_answer=q["answer"]) is True

        sprints = mes.list_sprints("数学", grade=g)
        assert len(sprints) >= 4, f"Math G{g} should have >= 4 sprints"
        for sp in sprints:
            assert sp["grade"] == g
            sqs = mes.compose_sprint_questions(sp["slug"], seed=1)
            assert len(sqs) == sp["questionCount"]


def test_all_english_grades_3_4_5_6_maps_and_sprints_with_age_assists():
    for g in (3, 4, 5, 6):
        bp = ebm.get_map_blueprint(g)
        assert bp["grade"] == g and len(bp["domains"]) == 4 and len(bp["nodes"]) == 16
        seen_types: set[str] = set()
        for node in bp["nodes"]:
            qs = ebm.generate_node_questions(node["key"], count=6, seed=1)
            assert len(qs) >= 5, f"English G{g} node {node['key']} should have >= 5 questions"
            for q in qs:
                qt = q["questionType"]
                seen_types.add(qt)
                pub = ebm.public_question(q)
                assert pub["grade"] == g and "answer" not in pub
                if qt in ("word_spell", "sentence_fill"):
                    assert pub.get("firstLetterHint"), f"English G{g} {q['id']} missing firstLetterHint"
                    assert pub.get("assistChunks"), f"English G{g} {q['id']} missing assistChunks"
                if qt in ("listen_choice", "listen_tf", "phonics_choice", "reading_choice"):
                    assert ebm.grade_answer(q, selected_index=q["correctIndex"]) is True
                elif qt == "speak_read":
                    assert ebm.grade_answer(q, text_answer=q["speakTarget"]) is True
                else:
                    assert ebm.grade_answer(q, text_answer=q["answer"]) is True
        assert len(seen_types) == 10, f"English G{g} should cover all 10 question types"

        sprints = ees.list_sprints("英语", grade=g)
        assert len(sprints) == 4
        by_ab = {s["ability"]: s for s in sprints}
        expected_sec = {3: 25, 4: 22, 5: 20, 6: 20}[g]
        assert by_ab["listening"]["perQuestionSec"] == expected_sec
        for sp in sprints:
            sqs = ees.compose_sprint_questions(sp["slug"], seed=2)
            assert len(sqs) == sp["questionCount"]


def test_all_chinese_grades_3_4_5_6_maps_and_sprints_with_age_assists():
    for g in (3, 4, 5, 6):
        bp = cbm.get_map_blueprint(g)
        assert bp["grade"] == g and len(bp["domains"]) == 4 and len(bp["nodes"]) == 16
        seen_types: set[str] = set()
        for node in bp["nodes"]:
            qs = cbm.generate_node_questions(node["key"], count=6, seed=1)
            assert len(qs) >= 5
            for q in qs:
                qt = q["questionType"]
                seen_types.add(qt)
                pub = cbm.public_question(q)
                assert pub["grade"] == g and "answer" not in pub
                if qt in ("dictation_spell", "poem_fill") and g in (3, 4):
                    assert pub.get("assistTiles"), f"Chinese G{g} {q['id']} missing assistTiles"
                if qt in cbm.SUBJECTIVE_TYPES and g in (3, 4):
                    assert pub.get("scaffolds"), f"Chinese G{g} {q['id']} missing scaffolds"
                if qt in ("basic_choice", "error_spot", "sentence_choice", "reading_choice"):
                    assert cbm.grade_objective_answer(q, selected_index=q["correctIndex"]) is True
                elif qt in cbm.SUBJECTIVE_TYPES:
                    sample = q.get("sampleAnswer") or q["answer"]
                    assert cbm.grade_subjective_rule_fallback(q, sample)["passed"] is True
                else:
                    assert cbm.grade_objective_answer(q, text_answer=q["answer"]) is True
        assert len(seen_types) == 10, f"Chinese G{g} should cover all 10 question types"

        sprints = ces.list_sprints("语文", grade=g)
        assert len(sprints) == 4
        by_sec = {s["section"]: s for s in sprints}
        expected_sec = {3: 25, 4: 22, 5: 20, 6: 20}[g]
        assert by_sec["foundation"]["perQuestionSec"] == expected_sec
        for sp in sprints:
            sqs = ces.compose_sprint_questions(sp["slug"], seed=2)
            assert len(sqs) == sp["questionCount"]


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.commit()

    # 1. Default grade is student's own grade (5), switching grade=3 returns G3 map & ageProfile
    m5 = client.get("/student/math-star-map", headers=sh).json()
    assert m5["grade"] == 5 and m5["studentGrade"] == 5 and m5["summary"]["totalNodes"] == 24
    assert m5["ageProfile"]["tier"] == "g56_mastery"

    m3 = client.get("/student/math-star-map?grade=3", headers=sh).json()
    assert m3["grade"] == 3 and m3["studentGrade"] == 5 and m3["summary"]["totalNodes"] == 16
    assert m3["ageProfile"]["tier"] == "g3_guided" and m3["ageProfile"]["mathKeypad"] == "full"

    # 2. Lighting a G3 node keeps G3 and G5 progress isolated while sharing Math PointLedger
    q3 = client.post("/student/math-star-map/nodes/G3-M1-1/quiz", headers=sh).json()
    assert q3["grade"] == 3 and q3["ageProfile"]["tier"] == "g3_guided"
    with legacy.SessionLocal() as db:
        qrow = db.execute(legacy.Base.metadata.tables["math_node_quizzes"].select().where(
            legacy.Base.metadata.tables["math_node_quizzes"].c.id == q3["quizId"]
        )).first()
        full_qs = json.loads(qrow.items_json)
    answers = [
        {"question_id": q["id"], "selected_index": q["correctIndex"]}
        if q["questionType"] in ("single_choice", "true_false")
        else {"question_id": q["id"], "text_answer": q["answer"]}
        for q in full_qs
    ]
    sub3 = client.post("/student/math-star-map/nodes/G3-M1-1/quiz/submit", headers=sh, json={"quiz_id": q3["quizId"], "answers": answers}).json()
    assert sub3["litUp"] is True and sub3["map"]["grade"] == 3 and sub3["map"]["summary"]["litNodes"] == 1
    assert sub3["pointsAwarded"]["total"] == 8

    # G5 map still has 0 lit nodes, while points balance reflects the +8 from G3
    m5_after = client.get("/student/math-star-map?grade=5", headers=sh).json()
    assert m5_after["summary"]["litNodes"] == 0
    assert m5_after["points"]["todayEarned"] == 8

    # 3. English G4 and Chinese G6 sprints & maps work seamlessly
    e4_sp = client.get("/student/english-sprints?grade=4", headers=sh).json()
    assert e4_sp["grade"] == 4 and len(e4_sp["sprints"]) == 4
    assert e4_sp["sprints"][0]["slug"].startswith("g4-")

    c6_map = client.get("/student/chinese-star-map?grade=6", headers=sh).json()
    assert c6_map["grade"] == 6 and len(c6_map["nodes"]) == 16
    assert c6_map["nodes"][0]["key"].startswith("G6-C")

    # 4. Teacher diagnostics & task dispatch across grades (e.g. G3 review task)
    td3 = client.get("/teacher/arena/diagnostics?subject=英语&grade=3", headers=th).json()
    assert td3["grade"] == 3 and len(td3["nodeHeat"]) == 16
    assert td3["nodeHeat"][0]["key"].startswith("G3-E")

    prev = client.get("/teacher/arena/target-preview?subject=英语&task_kind=map_node&target_key=G3-E1-1", headers=th)
    assert prev.status_code == 200 and len(prev.json()["items"]) >= 5

    t_create = client.post("/teacher/arena/tasks", headers=th, json={
        "subject": "英语",
        "class_id": 0,
        "task_kind": "map_node",
        "target_key": "G3-E1-1",
        "goal_code": "lit",
        "audience": "all",
    })
    assert t_create.status_code == 200
    st_tasks = client.get("/student/arena-tasks", headers=sh).json()["items"]
    g3_task = next(t for t in st_tasks if t["targetKey"] == "G3-E1-1")
    assert "grade=3" in g3_task["actionUrl"]

    # 5. Single-connection pool (pool_size=1, max_overflow=0) must never deadlock on arena routes
    from sqlalchemy import create_engine
    limited_engine = create_engine(
        legacy.engine.url,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.2,
        connect_args={"check_same_thread": False},
    )
    legacy.SessionLocal.configure(bind=limited_engine)
    for path in (
        "/student/math-star-map?grade=3",
        "/student/math-sprints?grade=4",
        "/student/english-star-map?grade=6",
        "/student/english-sprints?grade=3",
        "/student/chinese-star-map?grade=4",
        "/student/chinese-sprints?grade=6",
        "/student/arena-tasks",
        "/student/arena-wrongbook",
    ):
        r = client.get(path, headers=sh)
        assert r.status_code == 200, (path, r.status_code, r.text)
print("OK")
'''


def test_ensure_tables_on_session_never_deadlocks_8_connection_pool(tmp_path: Path):
    import threading
    from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select
    from sqlalchemy.orm import sessionmaker
    from changying.services.arena_review_and_custom import ensure_tables_on_session

    db_file = tmp_path / "pool8.sqlite3"
    eng = create_engine(
        f"sqlite:///{db_file}",
        pool_size=3,
        max_overflow=5,
        pool_timeout=1.5,
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(bind=eng)
    md = MetaData()
    t1 = Table("t_pool_1", md, Column("id", Integer, primary_key=True))
    t2 = Table("t_pool_2", md, Column("id", Integer, primary_key=True))
    t1.create(bind=eng, checkfirst=True)

    barrier = threading.Barrier(8)
    errors: list[str] = []

    def worker() -> None:
        s = Session()
        try:
            s.execute(select(t1)).all()  # holds 1 of 8 pool connections
            barrier.wait(timeout=3.0)
            ensure_tables_on_session(s, t1, t2)
            s.execute(select(t2)).all()
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    eng.dispose()
    assert errors == []


def test_multi_grade_arena_end_to_end(tmp_path: Path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {})
