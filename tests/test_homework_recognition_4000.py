from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_KEYS = (
    "HOMEWORK_ASSISTANT",
    "HOMEWORK_VISION_PROVIDER",
    "HOMEWORK_VISION_BASE_URL",
    "HOMEWORK_VISION_MODEL",
    "HOMEWORK_VISION_API_KEY",
    "HOMEWORK_STUDENT_DAILY_LIMIT",
    "HOMEWORK_SCHOOL_HOURLY_LIMIT",
    "HOMEWORK_AI_CONCURRENCY",
)


def run_isolated(tmp_path: Path, script: str, extra_env: dict[str, str] | None = None) -> str:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'recognition_4000.sqlite3'}",
        "PYTHONPATH": str(ROOT),
        "PYTHONUTF8": "1",
    }
    for key in ENV_KEYS:
        env.pop(key, None)
    env.update({
        "HOMEWORK_ASSISTANT": "1",
        "HOMEWORK_VISION_PROVIDER": "openai_compatible",
        "HOMEWORK_VISION_BASE_URL": "https://api.deepseek.com",
        "HOMEWORK_VISION_MODEL": "vision-test-model",
        "HOMEWORK_VISION_API_KEY": "test-key-not-real",
        **(extra_env or {}),
    })
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=env, text=True, capture_output=True, timeout=240
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout, result.stdout
    return result.stdout


COMMON = r'''
import base64
import json
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, update

import app_v924 as legacy
from app import app
from changying.services import homework_vision
from changying.web import weekend_precheck as wp

legacy._validate_ai_base_url = lambda base, runtime=False: base
legacy._ai_rate_check = lambda db, school_id: None

JPEG = b"\xff\xd8\xff\xe0" + b"img-bytes-" * 20
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5WQAAAAASUVORK5CYII="
)


def login_and_change(client, username, old_password, new_password):
    login = client.post("/login", json={"username": username, "password": old_password, "remember": False})
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    changed = client.post(
        "/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": old_password, "new_password": new_password, "remember": False},
    )
    assert changed.status_code == 200, changed.text
    return changed.json()["token"]


def setup(client):
    th = {"Authorization": "Bearer " + login_and_change(client, "teacher1", "123456", "Teacher1234")}
    sh = {"Authorization": "Bearer " + login_and_change(client, "student1", "123456", "Student1234")}
    session = client.get("/session", headers=sh).json()
    student_id = session["userID"]
    with legacy.SessionLocal() as db:
        school_id = db.get(legacy.User, student_id).school_id
        row = legacy.ai_config_for(db, school_id, True)
        row.enabled = True
        row.allow_student_data = True
        row.provider = "openai_compatible"
        row.base_url = "https://api.deepseek.com"
        row.model = "text-model"
        db.commit()
    return th, sh, student_id, school_id
'''


