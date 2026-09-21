from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from changying.services.classroom_execution import (
    can_complete_session,
    can_start_segment,
    candidate_signals,
    presenter_transition_allowed,
    segment_status_for_mode,
    session_transition_allowed,
)
from changying.web.v1 import v1_html
from changying.web.v1_classroom_review import patch_v1_classroom_review_html
from changying.web.v1_classroom_execution import (
    V1_CLASSROOM_EXECUTION_MARKER,
    patch_v1_classroom_execution_html,
)


ROOT = Path(__file__).resolve().parents[1]


def test_live_classroom_state_machine_keeps_teacher_control_and_student_consent():
    assert session_transition_allowed("planned", "active")
    assert session_transition_allowed("active", "paused")
    assert session_transition_allowed("paused", "active")
    assert not session_transition_allowed("completed", "active")

    assert segment_status_for_mode("teacher") == "planned"
    assert segment_status_for_mode("student") == "selecting_presenter"
    assert segment_status_for_mode("co_teach") == "selecting_presenter"
    assert segment_status_for_mode("skipped") == "completed"

    ok, reason = can_start_segment(
        session_status="active",
        segment_status="selecting_presenter",
        mode="student",
        presenter_status="invited",
    )
    assert ok is False
    assert "学生本人确认" in reason

    ok, _ = can_start_segment(
        session_status="active",
        segment_status="selecting_presenter",
        mode="student",
        presenter_status="accepted",
    )
    assert ok is True

    assert presenter_transition_allowed("invited", "accepted")
    assert presenter_transition_allowed("invited", "declined")
    assert not presenter_transition_allowed("declined", "presenting")
    assert can_complete_session(["completed", "completed"])
    assert not can_complete_session(["completed", "planned"])


def test_candidate_signals_are_private_evidence_not_an_opaque_score():
    signals = candidate_signals(
        source_exercise_correct=True,
        prior_success_evidence=2,
        prior_presentation_count=0,
    )
    assert "本次练习该知识点有正确作答" in signals
    assert any("成功学习证据" in x for x in signals)
    assert any("暂无已完成" in x for x in signals)


def test_v1_connects_review_to_teacher_execution_and_student_consent():
    html = patch_v1_classroom_execution_html(
        patch_v1_classroom_review_html(v1_html())
    )
    assert V1_CLASSROOM_EXECUTION_MARKER in html
    assert "进入课堂执行" in html
    assert "/v1/classroom-execution" in html
    assert "/v1/classroom-invitations" in html
    assert "学生讲解必须本人确认" in html
    assert "候选信息只对教师可见，不是公开排名" in html
    assert "婉拒不会扣分" in html
    assert "Phase C 接入即时检测后才真正向学生端展示" in html


