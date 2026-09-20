"""Central textbook registry and cross-subject/version consistency guard.

The registry is intentionally conservative.  It only declares textbook lines
that Changying has explicitly verified and supports in the automatic Grade 5
assessment/reinforcement loop.  Ambiguous labels are rejected instead of being
silently guessed into a different edition.
"""

from __future__ import annotations

from functools import wraps
from types import ModuleType
from typing import Any

from fastapi import HTTPException


MATH_G5_TEXTBOOK = "人教版"
MATH_G5_TEXTBOOK_LABEL = "人教版（当前最新版）"
CHINESE_G5_TEXTBOOK = "统编版（人民教育出版社）"
ENGLISH_G5_TEXTBOOK = "人教版（PEP·当前最新版）"


class TextbookRegistryError(ValueError):
    """Raised when a registered grade/subject receives an unsafe textbook label."""


_REGISTRY: dict[tuple[int, str], dict[str, Any]] = {
    (5, "数学"): {
        "canonical": MATH_G5_TEXTBOOK,
        "aliases": {
            MATH_G5_TEXTBOOK: MATH_G5_TEXTBOOK,
            MATH_G5_TEXTBOOK_LABEL: MATH_G5_TEXTBOOK,
        },
    },
    (5, "语文"): {
        "canonical": CHINESE_G5_TEXTBOOK,
        "aliases": {
            CHINESE_G5_TEXTBOOK: CHINESE_G5_TEXTBOOK,
            "统编版": CHINESE_G5_TEXTBOOK,
            "统编版（人教社）": CHINESE_G5_TEXTBOOK,
        },
    },
    (5, "英语"): {
        "canonical": ENGLISH_G5_TEXTBOOK,
        "aliases": {
            ENGLISH_G5_TEXTBOOK: ENGLISH_G5_TEXTBOOK,
            "PEP·当前最新版": ENGLISH_G5_TEXTBOOK,
        },
    },
}


def registered_subjects(grade: int) -> list[str]:
    return [
        subject
        for (registered_grade, subject) in _REGISTRY
        if registered_grade == int(grade)
    ]


def registered_textbooks(grade: int, subject: str) -> list[str]:
    entry = _REGISTRY.get((int(grade), str(subject or "").strip()))
    return [str(entry["canonical"])] if entry else []


def is_registered_scope(grade: int, subject: str) -> bool:
    return (int(grade), str(subject or "").strip()) in _REGISTRY


def normalize_textbook(
    grade: int,
    subject: str,
    textbook: str,
    *,
    default_registered: bool = False,
) -> str:
    """Return a canonical textbook label, rejecting unsafe registered aliases.

    Unsupported grade/subject pairs remain untouched so this guard does not
    accidentally outlaw older/manual workflows outside the currently verified
    automatic curriculum surface.
    """
    key = (int(grade), str(subject or "").strip())
    raw = str(textbook or "").strip()
    entry = _REGISTRY.get(key)
    if entry is None:
        return raw
    if not raw:
        return str(entry["canonical"]) if default_registered else ""
    normalized = entry["aliases"].get(raw)
    if normalized:
        return str(normalized)
    canonical = str(entry["canonical"])
    raise TextbookRegistryError(
        f"{key[0]}年级{key[1]}当前只允许使用核定教材“{canonical}”；"
        "不支持把其他出版社教材、旧版教材或其他学科教材当作同一版本混用"
    )


def require_textbook(grade: int, subject: str, textbook: str) -> str:
    normalized = normalize_textbook(grade, subject, textbook)
    if is_registered_scope(grade, subject) and not normalized:
        canonical = registered_textbooks(grade, subject)[0]
        raise TextbookRegistryError(
            f"{int(grade)}年级{str(subject or '').strip()}必须明确使用核定教材“{canonical}”"
        )
    return normalized


def normalize_question_batch(questions: list[Any]) -> tuple[int, str, str] | None:
    """Normalize one assignment batch and guarantee one grade/subject/textbook line."""
    if not questions:
        return None
    scope: tuple[int, str, str] | None = None
    for question in questions:
        grade = int(getattr(question, "grade", 0) or 0)
        subject = str(getattr(question, "subject", "") or "").strip()
        raw_textbook = str(getattr(question, "textbook", "") or "").strip()
        textbook = require_textbook(grade, subject, raw_textbook)
        if textbook != raw_textbook:
            setattr(question, "textbook", textbook)
        current = (grade, subject, textbook)
        if scope is None:
            scope = current
        elif current != scope:
            raise TextbookRegistryError(
                "同一次布置的题目必须属于同一年级、同一科目和同一教材版本，不能跨学科或跨教材混用"
            )
    return scope


def _route(implementation: ModuleType, path: str, method: str):
    for route in implementation.app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route
    raise RuntimeError(f"route not found: {method} {path}")


def _raise_http(error: TextbookRegistryError) -> None:
    raise HTTPException(400, str(error))


