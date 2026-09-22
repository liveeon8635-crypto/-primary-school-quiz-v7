from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from changying.services.classroom_execution import (
    can_start_segment,
    candidate_signals,
    candidate_sort_key,
    presenter_transition_allowed,
    segment_status_for_mode,
    session_transition_allowed,
)
from changying.web.v1 import v1_html
from changying.web.v1_classroom_execution import (
    V1_CLASSROOM_EXECUTION_MARKER,
    patch_v1_classroom_execution_html,
)


ROOT = Path(__file__).resolve().parents[1]


def test_live_classroom_state_machine_requires_presenter_consent():
    assert session_transition_allowed("planned", "active")
    assert session_transition_allowed("active", "paused")
    assert not session_transition_allowed("completed", "active")
    assert segment_status_for_mode("student") == "selecting_presenter"
    assert segment_status_for_mode("teacher") == "planned"
    assert segment_status_for_mode("skipped") == "completed"
    assert presenter_transition_allowed("invited", "accepted")
    assert presenter_transition_allowed("invited", "declined")
    assert not presenter_transition_allowed("declined", "presenting")

    ok, reason = can_start_segment(
        session_status="active",
        segment_status="selecting_presenter",
        mode="student",
        presenter_status="invited",
    )
    assert not ok
    assert "学生本人确认" in reason

    ok, _ = can_start_segment(
        session_status="active",
        segment_status="selecting_presenter",
        mode="student",
        presenter_status="accepted",
    )
    assert ok


def test_private_candidate_policy_uses_positive_signals_not_weak_labels():
    strong = {
        "id": 1,
        "name": "甲",
        "sourceExerciseCorrect": True,
        "priorSuccessEvidence": 2,
        "priorPresentationCount": 0,
    }
    other = {
        "id": 2,
        "name": "乙",
        "sourceExerciseCorrect": False,
        "priorSuccessEvidence": 0,
        "priorPresentationCount": 0,
    }
    assert sorted([other, strong], key=candidate_sort_key)[0]["id"] == 1
    text = "；".join(
        candidate_signals(
            source_exercise_correct=True,
            prior_success_evidence=2,
            prior_presentation_count=0,
        )
    )
    assert "正确作答" in text
    assert "成功学习证据" in text
    assert "薄弱" not in text
    assert "排名" not in text


def test_v1_execution_patch_contains_teacher_and_student_consent_pages():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert V1_CLASSROOM_EXECUTION_MARKER in html
    assert "/v1/classroom-execution" in html
    assert "/v1/classroom-invitations" in html
    assert "学生讲解必须本人确认" in html
    assert "你可以自主选择接受或婉拒" in html
    assert "不是公开排名，也不会自动指定学生" in html
    assert "婉拒不会扣分" in html
    assert "navigate('/v1/classroom-review?assignment='+s.sourceAssignmentID)" in html
    assert "status:'completed'" in html
    assert "完成本堂课并进入课堂复盘" in html
    assert "cy-session-complete-bottom" in html
    assert "segs.every(x=>x.status==='completed')" in html
    assert "进入课堂执行（最近课堂）" in html
    assert "新开一堂课" in html
    assert "force_new:false" in html
    assert "force_new:true" in html
    assert "取消未开始课堂并返回复盘" in html
    assert "interaction?.session?.id" in html

