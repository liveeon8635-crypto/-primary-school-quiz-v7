"""End-to-end tests for Teacher-Student-Parent three-way Arena sync:
class diagnostics heatmap -> targeted weak-student task dispatch -> student completion auto-verification -> parent sync & cheer."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from changying.web.arena_role_hub import ARENA_ROLE_HUB_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("three_way_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_arena_role_hub_has_no_unsafe_dom_calls():
    assert "innerHTML" not in ARENA_ROLE_HUB_JS
    assert "insertAdjacentHTML" not in ARENA_ROLE_HUB_JS
    assert "eval(" not in ARENA_ROLE_HUB_JS


FLOW = r'''
with TestClient(app) as client:
    th, sh1, sid1, school_id = setup(client)
    with legacy.SessionLocal() as db:
        t_user = db.query(legacy.User).filter(legacy.User.school_id == school_id, legacy.User.role == "teacher").first()
        u1 = db.get(legacy.User, sid1)
        u1.grade = 5
        # 创建第 2 名学生与家长，并建立班级和亲子关联
        u2 = legacy.User(
            school_id=school_id, username="stu_weak_2", name="陈小弱", role="student",
            grade=5, password_hash=legacy.hash_password("123456"),
        )
        p1 = legacy.User(
            school_id=school_id, username="parent_chen", name="陈妈妈", role="parent",
            password_hash=legacy.hash_password("123456"),
        )
        db.add_all([u2, p1])
        db.flush()
        sid2, pid1 = int(u2.id), int(p1.id)
        cls = legacy.SchoolClass(school_id=school_id, name="五年级一班", grade=5, teacher_id=t_user.id)
        db.add(cls)
        db.flush()
        cid = int(cls.id)
        db.add_all([
            legacy.ClassStudent(class_id=cid, student_id=sid1),
            legacy.ClassStudent(class_id=cid, student_id=sid2),
            legacy.ParentStudent(parent_id=pid1, student_id=sid2),
        ])
        db.commit()

    sh2 = {"Authorization": "Bearer " + login_and_change(client, "stu_weak_2", "123456", "Student2345")}
    ph1 = {"Authorization": "Bearer " + login_and_change(client, "parent_chen", "123456", "Parent2345")}

    # 1. stu1 先点亮英语 E1-1；stu2 未点亮
    q1 = client.post("/student/english-star-map/nodes/E1-1/quiz", headers=sh1).json()
    with legacy.SessionLocal() as db:
        import json
        from sqlalchemy import select
        t_q = legacy.Base.metadata.tables["english_node_quizzes"]
        rqs1 = json.loads(db.execute(select(t_q).where(t_q.c.id == q1["quizId"])).first().items_json)
    ans1 = [
        {"question_id": rq["id"], "selected_index": rq["correctIndex"]}
        if rq["questionType"] in ("listen_choice", "listen_tf", "phonics_choice", "reading_choice")
        else {"question_id": rq["id"], "text_answer": rq.get("speakTarget") or rq["answer"]}
        for rq in rqs1
    ]
    assert client.post("/student/english-star-map/nodes/E1-1/quiz/submit", headers=sh1, json={"quiz_id": q1["quizId"], "answers": ans1}).status_code == 200

    # 2. 教师按班级查看英语热力诊断：E1-1 应为 litCount=1, weakCount=1
    diag = client.get(f"/teacher/arena/diagnostics?subject=英语&class_id={cid}", headers=th)
    assert diag.status_code == 200
    dd = diag.json()
    assert dd["studentCount"] == 2 and any(c["id"] == cid for c in dd["classes"])
    e11 = next(x for x in dd["nodeHeat"] if x["key"] == "E1-1")
    assert e11["litCount"] == 1 and e11["weakCount"] == 1

    # 3. 教师按 audience="weak" 一键定向派发 E1-1 点亮任务 -> 仅派给 stu2
    created = client.post(
        "/teacher/arena/tasks",
        headers=th,
        json={"subject": "英语", "class_id": cid, "task_kind": "map_node", "target_key": "E1-1", "goal_code": "lit", "audience": "weak"},
    )
    assert created.status_code == 200
    assert created.json()["assignedCount"] == 1

    # stu1 不被打扰；stu2 收到 1 条待完成置顶任务
    assert client.get("/student/arena-tasks", headers=sh1).json()["pendingCount"] == 0
    s2_tasks = client.get("/student/arena-tasks", headers=sh2).json()
    assert s2_tasks["pendingCount"] == 1
    assert s2_tasks["items"][0]["targetKey"] == "E1-1" and s2_tasks["items"][0]["status"] == "pending"

    # 4. stu2 完成 E1-1 微测并点亮 -> 系统自动验收为 done
    q2 = client.post("/student/english-star-map/nodes/E1-1/quiz", headers=sh2).json()
    with legacy.SessionLocal() as db:
        t_q = legacy.Base.metadata.tables["english_node_quizzes"]
        rqs2 = json.loads(db.execute(select(t_q).where(t_q.c.id == q2["quizId"])).first().items_json)
    ans2 = [
        {"question_id": rq["id"], "selected_index": rq["correctIndex"]}
        if rq["questionType"] in ("listen_choice", "listen_tf", "phonics_choice", "reading_choice")
        else {"question_id": rq["id"], "text_answer": rq.get("speakTarget") or rq["answer"]}
        for rq in rqs2
    ]
    assert client.post("/student/english-star-map/nodes/E1-1/quiz/submit", headers=sh2, json={"quiz_id": q2["quizId"], "answers": ans2}).status_code == 200

    s2_after = client.get("/student/arena-tasks", headers=sh2).json()
    assert s2_after["pendingCount"] == 0 and s2_after["items"][0]["status"] == "done"

    # 5. 教师端任务追踪实时显示 1/1 已达标
    t_tasks = client.get(f"/teacher/arena/tasks?subject=英语&class_id={cid}", headers=th).json()
    assert t_tasks["items"][0]["doneCount"] == 1 and t_tasks["items"][0]["totalCount"] == 1
    assert t_tasks["items"][0]["pendingNames"] == []

    # 6. 家长端同步看到任务已完成，并发送每日点赞鼓励（重复发送防刷）
    p_sum = client.get("/parent/arena-summary?subject=英语", headers=ph1)
    assert p_sum.status_code == 200
    child = p_sum.json()["items"][0]
    assert child["studentId"] == sid2 and child["tasks"][0]["status"] == "done" and child["cheeredToday"] is False

    c1 = client.post("/parent/arena-cheers", headers=ph1, json={"student_id": sid2, "subject": "英语", "message": "宝贝英语点亮真棒！"})
    assert c1.status_code == 200 and c1.json()["alreadyCheered"] is False
    c2 = client.post("/parent/arena-cheers", headers=ph1, json={"student_id": sid2, "subject": "英语", "message": "再赞一次"})
    assert c2.status_code == 200 and c2.json()["alreadyCheered"] is True

    # 7. stu2 收到长缨助手转达的家长鼓励并标记已读
    s2_cheer = client.get("/student/arena-tasks", headers=sh2).json()
    assert len(s2_cheer["cheers"]) == 1 and s2_cheer["cheers"][0]["parentName"] == "陈妈妈"
    assert client.post("/student/arena-cheers/seen", headers=sh2).status_code == 200
    assert client.get("/student/arena-tasks", headers=sh2).json()["cheers"] == []
print("OK")
'''


def test_arena_three_way_sync_end_to_end(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {})
