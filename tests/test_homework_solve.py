from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_KEYS = (
    "HOMEWORK_ASSISTANT", "HOMEWORK_VISION_PROVIDER", "HOMEWORK_VISION_BASE_URL", "HOMEWORK_VISION_MODEL",
    "HOMEWORK_VISION_API_KEY", "HOMEWORK_STUDENT_DAILY_LIMIT", "HOMEWORK_SCHOOL_HOURLY_LIMIT", "HOMEWORK_AI_CONCURRENCY",
)


def run_isolated(tmp_path, script: str, extra_env: dict[str, str] | None = None) -> str:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path / 'solve.sqlite3'}", "PYTHONPATH": str(ROOT)}
    for key in ENV_KEYS:
        env.pop(key, None)
    env.update({"HOMEWORK_ASSISTANT": "1", **(extra_env or {})})
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=env, text=True, capture_output=True, timeout=240
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout, result.stdout
    return result.stdout


COMMON = r'''
import json
import os

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

import app_v924 as legacy
from app import app

prompts = []
replies = []          # queue of replies (str or Exception) for the fake model
calls = []


def sol(answer="7", expression="12-5", steps=("先算 12 减 5", "得到 7"), kp="两位数减一位数"):
    return json.dumps({"method": "直接相减", "steps": [{"n": i + 1, "text": t} for i, t in enumerate(steps)],
                       "answer": answer, "expression": expression, "knowledgePoint": kp}, ensure_ascii=False)


def fake_ai(db, u, feature, prompt, images=None, timeout=90, rate_check=None):
    # Mirrors the real function's contract: the limit hook runs first, every call is logged.
    (rate_check or legacy._ai_rate_check)(db, u.school_id)
    calls.append({"feature": feature, "timeout": timeout, "rate_check": rate_check})
    prompts.append(prompt)
    db.add(legacy.AIUsageLog(school_id=u.school_id, user_id=u.id, feature=feature, provider="p", model="m", status="ok"))
    db.commit()
    reply = replies.pop(0)
    if isinstance(reply, Exception):
        raise reply
    return reply


real_ai = legacy._ai_call   # the production chain, including the subject-aware wrappers
legacy._ai_call = fake_ai


def login_and_change(client, username, old_password, new_password):
    login = client.post("/login", json={"username": username, "password": old_password, "remember": False})
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    changed = client.post("/change-password", headers={"Authorization": f"Bearer {token}"},
                          json={"current_password": old_password, "new_password": new_password, "remember": False})
    assert changed.status_code == 200, changed.text
    return changed.json()["token"]


def setup(client):
    th = {"Authorization": "Bearer " + login_and_change(client, "teacher1", "123456", "Teacher1234")}
    sh = {"Authorization": "Bearer " + login_and_change(client, "student1", "123456", "Student1234")}
    session = client.get("/session", headers=sh).json()
    with legacy.SessionLocal() as db:
        school_id = db.get(legacy.User, session["userID"]).school_id
        row = legacy.ai_config_for(db, school_id, True)
        row.enabled = True
        row.allow_student_data = True
        row.provider = "openai_compatible"
        row.base_url = "https://api.deepseek.com"
        row.model = "text-model"
        db.commit()
    return th, sh, session["userID"], school_id


def make_help(client, sh, text="小明有 12 个苹果，吃了 5 个，还剩几个？ 电话 13812345678", grade=3):
    r = client.post("/student/homework/help", headers=sh, json={"questionText": text, "grade": grade})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def row_of(help_id):
    tbl = legacy.Base.metadata.tables["help_requests"]
    with legacy.SessionLocal() as db:
        return dict(db.execute(select(tbl).where(tbl.c.id == help_id)).first()._mapping)
'''


