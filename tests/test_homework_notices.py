from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_isolated(tmp_path, script: str, extra_env: dict[str, str] | None = None) -> str:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'homework.sqlite3'}",
        "PYTHONPATH": str(ROOT),
        **(extra_env or {}),
    }
    for key in ("HOMEWORK_ASSISTANT", "HOMEWORK_VISION_PROVIDER", "HOMEWORK_VISION_BASE_URL",
                "HOMEWORK_VISION_MODEL", "HOMEWORK_VISION_API_KEY"):
        if key not in (extra_env or {}):
            env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=env, text=True, capture_output=True, timeout=240
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout, result.stdout
    return result.stdout


COMMON = r'''
import json

from fastapi.testclient import TestClient

import app_v924 as legacy
from app import app


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


def allow_ai(school_id, allow=True, enabled=True):
    with legacy.SessionLocal() as db:
        row = legacy.ai_config_for(db, school_id, True)
        row.enabled = enabled
        row.allow_student_data = allow
        row.provider = "openai_compatible"
        row.base_url = "https://api.deepseek.com"
        row.model = "text-model"
        db.commit()


def school_of(student_id):
    with legacy.SessionLocal() as db:
        return db.get(legacy.User, student_id).school_id


def teacher_student_headers(client):
    th = {"Authorization": "Bearer " + login_and_change(client, "teacher1", "123456", "Teacher1234")}
    sh = {"Authorization": "Bearer " + login_and_change(client, "student1", "123456", "Student1234")}
    return th, sh, client.get("/session", headers=sh).json()["userID"]


NOTICE_JSON = json.dumps({
    "groupLabel": "实验小学 三(2)班",
    "items": [
        {"subject": "数学", "content": "口算题卡第5页", "page": "P5", "requirement": "家长签字"},
        {"subject": "语文", "content": "背诵《静夜思》", "page": "", "requirement": ""},
    ],
}, ensure_ascii=False)
'''


