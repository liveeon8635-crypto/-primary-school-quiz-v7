"""Pure helpers for teacher-reviewed classroom presentation feedback."""

from __future__ import annotations

from typing import Any


RATING_FIELDS = ("accuracy_rating", "clarity_rating", "interaction_rating")


def normalize_rating(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        rating = int(value)
    except Exception as exc:
        raise ValueError("讲解评价须为1-5分") from exc
    if rating not in range(1, 6):
        raise ValueError("讲解评价须为1-5分")
    return rating


def normalize_review_ratings(
    *,
    accuracy_rating: Any,
    clarity_rating: Any,
    interaction_rating: Any,
) -> dict[str, int | None]:
    return {
        "accuracy_rating": normalize_rating(accuracy_rating),
        "clarity_rating": normalize_rating(clarity_rating),
        "interaction_rating": normalize_rating(interaction_rating),
    }


def presentation_point_note(
    *,
    knowledge_key: str,
    accuracy_rating: int | None,
    clarity_rating: int | None,
    interaction_rating: int | None,
    quick_check_accuracy: int | None,
    presenter_check_correct: bool | None,
    teacher_note: str,
) -> str:
    parts = [f"知识点：{str(knowledge_key or '').strip() or '课堂讲解'}"]
    ratings = []
    if accuracy_rating is not None:
        ratings.append(f"准确性{accuracy_rating}/5")
    if clarity_rating is not None:
        ratings.append(f"表达清晰{clarity_rating}/5")
    if interaction_rating is not None:
        ratings.append(f"互动{interaction_rating}/5")
    if ratings:
        parts.append("教师评价：" + "、".join(ratings))
    if quick_check_accuracy is not None:
        parts.append(f"后续随堂检测班级正确率{quick_check_accuracy}%")
    if presenter_check_correct is not None:
        parts.append("讲解学生后续检测：" + ("正确" if presenter_check_correct else "未答对"))
    note = str(teacher_note or "").strip()
    if note:
        parts.append("教师备注：" + note[:600])
    return "；".join(parts)[:2000]


__all__ = [
    "RATING_FIELDS",
    "normalize_rating",
    "normalize_review_ratings",
    "presentation_point_note",
]