def test_solve_gives_one_stepwise_solution_with_the_fixed_warning(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    hid = make_help(client, sh)
    assert not calls, "confirming must not call the model"

    replies.append(sol())
    r = client.post(f"/student/homework/help/{hid}/solve", headers=sh)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "answered" and body["verifyStatus"] == "ok"
    s = body["solution"]
    assert s["method"] == "直接相减" and [x["n"] for x in s["steps"]] == [1, 2] and s["answer"] == "7"
    assert body["warning"] == "AI 可能出错，请自己判断" == s["warning"]
    assert "expression" not in s and "verify" not in s and "已验证" not in json.dumps(body, ensure_ascii=False)

    # Exactly one model call, student feature name, short timeout, with the student limit hook.
    assert len(calls) == 1
    assert calls[0]["feature"] == "homework_help_solve" and calls[0]["timeout"] == 30 and calls[0]["rate_check"] is not None

    # Only grade + question reached the model: no names, accounts, school, class, ids, phone.
    prompt = prompts[0]
    assert "三年级" in prompt and "小明有 12 个苹果" in prompt
    assert "13812345678" not in prompt
    for secret in ("student1", "Student1234", "三年级一班", "王老师", "teacher1", "schools"):
        assert secret not in prompt.replace("三年级学生", "").replace("三年级的", ""), secret
    assert "只给一种解法" in prompt and "不要出现初中及以上的知识" in prompt

    # Asking again never pays for a second answer.
    again = client.post(f"/student/homework/help/{hid}/solve", headers=sh)
    assert again.status_code == 200 and again.json()["solution"]["answer"] == "7" and len(calls) == 1
    assert client.get(f"/student/homework/help/{hid}", headers=sh).json()["solution"]["answer"] == "7"
print("OK")
''',
    )


def test_a_wrong_answer_is_rechecked_once_then_withheld_and_escalated(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    # Wrong first, right on the re-check -> the student only ever sees the checked answer.
    hid = make_help(client, sh)
    replies.extend([sol(answer="8"), sol(answer="7")])
    r = client.post(f"/student/homework/help/{hid}/solve", headers=sh).json()
    assert r["state"] == "answered" and r["solution"]["answer"] == "7" and len(calls) == 2
    assert "重新仔细计算" in prompts[1] and "重新仔细计算" not in prompts[0]
    assert row_of(hid)["verify_status"] == "ok"

    # Wrong twice -> nothing is shown, the request goes to the teacher.
    calls.clear(); prompts.clear()
    from datetime import datetime, timedelta
    from sqlalchemy import update
    with legacy.SessionLocal() as db:
        db.execute(update(legacy.Base.metadata.tables["help_requests"]).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.execute(update(legacy.AIUsageLog).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.commit()
    hid2 = make_help(client, sh, text="12-5=?")
    replies.extend([sol(answer="8"), sol(answer="9")])
    r = client.post(f"/student/homework/help/{hid2}/solve", headers=sh)
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "escalated" and body["solution"] is None and "没有把握" in body["message"]
    assert not any(ch.isdigit() for ch in body["message"]) and "answer" not in body and "steps" not in json.dumps(body)
    stored = row_of(hid2)
    assert stored["escalate_reason"] == "verify_mismatch" and stored["verify_status"] == "mismatch" and stored["escalated_at"]
    data = json.loads(stored["ai_json"])
    assert data["hidden"] is True and len(data["attempts"]) == 2          # the teacher still sees what the AI said
    got = client.get(f"/student/homework/help/{hid2}", headers=sh).json()
    assert got["solution"] is None and "没有把握" in got["message"]

    # The re-check itself failing counts as "still not sure": also escalated, answer withheld.
    with legacy.SessionLocal() as db:
        db.execute(update(legacy.Base.metadata.tables["help_requests"]).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.execute(update(legacy.AIUsageLog).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.commit()
    hid3 = make_help(client, sh, text="12-5=?")
    replies.extend([sol(answer="8"), HTTPException(503, "boom")])
    r3 = client.post(f"/student/homework/help/{hid3}/solve", headers=sh).json()
    assert r3["state"] == "escalated" and r3["solution"] is None

    # Wrong first, and the re-check cannot be verified: never show the unverified second answer.
    with legacy.SessionLocal() as db:
        db.execute(update(legacy.Base.metadata.tables["help_requests"]).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.execute(update(legacy.AIUsageLog).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.commit()
    hid4 = make_help(client, sh, text="12-5=?")
    replies.extend([sol(answer="8"), sol(answer="7", expression="先把 12 减去 5")])
    r4 = client.post(f"/student/homework/help/{hid4}/solve", headers=sh).json()
    assert r4["state"] == "escalated" and r4["solution"] is None
print("OK")
''',
    )


