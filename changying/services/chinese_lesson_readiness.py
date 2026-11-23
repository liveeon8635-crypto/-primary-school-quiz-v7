"""One server-side preparation gate shared by creation, start and teacher status."""
from sqlalchemy import select
from changying.services.weekend_course_types import course_type_for, register_weekend_course_type_tables
from changying.services.weekend_stages import stages_for


def chinese_lesson_readiness(implementation, db, lesson, teacher_id):
    from changying.web.weekend_plan_views import has_real_plan
    from changying.web.weekend_courseware import (
        items_of, register_courseware_table, stage_pages, practice_courseware_sources,
    )
    course_type = course_type_for(db, implementation, lesson)
    if course_type == "writing":
        from changying.services.writing_lesson import writing_package, writing_readiness
        _, package = writing_package(implementation, db, lesson.id)
        return writing_readiness(package)
    reasons = []
    if course_type not in ("reading", "writing"):
        reasons.append("先选择并保存阅读课或作文课")
    if not has_real_plan(lesson):
        reasons.append("尚无教案")
    materials = register_weekend_course_type_tables(implementation)["materials"]
    pending = len(db.execute(select(materials.c.id).where(
        materials.c.school_id == lesson.school_id, materials.c.lesson_id == lesson.id,
        materials.c.status == "pending")).all())
    if pending:
        reasons.append(f"还有 {pending} 项导入素材待确认")
    table = register_courseware_table(implementation)
    row = db.execute(select(table).where(table.c.school_id == lesson.school_id,
                                        table.c.lesson_id == lesson.id)).first()
    try:
        items = items_of(row, hydrate=False)
    except (TypeError, ValueError, KeyError):
        items = []
    sources = practice_courseware_sources(implementation, db, lesson, teacher_id)
    stages = []
    for spec in stages_for(course_type):
        stage = int(spec["no"])
        pages = [s[0] for s in sources] if stage == 5 else stage_pages(lesson, stage, course_type)
        candidates = [i for i in items if i.get("stage") == stage]
        has_whole_stage_slide = stage == 5 and any(i.get("kind") == "slide" and i.get("page") is None for i in candidates)
        missing = not candidates or (stage == 5 and not sources and not has_whole_stage_slide)
        valid = bool(candidates) and not missing
        if pages and not has_whole_stage_slide and any(not any(i.get("page") == p for i in candidates) for p in range(len(pages))):
            missing = True
            valid = False
        hint = ""
        for item in candidates:
            page = item.get("page")
            text = pages[page] if isinstance(page, int) and 0 <= page < len(pages) else ""
            is_whole_stage_slide = stage == 5 and item.get("kind") == "slide" and page is None
            bad_page = bool(pages) and not is_whole_stage_slide and (not isinstance(page, int) or not 0 <= page < len(pages))
            if item.get("reimportReviewRequired"):
                hint = hint or "重新导入后需重新审核"
                valid = False
            elif item.get("status") != "approved":
                hint = hint or ("草稿已更新，需重新审核" if item.get("approved") else "草稿尚未审核")
                valid = False
            elif not item.get("approved"):
                valid = False
            elif item.get("approved") != item.get("params"):
                hint = hint or "审核内容与当前草稿不一致，需重新审核"
                valid = False
            elif item.get("approvedPageText", "") != text:
                hint = hint or "原文已变化，需重新审核"
                valid = False
            elif bad_page:
                hint = hint or "页号越界，需重新核对"
                valid = False
            if stage == 5 and isinstance(page, int) and 0 <= page < len(sources):
                if item.get("approvedAnswerBinding") != sources[page][1]:
                    hint = hint or "答案绑定已变化，需重新审核"
                    valid = False
        state = "缺少素材" if missing else "已审核" if valid else "待确认"
        stages.append({"no": stage, "name": spec["name"], "status": state})
        if not valid:
            reason = f"第 {stage} 环节{spec['name']}：{state}"
            if state == "待确认" and hint:
                reason += f"（{hint}）"
            reasons.append(reason)
    reviewed = bool(stages) and all(s["status"] == "已审核" for s in stages)
    return {"courseType": course_type, "pendingMaterials": pending,
            "coursewareGenerated": bool(items), "coursewareApproved": reviewed,
            "canStart": not reasons, "startReasons": reasons, "stageReadiness": stages}
