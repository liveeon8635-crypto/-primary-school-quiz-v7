from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import json

from changying.services.classroom_review import (
    build_anonymized_handout_prompt,
    build_deterministic_interaction_handout_summary,
    classroom_interaction_summary,
    classroom_review_summary,
)
from changying.web.v1_classroom_review import (
    V1_CLASSROOM_REVIEW_MARKER,
    _default_handout_title,
    patch_v1_classroom_review_html,
)
from changying.web.v1 import v1_html
from changying.web.v1_operational import patch_v1_operational_html


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


def test_classroom_interaction_summary_keeps_rounds_reteach_and_teacher_review_aggregate():
    from datetime import datetime

    session = SimpleNamespace(
        id=7,
        title="课堂执行",
        status="completed",
        started_at=datetime(2026, 9, 22, 10, 0),
        completed_at=datetime(2026, 9, 22, 10, 40),
    )
    segments = [
        SimpleNamespace(
            id=31,
            knowledge_key="说明方法",
            title="说明方法",
            order_no=1,
            mode="student",
            status="completed",
            baseline_accuracy=0,
            postcheck_accuracy=None,
        )
    ]
    quick_checks = [
        SimpleNamespace(
            id=41,
            segment_id=31,
            question_type="single_choice",
            question_text="第一轮",
            status="closed",
            decision="reteach",
            created_at=datetime(2026, 9, 22, 10, 20),
        ),
        SimpleNamespace(
            id=42,
            segment_id=31,
            question_type="true_false",
            question_text="第二轮",
            status="closed",
            decision="complete",
            created_at=datetime(2026, 9, 22, 10, 35),
        ),
    ]
    responses = [
        SimpleNamespace(check_id=41, is_correct=False),
        SimpleNamespace(check_id=42, is_correct=True),
    ]
    turns = [SimpleNamespace(segment_id=31, status="completed", student_id=999)]
    reviews = [
        SimpleNamespace(
            segment_id=31,
            accuracy_rating=1,
            clarity_rating=2,
            interaction_rating=2,
            granted_points=1,
            student_id=999,
        )
    ]

    result = classroom_interaction_summary(
        session=session,
        segments=segments,
        quick_checks=quick_checks,
        responses=responses,
        presenter_turns=turns,
        presentation_reviews=reviews,
    )

    assert result["quickCheckRoundCount"] == 2
    assert result["reteachCount"] == 1
    assert result["presentationCount"] == 1
    assert result["teacherGrantedPoints"] == 1
    seg = result["segments"][0]
    assert [x["accuracy"] for x in seg["quickCheckRounds"]] == [0, 100]
    assert [x["decision"] for x in seg["quickCheckRounds"]] == ["reteach", "complete"]
    assert seg["presentationAverages"] == {
        "accuracy": 1.0,
        "clarity": 2.0,
        "interaction": 2.0,
    }
    assert "studentName" not in json.dumps(result, ensure_ascii=False)
    assert "999" not in json.dumps(result, ensure_ascii=False)


def test_deterministic_interaction_summary_preserves_reteach_scores_review_and_points():
    summary = {
        "classroomInteraction": {
            "segments": [
                {
                    "knowledge": "说明方法",
                    "quickCheckRounds": [
                        {
                            "round": 1,
                            "responseCount": 1,
                            "correctCount": 0,
                            "accuracy": 0,
                            "decision": "reteach",
                        },
                        {
                            "round": 2,
                            "responseCount": 1,
                            "correctCount": 1,
                            "accuracy": 100,
                            "decision": "complete",
                        },
                    ],
                    "reteachCount": 1,
                    "presentationCount": 1,
                    "presentationReviewCount": 1,
                    "presentationAverages": {
                        "accuracy": 1.0,
                        "clarity": 2.0,
                        "interaction": 2.0,
                    },
                    "teacherGrantedPoints": 1,
                },
                {
                    "knowledge": "资料整合、阅读推断",
                    "quickCheckRounds": [
                        {
                            "round": 1,
                            "responseCount": 1,
                            "correctCount": 1,
                            "accuracy": 100,
                            "decision": "complete",
                        }
                    ],
                    "reteachCount": 0,
                    "presentationCount": 0,
                    "presentationReviewCount": 0,
                    "presentationAverages": {},
                    "teacherGrantedPoints": 0,
                },
            ]
        }
    }

    text = build_deterministic_interaction_handout_summary(
        summary,
        selected_knowledge=["说明方法", "资料整合、阅读推断"],
    )

    assert "共进行了3轮随堂检测" in text
    assert "发生1次补讲" in text
    assert "第1轮：1人提交，0人正确，正确率0%，教师决定继续讲解" in text
    assert "第2轮：1人提交，1人正确，正确率100%，教师决定确认完成" in text
    assert "内容准确性1.0/5" in text
    assert "表达清晰度2.0/5" in text
    assert "互动效果2.0/5" in text
    assert "教师明确加分1分" in text
    assert "不自动改写长期知识掌握记录" in text
    assert "student" not in text.lower()


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
        "classroomInteraction": {
            "session": {"status": "completed"},
            "quickCheckRoundCount": 2,
            "reteachCount": 1,
            "presentationCount": 1,
            "presentationReviewCount": 1,
            "teacherGrantedPoints": 1,
            "segments": [
                {
                    "knowledge": "句子衔接",
                    "mode": "student",
                    "quickCheckRounds": [
                        {"round": 1, "questionType": "single_choice", "responseCount": 2, "correctCount": 0, "accuracy": 0, "decision": "reteach"},
                        {"round": 2, "questionType": "single_choice", "responseCount": 2, "correctCount": 2, "accuracy": 100, "decision": "complete"},
                    ],
                    "reteachCount": 1,
                    "presentationCount": 1,
                    "presentationReviewCount": 1,
                    "presentationAverages": {"accuracy": 4.0, "clarity": 4.5, "interaction": 4.0},
                    "teacherGrantedPoints": 1,
                }
            ],
        },
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
    assert "classroomInteraction" in prompt
    assert '"accuracy": 0' in prompt
    assert '"accuracy": 100' in prompt
    assert '"decision": "reteach"' in prompt


