"""Regression tests for explain finish/evaluation/points and Stage 5-7 student sync."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("explain_stage567_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_explain_finish_evaluation_and_stage567_student_sync(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r"""
with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(
            school_id=school_id,
            program_id=p.id,
            subject="数学",
            lesson_no=96,
            title="梯形复盘与收口",
            core_target="掌握梯形面积并完成互查",
            closure_training="1. 互查演练：核查高是否垂直。\n2. 课后任务：完成错题订正。",
        )
        db.add(l); db.flush(); lid = l.id
        tid = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id))
        cls.teacher_id = tid
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == student_id))
        if link is None:
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=student_id))
        else:
            link.class_id = cls.id
        db.commit()

    sid = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()["id"]
    base = f"/teacher/weekend/sessions/{sid}"
    student = f"/student/weekend/sessions/{sid}/written"
    q1 = client.post(base + "/written/questions", headers=th, json={"stem": "第1题 求梯形面积", "reference": "40平方厘米"}).json()["id"]
    assert client.post(base + "/start", headers=th).status_code == 200
    assert client.post(base + "/goto", headers=th, json={"stage": 4}).status_code == 200
    assert client.post(base + "/practice-question", headers=th, json={"question": 1}).status_code == 200
    assert client.post(f"{student}/{q1}", headers=sh, data={"text": "40平方厘米"}).status_code == 200

    # Move to stage 5 and invite student to explain.
    assert client.post(base + "/goto", headers=th, json={"stage": 5}).status_code == 200
    inv = client.post(base + "/explain", headers=th, json={"tutorId": student_id, "questionId": q1, "questionType": "written"})
    assert inv.status_code == 200, inv.text
    bd_during = client.get(base + "/board", headers=th).json()
    assert any("同学来讲" in line for line in bd_during["content"])

    # Student declines -> board hides prompt; then student accepts -> board shows prompt again.
    dec = client.post("/student/weekend/explain/respond", headers=sh, json={"sessionId": sid, "questionId": q1, "questionType": "written", "decision": "decline"})
    assert dec.status_code == 200, dec.text
    assert not any("同学来讲" in line for line in client.get(base + "/board", headers=th).json()["content"])
    acc = client.post("/student/weekend/explain/respond", headers=sh, json={"sessionId": sid, "questionId": q1, "questionType": "written", "decision": "accept"})
    assert acc.status_code == 200, acc.text
    assert any("同学来讲" in line for line in client.get(base + "/board", headers=th).json()["content"])

    # Finish explanation with rating & comment -> board clears invitation, teacher & student see review + points, and settle-preview includes the points.
    fin = client.post(
        base + "/explain/finish",
        headers=th,
        json={"tutorId": student_id, "questionId": q1, "questionType": "written", "rating": "clear", "comment": "步骤完整，表达清楚"},
    )
    assert fin.status_code == 200, fin.text
    assert fin.json()["finished"] is True
    assert fin.json()["review"]["points"] == 2
    assert fin.json()["review"]["label"] == "思路清晰"

    bd_after = client.get(base + "/board", headers=th).json()
    assert not any("同学来讲" in line for line in bd_after["content"])

    stu_exp = client.get("/student/weekend/explain", headers=sh).json()["items"]
    assert len(stu_exp) == 1
    assert stu_exp[0]["explainReview"]["finished"] is True
    assert stu_exp[0]["explainReview"]["points"] == 2
    assert stu_exp[0]["explainReview"]["comment"] == "步骤完整，表达清楚"
    assert stu_exp[0]["explainResponse"]["decision"] == "accept"

    sug = client.get(base + "/peer-suggest", headers=th).json()["questions"]
    assert sug[0]["submitted"][0]["explainReview"]["finished"] is True

    # Settle preview must include teacher-evaluated explain points in tutor parts and why.tutor.explained!
    pre = client.get(base + "/settle-preview", headers=th).json()
    me = next(x for x in pre["items"] if x["studentId"] == student_id)
    assert me["parts"]["tutor"] >= 2 and me["total"] >= 2
    assert me["why"]["tutor"]["explained"][0]["points"] == 2
    assert me["why"]["tutor"]["explained"][0]["label"] == "思路清晰"

    # Stage 5, 6, 7 student sync returns distinct stage content and Stage 7 homeworkUrl.
    c5 = client.get("/student/weekend/current", headers=sh).json()
    assert c5["stage"] == 5 and "练习复盘" in c5["message"]
    assert client.post(base + "/goto", headers=th, json={"stage": 6}).status_code == 200
    c6 = client.get("/student/weekend/current", headers=sh).json()
    assert c6["stage"] == 6 and c6["message"] != c5["message"] and bool(c6.get("stageContent"))
    assert client.post(base + "/goto", headers=th, json={"stage": 7}).status_code == 200
    c7 = client.get("/student/weekend/current", headers=sh).json()
    assert c7["stage"] == 7 and c7.get("homeworkUrl") == "/v1"
    assert any("互查演练" in x for x in c7.get("stageContent") or [])

    # Real HTML checks.
    control_html = client.get("/v1/weekend").text
    practice_html = client.get("/v1/weekend-practice").text
    assert "/explain/finish" in control_html
    assert "按未订正错题生成并下发个性化练习" in control_html
    assert "/stage6-checks" in control_html and "/stage6-checks" in practice_html
    assert "前往首页“作业”查看专属课后练习" in practice_html
    assert "本次讲题已完成" in practice_html
    assert "lastExplainSignature" in practice_html
    assert "我来讲（同意）" in practice_html and "暂不讲解（拒绝）" in practice_html
    print("OK")
