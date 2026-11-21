"""Explicitly gated one-time operational migrations and additive schema migrations.

Nothing in this module mutates business data unless the exact migration id is present in
``CHANGYING_ONE_TIME_MIGRATION``. Additive schema migrations (such as Block 4 node
identity/approvals/reveal tables) are registered idempotently via ``create_all`` and
recorded in ``schema_migrations``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from typing import Any

from changying.domain.student_merge import merge_student_records
from changying.web.weekend_node_reveal import register_block4_node_tables
from changying.web.weekend_paired_import import register_paired_import_tables
from changying.web.weekend_written import register_written_tables


TEST_DUPLICATE_MERGE_ID = "test-data-dedupe-20260915-v1"
NODE_APPROVAL_REVEAL_MIGRATION_VERSION = "10.6.7"
NODE_APPROVAL_REVEAL_MIGRATION_DESC = (
    "语文周末课块四：节点稳定 ID、审核真源与逐级开放撤回表（lesson_nodes / node_approvals / node_reveal_states）"
)
PAIRED_IMPORT_WRITTEN_VERSIONS_MIGRATION_VERSION = "10.6.8"
PAIRED_IMPORT_WRITTEN_VERSIONS_MIGRATION_DESC = (
    "语文周末课：成对导入绑定、勘误留痕与多图版本化批注表"
)
_TEST_DUPLICATE_PAIRS = (
    {"keep_id": 11, "merge_id": 13, "expected_name": "张志轩"},
    {"keep_id": 14, "merge_id": 15, "expected_name": "肖宇晨"},
)


def apply_node_approval_reveal_migration(implementation: Any) -> dict[str, Any]:
    """幂等建表（lesson_nodes / node_approvals / node_reveal_states）并在 schema_migrations 记账。"""
    tables = register_block4_node_tables(implementation)
    engine = getattr(implementation, "engine", None)
    Base = getattr(implementation, "Base", None)
    if engine is not None and Base is not None:
        create_targets = list(tables.values())
        schema_table = Base.metadata.tables.get("schema_migrations")
        if schema_table is not None:
            create_targets.append(schema_table)
        Base.metadata.create_all(engine, tables=create_targets)

    SessionLocal = getattr(implementation, "SessionLocal", None)
    SchemaMigration = getattr(implementation, "SchemaMigration", None)
    recorded = False
    if SessionLocal is not None and SchemaMigration is not None:
        with SessionLocal() as session:
            existing = session.get(SchemaMigration, NODE_APPROVAL_REVEAL_MIGRATION_VERSION)
            if existing is None:
                base_row = session.get(SchemaMigration, "10.6.6")
                if base_row is not None and getattr(base_row, "applied_at", None) is not None:
                    applied_at = base_row.applied_at - timedelta(seconds=1)
                else:
                    applied_at = datetime.utcnow() - timedelta(seconds=1)
                session.add(
                    SchemaMigration(
                        version=NODE_APPROVAL_REVEAL_MIGRATION_VERSION,
                        description=NODE_APPROVAL_REVEAL_MIGRATION_DESC,
                        applied_at=applied_at,
                    )
                )
                session.commit()
                recorded = True
    return {
        "version": NODE_APPROVAL_REVEAL_MIGRATION_VERSION,
        "description": NODE_APPROVAL_REVEAL_MIGRATION_DESC,
        "tables": sorted(tables.keys()),
        "recorded": recorded,
    }


def apply_paired_import_and_written_versions_migration(implementation: Any) -> dict[str, Any]:
    """幂等建表（lesson_import_pairs / lesson_content_bindings / lesson_errata_logs / submission_versions / annotations）。"""
    paired = register_paired_import_tables(implementation)
    written = register_written_tables(implementation)
    new_tables = {
        **paired,
        "weekend_written_submission_versions": written["submission_versions"],
        "weekend_written_annotations": written["annotations"],
    }
    engine = getattr(implementation, "engine", None)
    Base = getattr(implementation, "Base", None)
    if engine is not None and Base is not None:
        create_targets = list(new_tables.values())
        schema_table = Base.metadata.tables.get("schema_migrations")
        if schema_table is not None:
            create_targets.append(schema_table)
        Base.metadata.create_all(engine, tables=create_targets)
    SessionLocal = getattr(implementation, "SessionLocal", None)
    SchemaMigration = getattr(implementation, "SchemaMigration", None)
    recorded = False
    if SessionLocal is not None and SchemaMigration is not None:
        with SessionLocal() as session:
            existing = session.get(SchemaMigration, PAIRED_IMPORT_WRITTEN_VERSIONS_MIGRATION_VERSION)
            if existing is None:
                session.add(
                    SchemaMigration(
                        version=PAIRED_IMPORT_WRITTEN_VERSIONS_MIGRATION_VERSION,
                        description=PAIRED_IMPORT_WRITTEN_VERSIONS_MIGRATION_DESC,
                        applied_at=datetime.utcnow(),
                    )
                )
                session.commit()
                recorded = True
    return {
        "version": PAIRED_IMPORT_WRITTEN_VERSIONS_MIGRATION_VERSION,
        "description": PAIRED_IMPORT_WRITTEN_VERSIONS_MIGRATION_DESC,
        "tables": sorted(new_tables.keys()),
        "recorded": recorded,
    }


def maybe_apply_one_time_migration(implementation: Any) -> dict[str, Any]:
    schema_info = apply_node_approval_reveal_migration(implementation)
    paired_info = apply_paired_import_and_written_versions_migration(implementation)
    migration_id = os.getenv("CHANGYING_ONE_TIME_MIGRATION", "").strip()
    if not migration_id:
        return {"status": "disabled", "schema_migration": schema_info["version"], "tables": schema_info["tables"] + paired_info["tables"]}
    if migration_id == NODE_APPROVAL_REVEAL_MIGRATION_VERSION:
        return {"status": "applied", "migration": migration_id, **schema_info}
    if migration_id == PAIRED_IMPORT_WRITTEN_VERSIONS_MIGRATION_VERSION:
        return {"status": "applied", "migration": migration_id, **paired_info}
    if migration_id != TEST_DUPLICATE_MERGE_ID:
        raise RuntimeError(f"unsupported one-time migration: {migration_id}")

    SessionLocal = getattr(implementation, "SessionLocal", None)
    if SessionLocal is None:
        raise RuntimeError("production implementation does not expose SessionLocal")

    results: list[dict[str, Any]] = []
    with SessionLocal() as session:
        try:
            for item in _TEST_DUPLICATE_PAIRS:
                results.append(
                    merge_student_records(
                        session,
                        item["keep_id"],
                        item["merge_id"],
                        expected_name=item["expected_name"],
                        actor_id=None,
                        reason="user-confirmed duplicate test record; same-name records were created during setup testing",
                    )
                )
            session.commit()
        except Exception:
            session.rollback()
            raise

    summary = {
        "event": "CHANGYING_ONE_TIME_MIGRATION_APPLIED",
        "migration": migration_id,
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return summary


__all__ = [
    "NODE_APPROVAL_REVEAL_MIGRATION_DESC",
    "NODE_APPROVAL_REVEAL_MIGRATION_VERSION",
    "TEST_DUPLICATE_MERGE_ID",
    "apply_node_approval_reveal_migration",
    "maybe_apply_one_time_migration",
]