def _normalize_body_textbook(body: Any) -> None:
    try:
        canonical = require_textbook(
            int(getattr(body, "grade", 0) or 0),
            str(getattr(body, "subject", "") or ""),
            str(getattr(body, "textbook", "") or ""),
        )
    except TextbookRegistryError as exc:
        _raise_http(exc)
    if canonical != str(getattr(body, "textbook", "") or "").strip():
        setattr(body, "textbook", canonical)


def _validate_paper_body(implementation: ModuleType, body: Any, user: Any, db: Any) -> None:
    grade = int(getattr(body, "grade", 0) or 0)
    subject = str(getattr(body, "subject", "") or "").strip()
    raw_paper_textbook = str(getattr(body, "textbook", "") or "").strip()
    try:
        paper_textbook = require_textbook(grade, subject, raw_paper_textbook)
    except TextbookRegistryError as exc:
        _raise_http(exc)

    question_ids = [int(x) for x in (getattr(body, "question_ids", []) or [])]
    if not question_ids:
        return
    questions = db.scalars(
        implementation.select(implementation.Question).where(
            implementation.Question.school_id == user.school_id,
            implementation.Question.id.in_(question_ids),
        )
    ).all()
    if len({int(q.id) for q in questions}) != len(set(question_ids)):
        return  # The mature route will report missing/unauthorized IDs.

    question_textbooks: set[str] = set()
    for question in questions:
        if int(question.grade or 0) != grade or str(question.subject or "").strip() != subject:
            raise HTTPException(
                400,
                "试卷题目必须与试卷年级和科目一致，不能把其他年级或其他学科题目混入同一试卷",
            )
        try:
            q_textbook = require_textbook(
                int(question.grade or 0),
                str(question.subject or ""),
                str(question.textbook or ""),
            )
        except TextbookRegistryError as exc:
            _raise_http(exc)
        question_textbooks.add(q_textbook)

    if len(question_textbooks) > 1:
        raise HTTPException(400, "试卷包含多个教材版本，必须拆分为各自独立试卷")
    only_question_textbook = next(iter(question_textbooks), "")
    if not paper_textbook and only_question_textbook:
        paper_textbook = only_question_textbook
    if paper_textbook and only_question_textbook and paper_textbook != only_question_textbook:
        raise HTTPException(
            400,
            "试卷教材与题目教材不一致；请使用同一科目、同一核定教材版本的题目",
        )
    if paper_textbook != raw_paper_textbook:
        setattr(body, "textbook", paper_textbook)


def install_textbook_registry_guard(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "textbook_registry_guard_installed", False):
        return

    # Avoid spending an AI call on an invalid/obsolete registered textbook line.
    generate_route = _route(implementation, "/ai/questions/generate", "POST")
    original_generate = generate_route.dependant.call

    @wraps(original_generate)
    def guarded_generate(*args: Any, __original=original_generate, **kwargs: Any):
        body = kwargs.get("b") or (args[0] if args else None)
        if body is not None:
            _normalize_body_textbook(body)
        return __original(*args, **kwargs)

    generate_route.dependant.call = guarded_generate
    generate_route.endpoint = guarded_generate

    # Both AI paper assignment paths must stay inside one curriculum line.
    for path in (
        "/ai/questions/assign",
        "/teacher/students/{sid}/reinforcement/assign",
    ):
        route = _route(implementation, path, "POST")
        original = route.dependant.call

        @wraps(original)
        def guarded_batch(*args: Any, __original=original, **kwargs: Any):
            body = kwargs.get("b")
            if body is None:
                # reinforcement route has sid as the first positional argument.
                for value in reversed(args):
                    if hasattr(value, "questions"):
                        body = value
                        break
            if body is not None:
                try:
                    normalize_question_batch(list(getattr(body, "questions", []) or []))
                except TextbookRegistryError as exc:
                    _raise_http(exc)
            return __original(*args, **kwargs)

        route.dependant.call = guarded_batch
        route.endpoint = guarded_batch

    paper_route = _route(implementation, "/teacher/papers", "POST")
    original_paper = paper_route.dependant.call

    @wraps(original_paper)
    def guarded_paper(*args: Any, __original=original_paper, **kwargs: Any):
        body = kwargs.get("b") or (args[0] if args else None)
        user = kwargs.get("u")
        db = kwargs.get("db")
        if body is not None and user is not None and db is not None:
            _validate_paper_body(implementation, body, user, db)
        return __original(*args, **kwargs)

    paper_route.dependant.call = guarded_paper
    paper_route.endpoint = guarded_paper
    app.state.textbook_registry_guard_installed = True


__all__ = [
    "CHINESE_G5_TEXTBOOK",
    "ENGLISH_G5_TEXTBOOK",
    "MATH_G5_TEXTBOOK",
    "MATH_G5_TEXTBOOK_LABEL",
    "TextbookRegistryError",
    "install_textbook_registry_guard",
    "is_registered_scope",
    "normalize_question_batch",
    "normalize_textbook",
    "registered_subjects",
    "registered_textbooks",
    "require_textbook",
]
