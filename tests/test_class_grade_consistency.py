from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_named_class_grade_repair_and_validation(tmp_path):
    db_path = tmp_path / "class-grade-consistency.sqlite3"
    script = r'''
import app_v924 as m
from fastapi import HTTPException

m.Base.metadata.create_all(m.engine)

assert m.class_name_grade("数学五年级") == 5
assert m.class_name_grade("三年级数学") == 3
assert m.class_name_grade("晚托班") is None

try:
    m.validate_class_grade("数学五年级", 1)
    raise AssertionError("mismatched class grade should be rejected")
except HTTPException as exc:
    assert exc.status_code == 400
    assert "5年级" in str(exc.detail)

with m.SessionLocal() as db:
    school = m.School(name="迁移测试学校", code="grade-fix-test")
    db.add(school)
    db.flush()
    teacher = m.User(
        school_id=school.id,
        username="teacher-grade-fix",
        password_hash="test",
        name="测试教师",
        role="teacher",
        grade=None,
        active=True,
    )
    db.add(teacher)
    db.flush()

    class3 = m.SchoolClass(
        school_id=school.id,
        name="数学三年级",
        grade=1,
        teacher_id=teacher.id,
    )
    class5 = m.SchoolClass(
        school_id=school.id,
        name="数学五年级",
        grade=1,
        teacher_id=teacher.id,
    )
    ambiguous = m.SchoolClass(
        school_id=school.id,
        name="晚托班",
        grade=1,
        teacher_id=teacher.id,
    )
    db.add_all([class3, class5, ambiguous])
    db.flush()

    student3 = m.User(
        school_id=school.id,
        username="student-grade-3",
        password_hash="test",
        name="三年级学生",
        role="student",
        grade=1,
        active=True,
    )
    student5 = m.User(
        school_id=school.id,
        username="student-grade-5",
        password_hash="test",
        name="五年级学生",
        role="student",
        grade=1,
        active=True,
    )
    ambiguous_student = m.User(
        school_id=school.id,
        username="student-ambiguous",
        password_hash="test",
        name="晚托学生",
        role="student",
        grade=1,
        active=True,
    )
    db.add_all([student3, student5, ambiguous_student])
    db.flush()
    db.add_all([
        m.ClassStudent(class_id=class3.id, student_id=student3.id),
        m.ClassStudent(class_id=class5.id, student_id=student5.id),
        m.ClassStudent(class_id=ambiguous.id, student_id=ambiguous_student.id),
    ])
    db.commit()

with m.SessionLocal() as db:
    m.run_schema_migrations(db)

with m.SessionLocal() as db:
    class3 = db.scalar(m.select(m.SchoolClass).where(m.SchoolClass.name == "数学三年级"))
    class5 = db.scalar(m.select(m.SchoolClass).where(m.SchoolClass.name == "数学五年级"))
    ambiguous = db.scalar(m.select(m.SchoolClass).where(m.SchoolClass.name == "晚托班"))
    student3 = db.scalar(m.select(m.User).where(m.User.username == "student-grade-3"))
    student5 = db.scalar(m.select(m.User).where(m.User.username == "student-grade-5"))
    ambiguous_student = db.scalar(m.select(m.User).where(m.User.username == "student-ambiguous"))

    assert class3.grade == 3
    assert class5.grade == 5
    assert ambiguous.grade == 1
    assert student3.grade == 3
    assert student5.grade == 5
    assert ambiguous_student.grade == 1
    assert db.get(m.SchemaMigration, "10.6.3") is not None

    class_audits = list(db.scalars(
        m.select(m.AuditLog).where(m.AuditLog.action == "class.grade.repair")
    ).all())
    student_audits = list(db.scalars(
        m.select(m.AuditLog).where(m.AuditLog.action == "student.grade.repair")
    ).all())
    assert len(class_audits) == 2
    assert len(student_audits) == 2

with m.SessionLocal() as db:
    m.run_schema_migrations(db)
    assert db.scalar(
        m.select(m.func.count()).select_from(m.AuditLog).where(
            m.AuditLog.action == "class.grade.repair"
        )
    ) == 2
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "class-grade-test-jwt-secret-0123456789abcdef0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "class-grade-test-commercial-key-0123456789",
            "ENABLE_DEMO_SEED": "0",
            "PYTHONPATH": str(ROOT),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, (
        "class grade consistency subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
