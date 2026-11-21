"""测试块四：lesson_nodes 最小稳定节点身份层与 stable_node_id 派生规则。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker

from changying.services.node_identity import (
    VALID_NODE_KINDS,
    VALID_QUESTION_TYPES,
    compute_content_hash,
    normalize_node_text,
    register_lesson_nodes_table,
    stable_node_id,
    upsert_lesson_node,
    validate_node_kind_and_question_type,
)


def _make_implementation():
    Base = declarative_base()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    impl = SimpleNamespace(Base=Base, engine=engine, SessionLocal=SessionLocal)
    register_lesson_nodes_table(impl)
    Base.metadata.create_all(engine)
    return impl


def test_stable_node_id_is_deterministic_across_whitespace_and_fullwidth_variants():
    nid1 = stable_node_id("stem", "Q1", "  第1题：春风又绿江南岸，（  ）明月何时照我还？  ")
    nid2 = stable_node_id("STEM", "ｑ１", "\u3000第１题:春风又绿江南岸, (   ) 明月何时照我还?\n\t")
    assert len(nid1) == 40
    assert nid1 == nid2


def test_stable_node_id_is_sensitive_to_content_ref_and_kind_changes():
    base = stable_node_id("stem", "Q1", "春风又绿江南岸")
    changed_text = stable_node_id("stem", "Q1", "春风又绿江南岸（改动一字）")
    changed_ref = stable_node_id("stem", "Q2", "春风又绿江南岸")
    changed_kind = stable_node_id("answer", "Q1", "春风又绿江南岸")
    assert base != changed_text
    assert base != changed_ref
    assert base != changed_kind


def test_lesson_nodes_table_schema_and_unique_constraint():
    impl = _make_implementation()
    table = register_lesson_nodes_table(impl)
    cols = {c.name for c in table.columns}
    assert cols == {
        "id",
        "school_id",
        "lesson_id",
        "node_id",
        "node_kind",
        "question_type",
        "content_hash",
        "location_json",
        "created_at",
    }
    inspector = inspect(impl.engine)
    assert "lesson_nodes" in inspector.get_table_names()

    choice_row = upsert_lesson_node(
        101,
        "stem",
        "choice",
        "下列词语书写完全正确的一项是？",
        question_ref="choice-1",
        school_id=2,
        location={"stage": 5, "ordinal": 1},
        implementation=impl,
    )
    written_row = upsert_lesson_node(
        101,
        "stem",
        "written",
        "请结合全文概括作者的写作意图。",
        question_ref="written-1",
        school_id=2,
        location={"stage": 5, "ordinal": 2},
        implementation=impl,
    )
    assert choice_row["question_type"] == "choice"
    assert written_row["question_type"] == "written"
    assert choice_row["node_id"] != written_row["node_id"]
    assert choice_row["content_hash"] == compute_content_hash("下列词语书写完全正确的一项是？")

    # UniqueConstraint(lesson_id, node_id): 直接插入重复 (lesson_id, node_id) 触发 IntegrityError
    with impl.SessionLocal() as db:
        with pytest.raises(IntegrityError):
            db.execute(
                table.insert().values(
                    school_id=2,
                    lesson_id=101,
                    node_id=choice_row["node_id"],
                    node_kind="stem",
                    question_type="choice",
                    content_hash=choice_row["content_hash"],
                    location_json="{}",
                )
            )
            db.commit()


def test_node_kind_and_question_type_validation():
    for kind in VALID_NODE_KINDS:
        for qtype in VALID_QUESTION_TYPES:
            assert validate_node_kind_and_question_type(kind, qtype) == (kind, qtype)

    with pytest.raises(ValueError, match="节点类型不合法"):
        validate_node_kind_and_question_type("invalid_kind", "choice")

    with pytest.raises(ValueError, match="题型不合法"):
        validate_node_kind_and_question_type("stem", "invalid_type")

    with pytest.raises(ValueError, match="节点类型不能为空"):
        stable_node_id("   ", "Q1", "题干")
    assert normalize_node_text("  ＡＢＣ\u3000１２３ ") == "ABC 123"
