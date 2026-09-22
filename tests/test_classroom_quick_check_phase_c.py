from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from changying.services.classroom_quick_check import (
    clean_ai_quick_check,
    quick_check_prompt,
    quick_check_summary,
)
from changying.web.v1 import v1_html
from changying.web.v1_classroom_execution import patch_v1_classroom_execution_html
from changying.web.v1_classroom_quick_check import (
    V1_CLASSROOM_QUICK_CHECK_MARKER,
    patch_v1_classroom_quick_check_html,
)
from changying.web.v1_classroom_review import patch_v1_classroom_review_html


ROOT = Path(__file__).resolve().parents[1]


def test_quick_check_helpers_keep_objective_feedback_small_and_explicit():
    row = clean_ai_quick_check(
        {
            "questions": [
                {
                    "question_type": "single_choice",
                    "text": "下列哪一项最合适？",
                    "options": ["甲", "乙", "丙", "丁"],
                    "correct_index": 1,
                    "explanation": "乙符合条件。",
                }
            ]
        },
        requested_type="single_choice",
        knowledge="句子衔接",
    )
    assert row is not None
    assert row["correct_index"] == 1
    assert row["options"] == ["甲", "乙", "丙", "丁"]

    summary = quick_check_summary(
        [
            {"selected_index": 1, "is_correct": True},
            {"selected_index": 0, "is_correct": False},
            {"selected_index": 1, "is_correct": True},
        ],
        option_count=4,
    )
    assert summary["responseCount"] == 3
    assert summary["correctCount"] == 2
    assert summary["accuracy"] == 67
    assert summary["distribution"][1]["count"] == 2



def test_quick_check_prompt_excludes_sibling_knowledge_focus():
    prompt = quick_check_prompt(
        grade=5,
        subject="语文",
        textbook="统编版",
        knowledge="习作修改",
        qtype="single_choice",
        excluded_knowledge=["病句辨析", "说明方法", "资料整合、阅读推断"],
    )
    assert "知识点：习作修改" in prompt
    assert "本堂课其他知识点（不得作为本题主要考查目标）：病句辨析、说明方法、资料整合、阅读推断" in prompt
    assert "不要把“本堂课其他知识点”作为题目的主要考查目标" in prompt

def test_v1_phase_c_patch_exposes_teacher_controlled_quick_check_and_student_page():
    html = patch_v1_classroom_quick_check_html(
        patch_v1_classroom_execution_html(
            patch_v1_classroom_review_html(v1_html())
        )
    )
    assert V1_CLASSROOM_QUICK_CHECK_MARKER in html
    assert "/v1/classroom-quick-checks" in html
    assert "AI生成草稿" in html
    assert "重新AI生成草稿" in html
    assert "cy-q-regenerate" in html
    assert "重新AI生成会覆盖当前草稿内容，但不会向学生开放" in html
    assert "timeoutMs:90000" in html
    assert "手工建立草稿" in html
    assert "教师确认并开始检测" in html
    assert "根据反馈继续讲解" in html
    assert "再生成一轮检测" in html
    assert "['complete','reteach'].includes(q.decision)" in html
    assert "不会自动加分" in html
    assert "不会自动改写你的长期知识掌握记录" in html


