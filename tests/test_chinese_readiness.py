"""Exercise the launch gate through the application routes, never a forged row."""
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("readiness_helpers", Path(__file__).with_name("test_homework_solve.py"))
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def prepare_reviewed_lesson(client, headers, implementation, lid):
    from sqlalchemy import select
    from changying.web.weekend_courseware import practice_courseware_sources
    with implementation.SessionLocal() as db:
        lesson = db.get(implementation.TeachingLesson, lid)
        if not lesson.core_target:
            lesson.core_target = "构造测试：理解文章"
        teacher = db.scalar(select(implementation.User).where(implementation.User.username == "teacher1"))
        sources = practice_courseware_sources(implementation, db, lesson, teacher.id)
        if not sources:
            db.add(implementation.TeachingQuestion(school_id=lesson.school_id, program_id=lesson.program_id,
                lesson_id=lid, subject="语文", stage="lesson", level="B", stem="构造测试任务",
                options_json='["甲","乙"]', correct_index=0, active=True))
        db.commit()
    base = f"/teacher/weekend/lessons/{lid}/courseware"
    data = client.get(base, headers=headers).json()
    for stage in range(1, 7):
        pages = data["pages"].get(str(stage), [])
        for page in range(len(pages)) if pages else [None]:
            existing = next((i for i in data["items"] if i["stage"] == stage and i.get("page") == page), None)
            if existing and existing.get("status") == "approved":
                continue
            params = {"title": "构造测试课件", "slides": [{"heading": "构造测试", "body": ["教师核对过的公开正文"]}]}
            saved = client.put(base, headers=headers, json={"stageNo": stage, "page": page,
                "kind": "slide", "params": params, "writtenTask": False})
            assert saved.status_code == 200, saved.text
            approved = client.post(base + "/approve", headers=headers, json={"stageNo": stage, "page": page})
            assert approved.status_code == 200, approved.text


def test_launch_requires_all_stages_and_rechecks_start(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
__import__('sys').path.insert(0, 'tests')
from test_chinese_readiness import prepare_reviewed_lesson
with TestClient(app) as client:
    th, sh, student, school = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school))
        lesson = legacy.TeachingLesson(school_id=school, program_id=p.id, subject="语文",
            lesson_no=18, title="构造阅读", core_target="阅读", reading_plan="构造完整正文")
        db.add(lesson); db.commit(); lid = lesson.id
    assert client.put('/teacher/weekend/schedule/语文/18/course-type', headers=th,
        json={"courseType":"reading","expectedRevision":0}).status_code == 200
    base = f"/teacher/weekend/lessons/{lid}/courseware"
    for request in ({"lessonId":lid}, {"lessonId":lid,"requireReady":False}):
        assert client.post('/teacher/weekend/sessions',headers=th,json=request).status_code == 409
    assert client.post(base+'/generate-all',headers=th,json={}).status_code == 200
    assert client.post(base+'/approve',headers=th,json={"stageNo":2,"page":0}).status_code == 200
    assert client.post('/teacher/weekend/sessions',headers=th,json={"lessonId":lid}).status_code == 409
    prepare_reviewed_lesson(client, th, legacy, lid)
    st = next(x for x in client.get('/teacher/weekend/schedule?subject=语文',headers=th).json()["items"] if x["lessonId"] == lid)
    assert st["coursewareGenerated"] and st["coursewareApproved"] and st["canStart"], st
    created = client.post('/teacher/weekend/sessions',headers=th,json={"lessonId":lid})
    assert created.status_code == 200, created.text
    sid = created.json()["id"]
    saved = client.put(base,headers=th,json={"stageNo":1,"kind":"slide","writtenTask":False,
        "params":{"title":"修改后的草稿","slides":[{"heading":"待审","body":["尚未审核"]}]}})
    assert saved.status_code == 200, saved.text
    assert client.post(f'/teacher/weekend/sessions/{sid}/start',headers=th).status_code == 409
    assert client.post('/teacher/weekend/sessions',headers=th,json={"lessonId":lid,"requireReady":False}).status_code == 409
    assert client.post(base+'/approve',headers=th,json={"stageNo":1}).status_code == 200
    assert client.post(f'/teacher/weekend/sessions/{sid}/start',headers=th).status_code == 200
    print("OK")
''')
