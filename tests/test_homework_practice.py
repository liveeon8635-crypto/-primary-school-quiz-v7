from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hw_practice_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_ai_assisted_questions_become_reviewed_practice_that_can_clear_the_flag(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
from sqlalchemy import func
KP = "米和千米的换算"
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == sid))
        if link is None:
            cls = legacy.SchoolClass(school_id=school_id, name="晚托三年级", grade=3, teacher_id=teacher.id); db.add(cls); db.flush()
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid))
        else:
            db.get(legacy.SchoolClass, link.class_id).teacher_id = teacher.id
        db.add(legacy.Question(school_id=school_id, grade=3, subject="数学", knowledge=KP, text="题库题", options_json="[]", correct_index=0))
        db.commit()
    def assignments():
        with legacy.SessionLocal() as db:
            return db.scalar(select(func.count()).select_from(legacy.Assignment))

    q1 = "小志家距离学校500米。如果一天走2个完整来回，一共走多少米？合多少千米？"
    h1 = make_help(client, sh, text=q1)
    replies.append(sol(answer="2000米，2千米", expression="500×2×2", steps=("一个来回是 500×2=1000 米", "两个来回 2000 米", "2000 米=2 千米"), kp=KP))
    assert client.post(f"/student/homework/help/{h1}/solve", headers=sh).status_code == 200
    q2 = "一根长2米4分米的绳子，平均剪成4段，每段长多少分米？"
    h2 = make_help(client, sh, text=q2)
    replies.append(sol(answer="6分米", expression="24÷4", steps=("2米4分米=24分米", "24÷4=6"), kp="长度单位换算与平均分"))
    assert client.post(f"/student/homework/help/{h2}/solve", headers=sh).status_code == 200
    assert client.get("/student/homework/knowledge", headers=sh).json()["flags"][0]["state"] == "open"

    # ---- the teacher sees the pupil's AI-explained questions
    src = client.get(f"/teacher/homework/students/{sid}/practice-sources", headers=th)
    assert src.status_code == 200, src.text
    items = {i["helpId"]: i for i in src.json()["items"]}
    assert items[h1]["matched"] and items[h1]["flag"] == "open" and items[h1]["knowledge"] == KP
    assert not items[h2]["matched"] and items[h2]["knowledge"] == "长度单位换算与平均分"
    assert client.get(f"/teacher/homework/students/{sid}/practice-sources", headers=sh).status_code == 403
    k1, k2 = items[h1]["groupKey"], items[h2]["groupKey"]

    # ---- generate: copies and number-only changes are rejected; nothing is saved or assigned
    replies.append(json.dumps({"groups": [
        {"key": k1, "questions": [
            {"question_type": "fill_blank", "level": 1, "text": q1, "answer": "2000米"},                                   # the original
            {"question_type": "fill_blank", "level": 1, "text": q1.replace("500", "600"), "answer": "2400米"},          # number only
            {"question_type": "fill_blank", "level": 1, "text": "从家到书店300米，小华去书店买书再原路回家，一共走了多少米？", "answer": "600",
             "accepted_answers": ["600米"], "explanation": "来回是两倍路程"},
            {"question_type": "fill_blank", "level": 2, "text": "运动场一圈400米，小明跑了5圈，合多少千米？", "answer": "2",
             "accepted_answers": ["2千米"], "explanation": "400×5=2000米=2千米"},
            {"question_type": "single_choice", "level": 3, "text": "3千米和2800米相比，哪个更长？", "options": ["3千米", "2800米", "一样长", "无法比较"],
             "correct_index": 0, "explanation": "3千米=3000米"}]},
        {"key": k2, "questions": [
            {"question_type": "single_choice", "level": 1, "text": "3千米和2800米相比，哪个更长？", "options": ["3千米", "2800米", "一样长", "无法比较"],
             "correct_index": 0},                                                                                      # repeats another group's question
            {"question_type": "fill_blank", "level": 1, "text": "一根彩带长3米6分米，平均分成6段，每段长多少分米？", "answer": "6", "accepted_answers": ["6分米"]},
            {"question_type": "fill_blank", "level": 2, "text": "一块木板长1米2分米，锯成长度相等的3块，每块多少厘米？", "answer": "40", "accepted_answers": ["40厘米"]}]}]},
        ensure_ascii=False))
    n0 = assignments()
    g = client.post(f"/teacher/homework/students/{sid}/practice/generate", headers=th, json={"helpIds": [h1, h2]})
    assert g.status_code == 200, g.text
    groups = {x["key"]: x for x in g.json()["groups"]}
    assert len(groups[k1]["questions"]) == 3 and all(q["knowledge"] == KP for q in groups[k1]["questions"])     # exact name: can clear the flag
    assert groups[k1]["count"] == 3 and len(groups[k2]["questions"]) == 2 and groups[k2]["subject"] == "数学"
    assert all(q1 not in q["text"] for q in groups[k1]["questions"])
    assert not {q["text"] for q in groups[k1]["questions"]} & {q["text"] for q in groups[k2]["questions"]}
    assert "500米" in prompts[-1] and "2米4分米" in prompts[-1] and "小明" not in prompts[-1].split("学生问过的题")[0]
    assert assignments() == n0

    # ---- AI failure keeps everything as it was
    replies.append(RuntimeError("down"))
    assert client.post(f"/teacher/homework/students/{sid}/practice/generate", headers=th, json={"helpIds": [h1]}).status_code == 502

    # ---- teacher edits, then assigns once, only to this pupil
    edited = [dict(x, questions=x["questions"]) for x in g.json()["groups"]]
    mg = next(x for x in edited if x["key"] == k1)
    mg["questions"][0]["text"] = "从家到书店350米，小华去书店再原路回家，一共走了多少米？"
    mg["questions"][0]["answer"] = "700"; mg["questions"][0]["accepted_answers"] = ["700米"]
    bad = [dict(mg, questions=[dict(mg["questions"][0], text=q1)])]
    rb = client.post(f"/teacher/homework/students/{sid}/practice/assign", headers=th, json={"requestId": "req-bad-0001", "groups": bad}); assert rb.status_code == 400, (rb.status_code, rb.text)
    body = {"requestId": "req-0001-abcd", "groups": [{"key": x["key"], "subject": x["subject"], "helpIds": x["helpIds"], "questions": x["questions"]} for x in edited]}
    a = client.post(f"/teacher/homework/students/{sid}/practice/assign", headers=th, json=body)
    assert a.status_code == 200, a.text
    assert client.post(f"/teacher/homework/students/{sid}/practice/assign", headers=th, json=body).status_code == 409
    assert assignments() == n0 + 1
    aid = a.json()["assigned"][0]["assignmentId"]
    with legacy.SessionLocal() as db:
        assert list(db.scalars(select(legacy.AssignmentRecipient.student_id).where(legacy.AssignmentRecipient.assignment_id == aid))) == [sid]

    # ---- the pupil answers in the existing homework; doing well clears the flag
    mine = next(x for x in client.get("/student/assignments", headers=sh).json() if x["id"] == aid)
    paper = client.get(f"/papers/{mine['paperID']}/questions", headers=sh).json()
    assert len(paper) == 5 and all("correct_index" not in q and "explanation" not in q for q in paper)
    right = {"从家到书店350米": "700米", "运动场一圈400米": "2千米", "一根彩带": "6分米", "一块木板": "40厘米"}
    answers = [{"question_id": q["id"], "selected_index": 0} if q["questionType"] == "single_choice" else
               {"question_id": q["id"], "text_answer": next(v for k, v in right.items() if q["text"].startswith(k))} for q in paper]
    done = client.post(f"/student/assignments/{aid}/submit", headers=sh, json={"answers": answers})
    assert done.status_code == 200 and done.json()["correct"] == 5, done.text
    assert client.get("/student/homework/knowledge", headers=sh).json()["flags"][0]["state"] == "cleared"
    after = client.get(f"/teacher/homework/students/{sid}/practice-sources", headers=th).json()
    assert after["practice"][0]["state"] == "graded" and after["practice"][0]["correct"] == 5
    assert all(i["practised"] for i in after["items"] if i["helpId"] in (h1, h2))

    page = client.get("/v1/homework").text
    assert "生成巩固练习" in page and "/practice/generate" in page and "/practice/assign" in page and "审核确认并布置" in page
    print("OK")