def test_runtime_classroom_quick_check_phase_c(tmp_path):
    db_path = tmp_path / "classroom-quick-check.sqlite3"
    script = r"""
import json
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select

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

        q = legacy.Question(
            school_id=teacher.school_id,
            grade=5,
            subject="数学",
            textbook="人教版",
            semester="上册",
            unit="小数乘法",
            knowledge="小数乘法",
            text="0.4×3 的结果是？",
            options_json=json.dumps(["0.12", "1.2", "12", "120"], ensure_ascii=False),
            correct_index=1,
            explanation="0.4乘3等于1.2",
            question_type="single_choice",
            answer_json="{}",
            figure_json="{}",
            creator_id=teacher.id,
        )
        db.add(q)
        db.flush()
        paper = legacy.Paper(
            school_id=teacher.school_id,
            title="课堂源练习",
            grade=5,
            subject="数学",
            textbook="人教版",
            unit="小数乘法",
            question_ids_json=json.dumps([q.id]),
            teacher_id=teacher.id,
        )
        db.add(paper)
        db.flush()
        assignment = legacy.Assignment(
            school_id=teacher.school_id,
            title="小数乘法课堂练习",
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
                score=100,
                correct=1,
                total=1,
                answers_json=json.dumps(
                    [{"question_id": q.id, "selected_index": 1, "correct": True}],
                    ensure_ascii=False,
                ),
            )
        )
        handouts = legacy.Base.metadata.tables["classroom_review_handouts"]
        db.execute(
            handouts.insert().values(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                class_id=cls.id,
                teacher_id=teacher.id,
                title="小数乘法课堂复盘讲义",
                selected_knowledge_json=json.dumps(["小数乘法"], ensure_ascii=False),
                selected_question_ids_json=json.dumps([q.id]),
                teacher_notes="",
                content_text="讲解小数乘法的计算方法。",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        school_id = teacher.school_id
        student_id = student.id
        before_points = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.PointLedger)
                .where(
                    legacy.PointLedger.school_id == school_id,
                    legacy.PointLedger.student_id == student_id,
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
                    legacy.LearningEvidenceEvent.student_id == student_id,
                )
            )
            or 0
        )
        db.commit()
        aid = assignment.id

    created = client.post(
        f"/teacher/assignments/{aid}/classroom-session",
        headers=th,
        json={},
    )
    assert created.status_code == 200, created.text
    sid = created.json()["session"]["id"]
    segid = created.json()["segments"][0]["id"]

    started = client.post(
        f"/teacher/classroom-sessions/{sid}/state",
        headers=th,
        json={"status": "active"},
    )
    assert started.status_code == 200, started.text

    explaining = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/start",
        headers=th,
    )
    assert explaining.status_code == 200, explaining.text
    completed = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/complete",
        headers=th,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["segments"][0]["status"] == "completed"

    draft = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/quick-checks/draft",
        headers=th,
        json={"question_type": "single_choice", "use_ai": False},
    )
    assert draft.status_code == 200, draft.text
    check_id = draft.json()["id"]
    assert draft.json()["status"] == "draft"
    assert draft.json()["questionText"] == ""

    edited = client.put(
        f"/teacher/classroom-sessions/{sid}/quick-checks/{check_id}",
        headers=th,
        json={
            "question_text": "0.6×4 的结果是？",
            "options": ["0.24", "2.4", "24", "240"],
            "correct_index": 1,
            "explanation": "6×4=24，再点一位小数得到2.4。",
        },
    )
    assert edited.status_code == 200, edited.text

    opened = client.post(
        f"/teacher/classroom-sessions/{sid}/quick-checks/{check_id}/state",
        headers=th,
        json={"status": "open"},
    )
    assert opened.status_code == 200, opened.text
    state = client.get(f"/teacher/classroom-sessions/{sid}", headers=th).json()
    assert state["segments"][0]["status"] == "checking"

    student_open = client.get("/student/classroom-quick-checks", headers=sh)
    assert student_open.status_code == 200, student_open.text
    visible = next(x for x in student_open.json() if x["id"] == check_id)
    assert visible["status"] == "open"
    assert visible["correctIndex"] is None
    assert visible["stats"] is None

    answered = client.post(
        f"/student/classroom-quick-checks/{check_id}/respond",
        headers=sh,
        json={"selected_index": 1},
    )
    assert answered.status_code == 200, answered.text

    teacher_feedback = client.get(
        f"/teacher/classroom-sessions/{sid}/quick-checks",
        headers=th,
    )
    assert teacher_feedback.status_code == 200, teacher_feedback.text
    feedback = next(x for x in teacher_feedback.json() if x["id"] == check_id)
    assert feedback["stats"]["responseCount"] == 1
    assert feedback["stats"]["accuracy"] == 100
    assert feedback["responses"][0]["studentID"] == student_id
    assert feedback["responses"][0]["isCorrect"] is True

    reveal = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/reveal",
        headers=th,
        json={
            "reveal_distribution": True,
            "reveal_correct_answer": True,
            "reveal_explanation": True,
        },
    )
    assert reveal.status_code == 200, reveal.text

    closed = client.post(
        f"/teacher/classroom-sessions/{sid}/quick-checks/{check_id}/state",
        headers=th,
        json={"status": "closed"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["stats"]["accuracy"] == 100
    state = client.get(f"/teacher/classroom-sessions/{sid}", headers=th).json()
    assert state["segments"][0]["status"] == "reviewed"

    student_closed = client.get("/student/classroom-quick-checks", headers=sh)
    visible_closed = next(x for x in student_closed.json() if x["id"] == check_id)
    assert visible_closed["correctIndex"] == 1
    assert visible_closed["myResponse"]["isCorrect"] is True
    assert visible_closed["stats"]["accuracy"] == 100
    assert "6×4=24" in visible_closed["explanation"]

    reteach = client.post(
        f"/teacher/classroom-sessions/{sid}/quick-checks/{check_id}/decision",
        headers=th,
        json={"decision": "reteach"},
    )
    assert reteach.status_code == 200, reteach.text
    assert reteach.json()["segmentStatus"] == "planned"

    explaining2 = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/start",
        headers=th,
    )
    assert explaining2.status_code == 200, explaining2.text
    completed2 = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/complete",
        headers=th,
    )
    assert completed2.status_code == 200, completed2.text

    draft2 = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/quick-checks/draft",
        headers=th,
        json={"question_type": "true_false", "use_ai": False},
    )
    assert draft2.status_code == 200, draft2.text
    check2 = draft2.json()["id"]
    edited2 = client.put(
        f"/teacher/classroom-sessions/{sid}/quick-checks/{check2}",
        headers=th,
        json={
            "question_text": "0.5×2=1。",
            "options": ["正确", "错误"],
            "correct_index": 0,
            "explanation": "0.5的2倍是1。",
        },
    )
    assert edited2.status_code == 200, edited2.text
    opened2 = client.post(
        f"/teacher/classroom-sessions/{sid}/quick-checks/{check2}/state",
        headers=th,
        json={"status": "open"},
    )
    assert opened2.status_code == 200, opened2.text
    answered2 = client.post(
        f"/student/classroom-quick-checks/{check2}/respond",
        headers=sh,
        json={"selected_index": 0},
    )
    assert answered2.status_code == 200, answered2.text
    closed2 = client.post(
        f"/teacher/classroom-sessions/{sid}/quick-checks/{check2}/state",
        headers=th,
        json={"status": "closed"},
    )
    assert closed2.status_code == 200, closed2.text

    final_decision = client.post(
        f"/teacher/classroom-sessions/{sid}/quick-checks/{check2}/decision",
        headers=th,
        json={"decision": "complete"},
    )
    assert final_decision.status_code == 200, final_decision.text
    assert final_decision.json()["segmentStatus"] == "completed"

    done = client.post(
        f"/teacher/classroom-sessions/{sid}/state",
        headers=th,
        json={"status": "completed"},
    )
    assert done.status_code == 200, done.text

    with legacy.SessionLocal() as db:
        tables = legacy.Base.metadata.tables
        assert "classroom_quick_checks" in tables
        assert "classroom_quick_check_responses" in tables
        check_count = int(
            db.scalar(select(func.count()).select_from(tables["classroom_quick_checks"]))
            or 0
        )
        response_count = int(
            db.scalar(
                select(func.count()).select_from(tables["classroom_quick_check_responses"])
            )
            or 0
        )
        assert check_count == 2
        assert response_count == 2

        after_points = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.PointLedger)
                .where(
                    legacy.PointLedger.school_id == school_id,
                    legacy.PointLedger.student_id == student_id,
                )
            )
            or 0
        )
        after_evidence = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.LearningEvidenceEvent)
                .where(
                    legacy.LearningEvidenceEvent.school_id == school_id,
                    legacy.LearningEvidenceEvent.student_id == student_id,
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