""",
        {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    )


def test_stage6_mastery_checks_and_stage7_unresolved_homework_filter(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r"""
with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(
            school_id=school_id,
            program_id=p.id,
            subject="数学",
            lesson_no=97,
            title="梯形达标与遗留错题",
            core_target="辨认高并计算梯形面积",
        )
        db.add(l); db.flush(); lid = l.id
        tid = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id))
        cls.teacher_id = tid
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == student_id))
        if link is None:
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=student_id))
        else:
            link.class_id = cls.id
        db.commit()

    sid = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid}).json()["id"]
    base = f"/teacher/weekend/sessions/{sid}"
    student_w = f"/student/weekend/sessions/{sid}/written"
    q1 = client.post(base + "/written/questions", headers=th, json={"stem": "第1题 已知上底3下底5高4求梯形面积", "reference": "16"}).json()["id"]
    q2 = client.post(base + "/written/questions", headers=th, json={"stem": "第2题 寻找合适条件计算直角梯形面积", "reference": "40"}).json()["id"]
    assert client.post(base + "/start", headers=th).status_code == 200
    assert client.post(base + "/goto", headers=th, json={"stage": 4}).status_code == 200
    assert client.post(base + "/practice-question", headers=th, json={"question": 1}).status_code == 200
    assert client.post(base + "/practice-question", headers=th, json={"question": 2}).status_code == 200

    s1 = client.post(f"{student_w}/{q1}", headers=sh, data={"text": "1"}).json()["submission"]["id"]
    s2 = client.post(f"{student_w}/{q2}", headers=sh, data={"text": "1"}).json()["submission"]["id"]
    assert client.post(base + "/publish-answers", headers=th, json={"question": 1}).status_code == 200
    assert client.post(base + "/publish-answers", headers=th, json={"question": 2}).status_code == 200
    rev = client.post(base + "/written/review-batch", headers=th, json={"items": [
        {"id": s1, "revision": 1, "result": "revise", "comment": "重算"},
        {"id": s2, "revision": 1, "result": "revise", "comment": "找垂直高"},
    ]})
    assert rev.status_code == 200, rev.text

    # Stage 6: both questions appear as needing mastery confirmation, and student can still submit revisions!
    assert client.post(base + "/goto", headers=th, json={"stage": 6}).status_code == 200
    t6 = client.get(base + "/stage6-checks", headers=th).json()
    assert t6["total"] == 2 and t6["pending"] == 2
    assert all(it["wrongCount"] == 1 and it["isCommonError"] is False for it in t6["items"])
    stu_w6 = client.get(f"/student/weekend/sessions/{sid}/written", headers=sh).json()
    assert stu_w6["canSubmit"] is True
    assert all(q["canRevise"] is True for q in stu_w6["questions"])
    rev_s6 = client.post(f"{student_w}/{q1}", headers=sh, data={"text": "16", "revision": "1"})
    assert rev_s6.status_code == 200, rev_s6.text
    # Re-grade q1 as revise so downstream Stage-6 mastery test still exercises both questions
    rev_s6_id = rev_s6.json()["submission"]["id"]
    rev_s6_ver = rev_s6.json()["submission"]["revision"]
    assert client.post(base + "/written/review-batch", headers=th, json={"items": [
        {"id": rev_s6_id, "revision": rev_s6_ver, "result": "revise", "comment": "再核对单位"},
    ]}).status_code == 200
    stu6 = client.get(f"/student/weekend/sessions/{sid}/stage6-checks", headers=sh).json()
    assert len(stu6["items"]) == 2

    # Student marks q1 understood, raises doubt on q2 with a note.
    assert client.post(f"/student/weekend/sessions/{sid}/stage6-checks", headers=sh, json={"questionKey": f"written:{q1}", "status": "understood"}).status_code == 200
    assert client.post(f"/student/weekend/sessions/{sid}/stage6-checks", headers=sh, json={"questionKey": f"written:{q2}", "status": "doubt", "note": "为什么高是5不是5.5"}).status_code == 200

    # Teacher marks q1 mastered, leaves q2 for after-class homework.
    m1 = client.post(base + "/stage6-checks", headers=th, json={"questionKey": f"written:{q1}", "status": "mastered"}).json()
    m2 = client.post(base + "/stage6-checks", headers=th, json={"questionKey": f"written:{q2}", "status": "homework"}).json()
    assert m2["mastered"] == 1 and m2["homework"] == 1 and m2["doubtCount"] == 1

    # Board in stage 6 reflects live mastery progress without leaking student names.
    bd6 = client.get(base + "/board", headers=th).json()
    assert any("已达标 1" in line and "留入课后 1" in line for line in bd6["content"])

    # Stage 7 report & practice groups exclude Stage-6 mastered q1 and keep unresolved q2!
    rep = client.post("/teacher/weekend/reports", headers=th, json={"sessionIds": [sid], "studentId": student_id})
    assert rep.status_code == 200, rep.text
    report_body = rep.json()["report"]
    rid = report_body["id"]
    assert report_body["resolvedStage6Count"] == 1
    groups = report_body["practiceGroups"]
    assert len(groups) == 1
    assert groups[0]["items"][0]["no"] == 2
    assert groups[0]["items"][0]["stage6Note"] == "为什么高是5不是5.5"

    # Pre-existing draft immediately reflects later Stage-6 mastery updates on GET without recreating the draft!
    assert client.post(f"/student/weekend/sessions/{sid}/stage6-checks", headers=sh, json={"questionKey": f"written:{q2}", "status": "understood"}).status_code == 200
    assert client.post(base + "/stage6-checks", headers=th, json={"questionKey": f"written:{q2}", "status": "mastered"}).status_code == 200
    refreshed = client.get(f"/teacher/weekend/reports/{rid}", headers=th)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["resolvedStage6Count"] == 2
    assert refreshed.json()["practiceGroups"] == []

    # Entering Stage 7 closes classroom revision window
    assert client.post(base + "/goto", headers=th, json={"stage": 7}).status_code == 200
    stu_w7 = client.get(f"/student/weekend/sessions/{sid}/written", headers=sh).json()
    assert stu_w7["canSubmit"] is False
    assert all(q["canRevise"] is False for q in stu_w7["questions"])
    assert client.post(f"{student_w}/{q2}", headers=sh, data={"text": "40"}).status_code == 409
    print("OK")
