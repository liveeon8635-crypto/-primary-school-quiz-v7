"""Teacher-facing class evidence coverage for continuous student records.

This module answers one descriptive question: which evidence dimensions have
already been recorded for each currently visible student? Missing dimensions
mean "the system has no record", never "the student lacks the ability".
"""

from __future__ import annotations

from collections import defaultdict
from types import ModuleType
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from changying.domain.learning_evidence import EVIDENCE_TYPES


DIMENSION_NAMES = {
    "performance": "学习表现",
    "independent": "独立完成",
    "retention": "跨时保持",
    "transfer": "迁移应用",
}


def _visible_classes(implementation: ModuleType, db: Any, user, class_id: int | None):
    implementation.need(user, "teacher", "admin")
    query = implementation.select(implementation.SchoolClass).where(
        implementation.SchoolClass.school_id == user.school_id
    )
    if user.role == "teacher":
        query = query.where(implementation.SchoolClass.teacher_id == user.id)
    classes = db.scalars(query.order_by(implementation.SchoolClass.grade, implementation.SchoolClass.id)).all()

    if class_id is not None:
        selected = [row for row in classes if int(row.id) == int(class_id)]
        if not selected:
            raise HTTPException(403, "无权查看该班级的证据覆盖")
        classes = selected
    return classes


def teacher_evidence_coverage(
    implementation: ModuleType,
    db: Any,
    user,
    *,
    class_id: int | None = None,
) -> dict[str, Any]:
    classes = _visible_classes(implementation, db, user, class_id)
    class_ids = {int(row.id) for row in classes}
    class_by_id = {int(row.id): row for row in classes}

    if not class_ids:
        return {
            "classes": [],
            "students": [],
            "summary": {
                "studentCount": 0,
                "allDimensionsRecordedCount": 0,
                "noEvidenceRecordedCount": 0,
            },
            "dimensionNames": DIMENSION_NAMES,
            "boundary": "尚无可见班级。证据覆盖仅描述系统记录情况，不代表学生能力水平。",
            "automaticDiagnosis": False,
            "automaticRanking": False,
        }

    links = db.scalars(
        implementation.select(implementation.ClassStudent).where(
            implementation.ClassStudent.class_id.in_(class_ids)
        )
    ).all()
    student_ids = {int(row.student_id) for row in links}

    if not student_ids:
        return {
            "classes": [
                {"id": int(row.id), "name": row.name, "grade": row.grade}
                for row in classes
            ],
            "students": [],
            "summary": {
                "studentCount": 0,
                "allDimensionsRecordedCount": 0,
                "noEvidenceRecordedCount": 0,
            },
            "dimensionNames": DIMENSION_NAMES,
            "boundary": "班级暂无当前学生。证据覆盖仅描述系统记录情况，不代表学生能力水平。",
            "automaticDiagnosis": False,
            "automaticRanking": False,
        }

    students = db.scalars(
        implementation.select(implementation.User).where(
            implementation.User.school_id == user.school_id,
            implementation.User.role == "student",
            implementation.User.id.in_(student_ids),
            implementation.User.active == True,
        )
    ).all()
    student_by_id = {int(row.id): row for row in students}
    student_ids = set(student_by_id)

    classes_for_student: dict[int, list[int]] = defaultdict(list)
    for link in links:
        sid = int(link.student_id)
        cid = int(link.class_id)
        if sid in student_ids and cid in class_by_id:
            classes_for_student[sid].append(cid)

    submissions = db.scalars(
        implementation.select(implementation.Submission).where(
            implementation.Submission.school_id == user.school_id,
            implementation.Submission.student_id.in_(student_ids),
        )
    ).all() if student_ids else []

    events = db.scalars(
        implementation.select(implementation.LearningEvidenceEvent).where(
            implementation.LearningEvidenceEvent.school_id == user.school_id,
            implementation.LearningEvidenceEvent.student_id.in_(student_ids),
        )
    ).all() if student_ids else []

    retracted = {
        int(row.target_event_id)
        for row in events
        if row.event_kind == "retract" and row.target_event_id is not None
    }

    dimensions: dict[int, set[str]] = {sid: set() for sid in student_ids}
    counts: dict[int, int] = {sid: 0 for sid in student_ids}
    latest: dict[int, Any] = {sid: None for sid in student_ids}

    for row in submissions:
        sid = int(row.student_id)
        if sid not in dimensions:
            continue
        dimensions[sid].add("performance")
        counts[sid] += 1
        if latest[sid] is None or row.submitted_at > latest[sid]:
            latest[sid] = row.submitted_at

    for row in events:
        if (
            row.event_kind != "record"
            or int(row.id) in retracted
            or int(row.student_id) not in dimensions
            or row.evidence_type not in EVIDENCE_TYPES
        ):
            continue
        sid = int(row.student_id)
        dimensions[sid].add(row.evidence_type)
        counts[sid] += 1
        if latest[sid] is None or row.occurred_at > latest[sid]:
            latest[sid] = row.occurred_at

    output = []
    for sid, student in student_by_id.items():
        dims = sorted(dimensions[sid])
        missing = sorted(set(EVIDENCE_TYPES) - set(dims))
        cids = sorted(set(classes_for_student.get(sid, [])))
        output.append(
            {
                "studentID": sid,
                "studentName": student.name,
                "grade": student.grade,
                "classIDs": cids,
                "classNames": [class_by_id[cid].name for cid in cids if cid in class_by_id],
                "availableDimensions": dims,
                "missingDimensions": missing,
                "sourceEventCount": counts[sid],
                "latestEvidenceAt": (
                    implementation.school_local_iso(latest[sid])
                    if latest[sid] is not None
                    else None
                ),
                "allDimensionsRecorded": not missing,
                "automaticDiagnosis": False,
            }
        )

    output.sort(key=lambda row: (row["studentName"] or "", row["studentID"]))
    return {
        "classes": [
            {"id": int(row.id), "name": row.name, "grade": row.grade}
            for row in classes
        ],
        "students": output,
        "summary": {
            "studentCount": len(output),
            "allDimensionsRecordedCount": sum(1 for row in output if row["allDimensionsRecorded"]),
            "noEvidenceRecordedCount": sum(1 for row in output if not row["availableDimensions"]),
        },
        "dimensionNames": DIMENSION_NAMES,
        "boundary": (
            "这里统计的是系统已经记录到哪些证据维度。"
            "“尚无记录”不等于学生不会、能力不足或需要被分层；"
            "教师仍需结合真实课堂与教材情境决定是否继续观察或记录。"
        ),
        "automaticDiagnosis": False,
        "automaticRanking": False,
    }


def install_v22_evidence_coverage_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v22_evidence_coverage_routes_installed", False):
        return

    router = APIRouter()

    @router.get("/v2/teacher/evidence-coverage", include_in_schema=False)
    def evidence_coverage(
        class_id: int | None = None,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        return teacher_evidence_coverage(
            implementation,
            db,
            user,
            class_id=class_id,
        )

    app.include_router(router)
    app.state.v22_evidence_coverage_routes_installed = True


__all__ = [
    "DIMENSION_NAMES",
    "install_v22_evidence_coverage_routes",
    "teacher_evidence_coverage",
]