def test_unverifiable_answers_are_shown_with_the_warning_and_junk_can_be_retried(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    # Word reasoning without a calculation cannot be checked: shown, marked skipped, warning kept.
    hid = make_help(client, sh, text="为什么冬天白天比夏天短？")
    replies.append(sol(answer="地球倾斜", expression=""))
    r = client.post(f"/student/homework/help/{hid}/solve", headers=sh).json()
    assert r["state"] == "answered" and r["verifyStatus"] == "skipped" and r["warning"] == "AI 可能出错，请自己判断"

    # Not JSON / empty steps: friendly 502, the request stays "confirmed" and can be retried.
    hid2 = make_help(client, sh, text="3+4=?")
    replies.append("抱歉，我没法回答")
    bad = client.post(f"/student/homework/help/{hid2}/solve", headers=sh)
    assert bad.status_code == 502 and "再试" in bad.json()["detail"]
    assert row_of(hid2)["state"] == "confirmed"
    replies.append(sol(answer="7", expression="3+4", steps=("3 加 4",)))
    assert client.post(f"/student/homework/help/{hid2}/solve", headers=sh).json()["state"] == "answered"
print("OK")
''',
    )


def test_solve_respects_access_rules_limits_and_the_school_gate(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
from changying.services.homework_limits import ai_slot

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    hid = make_help(client, sh)

    # Teachers have no student solve endpoint; unknown ids are 404; other students cannot touch it.
    assert client.post(f"/student/homework/help/{hid}/solve", headers=th).status_code == 403
    assert client.post("/student/homework/help/9999/solve", headers=sh).status_code == 404
    with legacy.SessionLocal() as db:
        other = legacy.User(school_id=school_id, username="other9", password_hash=legacy.hash_password("Passw0rd!x"),
                            name="同学", role="student", grade=4)
        db.add(other); db.flush()
        db.add(legacy.UserSecurity(user_id=other.id, must_change_password=False)); db.commit()
    oh = {"Authorization": "Bearer " + client.post("/login", json={"username": "other9", "password": "Passw0rd!x", "remember": False}).json()["token"]}
    assert client.post(f"/student/homework/help/{hid}/solve", headers=oh).status_code == 404
    assert not calls

    # Concurrency gate: a busy moment gives a polite 429 and no model call is made.
    with ai_slot(), ai_slot():
        pass
    from changying.services import homework_limits
    os.environ["HOMEWORK_AI_CONCURRENCY"] = "1"
    with ai_slot():
        busy = client.post(f"/student/homework/help/{hid}/solve", headers=sh)
        assert busy.status_code == 429 and "稍等" in busy.json()["detail"] and not calls
    del os.environ["HOMEWORK_AI_CONCURRENCY"]

    # Per-student call limit goes through the hook passed to the model call (3 calls/day at limit 1).
    os.environ["HOMEWORK_STUDENT_DAILY_LIMIT"] = "1"
    from datetime import datetime, timedelta
    from sqlalchemy import update
    # Pin the school day so rows from 10 minutes ago still count when the test runs just after UTC+8 midnight.
    homework_limits.school_day_start_utc = lambda now=None: datetime.utcnow() - timedelta(hours=1)
    with legacy.SessionLocal() as db:
        for _ in range(3):
            db.add(legacy.AIUsageLog(school_id=school_id, user_id=sid, feature="homework_help_vision", provider="p", model="m", status="ok",
                                     created_at=datetime.utcnow() - timedelta(minutes=10)))
        db.commit()
    capped = client.post(f"/student/homework/help/{hid}/solve", headers=sh)
    assert capped.status_code == 429 and "明天" in capped.json()["detail"]
    assert not calls or calls[-1]["rate_check"] is not None

    # School gate: without allow_student_data nothing runs.
    del os.environ["HOMEWORK_STUDENT_DAILY_LIMIT"]
    with legacy.SessionLocal() as db:
        row = legacy.ai_config_for(db, school_id, False); row.allow_student_data = False; db.commit()
    assert client.post(f"/student/homework/help/{hid}/solve", headers=sh).status_code == 403
print("OK")
''',
    )


