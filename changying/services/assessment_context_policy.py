"""Choose reinforcement context from the student's latest textbook line.

The legacy route hard-coded a math textbook filter when generating targeted
practice. That was correct for the first Grade 5 math implementation but would
silently exclude Chinese and later subjects. This policy preserves publisher
separation while selecting the exact textbook line from the student's latest
eligible assessment.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

from changying.services.assessment_feedback import (
    student_assessment_context as base_student_assessment_context,
)


def install_subject_aware_assessment_context(implementation: ModuleType) -> None:
    if getattr(
        implementation.app.state,
        "subject_aware_assessment_context_installed",
        False,
    ):
        return

    def subject_aware_context(db: Any, **kwargs: Any) -> dict[str, Any]:
        requested_limit = max(1, min(int(kwargs.get("limit") or 6), 12))
        probe_kwargs = dict(kwargs)
        probe_kwargs["textbook_filter"] = None
        probe_kwargs["limit"] = 1
        probe = base_student_assessment_context(db, **probe_kwargs)
        primary = probe.get("primary") or {}
        textbook = str(primary.get("textbook") or "").strip()
        if not textbook:
            return probe

        final_kwargs = dict(kwargs)
        final_kwargs["textbook_filter"] = textbook
        final_kwargs["limit"] = requested_limit
        return base_student_assessment_context(db, **final_kwargs)

    implementation.student_assessment_context = subject_aware_context
    implementation.app.state.subject_aware_assessment_context_installed = True


__all__ = ["install_subject_aware_assessment_context"]
