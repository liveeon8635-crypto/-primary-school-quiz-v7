import inspect

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app_v924 as legacy


def test_retire_legacy_demo_identities_preserves_repurposed_school_and_real_users():
    engine = create_engine("sqlite:///:memory:")
    legacy.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with Session() as db:
        school = legacy.School(name="演示小学", code="demo", active=True)
        db.add(school)
        db.flush()

        db.add_all(
            [
                legacy.User(
                    school_id=school.id,
                    username="admin",
                    password_hash="changed-admin",
                    name="平台管理员",
                    role="admin",
                    active=True,
                ),
                legacy.User(
                    school_id=school.id,
                    username="teacher1",
                    password_hash="changed-teacher",
                    name="王老师",
                    role="teacher",
                    active=False,
                ),
                legacy.User(
                    school_id=school.id,
                    username="student1",
                    password_hash="changed-student",
                    name="小明",
                    role="student",
                    grade=3,
                    active=True,
                ),
                legacy.User(
                    school_id=school.id,
                    username="parent1",
                    password_hash="changed-parent",
                    name="小明家长",
                    role="parent",
                    active=True,
                ),
                legacy.User(
                    school_id=school.id,
                    username="liumaidi",
                    password_hash="real-user",
                    name="刘麦迪",
                    role="student",
                    grade=5,
                    active=True,
                ),
            ]
        )
        db.commit()

        result = legacy.retire_legacy_demo_identities(db)
        db.commit()

        refreshed_school = db.get(legacy.School, school.id)
        users = {
            row.username: row
            for row in db.scalars(
                select(legacy.User).where(legacy.User.school_id == school.id)
            ).all()
        }
        audits = db.scalars(
            select(legacy.AuditLog).where(
                legacy.AuditLog.school_id == school.id,
                legacy.AuditLog.action == "legacy_demo.accounts_retired",
            )
        ).all()

        assert refreshed_school.active is True
        assert users["admin"].active is True
        assert users["liumaidi"].active is True
        assert users["teacher1"].active is False
        assert users["student1"].active is False
        assert users["parent1"].active is False
        assert result["retiredLegacyUsers"] == ["student1", "parent1"]
        assert len(audits) == 1
        assert "school_preserved=true" in audits[0].detail
        assert "history_preserved=true" in audits[0].detail

        status = legacy.production_demo_identity_status(db)
        assert status["ok"] is True
        assert status["activeLegacyDemoUsers"] == []
        assert status["activeDemoSchoolIDs"] == [school.id]


def test_demo_account_retirement_is_registered_as_schema_1066():
    source = inspect.getsource(legacy.run_schema_migrations)

    assert legacy.SCHEMA_VERSION == "10.6.6"
    assert '("10.6.6","公开推广收口：停用历史默认演示账号' in source
    assert 'elif version=="10.6.6"' in source
    assert "retire_legacy_demo_identities(db)" in source