""",
        {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    )


def test_report_practice_ux_and_stage67_declutter():
    from changying.web.weekend_pages import BOARD_JS, CONTROL_JS, PRACTICE_JS
    from changying.web.weekend_report_pages import REPORT_JS

    assert "if(unmarked)qd.open=true" not in REPORT_JS
    assert "cardMsgs" in REPORT_JS
    assert "setGenBusy" in REPORT_JS
    assert "AbortController" in REPORT_JS
    assert "resolvedStage6Count" in REPORT_JS
    assert "pendingCnt" in REPORT_JS
    assert "去课堂批改" in REPORT_JS
    assert "batchSize=3" in REPORT_JS
    assert "s6Filter" in CONTROL_JS
    assert "s7Summary" in CONTROL_JS
    assert "pendingReview" in CONTROL_JS
    assert "pollBusy" in CONTROL_JS
    assert "boardBusy" in BOARD_JS
    assert "visibilitychange" in PRACTICE_JS


def test_courseware_lru_cache_hits_and_invalidates(tmp_path):
    from sqlalchemy import create_engine, insert, update
    from sqlalchemy.orm import sessionmaker
    from datetime import datetime, timedelta
    import json
    from changying.web.weekend_courseware import (
        _CW_ITEMS_CACHE,
        cached_courseware_items,
        register_courseware_table,
    )
    from sqlalchemy.orm import declarative_base

    Base = declarative_base()

    class _Impl:
        pass

    _Impl.Base = Base
    cw_t = register_courseware_table(_Impl)
    eng = create_engine(f"sqlite:///{tmp_path / 'cw_cache.sqlite3'}")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    t0 = datetime(2026, 11, 24, 1, 0, 0)
    with Session() as db:
        db.execute(insert(cw_t).values(
            school_id=1, lesson_id=10, teacher_id=2, kind="slide", stage_no=4, status="approved",
            params_json=json.dumps({"version": 2, "items": [{"stage": 4, "page": 0, "kind": "slide", "approved": {"title": "v1"}}]}),
            approved_json="{}", approved_stage=4, live_json="{}", updated_at=t0,
        ))
        db.commit()

        meta1, items1 = cached_courseware_items(db, cw_t, 1, 10, approved_only=True)
        meta2, items2 = cached_courseware_items(db, cw_t, 1, 10, approved_only=True)
        assert meta1 is not None and meta2 is not None
        assert items1 is items2  # second call hits in-process LRU cache without re-parsing JSON
        assert items1[0]["approved"]["title"] == "v1"

        # Updating updated_at invalidates cache automatically
        db.execute(update(cw_t).where(cw_t.c.lesson_id == 10).values(
            params_json=json.dumps({"version": 2, "items": [{"stage": 4, "page": 0, "kind": "slide", "approved": {"title": "v2"}}]}),
            updated_at=t0 + timedelta(seconds=1),
        ))
        db.commit()
        _, items3 = cached_courseware_items(db, cw_t, 1, 10, approved_only=True)
        assert items3 is not items1
        assert items3[0]["approved"]["title"] == "v2"
        assert len(_CW_ITEMS_CACHE) <= 6
