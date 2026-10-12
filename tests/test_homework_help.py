from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_KEYS = (
    "HOMEWORK_ASSISTANT", "HOMEWORK_VISION_PROVIDER", "HOMEWORK_VISION_BASE_URL", "HOMEWORK_VISION_MODEL",
    "HOMEWORK_VISION_API_KEY", "HOMEWORK_STUDENT_DAILY_LIMIT", "HOMEWORK_SCHOOL_HOURLY_LIMIT", "HOMEWORK_AI_CONCURRENCY",
)


def run_isolated(tmp_path, script: str, extra_env: dict[str, str] | None = None) -> str:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'help.sqlite3'}",
        "PYTHONPATH": str(ROOT),
    }
    for key in ENV_KEYS:
        env.pop(key, None)
    env.update(extra_env or {})
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=env, text=True, capture_output=True, timeout=240
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout, result.stdout
    return result.stdout


ON = {"HOMEWORK_ASSISTANT": "1"}
VISION = {
    **ON,
    "HOMEWORK_VISION_BASE_URL": "https://api.deepseek.com",
    "HOMEWORK_VISION_MODEL": "vision-model",
    "HOMEWORK_VISION_API_KEY": "test-key-not-real",
}

COMMON = r'''
import json

from fastapi.testclient import TestClient

import app_v924 as legacy
from app import app
from changying.services import homework_vision

legacy._validate_ai_base_url = lambda base, runtime=False: base
MARKER = b"UNIQUE-HELP-IMAGE-MARKER-9876543210"
JPEG = b"\xff\xd8\xff\xe0" + MARKER * 20
vision_calls = []


class FakeResponse:
    ok = True
    status_code = 200

    def json(self):
        return {"choices": [{"message": {"content": json.dumps({"text": "小明有 12 个苹果，吃了 5 个，还剩几个？", "hasFigure": False, "confidence": 0.93}, ensure_ascii=False)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 30}}


def fake_post(url, headers=None, json=None, timeout=None):
    vision_calls.append(json)
    return FakeResponse()


homework_vision.requests.post = fake_post


def no_text_model(*args, **kwargs):
    raise AssertionError("confirming a question must not call the text model in this step")


legacy._ai_call = no_text_model


def login_and_change(client, username, old_password, new_password):
    login = client.post("/login", json={"username": username, "password": old_password, "remember": False})
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    changed = client.post("/change-password", headers={"Authorization": f"Bearer {token}"},
                          json={"current_password": old_password, "new_password": new_password, "remember": False})
    assert changed.status_code == 200, changed.text
    return changed.json()["token"]


def allow_ai(school_id, allow=True):
    with legacy.SessionLocal() as db:
        row = legacy.ai_config_for(db, school_id, True)
        row.enabled = True
        row.allow_student_data = allow
        row.provider = "openai_compatible"
        row.base_url = "https://api.deepseek.com"
        row.model = "text-model"
        db.commit()


def setup(client, allow=True):
    th = {"Authorization": "Bearer " + login_and_change(client, "teacher1", "123456", "Teacher1234")}
    sh = {"Authorization": "Bearer " + login_and_change(client, "student1", "123456", "Student1234")}
    session = client.get("/session", headers=sh).json()
    with legacy.SessionLocal() as db:
        school_id = db.get(legacy.User, session["userID"]).school_id
    allow_ai(school_id, allow)
    return th, sh, session["userID"], school_id


def snap(client, sh):
    return client.post("/student/homework/recognize", headers={**sh, "Content-Type": "image/jpeg"}, content=JPEG)
'''


def test_new_routes_are_404_when_the_flag_is_off(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    assert snap(client, sh).status_code == 404
    assert client.post("/student/homework/help", headers=sh, json={"questionText": "1+1"}).status_code == 404
    assert client.get("/student/homework/help/1", headers=sh).status_code == 404
print("OK")
''',
    )


def test_student_needs_the_school_to_allow_ai_first(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client, allow=False)
    assert snap(client, sh).status_code == 403
    assert client.post("/student/homework/help", headers=sh, json={"questionText": "1+1"}).status_code == 403
    assert not vision_calls
    allow_ai(school_id, True)
    assert snap(client, sh).status_code == 200
print("OK")
''',
        VISION,
    )