def test_solve_works_through_the_real_call_chain_and_logs_a_student_row(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
legacy._ai_call = real_ai
legacy._validate_ai_base_url = lambda base, runtime=False: base
posts = []


class FakeResponse:
    ok = True
    status_code = 200

    def json(self):
        return {"choices": [{"message": {"content": sol()}}], "usage": {"prompt_tokens": 50, "completion_tokens": 60}}


legacy.requests.post = lambda url, headers=None, json=None, timeout=None: (posts.append((url, json, timeout)), FakeResponse())[1]

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    hid = make_help(client, sh)
    r = client.post(f"/student/homework/help/{hid}/solve", headers=sh)
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "answered" and r.json()["solution"]["answer"] == "7"
    assert len(posts) == 1 and posts[0][0] == "https://api.deepseek.com/chat/completions" and posts[0][2] == 30
    sent = posts[0][1]["messages"][0]["content"]
    assert "三年级" in sent and "student1" not in sent
    with legacy.SessionLocal() as db:
        log = db.scalars(select(legacy.AIUsageLog).where(legacy.AIUsageLog.feature == "homework_help_solve")).all()
        assert len(log) == 1 and log[0].user_id == sid and log[0].input_tokens == 50 and log[0].status == "ok"
print("OK")
''',
        {"AI_API_KEY": "test-key-not-real"},
    )


def test_page_always_carries_the_fixed_warning_text():
    import app  # noqa: F401
    from changying.web.homework_assistant_pages import homework_page_html

    html = homework_page_html()
    assert "AI 可能出错，请自己判断" in html
    assert "solve" in html and "看下一步" in html and "innerHTML" not in html


def test_two_simultaneous_solve_requests_pay_for_one_answer(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
import threading
import time

gate = threading.Event()


def slow_ai(db, u, feature, prompt, images=None, timeout=90, rate_check=None):
    calls.append(feature)
    gate.wait(5)                      # the model is "thinking"
    return sol()


legacy._ai_call = slow_ai

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    hid = make_help(client, sh)
    results = []

    def tap():
        results.append(client.post(f"/student/homework/help/{hid}/solve", headers=sh))

    first = threading.Thread(target=tap)
    first.start()
    time.sleep(0.5)                                              # first request is now waiting on the model
    assert row_of(hid)["state"] == "solving"
    second = client.post(f"/student/homework/help/{hid}/solve", headers=sh)   # the double tap
    assert second.status_code == 409 and "稍等" in second.json()["detail"]
    gate.set()
    first.join()
    assert results[0].status_code == 200 and results[0].json()["state"] == "answered"
    assert len(calls) == 1, "the model must be called once"
    assert client.post(f"/student/homework/help/{hid}/solve", headers=sh).json()["state"] == "answered"
    assert len(calls) == 1
print("OK")
''',
    )


