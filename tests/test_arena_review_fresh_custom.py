"""End-to-end tests for Arena Phase 1 features:
1. Memory freshness / review-due detection (14d for 1-2 stars, 30d for 3 stars) & recovery after re-quiz.
2. Force-refresh tasks (fresh_*) not reusing history, custom due_date, and teacher question preview.
3. Teacher custom questions CRUD, priority injection into student node quiz, grading, wrongbook archival, and deletion.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("review_fresh_custom_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


MATH_QUIZ_HELPERS = r'''
import json
from datetime import datetime, timedelta
from sqlalchemy import select, update


def setup_class_and_student(client, stu_username="stu_arena_1", stu_name="林小星"):
    th, _, sid0, school_id = setup(client)
    with legacy.SessionLocal() as db:
        t_user = db.query(legacy.User).filter(
            legacy.User.school_id == school_id,
            legacy.User.role == "teacher",
        ).first()
        u_extra = legacy.User(
            school_id=school_id,
            username=stu_username,
            name=stu_name,
            role="student",
            grade=5,
            password_hash=legacy.hash_password("123456"),
        )
        db.add(u_extra)
        db.flush()
        sid = int(u_extra.id)
        cls = legacy.SchoolClass(school_id=school_id, name="五年级二班", grade=5, teacher_id=t_user.id)
        db.add(cls)
        db.flush()
        cid = int(cls.id)
        db.add(legacy.ClassStudent(class_id=cid, student_id=sid))
        db.commit()
    sh = {"Authorization": "Bearer " + login_and_change(client, stu_username, "123456", "Student2345")}
    return th, sh, sid, cid, school_id


def build_math_answers(raw_questions, wrong_indices=()):
    wrong_set = set(wrong_indices)
    answers = []
    for idx, q in enumerate(raw_questions):
        qtype = q.get("questionType", "")
        is_wrong = idx in wrong_set
        if qtype in ("single_choice", "true_false"):
            cidx = int(q["correctIndex"])
            opts = q.get("options") or ["正确", "错误"]
            sel = (cidx + 1) % max(2, len(opts)) if is_wrong else cidx
            answers.append({"question_id": q["id"], "selected_index": sel})
        else:
            txt = "__WRONG_ANSWER_999999__" if is_wrong else str(q["answer"])
            answers.append({"question_id": q["id"], "text_answer": txt})
    return answers


def take_math_quiz(client, sh, node_key, wrong_indices=()):
    start_resp = client.post(f"/student/math-star-map/nodes/{node_key}/quiz", headers=sh)
    assert start_resp.status_code == 200, start_resp.text
    quiz_data = start_resp.json()
    with legacy.SessionLocal() as db:
        t_q = legacy.Base.metadata.tables["math_node_quizzes"]
        row = db.execute(select(t_q).where(t_q.c.id == quiz_data["quizId"])).first()
        raw_qs = json.loads(row.items_json)
    answers = build_math_answers(raw_qs, wrong_indices=wrong_indices)
    sub_resp = client.post(
        f"/student/math-star-map/nodes/{node_key}/quiz/submit",
        headers=sh,
        json={"quiz_id": quiz_data["quizId"], "answers": answers},
    )
    assert sub_resp.status_code == 200, sub_resp.text
    return quiz_data, raw_qs, sub_resp.json()
'''


FLOW_REVIEW_FRESHNESS = r'''
with TestClient(app) as client:
    th, sh, sid, cid, school_id = setup_class_and_student(client, "stu_review_1", "温习测试生")

    # 1. 点亮 M1-1 为 1 星（答对 4/5 = 80%，避免直接三星）
    _, _, sub1 = take_math_quiz(client, sh, "M1-1", wrong_indices=(4,))
    assert sub1["accuracy"] == 80
    assert sub1["light"]["stars"] == 1
    assert sub1["light"]["state"] == "lit"

    # 把 M1-1 的 updated_at 改为 15 天前 -> 超过 14 天周期，进入待温习
    with legacy.SessionLocal() as db:
        t_m = legacy.Base.metadata.tables["math_node_mastery"]
        db.execute(
            update(t_m)
            .where(t_m.c.school_id == school_id, t_m.c.student_id == sid, t_m.c.node_key == "M1-1")
            .values(updated_at=datetime.utcnow() - timedelta(days=15))
        )
        db.commit()

    m1 = client.get("/student/math-star-map", headers=sh)
    assert m1.status_code == 200
    m1_data = m1.json()
    n_m11 = next(n for n in m1_data["nodes"] if n["key"] == "M1-1")
    assert n_m11["reviewDue"] is True
    assert n_m11["reviewCycleDays"] == 14
    assert n_m11["daysSincePractice"] >= 15
    assert n_m11["light"]["reviewDue"] is True
    assert m1_data["summary"]["reviewDueCount"] >= 1

    # 教师诊断热力榜也同步体现 reviewDueCount >= 1
    diag = client.get(f"/teacher/arena/diagnostics?subject=数学&class_id={cid}", headers=th)
    assert diag.status_code == 200
    dd = diag.json()
    heat_m11 = next(x for x in dd["nodeHeat"] if x["key"] == "M1-1")
    assert heat_m11["reviewDueCount"] >= 1
    stu_row = next(s for s in dd["students"] if s["studentId"] == sid)
    assert stu_row["reviewDueCount"] >= 1

    # 2. 学生三星精通 M1-2（5/5 全对；若该随机题组无 hard 题则补一次确保 stars == 3）
    _, _, sub2 = take_math_quiz(client, sh, "M1-2", wrong_indices=())
    assert sub2["accuracy"] == 100
    if sub2["light"]["stars"] < 3:
        with legacy.SessionLocal() as db:
            t_m = legacy.Base.metadata.tables["math_node_mastery"]
            db.execute(
                update(t_m)
                .where(t_m.c.school_id == school_id, t_m.c.student_id == sid, t_m.c.node_key == "M1-2")
                .values(hard_correct=1)
            )
            db.commit()

    # 15 天前仍未到 30 天周期 -> reviewDue=False
    with legacy.SessionLocal() as db:
        t_m = legacy.Base.metadata.tables["math_node_mastery"]
        db.execute(
            update(t_m)
            .where(t_m.c.school_id == school_id, t_m.c.student_id == sid, t_m.c.node_key == "M1-2")
            .values(updated_at=datetime.utcnow() - timedelta(days=15))
        )
        db.commit()

    m2 = client.get("/student/math-star-map", headers=sh).json()
    n_m12_15d = next(n for n in m2["nodes"] if n["key"] == "M1-2")
    assert n_m12_15d["light"]["stars"] == 3
    assert n_m12_15d["reviewCycleDays"] == 30
    assert n_m12_15d["reviewDue"] is False

    # 改为 31 天前 -> reviewDue=True
    with legacy.SessionLocal() as db:
        t_m = legacy.Base.metadata.tables["math_node_mastery"]
        db.execute(
            update(t_m)
            .where(t_m.c.school_id == school_id, t_m.c.student_id == sid, t_m.c.node_key == "M1-2")
            .values(updated_at=datetime.utcnow() - timedelta(days=31))
        )
        db.commit()

    m3 = client.get("/student/math-star-map", headers=sh).json()
    n_m12_31d = next(n for n in m3["nodes"] if n["key"] == "M1-2")
    assert n_m12_31d["reviewDue"] is True
    assert n_m12_31d["daysSincePractice"] >= 31
    assert m3["summary"]["reviewDueCount"] >= 2

    # 3. 重做 M1-1 微测答对 >= 80% -> reviewDue 恢复为 False
    _, _, sub_re = take_math_quiz(client, sh, "M1-1", wrong_indices=(0,))
    assert sub_re["accuracy"] >= 80
    m4 = client.get("/student/math-star-map", headers=sh).json()
    n_m11_after = next(n for n in m4["nodes"] if n["key"] == "M1-1")
    assert n_m11_after["reviewDue"] is False
    assert n_m11_after["light"]["reviewDue"] is False
print("OK")
'''


FLOW_FRESH_TASK_AND_PREVIEW = r'''
with TestClient(app) as client:
    th, sh, sid, cid, school_id = setup_class_and_student(client, "stu_fresh_1", "重刷测试生")

    # 1. 学生先点亮数学 M1-1
    _, _, sub0 = take_math_quiz(client, sh, "M1-1", wrong_indices=(4,))
    assert sub0["accuracy"] == 80 and sub0["litUp"] is True

    # 2. 老师派发常规 goal_code='lit' -> 复用历史状态立即达标
    t_norm = client.post(
        "/teacher/arena/tasks",
        headers=th,
        json={
            "subject": "数学",
            "class_id": cid,
            "task_kind": "map_node",
            "target_key": "M1-1",
            "goal_code": "lit",
            "audience": "all",
        },
    )
    assert t_norm.status_code == 200, t_norm.text
    norm_id = t_norm.json()["taskId"]
    assert t_norm.json()["isFresh"] is False

    s_tasks1 = client.get("/student/arena-tasks", headers=sh).json()
    norm_item = next(x for x in s_tasks1["items"] if x["taskId"] == norm_id)
    assert norm_item["status"] == "done"
    assert s_tasks1["pendingCount"] == 0

    # 3. 老师再派发 goal_code='fresh_lit' 并传入自定义 due_date='2026-12-15'
    t_fresh = client.post(
        "/teacher/arena/tasks",
        headers=th,
        json={
            "subject": "数学",
            "class_id": cid,
            "task_kind": "map_node",
            "target_key": "M1-1",
            "goal_code": "fresh_lit",
            "audience": "all",
            "due_date": "2026-12-15",
        },
    )
    assert t_fresh.status_code == 200, t_fresh.text
    fresh_data = t_fresh.json()
    fresh_id = fresh_data["taskId"]
    assert fresh_data["isFresh"] is True
    assert fresh_data["dueDate"] == "2026-12-15"

    # 初始状态必须为未完成（不复用历史战绩）
    s_tasks2 = client.get("/student/arena-tasks", headers=sh).json()
    fresh_item = next(x for x in s_tasks2["items"] if x["taskId"] == fresh_id)
    assert fresh_item["status"] == "pending"
    assert fresh_item["dueDate"] == "2026-12-15"
    assert fresh_item["isFresh"] is True
    assert s_tasks2["pendingCount"] == 1

    # 教师端也显示 0/1
    t_list1 = client.get(f"/teacher/arena/tasks?subject=数学&class_id={cid}", headers=th).json()
    t_fresh_row1 = next(x for x in t_list1["items"] if x["id"] == fresh_id)
    assert t_fresh_row1["doneCount"] == 0 and t_fresh_row1["totalCount"] == 1
    assert t_fresh_row1["dueDate"] == "2026-12-15"

    # 4. 学生新提交一次微测达标后 -> 任务自动变为已完成
    _, _, sub_new = take_math_quiz(client, sh, "M1-1", wrong_indices=())
    assert sub_new["accuracy"] == 100

    s_tasks3 = client.get("/student/arena-tasks", headers=sh).json()
    fresh_item_after = next(x for x in s_tasks3["items"] if x["taskId"] == fresh_id)
    assert fresh_item_after["status"] == "done"
    assert s_tasks3["pendingCount"] == 0

    t_list2 = client.get(f"/teacher/arena/tasks?subject=数学&class_id={cid}", headers=th).json()
    t_fresh_row2 = next(x for x in t_list2["items"] if x["id"] == fresh_id)
    assert t_fresh_row2["doneCount"] == 1 and t_fresh_row2["pendingNames"] == []

    # 5. 验证 GET /teacher/arena/preview-questions 同时返回系统题与私房题预览
    cq_resp = client.post(
        "/teacher/arena/custom-questions",
        headers=th,
        json={
            "subject": "数学",
            "node_key": "M1-1",
            "question_type": "fill_blank",
            "stem": "【预览测试私房题】0.25 × 8 = （ ）",
            "options": [],
            "answer": "2",
            "explanation": "0.25 乘 4 得 1，再乘 2 得 2。",
        },
    )
    assert cq_resp.status_code == 200, cq_resp.text
    cq_qid = cq_resp.json()["questionId"]

    prev = client.get("/teacher/arena/preview-questions?subject=数学&kind=map_node&target_key=M1-1", headers=th)
    assert prev.status_code == 200, prev.text
    pd = prev.json()
    assert pd["subject"] == "数学" and pd["kind"] == "map_node" and pd["targetKey"] == "M1-1"
    assert pd["builtinCount"] > 0
    assert pd["customCount"] == 1
    assert len(pd["builtinQuestions"]) == pd["builtinCount"]
    assert len(pd["customQuestions"]) == 1
    assert pd["customQuestions"][0]["questionId"] == cq_qid
    assert pd["customQuestions"][0]["isCustom"] is True
    assert any(x["isCustom"] is True for x in pd["items"])
    assert any(x["isCustom"] is False for x in pd["items"])
print("OK")
'''


FLOW_CUSTOM_QUESTIONS = r'''
with TestClient(app) as client:
    th, sh, sid, cid, school_id = setup_class_and_student(client, "stu_custom_1", "私房题测试生")

    # 1. 老师给数学 M1-1 添加 1 道单选题和 1 道判断题
    r_sc = client.post(
        "/teacher/arena/custom-questions",
        headers=th,
        json={
            "subject": "数学",
            "node_key": "M1-1",
            "question_type": "single_choice",
            "stem": "【老师私房单选】0.3 × 4 的积是多少？",
            "options": ["1.2", "12", "0.12", "120"],
            "answer": "1.2",
            "explanation": "3×4=12，因数共一位小数，所以积是 1.2。",
        },
    )
    assert r_sc.status_code == 200, r_sc.text
    sc_obj = r_sc.json()
    sc_id = sc_obj["id"]
    sc_qid = sc_obj["questionId"]
    assert sc_qid == f"cq_{sc_id}" and sc_obj["isCustom"] is True

    r_tf = client.post(
        "/teacher/arena/custom-questions",
        headers=th,
        json={
            "subject": "数学",
            "node_key": "M1-1",
            "question_type": "true_false",
            "stem": "【老师私房判断】两个小数相乘，积一定大于其中一个因数。",
            "options": ["正确", "错误"],
            "answer": "错误",
            "explanation": "例如 0.5 × 0.2 = 0.1，积比两个因数都小。",
        },
    )
    assert r_tf.status_code == 200, r_tf.text
    tf_obj = r_tf.json()
    tf_id = tf_obj["id"]
    tf_qid = tf_obj["questionId"]
    assert tf_qid == f"cq_{tf_id}" and tf_obj["isCustom"] is True

    # 2. GET /teacher/arena/custom-questions 可查到这两道私房题
    listed = client.get("/teacher/arena/custom-questions?subject=数学&node_key=M1-1", headers=th)
    assert listed.status_code == 200
    listed_ids = {x["id"] for x in listed.json()["items"]}
    assert {sc_id, tf_id}.issubset(listed_ids)

    # 3. 学生发起 M1-1 微测，返回的 5 题中包含这两道 isCustom=True 的私房题
    q_start = client.post("/student/math-star-map/nodes/M1-1/quiz", headers=sh)
    assert q_start.status_code == 200
    q_data = q_start.json()
    assert q_data["count"] == 5 and len(q_data["questions"]) == 5
    custom_in_quiz = [q for q in q_data["questions"] if q.get("isCustom") is True]
    assert {q["id"] for q in custom_in_quiz} == {sc_qid, tf_qid}

    # 4. 学生提交答卷：私房单选答对、私房判断故意答错、其余自带题全部答对
    with legacy.SessionLocal() as db:
        t_q = legacy.Base.metadata.tables["math_node_quizzes"]
        raw_qs = json.loads(db.execute(select(t_q).where(t_q.c.id == q_data["quizId"])).first().items_json)

    answers = []
    for q in raw_qs:
        if q["id"] == sc_qid:
            # 正确答案 '1.2' 在索引 0
            answers.append({"question_id": q["id"], "selected_index": 0})
        elif q["id"] == tf_qid:
            # 正确答案 '错误' 在索引 1，故意选 0 ('正确')
            answers.append({"question_id": q["id"], "selected_index": 0})
        elif q["questionType"] in ("single_choice", "true_false"):
            answers.append({"question_id": q["id"], "selected_index": int(q["correctIndex"])})
        else:
            answers.append({"question_id": q["id"], "text_answer": str(q["answer"])})

    sub = client.post(
        "/student/math-star-map/nodes/M1-1/quiz/submit",
        headers=sh,
        json={"quiz_id": q_data["quizId"], "answers": answers},
    )
    assert sub.status_code == 200, sub.text
    sub_data = sub.json()
    assert sub_data["correct"] == 4 and sub_data["total"] == 5
    det_sc = next(d for d in sub_data["details"] if d["id"] == sc_qid)
    det_tf = next(d for d in sub_data["details"] if d["id"] == tf_qid)
    assert det_sc["correct"] is True and det_sc["isCustom"] is True
    assert det_tf["correct"] is False and det_tf["isCustom"] is True
    assert det_tf["answer"] == "错误"

    # 答错的私房题进入错题本，答对的不进入
    wb = client.get("/student/arena-wrongbook?subject=数学&status=active", headers=sh)
    assert wb.status_code == 200, wb.text
    wb_qids = {x["questionId"] for x in wb.json()["items"]}
    assert tf_qid in wb_qids
    assert sc_qid not in wb_qids

    # 5. 老师删除私房题后不再出现在列表与后续学生微测出题中
    assert client.delete(f"/teacher/arena/custom-questions/{sc_id}", headers=th).status_code == 200
    assert client.delete(f"/teacher/arena/custom-questions/{tf_id}", headers=th).status_code == 200

    listed_after = client.get("/teacher/arena/custom-questions?subject=数学&node_key=M1-1", headers=th).json()
    assert listed_after["items"] == []

    q_next = client.post("/student/math-star-map/nodes/M1-1/quiz", headers=sh)
    assert q_next.status_code == 200
    next_qs = q_next.json()["questions"]
    assert len(next_qs) == 5
    assert all(not q.get("isCustom") for q in next_qs)
    assert not ({q["id"] for q in next_qs} & {sc_qid, tf_qid})
print("OK")
'''


def test_arena_memory_freshness_review_due(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + MATH_QUIZ_HELPERS + FLOW_REVIEW_FRESHNESS, {})


def test_arena_fresh_task_due_date_and_preview(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + MATH_QUIZ_HELPERS + FLOW_FRESH_TASK_AND_PREVIEW, {})


def test_arena_custom_questions_crud_and_quiz_injection(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + MATH_QUIZ_HELPERS + FLOW_CUSTOM_QUESTIONS, {})
