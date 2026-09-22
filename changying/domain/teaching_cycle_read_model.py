"""Storage-neutral teaching-cycle read model.

Normalizes existing TeachingProgram academic_year/term/semester facts without
creating or mutating production records.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

from changying.domain.student_continuity import TeachingCycle


def _cycle_kind(term: str) -> str:
    value=(term or "").strip()
    if "寒" in value or "冬" in value:
        return TeachingCycle.WINTER.value
    if "暑" in value or "夏" in value:
        return TeachingCycle.SUMMER.value
    return TeachingCycle.TERM.value


def teaching_cycle_rows(implementation: ModuleType, db: Any, school_id: int) -> list[dict[str, Any]]:
    rows=db.scalars(
        implementation.select(implementation.TeachingProgram)
        .where(implementation.TeachingProgram.school_id == school_id)
        .order_by(
            implementation.TeachingProgram.academic_year.desc(),
            implementation.TeachingProgram.id.desc(),
        )
    ).all()
    out=[]
    for row in rows:
        out.append({
            "sourceType":"teaching_program",
            "sourceID":int(row.id),
            "academicYear":int(row.academic_year),
            "term":str(row.term or ""),
            "semester":str(row.semester or ""),
            "grade":int(row.grade) if row.grade is not None else None,
            "cycleKind":_cycle_kind(str(row.term or "")),
            "title":str(row.title or ""),
            "active":bool(row.active),
        })
    return out


__all__=["teaching_cycle_rows"]