def test_a_failed_answer_hands_the_request_back_and_asking_the_teacher_wins_a_race(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
from sqlalchemy import update

HELP = legacy.Base.metadata.tables["help_requests"]

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    # The model call fails: the request goes back to "confirmed" so the student can simply retry.
    hid = make_help(client, sh)
    replies.append(HTTPException(503, "model down"))
    failed = client.post(f"/student/homework/help/{hid}/solve", headers=sh)
    assert failed.status_code == 503
    assert row_of(hid)["state"] == "confirmed"
    replies.append(sol())
    assert client.post(f"/student/homework/help/{hid}/solve", headers=sh).json()["state"] == "answered"

    # The student asks the teacher while the answer is still being worked out: the teacher request is kept.
    from datetime import datetime, timedelta
    with legacy.SessionLocal() as db:
        db.execute(update(HELP).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.execute(update(legacy.AIUsageLog).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.commit()
    hid2 = make_help(client, sh, text="3+4=?")

    def ai_then_escalate(db, u, feature, prompt, images=None, timeout=90, rate_check=None):
        with legacy.SessionLocal() as other:                          # meanwhile, on another device
            other.execute(update(HELP).where(HELP.c.id == hid2).values(state="escalated", escalate_reason="student_request"))
            other.commit()
        return sol(answer="7", expression="3+4", steps=("3 加 4",))

    legacy._ai_call = ai_then_escalate
    done = client.post(f"/student/homework/help/{hid2}/solve", headers=sh)
    assert done.status_code == 200 and done.json()["state"] == "escalated"
    assert row_of(hid2)["state"] == "escalated" and row_of(hid2)["escalate_reason"] == "student_request"
print("OK")
''',
    )


def test_a_request_stuck_in_solving_after_a_restart_can_be_retried(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
from sqlalchemy import update

HELP = legacy.Base.metadata.tables["help_requests"]

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    hid = make_help(client, sh)
    # Simulate a crash/restart mid-answer: the row says "solving" but no worker in this process owns it.
    with legacy.SessionLocal() as db:
        db.execute(update(HELP).where(HELP.c.id == hid).values(state="solving"))
        db.commit()
    replies.append(sol())
    done = client.post(f"/student/homework/help/{hid}/solve", headers=sh)
    assert done.status_code == 200 and done.json()["state"] == "answered"
print("OK")
''',
    )


def test_questions_up_to_1000_characters_are_accepted_and_sent_whole(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    too_long = "读" * 1001
    r = client.post("/student/homework/help", headers=sh, json={"questionText": too_long, "grade": 5})
    assert r.status_code == 400 and "1000" in r.text

    text = "阅读短文：" + "春" * 980 + "ENDMARK"            # a long reading-comprehension passage, 992 characters
    assert len(text) <= 1000
    hid = make_help(client, sh, text=text, grade=5)
    replies.append(sol())
    done = client.post(f"/student/homework/help/{hid}/solve", headers=sh)
    assert done.status_code == 200 and done.json()["state"] == "answered"
    assert prompts and "ENDMARK" in prompts[0]           # nothing was cut off on the way to the model
print("OK")
''',
    )


def test_each_ai_assisted_question_leaves_a_permanent_knowledge_record(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
from sqlalchemy import select, update
from datetime import datetime, timedelta

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    table = legacy.Base.metadata.tables["homework_ai_knowledge"]
    with legacy.SessionLocal() as db:
        known = db.execute(select(legacy.Question.knowledge).where(legacy.Question.school_id == school_id, legacy.Question.grade == 3)).scalars().first()
    assert known, "the demo school must have grade-3 questions"

    def rows():
        with legacy.SessionLocal() as db:
            return [dict(r._mapping) for r in db.execute(select(table).order_by(table.c.id)).all()]

    def age_everything():
        with legacy.SessionLocal() as db:
            db.execute(update(legacy.Base.metadata.tables["help_requests"]).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
            db.execute(update(legacy.AIUsageLog).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
            db.commit()

    # 1. The AI's wording is matched to the school's own knowledge name.
    hid = make_help(client, sh)
    replies.append(sol(kp=known + "（应用）"))
    assert client.post(f"/student/homework/help/{hid}/solve", headers=sh).status_code == 200
    first = rows()
    assert len(first) == 1 and first[0]["help_id"] == hid and first[0]["student_id"] == sid and first[0]["school_id"] == school_id
    assert first[0]["knowledge_key"] == known and first[0]["matched"] in (True, 1) and first[0]["grade"] == 3
    assert "苹果" in first[0]["question_excerpt"] and "13812345678" not in first[0]["question_excerpt"]  # permanent: no contact details

    # 2. Asking for the same answer again never adds a second row.
    client.post(f"/student/homework/help/{hid}/solve", headers=sh)
    assert len(rows()) == 1

    # 3. A phrase that matches nothing is kept as written and marked unmatched.
    age_everything()
    hid2 = make_help(client, sh, text="3+4=?")
    replies.append(sol(answer="7", expression="3+4", steps=("3 加 4",), kp="完全无关的奇怪说法"))
    client.post(f"/student/homework/help/{hid2}/solve", headers=sh)
    second = rows()[1]
    assert second["matched"] in (False, 0) and second["knowledge_key"] == "完全无关的奇怪说法" and second["subject"] == ""

    # 4. A question the AI got wrong twice (withheld, sent to the teacher) is still a knowledge record.
    age_everything()
    hid3 = make_help(client, sh, text="12-5=?")
    replies.extend([sol(answer="8", kp=known), sol(answer="9", kp=known)])
    r3 = client.post(f"/student/homework/help/{hid3}/solve", headers=sh).json()
    assert r3["state"] == "escalated"
    third = rows()[2]
    assert third["verify_status"] == "mismatch" and third["knowledge_key"] == known

    # 5. The record outlives the conversation: purging the help request keeps it.
    with legacy.SessionLocal() as db:
        db.execute(legacy.Base.metadata.tables["help_requests"].delete())
        db.commit()
    assert len(rows()) == 3

    # 6. A failed AI call leaves no record.
    age_everything()
    hid4 = make_help(client, sh, text="1+1=?")
    replies.append(HTTPException(503, "down"))
    assert client.post(f"/student/homework/help/{hid4}/solve", headers=sh).status_code == 503
    assert len(rows()) == 3
print("OK")
''',
    )


def test_knowledge_matching_prefers_the_school_name_and_refuses_weak_matches():
    from changying.services.homework_knowledge import match_knowledge

    names = [("数学", "小数乘法"), ("数学", "分数加减法"), ("数学", "三角形的面积")]
    assert match_knowledge("小数乘法", names) == ("数学", "小数乘法")
    assert match_knowledge("小数乘法（积的小数位数）", names) == ("数学", "小数乘法")
    assert match_knowledge("分数的加减", names) == ("数学", "分数加减法")
    assert match_knowledge("古诗词鉴赏", names) is None
    assert match_knowledge("", names) is None and match_knowledge("小数乘法", []) is None
