from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("weekend_review_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_review_separates_examples_and_blocks_duplicate_practice(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import json
from sqlalchemy import insert, select
from changying.web.weekend_written import register_written_tables

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        program = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        lesson = legacy.TeachingLesson(
            school_id=school_id, program_id=program.id, subject="数学", lesson_no=17,
            title="平行四边形面积", core_target="掌握平行四边形面积计算",
            duration_min=90, reading_plan="第1题\n平行四边形面积=底×高\n第2题\n平行四边形底长4厘米、高3厘米，面积是多少？",
            examples_json="[]",
        )
        db.add(lesson); db.flush(); lid = lesson.id
        duplicate = legacy.TeachingQuestion(
            school_id=school_id, program_id=program.id, lesson_id=lid, stage="lesson", subject="数学",
            level="C", knowledge="平行四边形面积", stem="平行四边形面积=底×高",
            options_json='["底×高","底+高","底×2","高×2"]', correct_index=0,
            explanation="例题答案", active=False,
        )
        fresh = legacy.TeachingQuestion(
            school_id=school_id, program_id=program.id, lesson_id=lid, stage="lesson", subject="数学",
            level="C", knowledge="平行四边形面积", stem="底长4厘米、高3厘米的平行四边形面积是多少？",
            options_json='["12平方厘米","7厘米","14平方厘米","24平方厘米"]', correct_index=0,
            explanation="新练习答案", active=False,
        )
        db.add_all([duplicate, fresh]); db.flush(); duplicate_id, fresh_id = duplicate.id, fresh.id
        written = register_written_tables(legacy)["questions"]
        values = [
            dict(school_id=school_id, lesson_id=lid, session_id=0, teacher_id=teacher.id,
                 stem="阅读材料\n\n平行四边形面积=底×高", reference="仅老师可见",
                 hints_json=json.dumps({"type": "short_answer", "approved": False}, ensure_ascii=False)),
            dict(school_id=school_id, lesson_id=lid, session_id=0, teacher_id=teacher.id,
                 stem="底长4厘米、高3厘米的平行四边形面积是多少？", reference="12平方厘米",
                 hints_json=json.dumps({"type": "short_answer", "approved": False}, ensure_ascii=False)),
        ]
        ids = db.execute(insert(written).returning(written.c.id), values).scalars().all()
        duplicate_written_id, fresh_written_id = ids
        db.commit()

    base = f"/teacher/weekend/lessons/{lid}"
    qdata = client.get(base + "/questions", headers=th).json()
    assert len(qdata["workedExamples"]) == 2
    assert qdata["items"][0]["duplicateOf"] == "例1"
    assert client.post(base + "/questions", headers=th, json={"approve": [duplicate_id]}).status_code == 409
    assert client.post(base + "/questions", headers=th, json={"approve": [fresh_id]}).status_code == 200

    wdata = client.get(base + "/written/questions", headers=th).json()
    witems = {item["id"]: item for item in wdata["items"]}
    assert witems[duplicate_written_id]["duplicateOf"] == "例1"
    assert client.post(base + "/written/questions", headers=th, json={"approve": [duplicate_written_id]}).status_code == 409
    assert client.post(base + "/written/questions", headers=th, json={"approve": [fresh_written_id]}).status_code == 200

    html = client.get("/v1/weekend-plan").text
    assert "例题讲解（第3环节，只讲不发题）" in html
    assert "随堂练习候选（审核通过后进入第4环节）" in html
print("OK")
''')
