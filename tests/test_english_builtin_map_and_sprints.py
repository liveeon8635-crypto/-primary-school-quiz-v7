"""Tests for English Star Map (knowledge domains), Listening/Speaking/Reading/Writing Sprints,
static MP3 audio serving, mixed timing, independent daily 30-pt PointLedger cap, and role views."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from changying.services import english_builtin_map as ebm
from changying.services import english_exam_sprints as ees
from changying.web.english_arena_pages import ENGLISH_MAP_JS, ENGLISH_SPRINTS_JS
from changying.web.english_arena_views import AUDIO_DIR

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("english_arena_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_builtin_english_map_nodes_and_all_10_question_types():
    bp = ebm.get_map_blueprint()
    assert bp["subject"] == "英语"
    assert len(bp["domains"]) == 4
    assert len(bp["nodes"]) == 16

    seen_types: set[str] = set()
    for node in bp["nodes"]:
        qs = ebm.generate_node_questions(node["key"], count=6, seed=2)
        assert len(qs) >= 5, f"node {node['key']} should have >= 5 questions"
        for q in qs:
            seen_types.add(q["questionType"])
            pub = ebm.public_question(q)
            assert "answer" not in pub and "correctIndex" not in pub
            qt = q["questionType"]
            if qt in ("listen_choice", "listen_tf", "phonics_choice", "reading_choice"):
                assert ebm.grade_answer(q, selected_index=q["correctIndex"]) is True
                wrong_idx = (int(q["correctIndex"]) + 1) % len(q["options"])
                assert ebm.grade_answer(q, selected_index=wrong_idx) is False
            elif qt == "speak_read":
                assert ebm.grade_answer(q, text_answer=q["speakTarget"]) is True
                assert ebm.grade_answer(q, text_answer="completely unrelated words") is False
                # 老设备降级辨音模式判分
                fb_ok = f"__fallback__:{q['fallbackCorrectIndex']}"
                fb_bad = f"__fallback__:{(int(q['fallbackCorrectIndex']) + 1) % len(q['fallbackOptions'])}"
                assert ebm.grade_answer(q, text_answer=fb_ok) is True
                assert ebm.grade_answer(q, text_answer=fb_bad) is False
            else:
                assert ebm.grade_answer(q, text_answer=q["answer"]) is True
                assert ebm.grade_answer(q, text_answer="") is False

    # 验证 10 类英语核心题型全覆盖
    assert seen_types == {
        "listen_choice", "listen_tf", "phonics_choice", "speak_read",
        "word_tiles", "word_spell", "sentence_bank", "sentence_fill",
        "sentence_order", "reading_choice",
    }


def test_static_english_audio_manifest_and_mp3_files_exist():
    specs = ebm.collect_audio_specs()
    assert len(specs) >= 40
    manifest_path = AUDIO_DIR / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for s in specs:
        aid = s["audioId"]
        assert aid in manifest, f"missing {aid} in manifest.json"
        mp3 = AUDIO_DIR / f"{aid}.mp3"
        assert mp3.is_file() and mp3.stat().st_size > 256, f"missing or empty MP3: {mp3}"


def test_english_sprints_abilities_and_mixed_timing():
    sprints = ees.list_sprints("英语")
    assert [s["ability"] for s in sprints] == ["listening", "speaking", "reading", "writing"]
    by_ab = {s["ability"]: s for s in sprints}
    assert by_ab["listening"]["timingMode"] == "per_question" and by_ab["listening"]["perQuestionSec"] == 20
    assert by_ab["speaking"]["timingMode"] == "per_question" and by_ab["speaking"]["perQuestionSec"] == 20
    assert by_ab["reading"]["timingMode"] == "overall"
    assert by_ab["writing"]["timingMode"] == "overall"

    for sp in sprints:
        qs = ees.compose_sprint_questions(sp["slug"], seed=4)
        assert len(qs) == sp["questionCount"], f"{sp['slug']} should compose {sp['questionCount']} questions"
        all_right = {}
        for q in qs:
            qt = q["questionType"]
            if qt in ("listen_choice", "listen_tf", "phonics_choice", "reading_choice"):
                all_right[q["id"]] = {"selected_index": q["correctIndex"]}
            elif qt == "speak_read":
                all_right[q["id"]] = {"text_answer": q["speakTarget"]}
            else:
                all_right[q["id"]] = {"text_answer": q["answer"]}
        res = ees.evaluate_sprint_attempt(
            questions=qs,
            answers_by_id=all_right,
            elapsed_sec=int(sp["timeLimitSec"] * 0.5),
            time_limit_sec=sp["timeLimitSec"],
        )
        assert res["tier"]["code"] == "L4" and res["scoreRate"] == 100 and res["topLosses"] == []


def test_english_arena_pages_have_no_unsafe_dom_calls():
    for src in (ENGLISH_MAP_JS, ENGLISH_SPRINTS_JS):
        assert "innerHTML" not in src and "insertAdjacentHTML" not in src and "eval(" not in src


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.commit()

    # 1. 页面与静态音频路由正常
    r_map_html = client.get("/v1/english-star-map")
    r_sp_html = client.get("/v1/english-sprints")
    assert r_map_html.status_code == 200 and "英语知识地图" in r_map_html.text
    assert r_sp_html.status_code == 200 and "英语应试专项" in r_sp_html.text

    from changying.services import english_builtin_map as ebm
    first_audio_id = ebm.collect_audio_specs()[0]["audioId"]
    r_mp3 = client.get(f"/assets/english-audio/{first_audio_id}.mp3")
    assert r_mp3.status_code == 200 and r_mp3.headers["content-type"].startswith("audio/mpeg")
    assert client.get("/assets/english-audio/..bad..path.mp3").status_code == 404

    # 2. 学生英语地图微测点亮 -> 写入 PointLedger (+3 首亮 +5 精通 = +8) 且重复提交幂等 (+0)
    m0 = client.get("/student/english-star-map", headers=sh)
    assert m0.status_code == 200
    assert m0.json()["summary"]["totalNodes"] == 16

    q_start = client.post("/student/english-star-map/nodes/E1-1/quiz", headers=sh)
    assert q_start.status_code == 200
    qd = q_start.json()
    assert len(qd["questions"]) == 5

    # 读取真实题目构造全对答案
    with legacy.SessionLocal() as db:
        import json
        from sqlalchemy import select
        t_quizzes = legacy.Base.metadata.tables["english_node_quizzes"]
        row = db.execute(select(t_quizzes).where(t_quizzes.c.id == qd["quizId"])).first()
        real_qs = json.loads(row.items_json)

    ans_list = []
    for rq in real_qs:
        qt = rq["questionType"]
        if qt in ("listen_choice", "listen_tf", "phonics_choice", "reading_choice"):
            ans_list.append({"question_id": rq["id"], "selected_index": rq["correctIndex"]})
        elif qt == "speak_read":
            ans_list.append({"question_id": rq["id"], "text_answer": rq["speakTarget"]})
        else:
            ans_list.append({"question_id": rq["id"], "text_answer": rq["answer"]})

    q_sub = client.post(
        "/student/english-star-map/nodes/E1-1/quiz/submit",
        headers=sh,
        json={"quiz_id": qd["quizId"], "answers": ans_list},
    )
    assert q_sub.status_code == 200
    sub_d = q_sub.json()
    assert sub_d["passed"] is True
    assert sub_d["pointsAwarded"]["total"] in (3, 8)
    first_bal = sub_d["points"]["balance"]
    assert first_bal == sub_d["pointsAwarded"]["total"]

    # 再次刷同一节点 -> 幂等不重复加分
    q_start2 = client.post("/student/english-star-map/nodes/E1-1/quiz", headers=sh).json()
    with legacy.SessionLocal() as db:
        t_quizzes = legacy.Base.metadata.tables["english_node_quizzes"]
        row2 = db.execute(select(t_quizzes).where(t_quizzes.c.id == q_start2["quizId"])).first()
        real_qs2 = json.loads(row2.items_json)
    ans2 = [
        {"question_id": rq["id"], "selected_index": rq["correctIndex"]}
        if rq["questionType"] in ("listen_choice", "listen_tf", "phonics_choice", "reading_choice")
        else {"question_id": rq["id"], "text_answer": rq.get("speakTarget") or rq["answer"]}
        for rq in real_qs2
    ]
    q_sub2 = client.post(
        "/student/english-star-map/nodes/E1-1/quiz/submit",
        headers=sh,
        json={"quiz_id": q_start2["quizId"], "answers": ans2},
    ).json()
    assert q_sub2["pointsAwarded"]["total"] == 0
    assert q_sub2["points"]["balance"] == first_bal

    # 3. 听力专项（单题限时）全对达 L4 -> 反哺点亮地图 + 每日上限严格截断在 30 分
    sp_list = client.get("/student/english-sprints", headers=sh)
    assert sp_list.status_code == 200
    assert len(sp_list.json()["sprints"]) == 4

    sp_start = client.post("/student/english-sprints/listening-sprint/start", headers=sh)
    assert sp_start.status_code == 200
    att = sp_start.json()
    assert att["timingMode"] == "per_question" and att["perQuestionSec"] == 20 and att["maxPlays"] == 2

    with legacy.SessionLocal() as db:
        t_sprints = legacy.Base.metadata.tables["english_sprint_attempts"]
        srow = db.execute(select(t_sprints).where(t_sprints.c.id == att["attemptId"])).first()
        s_qs = json.loads(srow.items_json)

    sp_ans = [
        {"question_id": rq["id"], "selected_index": rq["correctIndex"]}
        if rq["questionType"] in ("listen_choice", "listen_tf", "phonics_choice", "reading_choice")
        else {"question_id": rq["id"], "text_answer": rq.get("speakTarget") or rq["answer"]}
        for rq in s_qs
    ]
    sp_sub = client.post(
        f"/student/english-sprints/attempts/{att['attemptId']}/submit",
        headers=sh,
        json={"answers": sp_ans, "auto_submitted": False},
    )
    assert sp_sub.status_code == 200
    sr = sp_sub.json()
    assert sr["tier"]["code"] == "L4"
    assert sr["points"]["todayEarned"] <= 30
    assert sr["points"]["todayEarned"] == 30  # 专项 L2+L3+L4(25) + 地图节点反哺 -> 严格截断在 30

    # 4. 教师学情概览接口正常返回英语进度
    t_ov = client.get("/teacher/english-arena/overview", headers=th)
    assert t_ov.status_code == 200
    td = t_ov.json()
    assert td["subject"] == "英语" and td["totalNodes"] == 16 and td["totalSprints"] == 4
    assert any(it["studentId"] == sid and it["litNodes"] >= 1 for it in td["items"])
print("OK")
'''


def test_english_arena_end_to_end_flow(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {})
