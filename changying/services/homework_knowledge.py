"""Permanent record of "this student used AI help on this knowledge point" (晚托作业助手).

The help conversation itself is only kept for 90 days, but the knowledge-level fact must outlive it:
a knowledge point the student needed AI help with stays flagged until a later submission shows it is
learned (see ``homework_knowledge_flags``). This module owns the table and the recording; it adds no
new evidence type to the shared learning-evidence vocabulary, so the existing "missing evidence
dimension" screens are not affected.

The AI names the knowledge point in free text. It is matched to the school's own knowledge names
(the ``questions.knowledge`` values for the student's grade) so that the statistics line up with the
ones the rest of the product already computes. A phrase that cannot be matched is stored as-is and
marked unmatched; it is listed but never turns into a flag that nothing could clear.
"""

from __future__ import annotations

import difflib
import logging
import re
from datetime import datetime
from typing import Any

from changying.services.homework_prompts import scrub_question
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, UniqueConstraint, insert, select

LOGGER = logging.getLogger(__name__)

TABLE_NAME = "homework_ai_knowledge"
MATCH_THRESHOLD = 0.6
_STRIP = re.compile(r"[\s·・、，,。.：:；;（）()\[\]【】\-—_/]+")


def _utcnow() -> datetime:
    return datetime.utcnow()


def register_homework_knowledge_table(implementation: Any) -> Table:
    """Idempotently register the table on ``implementation.Base.metadata`` (created by the startup create_all)."""
    metadata = implementation.Base.metadata
    table = metadata.tables.get(TABLE_NAME)
    if table is None:
        table = Table(
            TABLE_NAME,
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, ForeignKey("schools.id"), nullable=False, index=True),
            Column("student_id", Integer, ForeignKey("users.id"), nullable=False, index=True),
            Column("help_id", Integer, nullable=False),  # no FK: the help request is purged after 90 days
            Column("grade", Integer, nullable=True),
            Column("subject", String(30), nullable=False, default=""),
            Column("knowledge_key", String(160), nullable=False, default="", index=True),
            Column("raw_knowledge", String(120), nullable=False, default=""),
            Column("matched", Boolean, nullable=False, default=False),
            Column("question_excerpt", String(120), nullable=False, default=""),
            Column("verify_status", String(12), nullable=False, default="skipped"),
            Column("created_at", DateTime, nullable=False, default=_utcnow, index=True),
            UniqueConstraint("help_id", name="uq_homework_ai_knowledge_help"),
        )
    return table


def _norm(text: str) -> str:
    return _STRIP.sub("", str(text or "")).lower()


def match_knowledge(phrase: str, candidates: list[tuple[str, str]]) -> tuple[str, str] | None:
    """The school knowledge name (subject, knowledge) that best fits the AI's phrase, or None."""
    wanted = _norm(phrase)
    if not wanted:
        return None
    best: tuple[float, tuple[str, str]] | None = None
    for subject, knowledge in candidates:
        name = _norm(knowledge)
        if not name:
            continue
        if wanted == name:
            score = 1.0
        elif name in wanted or wanted in name:
            score = 0.7 + 0.3 * min(len(name), len(wanted)) / max(len(name), len(wanted))
        else:
            score = difflib.SequenceMatcher(None, wanted, name).ratio()
        if best is None or score > best[0]:
            best = (score, (subject, knowledge))
    if best is not None and best[0] >= MATCH_THRESHOLD:
        return best[1]
    return None


def school_knowledge(implementation: Any, db: Any, school_id: int, grade: int | None) -> list[tuple[str, str]]:
    question = implementation.Question
    query = select(question.subject, question.knowledge).where(question.school_id == school_id).distinct()
    if grade is not None:
        query = query.where(question.grade == int(grade))
    return [(str(s or ""), str(k or "")) for s, k in db.execute(query).all() if str(k or "").strip()]


def record_ai_help(
    implementation: Any,
    db: Any,
    *,
    school_id: int,
    student_id: int,
    help_id: int,
    grade: int | None,
    knowledge_point: str,
    question_text: str,
    verify_status: str,
) -> bool:
    """Write the permanent knowledge record for one AI-assisted question. Never raises: recording must not break the answer."""
    try:
        table = register_homework_knowledge_table(implementation)
        if db.execute(select(table.c.id).where(table.c.help_id == help_id)).first() is not None:
            return False
        raw = str(knowledge_point or "").strip()[:120]
        matched = match_knowledge(raw, school_knowledge(implementation, db, school_id, grade)) if raw else None
        subject, key = matched if matched else ("", raw)
        db.execute(
            insert(table).values(
                school_id=school_id,
                student_id=student_id,
                help_id=help_id,
                grade=grade,
                subject=subject[:30],
                knowledge_key=key[:160],
                raw_knowledge=raw,
                matched=bool(matched),
                question_excerpt=" ".join(scrub_question(str(question_text or "")).split())[:120],  # permanent: contact details removed
                verify_status=str(verify_status or "skipped")[:12],
                created_at=_utcnow(),
            )
        )
        db.commit()
        return True
    except Exception:  # noqa: BLE001 - the student's answer is already saved; just report
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        LOGGER.exception("homework_ai_knowledge_record_failed help_id=%s", help_id)
        return False


__all__ = ["TABLE_NAME", "match_knowledge", "record_ai_help", "register_homework_knowledge_table", "school_knowledge"]
