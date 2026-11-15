"""Ordinary assignment submissions must feed the student's wrong-question book.

F4 in the 2026-11-10 production audit: 普通作业批改进不了错题本.  The student
submit route already calls ``archive_objective_assessment_wrong_answers``, but
the helper only accepted comprehensive/module/AI-practice sources, so ordinary
assignments (``AssignmentRecipient.source == "assignment"``) silently archived
nothing.  This test drives the real routes: submit an assignment with one wrong
answer, then read the wrong-question book through both the student and teacher
endpoints, and verify a repeated submit does not duplicate the record.
"""
import json
from contextlib import nullcontext
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import app
import app_v924 as legacy


def _headers(db, username):
    user = db.scalar(legacy.select(legacy.User).where(legacy.User.username == username))
    assert user is not None
    security = legacy.security_for(db, user)
    security.must_change_password = False
    db.commit()
    return user, {"Authorization": "Bearer " + legacy.make_token(user, security, False)}


def _fixture(db):
    legacy.Base.metadata.create_all(legacy.engine)
    if db.scalar(legacy.select(legacy.User.id).where(legacy.User.username == "teacher1")) is None:
        legacy.seed(db)
        db.commit()
    teacher, th = _headers(db, "teacher1")
    student, sh = _headers(db, "student1")
    cls = db.scalar(
        legacy.select(legacy.SchoolClass)
        .join(legacy.ClassStudent, legacy.ClassStudent.class_id == legacy.SchoolClass.id)
        .where(
            legacy.SchoolClass.teacher_id == teacher.id,
            legacy.ClassStudent.student_id == student.id,
        )
    )
    assert cls is not None
    suffix = str(int(datetime.utcnow().timestamp() * 1_000_000))
    questions = []
    for number in (1, 2):
        row = legacy.Question(
            school_id=teacher.school_id,
            grade=cls.grade,
            subject="数学",
            textbook="人教版",
            semester="上册",
            unit="错题本测试",
            knowledge="加法",
            text=f"{number}+{number} 等于多少？ {suffix}",
            options_json=json.dumps([str(number), str(number * 2), str(number * 3), str(number * 4)]),
            correct_index=1,
            explanation=f"解析 {number}",
            question_type="single_choice",
            answer_json="{}",
            figure_json="{}",
            creator_id=teacher.id,
        )
        db.add(row)
        db.flush()
        questions.append(row)
    paper = legacy.Paper(
        school_id=teacher.school_id,
        title=f"错题本试卷 {suffix}",
        grade=cls.grade,
        subject="数学",
        textbook="人教版",
        unit="错题本测试",
        question_ids_json=json.dumps([q.id for q in questions]),
        teacher_id=teacher.id,
    )
    db.add(paper)
    db.flush()
    assignment = legacy.Assignment(
        school_id=teacher.school_id,
        title=f"普通作业错题本 {suffix}",
        class_id=cls.id,
        paper_id=paper.id,
        due_date="2035-01-01",
    )
    db.add(assignment)
    db.flush()
    db.add(legacy.AssignmentSubmissionSetting(
        school_id=teacher.school_id,
        assignment_id=assignment.id,
        mode="quiz",
        instructions="",
    ))
    db.add(legacy.AssignmentRecipient(
        school_id=teacher.school_id,
        assignment_id=assignment.id,
        class_id=cls.id,
        student_id=student.id,
        source="assignment",
    ))
    db.commit()
    return (
        SimpleNamespace(id=teacher.id, school_id=teacher.school_id),
        SimpleNamespace(id=student.id, school_id=student.school_id),
        th,
        sh,
        SimpleNamespace(id=assignment.id, title=assignment.title),
        [SimpleNamespace(id=q.id, correct_index=q.correct_index) for q in questions],
    )


def _answer(question, correct=True):
    selected = int(question.correct_index)
    if not correct:
        selected = 0 if selected != 0 else 1
    return {"question_id": question.id, "selected_index": selected}


def test_ordinary_assignment_wrong_answers_enter_the_wrong_question_book():
    with nullcontext(TestClient(app)) as client:
        with legacy.SessionLocal() as db:
            teacher, student, th, sh, assignment, questions = _fixture(db)
            q1, q2 = questions
            aid = assignment.id
            sid = student.id

        submitted = client.post(
            f"/student/assignments/{aid}/submit",
            headers=sh,
            json={"partial": False, "answers": [_answer(q1), _answer(q2, correct=False)]},
        )
        assert submitted.status_code == 200, submitted.text
        body = submitted.json()
        assert body["completed"] is True
        assert body["score"] == 50
        assert body["assessmentFeedbackArchived"] == 1, body

        student_book = client.get("/student/wrong-questions", headers=sh)
        assert student_book.status_code == 200, student_book.text
        items = student_book.json()["items"]
        archived = [x for x in items if x["assignmentID"] == aid]
        assert len(archived) == 1, items
        record = archived[0]
        assert record["questionID"] == q2.id
        assert record["source"] == "assessment"
        assert record["problem"]
        assert record["correctAnswer"]
        assert record["wrongAnswer"]
        assert record["status"] == "active"

        teacher_book = client.get(
            f"/teacher/students/{sid}/wrong-questions", headers=th
        )
        assert teacher_book.status_code == 200, teacher_book.text
        teacher_items = [
            x for x in teacher_book.json()["items"] if x["assignmentID"] == aid
        ]
        assert len(teacher_items) == 1
        assert teacher_items[0]["id"] == record["id"]

        again = client.post(
            f"/student/assignments/{aid}/submit",
            headers=sh,
            json={"partial": True, "answers": [_answer(q2, correct=False)]},
        )
        assert again.status_code == 200, again.text
        after = client.get("/student/wrong-questions", headers=sh).json()["items"]
        remaining = [x for x in after if x["assignmentID"] == aid]
        assert len(remaining) == 1, "repeated submit must not duplicate the wrong-question record"
        assert remaining[0]["id"] == record["id"]
