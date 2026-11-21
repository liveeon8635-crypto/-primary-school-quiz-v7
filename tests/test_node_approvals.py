"""测试块四：node_approvals 审核通过、撤回留痕、唯一约束与内容变更批量失效。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker

from changying.ops.one_time_migrations import (
    NODE_APPROVAL_REVEAL_MIGRATION_VERSION,
    maybe_apply_one_time_migration,
)
from changying.services.node_approvals import (
     approve_node,
    get_node_approval,
    invalidate_approvals_on_content_change,
    register_node_approvals_table,
    revoke_node,
)
from changying.services.node_identity import (
    compute_content_hash,
    register_lesson_nodes_table,
    stable_node_id,
    upsert_lesson_node,
)


def _make_implementation():
    Base = declarative_base()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    impl = SimpleNamespace(Base=Base, engine=engine, SessionLocal=SessionLocal)
    register_lesson_nodes_table(impl)
    register_node_approvals_table(impl)
    Base.metadata.create_all(engine)
    return impl


def test_approve_then_revoke_keeps_row_and_reapprove_clears_revocation():
    impl = _make_implementation()
    table = register_node_approvals_table(impl)
    cols = {c.name for c in table.columns}
    assert cols == {
        "id",
        "school_id",
        "lesson_id",
        "node_id",
        "approved_content_hash",
        "approved_by",
        "approved_at",
        "revoked_at",
        "revoke_reason",
    }

    node = upsert_lesson_node(
        201,
        "stem",
        "choice",
        "选择正确读音：参差（cēn cī）",
        question_ref="q1",
        school_id=3,
        implementation=impl,
    )
    approved = approve_node(
        201,
        node["node_id"],
        node["content_hash"],
        approved_by=12,
        school_id=3,
        implementation=impl,
    )
    assert approved["lesson_id"] == 201
    assert approved["node_id"] == node["node_id"]
    assert approved["approved_content_hash"] == node["content_hash"]
    assert approved["approved_by"] == 12
    assert approved["revoked_at"] is None
    assert approved["revoke_reason"] is None

    revoked = revoke_node(201, node["node_id"], "教师发现错字撤回", implementation=impl)
    assert revoked["id"] == approved["id"]
    assert revoked["revoked_at"] is not None
    assert revoked["revoke_reason"] == "教师发现错字撤回"

    # 撤回不删行，且再次 approve 时复用同一行并将 revoked_at 置回 None
    new_hash = compute_content_hash("选择正确读音：参差（cēn cī）【修订版】")
    reapproved = approve_node(
        201,
        node["node_id"],
        new_hash,
        approved_by=15,
        school_id=3,
        implementation=impl,
    )
    assert reapproved["id"] == approved["id"]
    assert reapproved["approved_content_hash"] == new_hash
    assert reapproved["approved_by"] == 15
    assert reapproved["revoked_at"] is None
    assert reapproved["revoke_reason"] is None

    with impl.SessionLocal() as db:
        total = db.scalar(select(func.count()).select_from(table))
        assert total == 1


def test_node_approvals_unique_constraint_and_missing_revoke():
    impl = _make_implementation()
    table = register_node_approvals_table(impl)
    nid = stable_node_id("answer", "q2", "参考答案：A")
    approve_node(202, nid, compute_content_hash("参考答案：A"), approved_by=1, school_id=1, implementation=impl)

    with impl.SessionLocal() as db:
        with pytest.raises(IntegrityError):
            db.execute(
                table.insert().values(
                    school_id=1,
                    lesson_id=202,
                    node_id=nid,
                    approved_content_hash="dup",
                    approved_by=1,
                )
            )
            db.commit()

    with pytest.raises(LookupError, match="未找到该节点的审核记录"):
        revoke_node(202, "nonexistent_node_id", "撤回不存在节点", implementation=impl)


def test_invalidate_approvals_on_content_change_batch_revokes_only_target_nodes():
    impl = _make_implementation()
    n1 = stable_node_id("stem", "q1", "第一题题干")
    n2 = stable_node_id("hint", "q1", "第一题提示")
    n3 = stable_node_id("answer", "q1", "第一题答案")

    for nid, text in ((n1, "第一题题干"), (n2, "第一题提示"), (n3, "第一题答案")):
        approve_node(301, nid, compute_content_hash(text), approved_by=7, school_id=2, implementation=impl)

    invalidated = invalidate_approvals_on_content_change(301, [n1, n2], implementation=impl)
    assert [row["node_id"] for row in invalidated] == [n1, n2]
    for row in invalidated:
        assert row["revoked_at"] is not None
        assert row["revoke_reason"] == "内容变更自动失效"

    untouched = get_node_approval(301, n3, implementation=impl)
    assert untouched is not None
    assert untouched["revoked_at"] is None
    assert untouched["revoke_reason"] is None


def test_one_time_migration_registers_tables_and_records_schema_migration():
    import app_v924 as legacy

    info = maybe_apply_one_time_migration(legacy)
    assert info["schema_migration"] == NODE_APPROVAL_REVEAL_MIGRATION_VERSION
    with legacy.SessionLocal() as db:
        mig = db.get(legacy.SchemaMigration, NODE_APPROVAL_REVEAL_MIGRATION_VERSION)
        assert mig is not None
        assert "块四" in mig.description