def test_runtime_interactive_classroom_phase_ab(tmp_path):
    db_path = tmp_path / "interactive-classroom.sqlite3"
    script = r"""
import json
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select, func

import app_v924 as legacy
from app import app


def auth(db, username):
    user = db.scalar(select(legacy.User).where(legacy.User.username == username))
    sec = legacy.security_for(db, user)
    sec.must_change_password = False
    db.commit()
    return user, {"Authorization": "Bearer " + legacy.make_token(user, sec, False)}


with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        teacher, th = auth(db, "teacher1")
        student, sh = auth(db, "student1")
        cls = db.scalar(
            select(legacy.SchoolClass).where(
                legacy.SchoolClass.school_id == teacher.school_id,
                legacy.SchoolClass.teacher_id == teacher.id,
            )
        )
        assert cls is not None

        membership = db.scalar(
            select(legacy.ClassStudent).where(
                legacy.ClassStudent.class_id == cls.id,
                legacy.ClassStudent.student_id == student.id,
            )
        )
        if membership is None:
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=student.id))
            db.flush()

        questions = []
        for knowledge, text in [
            ("句子衔接", "选择衔接最自然的一项"),
            ("关联词运用", "选择最合适的关联词"),
        ]:
            q = legacy.Question(
                school_id=teacher.school_id,
                grade=5,
                subject="语文",
                textbook="统编版（人民教育出版社）",
                semester="上册",
                unit="全册基础",
                knowledge=knowledge,
                text=text,
                options_json=json.dumps(["A", "B", "C", "D"], ensure_ascii=False),
                correct_index=0,
                explanation="解析",
                question_type="single_choice",
                answer_json="{}",
                figure_json="{}",
                creator_id=teacher.id,
            )
            db.add(q)
            db.flush()
            questions.append(q)

        paper = legacy.Paper(
            school_id=teacher.school_id,
            title="互动课堂测试卷",
            grade=5,
            subject="语文",
            textbook="统编版（人民教育出版社）",
            unit="全册基础",
            question_ids_json=json.dumps([q.id for q in questions]),
            teacher_id=teacher.id,
        )
        db.add(paper)
        db.flush()

        assignment = legacy.Assignment(
            school_id=teacher.school_id,
            title="互动课堂源练习",
            class_id=cls.id,
            paper_id=paper.id,
            due_date="2026-09-30",
        )
        db.add(assignment)
        db.flush()
        db.add(
            legacy.AssignmentRecipient(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                class_id=cls.id,
                student_id=student.id,
                source="assignment",
            )
        )
        db.add(
            legacy.Submission(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                student_id=student.id,
                title=assignment.title,
                score=50,
                correct=1,
                total=2,
                answers_json=json.dumps(
                    [
                        {
                            "question_id": questions[0].id,
                            "selected_index": 0,
                            "correct": True,
                        },
                        {
                            "question_id": questions[1].id,
                            "selected_index": 1,
                            "correct": False,
                        },
                    ],
                    ensure_ascii=False,
                ),
            )
        )
        db.flush()

        handouts = legacy.Base.metadata.tables["classroom_review_handouts"]
        handout_id = db.execute(
            handouts.insert()
            .values(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                class_id=cls.id,
                teacher_id=teacher.id,
                title="互动课堂复盘讲义",
                selected_knowledge_json=json.dumps(
                    ["句子衔接", "关联词运用"], ensure_ascii=False
                ),
                selected_question_ids_json=json.dumps(
                    [questions[0].id, questions[1].id]
                ),
                teacher_notes="教师已确认讲义",
                content_text="已确认的课堂复盘讲义正文",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            .returning(handouts.c.id)
        ).scalar_one()

        before_points = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.PointLedger)
                .where(
                    legacy.PointLedger.school_id == school_id,
                    legacy.PointLedger.student_id == student.id,
                )
            )
            or 0
        )
        before_evidence = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.LearningEvidenceEvent)
                .where(
                    legacy.LearningEvidenceEvent.school_id == school_id,
                    legacy.LearningEvidenceEvent.student_id == student.id,
                )
            )
            or 0
        )
        school_id = teacher.school_id
        db.commit()
        aid = assignment.id
        sid_student = student.id

    created = client.post(
        f"/teacher/assignments/{aid}/classroom-session",
        headers=th,
        json={},
    )
    assert created.status_code == 200, created.text
    payload = created.json()
    assert payload["created"] is True
    sid = payload["session"]["id"]
    assert payload["session"]["handoutID"] == handout_id
    assert len(payload["segments"]) == 2
    assert payload["segments"][0]["knowledgeKey"] == "句子衔接"
    assert payload["segments"][0]["baselineAccuracy"] == 100
    assert payload["segments"][1]["baselineAccuracy"] == 0

    repeated = client.post(
        f"/teacher/assignments/{aid}/classroom-session",
        headers=th,
        json={},
    )
    assert repeated.status_code == 200
    assert repeated.json()["created"] is False
    assert repeated.json()["session"]["id"] == sid

    started = client.post(
        f"/teacher/classroom-sessions/{sid}/state",
        headers=th,
        json={"status": "active"},
    )
    assert started.status_code == 200, started.text
    seg1 = started.json()["segments"][0]
    seg2 = started.json()["segments"][1]

    mode = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{seg1['id']}/mode",
        headers=th,
        json={"mode": "student"},
    )
    assert mode.status_code == 200, mode.text
    assert mode.json()["segments"][0]["status"] == "selecting_presenter"

    candidates = client.get(
        f"/teacher/classroom-sessions/{sid}/segments/{seg1['id']}/candidates",
        headers=th,
    )
    assert candidates.status_code == 200, candidates.text
    candidate = next(x for x in candidates.json() if x["id"] == sid_student)
    assert candidate["sourceExerciseCorrect"] is True
    assert candidate["sourceAccuracy"] if "sourceAccuracy" in candidate else True
    assert "candidateScore" not in candidate

    invited = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{seg1['id']}/invite",
        headers=th,
        json={
            "student_id": sid_student,
            "presenter_type": "student",
            "note": "愿意给大家讲一下你的思路吗？",
        },
    )
    assert invited.status_code == 200, invited.text
    turn_id = invited.json()["segments"][0]["presenterTurn"]["id"]

    blocked_start = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{seg1['id']}/start",
        headers=th,
    )
    assert blocked_start.status_code == 400
    assert "确认" in blocked_start.text

    student_view = client.get("/student/classroom-invitations", headers=sh)
    assert student_view.status_code == 200, student_view.text
    visible = next(x for x in student_view.json() if x["id"] == turn_id)
    assert visible["knowledgeKey"] == "句子衔接"
    assert visible["note"] == "愿意给大家讲一下你的思路吗？"

    declined = client.post(
        f"/student/classroom-invitations/{turn_id}/respond",
        headers=sh,
        json={"response": "declined"},
    )
    assert declined.status_code == 200, declined.text
    assert declined.json()["status"] == "declined"

    duplicate = client.post(
        f"/student/classroom-invitations/{turn_id}/respond",
        headers=sh,
        json={"response": "accepted"},
    )
    assert duplicate.status_code == 400

    invited2 = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{seg1['id']}/invite",
        headers=th,
        json={
            "student_id": sid_student,
            "presenter_type": "student",
            "note": "如果现在愿意，可以再次确认。",
        },
    )
    assert invited2.status_code == 200, invited2.text
    turn2 = invited2.json()["segments"][0]["presenterTurn"]["id"]
    assert turn2 != turn_id

    accepted = client.post(
        f"/student/classroom-invitations/{turn2}/respond",
        headers=sh,
        json={"response": "accepted"},
    )
    assert accepted.status_code == 200, accepted.text

    presenting = client.post(
        f"/teacher/classroom-sessions/{sid}/presenter-turns/{turn2}/state",
        headers=th,
        json={"status": "presenting"},
    )
    assert presenting.status_code == 200, presenting.text
    assert presenting.json()["segments"][0]["status"] == "explaining"
    assert presenting.json()["segments"][0]["presenterTurn"]["status"] == "presenting"

    completed_seg1 = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{seg1['id']}/complete",
        headers=th,
    )
    assert completed_seg1.status_code == 200, completed_seg1.text
    assert completed_seg1.json()["segments"][0]["status"] == "completed"
    assert completed_seg1.json()["segments"][0]["presenterTurn"]["status"] == "completed"

    skipped = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{seg2['id']}/mode",
        headers=th,
        json={"mode": "skipped"},
    )
    assert skipped.status_code == 200, skipped.text
    assert skipped.json()["segments"][1]["status"] == "completed"

    finished = client.post(
        f"/teacher/classroom-sessions/{sid}/state",
        headers=th,
        json={"status": "completed"},
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["session"]["status"] == "completed"
    event_types = [x["eventType"] for x in finished.json()["events"]]
    assert "presenter.invited" in event_types
    assert "presenter.accepted" in event_types
    assert "presenter.declined" in event_types
    assert "presenter.completed" in event_types
    assert "segment.completed" in event_types

    after_student = client.get("/student/classroom-invitations", headers=sh)
    assert after_student.status_code == 200
    assert after_student.json() == []

    with legacy.SessionLocal() as db:
        after_points = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.PointLedger)
                .where(
                    legacy.PointLedger.school_id == teacher.school_id,
                    legacy.PointLedger.student_id == sid_student,
                )
            )
            or 0
        )
        after_evidence = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.LearningEvidenceEvent)
                .where(
                    legacy.LearningEvidenceEvent.school_id == teacher.school_id,
                    legacy.LearningEvidenceEvent.student_id == sid_student,
                )
            )
            or 0
        )
        assert after_points == before_points
        assert after_evidence == before_evidence
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
