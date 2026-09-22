from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from changying.web.v1 import v1_html
from changying.web.v1_classroom_execution import patch_v1_classroom_execution_html
from changying.web.v1_classroom_handout_release import (
    V1_CLASSROOM_HANDOUT_RELEASE_MARKER,
    patch_v1_classroom_handout_release_html,
)
from changying.web.v1_classroom_presentation_review import (
    patch_v1_classroom_presentation_review_html,
)
from changying.web.v1_classroom_quick_check import patch_v1_classroom_quick_check_html
from changying.web.v1_classroom_review import patch_v1_classroom_review_html


ROOT = Path(__file__).resolve().parents[1]


def final_classroom_html() -> str:
    html = patch_v1_classroom_review_html(v1_html())
    html = patch_v1_classroom_execution_html(html)
    html = patch_v1_classroom_quick_check_html(html)
    html = patch_v1_classroom_presentation_review_html(html)
    return patch_v1_classroom_handout_release_html(html)


def test_v1_handout_release_requires_teacher_confirmation_and_exposes_student_entry():
    html = final_classroom_html()
    assert V1_CLASSROOM_HANDOUT_RELEASE_MARKER in html
    assert "课堂讲义" in html
    assert "/v1/classroom-handouts" in html
    assert "/student/classroom-handouts" in html
    assert "/class-review/handout-publish" in html
    assert "/class-review/handout-revoke" in html
    assert "确认发布" in html
    assert "发布会把当前草稿复制为冻结版本" in html
    assert "撤回只取消学生可见性，不删除历史快照" in html
    assert "confirm('确认将当前教师草稿发布给本作业接收学生" in html
    assert "confirm('确认撤回当前已发布讲义" in html
    assert "后续修改草稿不会改变本版本内容" in html
    assert "查看版本" in html
    assert "历史版本只读预览" in html
    assert "版本差异" in html
    assert "/class-review/handout-releases/" in html
    assert "sort((a,b)=>Number(a.version)-Number(b.version))" in html
    assert "targetIndex>0?ordered[targetIndex-1]" in html
    assert "来源草稿更新时间" in html
    assert "被新版本替代" in html
    assert "本堂课完整课堂记录" in html
    assert "按课堂事实自动汇总的只读记录" in html
    assert "查看互动课堂" in html
    assert "查看当前讲义版本" in html
    assert "paperInfo.textbook" in html
    assert "sessionInfo.completedAt" in html
    assert "课堂练习" in html
    assert "知识点讲解" in html
    assert "补讲决策" in html
    assert "教师加分" in html
    assert "这里只汇总既有事实，不自动改变学生长期掌握状态" in html
    assert "window.__cyClassroomClosureSummary=summary" in html