def test_photo_to_confirmed_question_without_text_model_or_stored_image(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
from pathlib import Path
from sqlalchemy import select

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    # Teachers and parents have no student help flow.
    assert client.post("/student/homework/recognize", headers={**th, "Content-Type": "image/jpeg"}, content=JPEG).status_code == 403
    assert client.post("/student/homework/help", headers=th, json={"questionText": "x"}).status_code == 403

    r = snap(client, sh)
    assert r.status_code == 200, r.text
    recognised = r.json()
    assert recognised["text"].startswith("小明有 12 个苹果") and recognised["hasFigure"] is False
    # Only the picture went to the vision model; no identity data, exact model name.
    sent = json.dumps(vision_calls[-1], ensure_ascii=False)
    assert "vision-model" in sent and "student1" not in sent and "小明" not in sent.split("data:")[0]
    assert "只识别学生要问的这一道题" in sent and "页眉页脚" in sent  # the student prompt keeps one question only

    # Bad inputs are refused before anything is stored.
    assert client.post("/student/homework/help", headers=sh, json={"questionText": "   "}).status_code == 400
    assert client.post("/student/homework/help", headers=sh, json={"questionText": "x" * 1001}).status_code == 400
    assert client.post("/student/homework/help", headers=sh, json={"questionText": "1+1", "grade": 9}).status_code == 400
    assert client.post("/student/homework/help", headers=sh, json={"questionText": "1+1", "noticeID": 999}).status_code == 404

    # The student edits the recognised text and confirms: one row, no text-model call.
    edited = recognised["text"].replace("12", "15")
    created = client.post("/student/homework/help", headers=sh, json={"questionText": edited, "grade": 3})
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["questionText"] == edited and body["grade"] == 3 and body["state"] == "confirmed"
    assert body["solution"] is None
    assert client.get(f"/student/homework/help/{body['id']}", headers=sh).json()["questionText"] == edited
    assert client.get("/student/homework/help/9999", headers=sh).status_code == 404

    # Grade defaults to the account's grade (student1 is grade 3).
    default = client.post("/student/homework/help", headers=sh, json={"questionText": "3+4=?"})
    assert default.status_code == 200 and default.json()["grade"] == 3

    # Another student cannot read it.
    with legacy.SessionLocal() as db:
        other = legacy.User(school_id=school_id, username="other9", password_hash=legacy.hash_password("Passw0rd!x"),
                            name="同学", role="student", grade=4)
        db.add(other); db.flush()
        db.add(legacy.UserSecurity(user_id=other.id, must_change_password=False))
        db.commit()
    token = client.post("/login", json={"username": "other9", "password": "Passw0rd!x", "remember": False}).json()["token"]
    oh = {"Authorization": "Bearer " + token}
    assert client.get(f"/student/homework/help/{body['id']}", headers=oh).status_code == 404

    # The picture is nowhere: not in the database file, not in the usage log.
    import base64
    with legacy.SessionLocal() as db:
        logs = db.scalars(select(legacy.AIUsageLog).where(legacy.AIUsageLog.feature == "homework_help_vision")).all()
        assert len(logs) == 1 and logs[0].user_id == sid and logs[0].error == ""
    legacy.engine.dispose()
    raw = Path(legacy.engine.url.database).read_bytes()
    assert MARKER not in raw and base64.b64encode(MARKER) not in raw
print("OK")
''',
        VISION,
    )


def test_per_student_limits_return_friendly_429(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
from datetime import datetime, timedelta
from sqlalchemy import update

help_tbl = legacy.Base.metadata.tables["help_requests"]

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    # Per minute: two confirmed questions, the third in the same minute is refused.
    assert client.post("/student/homework/help", headers=sh, json={"questionText": "a"}).status_code == 200
    assert client.post("/student/homework/help", headers=sh, json={"questionText": "b"}).status_code == 200
    fast = client.post("/student/homework/help", headers=sh, json={"questionText": "c"})
    assert fast.status_code == 429 and "太快" in fast.json()["detail"]

    # Per day (HOMEWORK_STUDENT_DAILY_LIMIT=2): after the minute passed, still no more today.
    with legacy.SessionLocal() as db:
        db.execute(update(help_tbl).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.commit()
    done = client.post("/student/homework/help", headers=sh, json={"questionText": "d"})
    assert done.status_code == 429 and "明天" in done.json()["detail"]

    # Model calls: six per minute, then the daily call cap (limit 2 * 3 calls = 6 per day).
    for _ in range(6):
        assert snap(client, sh).status_code == 200
    assert snap(client, sh).status_code == 429
    with legacy.SessionLocal() as db:
        db.execute(update(legacy.AIUsageLog).values(created_at=datetime.utcnow() - timedelta(minutes=5)))
        db.commit()
    capped = snap(client, sh)
    assert capped.status_code == 429 and "明天" in capped.json()["detail"]
    assert len(vision_calls) == 6
print("OK")
''',
        {**VISION, "HOMEWORK_STUDENT_DAILY_LIMIT": "2"},
    )


