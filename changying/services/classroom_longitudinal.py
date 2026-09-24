"""Read-only longitudinal classroom participation snapshot."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from changying.utils.datetime_tools import school_local_iso


def _percent(correct: int, total: int) -> int | None:
    if total <= 0:
        return None
    return (int(correct) * 100 + int(total) // 2) // int(total)


def _average(values: list[int]) -> float | None:
    clean = [int(value) for value in values if value is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 1)


def empty_classroom_snapshot() -> dict[str, Any]:
    return {
        "summary": {
            "quickCheckCount": 0,
            "quickCheckCorrectCount": 0,
            "quickCheckAccuracy": None,
            "presentationCount": 0,
            "reviewedPresentationCount": 0,
            "accuracyRatingAverage": None,
            "clarityRatingAverage": None,
            "interactionRatingAverage": None,
            "interactionPointsAwarded": 0,
            "dimensionsSeparate": True,
            "combinedAbilityScore": None,
        },
        "quickChecks": [],
        "presentations": [],
        "timelineEvents": [],
    }


def classroom_student_snapshot(
    implementation: Any,
    db: Any,
    *,
    student_id: int,
    school_id: int,
    limit: int = 40,
) -> dict[str, Any]:
    """Return factual classroom history without writing evidence or mastery."""
    metadata = implementation.Base.metadata
    sessions = metadata.tables.get("classroom_sessions")
    segments = metadata.tables.get("classroom_segments")
    turns = metadata.tables.get("classroom_presenter_turns")
    checks = metadata.tables.get("classroom_quick_checks")
    responses = metadata.tables.get("classroom_quick_check_responses")
    reviews = metadata.tables.get("classroom_presentation_reviews")
    if any(table is None for table in (sessions, segments, turns, checks, responses, reviews)):
        return empty_classroom_snapshot()

    bounded_limit = max(1, min(int(limit or 40), 120))

    quick_rows = db.execute(
        select(
            responses.c.id.label("response_id"),
            responses.c.check_id,
            responses.c.session_id,
            responses.c.segment_id,
            responses.c.is_correct,
            responses.c.submitted_at,
            checks.c.question_type,
            checks.c.question_text,
            checks.c.status.label("check_status"),
            checks.c.decision,
            segments.c.knowledge_key,
            sessions.c.subject,
            sessions.c.title.label("session_title"),
        )
        .select_from(
            responses.join(
                checks,
                (checks.c.id == responses.c.check_id)
                & (checks.c.school_id == responses.c.school_id),
            )
            .join(
                segments,
                (segments.c.id == responses.c.segment_id)
                & (segments.c.school_id == responses.c.school_id),
            )
            .join(
                sessions,
                (sessions.c.id == responses.c.session_id)
                & (sessions.c.school_id == responses.c.school_id),
            )
        )
        .where(
            responses.c.school_id == school_id,
            responses.c.student_id == student_id,
        )
        .order_by(responses.c.submitted_at.desc(), responses.c.id.desc())
        .limit(bounded_limit)
    ).mappings().all()

    point_table = getattr(implementation.PointLedger, "__table__", None)
    presentation_from = (
        turns.join(
            segments,
            (segments.c.id == turns.c.segment_id)
            & (segments.c.school_id == turns.c.school_id),
        )
        .join(
            sessions,
            (sessions.c.id == turns.c.session_id)
            & (sessions.c.school_id == turns.c.school_id),
        )
        .outerjoin(
            reviews,
            (reviews.c.turn_id == turns.c.id)
            & (reviews.c.school_id == turns.c.school_id),
        )
    )
    presentation_columns = [
        turns.c.id.label("turn_id"),
        turns.c.session_id,
        turns.c.segment_id,
        turns.c.presenter_type,
        turns.c.status.label("turn_status"),
        turns.c.completed_at,
        segments.c.knowledge_key,
        sessions.c.subject,
        sessions.c.title.label("session_title"),
        reviews.c.id.label("review_id"),
        reviews.c.accuracy_rating,
        reviews.c.clarity_rating,
        reviews.c.interaction_rating,
        reviews.c.teacher_note,
        reviews.c.granted_points,
        reviews.c.point_reason,
        reviews.c.points_granted_at,
        reviews.c.point_ledger_id,
    ]
    if point_table is not None:
        presentation_from = presentation_from.outerjoin(
            point_table,
            (point_table.c.id == reviews.c.point_ledger_id)
            & (point_table.c.school_id == turns.c.school_id),
        )
        presentation_columns.append(point_table.c.reversed.label("point_reversed"))
    presentation_select = select(*presentation_columns).select_from(presentation_from)

    presentation_rows = db.execute(
        presentation_select.where(
            turns.c.school_id == school_id,
            turns.c.student_id == student_id,
            turns.c.status == "completed",
        )
        .order_by(turns.c.completed_at.desc(), turns.c.id.desc())
        .limit(bounded_limit)
    ).mappings().all()

    quick_checks = []
    timeline_events = []
    for row in quick_rows:
        item = {
            "responseID": int(row["response_id"]),
            "checkID": int(row["check_id"]),
            "sessionID": int(row["session_id"]),
            "segmentID": int(row["segment_id"]),
            "subject": str(row["subject"] or ""),
            "sessionTitle": str(row["session_title"] or ""),
            "knowledgeKey": str(row["knowledge_key"] or ""),
            "questionType": str(row["question_type"] or ""),
            "questionText": str(row["question_text"] or ""),
            "checkStatus": str(row["check_status"] or ""),
            "decision": str(row["decision"] or ""),
            "isCorrect": bool(row["is_correct"]),
            "submittedAt": school_local_iso(row["submitted_at"]),
        }
        quick_checks.append(item)
        detail = " · ".join(
            value
            for value in (
                item["subject"],
                item["sessionTitle"],
                "答对" if item["isCorrect"] else "本题未答对",
            )
            if value
        )
        timeline_events.append(
            {
                "type": "classroom_quick_check",
                "icon": "🧩",
                "title": f"课堂即时检测：{item['knowledgeKey'] or '课堂知识点'}",
                "detail": detail,
                "time": item["submittedAt"],
            }
        )

    presentations = []
    for row in presentation_rows:
        reversed_point = bool(row.get("point_reversed")) if "point_reversed" in row else False
        granted_points = int(row["granted_points"] or 0) if row["review_id"] else 0
        item = {
            "turnID": int(row["turn_id"]),
            "sessionID": int(row["session_id"]),
            "segmentID": int(row["segment_id"]),
            "subject": str(row["subject"] or ""),
            "sessionTitle": str(row["session_title"] or ""),
            "knowledgeKey": str(row["knowledge_key"] or ""),
            "presenterType": str(row["presenter_type"] or ""),
            "completedAt": school_local_iso(row["completed_at"]),
            "review": None,
            "interactionPoint": None,
        }
        if row["review_id"] is not None:
            item["review"] = {
                "id": int(row["review_id"]),
                "accuracyRating": row["accuracy_rating"],
                "clarityRating": row["clarity_rating"],
                "interactionRating": row["interaction_rating"],
                "teacherNote": str(row["teacher_note"] or ""),
            }
            if row["point_ledger_id"] is not None:
                item["interactionPoint"] = {
                    "ledgerID": int(row["point_ledger_id"]),
                    "points": granted_points,
                    "reason": str(row["point_reason"] or ""),
                    "grantedAt": school_local_iso(row["points_granted_at"]),
                    "reversed": reversed_point,
                }
        presentations.append(item)

        review = item["review"] or {}
        ratings = []
        if review.get("accuracyRating") is not None:
            ratings.append(f"内容 {review['accuracyRating']}/5")
        if review.get("clarityRating") is not None:
            ratings.append(f"清晰 {review['clarityRating']}/5")
        if review.get("interactionRating") is not None:
            ratings.append(f"互动 {review['interactionRating']}/5")
        point = item["interactionPoint"]
        if point:
            ratings.append(
                "互动积分记录已撤销"
                if point["reversed"]
                else f"教师互动积分 +{point['points']}"
            )
        detail = " · ".join(
            value
            for value in (
                item["subject"],
                item["sessionTitle"],
                *ratings,
            )
            if value
        )
        timeline_events.append(
            {
                "type": "classroom_presentation",
                "icon": "🎤",
                "title": f"学生讲解：{item['knowledgeKey'] or '课堂知识点'}",
                "detail": detail or "讲解已完成",
                "time": item["completedAt"],
            }
        )

    quick_count = len(quick_checks)
    quick_correct = sum(1 for item in quick_checks if item["isCorrect"])
    reviewed = [item for item in presentations if item["review"] is not None]
    active_points = [
        item["interactionPoint"]["points"]
        for item in presentations
        if item["interactionPoint"] is not None and not item["interactionPoint"]["reversed"]
    ]
    summary = {
        "quickCheckCount": quick_count,
        "quickCheckCorrectCount": quick_correct,
        "quickCheckAccuracy": _percent(quick_correct, quick_count),
        "presentationCount": len(presentations),
        "reviewedPresentationCount": len(reviewed),
        "accuracyRatingAverage": _average(
            [item["review"]["accuracyRating"] for item in reviewed if item["review"]["accuracyRating"] is not None]
        ),
        "clarityRatingAverage": _average(
            [item["review"]["clarityRating"] for item in reviewed if item["review"]["clarityRating"] is not None]
        ),
        "interactionRatingAverage": _average(
            [item["review"]["interactionRating"] for item in reviewed if item["review"]["interactionRating"] is not None]
        ),
        "interactionPointsAwarded": sum(active_points),
        "dimensionsSeparate": True,
        "combinedAbilityScore": None,
    }
    timeline_events.sort(key=lambda item: str(item.get("time") or ""), reverse=True)
    return {
        "summary": summary,
        "quickChecks": quick_checks,
        "presentations": presentations,
        "timelineEvents": timeline_events[:bounded_limit],
    }


__all__ = ["classroom_student_snapshot", "empty_classroom_snapshot"]
