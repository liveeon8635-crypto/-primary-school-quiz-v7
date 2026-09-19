from __future__ import annotations

from datetime import datetime, timedelta
import json

from sqlalchemy import DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from changying.services.learning_feedback import (
    collect_student_learning_feedback,
    compact_feedback_for_ai,
)


class Base(DeclarativeBase):
    pass


class TestAssignment(Base):
    __tablename__ = "feedback_test_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    class_id: Mapped[int] = mapped_column(Integer)
    paper_id: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))


class TestRecipient(Base):
    __tablename__ = "feedback_test_recipients"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    assignment_id: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(40))


class TestPaper(Base):
    __tablename__ = "feedback_test_papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    grade: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str] = mapped_column(String(30))
    textbook: Mapped[str] = mapped_column(String(80))
    unit: Mapped[str] = mapped_column(String(100))


class TestSubmission(Base):
    __tablename__ = "feedback_test_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    assignment_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    student_id: Mapped[int] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer)
    correct: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    answers_json: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime)


class TestQuestion(Base):
    __tablename__ = "feedback_test_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    grade: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str] = mapped_column(String(30))
    textbook: Mapped[str] = mapped_column(String(80))
    unit: Mapped[str] = mapped_column(String(100))
    knowledge: Mapped[str] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(Text)
    options_json: Mapped[str] = mapped_column(Text)
    correct_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text)


MODELS = {
    "Assignment": TestAssignment,
    "AssignmentRecipient": TestRecipient,
    "Paper": TestPaper,
    "Submission": TestSubmission,
    "Question": TestQuestion,
}


def _seed(db: Session):
    now = datetime(2026, 9, 19, 10, 0, 0)
    db.add_all(
        [
            TestPaper(
                id=10,
                school_id=1,
                grade=5,
                subject="数学",
                textbook="北师大版",
                unit="综合",
            ),
            TestPaper(
                id=11,
                school_id=1,
                grade=5,
                subject="数学",
                textbook="北师大版",
                unit="分数的意义",
            ),
            TestPaper(
                id=12,
                school_id=1,
                grade=5,
                subject="数学",
                textbook="北师大版",
                unit="AI针对性练习",
            ),
            TestPaper(
                id=13,
                school_id=1,
                grade=5,
                subject="数学",
                textbook="北师大版",
                unit="普通作业",
            ),
            TestAssignment(
                id=100,
                school_id=1,
                class_id=7,
                paper_id=10,
                title="五年级数学（北师大版）综合测试",
            ),
            TestAssignment(
                id=101,
                school_id=1,
                class_id=7,
                paper_id=11,
                title="分数的意义专项练习",
            ),
            TestAssignment(
                id=102,
                school_id=1,
                class_id=7,
                paper_id=12,
                title="AI针对性练习",
            ),
            TestAssignment(
                id=103,
                school_id=1,
                class_id=7,
                paper_id=13,
                title="普通作业",
            ),
            TestRecipient(
                id=1,
                school_id=1,
                assignment_id=100,
                student_id=20,
                source="student_comprehensive_test",
            ),
            TestRecipient(
                id=2,
                school_id=1,
                assignment_id=101,
                student_id=20,
                source="student_module_practice",
            ),
            TestRecipient(
                id=3,
                school_id=1,
                assignment_id=102,
                student_id=20,
                source="ai_reinforcement",
            ),
            TestRecipient(
                id=4,
                school_id=1,
                assignment_id=103,
                student_id=20,
                source="assignment",
            ),
            TestQuestion(
                id=1,
                school_id=1,
                grade=5,
                subject="数学",
                textbook="北师大版",
                unit="第五单元 · 分数的意义",
                knowledge="分数基本性质",
                text="1/2 与下面哪个分数相等？",
                options_json=json.dumps(["2/4", "2/3", "3/5", "4/5"], ensure_ascii=False),
                correct_index=0,
                explanation="分子分母同时乘相同非零数。",
            ),
            TestQuestion(
                id=2,
                school_id=1,
                grade=5,
                subject="数学",
                textbook="北师大版",
                unit="第五单元 · 分数的意义",
                knowledge="分数大小比较",
                text="比较两个分数。",
                options_json=json.dumps(["A", "B", "C", "D"], ensure_ascii=False),
                correct_index=2,
                explanation="通分后比较。",
            ),
            TestQuestion(
                id=3,
                school_id=1,
                grade=5,
                subject="数学",
                textbook="北师大版",
                unit="第五单元 · 分数的意义",
                knowledge="分数基本性质",
                text="约分题。",
                options_json=json.dumps(["A", "B", "C", "D"], ensure_ascii=False),
                correct_index=1,
                explanation="同时除以公因数。",
            ),
        ]
    )
    db.add_all(
        [
            TestSubmission(
                id=1,
                school_id=1,
                assignment_id=100,
                student_id=20,
                score=50,
                correct=1,
                total=2,
                answers_json=json.dumps(
                    [
                        {"question_id": 1, "selected_index": 1, "correct": False},
                        {"question_id": 2, "selected_index": 2, "correct": True},
                    ]
                ),
                submitted_at=now - timedelta(days=2),
            ),
            TestSubmission(
                id=2,
                school_id=1,
                assignment_id=101,
                student_id=20,
                score=0,
                correct=0,
                total=1,
                answers_json=json.dumps(
                    [{"question_id": 3, "selected_index": 0, "correct": False}]
                ),
                submitted_at=now - timedelta(days=1),
            ),
            TestSubmission(
                id=3,
                school_id=1,
                assignment_id=102,
                student_id=20,
                score=100,
                correct=1,
                total=1,
                answers_json=json.dumps(
                    [{"question_id": 1, "selected_index": 0, "correct": True}]
                ),
                submitted_at=now,
            ),
            TestSubmission(
                id=4,
                school_id=1,
                assignment_id=103,
                student_id=20,
                score=0,
                correct=0,
                total=1,
                answers_json=json.dumps(
                    [{"question_id": 2, "selected_index": 0, "correct": False}]
                ),
                submitted_at=now + timedelta(minutes=1),
            ),
        ]
    )
    db.commit()


