"""Tests for Chinese Star Map (4 domains, 16 nodes), 4 Exam Sprints (mixed timing),
static Mandarin MP3 audio, AI + rule-fallback subjective grading, independent daily 30-pt cap, and role views."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from changying.services import chinese_ai_grader as caig
from changying.services import chinese_builtin_map as cbm
from changying.services import chinese_exam_sprints as ces
from changying.web.chinese_arena_pages import CHINESE_MAP_JS, CHINESE_SPRINTS_JS
from changying.web.chinese_arena_views import AUDIO_DIR

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("chinese_arena_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_builtin_chinese_map_nodes_and_all_10_question_types():
    bp = cbm.get_map_blueprint()
    assert bp["subject"] == "语文"
    assert len(bp["domains"]) == 4
    assert len(bp["nodes"]) == 16

    seen_types: set[str] = set()
    for node in bp["nodes"]:
        qs = cbm.generate_node_questions(node["key"], count=6, seed=2)
        assert len(qs) >= 5
        for q in qs:
            qt = q["questionType"]
            seen_types.add(qt)
            pub = cbm.public_question(q)
            assert "answer" not in pub and "correctIndex" not in pub
            if qt in ("basic_choice", "error_spot", "sentence_choice", "reading_choice"):
                assert cbm.grade_objective_answer(q, selected_index=q["correctIndex"]) is True
                wrong_idx = (int(q["correctIndex"]) + 1) % len(q["options"])
                assert cbm.grade_objective_answer(q, selected_index=wrong_idx) is False
            elif qt in cbm.SUBJECTIVE_TYPES:
                sample = q.get("sampleAnswer") or q["answer"]
                res_ok = cbm.grade_subjective_rule_fallback(q, sample)
                assert res_ok["passed"] is True and res_ok["earnedMarks"] >= 1
                res_empty = cbm.grade_subjective_rule_fallback(q, "好")
                assert res_empty["passed"] is False and res_empty["earnedMarks"] == 0
            else:
                assert cbm.grade_objective_answer(q, text_answer=q["answer"]) is True
                assert cbm.grade_objective_answer(q, text_answer="") is False

    assert seen_types == {
        "basic_choice", "hanzi_tiles", "dictation_spell", "poem_tiles", "poem_fill",
        "error_spot", "sentence_choice", "reading_choice", "reading_short", "micro_writing",
    }


def test_static_chinese_audio_manifest_and_mp3_files_exist():
    specs = cbm.collect_audio_specs()
    assert len(specs) >= 20
    manifest_path = AUDIO_DIR / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for s in specs:
        aid = s["audioId"]
        assert aid in manifest, f"missing {aid} in manifest.json"
        mp3 = AUDIO_DIR / f"{aid}.mp3"
        assert mp3.is_file() and mp3.stat().st_size > 256, f"missing or empty MP3: {mp3}"


def test_chinese_ai_grader_uses_ai_when_available_and_falls_back_gracefully():
    q = next(q for q in cbm.QUESTION_BANK["C4-3"] if q["questionType"] == "micro_writing")
    sample = q["sampleAnswer"]

    # 1. Mock AI 实时批改成功路径
    def fake_ai(payload):
        return {payload[0]["id"]: {"earnedMarks": 6, "comment": "动作和心跳细节非常逼真，画面感十足！"}}

    ai_res = caig.grade_subjective_items([(q, sample)], ai_caller=fake_ai)
    assert ai_res[q["id"]]["gradingMode"] == "ai"
    assert ai_res[q["id"]]["earnedMarks"] == 6
    assert ai_res[q["id"]]["passed"] is True

    # 2. Mock AI 异常时自动无缝降级到本地规则兜底
    def broken_ai(_payload):
        raise RuntimeError("network timeout")

    fb_res = caig.grade_subjective_items([(q, sample)], ai_caller=broken_ai)
    assert fb_res[q["id"]]["gradingMode"] == "rule_fallback"
    assert fb_res[q["id"]]["passed"] is True and fb_res[q["id"]]["earnedMarks"] >= 4


def test_chinese_sprints_sections_and_mixed_timing():
    sprints = ces.list_sprints("语文")
    assert [s["section"] for s in sprints] == ["foundation", "poetry", "reading", "writing"]
    by_sec = {s["section"]: s for s in sprints}
    assert by_sec["foundation"]["timingMode"] == "per_question" and by_sec["foundation"]["perQuestionSec"] == 20
    assert by_sec["poetry"]["timingMode"] == "overall"
    assert by_sec["reading"]["timingMode"] == "overall"
    assert by_sec["writing"]["timingMode"] == "overall"

    for sp in sprints:
        qs = ces.compose_sprint_questions(sp["slug"], seed=3)
        assert len(qs) == sp["questionCount"]
        all_right = {}
        for q in qs:
            qt = q["questionType"]
            if qt in ("basic_choice", "error_spot", "sentence_choice", "reading_choice"):
                all_right[q["id"]] = {"selected_index": q["correctIndex"]}
            elif qt in cbm.SUBJECTIVE_TYPES:
                all_right[q["id"]] = {"text_answer": q.get("sampleAnswer") or q["answer"]}
            else:
                all_right[q["id"]] = {"text_answer": q["answer"]}
        res = ces.evaluate_sprint_attempt(
            questions=qs,
            answers_by_id=all_right,
            elapsed_sec=int(sp["timeLimitSec"] * 0.5),
            time_limit_sec=sp["timeLimitSec"],
            ai_caller=lambda payload: {p["id"]: {"earnedMarks": p["maxMarks"], "comment": "非常棒"} for p in payload},
        )
        assert res["tier"]["code"] == "L4" and res["scoreRate"] == 100 and res["topLosses"] == []


def test_chinese_arena_pages_have_no_unsafe_dom_calls():
    for src in (CHINESE_MAP_JS, CHINESE_SPRINTS_JS):
        assert "innerHTML" not in src and "insertAdjacentHTML" not in src and "eval(" not in src


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.commit()

    # 1. 页面与静态普通话音频路由正常
    r_map = client.get("/v1/chinese-star-map")
    r_sp = client.get("/v1/chinese-sprints")
    assert r_map.status_code == 200 and "语文知识地图" in r_map.text
    assert r_sp.status_code == 200 and "语文应试专项" in r_sp.text

    from changying.services import chinese_builtin_map as cbm
    first_audio = cbm.collect_audio_specs()[0]["audioId"]
    r_mp3 = client.get(f"/assets/chinese-audio/{first_audio}.mp3")
    assert r_mp3.status_code == 200 and r_mp3.headers["content-type"].startswith("audio/mpeg")
    assert client.get("/assets/chinese-audio/..invalid.mp3").status_code == 404

    # 2. 学生语文知识地图点亮 + 幂等防刷分
    m0 = client.get("/student/chinese-star-map", headers=sh)
    assert m0.status_code == 200 and m0.json()["summary"]["totalNodes"] == 16

    q_start = client.post("/student/chinese-star-map/nodes/C1-1/quiz", headers=sh)
    assert q_start.status_code == 200
    qd = q_start.json()
    assert len(qd["questions"]) == 5

    with legacy.SessionLocal() as db:
        import json
        from sqlalchemy import select
        t_q = legacy.Base.metadata.tables["chinese_node_quizzes"]
        real_qs = json.loads(db.execute(select(t_q).where(t_q.c.id == qd["quizId"])).first().items_json)

    ans_list = [
        {"question_id": rq["id"], "selected_index": rq["correctIndex"]}
        if rq["questionType"] in ("basic_choice", "error_spot", "sentence_choice", "reading_choice")
        else {"question_id": rq["id"], "text_answer": rq.get("sampleAnswer") or rq["answer"]}
        for rq in real_qs
    ]
    q_sub = client.post(
        "/student/chinese-star-map/nodes/C1-1/quiz/submit",
        headers=sh,
        json={"quiz_id": qd["quizId"], "answers": ans_list},
    )
    assert q_sub.status_code == 200
    sub_d = q_sub.json()
    assert sub_d["passed"] is True
    assert sub_d["pointsAwarded"]["total"] in (3, 8)

    # 3. 语文基础专项（单题限时 20s）全对达 L4 + 语文独立 30 分日上限校验
    sp_start = client.post("/student/chinese-sprints/chinese-foundation-sprint/start", headers=sh)
    assert sp_start.status_code == 200
    att = sp_start.json()
    assert att["timingMode"] == "per_question" and att["perQuestionSec"] == 20

    with legacy.SessionLocal() as db:
        t_s = legacy.Base.metadata.tables["chinese_sprint_attempts"]
        s_qs = json.loads(db.execute(select(t_s).where(t_s.c.id == att["attemptId"])).first().items_json)

    sp_ans = [
        {"question_id": rq["id"], "selected_index": rq["correctIndex"]}
        if rq["questionType"] in ("basic_choice", "error_spot", "sentence_choice", "reading_choice")
        else {"question_id": rq["id"], "text_answer": rq.get("sampleAnswer") or rq["answer"]}
        for rq in s_qs
    ]
    sp_sub = client.post(
        f"/student/chinese-sprints/attempts/{att['attemptId']}/submit",
        headers=sh,
        json={"answers": sp_ans, "auto_submitted": False},
    )
    assert sp_sub.status_code == 200
    sr = sp_sub.json()
    assert sr["tier"]["code"] == "L4"
    assert sr["points"]["todayEarned"] == 30

    # 4. 现代文阅读专项（含主观简答规则兜底点评）正常交卷
    rd_start = client.post("/student/chinese-sprints/chinese-reading-sprint/start", headers=sh).json()
    assert rd_start["timingMode"] == "overall"
    with legacy.SessionLocal() as db:
        t_s = legacy.Base.metadata.tables["chinese_sprint_attempts"]
        r_qs = json.loads(db.execute(select(t_s).where(t_s.c.id == rd_start["attemptId"])).first().items_json)
    rd_ans = [
        {"question_id": rq["id"], "selected_index": rq["correctIndex"]}
        if rq["questionType"] in ("basic_choice", "error_spot", "sentence_choice", "reading_choice")
        else {"question_id": rq["id"], "text_answer": rq.get("sampleAnswer") or rq["answer"]}
        for rq in r_qs
    ]
    rd_sub = client.post(
        f"/student/chinese-sprints/attempts/{rd_start['attemptId']}/submit",
        headers=sh,
        json={"answers": rd_ans, "auto_submitted": False},
    )
    assert rd_sub.status_code == 200
    rd_res = rd_sub.json()
    assert any(d["aiComment"] for d in rd_res["details"])

    # 5. 教师语文学情概览接口正常
    t_ov = client.get("/teacher/chinese-arena/overview", headers=th)
    assert t_ov.status_code == 200
    td = t_ov.json()
    assert td["subject"] == "语文" and td["totalNodes"] == 16 and td["totalSprints"] == 4
    assert any(it["studentId"] == sid and it["litNodes"] >= 1 for it in td["items"])
print("OK")
'''


def test_chinese_arena_end_to_end_flow(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {})