def test_chain1_teacher_notice_4000_boundary_and_recovery(tmp_path: Path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
vision_out = {"content": ""}
vision_calls = []


class FakeVisionResp:
    ok = True
    status_code = 200

    def json(self):
        return {
            "choices": [{"message": {"content": vision_out["content"]}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 50},
        }


def fake_post(url, headers=None, json=None, timeout=None):
    vision_calls.append(url)
    if isinstance(vision_out["content"], Exception):
        raise vision_out["content"]
    return FakeVisionResp()


homework_vision.requests.post = fake_post

parse_prompts = []
parse_replies = []


def fake_ai(db, u, feature, prompt, images=None, timeout=90, **kw):
    parse_prompts.append(prompt)
    reply = parse_replies.pop(0)
    if isinstance(reply, Exception):
        raise reply
    return reply


legacy._ai_call = fake_ai
valid_notice = json.dumps({
    "groupLabel": "实验小学 三(2)班",
    "items": [{"subject": "数学", "content": "口算第5页", "page": "P5", "requirement": "签字"}],
}, ensure_ascii=False)

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    # 1) /teacher/homework/parse-image 3999 / 4000 / 4001 boundary + explicit truncation warning + half-JSON rejection
    for n, exp_len, exp_trunc in [(3999, 3999, False), (4000, 4000, True), (4001, 4000, True)]:
        vision_out["content"] = json.dumps({"text": "甲" * n, "hasFigure": False, "confidence": 0.95}, ensure_ascii=False)
        r = client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"}, content=JPEG)
        assert r.status_code == 200, (n, r.text)
        body = r.json()
        assert len(body["text"]) == exp_len, (n, len(body["text"]))
        assert body["truncated"] is exp_trunc, (n, body)
        if exp_trunc:
            assert "可能不完整，请核对" in body["warning"], body
        else:
            assert body["warning"] == "", body

    vision_out["content"] = '{"text": "半截JSON通知未闭合'
    half_img = client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"}, content=JPEG)
    assert half_img.status_code == 502 and "半截JSON" not in half_img.text

    # 模型直接回纯文本（不是 JSON）：仍然当草稿收下，不能因为格式判定把老师挡在 502
    vision_out["content"] = "作业：数学口算第 5 页，家长签字"
    plain = client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"}, content=JPEG)
    assert plain.status_code == 200, plain.text
    plain_body = plain.json()
    assert "口算第 5 页" in plain_body["text"], plain_body
    assert plain_body["truncated"] is False and plain_body["warning"] == "", plain_body

    # 2) /teacher/homework/parse 3999 / 4000 / 4001 / 6000 / 6001 boundary
    notices_tbl = legacy.Base.metadata.tables["homework_notices"]
    for n in (3999, 4000, 4001, 6000):
        parse_replies.append(valid_notice)
        txt = "乙" * n
        r = client.post("/teacher/homework/parse", headers=th, json={"text": txt})
        assert r.status_code == 200, (n, r.text)
        assert txt in parse_prompts[-1], f"prompt should contain all {n} chars"
        nid = r.json()["id"]
        with legacy.SessionLocal() as db:
            saved_raw = db.scalar(select(notices_tbl.c.raw_text).where(notices_tbl.c.id == nid))
            assert len(saved_raw) == n, (n, len(saved_raw))

    too_long = client.post("/teacher/homework/parse", headers=th, json={"text": "乙" * 6001})
    assert too_long.status_code == 400 and "6000" in too_long.json()["detail"]

    # 3) Structured output anomalies on /teacher/homework/parse: invalid JSON, half JSON, missing items, overlong fields
    for bad_out in (
        "not json at all",
        '{"groupLabel": "三(2)班", "items": [{"subject": "数学", "content": "未闭合',
        '{"groupLabel": "三(2)班"}',
        '{"groupLabel": "三(2)班", "items": [{"subject": "数学", "content": "   "}]}',
    ):
        parse_replies.append(bad_out)
        r = client.post("/teacher/homework/parse", headers=th, json={"text": "明天数学口算第5页"})
        assert r.status_code == 422 and "手动" in r.json()["detail"], (bad_out, r.status_code, r.text)

    # Overlong fields in model output are clipped safely (groupLabel<=120, content<=300, items<=30)
    overlong_out = json.dumps({
        "groupLabel": "班" * 200,
        "items": [{"subject": "数" * 50, "content": "题" * 500, "page": "P" * 80, "requirement": "要" * 300} for _ in range(40)],
    }, ensure_ascii=False)
    parse_replies.append(overlong_out)
    r = client.post("/teacher/homework/parse", headers=th, json={"text": "明天数学口算"})
    assert r.status_code == 200
    parsed_body = r.json()
    assert len(parsed_body["groupLabel"]) == 120
    assert len(parsed_body["items"]) == 30
    assert len(parsed_body["items"][0]["content"]) == 300

    # 4) Failure & retry: single call, clear message, no infinite retry
    before_calls = len(parse_prompts)
    parse_replies.append(HTTPException(504, "AI 调用超时，请稍后重试"))
    fail = client.post("/teacher/homework/parse", headers=th, json={"text": "明天数学口算"})
    assert fail.status_code == 504 and len(parse_prompts) == before_calls + 1

    import requests as req_mod
    before_v = len(vision_calls)
    vision_out["content"] = req_mod.Timeout()
    vfail = client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"}, content=JPEG)
    assert vfail.status_code == 504 and len(vision_calls) == before_v + 1
print("OK")
''',
    )


def test_chain2_student_help_4000_boundary_and_downstream(tmp_path: Path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
vision_text = {"value": ""}


class FakeVisionResp:
    ok = True
    status_code = 200

    def json(self):
        return {
            "choices": [{"message": {"content": json.dumps({"text": vision_text["value"], "hasFigure": False, "confidence": 0.92}, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 40},
        }


homework_vision.requests.post = lambda url, headers=None, json=None, timeout=None: FakeVisionResp()

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    # 1) /student/homework/recognize at 3999 / 4000 / 4001 chars + truncation flag/warning
    for n, exp_len, exp_trunc in [(3999, 3999, False), (4000, 4000, True), (4001, 4000, True)]:
        vision_text["value"] = "题" * n
        r = client.post("/student/homework/recognize", headers={**sh, "Content-Type": "image/jpeg"}, content=JPEG)
        assert r.status_code == 200, (n, r.text)
        body = r.json()
        assert len(body["text"]) == exp_len, (n, len(body["text"]))
        assert body["truncated"] is exp_trunc, (n, body)
        if exp_trunc:
            assert "可能不完整，请核对" in body["warning"], body
        else:
            assert body["warning"] == "", body
        # Downstream /student/homework/help enforces MAX_QUESTION_CHARS = 1000:
        # passing 3999 or 4000 chars from recognize into /student/homework/help is rejected with 400!
        downstream = client.post("/student/homework/help", headers=sh, json={"questionText": body["text"], "grade": 3})
        assert downstream.status_code == 400 and "1000" in downstream.json()["detail"], (n, downstream.status_code, downstream.text)

    # 2) /student/homework/help boundary at 1000 vs 1001 chars
    ok_1000 = client.post("/student/homework/help", headers=sh, json={"questionText": "算" * 1000, "grade": 3})
    assert ok_1000.status_code == 200 and len(ok_1000.json()["questionText"]) == 1000
    bad_1001 = client.post("/student/homework/help", headers=sh, json={"questionText": "算" * 1001, "grade": 3})
    assert bad_1001.status_code == 400 and "1000" in bad_1001.json()["detail"]
print("OK")
''',
        {"HOMEWORK_STUDENT_DAILY_LIMIT": "50"},
    )


def test_chain2_student_solve_structured_output_and_retry_recovery(tmp_path: Path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
calls = []
replies = []


def fake_ai(db, u, feature, prompt, images=None, timeout=90, rate_check=None):
    if rate_check:
        rate_check(db, u.school_id)
    calls.append(prompt)
    db.add(legacy.AIUsageLog(school_id=u.school_id, user_id=u.id, feature=feature, provider="p", model="m", status="ok"))
    db.commit()
    reply = replies.pop(0)
    if isinstance(reply, Exception):
        raise reply
    return reply


legacy._ai_call = fake_ai
helps_tbl = legacy.Base.metadata.tables["help_requests"]

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    created = client.post("/student/homework/help", headers=sh, json={"questionText": "12-5=?", "grade": 3})
    assert created.status_code == 200
    hid = created.json()["id"]

    # 1) Invalid JSON, half-truncated JSON, missing steps, missing answer -> 502, single call, stays 'confirmed', preserves question_text
    for bad_reply in (
        "not json",
        '{"method": "相减", "steps": [{"n": 1, "text": "半截JSON',
        '{"method": "相减", "steps": [], "answer": "7"}',
        '{"method": "相减", "steps": [{"n": 1, "text": "先算12-5"}]}',
    ):
        before = len(calls)
        replies.append(bad_reply)
        r = client.post(f"/student/homework/help/{hid}/solve", headers=sh)
        assert r.status_code == 502 and "再试" in r.json()["detail"], (bad_reply, r.status_code, r.text)
        assert len(calls) == before + 1, "must not loop/retry on malformed JSON"
        with legacy.SessionLocal() as db:
            row = db.execute(select(helps_tbl).where(helps_tbl.c.id == hid)).first()._mapping
            assert row["state"] == "confirmed" and row["question_text"] == "12-5=?"

    # 2) Model call failure (timeout 504) -> single call, reverts to 'confirmed', preserves question_text
    before = len(calls)
    replies.append(HTTPException(504, "AI 调用超时，请稍后重试"))
    fail = client.post(f"/student/homework/help/{hid}/solve", headers=sh)
    assert fail.status_code == 504 and len(calls) == before + 1
    with legacy.SessionLocal() as db:
        row = db.execute(select(helps_tbl).where(helps_tbl.c.id == hid)).first()._mapping
        assert row["state"] == "confirmed" and row["question_text"] == "12-5=?"

    # 3) Overlong fields in valid structured output are clipped (steps<=12, step.text<=400, method<=40, answer<=120)
    overlong_sol = json.dumps({
        "method": "法" * 100,
        "steps": [{"n": i + 1, "text": "步" * 600} for i in range(20)],
        "answer": "7",
        "expression": "12-5",
        "knowledgePoint": "点" * 100,
    }, ensure_ascii=False)
    replies.append(overlong_sol)
    ok = client.post(f"/student/homework/help/{hid}/solve", headers=sh)
    assert ok.status_code == 200
    sol = ok.json()["solution"]
    assert len(sol["method"]) == 40
    assert len(sol["steps"]) == 12
    assert len(sol["steps"][0]["text"]) == 400
print("OK")
''',
        {"HOMEWORK_STUDENT_DAILY_LIMIT": "50"},
    )


def test_chain3_written_precheck_4000_boundary_and_recovery(tmp_path: Path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
ocr_out = {"text": "", "confidence": 0.98}
ocr_calls = []


def fake_ocr(impl, db, user, image, **kw):
    ocr_calls.append(kw)
    if isinstance(ocr_out["text"], Exception):
        raise ocr_out["text"]
    # Simulate recognize_image's 4000-char slice + truncated flag on the returned text field
    raw_text = str(ocr_out["text"] or "").strip()
    truncated = len(raw_text) >= homework_vision.RECOGNIZED_CHAR_LIMIT
    return {
        "text": raw_text[:homework_vision.RECOGNIZED_CHAR_LIMIT],
        "hasFigure": False,
        "confidence": ocr_out["confidence"],
        "truncated": truncated,
        "warning": "识别内容已达 4000 字上限，可能不完整，请核对" if truncated else "",
    }


wp.vision_enabled = lambda: True
wp.recognize_image = fake_ocr

with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        lesson = legacy.TeachingLesson(
            school_id=school_id, program_id=p.id, subject="数学", lesson_no=94, title="4000边界测试", core_target="代数式"
        )
        db.add(lesson)
        db.flush()
        lid = lesson.id
        tid = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id))
        cls.teacher_id = tid
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == student_id))
        if link:
            link.class_id = cls.id
        else:
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=student_id))
        db.commit()

    sid = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()["id"]
    base = f"/teacher/weekend/sessions/{sid}/written"
    qid_photo = client.post(base + "/questions", headers=th, json={"stem": "a×1.5简写成（）。", "reference": "1.5a"}).json()["id"]
    qid_text = client.post(base + "/questions", headers=th, json={"stem": "12-5=（）", "reference": "7"}).json()["id"]
    client.post(f"/teacher/weekend/sessions/{sid}/start", headers=th)
    client.post(f"/teacher/weekend/sessions/{sid}/goto", headers=th,json={"stage": 4})

    # 1) Typed answer 3999 / 4000 / 4001 boundary on /student/weekend/sessions/{sid}/written/{qid}
    r_4001 = client.post(f"/student/weekend/sessions/{sid}/written/{qid_text}", headers=sh, data={"text": "7" * 4001})
    assert r_4001.status_code == 400 and "4000" in r_4001.json()["detail"]

    r_3999 = client.post(f"/student/weekend/sessions/{sid}/written/{qid_text}", headers=sh, data={"text": "7" * 3999})
    assert r_3999.status_code == 200 and len(r_3999.json()["submission"]["text"]) == 3999

    r_4000 = client.post(
        f"/student/weekend/sessions/{sid}/written/{qid_text}", headers=sh, data={"text": "8" * 4000, "revision": 1}
    )
    assert r_4000.status_code == 200 and len(r_4000.json()["submission"]["text"]) == 4000

    # 2) Photo OCR precheck at 3999 / 4000 / 4001 chars of inner transcription JSON
    def make_inner_json(target_len: int) -> str:
        shell = '{"items":[{"key":"1","question":"__Q__","answers":["1.5a"],"confidence":0.98}]}'
        pad = target_len - (len(shell) - len("__Q__"))
        assert pad > 0
        out = shell.replace("__Q__", "甲" * pad)
        assert len(out) == target_len
        return out

    ocr_out["text"] = make_inner_json(3999)
    sub = client.post(
        f"/student/weekend/sessions/{sid}/written/{qid_photo}",
        headers=sh,
        files={"photo": ("answer.png", PNG, "image/png")},
    )
    assert sub.status_code == 200
    item_3999 = next(i for i in client.get(base, headers=th).json()["items"] if i["questionId"] == qid_photo)
    aid = item_3999["id"]
    assert item_3999["precheck"]["status"] == "manual"
    assert len(item_3999["precheck"]["items"][0]["observedQuestion"]) > 3900

    subs_tbl = legacy.Base.metadata.tables["weekend_written_submissions"]

    # 4000 chars inner JSON -> reaches 4000-char ceiling, marked truncated=True and manual review
    with legacy.SessionLocal() as db:
        db.execute(update(subs_tbl).where(subs_tbl.c.id == aid).values(revision=10, result="pending"))
        db.commit()
    ocr_out["text"] = make_inner_json(4000)
    assert client.post(base + f"/{aid}/precheck", headers=th, json={"revision": 10, "retry": True}).status_code == 200
    item_4000 = next(i for i in client.get(base, headers=th).json()["items"] if i["id"] == aid)
    assert item_4000["result"] == "pending"
    assert item_4000["precheck"]["status"] == "manual"
    assert item_4000["precheck"]["truncated"] is True
    assert item_4000["precheck"]["suggestedResult"] is None
    assert "可能不完整，请老师核对" in item_4000["precheck"]["message"]

    # 4001 chars inner JSON -> sliced at 4000 -> broken JSON -> invalid_transcription + truncated warning, formal answer stays pending
    with legacy.SessionLocal() as db:
        db.execute(update(subs_tbl).where(subs_tbl.c.id == aid).values(revision=11, result="pending"))
        db.commit()
    ocr_out["text"] = make_inner_json(4001)
    before_ocr = len(ocr_calls)
    assert client.post(base + f"/{aid}/precheck", headers=th, json={"revision": 11, "retry": True}).status_code == 200
    assert len(ocr_calls) == before_ocr + 1, "must not retry automatically on truncated/invalid transcription"
    item_4001 = next(i for i in client.get(base, headers=th).json()["items"] if i["id"] == aid)
    assert item_4001["result"] == "pending" and item_4001["hasPhoto"] is True
    assert item_4001["precheck"]["status"] == "failed"
    assert item_4001["precheck"]["code"] == "invalid_transcription"
    assert item_4001["precheck"]["truncated"] is True
    assert "可能不完整，请核对" in item_4001["precheck"]["message"]
    assert item_4001["precheck"]["suggestedResult"] is None

    # 3) Timeout / failure -> single call, status='failed', code='timeout', original submission untouched
    with legacy.SessionLocal() as db:
        db.execute(update(subs_tbl).where(subs_tbl.c.id == aid).values(revision=12, result="pending"))
        db.commit()
    ocr_out["text"] = wp.VisionFailure(504, "识别服务响应超时", "timeout")
    before_ocr = len(ocr_calls)
    assert client.post(base + f"/{aid}/precheck", headers=th, json={"revision": 12, "retry": True}).status_code == 200
    assert len(ocr_calls) == before_ocr + 1
    item_timeout = next(i for i in client.get(base, headers=th).json()["items"] if i["id"] == aid)
    assert item_timeout["result"] == "pending" and item_timeout["precheck"]["code"] == "timeout"
print("OK")
''',
    )


def test_three_chains_roles_and_permissions(tmp_path: Path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    # 1) Unauthenticated -> 401
    for method, path, kwargs in [
        ("post", "/teacher/homework/parse", {"json": {"text": "数学第5页"}}),
        ("post", "/teacher/homework/parse-image", {"content": JPEG, "headers": {"Content-Type": "image/jpeg"}}),
        ("post", "/student/homework/recognize", {"content": JPEG, "headers": {"Content-Type": "image/jpeg"}}),
        ("post", "/student/homework/help", {"json": {"questionText": "1+1=?", "grade": 3}}),
        ("post", "/student/homework/help/1/solve", {}),
        ("get", "/teacher/weekend/sessions/1/written/1/precheck?revision=1", {}),
        ("post", "/teacher/weekend/sessions/1/written/1/precheck", {"json": {"revision": 1}}),
    ]:
        r = getattr(client, method)(path, **kwargs)
        assert r.status_code in (401, 403), (path, r.status_code, r.text)

    # 2) Student cannot call teacher endpoints -> 403
    assert client.post("/teacher/homework/parse", headers=sh, json={"text": "数学第5页"}).status_code == 403
    assert client.post(
        "/teacher/homework/parse-image", headers={**sh, "Content-Type": "image/jpeg"}, content=JPEG
    ).status_code == 403
    assert client.get("/teacher/weekend/sessions/1/written/1/precheck?revision=1", headers=sh).status_code == 403
    assert client.post(
        "/teacher/weekend/sessions/1/written/1/precheck", headers=sh, json={"revision": 1}
    ).status_code == 403
    assert client.post(
        "/teacher/weekend/sessions/1/written/1/precheck/transcription",
        headers=sh,
        json={"revision": 1, "token": "t", "items": []},
    ).status_code == 403

    # 3) Teacher cannot call student endpoints -> 403
    assert client.post(
        "/student/homework/recognize", headers={**th, "Content-Type": "image/jpeg"}, content=JPEG
    ).status_code == 403
    assert client.post("/student/homework/help", headers=th, json={"questionText": "1+1=?", "grade": 3}).status_code == 403
    assert client.post("/student/homework/help/1/solve", headers=th).status_code == 403
    assert client.post("/student/weekend/sessions/1/written/1", headers=th, data={"text": "1"}).status_code == 403
print("OK")
''',
    )
