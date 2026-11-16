"""Guarded merge support for duplicate student records.

The merge keeps one durable ``users.id`` as the student identity, rewrites every
foreign-key-like ``student_id`` reference to that id, preserves class/history
rows, archives the duplicate login, and appends an audit record.  It is designed
for explicitly confirmed duplicates only; same-name matching is a safety guard,
not an automatic identity rule for normal production use.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


class StudentMergeError(RuntimeError):
    """Base error for a merge that is unsafe to execute."""


class StudentMergeConflict(StudentMergeError):
    """Raised when moving rows would violate an existing unique constraint."""


@dataclass(frozen=True)
class MergePlan:
    keep_id: int
    merge_id: int
    school_id: int
    normalized_name: str
    target_grade: int | None
    reference_counts: dict[str, int]
    conflicts: tuple[dict[str, Any], ...]


def _normalized_name(value: str | None) -> str:
    return re.sub(r"\s+", "", value or "").casefold()


def _quote(bind, identifier: str) -> str:
    return bind.dialect.identifier_preparer.quote(identifier)


def _student_tables(session: Session) -> list[str]:
    inspector = inspect(session.connection())
    out: list[str] = []
    for table in inspector.get_table_names():
        names = {column["name"] for column in inspector.get_columns(table)}
        if "student_id" in names:
            out.append(table)
    return sorted(out)


def _count_refs(session: Session, table: str, student_id: int) -> int:
    bind = session.connection()
    qtable = _quote(bind, table)
    return int(
        session.execute(
            text(f"SELECT COUNT(*) FROM {qtable} WHERE student_id=:student_id"),
            {"student_id": student_id},
        ).scalar_one()
    )


def _unique_conflicts(session: Session, table: str, keep_id: int, merge_id: int) -> list[dict[str, Any]]:
    bind = session.connection()
    inspector = inspect(bind)
    qtable = _quote(bind, table)
    conflicts: list[dict[str, Any]] = []
    for constraint in inspector.get_unique_constraints(table):
        columns = list(constraint.get("column_names") or [])
        if "student_id" not in columns or len(columns) < 2:
            continue
        other_columns = [column for column in columns if column != "student_id"]
        comparisons = []
        for column in other_columns:
            qcolumn = _quote(bind, column)
            comparisons.append(
                f"(k.{qcolumn}=m.{qcolumn} OR (k.{qcolumn} IS NULL AND m.{qcolumn} IS NULL))"
            )
        where = " AND ".join(comparisons) if comparisons else "1=1"
        exists = session.execute(
            text(
                f"SELECT 1 FROM {qtable} m JOIN {qtable} k ON k.student_id=:keep_id "
                f"WHERE m.student_id=:merge_id AND {where} LIMIT 1"
            ),
            {"keep_id": keep_id, "merge_id": merge_id},
        ).first()
        if exists:
            conflicts.append(
                {
                    "table": table,
                    "constraint": constraint.get("name") or "unnamed_unique",
                    "columns": columns,
                }
            )
    return conflicts


def _row_lock_sql(session: Session) -> str:
    """Lock the student rows for the rest of the transaction (PostgreSQL/MySQL only).

    SQLite has no row locks, so the clause is skipped there (tests run on SQLite).
    """
    name = getattr(getattr(session.get_bind(), "dialect", None), "name", "")
    return " FOR UPDATE" if name in {"postgresql", "mysql", "mariadb"} else ""


def plan_student_merge(session: Session, keep_id: int, merge_id: int, *, expected_name: str | None = None) -> MergePlan:
    if keep_id == merge_id:
        raise StudentMergeError("keep_id and merge_id must differ")

    rows = session.execute(
        text(
            "SELECT id, school_id, name, role, grade, active FROM users "
            "WHERE id IN (:keep_id,:merge_id) ORDER BY id" + _row_lock_sql(session)
        ),
        {"keep_id": keep_id, "merge_id": merge_id},
    ).mappings().all()
    by_id = {int(row["id"]): row for row in rows}
    if keep_id not in by_id or merge_id not in by_id:
        raise StudentMergeError("both student ids must exist")
    keep, duplicate = by_id[keep_id], by_id[merge_id]
    if keep["role"] != "student" or duplicate["role"] != "student":
        raise StudentMergeError("both records must have role=student")
    if int(keep["school_id"]) != int(duplicate["school_id"]):
        raise StudentMergeError("student records belong to different schools")

    keep_name = _normalized_name(keep["name"])
    duplicate_name = _normalized_name(duplicate["name"])
    if not keep_name or keep_name != duplicate_name:
        raise StudentMergeError("student names do not match")
    if expected_name is not None and keep_name != _normalized_name(expected_name):
        raise StudentMergeError("student name no longer matches authorized migration")

    grades = [int(value) for value in (keep["grade"], duplicate["grade"]) if value is not None]
    target_grade = max(grades) if grades else None
    counts: dict[str, int] = {}
    conflicts: list[dict[str, Any]] = []
    for table in _student_tables(session):
        count = _count_refs(session, table, merge_id)
        if count:
            counts[table] = count
            conflicts.extend(_unique_conflicts(session, table, keep_id, merge_id))

    return MergePlan(
        keep_id=keep_id,
        merge_id=merge_id,
        school_id=int(keep["school_id"]),
        normalized_name=keep_name,
        target_grade=target_grade,
        reference_counts=counts,
        conflicts=tuple(conflicts),
    )


def merge_student_records(
    session: Session,
    keep_id: int,
    merge_id: int,
    *,
    expected_name: str | None = None,
    actor_id: int | None = None,
    reason: str = "confirmed duplicate student record",
) -> dict[str, Any]:
    """Merge an explicitly confirmed duplicate inside the caller's transaction.

    The function never commits.  The caller must commit the transaction after
    inspecting the returned summary.  Any unique-key collision aborts before a
    write is made so potentially conflicting learning records are never dropped.
    """

    plan = plan_student_merge(session, keep_id, merge_id, expected_name=expected_name)
    if plan.conflicts:
        raise StudentMergeConflict(json.dumps(plan.conflicts, ensure_ascii=False, sort_keys=True))

    duplicate_active = session.execute(
        text("SELECT active FROM users WHERE id=:merge_id"), {"merge_id": merge_id}
    ).scalar_one()
    if not duplicate_active and not plan.reference_counts:
        return {
            "status": "already_merged",
            "keep_id": keep_id,
            "merge_id": merge_id,
            "moved": {},
            "target_grade": plan.target_grade,
        }

    moved: dict[str, int] = {}
    bind = session.connection()
    for table, expected_count in plan.reference_counts.items():
        qtable = _quote(bind, table)
        result = session.execute(
            text(f"UPDATE {qtable} SET student_id=:keep_id WHERE student_id=:merge_id"),
            {"keep_id": keep_id, "merge_id": merge_id},
        )
        moved[table] = int(result.rowcount if result.rowcount is not None and result.rowcount >= 0 else expected_count)
        if moved[table] != expected_count:
            # Rows appeared or vanished between planning and writing: abort the transaction
            # instead of half-merging a student's history.
            raise StudentMergeError(
                f"reference count changed during merge for {table}: planned {expected_count}, moved {moved[table]}"
            )

    session.execute(
        text("UPDATE users SET grade=:grade WHERE id=:keep_id"),
        {"grade": plan.target_grade, "keep_id": keep_id},
    )
    session.execute(
        text("UPDATE users SET active=false WHERE id=:merge_id"),
        {"merge_id": merge_id},
    )

    inspector = inspect(bind)
    if "audit_logs" in inspector.get_table_names():
        detail = json.dumps(
            {
                "keep_id": keep_id,
                "merged_id": merge_id,
                "reason": reason,
                "moved": moved,
                "target_grade": plan.target_grade,
                "archived_duplicate": True,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        session.execute(
            text(
                "INSERT INTO audit_logs (school_id,user_id,action,detail,created_at) "
                "VALUES (:school_id,:actor_id,'student.merge',:detail,:created_at)"
            ),
            {
                "school_id": plan.school_id,
                "actor_id": actor_id,
                "detail": detail,
                "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
            },
        )

    return {
        "status": "merged",
        "keep_id": keep_id,
        "merge_id": merge_id,
        "moved": moved,
        "target_grade": plan.target_grade,
    }


__all__ = [
    "MergePlan",
    "StudentMergeConflict",
    "StudentMergeError",
    "merge_student_records",
    "plan_student_merge",
]
