from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import json

from changying.services.classroom_review import (
    build_anonymized_handout_prompt,
    classroom_review_summary,
)
from changying.web.v1_classroom_review import (
    V1_CLASSROOM_REVIEW_MARKER,
    patch_v1_classroom_review_html,
)
from changying.web.v1 import v1_html


ROOT = Path(__file__).resolve().parents[1]


def q(qid, knowledge, text, correct_index=0):
    return SimpleNamespace(
        id=qid,
        knowledge=knowledge,
        unit="第一单元",
        text=text,
        question_type="single_choice",
        options_json=json.dumps(["A", "B", "C", "D"], ensure_ascii=False),
        correct_index=correct_index,
        answer_json="{}",
    )


def sub(sid, score, answers):
    from datetime import datetime

    return SimpleNamespace(
        id=sid,
        student_id=sid,
        score=score,
        correct=sum(1 for x in answers if x["correct"]),
        total=len(answers),
        answers_json=json.dumps(answers, ensure_ascii=False),
        submitted_at=datetime(2026, 9, 22, 10, sid),
    )


def test_classroom_review_aggregates_class_facts_without_long_term_inference():
    assignment = SimpleNamespace(id=9, title="课堂练习", due_date="2026-09-22", created_at=None)
    class_row = SimpleNamespace(id=2, name="五年级1班", grade=5)
    paper = SimpleNamespace(id=3, title="第一单元", subject="语文", textbook="统编版", unit="第一单元")
    recipients = [
        SimpleNamespace(id=1, name="学生甲"),
        SimpleNamespace(id=2, name="学生乙"),
        SimpleNamespace(id=3, name="学生丙"),
    ]
    questions = [
        q(11, "句子衔接", "选择最连贯的句子", 1),
        q(12, "关联词运用", "选择合适的关联词", 0),
    ]
    submissions = [
        sub(1, 100, [
            {"question_id": 11, "selected_index": 1, "correct": True},
            {"question_id": 12, "selected_index": 0, "correct": True},
        ]),
        sub(2, 50, [
            {"question_id": 11, "selected_index": 0, "correct": False},
            {"question_id": 12, "selected_index": 0, "correct": True},
        ]),
    ]

    result = classroom_review_summary(
        assignment=assignment,
        class_row=class_row,
        paper=paper,
        recipients=recipients,
        submissions=submissions,
        questions=questions,
    )

    assert result["recipientCount"] == 3
    assert result["completedCount"] == 2
    assert result["pendingCount"] == 1
    assert result["completionRate"] == 67
    assert result["averageScore"] == 75
    assert result["knowledgeStats"][0]["knowledge"] == "句子衔接"
    assert result["knowledgeStats"][0]["accuracy"] == 50
    assert result["commonErrors"][0]["questionID"] == 11
    assert result["commonErrors"][0]["wrongRate"] == 50
    assert result["handoutReady"] is True
    assert "阶段数据" in result["dataNotice"]


def test_handout_prompt_is_anonymized_and_excludes_student_rows():
    summary = {
        "class": {"id": 2, "name": "五年级1班", "grade": 5},
        "paper": {"subject": "语文", "textbook": "统编版", "unit": "第一单元"},
        "recipientCount": 3,
        "completedCount": 2,
        "completionRate": 67,
        "averageScore": 75,
        "knowledgeStats": [{"knowledge": "句子衔接", "accuracy": 50, "answered": 2}],
        "commonErrors": [{"questionID": 11, "knowledge": "句子衔接", "problem": "测试题", "wrongRate": 50}],
        "students": [
            {"studentID": 12345, "studentName": "绝不能进入AI提示词", "score": 50}
        ],
    }
    prompt = build_anonymized_handout_prompt(
        summary,
        selected_knowledge=["句子衔接"],
        selected_question_ids=[11],
        teacher_notes="重点讲方法",
    )
    assert "绝不能进入AI提示词" not in prompt
    assert "12345" not in prompt
    assert "句子衔接" in prompt
    assert "重点讲方法" in prompt
    assert "不出现学生姓名" in prompt


def test_v1_exposes_classroom_review_entry_and_teacher_decision_language():
    html = patch_v1_classroom_review_html(v1_html())
    assert V1_CLASSROOM_REVIEW_MARKER in html
    assert "课堂复盘" in html
    assert "/v1/classroom-review" in html
    assert "先看班级事实，再由教师决定讲什么、是否生成讲义" in html
    assert "不会自动发布给学生" in html
    assert "不会把学生姓名送入 AI" in html
    assert "/teacher/classroom-reviews/assignments" in html
    assert "/class-review/handout-generate" in html


def test_runtime_classroom_review_full_loop(tmp_path):
    db_path = tmp_path / "classroom-review.sqlite3"
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
    return {"Authorization": "Bearer " + legacy.make_token(user, sec, False)}


