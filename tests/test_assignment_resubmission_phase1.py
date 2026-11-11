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
            unit="重交测试",
            knowledge="加法",
            text=f"{number}+{number} 等于多少？ {suffix}",
            options_json=json.dumps([str(number), str(number * 2), str(number * 3), str(number * 4)]),
            correct_index=1,
            explanation="",
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
        title=f"重交试卷 {suffix}",
        grade=cls.grade,
        subject="数学",
        textbook="人教版",
        unit="重交测试",
        question_ids_json=json.dumps([q.id for q in questions]),
        teacher_id=teacher.id,
    )
    db.add(paper)
    db.flush()
    assignment = legacy.Assignment(
        school_id=teacher.school_id,
        title=f"普通作业重交 {suffix}",
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
    other = legacy.User(
        school_id=teacher.school_id,
        username=f"other_teacher_{suffix}",
        password_hash=legacy.hash_password("OtherTeacher123"),
        name="其他教师",
        role="teacher",
        active=True,
    )
    db.add(other)
    db.flush()
    other_security = legacy.UserSecurity(user_id=other.id, must_change_password=False, failed_login_count=0)
    db.add(other_security)
    db.commit()
    oh = {"Authorization": "Bearer " + legacy.make_token(other, other_security, False)}
    return (
        SimpleNamespace(id=teacher.id, school_id=teacher.school_id),
        SimpleNamespace(id=student.id, school_id=student.school_id),
        th,
        sh,
        oh,
        SimpleNamespace(id=assignment.id, title=assignment.title),
        [SimpleNamespace(id=q.id, correct_index=q.correct_index) for q in questions],
    )


def _answer(question, correct=True):
    selected = int(question.correct_index)
    if not correct:
        selected = 0 if selected != 0 else 1
    return {"question_id": question.id, "selected_index": selected}


def test_real_routes_cover_draft_partial_history_limits_grants_and_points():
    with nullcontext(TestClient(app)) as client:
        with legacy.SessionLocal() as db:
            teacher, student, th, sh, oh, assignment, questions = _fixture(db)
            aid = assignment.id
            q1, q2 = questions
            baseline_submission_count = db.scalar(
                legacy.select(legacy.func.count()).select_from(legacy.Submission)
            )
            baseline_point_count = db.scalar(
                legacy.select(legacy.func.count()).select_from(legacy.PointLedger)
            )
            baseline_point_sum = db.scalar(
                legacy.select(legacy.func.coalesce(legacy.func.sum(legacy.PointLedger.points), 0))
            )

        saved = client.put(
            f"/student/assignments/{aid}/draft",
            headers=sh,
            json={"answers": [_answer(q1), _answer(q2)]},
        )
        assert saved.status_code == 200, saved.text
        restored = client.get(f"/student/assignments/{aid}/draft", headers=sh)
        assert restored.status_code == 200
        assert {x["question_id"] for x in restored.json()["answers"]} == {q1.id, q2.id}

        first = client.post(
            f"/student/assignments/{aid}/submit",
            headers=sh,
            json={"partial": True, "answers": [_answer(q1)]},
        )
        assert first.status_code == 200, first.text
        assert first.json()["completed"] is False
        assert first.json()["status"] == "进行中"
        assert first.json()["score"] == 50
        assert first.json()["answeredCount"] == 1
        assert first.json()["learningPointsAwarded"] == 0
        submission_id = first.json()["id"]
        remaining_draft = client.get(f"/student/assignments/{aid}/draft", headers=sh).json()
        assert [x["question_id"] for x in remaining_draft["answers"]] == [q2.id]

        for correct in (False, True, True):
            retry = client.post(
                f"/student/assignments/{aid}/submit",
                headers=sh,
                json={"partial": True, "answers": [_answer(q1, correct)]},
            )
            assert retry.status_code == 200, retry.text
            assert retry.json()["id"] == submission_id

        rejected = client.post(
            f"/student/assignments/{aid}/submit",
            headers=sh,
            json={"partial": True, "answers": [_answer(q1)]},
        )
        assert rejected.status_code == 409
        assert "最多提交 4 次" in rejected.json()["detail"]

        completed = client.post(
            f"/student/assignments/{aid}/submit",
            headers=sh,
            json={"partial": True, "answers": [_answer(q2)]},
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["completed"] is True
        assert completed.json()["learningPointsAwarded"] == 2
        assert completed.json()["id"] == submission_id

        revised = client.post(
            f"/student/assignments/{aid}/submit",
            headers=sh,
            json={"partial": True, "answers": [_answer(q2, False)]},
        )
        assert revised.status_code == 200, revised.text
        assert revised.json()["learningPointsAwarded"] == 0
        assert revised.json()["score"] == 50

        student_history = client.get(f"/student/assignments/{aid}/history", headers=sh)
        teacher_history = client.get(
            f"/teacher/assignments/{aid}/students/{student.id}/history", headers=th
        )
        assert student_history.status_code == teacher_history.status_code == 200
        attempts = student_history.json()["attempts"]
        assert len([x for x in attempts if x["questionID"] == q1.id]) == 4
        assert len([x for x in attempts if x["questionID"] == q2.id]) == 2

        forbidden = client.post(
            f"/teacher/assignments/{aid}/students/{student.id}/retry-grants",
            headers=oh,
            json={"extra_attempts": 1, "reason": "越权"},
        )
        assert forbidden.status_code == 404
        granted = client.post(
            f"/teacher/assignments/{aid}/students/{student.id}/retry-grants",
            headers=th,
            json={"extra_attempts": 1, "reason": "允许订正一次"},
        )
        assert granted.status_code == 200, granted.text
        fifth = client.post(
            f"/student/assignments/{aid}/submit",
            headers=sh,
            json={"partial": True, "answers": [_answer(q1, False)]},
        )
        assert fifth.status_code == 200, fifth.text
        sixth = client.post(
            f"/student/assignments/{aid}/submit",
            headers=sh,
            json={"partial": True, "answers": [_answer(q1)]},
        )
        assert sixth.status_code == 409
        assert "最多提交 5 次" in sixth.json()["detail"]

        with legacy.SessionLocal() as db:
            submission_count = db.scalar(
                legacy.select(legacy.func.count()).select_from(legacy.Submission)
            )
            assignment_submissions = db.scalars(
                legacy.select(legacy.Submission).where(
                    legacy.Submission.assignment_id == aid,
                    legacy.Submission.student_id == student.id,
                )
            ).all()
            point_count = db.scalar(
                legacy.select(legacy.func.count()).select_from(legacy.PointLedger)
            )
            point_sum = db.scalar(
                legacy.select(legacy.func.coalesce(legacy.func.sum(legacy.PointLedger.points), 0))
            )
        assert submission_count == baseline_submission_count + 1
        assert len(assignment_submissions) == 1
        assert assignment_submissions[0].id == submission_id
        assert point_count == baseline_point_count + 1
        assert point_sum == baseline_point_sum + 2


def test_historical_submission_stays_complete_and_is_not_reawarded():
    with nullcontext(TestClient(app)) as client:
        with legacy.SessionLocal() as db:
            _, student, th, sh, _, assignment, questions = _fixture(db)
            answers = [
                {**_answer(q), "text_answer": "", "correct": True}
                for q in questions
            ]
            old = legacy.Submission(
                school_id=student.school_id,
                assignment_id=assignment.id,
                student_id=student.id,
                title=assignment.title,
                score=100,
                correct=2,
                total=2,
                answers_json=json.dumps(answers, ensure_ascii=False),
                completion_actor="student",
            )
            db.add(old)
            db.commit()
            old_id = old.id
            point_count = db.scalar(legacy.select(legacy.func.count()).select_from(legacy.PointLedger))
            point_sum = db.scalar(legacy.select(legacy.func.coalesce(legacy.func.sum(legacy.PointLedger.points), 0)))

        before = client.get("/student/assignments", headers=sh).json()
        before_row = next(x for x in before if x["id"] == assignment.id)
        assert before_row["completed"] is True
        history = client.get(f"/student/assignments/{assignment.id}/history", headers=sh)
        assert history.status_code == 200
        assert history.json()["completed"] is True
        assert {x["source"] for x in history.json()["attempts"]} == {"legacy_snapshot"}

        retry = client.post(
            f"/student/assignments/{assignment.id}/submit",
            headers=sh,
            json={"partial": True, "answers": [_answer(questions[0], False)]},
        )
        assert retry.status_code == 200, retry.text
        assert retry.json()["id"] == old_id
        assert retry.json()["completed"] is True
        assert retry.json()["learningPointsAwarded"] == 0
        after = client.get("/student/assignments", headers=sh).json()
        after_row = next(x for x in after if x["id"] == assignment.id)
        assert after_row["completed"] is True

        with legacy.SessionLocal() as db:
            rows = db.scalars(legacy.select(legacy.Submission).where(
                legacy.Submission.assignment_id == assignment.id,
                legacy.Submission.student_id == student.id,
            )).all()
            assert len(rows) == 1 and rows[0].id == old_id
            assert db.scalar(legacy.select(legacy.func.count()).select_from(legacy.PointLedger)) == point_count
            assert db.scalar(legacy.select(legacy.func.coalesce(legacy.func.sum(legacy.PointLedger.points), 0))) == point_sum
            history_rows = db.scalars(legacy.select(legacy.AssignmentQuestionAttempt).where(
                legacy.AssignmentQuestionAttempt.assignment_id == assignment.id,
                legacy.AssignmentQuestionAttempt.student_id == student.id,
            )).all()
            assert len(history_rows) == 3
            assert len([x for x in history_rows if x.source == "legacy_snapshot"]) == 2


def test_new_tables_are_additive_and_registered_before_startup_create_all():
    names = set(legacy.Base.metadata.tables)
    assert {
        "assignment_question_attempts",
        "assignment_drafts",
        "assignment_retry_grants",
    } <= names
    inspector = legacy.sa_inspect(legacy.engine)
    assert {
        "assignment_question_attempts",
        "assignment_drafts",
        "assignment_retry_grants",
    } <= set(inspector.get_table_names())


def test_startup_create_all_adds_only_new_tables_and_keeps_legacy_submission_rows():
    isolated = legacy.create_engine("sqlite://")
    legacy.Submission.__table__.create(isolated)
    with isolated.begin() as connection:
        connection.execute(
            legacy.Submission.__table__.insert().values(
                id=9001,
                school_id=1,
                assignment_id=2,
                student_id=3,
                title="历史提交",
                score=80,
                correct=4,
                total=5,
                answers_json="[]",
                completion_actor=None,
                submitted_at=datetime(2026, 1, 1),
            )
        )
        before = connection.scalar(
            legacy.select(legacy.func.count()).select_from(legacy.Submission)
        )

    legacy.Base.metadata.create_all(isolated)

    with isolated.begin() as connection:
        after = connection.scalar(
            legacy.select(legacy.func.count()).select_from(legacy.Submission)
        )
    assert before == after == 1
    assert {
        "assignment_question_attempts",
        "assignment_drafts",
        "assignment_retry_grants",
    } <= set(legacy.sa_inspect(isolated).get_table_names())

