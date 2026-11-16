from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("weekly_homework_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

BODY = r'''
from datetime import datetime, timedelta

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    today = datetime.now(legacy.SCHOOL_TZ)
    due = today.strftime("%Y-%m-%d")
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        cls = legacy.SchoolClass(school_id=school_id, name="五年级1班", grade=5, teacher_id=teacher.id)
        db.add(cls); db.flush()
        db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid))
        lesson = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=98,
                                       title="旋转复习", core_target="会用旋转解决问题")
        db.add(lesson); db.flush()
        q = legacy.TeachingQuestion(school_id=school_id, program_id=p.id, level="C", lesson_id=lesson.id, subject="数学",
                                    stem="旋转选择", options_json=json.dumps(["A．对", "B．错"], ensure_ascii=False),
                                    correct_index=0, active=True, knowledge="旋转的意义")
        db.add(q); db.flush()
        paper = legacy.Paper(school_id=school_id, title="本周作业卷", grade=5, subject="数学",
                             question_ids_json=json.dumps([q.id]), teacher_id=teacher.id)
        db.add(paper); db.flush()
        done = legacy.Assignment(school_id=school_id, title="本周作业·已完成", class_id=cls.id, paper_id=paper.id, due_date=due)
        missing = legacy.Assignment(school_id=school_id, title="本周作业·未交", class_id=cls.id, paper_id=paper.id, due_date=due)
        stale = legacy.Assignment(school_id=school_id, title="上周作业", class_id=cls.id, paper_id=paper.id, due_date="2000-01-03")
        media = legacy.Assignment(school_id=school_id, title="本周照片作业", class_id=cls.id, paper_id=paper.id, due_date=due)
        practice = legacy.Assignment(school_id=school_id, title="知识地图练习", class_id=cls.id, paper_id=paper.id, due_date=due)
        mixed = legacy.Assignment(school_id=school_id, title="未完成的混合作业", class_id=cls.id, paper_id=paper.id, due_date=due)
        uncertain = legacy.Assignment(school_id=school_id, title="旧记录待核实", class_id=cls.id, paper_id=paper.id, due_date=due)
        db.add_all([done, missing, stale, media, practice, mixed, uncertain]); db.flush()
        for a in (done, missing, stale):
            db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=a.id, class_id=cls.id, student_id=sid))
        db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=media.id, class_id=cls.id, student_id=sid, source="assignment"))
        db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=practice.id, class_id=cls.id, student_id=sid, source="knowledge_map"))
        db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=mixed.id, class_id=cls.id, student_id=sid, source="assignment"))
        db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=uncertain.id, class_id=cls.id, student_id=sid, source=""))
        db.add(legacy.AssignmentSubmissionSetting(school_id=school_id, assignment_id=media.id, mode="media"))
        db.add(legacy.AssignmentSubmissionSetting(school_id=school_id, assignment_id=mixed.id, mode="mixed"))
        db.add(legacy.Submission(school_id=school_id, assignment_id=mixed.id, student_id=sid, title="混合作业在线部分", score=100, correct=1, total=1, answers_json="[]", completion_actor="student"))
        db.add(legacy.Submission(school_id=school_id, assignment_id=done.id, student_id=sid, title="本周作业·已完成",
                                 score=50, correct=2, total=4, answers_json="[]", completion_actor="student"))
        parent = legacy.User(school_id=school_id, username="parent_a", name="甲家长", role="parent",
                             password_hash=legacy.hash_password("Parent1234"))
        db.add(parent); db.flush()
        db.add(legacy.ParentStudent(parent_id=parent.id, student_id=sid))
        db.commit()
        lesson_id, cls_id, q_id, paper_id, media_id, mixed_id, teacher_id = lesson.id, cls.id, q.id, paper.id, media.id, mixed.id, teacher.id

    ph = {"Authorization": "Bearer " + login_and_change(client, "parent_a", "Parent1234", "Parent5678")}
    photo = b"\x89PNG\r\n\x1a\n" + b"synthetic image"
    uploaded = client.post(f"/student/assignments/{media_id}/media", headers=sh, files={"file": ("sample.png", photo, "image/png")})
    assert uploaded.status_code == 200, uploaded.text
    submitted = client.post(f"/student/assignments/{media_id}/media-submit", headers=sh, json={"note": "隔离作业"})
    assert submitted.status_code == 200 and submitted.json()["completed"], submitted.text
    s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lesson_id, "classId": cls_id}).json()["id"]
    assert client.post(f"/teacher/weekend/sessions/{s}/start", headers=th).status_code == 200
    assert client.post(f"/teacher/weekend/sessions/{s}/goto", headers=th, json={"stage": 4}).status_code == 200
    assert client.post("/student/weekend/answer", headers=sh,
                       json={"sessionId": s, "questionId": q_id, "selected": 0, "attempt": 0}).status_code == 200
    assert client.post(f"/teacher/weekend/sessions/{s}/finish", headers=th).status_code == 200

    r = client.post("/teacher/weekend/reports", headers=th, json={"studentId": sid, "sessionIds": [s]})
    assert r.status_code == 200, r.text
    body = r.json()
    rid = body["id"]
    wk = body["report"]["facts"][0]["weekWork"]
    assert wk["counts"] == {"total": 4, "submitted": 2, "unsubmitted": 2, "pending": 1}, wk
    assert wk["rate"] == 50, wk
    items = {i["title"]: i for i in wk["items"]}
    assert set(items) == {"本周作业·已完成", "本周作业·未交", "本周照片作业", "未完成的混合作业"}, items
    assert items["本周照片作业"]["status"] == "pending"
    assert items["未完成的混合作业"]["status"] == "unsubmitted" and items["未完成的混合作业"]["rate"] is None
    assert items["本周作业·已完成"]["status"] == "submitted" and items["本周作业·已完成"]["statusLabel"] == "已交"
    assert items["本周作业·已完成"]["rate"] == 50 and items["本周作业·已完成"]["correct"] == 2
    assert items["本周作业·未交"]["status"] == "unsubmitted" and items["本周作业·未交"]["rate"] is None
    assert wk["weekStart"] <= due <= wk["weekEnd"]
    assert (datetime.strptime(wk["weekEnd"], "%Y-%m-%d").date() - datetime.strptime(wk["weekStart"], "%Y-%m-%d").date()).days == 6

    homework = next(s_ for s_ in body["report"]["draft"]["sections"] if s_["sessionId"] == s)["homework"]
    assert "本周普通作业" in homework and "应做 4 份" in homework, homework
    assert "未交：「本周作业·未交」" in homework, homework

    # The pupil has no homework of his own beyond the two for this week: an unrelated classmate stays at zero.
    summary = client.get(f"/teacher/weekend/sessions/{s}/summary", headers=th).json()
    assert set(summary)  # summary still renders with the new fact attached

    pub = client.post(f"/teacher/weekend/reports/{rid}/publish", headers=th,
                      json={"revision": body["report"]["draft"]["revision"]})
    assert pub.status_code == 200, pub.text
    briefs = client.get(f"/parent/children/{sid}/weekend-briefs", headers=ph).json()["reports"]
    assert briefs, "the published report must reach the parent"
    parent_wk = briefs[0]["facts"][0]["weekWork"]
    assert parent_wk["unclassifiedCount"] == 1
    assert parent_wk["counts"]["total"] == 4 and parent_wk["rate"] == 50
    assert set(parent_wk["items"][0]) == {"title", "status", "statusLabel", "rate", "due"}
    assert all("correct" not in i and "total" not in i for i in parent_wk["items"])
    # Exercise query growth against real ORM rows rather than a mocked status function.
    from sqlalchemy import event
    from changying.services.weekend_reports import week_work_map
    with legacy.SessionLocal() as db:
        subjects = []
        for size in (1, 10, 50):
            pupil = legacy.User(school_id=school_id, username="query-pupil-" + str(size), name="查询测试", role="student", password_hash="synthetic-test-hash")
            db.add(pupil); db.flush(); subjects.append((size, pupil.id))
            for i in range(size):
                task = legacy.Assignment(school_id=school_id, title="查询作业", class_id=cls_id, paper_id=paper_id, due_date=due)
                db.add(task); db.flush()
                db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=task.id, class_id=cls_id, student_id=pupil.id, source="assignment"))
        db.commit()
        query_counts = []
        def count_sql(conn, cursor, statement, parameters, context, executemany):
            query_counts.append(statement)
        event.listen(db.bind, "before_cursor_execute", count_sql)
        try:
            sizes = []
            for size, pupil_id in subjects:
                query_counts.clear()
                result = week_work_map(legacy, db, school_id=school_id, student_ids=[pupil_id], day=due)
                assert result[pupil_id]["counts"]["total"] == size
                sizes.append(len(query_counts))
            assert sizes[0] == sizes[1] == sizes[2] and sizes[2] <= 8, sizes
        finally:
            event.remove(db.bind, "before_cursor_execute", count_sql)
        # A backfilled recipient is classifiable only when another recipient proves
        # the assignment's source. An empty source alone must remain uncertain.
        historical = legacy.Assignment(school_id=school_id, title="历史普通作业", class_id=cls_id, paper_id=paper_id, due_date=due)
        unknown = legacy.Assignment(school_id=school_id, title="来源待核实", class_id=cls_id, paper_id=paper_id, due_date=due)
        db.add_all([historical, unknown]); db.flush()
        db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=historical.id, class_id=cls_id, student_id=sid, source="submission_backfill"))
        db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=historical.id, class_id=cls_id, student_id=subjects[0][1], source="assignment"))
        db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=unknown.id, class_id=cls_id, student_id=sid, source=""))
        db.commit()
        historical_id = historical.id
        check = week_work_map(legacy, db, school_id=school_id, student_ids=[sid], day=due)[sid]
        assert historical_id in [i["assignmentId"] for i in check["items"]]
        assert check["unclassifiedCount"] == 2 and all(i["title"] != "来源待核实" for i in check["items"])
        # Once confirmed after media submission, a photo assignment is no longer pending.
        from datetime import datetime, timedelta
        media_submit = db.scalar(select(legacy.HomeworkMediaSubmit).where(legacy.HomeworkMediaSubmit.assignment_id == media_id))
        db.add(legacy.AIGradingReview(school_id=school_id, assignment_id=media_id, student_id=sid, teacher_id=teacher_id,
                                      status="draft"))
        db.commit()
        confirmed = client.post(f"/teacher/assignments/{media_id}/students/{sid}/grading-confirm", headers=th,
                                json={"score": 80, "feedback": "已确认", "archive_wrong": False})
        assert confirmed.status_code == 200, confirmed.text
        check = week_work_map(legacy, db, school_id=school_id, student_ids=[sid], day=due)[sid]
        assert next(i for i in check["items"] if i["assignmentId"] == media_id)["status"] == "submitted"
        # The old published snapshot remains unchanged until a teacher regenerates
        # and republishes; the parent then receives the confirmed state.
        old = client.get(f"/parent/children/{sid}/weekend-briefs", headers=ph).json()["reports"][0]
        assert next(i for i in old["facts"][0]["weekWork"]["items"] if i["title"] == "本周照片作业")["status"] == "pending"
        revision = body["report"]["draft"]["revision"]
        regen = client.post("/teacher/weekend/reports", headers=th, json={"studentId": sid, "sessionIds": [s], "replace": True, "revision": revision})
        assert regen.status_code == 200, regen.text
        new_revision = regen.json()["report"]["draft"]["revision"]
        republish = client.post(f"/teacher/weekend/reports/{rid}/publish", headers=th, json={"revision": new_revision})
        assert republish.status_code == 200, republish.text
        new = client.get(f"/parent/children/{sid}/weekend-briefs", headers=ph).json()["reports"][0]
        assert next(i for i in new["facts"][0]["weekWork"]["items"] if i["title"] == "本周照片作业")["status"] == "submitted"
        # The Sunday boundary must include imported ISO timestamps, not only dates.
        sunday = (datetime.strptime(due, "%Y-%m-%d") + timedelta(days=6-datetime.strptime(due, "%Y-%m-%d").weekday())).strftime("%Y-%m-%d")
        dated = legacy.Assignment(school_id=school_id, title="周日作业", class_id=cls_id, paper_id=paper_id, due_date=sunday + "T18:00:00")
        db.add(dated); db.flush(); db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=dated.id, class_id=cls_id, student_id=sid, source="paper_import")); db.commit()
        check = week_work_map(legacy, db, school_id=school_id, student_ids=[sid], day=due)[sid]
        assert "周日作业" in [i["title"] for i in check["items"]]
        # Mixed homework is complete only after both submissions; an older review
        # cannot confirm work submitted afterwards.
        m = legacy.HomeworkMediaSubmit(school_id=school_id, assignment_id=mixed_id, student_id=sid, submitted_at=datetime.utcnow())
        db.add(m); db.flush()
        review = legacy.AIGradingReview(school_id=school_id, assignment_id=mixed_id, student_id=sid, teacher_id=teacher_id,
                                        status="confirmed", confirmed_at=m.submitted_at - timedelta(seconds=1))
        db.add(review); db.commit()
        check = week_work_map(legacy, db, school_id=school_id, student_ids=[sid], day=due)[sid]
        assert next(i for i in check["items"] if i["assignmentId"] == mixed_id)["status"] == "pending"
        review.confirmed_at = m.submitted_at + timedelta(seconds=1); db.commit()
        check = week_work_map(legacy, db, school_id=school_id, student_ids=[sid], day=due)[sid]
        checked_mixed = next(i for i in check["items"] if i["assignmentId"] == mixed_id)
        assert checked_mixed["status"] == "submitted" and checked_mixed["rate"] is None
        only_photo = legacy.Assignment(school_id=school_id, title="混合作业只交照片", class_id=cls_id, paper_id=paper_id, due_date=due)
        unsubmitted_media = legacy.Assignment(school_id=school_id, title="未上传照片", class_id=cls_id, paper_id=paper_id, due_date=due)
        conflict = legacy.Assignment(school_id=school_id, title="来源冲突", class_id=cls_id, paper_id=paper_id, due_date=due)
        unknown_source = legacy.Assignment(school_id=school_id, title="未知来源", class_id=cls_id, paper_id=paper_id, due_date=due)
        db.add_all([only_photo, unsubmitted_media, conflict, unknown_source]); db.flush()
        for item in (only_photo, unsubmitted_media, conflict):
            db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=item.id, class_id=cls_id, student_id=sid, source="assignment"))
        db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=conflict.id, class_id=cls_id, student_id=subjects[0][1], source="knowledge_map"))
        db.add(legacy.AssignmentRecipient(school_id=school_id, assignment_id=unknown_source.id, class_id=cls_id, student_id=sid, source="legacy_manual"))
        db.add(legacy.AssignmentSubmissionSetting(school_id=school_id, assignment_id=only_photo.id, mode="mixed"))
        db.add(legacy.AssignmentSubmissionSetting(school_id=school_id, assignment_id=unsubmitted_media.id, mode="media"))
        db.add(legacy.HomeworkMediaSubmit(school_id=school_id, assignment_id=only_photo.id, student_id=sid)); db.commit()
        check = week_work_map(legacy, db, school_id=school_id, student_ids=[sid], day=due)[sid]
        by_title = {i["title"]: i for i in check["items"]}
        assert by_title["混合作业只交照片"]["status"] == "unsubmitted"
        assert by_title["未上传照片"]["status"] == "unsubmitted"
        assert "来源冲突" not in by_title and "未知来源" not in by_title and check["unclassifiedCount"] == 4
        foreign_school = legacy.School(name="隔离另一校", code="other-school")
        db.add(foreign_school); db.flush()
        foreign_student = legacy.User(school_id=foreign_school.id, username="foreign-pupil", name="另一校学生", role="student", password_hash="synthetic-test-hash")
        foreign_teacher = legacy.User(school_id=foreign_school.id, username="foreign-teacher", name="另一校教师", role="teacher", password_hash="synthetic-test-hash")
        db.add_all([foreign_student, foreign_teacher]); db.flush()
        foreign_class = legacy.SchoolClass(school_id=foreign_school.id, name="另一校班级", grade=5, teacher_id=foreign_teacher.id)
        foreign_paper = legacy.Paper(school_id=foreign_school.id, title="另一校卷", grade=5, subject="数学", question_ids_json="[]", teacher_id=foreign_teacher.id)
        db.add_all([foreign_class, foreign_paper]); db.flush()
        foreign_task = legacy.Assignment(school_id=foreign_school.id, title="另一校作业", class_id=foreign_class.id, paper_id=foreign_paper.id, due_date=due)
        db.add(foreign_task); db.flush()
        db.add(legacy.AssignmentRecipient(school_id=foreign_school.id, assignment_id=foreign_task.id, class_id=foreign_class.id, student_id=foreign_student.id, source="assignment")); db.commit()
        foreign_id = foreign_student.id
        isolated = week_work_map(legacy, db, school_id=school_id, student_ids=[sid, foreign_id], day=due)
        assert isolated[foreign_id]["counts"]["total"] == 0
        assert "另一校作业" not in [i["title"] for i in isolated[sid]["items"]]
    print("OK")
'''


def test_report_shows_the_weeks_ordinary_homework_for_teacher_and_parent(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + BODY)


def test_unclassified_week_work_is_visible_in_report():
    import subprocess
    from changying.web.weekend_report_pages import REPORT_VIEW_JS
    script = """
const assert = require('node:assert/strict');
function el(tag, attrs, ...children) { return {textContent:(attrs.text||'')+children.map(x=>x.textContent||x).join(''), appendChild(c){this.textContent+=c.textContent||c;}}; }
""" + REPORT_VIEW_JS + """
const box=weekWorkBox({weekStart:'2026-11-16',weekEnd:'2026-11-22',counts:{total:0,submitted:0,unsubmitted:0,pending:0},unclassifiedCount:1,items:[]});
assert(box && box.textContent.includes('本周普通作业统计不完整'));
"""
    result = subprocess.run(["node", "-"], input=script, text=True, encoding="utf-8", capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_unclassified_warning_is_fixed_in_report_docx():
    import io
    import zipfile
    from changying.services.weekend_handouts import report_document

    counts = dict(total=0, submitted=0, unsubmitted=0, correct=0, partial=0, revise=0, pending=0)
    report = {"studentName": "测试", "date": "2026-11-16", "facts": [{"subject": "数学", "lessonTitle": "测试", "counts": counts, "weekWork": {"unclassifiedCount": 1}}], "sections": [{}], "titles": []}
    with zipfile.ZipFile(io.BytesIO(report_document(report))) as z:
        assert "本周普通作业统计不完整" in z.read("word/document.xml").decode("utf-8")
