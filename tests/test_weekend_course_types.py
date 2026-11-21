from __future__ import annotations

import json
from types import SimpleNamespace
from datetime import datetime

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, create_mock_engine, insert, inspect
from sqlalchemy.orm import Session

from changying.services.weekend_course_types import (
    course_type_for,
    compare_and_set_course_type,
    frozen_session,
    lesson_snapshot,
    register_weekend_course_type_tables,
    workflow_for,
    WorkflowRevisionConflict,
    store_pending_materials,
)
from changying.services.weekend_stages import stage_by_no, stages_for


def test_workflow_selection_is_persisted_and_old_chinese_lessons_remain_unset():
    metadata = MetaData()
    legacy_lessons = Table("teaching_lessons", metadata,
                           Column("id", Integer, primary_key=True), Column("title", String(80)))
    implementation = SimpleNamespace(Base=SimpleNamespace(metadata=metadata))
    tables = register_weekend_course_type_tables(implementation)
    engine = create_engine("sqlite://")
    legacy_lessons.create(engine)
    with engine.begin() as conn:
        conn.execute(insert(legacy_lessons).values(id=12, title="舐犊情深"))
    implementation.Base.metadata.create_all(engine)
    implementation.Base.metadata.create_all(engine)  # idempotent upgrade
    with engine.connect() as conn:
        assert conn.execute(legacy_lessons.select()).first().title == "舐犊情深"
        assert {"weekend_lesson_workflows", "weekend_session_workflows", "weekend_lesson_materials"}.issubset(
            set(inspect(engine).get_table_names())
        )
    old_chinese = SimpleNamespace(school_id=1, program_id=1, subject="语文", lesson_no=12)
    math = SimpleNamespace(school_id=1, program_id=1, subject="数学", lesson_no=12)

    with Session(engine) as db:
        assert course_type_for(db, implementation, old_chinese) is None
        assert course_type_for(db, implementation, math) == "math"
        db.execute(insert(tables["config"]).values(
            school_id=1, program_id=1, subject="语文", lesson_no=12,
            course_type="reading", revision=1, updated_by=7,
        ))
        db.commit()
        assert course_type_for(db, implementation, old_chinese) == "reading"
        assert workflow_for(db, implementation, old_chinese).revision == 1


def test_frozen_classroom_snapshots_keep_independent_type_and_content():
    implementation = SimpleNamespace(Base=SimpleNamespace(metadata=MetaData()))
    tables = register_weekend_course_type_tables(implementation)
    engine = create_engine("sqlite://")
    implementation.Base.metadata.create_all(engine)
    lesson = SimpleNamespace(
        id=12, school_id=1, program_id=1, subject="语文", lesson_no=12, unit="阅读",
        title="舐犊情深", core_target="体会人物情感", duration_min=120,
        teacher_plan="教师教学提示", reading_plan="母亲的那盏灯；父亲的泥脚",
        writing_plan="", examples_json="[]", ppt_json="[]", closure_training="课后反馈",
        essay_review="",
    )
    original_snapshot = lesson_snapshot(lesson)
    with Session(engine) as db:
        db.execute(insert(tables["frozen"]), [
            {"session_id": 501, "school_id": 1, "lesson_id": 12, "course_type": "reading",
             "revision": 3, "lesson_json": original_snapshot},
            {"session_id": 502, "school_id": 1, "lesson_id": 12, "course_type": "writing",
             "revision": 4, "lesson_json": json.dumps({"title": "另一个班级的版本"}, ensure_ascii=False)},
        ])
        db.commit()

        lesson.title = "后续修订标题"
        assert frozen_session(db, implementation, 501) == {
            "courseType": "reading", "revision": 3, "lesson": json.loads(original_snapshot),
        }
        second = frozen_session(db, implementation, 502)
        assert second == {"courseType": "writing", "revision": 4, "lesson": {"title": "另一个班级的版本"}}


def test_course_type_compare_and_set_rejects_stale_edits_without_overwriting():
    implementation = SimpleNamespace(Base=SimpleNamespace(metadata=MetaData()))
    tables = register_weekend_course_type_tables(implementation)
    engine = create_engine("sqlite://")
    implementation.Base.metadata.create_all(engine)
    args = dict(
        school_id=1, program_id=1, lesson_no=12, lesson_id=None,
        updated_by=7, updated_at=datetime(2026, 1, 1),
    )
    with Session(engine) as db:
        assert compare_and_set_course_type(
            db, implementation, course_type="reading", expected_revision=0, **args,
        ) == 1
        db.commit()
        assert compare_and_set_course_type(
            db, implementation, course_type="writing", expected_revision=1, **args,
        ) == 2
        db.commit()
        try:
            compare_and_set_course_type(
                db, implementation, course_type="reading", expected_revision=1, **args,
            )
        except WorkflowRevisionConflict:
            pass
        else:
            raise AssertionError("a stale teacher form must not overwrite the latest workflow")
        row = db.execute(tables["config"].select()).first()
        assert row.course_type == "writing" and row.revision == 2


