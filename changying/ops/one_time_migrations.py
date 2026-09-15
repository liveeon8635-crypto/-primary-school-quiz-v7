"""Explicitly gated one-time operational migrations.

Nothing in this module mutates data unless the exact migration id is present in
``CHANGYING_ONE_TIME_MIGRATION``.  The currently supported migration only
contains duplicate student records that were manually confirmed as test data.
"""

from __future__ import annotations

import json
import os
from typing import Any

from changying.domain.student_merge import merge_student_records


TEST_DUPLICATE_MERGE_ID = "test-data-dedupe-20260915-v1"
_TEST_DUPLICATE_PAIRS = (
    {"keep_id": 11, "merge_id": 13, "expected_name": "张志轩"},
    {"keep_id": 14, "merge_id": 15, "expected_name": "肖宇晨"},
)


def maybe_apply_one_time_migration(implementation: Any) -> dict[str, Any]:
    migration_id = os.getenv("CHANGYING_ONE_TIME_MIGRATION", "").strip()
    if not migration_id:
        return {"status": "disabled"}
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


__all__ = ["TEST_DUPLICATE_MERGE_ID", "maybe_apply_one_time_migration"]
