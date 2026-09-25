from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app_v924 as legacy


def test_retire_legacy_demo_accounts_preserves_live_school_and_real_users():
    engine = create_engine("sqlite:///:memory:")
    legacy.Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with SessionLocal() as db:
        school = legacy.School(name="演示小学", code="demo", active=True)
        db.add(school)
        db.flush()

        demo_teacher = legacy.User(
            school_id=school.id,
            username="teacher1",
            password_hash="x",
            name="演示教师",
            role="teacher",
            active=True,
        )
        demo_student = legacy.User(
            school_id=school.id,
            username="student1",
            password_hash="x",
            name="演示学生",
            role="student",
            grade=3,
            active=True,
        )
        demo_parent = legacy.User(
            school_id=school.id,
            username="parent1",
            password_hash="x",
            name="演示家长",
            role="parent",
            active=True,
        )
        real_teacher = legacy.User(
            school_id=school.id,
            username="real-teacher",
            password_hash="x",
            name="真实教师",
            role="teacher",
            active=True,
        )
        real_student = legacy.User(
            school_id=school.id,
            username="real-student",
            password_hash="x",
            name="真实学生",
            role="student",
            grade=5,
            active=True,
        )
        db.add_all([demo_teacher, demo_student, demo_parent, real_teacher, real_student])
        db.commit()

        result = legacy.retire_legacy_demo_identities(db)
        db.commit()

        assert set(result["retiredLegacyUsers"]) == {"teacher1", "student1", "parent1"}
        assert result["demoSchoolIDs"] == [school.id]

        db.refresh(school)
        db.refresh(demo_teacher)
        db.refresh(demo_student)
        db.refresh(demo_parent)
        db.refresh(real_teacher)
        db.refresh(real_student)

        assert school.active is True
        assert demo_teacher.active is False
        assert demo_student.active is False
        assert demo_parent.active is False
        assert real_teacher.active is True
        assert real_student.active is True

        status = legacy.production_demo_identity_status(db)
        assert status["ok"] is True
        assert status["activeLegacyDemoUsers"] == []
        assert status["activeDemoSchoolIDs"] == [school.id]

        audits = db.query(legacy.AuditLog).filter(
            legacy.AuditLog.action == "legacy_demo.accounts_retired"
        ).all()
        assert len(audits) == 1
        assert "history_preserved=true" in audits[0].detail
        assert "school_preserved=true" in audits[0].detail


def test_demo_retirement_is_registered_as_schema_migration():
    assert legacy.SCHEMA_VERSION == "10.6.6"
    source = open(legacy.__file__, "r", encoding="utf-8").read()
    assert '("10.6.6","公开推广收口：停用历史演示学校与默认演示账号，保留历史记录")' in source
    assert 'elif version=="10.6.6":' in source
    assert "retire_legacy_demo_identities(db)" in source