with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        th = headers_for(db, "teacher1")
        teacher = db.scalar(legacy.select(legacy.User).where(legacy.User.username == "teacher1"))
        student1 = db.scalar(legacy.select(legacy.User).where(legacy.User.username == "student1"))
        cls = db.scalar(
            legacy.select(legacy.SchoolClass).where(
                legacy.SchoolClass.school_id == teacher.school_id,
                legacy.SchoolClass.teacher_id == teacher.id,
            )
        )
        student2 = legacy.User(
            school_id=teacher.school_id,
            username="review_student_2",
            password_hash=legacy.hash_password("Review1234"),
            name="复盘学生乙",
            role="student",
            grade=cls.grade,
        )
        db.add(student2); db.flush()
        db.add(legacy.UserSecurity(user_id=student2.id, must_change_password=False, failed_login_count=0))
        db.add(legacy.ClassStudent(class_id=cls.id, student_id=student2.id))

        questions = []
        for i, knowledge in enumerate(["句子衔接", "关联词运用"], start=1):
            row = legacy.Question(
                school_id=teacher.school_id,
                grade=5,
                subject="语文",
                textbook="统编版（人民教育出版社）",
                semester="上册",
                unit="全册基础",
                knowledge=knowledge,
                text=f"课堂复盘测试题{i}",
                options_json=json.dumps(["A", "B", "C", "D"], ensure_ascii=False),
                correct_index=0,
                explanation="解析",
                question_type="single_choice",
                answer_json="{}",
                figure_json="{}",
                creator_id=teacher.id,
            )
            db.add(row); db.flush(); questions.append(row)
        paper = legacy.Paper(
            school_id=teacher.school_id,
            title="课堂复盘试卷",
            grade=5,
            subject="语文",
            textbook="统编版（人民教育出版社）",
            unit="全册基础",
            question_ids_json=json.dumps([q.id for q in questions]),
            teacher_id=teacher.id,
        )
        db.add(paper); db.flush()
        assignment = legacy.Assignment(
            school_id=teacher.school_id,
            title="课堂练习复盘测试",
            class_id=cls.id,
            paper_id=paper.id,
            due_date="2026-09-30",
        )
        db.add(assignment); db.flush()
        for sid in [student1.id, student2.id]:
            db.add(legacy.AssignmentRecipient(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                class_id=cls.id,
                student_id=sid,
                source="assignment",
            ))
        db.add(legacy.Submission(
            school_id=teacher.school_id,
            assignment_id=assignment.id,
            student_id=student1.id,
            title=assignment.title,
            score=50,
            correct=1,
            total=2,
            answers_json=json.dumps([
                {"question_id": questions[0].id, "selected_index": 1, "correct": False},
                {"question_id": questions[1].id, "selected_index": 0, "correct": True},
            ], ensure_ascii=False),
        ))
        cfg = legacy.ai_config_for(db, teacher.school_id, True)
        cfg.allow_student_data = True
        db.commit()
        aid = assignment.id
        qid = questions[0].id

    listing = client.get("/teacher/classroom-reviews/assignments", headers=th)
    assert listing.status_code == 200, listing.text
    row = next(x for x in listing.json() if x["id"] == aid)
    assert row["recipientCount"] == 2
    assert row["completedCount"] == 1

    review = client.get(f"/teacher/assignments/{aid}/class-review", headers=th)
    assert review.status_code == 200, review.text
    data = review.json()
    assert data["recipientCount"] == 2
    assert data["completedCount"] == 1
    assert data["completionRate"] == 50
    assert data["handoutDraft"] is None

    captured = {}
    def fake_ai_call(db, user, feature, prompt, images=None, timeout=90):
        captured["feature"] = feature
        captured["prompt"] = prompt
        return "课堂练习概况\n本次为阶段性数据。\n\n重点讲解\n句子衔接。"

    legacy._ai_call = fake_ai_call
    generated = client.post(
        f"/teacher/assignments/{aid}/class-review/handout-generate",
        headers=th,
        json={
            "selected_knowledge": ["句子衔接"],
            "selected_question_ids": [qid],
            "teacher_notes": "先讲方法，再做变式",
        },
    )
    assert generated.status_code == 200, generated.text
    draft = generated.json()["handoutDraft"]
    assert draft["content"].startswith("课堂练习概况")
    assert captured["feature"] == "class_review_handout"
    assert "student1" not in captured["prompt"]
    assert "复盘学生乙" not in captured["prompt"]

    saved = client.put(
        f"/teacher/assignments/{aid}/class-review/handout",
        headers=th,
        json={
            "title": "教师修改后的课堂讲义",
            "content": draft["content"] + "\n教师补充。",
            "selected_knowledge": ["句子衔接"],
            "selected_question_ids": [qid],
            "teacher_notes": "已人工审核",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["handoutDraft"]["title"] == "教师修改后的课堂讲义"

    reread = client.get(f"/teacher/assignments/{aid}/class-review", headers=th)
    assert reread.status_code == 200
    assert reread.json()["handoutDraft"]["teacherNotes"] == "已人工审核"
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