def test_runtime_handout_release_version_snapshot_and_revoke(tmp_path):
    db_path = tmp_path / "handout-release.sqlite3"
    script = r"""
from datetime import datetime
import json

from fastapi.testclient import TestClient
import app_v924 as legacy
from app import app


def headers_for(db, username):
    user = db.scalar(legacy.select(legacy.User).where(legacy.User.username == username))
    sec = legacy.security_for(db, user)
    sec.must_change_password = False
    db.commit()
    return {"Authorization": "Bearer " + legacy.make_token(user, sec, False)}


with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        th = headers_for(db, "teacher1")
        sh = headers_for(db, "student1")
        teacher = db.scalar(legacy.select(legacy.User).where(legacy.User.username == "teacher1"))
        student = db.scalar(legacy.select(legacy.User).where(legacy.User.username == "student1"))
        cls = db.scalar(
            legacy.select(legacy.SchoolClass).where(
                legacy.SchoolClass.school_id == teacher.school_id,
                legacy.SchoolClass.teacher_id == teacher.id,
            )
        )

        q = legacy.Question(
            school_id=teacher.school_id,
            grade=cls.grade,
            subject="语文",
            textbook="统编版（人民教育出版社）",
            semester="上册",
            unit="综合",
            knowledge="课堂讲义发布",
            text="发布快照测试题",
            options_json=json.dumps(["A", "B"], ensure_ascii=False),
            correct_index=0,
            explanation="",
            question_type="single_choice",
            answer_json="{}",
            figure_json="{}",
            creator_id=teacher.id,
        )
        db.add(q); db.flush()
        paper = legacy.Paper(
            school_id=teacher.school_id,
            title="发布快照测试试卷",
            grade=cls.grade,
            subject="语文",
            textbook="统编版（人民教育出版社）",
            unit="综合",
            question_ids_json=json.dumps([q.id]),
            teacher_id=teacher.id,
        )
        db.add(paper); db.flush()
        assignment = legacy.Assignment(
            school_id=teacher.school_id,
            title="发布快照测试作业",
            class_id=cls.id,
            paper_id=paper.id,
            due_date="2026-09-30",
        )
        db.add(assignment); db.flush()
        db.add(
            legacy.AssignmentRecipient(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                class_id=cls.id,
                student_id=student.id,
                source="assignment",
            )
        )
        drafts = legacy.Base.metadata.tables["classroom_review_handouts"]
        sessions = legacy.Base.metadata.tables["classroom_sessions"]
        releases = legacy.Base.metadata.tables["classroom_handout_releases"]
        now = datetime(2026, 9, 22, 17, 30)
        draft_id = db.execute(
            drafts.insert().values(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                class_id=cls.id,
                teacher_id=teacher.id,
                title="课堂讲义草稿",
                selected_knowledge_json='["课堂讲义发布"]',
                selected_question_ids_json=json.dumps([q.id]),
                teacher_notes="教师已审核",
                content_text="V1 冻结正文",
                created_at=now,
                updated_at=now,
            )
        ).inserted_primary_key[0]
        db.execute(
            sessions.insert().values(
                school_id=teacher.school_id,
                class_id=cls.id,
                teacher_id=teacher.id,
                source_assignment_id=assignment.id,
                handout_id=draft_id,
                subject="语文",
                textbook="统编版（人民教育出版社）",
                title="发布测试课堂",
                status="completed",
                started_at=now,
                completed_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
        aid = assignment.id
        baseline_points = db.scalar(legacy.select(legacy.func.count()).select_from(legacy.PointLedger))
        baseline_evidence = db.scalar(legacy.select(legacy.func.count()).select_from(legacy.LearningEvidenceEvent))

    state = client.get(
        f"/teacher/assignments/{aid}/class-review/handout-releases",
        headers=th,
    )
    assert state.status_code == 200, state.text
    assert state.json()["canPublish"] is True
    assert state.json()["nextVersion"] == 1
    assert state.json()["current"] is None

    denied = client.post(
        f"/teacher/assignments/{aid}/class-review/handout-publish",
        headers=th,
        json={"confirm": False},
    )
    assert denied.status_code == 400

    published1 = client.post(
        f"/teacher/assignments/{aid}/class-review/handout-publish",
        headers=th,
        json={"confirm": True},
    )
    assert published1.status_code == 200, published1.text
    release1 = published1.json()["release"]
    assert release1["version"] == 1
    assert release1["status"] == "published"

    student_list = client.get("/student/classroom-handouts", headers=sh)
    assert student_list.status_code == 200, student_list.text
    assert len(student_list.json()) == 1
    assert student_list.json()[0]["id"] == release1["id"]

    student_detail1 = client.get(
        f"/student/classroom-handouts/{release1['id']}",
        headers=sh,
    )
    assert student_detail1.status_code == 200, student_detail1.text
    assert student_detail1.json()["content"] == "V1 冻结正文"

    with legacy.SessionLocal() as db:
        drafts = legacy.Base.metadata.tables["classroom_review_handouts"]
        db.execute(
            drafts.update()
            .where(drafts.c.assignment_id == aid)
            .values(
                title="课堂讲义草稿 · 第二版",
                content_text="V2 新正文，不得覆盖 V1",
                updated_at=datetime(2026, 9, 22, 17, 40),
            )
        )
        db.commit()

    frozen = client.get(
        f"/student/classroom-handouts/{release1['id']}",
        headers=sh,
    )
    assert frozen.status_code == 200
    assert frozen.json()["content"] == "V1 冻结正文"

    published2 = client.post(
        f"/teacher/assignments/{aid}/class-review/handout-publish",
        headers=th,
        json={"confirm": True},
    )
    assert published2.status_code == 200, published2.text
    release2 = published2.json()["release"]
    assert release2["version"] == 2
    assert release2["status"] == "published"

    state2 = client.get(
        f"/teacher/assignments/{aid}/class-review/handout-releases",
        headers=th,
    ).json()
    assert state2["current"]["id"] == release2["id"]
    assert [x["version"] for x in state2["history"]] == [2, 1]
    assert state2["history"][1]["status"] == "superseded"

    teacher_v1 = client.get(
        f"/teacher/assignments/{aid}/class-review/handout-releases/{release1['id']}",
        headers=th,
    )
    assert teacher_v1.status_code == 200, teacher_v1.text
    assert teacher_v1.json()["version"] == 1
    assert teacher_v1.json()["status"] == "superseded"
    assert teacher_v1.json()["content"] == "V1 冻结正文"
    assert teacher_v1.json()["teacherNotes"] == "教师已审核"
    assert teacher_v1.json()["snapshot"]["handoutID"] == draft_id
    assert teacher_v1.json()["snapshot"]["sourceDraftUpdatedAt"]
    assert teacher_v1.json()["snapshot"]["publishedAt"]
    assert teacher_v1.json()["snapshot"]["supersededAt"]
    assert teacher_v1.json()["snapshot"]["revokedAt"] == ""

    teacher_v2 = client.get(
        f"/teacher/assignments/{aid}/class-review/handout-releases/{release2['id']}",
        headers=th,
    )
    assert teacher_v2.status_code == 200, teacher_v2.text
    assert teacher_v2.json()["version"] == 2
    assert teacher_v2.json()["status"] == "published"
    assert teacher_v2.json()["content"] == "V2 新正文，不得覆盖 V1"
    assert teacher_v2.json()["snapshot"]["handoutID"] == draft_id
    assert teacher_v2.json()["snapshot"]["sourceDraftUpdatedAt"]
    assert teacher_v2.json()["snapshot"]["publishedAt"]
    assert teacher_v2.json()["snapshot"]["supersededAt"] == ""
    assert teacher_v2.json()["snapshot"]["revokedAt"] == ""

    teacher_detail_denied = client.get(
        f"/teacher/assignments/{aid}/class-review/handout-releases/{release1['id']}",
        headers=sh,
    )
    assert teacher_detail_denied.status_code == 403

    historical_student = client.get(
        f"/student/classroom-handouts/{release1['id']}",
        headers=sh,
    )
    assert historical_student.status_code == 404

    current_student = client.get("/student/classroom-handouts", headers=sh).json()
    assert len(current_student) == 1
    assert current_student[0]["version"] == 2

    revoke_denied = client.post(
        f"/teacher/assignments/{aid}/class-review/handout-revoke",
        headers=th,
        json={"confirm": False},
    )
    assert revoke_denied.status_code == 400

    revoked = client.post(
        f"/teacher/assignments/{aid}/class-review/handout-revoke",
        headers=th,
        json={"confirm": True},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["releaseState"]["current"] is None

    assert client.get("/student/classroom-handouts", headers=sh).json() == []
    hidden = client.get(
        f"/student/classroom-handouts/{release2['id']}",
        headers=sh,
    )
    assert hidden.status_code == 404

    with legacy.SessionLocal() as db:
        releases = legacy.Base.metadata.tables["classroom_handout_releases"]
        rows = db.execute(
            legacy.select(releases)
            .where(releases.c.assignment_id == aid)
            .order_by(releases.c.version_no)
        ).all()
        assert len(rows) == 2
        assert rows[0]._mapping["content_text"] == "V1 冻结正文"
        assert rows[0]._mapping["status"] == "superseded"
        assert rows[1]._mapping["content_text"] == "V2 新正文，不得覆盖 V1"
        assert rows[1]._mapping["status"] == "revoked"

        assert db.scalar(legacy.select(legacy.func.count()).select_from(legacy.PointLedger)) == baseline_points
        assert db.scalar(legacy.select(legacy.func.count()).select_from(legacy.LearningEvidenceEvent)) == baseline_evidence
        publish_audits = db.scalar(
            legacy.select(legacy.func.count()).select_from(legacy.AuditLog).where(
                legacy.AuditLog.action == "class.review.handout.publish"
            )
        )
        revoke_audits = db.scalar(
            legacy.select(legacy.func.count()).select_from(legacy.AuditLog).where(
                legacy.AuditLog.action == "class.review.handout.revoke"
            )
        )
        assert publish_audits >= 2
        assert revoke_audits >= 1
"""

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "ENABLE_DEMO_SEED": "1",
            "PYTHONPATH": str(ROOT),
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, (
        "handout release runtime failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
