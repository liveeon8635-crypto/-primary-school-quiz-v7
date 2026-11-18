"""Regression guard for the shared model-call helper.

The homework assistant added an optional ``rate_check`` argument to ``_ai_call`` and made the
school-wide hourly counter ignore the student-side ``homework_help_*`` features. Everything a
teacher-side caller relies on must stay exactly as it was: request shape, the usage log row,
what counts towards the hourly limit, and the 429 that follows.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_isolated(tmp_path, script: str) -> None:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'ai.sqlite3'}",
        "PYTHONPATH": str(ROOT),
        "AI_API_KEY": "test-key-not-real",
    }
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=env, text=True, capture_output=True, timeout=240
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout, result.stdout


COMMON = r'''
import json
from datetime import datetime, timedelta

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app_v924 as legacy
from app import app

legacy._validate_ai_base_url = lambda base, runtime=False: base
posts = []


class FakeResponse:
    ok = True
    status_code = 200

    def json(self):
        return {"choices": [{"message": {"content": "回复"}}], "usage": {"prompt_tokens": 11, "completion_tokens": 7}}


def fake_post(url, headers=None, json=None, timeout=None):
    posts.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
    return FakeResponse()


legacy.requests.post = fake_post


def log_count(db, **where):
    q = select(func.count()).select_from(legacy.AIUsageLog)
    for key, value in where.items():
        q = q.where(getattr(legacy.AIUsageLog, key) == value)
    return db.scalar(q)


def prepare(db):
    teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
    row = legacy.ai_config_for(db, teacher.school_id, True)
    row.enabled = True; row.allow_student_data = True; row.provider = "openai_compatible"; row.base_url = "https://api.deepseek.com"; row.model = "m"
    db.commit()
    return teacher


def student_id_for(db, teacher):
    return db.scalar(select(legacy.User.id).where(legacy.User.school_id == teacher.school_id, legacy.User.role == "student"))


def add_logs(db, school_id, user_id, feature, n, age_minutes=1):
    for _ in range(n):
        db.add(legacy.AIUsageLog(school_id=school_id, user_id=user_id, feature=feature, provider="p", model="m",
                                 status="ok", created_at=datetime.utcnow() - timedelta(minutes=age_minutes)))
    db.commit()
'''


def test_teacher_call_request_shape_and_usage_log_are_unchanged(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
with TestClient(app):
    with legacy.SessionLocal() as db:
        teacher = prepare(db)
        sid = student_id_for(db, teacher)
        out = legacy._ai_call(db, teacher, "grading_assist", "hello", student_ids=(sid,))
        assert out == "回复"
        assert len(posts) == 1
        assert posts[0]["url"] == "https://api.deepseek.com/chat/completions"
        assert posts[0]["json"] == {"model": "m", "messages": [{"role": "user", "content": "hello"}], "temperature": 0.2}
        assert posts[0]["timeout"] == 90
        assert posts[0]["headers"]["Authorization"] == "Bearer test-key-not-real"
        row = db.scalars(select(legacy.AIUsageLog)).all()[-1]
        assert (row.feature, row.status, row.prompt_chars, row.output_chars, row.input_tokens, row.output_tokens, row.error) == (
            "grading_assist", "ok", 5, 2, 11, 7, "")
        assert row.user_id == teacher.id and row.school_id == teacher.school_id and row.provider == "openai_compatible"
        # Image callers keep working too.
        legacy._ai_call(db, teacher, "grading_assist", "see", images=["data:image/png;base64,AAAA"], timeout=30, student_ids=(sid,))
        sent = posts[-1]["json"]["messages"][0]["content"]
        assert sent[0] == {"type": "text", "text": "see"} and sent[1]["type"] == "image_url" and posts[-1]["timeout"] == 30
print("OK")
''',
    )


def test_hourly_limit_counts_and_429_are_unchanged_for_teacher_features(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
legacy.AI_HOURLY_LIMIT = 3

with TestClient(app):
    with legacy.SessionLocal() as db:
        teacher = prepare(db)
        sid = student_id_for(db, teacher)
        before = log_count(db)
        for i in range(3):
            legacy._ai_call(db, teacher, "grading_assist", f"p{i}", student_ids=(sid,))
        assert log_count(db) == before + 3 and len(posts) == 3
        # The fourth call in the hour is refused exactly as before: same status and message, no request, no log row.
        try:
            legacy._ai_call(db, teacher, "grading_assist", "p4", student_ids=(sid,))
            raise SystemExit("expected a 429")
        except HTTPException as exc:
            assert exc.status_code == 429
            assert exc.detail == "本校 AI 调用已达到每小时 3 次保护上限，请稍后再试"
        assert len(posts) == 3 and log_count(db) == before + 3

        # Rows older than an hour or from another school never counted.
        db.execute(legacy.AIUsageLog.__table__.delete()); db.commit()
        add_logs(db, teacher.school_id, teacher.id, "grading_assist", 5, age_minutes=61)
        add_logs(db, teacher.school_id + 999, teacher.id, "grading_assist", 5)
        legacy._ai_call(db, teacher, "grading_assist", "fine", student_ids=(sid,))
        # Any other (non-student) feature of the same school does count.
        db.execute(legacy.AIUsageLog.__table__.delete()); db.commit()
        add_logs(db, teacher.school_id, teacher.id, "teacher_reinforcement", 3)
        try:
            legacy._ai_call(db, teacher, "grading_assist", "blocked", student_ids=(sid,))
            raise SystemExit("expected a 429")
        except HTTPException as exc:
            assert exc.status_code == 429
print("OK")
''',
    )


def test_student_side_calls_do_not_use_up_the_teachers_hourly_budget(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
legacy.AI_HOURLY_LIMIT = 3

with TestClient(app):
    with legacy.SessionLocal() as db:
        teacher = prepare(db)
        sid = student_id_for(db, teacher)
        add_logs(db, teacher.school_id, 4242, "homework_help_solve", 40)
        add_logs(db, teacher.school_id, 4242, "homework_help_vision", 40)
        for i in range(3):
            legacy._ai_call(db, teacher, "grading_assist", f"p{i}", student_ids=(sid,))      # still the full budget of 3
        try:
            legacy._ai_call(db, teacher, "grading_assist", "p4", student_ids=(sid,))
            raise SystemExit("expected a 429")
        except HTTPException as exc:
            assert exc.status_code == 429 and exc.detail.startswith("本校 AI 调用已达到每小时 3 次")
        # Teacher-side homework features (parsing notices) are ordinary teacher features and do count.
        db.execute(legacy.AIUsageLog.__table__.delete()); db.commit()
        add_logs(db, teacher.school_id, teacher.id, "homework_parse", 3)
        try:
            legacy._ai_call(db, teacher, "grading_assist", "blocked", student_ids=(sid,))
            raise SystemExit("expected a 429")
        except HTTPException as exc:
            assert exc.status_code == 429
print("OK")
''',
    )


def test_rate_check_argument_is_optional_and_replaces_only_the_limit(tmp_path):
    run_isolated(
        tmp_path,
        COMMON
        + r'''
seen = []
original = legacy._ai_rate_check


def spy(db, school_id):
    seen.append(("default", school_id))
    return original(db, school_id)


legacy._ai_rate_check = spy

with TestClient(app):
    with legacy.SessionLocal() as db:
        teacher = prepare(db)
        sid = student_id_for(db, teacher)
        # No argument: the default school-wide check runs, once, with the school id.
        legacy._ai_call(db, teacher, "grading_assist", "a", student_ids=(sid,))
        assert seen == [("default", teacher.school_id)]

        # With an argument: only that check runs; the request and the log row are otherwise identical.
        custom = []
        legacy._ai_call(db, teacher, "homework_help_solve", "b", rate_check=lambda d, s: custom.append(s), student_ids=(sid,))
        assert custom == [teacher.school_id] and seen == [("default", teacher.school_id)]
        assert posts[-1]["json"] == {"model": "m", "messages": [{"role": "user", "content": "b"}], "temperature": 0.2}
        assert db.scalars(select(legacy.AIUsageLog)).all()[-1].feature == "homework_help_solve"

        # A custom check that refuses stops the call before any request or log row.
        def refuse(d, sid):
            raise HTTPException(429, "nope")
        n_posts, n_logs = len(posts), log_count(db)
        try:
            legacy._ai_call(db, teacher, "homework_help_solve", "c", rate_check=refuse, student_ids=(sid,))
            raise SystemExit("expected a 429")
        except HTTPException as exc:
            assert exc.status_code == 429 and exc.detail == "nope"
        assert len(posts) == n_posts and log_count(db) == n_logs
print("OK")
''',
    )