def _feedback(db: Session, **kwargs):
    return collect_student_learning_feedback(
        db,
        school_id=1,
        student_id=20,
        limit=8,
        **MODELS,
        **kwargs,
    )


def test_feedback_links_comprehensive_module_and_ai_reinforcement_results():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed(db)
        data = _feedback(db)

    assert data["sourceAssignmentIDs"] == [102, 101, 100]
    assert [row["source"] for row in data["tests"]] == [
        "ai_reinforcement",
        "student_module_practice",
        "student_comprehensive_test",
    ]
    assert 103 not in data["sourceAssignmentIDs"]
    assert data["primary"]["textbook"] == "北师大版"


def test_feedback_aggregates_weak_knowledge_and_real_wrong_answers():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed(db)
        data = _feedback(db)

    weak = {row["knowledge"]: row for row in data["weakKnowledge"]}
    assert weak["分数基本性质"]["correct"] == 1
    assert weak["分数基本性质"]["total"] == 3
    assert weak["分数基本性质"]["accuracy"] == 33
    assert len(data["wrongQuestions"]) == 2
    first = next(row for row in data["wrongQuestions"] if row["questionID"] == 1)
    assert first["wrongAnswer"] == "2/3"
    assert first["correctAnswer"] == "2/4"
    assert first["textbook"] == "北师大版"


def test_assignment_filter_focuses_ai_context_on_selected_test():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed(db)
        data = _feedback(db, assignment_id=100)

    assert data["sourceAssignmentIDs"] == [100]
    assert data["tests"][0]["score"] == 50
    assert {row["assignmentID"] for row in data["wrongQuestions"]} == {100}


def test_perfect_targeted_practice_remains_future_ai_evidence():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed(db)
        data = _feedback(db, assignment_id=102)

    assert data["hasEvidence"] is True
    assert data["tests"][0]["sourceName"] == "AI针对性练习"
    assert data["tests"][0]["score"] == 100
    assert data["wrongQuestions"] == []


def test_compact_ai_payload_contains_learning_evidence_without_identity_fields():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed(db)
        data = _feedback(db)
        compact = compact_feedback_for_ai(data)

    assert len(compact["sourceAssignments"]) == 3
    assert compact["sourceAssignments"][0]["textbook"] == "北师大版"
    assert compact["weakKnowledge"]
    serialized = json.dumps(compact, ensure_ascii=False)
    assert "studentName" not in serialized
    assert "studentID" not in serialized