def test_school_hourly_bucket_and_concurrency_gate(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
from changying.services.homework_limits import ai_slot, slots_in_use

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    # Concurrency: with one slot taken the next student call gets a polite 429, then recovers.
    with ai_slot():
        busy = snap(client, sh)
        assert busy.status_code == 429 and "稍等" in busy.json()["detail"]
    assert slots_in_use() == 0
    assert snap(client, sh).status_code == 200
    assert slots_in_use() == 0

    # School bucket: ten student-side calls by classmates in the last hour fill it.
    with legacy.SessionLocal() as db:
        for _ in range(10):
            db.add(legacy.AIUsageLog(school_id=school_id, user_id=sid + 1000, feature="homework_help_solve",
                                     provider="p", model="m", status="ok"))
        db.commit()
    full = snap(client, sh)
    assert full.status_code == 429 and "稍等" in full.json()["detail"]
print("OK")
''',
        {**VISION, "HOMEWORK_AI_CONCURRENCY": "1", "HOMEWORK_SCHOOL_HOURLY_LIMIT": "10"},
    )


def test_a_failing_call_still_releases_the_slot(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
import requests
from changying.services.homework_limits import slots_in_use


def boom(*a, **k):
    raise requests.Timeout()


homework_vision.requests.post = boom
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    assert snap(client, sh).status_code == 504
    assert slots_in_use() == 0
print("OK")
''',
        {**VISION, "HOMEWORK_AI_CONCURRENCY": "1"},
    )


def test_limit_settings_come_from_the_environment_with_safe_defaults(monkeypatch):
    from changying.services import homework_limits as limits

    for key in ("HOMEWORK_STUDENT_DAILY_LIMIT", "HOMEWORK_SCHOOL_HOURLY_LIMIT", "HOMEWORK_AI_CONCURRENCY"):
        monkeypatch.delenv(key, raising=False)
    assert (limits.student_daily_limit(), limits.school_hourly_limit(), limits.concurrency_limit()) == (8, 300, 8)
    monkeypatch.setenv("HOMEWORK_STUDENT_DAILY_LIMIT", "12")
    monkeypatch.setenv("HOMEWORK_SCHOOL_HOURLY_LIMIT", "500")
    monkeypatch.setenv("HOMEWORK_AI_CONCURRENCY", "4")
    assert (limits.student_daily_limit(), limits.school_hourly_limit(), limits.concurrency_limit()) == (12, 500, 4)
    monkeypatch.setenv("HOMEWORK_STUDENT_DAILY_LIMIT", "oops")
    monkeypatch.setenv("HOMEWORK_SCHOOL_HOURLY_LIMIT", "999999")
    monkeypatch.setenv("HOMEWORK_AI_CONCURRENCY", "0")
    assert (limits.student_daily_limit(), limits.school_hourly_limit(), limits.concurrency_limit()) == (8, 5000, 1)


def test_school_day_starts_at_local_midnight():
    from changying.services.homework_limits import school_day_start_utc

    # 2026-10-11 20:00 UTC is 2026-10-12 04:00 in UTC+8: the school day began at 2026-10-11 16:00 UTC.
    start = school_day_start_utc(datetime(2026, 10, 11, 20, 0, tzinfo=timezone.utc))
    assert start == datetime(2026, 10, 11, 16, 0)
    start = school_day_start_utc(datetime(2026, 10, 11, 10, 0, tzinfo=timezone.utc))
    assert start == datetime(2026, 10, 10, 16, 0)


