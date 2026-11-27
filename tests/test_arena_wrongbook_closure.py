"""Tests for cross-subject Arena Wrongbook closure (auto-archive, auto-resolve on retry, manual master)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wb_closure_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.commit()

    # 1. 初始错题本为空
    wb0 = client.get("/student/arena-wrongbook", headers=sh)
    assert wb0.status_code == 200 and wb0.json()["total"] == 0

    # 2. 英语地图节点微测全部交空卷 -> 5 道错题自动收录进自主练习错题本
    q1 = client.post("/student/english-star-map/nodes/E1-1/quiz", headers=sh).json()
    sub1 = client.post(
        "/student/english-star-map/nodes/E1-1/quiz/submit",
        headers=sh,
        json={"quiz_id": q1["quizId"], "answers": []},
    )
    assert sub1.status_code == 200
    wb1 = client.get("/student/arena-wrongbook?subject=英语", headers=sh).json()
    assert wb1["total"] == 5 and wb1["counts"]["英语"] == 5
    first_item = wb1["items"][0]
    assert first_item["repairUrl"] == "/v1/english-star-map#node=E1-1"

    # 3. 手动标记 1 题已掌握 -> 待攻克变为 4
    m_res = client.post(f"/student/arena-wrongbook/{first_item['id']}/master", headers=sh)
    assert m_res.status_code == 200 and m_res.json()["status"] == "mastered"
    wb2 = client.get("/student/arena-wrongbook", headers=sh).json()
    assert wb2["total"] == 4

    # 4. 再次作答同一节点并全部答对 -> 对应错题自动消错
    q2 = client.post("/student/english-star-map/nodes/E1-1/quiz", headers=sh).json()
    with legacy.SessionLocal() as db:
        import json
        from sqlalchemy import select
        t_q = legacy.Base.metadata.tables["english_node_quizzes"]
        real_qs = json.loads(db.execute(select(t_q).where(t_q.c.id == q2["quizId"])).first().items_json)
    ans_ok = [
        {"question_id": rq["id"], "selected_index": rq["correctIndex"]}
        if rq["questionType"] in ("listen_choice", "listen_tf", "phonics_choice", "reading_choice")
        else {"question_id": rq["id"], "text_answer": rq.get("speakTarget") or rq["answer"]}
        for rq in real_qs
    ]
    sub2 = client.post(
        "/student/english-star-map/nodes/E1-1/quiz/submit",
        headers=sh,
        json={"quiz_id": q2["quizId"], "answers": ans_ok},
    )
    assert sub2.status_code == 200
    wb3 = client.get("/student/arena-wrongbook", headers=sh).json()
    assert wb3["total"] < wb2["total"]
print("OK")
'''


def test_arena_wrongbook_end_to_end_closure(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {})
