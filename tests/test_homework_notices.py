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
    allow_ai(school_of(sid))

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
    allow_ai(school_of(sid))

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
    allow_ai(school_of(sid))
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
    assert "changying_homework_assistant_entry_v1" not in html and "cy-homework-entry" not in html  # no floating button
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
    r = client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"}, content=jpeg)
    assert r.status_code == 503 and not captured

    import os
    os.environ.update({
        "HOMEWORK_VISION_PROVIDER": "openai_compatible",
        "HOMEWORK_VISION_BASE_URL": "https://api.deepseek.com",
        "HOMEWORK_VISION_MODEL": MODEL,
        "HOMEWORK_VISION_API_KEY": "test-key-not-real",
    })
    assert client.get("/homework/config").json()["visionEnabled"] is True

    ok = client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"}, content=jpeg)
    assert ok.status_code == 200, ok.text
    assert "13812345678" not in ok.json()["text"] and "数学第5页" in ok.json()["text"]
    # The model name is sent exactly as configured, the key only in the header.
    assert captured["payload"]["model"] == MODEL
    assert captured["headers"]["Authorization"] == "Bearer test-key-not-real"
    assert "test-key-not-real" not in json.dumps(captured["payload"])

    # Bad inputs.
    assert client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"}, content=b"GIF89a....").status_code == 415
    big = b"\xff\xd8\xff" + b"0" * (homework_vision.MAX_IMAGE_BYTES + 10)
    assert client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"}, content=big).status_code == 413
    assert client.post("/teacher/homework/parse-image", headers={**sh, "Content-Type": "image/jpeg"}, content=jpeg).status_code == 403

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
    r = client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"}, content=jpeg)
    assert r.status_code == 502 and "secret-key-xyz" not in r.text and "429" in r.text
    assert "rate_limit" not in r.text  # provider-controlled strings are no longer exposed
    homework_vision.requests.post = boom
    r = client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"}, content=jpeg)
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
    return client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"}, content=jpeg)

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    school_id = school_of(sid)

    # No AI settings at all, then AI enabled but content not allowed to leave: nothing is sent.
    assert upload(client, th).status_code == 503
    allow_ai(school_id, allow=False, enabled=True)
    refused = upload(client, th)
    assert refused.status_code == 403 and "手动录入" in refused.json()["detail"]
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


with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    allow_ai(school_of(sid))
    result = {}

    def upload():
        r = client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"}, content=jpeg)
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