def test_workflow_schema_compiles_for_postgresql():
    implementation = SimpleNamespace(Base=SimpleNamespace(metadata=MetaData()))
    register_weekend_course_type_tables(implementation)
    statements = []
    engine = create_mock_engine("postgresql://", lambda statement, *_a, **_kw: statements.append(str(statement)))
    implementation.Base.metadata.create_all(engine)
    joined = "\n".join(statements).lower()
    assert "create table weekend_lesson_workflows" in joined
    assert "create table weekend_session_workflows" in joined
    assert "create table weekend_lesson_materials" in joined
    assert "uq_weekend_lesson_workflow" in joined


def test_imported_pictures_persist_as_pending_and_keep_provenance():
    implementation = SimpleNamespace(Base=SimpleNamespace(metadata=MetaData()))
    tables = register_weekend_course_type_tables(implementation)
    engine = create_engine("sqlite://")
    implementation.Base.metadata.create_all(engine)
    material = {"data_url": "data:image/jpeg;base64," + "A" * 40,
                "source_name": "image4.png", "source_sha256": "a" * 64, "source_format": "png"}
    with Session(engine) as db:
        assert store_pending_materials(db, implementation, school_id=9, lesson_id=12,
                                      source_file="语文12次.docx", created_by=7, figures=[material]) == 1
        db.commit()
        rows = db.execute(tables["materials"].select()).all()
        assert store_pending_materials(db, implementation, school_id=9, lesson_id=12,
                                      source_file="语文12次.docx", created_by=7, figures=[material]) == 0
    assert len(rows) == 1
    row = rows[0]
    assert (row.status, row.relationship, row.stage_no, row.source_file, row.source_part) == (
        "pending", "", None, "语文12次.docx", "image4.png")
    assert row.source_sha256 == "a" * 64 and row.source_format == "png"


def test_missing_question_gate_closes_new_chinese_classroom_but_preserves_legacy():
    from sqlalchemy import Text
    from changying.services.weekend_answers import question_is_open

    implementation = SimpleNamespace(Base=SimpleNamespace(metadata=MetaData()))
    tables = register_weekend_course_type_tables(implementation)
    gate = Table("weekend_open_questions", implementation.Base.metadata,
                 Column("session_id", Integer, primary_key=True), Column("school_id", Integer),
                 Column("opened_question_ids", Text))
    engine = create_engine("sqlite://")
    implementation.Base.metadata.create_all(engine)
    chinese = SimpleNamespace(id=501, school_id=1)
    legacy = SimpleNamespace(id=502, school_id=1)
    with Session(engine) as db:
        db.execute(insert(tables["frozen"]).values(session_id=501, school_id=1, lesson_id=12,
            course_type="reading", revision=1, lesson_json="{}"))
        db.commit()
        assert question_is_open(implementation, db, chinese, "choice", 9) is False
        assert question_is_open(implementation, db, legacy, "choice", 9) is True
        db.execute(insert(gate).values(session_id=501, school_id=1, opened_question_ids='["choice:9"]'))
        db.commit()
        assert question_is_open(implementation, db, chinese, "choice", 9) is True
        assert question_is_open(implementation, db, chinese, "choice", 10) is False


def test_course_workflows_have_the_expected_six_steps_and_math_stays_seven():
    assert len(stages_for("reading")) == 6
    assert [stage["name"] for stage in stages_for("reading")] == [
        "点名与回顾", "短文阅读", "长文阅读", "考点总结", "综合练习", "课后反馈",
    ]
    assert len(stages_for("writing")) == 6
    assert [stage["name"] for stage in stages_for("writing")] == [
        "点名与回顾", "范文导览", "看图写话", "技法梳理", "随堂练习", "课后反馈",
    ]
    assert len(stages_for("math")) == 7
    assert stage_by_no(5, "reading")["key"] == "integrated_practice"
    assert stage_by_no(5, "writing")["key"] == "writing_practice"
    assert stages_for(None) == []