def test_runtime_phase_ab_classroom_execution(tmp_path):
    db_path = tmp_path / "classroom-execution.sqlite3"
    script = r"""
import json
from fastapi.testclient import TestClient
import app_v924 as legacy
from app import app


def headers_for(db, username):
    user = db.scalar(legacy.select(legacy.User).where(legacy.User.username == username))
    sec = legacy.security_for(db, user)
    sec.must_change_password = False
    db.commit()
    return {"Authorization": "Bearer " + legacy.make_token(user, sec, False)}, user


with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        th, teacher = headers_for(db, "teacher1")
        sh, student = headers_for(db, "student1")
        cls = db.scalar(
            legacy.select(legacy.SchoolClass).where(
                legacy.SchoolClass.school_id == teacher.school_id,
                legacy.SchoolClass.teacher_id == teacher.id,
            )
        )
        q = legacy.Question(
            school_id=teacher.school_id,
            grade=5,
            subject="语文",
            textbook="统编版（人民教育出版社）",
            semester="上册",
            unit="全册基础",
            knowledge="句子衔接",
            text="选择最连贯的一项",
            options_json=json.dumps(["甲","乙","丙","丁"], ensure_ascii=False),
            correct_index=0,
            explanation="解析",
            question_type="single_choice",
            answer_json="{}",
            figure_json="{}",
            creator_id=teacher.id,
        )
        db.add(q); db.flush()
        paper = legacy.Paper(
            school_id=teacher.school_id,
            title="互动课堂源练习",
            grade=5,
            subject="语文",
            textbook="统编版（人民教育出版社）",
            unit="全册基础",
            question_ids_json=json.dumps([q.id]),
            teacher_id=teacher.id,
        )
        db.add(paper); db.flush()
        assignment = legacy.Assignment(
            school_id=teacher.school_id,
            title="互动课堂练习",
            class_id=cls.id,
            paper_id=paper.id,
            due_date="2026-09-30",
        )
        db.add(assignment); db.flush()
        db.add(legacy.AssignmentRecipient(
            school_id=teacher.school_id,
            assignment_id=assignment.id,
            class_id=cls.id,
            student_id=student.id,
            source="assignment",
        ))
        db.add(legacy.Submission(
            school_id=teacher.school_id,
            assignment_id=assignment.id,
            student_id=student.id,
            title=assignment.title,
            score=100,
            correct=1,
            total=1,
            answers_json=json.dumps([
                {"question_id": q.id, "selected_index": 0, "correct": True}
            ], ensure_ascii=False),
        ))
        handouts = legacy.Base.metadata.tables["classroom_review_handouts"]
        db.execute(
            handouts.insert().values(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                class_id=cls.id,
                teacher_id=teacher.id,
                title="互动课堂讲义",
                selected_knowledge_json=json.dumps(["句子衔接"], ensure_ascii=False),
                selected_question_ids_json=json.dumps([q.id]),
                teacher_notes="",
                content_text="句子衔接讲义正文",
            )
        )
        db.commit()
        aid = assignment.id
        student_id = student.id

    created = client.post(f"/teacher/assignments/{aid}/classroom-session", headers=th, json={})
    assert created.status_code == 200, created.text
    data = created.json()
    sid = data["session"]["id"]
    assert data["session"]["status"] == "planned"
    assert len(data["segments"]) == 1
    segid = data["segments"][0]["id"]
    assert data["segments"][0]["knowledgeKey"] == "句子衔接"
    assert data["segments"][0]["baselineAccuracy"] == 100

    started = client.post(f"/teacher/classroom-sessions/{sid}/state", headers=th, json={"status": "active"})
    assert started.status_code == 200, started.text
    assert started.json()["session"]["status"] == "active"

    mode = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/mode",
        headers=th,
        json={"mode": "student"},
    )
    assert mode.status_code == 200, mode.text

    state = client.get(f"/teacher/classroom-sessions/{sid}", headers=th)
    assert state.status_code == 200
    candidates = client.get(f"/teacher/classroom-sessions/{sid}/segments/{segid}/candidates", headers=th)
    assert candidates.status_code == 200, candidates.text
    candidate = next(x for x in candidates.json() if x["id"] == student_id)
    assert candidate["sourceExerciseCorrect"] is True
    assert any("正确作答" in x for x in candidate["signals"])

    invited = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/invite",
        headers=th,
        json={"student_id": student_id, "presenter_type": "student"},
    )
    assert invited.status_code == 200, invited.text
    turnid = invited.json()["segments"][0]["presenterTurn"]["id"]

    blocked = client.post(f"/teacher/classroom-sessions/{sid}/segments/{segid}/start", headers=th)
    assert blocked.status_code == 400
    assert "学生本人确认" in blocked.text

    invitations = client.get("/student/classroom-invitations", headers=sh)
    assert invitations.status_code == 200, invitations.text
    invite = next(x for x in invitations.json() if x["id"] == turnid)
    assert invite["knowledgeKey"] == "句子衔接"
    assert invite["status"] == "invited"

    accepted = client.post(
        f"/student/classroom-invitations/{turnid}/respond",
        headers=sh,
        json={"response": "accepted"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"

    explaining = client.post(f"/teacher/classroom-sessions/{sid}/segments/{segid}/start", headers=th)
    assert explaining.status_code == 200, explaining.text

    state = client.get(f"/teacher/classroom-sessions/{sid}", headers=th).json()
    assert state["segments"][0]["status"] == "explaining"
    assert state["segments"][0]["presenterTurn"]["status"] == "presenting"
    event_types = [x["eventType"] for x in state["events"]]
    assert "presenter.invited" in event_types
    assert "presenter.accepted" in event_types
    assert "explanation.started" in event_types

    completed_seg = client.post(f"/teacher/classroom-sessions/{sid}/segments/{segid}/complete", headers=th)
    assert completed_seg.status_code == 200, completed_seg.text

    done = client.post(f"/teacher/classroom-sessions/{sid}/state", headers=th, json={"status": "completed"})
    assert done.status_code == 200, done.text
    assert done.json()["session"]["status"] == "completed"

    reopened = client.post(
        f"/teacher/assignments/{aid}/classroom-session",
        headers=th,
        json={},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["created"] is False
    assert reopened.json()["session"]["id"] == sid
    assert reopened.json()["session"]["status"] == "completed"

    explicit_new = client.post(
        f"/teacher/assignments/{aid}/classroom-session",
        headers=th,
        json={"force_new": True},
    )
    assert explicit_new.status_code == 200, explicit_new.text
    assert explicit_new.json()["created"] is True
    assert explicit_new.json()["session"]["id"] != sid
    assert explicit_new.json()["session"]["status"] == "planned"
    new_sid = explicit_new.json()["session"]["id"]

    cancelled = client.post(
        f"/teacher/classroom-sessions/{new_sid}/state",
        headers=th,
        json={"status": "cancelled"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["session"]["status"] == "cancelled"

    with legacy.SessionLocal() as db:
        tables = legacy.Base.metadata.tables
        assert "classroom_sessions" in tables
        assert "classroom_segments" in tables
        assert "classroom_presenter_turns" in tables
        assert "classroom_events" in tables
        session_count = db.scalar(legacy.select(legacy.func.count()).select_from(tables["classroom_sessions"]))
        event_count = db.scalar(legacy.select(legacy.func.count()).select_from(tables["classroom_events"]))
        assert session_count == 2
        assert event_count >= 7
"""

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["ENABLE_DEMO_SEED"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