def test_pasted_notice_text_is_only_sent_when_the_school_allowed_content_to_leave(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
sent = []


def fake_ai(db, u, feature, prompt, images=None, timeout=90, **kw):
    sent.append(prompt)
    return NOTICE_JSON


legacy._ai_call = fake_ai

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    school_id = school_of(sid)
    text = {"text": "三(2)班 张小明 家长王女士：明天作业口算题卡第5页"}

    assert client.post("/teacher/homework/parse", headers=th, json=text).status_code == 503      # AI not set up
    allow_ai(school_id, allow=False, enabled=True)
    refused = client.post("/teacher/homework/parse", headers=th, json=text)
    assert refused.status_code == 403 and "手动录入" in refused.json()["detail"]
    allow_ai(school_id, allow=True, enabled=False)
    assert client.post("/teacher/homework/parse", headers=th, json=text).status_code == 503
    assert not sent, "no notice text may reach the AI provider without the school's permission"

    # Typing the list by hand never needs AI.
    assert client.post("/teacher/homework/notices", headers=th, json={"items": [{"content": "口算第5页"}]}).status_code == 200

    allow_ai(school_id, allow=True, enabled=True)
    assert client.post("/teacher/homework/parse", headers=th, json=text).status_code == 200 and len(sent) == 1
print("OK")
''',
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_entry_points_live_in_existing_screens_not_a_floating_button():
    from changying.web.v1_classic_unified_top import inject_v1_classic_unified
    from changying.web.v1_workspace_tabs import patch_v1_workspace_tabs

    shell = patch_v1_workspace_tabs("<html><body></body></html>")
    assert 'data-homework-entry' in shell and "/homework/config" in shell and "page=papers" in shell
    classic = inject_v1_classic_unified("<html><head></head><body><div id=page></div></body></html>")
    assert "cy-hw-band" in classic and "/student/homework/today" in classic
    band = classic.split("cy-hw-band", 1)[1].split("setInterval(ensure,1200)", 1)[0]
    assert "innerHTML" not in band and "POST" not in band  # read-only: ticking items happens on /v1/homework
    assert "cy-homework-entry" not in shell and "cy-homework-entry" not in classic


def test_time_limit_starts_with_the_pupil_and_flags_overtime(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
from datetime import datetime, timedelta
from sqlalchemy import text

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    made = client.post("/teacher/homework/notices", headers=th, json=json.loads(NOTICE_JSON))
    assert made.status_code == 200, made.text
    nid = made.json()["id"]
    pub = client.post(f"/teacher/homework/notices/{nid}/publish", headers=th,
                      json={"studentIDs": [sid], "timeLimitMinutes": 90})
    assert pub.status_code == 200, pub.text

    today = client.get("/student/homework/today", headers=sh).json()[0]
    assert today["timeLimitMinutes"] == 90
    # 未开始时 startedAt 是空字符串（_iso(None)），剩余时间才是 None
    assert not today["startedAt"] and today["remainingSeconds"] is None

    tick = client.post(f"/student/homework/items/{nid}/1/done", headers=sh, json={"done": True})
    assert tick.status_code == 200, tick.text
    after = client.get("/student/homework/today", headers=sh).json()[0]
    assert after["startedAt"] is not None
    assert 0 < after["remainingSeconds"] <= 90 * 60

    board = client.get(f"/teacher/homework/notices/{nid}", headers=th).json()
    assert board["recipients"][0]["usedMinutes"] == 0
    assert board["recipients"][0]["overtime"] is False

    with legacy.SessionLocal() as db:
        db.execute(text("UPDATE homework_recipients SET started_at = :s WHERE notice_id = :n"),
                   {"s": datetime.utcnow() - timedelta(minutes=120), "n": nid})
        db.commit()

    late = client.get("/student/homework/today", headers=sh).json()[0]
    assert late["remainingSeconds"] < 0
    late_board = client.get(f"/teacher/homework/notices/{nid}", headers=th).json()
    assert late_board["recipients"][0]["overtime"] is True
    assert late_board["recipients"][0]["usedMinutes"] >= 119
print("OK")
''',
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_truncated_flag_is_set_when_recognition_hits_the_limit(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r"""
import os
from changying.services import homework_vision
import app_v924 as legacy

LONG = "x" * 4001

class FakeResp:
    status_code = 200
    ok = True
    def json(self):
        return {"choices": [{"message": {"content": json.dumps({"text": LONG, "hasFigure": False, "confidence": 0.9})}}], "usage": {}}

homework_vision.requests.post = lambda url, headers=None, json=None, timeout=None: FakeResp()
legacy._ai_rate_check = lambda db, school_id: None
legacy._validate_ai_base_url = lambda base, runtime=False: base

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    allow_ai(school_of(sid))
    os.environ.update({
        "HOMEWORK_VISION_PROVIDER": "openai_compatible",
        "HOMEWORK_VISION_BASE_URL": "https://api.deepseek.com",
        "HOMEWORK_VISION_MODEL": "vision-test-model",
        "HOMEWORK_VISION_API_KEY": "test-key-not-real",
    })
    r = client.post("/teacher/homework/parse-image", headers={**th, "Content-Type": "image/jpeg"},
                    content=b"\xff\xd8\xff\xe0" + b"y" * 200)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["text"]) == 4000, len(body["text"])
    assert body["truncated"] is True, "到 4000 字上限必须标记 truncated"
print("OK")
""",
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_follow_ups_lists_own_students_only(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r"""
from datetime import datetime
from sqlalchemy import insert

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    tbl = legacy.Base.metadata.tables["help_requests"]
    school_id = school_of(sid)
    with legacy.SessionLocal() as db:
        db.execute(insert(tbl).values(
            school_id=school_id, student_id=sid, grade=3, question_text="半径2厘米求面积",
            state="escalated", escalate_reason="student_request", escalated_at=datetime.utcnow(),
        ))
        db.commit()

    r = client.get("/teacher/homework/follow-ups", headers=th)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"], "有求助时应该给出候选"
    first = body["items"][0]
    assert first["helpID"] and first["reason"] and first["evidence"]["helpID"] == first["helpID"]
    assert first["next"]["params"]["helpID"] == first["helpID"], "下一步必须带定位参数"
    assert body["dailyLimit"] == 5 and "每天每班" in body["note"]

    assert client.get("/teacher/homework/follow-ups", headers=sh).status_code == 403
print("OK")
""",
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_follow_ups_budget_and_dismiss(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r"""
from datetime import datetime
from sqlalchemy import insert

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    tbl = legacy.Base.metadata.tables["help_requests"]
    school_id = school_of(sid)
    ids = []
    with legacy.SessionLocal() as db:
        for n in range(7):
            r = db.execute(insert(tbl).values(
                school_id=school_id, student_id=sid, grade=3, question_text="题%d" % n,
                state="escalated", escalate_reason="student_request", escalated_at=datetime.utcnow(),
            ))
            ids.append(r.inserted_primary_key[0])
        db.commit()

    # 预览不占名额；正式展示先 claim，返回的就是已经记账、可以渲染的条目
    preview = client.get("/teacher/homework/follow-ups", headers=th).json()
    assert preview["dailyLimit"] == 5
    assert len(preview["items"]) == 1, ("同一学生 7 条求助当天只推 1 条，实际 %d" % len(preview["items"]))

    body = client.post("/teacher/homework/follow-ups/claim", headers=th).json()
    assert len(body["items"]) == 1
    first = body["items"][0]["helpID"]
    assert body["recorded"] == [first], body
    # 再确认一次不会再记一遍，也不会多出条目
    again = client.post("/teacher/homework/follow-ups/claim", headers=th).json()
    assert again["recorded"] == [] and [x["helpID"] for x in again["items"]] == [first], again

    # 暂缓 → 该学生当天整体不再出现
    snoozed = client.post("/teacher/homework/follow-ups/%d/snooze" % first, headers=th)
    assert snoozed.status_code == 200
    assert client.get("/teacher/homework/follow-ups", headers=th).json()["items"] == []
    assert client.post("/teacher/homework/follow-ups/claim", headers=th).json()["items"] == []

    # 暂缓 → 该学生当天整体不再出现
    snoozed = client.post("/teacher/homework/follow-ups/%d/snooze" % first, headers=th)
    assert snoozed.status_code == 200
    assert client.get("/teacher/homework/follow-ups", headers=th).json()["items"] == []

    # 新求助也不行：当天已经给这个学生推过一条
    with legacy.SessionLocal() as db:
        db.execute(insert(tbl).values(
            school_id=school_id, student_id=sid, grade=3, question_text="新题",
            state="escalated", escalate_reason="student_request", escalated_at=datetime.utcnow()))
        db.commit()
    after2 = client.get("/teacher/homework/follow-ups", headers=th).json()
    assert after2["items"] == [], "该学生当天已处理过，新求助也不再推"

    assert client.get("/teacher/homework/follow-ups", headers=sh).status_code == 403
print("OK")
""",
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_dismissed_follow_ups_stay_hidden_across_days(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r"""
from datetime import datetime, timedelta
import json as _json
from sqlalchemy import insert

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    tbl = legacy.Base.metadata.tables["help_requests"]
    school_id = school_of(sid)
    with legacy.SessionLocal() as db:
        r = db.execute(insert(tbl).values(
            school_id=school_id, student_id=sid, grade=3, question_text="a",
            state="escalated", escalate_reason="student_request", escalated_at=datetime.utcnow()))
        hid = r.inserted_primary_key[0]
        # 三天前"已处理"过这条求助：created_at 也挪到三天前，才能证明旧的 24 小时窗口问题已修
        db.add(legacy.AuditLog(
            school_id=school_id, user_id=client.get("/session", headers=th).json()["userID"],
            action="follow_up_dismissed",
            created_at=datetime.utcnow() - timedelta(days=3),
            detail=_json.dumps({"helpID": hid, "studentID": sid, "day": (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")}),
        ))
        db.commit()

    body = client.get("/teacher/homework/follow-ups", headers=th).json()
    assert hid not in [x["helpID"] for x in body["items"]], "三天前已处理的求助不能再次出现"
print("OK")
""",
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_follow_ups_stats_measure_time_from_shown_to_handled(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r"""
from datetime import datetime, timedelta
from sqlalchemy import insert

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    tbl = legacy.Base.metadata.tables["help_requests"]
    with legacy.SessionLocal() as db:
        r = db.execute(insert(tbl).values(
            school_id=school_of(sid), student_id=sid, grade=3, question_text="a",
            state="escalated", escalate_reason="student_request", escalated_at=datetime.utcnow()))
        hid = r.inserted_primary_key[0]
        db.commit()

    client.post("/teacher/homework/follow-ups/shown", headers=th, json={"helpIDs": [hid]})
    # 把展示时间挪到 30 分钟前，模拟老师过了一会儿才处理
    audit = legacy.AuditLog
    with legacy.SessionLocal() as db:
        db.query(audit).filter(audit.action == "follow_up_shown").update(
            {audit.created_at: datetime.utcnow() - timedelta(minutes=30)})
        db.commit()
    client.post("/teacher/homework/follow-ups/%d/dismiss" % hid, headers=th)

    stats = client.get("/teacher/homework/follow-ups/stats?days=10", headers=th).json()
    assert stats["overall"]["handledWithTiming"] == 1, stats
    assert stats["overall"]["medianMinutes"] >= 29, stats
    assert client.get("/teacher/homework/follow-ups/stats", headers=sh).status_code == 403
print("OK")
""",
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_follow_ups_verification_comes_from_real_submissions(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r"""
import json
from datetime import datetime, timedelta
from sqlalchemy import func, insert, select

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    teacher_id = client.get("/session", headers=th).json()["userID"]
    school_id = school_of(sid)
    helps_tbl = legacy.Base.metadata.tables["help_requests"]
    know_tbl = legacy.Base.metadata.tables["homework_ai_knowledge"]
    subs_tbl = legacy.Base.metadata.tables["submissions"]

    # 造 3 道数学题 + 3 道科学同名知识点题：默认门槛是"后续提交 3 题、80% 正确"。
    knowledge = "独立验证测试点"
    shared_kp = "统计图表"
    with legacy.SessionLocal() as db:
        qids = []
        math_shared_qids = []
        sci_shared_qids = []
        for n in range(3):
            r = db.execute(insert(legacy.Base.metadata.tables["questions"]).values(
                school_id=school_id, grade=3, subject="数学", knowledge=knowledge,
                text="第%d题" % n, options_json="{}", correct_index=0))
            qids.append(int(r.inserted_primary_key[0]))
            rm = db.execute(insert(legacy.Base.metadata.tables["questions"]).values(
                school_id=school_id, grade=3, subject="数学", knowledge=shared_kp,
                text="数学统计第%d题" % n, options_json="{}", correct_index=0))
            math_shared_qids.append(int(rm.inserted_primary_key[0]))
            rs = db.execute(insert(legacy.Base.metadata.tables["questions"]).values(
                school_id=school_id, grade=3, subject="科学", knowledge=shared_kp,
                text="科学统计第%d题" % n, options_json="{}", correct_index=0))
            sci_shared_qids.append(int(rs.inserted_primary_key[0]))
        class_a = db.scalar(
            select(legacy.ClassStudent.class_id).where(legacy.ClassStudent.student_id == sid).limit(1)
        )
        # 每班每天最多展示 5 人，额外建两个班让所有测试学生都能在同一次 GET 中看到
        cls_b = legacy.SchoolClass(school_id=school_id, name="验证B班", grade=3, teacher_id=teacher_id)
        cls_c = legacy.SchoolClass(school_id=school_id, name="验证C班", grade=3, teacher_id=teacher_id)
        db.add_all([cls_b, cls_c]); db.flush()
        class_b, class_c = int(cls_b.id), int(cls_c.id)
        db.commit()

    def add_student(name, target_class=class_a):
        with legacy.SessionLocal() as db:
            pupil = legacy.User(school_id=school_id, username=name, password_hash=legacy.hash_password("x"),
                                name=name, role="student", grade=3)
            db.add(pupil); db.flush()
            db.add(legacy.ClassStudent(class_id=target_class, student_id=pupil.id))
            db.commit()
            return int(pupil.id)

    def add_help(student_id, question="题", when=None, state="escalated"):
        ts = when or datetime.utcnow()
        with legacy.SessionLocal() as db:
            r = db.execute(insert(helps_tbl).values(
                school_id=school_id, student_id=student_id, grade=3, question_text=question,
                state=state, escalate_reason="student_request", escalated_at=ts, created_at=ts))
            db.commit()
            return int(r.inserted_primary_key[0])

    def add_knowledge(student_id, help_id, matched=True, key=None, subject=None, created_at=None):
        subj = ("数学" if matched else "") if subject is None else subject
        kp = key if key is not None else knowledge
        with legacy.SessionLocal() as db:
            db.execute(insert(know_tbl).values(
                school_id=school_id, student_id=student_id, help_id=help_id, grade=3,
                subject=subj, knowledge_key=kp, raw_knowledge=kp,
                matched=matched, question_excerpt="题", verify_status="skipped",
                created_at=created_at or (datetime.utcnow() - timedelta(hours=2))))
            db.commit()

    def add_submission(student_id, correct, question_ids=None, submitted_at=None):
        used_qids = question_ids if question_ids is not None else qids
        with legacy.SessionLocal() as db:
            db.execute(insert(subs_tbl).values(
                school_id=school_id, student_id=student_id, title="巩固",
                score=0, correct=0, total=len(used_qids),
                answers_json=json.dumps([{"question_id": q, "correct": correct} for q in used_qids]),
                submitted_at=submitted_at or datetime.utcnow()))
            db.commit()

    base_now = datetime.utcnow()

    # 1) 匹配到知识点，后续巩固 3 题全对（刚好达标）→ 后续练习达到条件
    passed = add_help(sid, when=base_now - timedelta(hours=2))
    add_knowledge(sid, passed, created_at=base_now - timedelta(hours=2))
    add_submission(sid, True, submitted_at=base_now - timedelta(hours=1))

    # 2) 匹配到知识点，后续巩固 3 题全错 → 已有结果尚未达标
    failed_sid = add_student("pupil_failed", class_a)
    failed = add_help(failed_sid)
    add_knowledge(failed_sid, failed, created_at=base_now - timedelta(hours=2))
    add_submission(failed_sid, False, submitted_at=base_now - timedelta(hours=1))

    # 3) 知识点匹配但零提交 → 尚无后续作答
    no_sub_sid = add_student("pupil_no_sub", class_a)
    no_sub = add_help(no_sub_sid)
    add_knowledge(no_sub_sid, no_sub, created_at=base_now - timedelta(hours=2))

    # 4) 只提交 2 题（即使全对，< 3 题）→ 题量不足待补充
    two_q_sid = add_student("pupil_two_q", class_a)
    two_q = add_help(two_q_sid)
    add_knowledge(two_q_sid, two_q, created_at=base_now - timedelta(hours=2))
    add_submission(two_q_sid, True, question_ids=qids[:2], submitted_at=base_now - timedelta(hours=1))

    # 5a) 提交时间早于求助记录（之后无提交）→ 不采信，回到"尚无后续作答"
    early_none_sid = add_student("pupil_early_none", class_a)
    early_none = add_help(early_none_sid)
    add_knowledge(early_none_sid, early_none, created_at=base_now - timedelta(hours=1))
    add_submission(early_none_sid, True, submitted_at=base_now - timedelta(hours=3))

    # 5b) 提交时间早于求助记录 3 题全对，求助后只交了 1 题 → 旧提交不采信，回到"题量不足待补充"
    early_part_sid = add_student("pupil_early_part", class_b)
    early_part = add_help(early_part_sid)
    add_knowledge(early_part_sid, early_part, created_at=base_now - timedelta(hours=2))
    add_submission(early_part_sid, True, submitted_at=base_now - timedelta(hours=3))
    add_submission(early_part_sid, True, question_ids=qids[:1], submitted_at=base_now - timedelta(hours=1))

    # 6a) 同名知识点不同学科：同一学生有"数学·统计图表"（3题全对）和"科学·统计图表"（0提交）两条知识记录，
    # 当前待跟进求助是"科学·统计图表"，不能被数学达标结果覆盖 → 尚无后续作答
    cross_sci_sid = add_student("pupil_cross_sci", class_b)
    old_math_help = add_help(cross_sci_sid, state="answered", when=base_now - timedelta(hours=3))
    add_knowledge(cross_sci_sid, old_math_help, key=shared_kp, subject="数学", created_at=base_now - timedelta(hours=3))
    add_submission(cross_sci_sid, True, question_ids=math_shared_qids, submitted_at=base_now - timedelta(hours=2))
    cross_sci_help = add_help(cross_sci_sid, when=base_now - timedelta(hours=2))
    add_knowledge(cross_sci_sid, cross_sci_help, key=shared_kp, subject="科学", created_at=base_now - timedelta(hours=2))

    # 6b) 反向验证同名知识点不同学科：同一学生有"科学·统计图表"（3题全错）和"数学·统计图表"（3题全对）两条知识记录，
    # 当前待跟进求助是"数学·统计图表"，不能被科学未达标覆盖 → 后续练习达到条件
    cross_math_sid = add_student("pupil_cross_math", class_b)
    old_sci_help = add_help(cross_math_sid, state="answered", when=base_now - timedelta(hours=3))
    add_knowledge(cross_math_sid, old_sci_help, key=shared_kp, subject="科学", created_at=base_now - timedelta(hours=3))
    add_submission(cross_math_sid, False, question_ids=sci_shared_qids, submitted_at=base_now - timedelta(hours=2))
    cross_math_help = add_help(cross_math_sid, when=base_now - timedelta(hours=2))
    add_knowledge(cross_math_sid, cross_math_help, key=shared_kp, subject="数学", created_at=base_now - timedelta(hours=2))
    add_submission(cross_math_sid, True, question_ids=math_shared_qids, submitted_at=base_now - timedelta(hours=1))

    # 7a) 没有任何知识点记录 → 无法匹配知识点
    unknown_sid = add_student("pupil_unknown", class_b)
    unknown = add_help(unknown_sid)

    # 7b) 有记录但 matched=False → 无法匹配知识点
    unmatched_sid = add_student("pupil_unmatched", class_b)
    unmatched = add_help(unmatched_sid)
    add_knowledge(unmatched_sid, unmatched, matched=False, key="完全无关的奇怪说法")

    # 7c) matched=True 但 subject 为空（即使提交了同名数学题也不得混用）→ 无法匹配知识点
    empty_subj_sid = add_student("pupil_empty_subj", class_c)
    empty_subj = add_help(empty_subj_sid)
    add_knowledge(empty_subj_sid, empty_subj, matched=True, key=knowledge, subject="", created_at=base_now - timedelta(hours=2))
    add_submission(empty_subj_sid, True, submitted_at=base_now - timedelta(hours=1))

    body = client.get("/teacher/homework/follow-ups", headers=th).json()
    by_help = {x["helpID"]: x for x in body["items"]}
    labels = {hid: item["verification"] for hid, item in by_help.items()}
    assert labels.get(failed) == "已有结果尚未达标", labels
    assert labels.get(no_sub) == "尚无后续作答", labels
    assert labels.get(two_q) == "题量不足待补充", labels
    assert labels.get(early_none) == "尚无后续作答", labels
    assert labels.get(early_part) == "题量不足待补充", labels
    assert labels.get(cross_sci_help) == "尚无后续作答", labels
    # 达到条件的求助不再需要跟进，会从当天列表移出（名额仍不返还）
    assert passed not in labels, ("达到条件的求助应移出待跟进", labels)
    assert cross_math_help not in labels, ("达到条件的求助应移出待跟进", labels)
    assert labels.get(unknown) == "无法匹配知识点", labels
    assert labels.get(unmatched) == "无法匹配知识点", labels
    assert labels.get(empty_subj) == "无法匹配知识点", labels
    assert all(v != "练习尚未通过" for v in labels.values()), labels

    # 移出列表的"达到条件"要用服务层 flag 断言（详情字段只在列表里暴露）
    from changying.services.homework_knowledge_flags import knowledge_flags as _knowledge_flags
    with legacy.SessionLocal() as db:
        sid_flags = _knowledge_flags(legacy, db, school_id, sid)["flags"]
    passed_flag = [f for f in sid_flags if f["knowledge"] == knowledge][0]
    assert passed_flag["verification"] == "后续练习达到条件", passed_flag
    assert passed_flag["verificationState"] == "passed", passed_flag
    assert passed_flag["hits"] == 3 and passed_flag["total"] == 3, passed_flag

    # 达标之后再做错题：状态仍是“达到条件”，计数冻结在达标那一刻
    add_submission(sid, False, submitted_at=base_now - timedelta(minutes=30))
    with legacy.SessionLocal() as db:
        frozen = [f for f in _knowledge_flags(legacy, db, school_id, sid)["flags"]
                  if f["knowledge"] == knowledge][0]
    assert frozen["verification"] == "后续练习达到条件", frozen
    assert (frozen["hits"], frozen["total"]) == (3, 3), frozen

    # 单次达标只算那一次的证据：之前做错 1 题，不能把 3/3 显示成 3/4
    batch_sid = add_student("pupil_batch", class_c)
    batch = add_help(batch_sid)
    add_knowledge(batch_sid, batch, created_at=base_now - timedelta(hours=2))
    add_submission(batch_sid, False, question_ids=qids[:1], submitted_at=base_now - timedelta(hours=1, minutes=30))
    add_submission(batch_sid, True, submitted_at=base_now - timedelta(hours=1))
    with legacy.SessionLocal() as db:
        batch_flag = [f for f in _knowledge_flags(legacy, db, school_id, batch_sid)["flags"]
                      if f["knowledge"] == knowledge][0]
    assert batch_flag["verification"] == "后续练习达到条件", batch_flag
    assert (batch_flag["hits"], batch_flag["total"]) == (3, 3), batch_flag
    assert batch_flag["submissionCount"] == 2, batch_flag

    # 验证新增详情字段结构与数值
    assert by_help[two_q]["verificationDetail"]["state"] == "insufficient_questions"
    assert by_help[two_q]["verificationDetail"]["total"] == 2
    assert by_help[failed]["verificationDetail"]["state"] == "below_threshold"
    assert by_help[failed]["verificationDetail"]["hits"] == 0 and by_help[failed]["verificationDetail"]["total"] == 3

    # 8) 同一学生再次求助后，旧提交不再算新问题已解决
    reask_help = add_help(sid, question="同一知识点再次求助", when=base_now - timedelta(minutes=10))
    add_knowledge(sid, reask_help, created_at=base_now - timedelta(minutes=10))
    after_reask = client.get("/teacher/homework/follow-ups", headers=th).json()
    sid_items = [x for x in after_reask["items"] if x["studentID"] == sid]
    assert len(sid_items) == 1, sid_items
    assert sid_items[0]["verification"] == "尚无后续作答", sid_items[0]
    assert sid_items[0]["verificationDetail"]["total"] == 0, sid_items[0]

    # 9) 判定依赖对单个学生抛异常 → 只把该学生记为"无法判定"，其他学生仍正常
    import changying.services.homework_knowledge_flags as flags_mod
    real_knowledge_flags = flags_mod.knowledge_flags

    def boom_one(implementation, db, s_id, stu_id):
        if stu_id == failed_sid:
            raise RuntimeError("single student flags failure")
        return real_knowledge_flags(implementation, db, s_id, stu_id)

    flags_mod.knowledge_flags = boom_one
    partial = client.get("/teacher/homework/follow-ups", headers=th).json()
    partial_labels = {x["helpID"]: x["verification"] for x in partial["items"]}
    assert partial_labels.get(failed) == "无法判定", partial_labels
    assert partial_labels.get(no_sub) == "尚无后续作答", partial_labels
    assert partial_labels.get(two_q) == "题量不足待补充", partial_labels
    assert partial_labels.get(cross_math_help) is None, ("达到条件的求助仍应移出", partial_labels)
    assert partial_labels.get(unknown) == "无法匹配知识点", partial_labels

    # 全部抛异常时整表退回"无法判定"，不 500
    def boom_all(*args, **kwargs):
        raise RuntimeError("knowledge flags down")

    flags_mod.knowledge_flags = boom_all
    after = client.get("/teacher/homework/follow-ups", headers=th).json()
    assert after["items"], after
    assert all(x["verification"] == "无法判定" for x in after["items"]), after
print("OK")
""",
        {"HOMEWORK_ASSISTANT": "1"},
    )


def test_follow_ups_budget_is_per_class_and_never_refunded(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r"""
from datetime import datetime, timedelta
from sqlalchemy import insert, select

with TestClient(app) as client:
    th, sh, sid = teacher_student_headers(client)
    teacher_id = client.get("/session", headers=th).json()["userID"]
    school_id = school_of(sid)
    helps_tbl = legacy.Base.metadata.tables["help_requests"]

    with legacy.SessionLocal() as db:
        class_a = db.scalar(select(legacy.ClassStudent.class_id).where(legacy.ClassStudent.student_id == sid).limit(1))
        class_b = legacy.SchoolClass(school_id=school_id, name="晚托B班", grade=3, teacher_id=teacher_id)
        db.add(class_b); db.flush(); class_b_id = class_b.id; db.commit()

    def add_student(name, class_id):
        with legacy.SessionLocal() as db:
            pupil = legacy.User(school_id=school_id, username=name, password_hash=legacy.hash_password("x"),
                                name=name, role="student", grade=3)
            db.add(pupil); db.flush()
            db.add(legacy.ClassStudent(class_id=class_id, student_id=pupil.id))
            db.commit()
            return int(pupil.id)

    base_time = datetime.utcnow()

    def add_help(student_id, minutes):
        with legacy.SessionLocal() as db:
            r = db.execute(insert(helps_tbl).values(
                school_id=school_id, student_id=student_id, grade=3, question_text="题",
                state="escalated", escalate_reason="student_request",
                escalated_at=base_time + timedelta(minutes=minutes)))
            db.commit()
            return int(r.inserted_primary_key[0])

    # A 班 6 人（sid + 新增 5 人），B 班 2 人
    a_students = [sid] + [add_student("a_pupil_%d" % n, class_a) for n in range(5)]
    b_students = [add_student("b_pupil_%d" % n, class_b_id) for n in range(2)]

    a_helps = []
    for index, student_id in enumerate(a_students):
        a_helps.append(add_help(student_id, index * 10))
    b_helps = [add_help(student_id, 100 + index) for index, student_id in enumerate(b_students)]

    # 第 6 个 A 班学生还有一条更晚的求助：名额满了以后也不能靠"再来一条"补进
    a6_extra = add_help(a_students[5], 500)

    # 预览不算名额
    preview = client.get("/teacher/homework/follow-ups", headers=th).json()
    assert len(preview["items"]) == 7, preview["items"]

    # 正式展示：先 claim 确认名额，返回的就是可以渲染的条目
    body = client.post("/teacher/homework/follow-ups/claim", headers=th).json()
    shown_ids = [x["helpID"] for x in body["items"]]
    shown_students = {x["studentID"] for x in body["items"]}
    assert len(shown_ids) == 7, (len(shown_ids), shown_ids)
    assert sorted(body["recorded"]) == sorted(shown_ids), body
    assert set(a_helps[:5]) <= set(shown_ids), shown_ids
    assert a_students[5] not in shown_students, "A 班第 6 人不能出现：这个班的名额已满"
    assert a6_extra not in shown_ids, "同一学生的第二条求助也不能顶进来"
    assert set(b_helps) <= set(shown_ids), shown_ids

    # 两台设备分别确认：允许两台看到同一批 5 人；验收看当天同班"获准学生去重后的并集"不超过 5
    second_token = client.post("/login", json={"username": "teacher1", "password": "Teacher1234", "remember": False}).json()["token"]
    th2 = {"Authorization": "Bearer " + second_token}
    device2 = client.post("/teacher/homework/follow-ups/claim", headers=th2).json()
    assert device2["recorded"] == [], device2
    assert {x["studentID"] for x in device2["items"]} == shown_students, device2["items"]
    class_a_set = set(a_students)
    union_a = {x["studentID"] for x in body["items"] if x["studentID"] in class_a_set} | \
              {x["studentID"] for x in device2["items"] if x["studentID"] in class_a_set}
    assert len(union_a) == 5, union_a
    assert a_students[5] not in union_a

    # 同一学生的多条 helpID 不会被后来者补记
    dup = client.post("/teacher/homework/follow-ups/shown", headers=th,
                      json={"helpIDs": [a6_extra, add_help(a_students[5], -10)]}).json()
    assert dup["recorded"] == [], dup

    # 处理掉一个已经展示过的 A 班学生：名额不返还，第 6 人仍然不能出现
    client.post("/teacher/homework/follow-ups/%d/dismiss" % a_helps[0], headers=th)
    after = client.post("/teacher/homework/follow-ups/claim", headers=th).json()
    after_ids = [x["helpID"] for x in after["items"]]
    after_students = {x["studentID"] for x in after["items"]}
    assert len(after_ids) == 6, after_ids
    assert a_helps[0] not in after_ids, "已处理的建议当天收起"
    assert a_students[5] not in after_students, "处理掉一条不能把名额还给第 6 人"
    assert a6_extra not in after_ids
    assert set(b_helps) <= set(after_ids), "B 班有自己的预算，不受 A 班影响"

    # 已展示但未处理的学生，刷新后仍是同一条求助，不会换成同学生的另一条
    second_help = add_help(a_students[1], 300)
    refreshed = client.post("/teacher/homework/follow-ups/claim", headers=th).json()
    refreshed_ids = [x["helpID"] for x in refreshed["items"]]
    assert a_helps[1] in refreshed_ids, refreshed_ids
    assert second_help not in refreshed_ids, "同一学生当天只保留最早那条已展示的求助"
    assert refreshed["recorded"] == []
print("OK")
""",
        {"HOMEWORK_ASSISTANT": "1"},
    )

