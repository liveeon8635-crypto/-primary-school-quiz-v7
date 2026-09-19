"""Assignment application services.

This is a transitional service layer while ORM models still live in the legacy
module. Model classes are injected explicitly so this module does not import the
legacy application or create a circular dependency.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select


def teacher_assignment_rows(
    db: Any,
    *,
    assignment_model: Any,
    class_model: Any,
    school_id: int,
    teacher_id: int,
) -> list[Any]:
    """Return a teacher's assignments using the existing legacy query contract."""
    statement = (
        select(assignment_model)
        .join(class_model, assignment_model.class_id == class_model.id)
        .where(
            assignment_model.school_id == school_id,
            class_model.teacher_id == teacher_id,
        )
        .order_by(assignment_model.id.desc())
    )
    return list(db.scalars(statement).all())


__all__ = ["teacher_assignment_rows"]