def test_recognition_does_not_block_other_requests_and_logs_the_output_size(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
import inspect
import threading
import time
from sqlalchemy import select

slow = {"on": True}
original_post = homework_vision.requests.post


def slow_post(*a, **k):
    if slow["on"]:
        time.sleep(1.5)
    return original_post(*a, **k)


homework_vision.requests.post = slow_post


with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    result = {}
    worker = threading.Thread(target=lambda: result.update(status=snap(client, sh).status_code))
    worker.start()
    time.sleep(0.4)
    started = time.time()
    assert client.get("/homework/config").status_code == 200
    assert time.time() - started < 0.8, "another request had to wait for the recognition call"
    worker.join()
    assert result["status"] == 200

    # The usage log records how much text came back (it must not stay at 0).
    with legacy.SessionLocal() as db:
        log = db.scalars(select(legacy.AIUsageLog).where(legacy.AIUsageLog.feature == "homework_help_vision")).all()[-1]
        assert log.output_chars > 0 and log.input_tokens == 100 and log.output_tokens == 30
print("OK")
''',
        VISION,
    )


def test_a_large_photo_never_touches_the_disk(tmp_path):
    tmp = tmp_path / "scratch"
    tmp.mkdir()
    run_isolated(
        tmp_path,
        COMMON
        + r'''
import os
import tempfile

# Count every time the framework's in-memory upload buffer spills over to a file on disk (that is what a
# multipart upload larger than ~1 MB does; temporary files are deleted afterwards, so only this shows it).
spilled = []
_rollover = tempfile.SpooledTemporaryFile.rollover


def spy(self):
    spilled.append(1)
    return _rollover(self)


tempfile.SpooledTemporaryFile.rollover = spy

big_ok = b"\xff\xd8\xff\xe0" + b"7" * (2 * 1024 * 1024)       # 2 MB: above the ~1 MB a multipart parser keeps in memory
too_big = b"\xff\xd8\xff\xe0" + b"7" * (7 * 1024 * 1024)      # over our own limit
scratch = os.environ["TMPDIR"]

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    headers = {**sh, "Content-Type": "image/jpeg"}
    assert os.listdir(scratch) == []

    ok = client.post("/student/homework/recognize", headers=headers, content=big_ok)
    assert ok.status_code == 200, ok.text
    big = client.post("/student/homework/recognize", headers=headers, content=too_big)
    assert big.status_code == 413
    # Not an image at all, and the old multipart form is no longer accepted.
    assert client.post("/student/homework/recognize", headers=headers, content=b"hello").status_code == 415
    old_style = client.post("/student/homework/recognize", headers=sh, files={"file": ("q.jpg", big_ok, "image/jpeg")})
    assert old_style.status_code == 415

    # Unauthenticated callers are refused before the body is read at all.
    assert client.post("/student/homework/recognize", headers={"Content-Type": "image/jpeg"}, content=big_ok).status_code in (401, 403)

    # Nothing was ever spooled or written to the temporary directory.
    assert spilled == [], "a photo was spilled to disk"
    assert os.listdir(scratch) == [], os.listdir(scratch)
print("OK")
''',
        {**VISION, "TMPDIR": str(tmp)},
    )


def test_a_help_request_can_only_point_at_a_real_item_of_the_students_own_list(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    created = client.post("/teacher/homework/notices", headers=th,
                          json={"items": [{"content": "口算第5页"}, {"content": "练习册第3页"}]}).json()
    nid = created["id"]
    assert client.post(f"/teacher/homework/notices/{nid}/publish", headers=th, json={"studentIDs": [sid]}).status_code == 200

    def ask(**extra):
        return client.post("/student/homework/help", headers=sh, json={"questionText": "3+4=?", "grade": 3, **extra})

    ok = ask(noticeID=nid, itemSeq=2)
    assert ok.status_code == 200, ok.text
    for bad in (0, 3, 99, -1):
        r = ask(noticeID=nid, itemSeq=bad)
        assert r.status_code == 400 and "没有这条作业" in r.json()["detail"], (bad, r.text)
    assert ask(noticeID=nid).status_code == 200                  # no item given is fine
    assert ask(noticeID=9999, itemSeq=1).status_code == 404       # not a list of this student
print("OK")
''',
        VISION,
    )


def test_student_page_lets_the_student_frame_one_question_before_sending():
    from changying.web.homework_assistant_pages import homework_page_html

    html = homework_page_html()
    assert "function cropPhoto(" in html and "cropPhoto(f).then(" in html
    assert "只框住这一道题" in html and "不裁剪，用整张" in html
    assert "innerHTML" not in html and "eval(" not in html