''')


def test_failed_assignments_resume_without_reissuing_successful_subjects(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
from sqlalchemy import func
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == sid))
        if link is None:
            cls = legacy.SchoolClass(school_id=school_id, name="晚托班", grade=3, teacher_id=teacher.id)
            db.add(cls); db.flush()
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid))
        else:
            db.get(legacy.SchoolClass, link.class_id).teacher_id = teacher.id
        db.commit()
    h1 = make_help(client, sh, text="小明有十二个苹果，吃掉五个，还剩几个？")
    replies.append(sol(kp="加减法"))
    assert client.post(f"/student/homework/help/{h1}/solve", headers=sh).status_code == 200
    h2 = make_help(client, sh, text="请写出 cat 这个单词的中文意思。")
    replies.append(sol(kp="英语单词"))
    assert client.post(f"/student/homework/help/{h2}/solve", headers=sh).status_code == 200
    sources = client.get(f"/teacher/homework/students/{sid}/practice-sources", headers=th).json()["items"]
    keys = {i["helpId"]: i["groupKey"] for i in sources}
    def payload(request_id):
        return {"requestId": request_id, "groups": [
            {"key": keys[h1], "subject": "数学", "helpIds": [h1], "questions": [
                {"question_type": "fill_blank", "level": 1, "text": "小红在操场捡到四片树叶，又捡到三片，共有几片？", "answer": "7"}]},
            {"key": keys[h2], "subject": "英语", "helpIds": [h2], "questions": [
                {"question_type": "fill_blank", "level": 1, "text": "请写出 dog 这个单词的中文意思。", "answer": "狗"}]},
        ]}
    def count():
        with legacy.SessionLocal() as db:
            return db.scalar(select(func.count()).select_from(legacy.Assignment))
    url = f"/teacher/homework/students/{sid}/practice/assign"
    original = legacy._teacher_reinforcement_assign
    fail = {"subject": "数学", "after": False}
    calls = []
    def flaky(student_id, body, teacher, db, *, before_commit=None):
        subject = body.questions[0].subject
        calls.append(subject)
        if fail["subject"] == subject and not fail["after"]:
            fail["subject"] = ""
            raise HTTPException(503, "临时故障")
        result = original(student_id, body, teacher, db, before_commit=before_commit)
        if fail["subject"] == subject and fail["after"]:
            fail["subject"] = ""
            raise RuntimeError("提交后连接断开")
        return result
    legacy._teacher_reinforcement_assign = flaky
    start = count()
    first = payload("retry-first-0001")
    r = client.post(url, headers=th, json=first)
    assert r.status_code == 409 and "重试未布置科目" in r.json()["detail"], r.text
    assert count() == start
    r = client.post(url, headers=th, json=first)
    assert r.status_code == 200 and len(r.json()["assigned"]) == 2, r.text
    assert count() == start + 2 and calls == ["数学", "数学", "英语"]
    assert client.post(url, headers=th, json=first).status_code == 409
    assert count() == start + 2

    # A second subject fails after the first has been committed; the retry skips the first.
    fail.update(subject="英语", after=False)
    second = payload("retry-second-002")
    r = client.post(url, headers=th, json=second)
    assert r.status_code == 409 and "已布置：数学" in r.json()["detail"], r.text
    assert count() == start + 3
    altered = {**second, "dueDate": "2026-12-01"}
    assert client.post(url, headers=th, json=altered).status_code == 409
    before_retry = calls.count("数学")
    r = client.post(url, headers=th, json=second)
    assert r.status_code == 200 and len(r.json()["assigned"]) == 2, r.text
    assert calls.count("数学") == before_retry and count() == start + 4
    assert client.post(url, headers=th, json=second).status_code == 409

    # Even if the response is lost after commit, the assignment and receipt stay together.
    fail.update(subject="数学", after=True)
    third = payload("retry-after-0003")
    r = client.post(url, headers=th, json=third)
    assert r.status_code == 409 and count() == start + 5, r.text
    before_retry = calls.count("数学")
    r = client.post(url, headers=th, json=third)
    assert r.status_code == 200 and len(r.json()["assigned"]) == 2, r.text
    assert calls.count("数学") == before_retry and count() == start + 6
    page = client.get("/v1/homework").text
    assert "重试未布置的科目" in page and "按首次审核的题目补布置" in page
    print("OK")
''')