def test_default_handout_title_uses_grade_and_actual_subject_not_class_label():
    summary = {
        "class": {"id": 8, "name": "数学五年级", "grade": 5},
        "paper": {"subject": "语文", "textbook": "统编版（人民教育出版社）"},
        "assignment": {"id": 32, "title": "语文 AI 针对性练习"},
    }
    title = _default_handout_title(summary)
    assert title == "5年级语文 · 语文 AI 针对性练习 课堂练习复盘讲义"
    assert "数学五年级" not in title


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
    assert "互动课堂反馈" in html
    assert "不会自动改写长期知识掌握记录" in html
    assert "随堂检测" in html
    assert "学生讲解" in html
    assert "旧草稿 · 建议重新生成" in html
    assert "重新生成本堂课讲义草稿" in html
    assert "draftUpdatedAt<completedAt" in html
    assert "讲义需补全互动摘要" in html
    assert "重新生成并补全互动摘要" in html
    assert "互动课堂过程摘要（系统记录）" in html


def test_runtime_classroom_review_full_loop(tmp_path):
    db_path = tmp_path / "classroom-review.sqlite3"
    script = r"""
import json
from datetime import datetime, timedelta
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

        sessions = legacy.Base.metadata.tables["classroom_sessions"]
        completed_time = datetime(2026, 9, 22, 10, 40)
        db.execute(
            sessions.insert().values(
                school_id=teacher.school_id,
                class_id=cls.id,
                teacher_id=teacher.id,
                source_assignment_id=assignment.id,
                subject="语文",
                textbook="统编版（人民教育出版社）",
                title="已完成互动课堂",
                status="completed",
                started_at=completed_time - timedelta(minutes=40),
                completed_at=completed_time,
                created_at=completed_time - timedelta(minutes=41),
                updated_at=completed_time,
            )
        )
        db.execute(
            sessions.insert().values(
                school_id=teacher.school_id,
                class_id=cls.id,
                teacher_id=teacher.id,
                source_assignment_id=assignment.id,
                subject="语文",
                textbook="统编版（人民教育出版社）",
                title="误创建待开始课堂",
                status="planned",
                created_at=completed_time + timedelta(minutes=1),
                updated_at=completed_time + timedelta(minutes=1),
            )
        )
        db.commit()

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
    assert data["classroomInteraction"]["session"]["status"] == "completed"
    assert data["classroomInteraction"]["session"]["title"] == "已完成互动课堂"
    assert data["openClassroomSession"]["status"] == "planned"
    assert data["openClassroomSession"]["title"] == "误创建待开始课堂"

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



def test_operational_capture_handler_preserves_classroom_review_navigation():
    html = patch_v1_operational_html(
        patch_v1_classroom_review_html(v1_html())
    )
    assert "if(name==='课堂复盘')" in html
    assert "navigate('/v1/classroom-review')" in html
    assert "showFeature(name)" in html



def test_classroom_review_ai_generation_uses_long_timeout_without_changing_default():
    html = patch_v1_classroom_review_html(v1_html())
    assert "const timeoutMs=Number(options.timeoutMs||10000)" in html
    assert "delete requestOptions.timeoutMs" in html
    assert "timeoutMs:90000" in html
    assert "setTimeout(()=>controller.abort(),timeoutMs)" in html



def test_classroom_review_requires_explicit_assignment_instead_of_old_default():
    """Regression: finishing a new class must not open an unrelated old lesson."""
    html = patch_v1_classroom_review_html(v1_html())
    assert "let current=requested||0,summary=null;" in html
    assert "let current=requested||Number(assignments[0]?.id||0)" not in html
    assert "if(!requested || !assignments.some(a=>Number(a.id)===requested))" in html
    assert "系统不会自动选取另一堂课的历史作业" in html
    assert "此课堂尚未核实关联的作业" in html
    assert "if(e.target.value)load(e.target.value)" in html
