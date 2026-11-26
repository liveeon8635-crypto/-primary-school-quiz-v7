from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from changying.web.weekend_courseware_pages import COURSEWARE_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("stage4_hw_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

EVIDENCE_FLOW = """
from datetime import datetime, timedelta
from sqlalchemy import insert

with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    with legacy.SessionLocal() as db:
        legacy_u = db.get(legacy.User, student_id)
        legacy_u.grade = 5
        db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id)).grade = 5
        db.commit()

    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    base = f"/teacher/knowledge-maps/{mid}/nodes"
    for key in ("6-1", "6-2", "6-3", "6-4"):
        got = client.post(base + f"/{key}/visual", headers=th, json={"level": "basic", "count": 4}).json()
        r = client.post(base + f"/{key}/visual/save", headers=th, json={"level": "basic", "revision": rev, "questions": got["items"]}).json()
        rev = r["revision"]
    client.post(f"/teacher/knowledge-maps/{mid}/publish", headers=th, json={"revision": rev})

    lst = client.get("/teacher/exam-goals", headers=th).json()
    cid = lst["classes"][0]["id"]
    goal = client.post("/teacher/exam-goals", headers=th, json={
        "mapId": mid, "classId": cid, "title": "期末证据联动",
        "examDate": (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d"),
        "unitKeys": ["U6"],
    }).json()
    mock = client.post(f"/teacher/exam-goals/{goal['id']}/mock", headers=th, json={"count": 8, "timeLimit": 60}).json()

    md = legacy.Base.metadata
    with legacy.SessionLocal() as db:
        a = db.get(legacy.Assignment, mock["assignmentId"])
        qids = json.loads(db.get(legacy.Paper, a.paper_id).question_ids_json)
        db.add(legacy.Submission(
            school_id=school_id, assignment_id=a.id, student_id=student_id,
            score=0, total=len(qids), correct=0,
            answers_json=json.dumps([{"question_id": q, "correct": False} for q in qids]),
            submitted_at=datetime.utcnow(),
        ))
        hw_know = md.tables["homework_ai_knowledge"]
        db.execute(insert(hw_know).values(
            school_id=school_id, student_id=student_id, help_id=999,
            grade=5, subject="数学", knowledge_key="6-1", raw_knowledge="平行四边形的面积",
            matched=1, question_excerpt="求平行四边形的面积", verify_status="verified",
            created_at=datetime.utcnow(),
        ))
        km_runs = md.tables["knowledge_map_runs"]
        db.execute(insert(km_runs).values(
            school_id=school_id, map_id=mid, student_id=student_id, map_revision=rev,
            items_json=json.dumps([["6-1", qids[0]]]), status="submitted",
            submission_id=None, correct=1, created_at=datetime.utcnow(),
        ))
        db.commit()

    analysis = client.get(f"/teacher/exam-goals/{goal['id']}/papers/{mock['id']}/analysis", headers=th).json()
    assert "evidenceDisclaimer" in analysis and "不改变" in analysis["evidenceDisclaimer"]
    pupil = analysis["pupils"][0]
    assert pupil["score"] == 0
    assert "6-1" in pupil["pointEvidence"]
    sources = {ev["source"]: ev for ev in pupil["pointEvidence"]["6-1"]}
    assert sources["晚托作业求助"]["helpStatus"] == "接受过AI讲解"
    assert sources["知识地图测验"]["helpStatus"] == "未知"
print("OK")
"""

FOLLOWUP_FLOW = """
from datetime import datetime
from sqlalchemy import insert, select

with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    md = legacy.Base.metadata
    helps = md.tables["help_requests"]
    peer = md.tables["weekend_peer_help"]

    with legacy.SessionLocal() as db:
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id))
        extra_students = []
        for idx in range(5):
            u = legacy.User(school_id=school_id, username=f"wk_stu_{idx}", name=f"学生{idx}", role="student", password_hash="x", active=True)
            db.add(u)
            db.flush()
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=u.id))
            extra_students.append(u.id)
        for idx, sid in enumerate(extra_students[:4]):
            db.execute(insert(helps).values(
                school_id=school_id, student_id=sid, grade=5,
                question_text=f"晚托题 {idx}", state="escalated", escalate_reason="student_request",
                escalated_at=datetime.utcnow(), created_at=datetime.utcnow(),
            ))
        peer_id = db.execute(insert(peer).values(
            school_id=school_id, session_id=1, tutor_id=student_id, tutee_id=extra_students[4],
            question_id=10, followup_json=json.dumps({"stem": "周末巩固题：求面积", "options": ["1", "2"], "correctIndex": 0}, ensure_ascii=False),
            followup_correct=None, created_at=datetime.utcnow(),
        )).inserted_primary_key[0]
        u6 = legacy.User(school_id=school_id, username="wk_stu_6", name="学生6", role="student", password_hash="x", active=True)
        db.add(u6)
        db.flush()
        db.add(legacy.ClassStudent(class_id=cls.id, student_id=u6.id))
        wrong_peer_id = db.execute(insert(peer).values(
            school_id=school_id, session_id=1, tutor_id=student_id, tutee_id=u6.id,
            question_id=11, followup_json=json.dumps({"stem": "第6条周末巩固题", "options": ["1", "2"], "correctIndex": 0}, ensure_ascii=False),
            followup_correct=False, created_at=datetime.utcnow(),
        )).inserted_primary_key[0]
        db.commit()

    claimed = client.post("/teacher/homework/follow-ups/claim", headers=th)
    assert claimed.status_code == 200, claimed.text
    items = claimed.json()["items"]
    assert len(items) == 5
    wk_items = [it for it in items if it.get("source") == "weekend"]
    assert len(wk_items) == 1
    assert wk_items[0]["peerHelpID"] == wrong_peer_id
    assert wk_items[0]["next"]["route"] == "/v1/weekend"

    dismissed = client.post(f"/teacher/homework/follow-ups/weekend/{wrong_peer_id}/dismiss", headers=th)
    assert dismissed.status_code == 200 and dismissed.json()["helpStateUnchanged"] is True

    after = client.get("/teacher/homework/follow-ups", headers=th).json()["items"]
    assert all(it.get("peerHelpID") != wrong_peer_id for it in after)
print("OK")
"""


def test_exam_prep_analysis_includes_cross_scene_evidence(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + EVIDENCE_FLOW, {"KNOWLEDGE_MAP": "1"})


def test_weekend_followups_share_5_per_day_budget(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FOLLOWUP_FLOW)


def test_math_courseware_models_support_stepwise_and_fallback():
    for fn in (
        "cwRotation",
        "cwClock",
        "cwParallelogramMethods",
        "cwEqualBaseHeight",
        "cwParallelogramThirds",
        "cwObtuseTriangleHeight",
    ):
        assert f"function {fn}(" in COURSEWARE_JS
    assert "cwEqualBaseHeight(box,f,view,big,teacher,stepCount)" in COURSEWARE_JS
    assert "cwParallelogramThirds(box,f,view,big,teacher,stepCount)" in COURSEWARE_JS
    assert "等底等高，三个平行四边形面积相等" in COURSEWARE_JS
    assert "等底等高的 3 份各占总面积的 1/3" in COURSEWARE_JS