def test_everything_is_404_when_the_flag_is_off(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    for method, path, headers in [
        ("get", "/homework/config", {}),
        ("get", "/v1/homework", {}),
        ("get", "/teacher/homework/students", th),
        ("get", "/teacher/homework/notices", th),
        ("post", "/teacher/homework/parse", th),
        ("post", "/teacher/homework/parse-image", th),
        ("post", "/teacher/homework/notices", th),
        ("get", "/student/homework/today", sh),
    ]:
        r = getattr(client, method)(path, headers=headers)
        assert r.status_code == 404, (path, r.status_code, r.text)
    # Without the flag the shell link never shows up either (the script asks /homework/config).
    assert client.get("/homework/config").status_code == 404
print("OK")
''',
    )


def test_teacher_imports_confirms_publishes_and_student_ticks_items(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
prompts = []


def fake_ai(db, u, feature, prompt, images=None, timeout=90, **kw):
    prompts.append((feature, prompt))
    return NOTICE_JSON


legacy._ai_call = fake_ai

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)

    assert client.get("/homework/config").status_code == 200

    # Students cannot use the teacher side and teachers cannot use the student side.
    assert client.get("/teacher/homework/students", headers=sh).status_code == 403
    assert client.get("/student/homework/today", headers=th).status_code == 403

    students = client.get("/teacher/homework/students", headers=th).json()
    assert sid in [s["id"] for s in students]

    pasted = "各位家长好，明天作业：口算题卡第5页。有事请联系 13812345678 或 123456789012。"
    parsed = client.post("/teacher/homework/parse", headers=th, json={"text": pasted})
    assert parsed.status_code == 200, parsed.text
    notice = parsed.json()
    assert notice["status"] == "draft" and len(notice["items"]) == 2
    assert notice["groupLabel"] == "实验小学 三(2)班"
    assert [i["seq"] for i in notice["items"]] == [1, 2]

    # Only the (scrubbed) notice text went to the model: no names, ids, school or account data.
    feature, prompt = prompts[-1]
    assert feature == "homework_parse"
    assert "口算题卡第5页" in prompt
    assert "13812345678" not in prompt and "123456789012" not in prompt
    for secret in ("王老师", "teacher1", "小明", "student1", "Teacher1234", "三年级一班"):
        assert secret not in prompt, secret

    # A draft is invisible to the student.
    assert client.get("/student/homework/today", headers=sh).json() == []

    # The teacher edits (drops the second item) and publishes to the selected student.
    edited = client.put(
        f"/teacher/homework/notices/{notice['id']}",
        headers=th,
        json={"groupLabel": "实验小学 三(2)班", "items": notice["items"][:1]},
    )
    assert edited.status_code == 200 and len(edited.json()["items"]) == 1
    published = client.post(
        f"/teacher/homework/notices/{notice['id']}/publish", headers=th, json={"studentIDs": [sid]}
    )
    assert published.status_code == 200 and published.json()["recipients"] == 1
    # Items of a published list can no longer be edited; publishing again is harmless.
    again = client.put(f"/teacher/homework/notices/{notice['id']}", headers=th, json={"items": notice["items"]})
    assert again.status_code == 409
    assert client.post(
        f"/teacher/homework/notices/{notice['id']}/publish", headers=th, json={"studentIDs": [sid]}
    ).json()["recipients"] == 1

    today = client.get("/student/homework/today", headers=sh).json()
    assert len(today) == 1 and today[0]["items"][0]["content"] == "口算题卡第5页"
    assert today[0]["items"][0]["done"] is False

    tick = client.post(f"/student/homework/items/{notice['id']}/1/done", headers=sh, json={"done": True})
    assert tick.status_code == 200
    assert client.get("/student/homework/today", headers=sh).json()[0]["items"][0]["done"] is True
    assert client.post(f"/student/homework/items/{notice['id']}/9/done", headers=sh, json={"done": True}).status_code == 404

    detail = client.get(f"/teacher/homework/notices/{notice['id']}", headers=th).json()
    assert detail["recipients"][0]["done"] == [1]
    listing = client.get("/teacher/homework/notices", headers=th).json()
    assert listing[0]["doneCount"] == 1 and listing[0]["totalCount"] == 1

    # Raw pasted text is cleared once published.
    from sqlalchemy import select
    tbl = legacy.Base.metadata.tables["homework_notices"]
    with legacy.SessionLocal() as db:
        assert db.scalar(select(tbl.c.raw_text).where(tbl.c.id == notice["id"])) == ""
print("OK")
''',
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_publish_is_limited_to_own_students_and_manual_entry_works(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
legacy._ai_call = lambda *a, **k: "not json at all"

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)

    # A model answer that is not usable asks the teacher to type the list by hand.
    bad = client.post("/teacher/homework/parse", headers=th, json={"text": "明天作业：略"})
    assert bad.status_code == 422 and "手动" in bad.json()["detail"]
    assert client.post("/teacher/homework/parse", headers=th, json={"text": "   "}).status_code == 400

    manual = client.post(
        "/teacher/homework/notices", headers=th,
        json={"groupLabel": "", "items": [{"subject": "数学", "content": "练习册第3页"}]},
    )
    assert manual.status_code == 200
    nid = manual.json()["id"]
    assert client.post("/teacher/homework/notices", headers=th, json={"items": []}).status_code == 400

    # A student who is not in one of this teacher's classes cannot be assigned.
    with legacy.SessionLocal() as db:
        school_id = db.get(legacy.User, sid).school_id
        stranger = legacy.User(school_id=school_id, username="stranger1", password_hash=legacy.hash_password("x"),
                               name="外班同学", role="student", grade=3)
        db.add(stranger); db.commit(); stranger_id = stranger.id
    r = client.post(f"/teacher/homework/notices/{nid}/publish", headers=th, json={"studentIDs": [sid, stranger_id]})
    assert r.status_code == 403
    assert client.post(f"/teacher/homework/notices/{nid}/publish", headers=th, json={"studentIDs": []}).status_code == 400
    assert client.get("/student/homework/today", headers=sh).json() == []

    # Unknown notice ids are 404 for everyone.
    assert client.get("/teacher/homework/notices/99999", headers=th).status_code == 404
    assert client.post("/teacher/homework/notices/99999/publish", headers=th, json={"studentIDs": [sid]}).status_code == 404
print("OK")
''',
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_old_draft_text_is_purged_lazily(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
from datetime import datetime, timedelta
from sqlalchemy import select, update

legacy._ai_call = lambda *a, **k: NOTICE_JSON

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    nid = client.post("/teacher/homework/parse", headers=th, json={"text": "明天作业：略"}).json()["id"]
    tbl = legacy.Base.metadata.tables["homework_notices"]
    with legacy.SessionLocal() as db:
        assert db.scalar(select(tbl.c.raw_text).where(tbl.c.id == nid)) != ""
        db.execute(update(tbl).where(tbl.c.id == nid).values(created_at=datetime.utcnow() - timedelta(days=8)))
        db.commit()
    assert client.get("/teacher/homework/notices", headers=th).status_code == 200
    with legacy.SessionLocal() as db:
        assert db.scalar(select(tbl.c.raw_text).where(tbl.c.id == nid)) == ""
print("OK")
''',
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_prompt_helpers_scrub_and_clean():
    from changying.services.homework_prompts import (
        build_parse_prompt,
        clean_items,
        clean_parse_result,
        scrub_notice_text,
    )

    text = scrub_notice_text("联系 13812345678，邮箱 a.b@x.com，群 https://x.cn/a?b=1，学号 2023001122")
    for hidden in ("13812345678", "a.b@x.com", "https://x.cn", "2023001122"):
        assert hidden not in text
    assert "第5页" in build_parse_prompt("口算第5页")
    items = clean_items([{"content": "  a  b ", "subject": "数学"}, {"content": ""}, "x", {"content": "c" * 999}])
    assert [i["seq"] for i in items] == [1, 2] and items[0]["content"] == "a b" and len(items[1]["content"]) == 300
    assert len(clean_items([{"content": str(n)} for n in range(99)])) == 30
    assert clean_parse_result("nope") == {"groupLabel": "", "items": []}


def test_page_is_served_when_on_and_never_uses_innerhtml(tmp_path):
    run_isolated(
        tmp_path,
        r'''
from fastapi.testclient import TestClient
from app import app
import app_v924 as legacy
import changying.web.v1 as v1_module

with TestClient(app) as client:
    page = client.get("/v1/homework")
    assert page.status_code == 200 and "晚托作业助手" in page.text
    assert "innerHTML" not in page.text and "eval(" not in page.text
    assert "no-cache" in page.headers["cache-control"]
    html = v1_module.v1_html()
    assert html.count("changying_homework_assistant_entry_v1") == 1
    assert "/homework/config" in html
print("OK")
''',
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_vision_uses_the_exact_configured_model_and_never_keeps_the_image(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
import base64
from pathlib import Path

import requests

from changying.services import homework_vision

MODEL = "deepseek-v4-flash-vision-exp"
captured = {}


class FakeResponse:
    ok = True
    status_code = 200

    def json(self):
        return {
            "choices": [{"message": {"content": json.dumps({"text": "通知：数学第5页，电话 13812345678", "hasFigure": False, "confidence": 0.9}, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 40},
        }


def fake_post(url, headers=None, json=None, timeout=None):
    captured.update(url=url, headers=headers, payload=json, timeout=timeout)
    return FakeResponse()


homework_vision.requests.post = fake_post
legacy._ai_rate_check = lambda db, school_id: None
legacy._validate_ai_base_url = lambda base, runtime=False: base  # no DNS in the sandbox

# The legacy alias table is untouched: it still rewrites these names for the *text* models.
assert legacy.AI_DEEPSEEK_LEGACY_MODEL_ALIASES == {
    "deepseek-v4-flash": "deepseek-flash",
    "deepseek-v4-flash-vision-exp": "deepseek-flash",
}
assert legacy._ai_effective_model("openai_compatible", "https://api.deepseek.com", MODEL) == "deepseek-flash"

MARKER = b"UNIQUE-IMAGE-MARKER-0123456789"
jpeg = b"\xff\xd8\xff\xe0" + MARKER * 20

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    allow_ai(school_of(sid))

    # Not configured: clear message, nothing is sent anywhere.
    r = client.post("/teacher/homework/parse-image", headers=th, files={"file": ("n.jpg", jpeg, "image/jpeg")})
    assert r.status_code == 503 and not captured

    import os
    os.environ.update({
        "HOMEWORK_VISION_PROVIDER": "openai_compatible",
        "HOMEWORK_VISION_BASE_URL": "https://api.deepseek.com",
        "HOMEWORK_VISION_MODEL": MODEL,
        "HOMEWORK_VISION_API_KEY": "test-key-not-real",
    })
    assert client.get("/homework/config").json()["visionEnabled"] is True

    ok = client.post("/teacher/homework/parse-image", headers=th, files={"file": ("n.jpg", jpeg, "image/jpeg")})
    assert ok.status_code == 200, ok.text
    assert "13812345678" not in ok.json()["text"] and "数学第5页" in ok.json()["text"]
    # The model name is sent exactly as configured, the key only in the header.
    assert captured["payload"]["model"] == MODEL
    assert captured["headers"]["Authorization"] == "Bearer test-key-not-real"
    assert "test-key-not-real" not in json.dumps(captured["payload"])

    # Bad inputs.
    assert client.post("/teacher/homework/parse-image", headers=th, files={"file": ("n.gif", b"GIF89a....", "image/gif")}).status_code == 415
    big = b"\xff\xd8\xff" + b"0" * (homework_vision.MAX_IMAGE_BYTES + 10)
    assert client.post("/teacher/homework/parse-image", headers=th, files={"file": ("b.jpg", big, "image/jpeg")}).status_code == 413
    assert client.post("/teacher/homework/parse-image", headers=sh, files={"file": ("n.jpg", jpeg, "image/jpeg")}).status_code == 403

    # Only metadata is logged; the image bytes appear nowhere in the database file.
    from sqlalchemy import select
    with legacy.SessionLocal() as db:
        rows = db.scalars(select(legacy.AIUsageLog).where(legacy.AIUsageLog.feature == "homework_parse_vision")).all()
        assert len(rows) == 1 and rows[0].model == MODEL and rows[0].input_tokens == 120
        assert rows[0].error == "" and rows[0].prompt_chars > 0
    legacy.engine.dispose()
    raw = Path(legacy.engine.url.database).read_bytes()
    assert MARKER not in raw and base64.b64encode(MARKER) not in raw
print("OK")
''',
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_vision_failures_are_friendly_and_do_not_leak_the_key(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
import os

import requests

from changying.services import homework_vision

os.environ.update({
    "HOMEWORK_VISION_BASE_URL": "https://api.deepseek.com",
    "HOMEWORK_VISION_MODEL": "m",
    "HOMEWORK_VISION_API_KEY": "secret-key-xyz",
})
legacy._ai_rate_check = lambda db, school_id: None
legacy._validate_ai_base_url = lambda base, runtime=False: base  # no DNS in the sandbox
jpeg = b"\xff\xd8\xff\xe0" + b"1" * 50


class Bad:
    ok = False
    status_code = 429

    def json(self):
        return {"error": {"code": "rate_limit", "message": "secret-key-xyz is over quota"}}


def boom(*a, **k):
    raise requests.Timeout()


with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    allow_ai(school_of(sid))
    homework_vision.requests.post = lambda *a, **k: Bad()
    r = client.post("/teacher/homework/parse-image", headers=th, files={"file": ("n.jpg", jpeg, "image/jpeg")})
    assert r.status_code == 502 and "secret-key-xyz" not in r.text and "rate_limit" in r.text
    homework_vision.requests.post = boom
    r = client.post("/teacher/homework/parse-image", headers=th, files={"file": ("n.jpg", jpeg, "image/jpeg")})
    assert r.status_code == 504 and "secret-key-xyz" not in r.text
    from sqlalchemy import select
    with legacy.SessionLocal() as db:
        errors = [x.error for x in db.scalars(select(legacy.AIUsageLog)).all()]
        assert all("secret-key-xyz" not in e for e in errors)
print("OK")
''',
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_screenshot_is_only_sent_when_the_school_enabled_ai_and_allowed_content_out(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
import os

from changying.services import homework_vision

os.environ.update({
    "HOMEWORK_VISION_BASE_URL": "https://api.deepseek.com",
    "HOMEWORK_VISION_MODEL": "m",
    "HOMEWORK_VISION_API_KEY": "test-key-not-real",
})
legacy._validate_ai_base_url = lambda base, runtime=False: base
legacy._ai_rate_check = lambda db, school_id: None
sent = []


class FakeResponse:
    ok = True
    status_code = 200

    def json(self):
        return {"choices": [{"message": {"content": json.dumps({"text": "数学第5页", "confidence": 0.9}, ensure_ascii=False)}}]}


homework_vision.requests.post = lambda *a, **k: (sent.append(1), FakeResponse())[1]
jpeg = b"\xff\xd8\xff\xe0" + b"1" * 50

def upload(client, th):
    return client.post("/teacher/homework/parse-image", headers=th, files={"file": ("n.jpg", jpeg, "image/jpeg")})

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    school_id = school_of(sid)

    # No AI settings at all, then AI enabled but content not allowed to leave: nothing is sent.
    assert upload(client, th).status_code == 503
    allow_ai(school_id, allow=False, enabled=True)
    refused = upload(client, th)
    assert refused.status_code == 403 and "粘贴文字" in refused.json()["detail"]
    allow_ai(school_id, allow=True, enabled=False)
    assert upload(client, th).status_code == 503
    assert not sent, "no picture may leave the server without the school's permission"

    # Both switched on: it works.
    allow_ai(school_id, allow=True, enabled=True)
    assert upload(client, th).status_code == 200 and len(sent) == 1
print("OK")
''',
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_screenshot_recognition_does_not_block_other_requests(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
import inspect
import os
import threading
import time

from changying.services import homework_vision

os.environ.update({
    "HOMEWORK_VISION_BASE_URL": "https://api.deepseek.com",
    "HOMEWORK_VISION_MODEL": "m",
    "HOMEWORK_VISION_API_KEY": "test-key-not-real",
})
legacy._validate_ai_base_url = lambda base, runtime=False: base
legacy._ai_rate_check = lambda db, school_id: None


class FakeResponse:
    ok = True
    status_code = 200

    def json(self):
        return {"choices": [{"message": {"content": json.dumps({"text": "数学第5页", "confidence": 0.9}, ensure_ascii=False)}}]}


def slow_post(*a, **k):
    time.sleep(1.5)   # a slow recognition service
    return FakeResponse()


homework_vision.requests.post = slow_post
jpeg = b"\xff\xd8\xff\xe0" + b"1" * 50

# The endpoint must not be a coroutine: a coroutine making a blocking call would freeze the whole server.
for route in app.routes:
    if getattr(route, "path", "") == "/teacher/homework/parse-image":
        assert not inspect.iscoroutinefunction(route.endpoint)

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    allow_ai(school_of(sid))
    result = {}

    def upload():
        r = client.post("/teacher/homework/parse-image", headers=th, files={"file": ("n.jpg", jpeg, "image/jpeg")})
        result["status"] = r.status_code

    worker = threading.Thread(target=upload)
    worker.start()
    time.sleep(0.4)                       # the upload is now waiting on the slow service
    started = time.time()
    assert client.get("/homework/config").status_code == 200
    assert time.time() - started < 0.8, "another request had to wait for the recognition call"
    worker.join()
    assert result["status"] == 200
print("OK")
''',
        {"HOMEWORK_ASSISTANT": "1"},
    )
