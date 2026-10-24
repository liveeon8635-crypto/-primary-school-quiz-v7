from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("weekend_report_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

SETUP = r'''
import io, zipfile
from datetime import datetime, timedelta
from sqlalchemy import insert, func

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32 + b"IEND\xaeB`\x82"

def token_for(user_id):
    with legacy.SessionLocal() as db:
        u = db.get(legacy.User, user_id)
        sec = legacy.security_for(db, u); sec.must_change_password = False; db.commit()
        return {"Authorization": "Bearer " + legacy.make_token(u, sec)}

def counts(db):
    md = legacy.Base.metadata.tables
    return {name: db.scalar(select(func.count()).select_from(md[name])) for name in
            ("weekend_answers", "weekend_written_submissions", "weekend_awards", "weekend_briefs")} | {
            "ledger": db.scalar(select(func.count()).select_from(legacy.PointLedger))}

with TestClient(app) as client:
    th, a_h, a_id, school_id = setup(client)
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        cls = legacy.SchoolClass(school_id=school_id, name="周末五年级", grade=5, teacher_id=teacher.id)
        db.add(cls); db.flush()
        b = legacy.User(school_id=school_id, username="pupil_b", name="乙同学", role="student", grade=5, password_hash=teacher.password_hash)
        c = legacy.User(school_id=school_id, username="pupil_c", name="丙同学", role="student", grade=5, password_hash=teacher.password_hash)
        pa = legacy.User(school_id=school_id, username="parent_a", name="甲家长", role="parent", password_hash=legacy.hash_password("Parent1234"))
        pb = legacy.User(school_id=school_id, username="parent_b", name="乙家长", role="parent", password_hash=legacy.hash_password("Parent1234"))
        db.add_all([b, c, pa, pb]); db.flush()
        b_id, c_id, pa_id, pb_id = b.id, c.id, pa.id, pb.id
        for sid_ in (a_id, b_id, c_id):
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid_))
        db.add(legacy.ParentStudent(parent_id=pa_id, student_id=a_id)); db.add(legacy.ParentStudent(parent_id=pb_id, student_id=b_id))
        math = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=97, title="旋转、解决问题、整理和复习",
                                     core_target="会用旋转解决问题")
        chin = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="语文", lesson_no=96, title="阅读·家国情怀", core_target="提取文本依据")
        db.add_all([math, chin]); db.flush()
        mq = []
        for i, k in enumerate(["旋转的意义", "旋转作图"]):
            q = legacy.TeachingQuestion(school_id=school_id, program_id=p.id, level="C", lesson_id=math.id, subject="数学", stem=f"数学选择{i}",
                                        options_json=json.dumps(["对", "错"], ensure_ascii=False), correct_index=0, active=True, knowledge=k)
            db.add(q); db.flush(); mq.append(q.id)
        cq = legacy.TeachingQuestion(school_id=school_id, program_id=p.id, level="C", lesson_id=chin.id, subject="语文", stem="语文选择",
                                     options_json=json.dumps(["甲", "乙"], ensure_ascii=False), correct_index=1, active=True, knowledge="词语理解")
        db.add(cq); db.flush(); cq = cq.id
        math_id, chin_id, cls_id = math.id, chin.id, cls.id
        db.commit()
    b_h, c_h = token_for(b_id), token_for(c_id)
    pa_h = {"Authorization": "Bearer " + login_and_change(client, "parent_a", "Parent1234", "Parent5678")}
    pb_h = {"Authorization": "Bearer " + login_and_change(client, "parent_b", "Parent1234", "Parent5678")}

    def lesson_session(lid, written):
        s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid, "classId": cls_id}).json()["id"]
        wids = [client.post(f"/teacher/weekend/sessions/{s}/written/questions", headers=th, json={"stem": stem, "reference": "评分要点：秘密参考"}).json()["id"]
                for stem in written]
        client.post(f"/teacher/weekend/sessions/{s}/start", headers=th)
        client.post(f"/teacher/weekend/sessions/{s}/goto", headers=th, json={"stage": 4})
        return s, wids

    # 数学：甲、乙参加；丙没有任何作答记录。
    m, (mw,) = lesson_session(math_id, ["阅读条件\n\n写出旋转过程"])
    r = client.post("/student/weekend/answer", headers=a_h, json={"sessionId": m, "questionId": mq[0], "selected": 1, "attempt": 0}); assert r.status_code == 200, r.text
    r = client.post("/student/weekend/answer", headers=a_h, json={"sessionId": m, "questionId": mq[0], "selected": 0, "attempt": 1}); assert r.status_code == 200, r.text
    assert client.post(f"/student/weekend/sessions/{m}/written/{mw}", headers=a_h, data={"text": "绕O点顺时针90度", "revision": "0"}).status_code == 200
    assert client.post("/student/weekend/answer", headers=b_h, json={"sessionId": m, "questionId": mq[0], "selected": 1, "attempt": 0}).status_code == 200
    assert client.post("/student/weekend/answer", headers=b_h, json={"sessionId": m, "questionId": mq[1], "selected": 0, "attempt": 0}).status_code == 200
    assert client.post(f"/student/weekend/sessions/{m}/written/{mw}", headers=b_h, data={"text": "", "revision": "0"},
                       files={"photo": ("a.png", PNG, "image/png")}).status_code == 200
    client.post(f"/teacher/weekend/sessions/{m}/finish", headers=th)
    # 语文：甲、丙参加；乙没有作答。
    ch, (cw1, cw2) = lesson_session(chin_id, ["文章\n\n找出体现家国情怀的句子", "文章\n\n说说你的理解"])
    assert client.post("/student/weekend/answer", headers=a_h, json={"sessionId": ch, "questionId": cq, "selected": 1, "attempt": 0}).status_code == 200
    assert client.post(f"/student/weekend/sessions/{ch}/written/{cw1}", headers=a_h, data={"text": "第三段", "revision": "0"}).status_code == 200
    assert client.post(f"/student/weekend/sessions/{ch}/written/{cw2}", headers=c_h, data={"text": "爱国", "revision": "0"}).status_code == 200
    client.post(f"/teacher/weekend/sessions/{ch}/finish", headers=th)
    written = client.get(f"/teacher/weekend/sessions/{m}/written", headers=th).json()["items"]
    a_written = next(i for i in written if i["studentId"] == a_id)
    assert client.post(f"/teacher/weekend/sessions/{m}/written/review-batch", headers=th,
                       json={"items": [{"id": a_written["id"], "revision": a_written["revision"], "result": "partial", "comment": "过程不完整"}]}).status_code == 200
    with legacy.SessionLocal() as db:
        before = counts(db)
'''


def test_weekend_reports_use_real_records_without_touching_them(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + SETUP + r'''
    # ---- class summary: completion, review state and denominators are kept apart
    s = client.get(f"/teacher/weekend/sessions/{m}/summary", headers=th)
    assert s.status_code == 200, s.text
    s = s.json()
    assert s["subject"] == "数学" and s["className"] == "周末五年级" and s["date"] and s["settled"] is False
    pupils = {p["studentId"]: p for p in s["students"]}
    A, B, C = pupils[a_id], pupils[b_id], pupils[c_id]
    assert A["counts"] == {"total": 3, "submitted": 2, "unsubmitted": 1, "correct": 1, "partial": 1, "revise": 0, "pending": 0}
    assert B["counts"] == {"total": 3, "submitted": 3, "unsubmitted": 0, "correct": 1, "partial": 0, "revise": 1, "pending": 1}
    assert C["participated"] is False and C["counts"]["submitted"] == 0
    a_items = {i["no"]: i for i in A["items"]}
    assert a_items[1]["attempts"] == 2 and a_items[1]["status"] == "correct"          # resubmitted, counted once
    assert a_items[1]["reference"].startswith("A.")                                     # teacher-only reference
    b_photo = next(i for i in B["items"] if i["kind"] == "written")
    assert b_photo["status"] == "pending" and b_photo["photoUrl"].endswith("/photo")
    assert s["summary"]["counts"]["total"] == 9 and s["summary"]["pendingReview"] == 1 and s["summary"]["participated"] == 2
    assert {k["knowledge"] for k in s["summary"]["knowledge"]} == {"旋转的意义", "旋转作图", "「写出旋转过程」（考点待教师补充）"}
    assert client.get(f"/teacher/weekend/sessions/{m}/summary", headers=a_h).status_code == 403

    # ---- the day's lessons and who actually took part
    day = client.get("/teacher/weekend/report-sessions?date=" + s["date"], headers=th).json()["items"]
    assert [x["sessionId"] for x in day] == [m, ch]
    assert {p["studentId"] for p in day[0]["participants"]} == {a_id, b_id}
    assert {p["studentId"] for p in day[1]["participants"]} == {a_id, c_id}

    # ---- generating drafts writes nothing to answers, reviews, points or the old briefs
    r = client.post("/teacher/weekend/reports", headers=th, json={"studentId": c_id, "sessionIds": [m, ch]})
    assert r.status_code == 400 and "没有作答记录" in r.json()["detail"]                   # 丙 did not take part in maths
    r = client.post("/teacher/weekend/reports", headers=th, json={"studentId": a_id, "sessionIds": [ch, m]})
    assert r.status_code == 200, r.text
    rep = r.json()["report"]; rid = rep["id"]
    assert r.json()["created"] and r.json()["source"] == "template" and rep["state"] == "draft" and rep["published"] is None
    math_part, chin_part = rep["draft"]["sections"]
    assert math_part["sessionId"] == m and chin_part["sessionId"] == ch                  # one report, one section per subject
    assert "应做 3 题，已提交 2 题，未提交 1 题" in math_part["completion"] and "部分正确 1 题" in math_part["completion"]
    # Concrete for parents: task + performance + teacher's note; never a bare number, "未标注考点" or the lesson goal.
    assert "题目任务「写出旋转过程」（第3题）：答对了一部分；老师批注：过程不完整。" in math_part["issues"]
    assert "旋转的意义（题目任务：数学选择0）（第1题）：作答正确。" in math_part["mastery"]
    assert "补做未提交的题目：「数学选择1」（第2题）" in math_part["homework"]
    for generic in ("未标注考点", "会用旋转解决问题", "概念理解、方法选择", "同类练习 3 题", "练3题"):
        assert generic not in math_part["issues"] + math_part["mastery"] + math_part["homework"], generic
    assert "待老师批改 1 题（待批改不算错误）" in chin_part["completion"]
    assert math_part["observation"] == "" and math_part["consolidation"] == ""
    joined = json.dumps(rep["draft"], ensure_ascii=False)
    for word in ("认真", "注意力", "排名", "秘密参考", "乙同学", "丙同学", "不独立"):
        assert word not in joined, word
    with legacy.SessionLocal() as db:
        assert counts(db) == before
    assert client.get(f"/teacher/weekend/sessions/{m}/summary", headers=th).json()["settled"] is False
    assert client.get(f"/student/weekend/sessions/{ch}/written", headers=c_h).json()["questions"][1]["submission"]["result"] == "pending"

    # ---- parents see nothing before publishing
    assert client.get(f"/parent/children/{a_id}/weekend-briefs", headers=pa_h).json()["reports"] == []

    # ---- teacher edits survive refresh and a repeated generate request
    math_part["observation"] = "能主动说出旋转中心"; math_part["homework"] = "订正第3题并完成练习册 P12 三题"
    saved = client.put(f"/teacher/weekend/reports/{rid}", headers=th, json={"revision": 1, "sections": [math_part, chin_part], "comment": "继续加油"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["draft"]["revision"] == 2
    stale = client.put(f"/teacher/weekend/reports/{rid}", headers=th, json={"revision": 1, "sections": [math_part, chin_part], "comment": "旧标签页"})
    assert stale.status_code == 409
    again = client.post("/teacher/weekend/reports", headers=th, json={"studentId": a_id, "sessionIds": [m, ch]}).json()
    assert again["created"] is False and again["source"] == "existing" and again["report"]["draft"]["sections"][0]["homework"] == "订正第3题并完成练习册 P12 三题"
    assert client.get(f"/teacher/weekend/reports/{rid}", headers=th).json()["draft"]["comment"] == "继续加油"

    # ---- publish: only the linked parent sees only the published version
    assert client.post(f"/teacher/weekend/reports/{rid}/publish", headers=th, json={"revision": 1}).status_code == 409
    pub = client.post(f"/teacher/weekend/reports/{rid}/publish", headers=th, json={"revision": 2})
    assert pub.status_code == 200, pub.text
    assert pub.json()["state"] == "published" and pub.json()["published"]["version"] == 1
    got = client.get(f"/parent/children/{a_id}/weekend-briefs", headers=pa_h).json()["reports"]
    assert len(got) == 1 and got[0]["subjects"] == ["数学", "语文"] and got[0]["version"] == 1
    assert got[0]["sections"][0]["observation"] == "能主动说出旋转中心" and got[0]["comment"] == "继续加油"
    assert got[0]["facts"][0]["counts"]["unsubmitted"] == 1 and "points" not in got[0]["facts"][0]
    text = json.dumps(got, ensure_ascii=False)
    for word in ("秘密参考", "乙同学", "丙同学", "绕O点", "photo", "reference"):
        assert word not in text, word
    assert client.get(f"/parent/children/{a_id}/weekend-briefs", headers=pb_h).status_code == 404     # other child's parent
    assert client.get(f"/parent/children/{b_id}/weekend-briefs", headers=pb_h).json()["reports"] == []
    assert client.get(f"/parent/children/{a_id}/weekend-briefs", headers=a_h).status_code == 403
    assert client.get(f"/teacher/weekend/reports/{rid}", headers=a_h).status_code == 403

    # ---- a later review marks the published report as having new data, without changing what parents see
    summary = client.get(f"/teacher/weekend/sessions/{m}/summary", headers=th).json()
    assert next(p for p in summary["students"] if p["studentId"] == a_id)["report"]["state"] == "published"
    w = client.get(f"/teacher/weekend/sessions/{ch}/written", headers=th).json()["items"]
    a_cw = next(i for i in w if i["studentId"] == a_id)
    client.post(f"/teacher/weekend/sessions/{ch}/written/review-batch", headers=th,
                json={"items": [{"id": a_cw["id"], "revision": a_cw["revision"], "result": "correct", "comment": ""}]})
    after = client.get(f"/teacher/weekend/reports/{rid}", headers=th).json()
    assert after["state"] == "stale" and after["stateLabel"] == "发布后有新数据" and after["draft"]["factsChanged"] is True
    assert after["facts"][1]["counts"]["pending"] == 0                                   # live facts refreshed
    assert after["draft"]["sections"][0]["observation"] == "能主动说出旋转中心"            # edits kept
    assert client.get(f"/parent/children/{a_id}/weekend-briefs", headers=pa_h).json()["reports"][0]["facts"][1]["counts"]["pending"] == 1
    summary = client.get(f"/teacher/weekend/sessions/{ch}/summary", headers=th).json()
    assert next(p for p in summary["students"] if p["studentId"] == a_id)["report"]["stateLabel"] == "发布后有新数据"

    # ---- regenerating needs an explicit replace and keeps the teacher's observation and comment
    regen = client.post("/teacher/weekend/reports", headers=th, json={"studentId": a_id, "sessionIds": [m, ch], "replace": True, "revision": 1})
    assert regen.status_code == 409
    regen = client.post("/teacher/weekend/reports", headers=th, json={"studentId": a_id, "sessionIds": [m, ch], "replace": True, "revision": 2}).json()["report"]
    assert regen["draft"]["sections"][0]["observation"] == "能主动说出旋转中心" and regen["draft"]["comment"] == "继续加油"
    assert "补做未提交的题目：「数学选择1」（第2题）" in regen["draft"]["sections"][0]["homework"] and regen["draft"]["factsChanged"] is False
    assert regen["state"] == "stale" and regen["draft"]["unpublishedEdits"] is True
    assert client.get(f"/parent/children/{a_id}/weekend-briefs", headers=pa_h).json()["reports"][0]["version"] == 1
    republished = client.post(f"/teacher/weekend/reports/{rid}/publish", headers=th, json={"revision": 3}).json()
    assert republished["state"] == "published" and republished["published"]["version"] == 2
    latest = client.get(f"/parent/children/{a_id}/weekend-briefs", headers=pa_h).json()["reports"]
    assert len(latest) == 1 and latest[0]["version"] == 2 and latest[0]["facts"][1]["counts"]["correct"] == 2

    # ---- Word: same text and counts as the published version, nothing about classmates
    d = client.get(f"/teacher/weekend/reports/{rid}/report.docx?version=published", headers=th)
    assert d.status_code == 200 and d.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert f"weekend-report-{rid}-" in d.headers["content-disposition"] and "filename*=UTF-8''" in d.headers["content-disposition"]
    xml = zipfile.ZipFile(io.BytesIO(d.content)).read("word/document.xml").decode()
    assert "周末课学情反馈" in xml and "能主动说出旋转中心" in xml and "继续加油" in xml and "已发布第2版" in xml
    assert "应做 3 题，已提交 2 题，未提交 1 题" in xml and "数学" in xml and "语文" in xml
    for word in ("乙同学", "丙同学", "秘密参考"):
        assert word not in xml, word
    assert client.get(f"/teacher/weekend/reports/{rid}/report.docx?version=published", headers=a_h).status_code == 403

    # ---- another teacher cannot open the report or the lessons
    with legacy.SessionLocal() as db:
        other = legacy.User(school_id=school_id, username="teacher_x", name="别的老师", role="teacher", password_hash=legacy.hash_password("Teacher1234"))
        db.add(other); db.commit(); other_id = other.id
    oh = token_for(other_id)
    assert client.get(f"/teacher/weekend/reports/{rid}", headers=oh).status_code == 404
    assert client.get(f"/teacher/weekend/sessions/{m}/summary", headers=oh).status_code == 404
    assert client.post("/teacher/weekend/reports", headers=oh, json={"studentId": a_id, "sessionIds": [m]}).status_code == 404

    # ---- lessons from different days are not merged; a single-subject report works for 丙
    with legacy.SessionLocal() as db:
        t = legacy.Base.metadata.tables["weekend_sessions"]
        db.execute(t.update().where(t.c.id == ch).values(started_at=datetime.utcnow() - timedelta(days=3))); db.commit()
    assert client.post("/teacher/weekend/reports", headers=th, json={"studentId": a_id, "sessionIds": [m, ch], "replace": True, "revision": 3}).status_code == 400
    single = client.post("/teacher/weekend/reports", headers=th, json={"studentId": c_id, "sessionIds": [ch]}).json()["report"]
    assert [f["subject"] for f in single["facts"]] == ["语文"] and single["state"] == "draft"
    with legacy.SessionLocal() as db:
        assert counts(db) == before
    print("OK")
''')


def test_ai_suggestions_stay_unconfirmed_until_the_teacher_checks_them(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + SETUP + r'''
    replies.append(RuntimeError("model down"))
    r = client.post("/teacher/weekend/reports", headers=th, json={"studentId": a_id, "sessionIds": [ch], "useAi": True}).json()
    assert r["source"] == "ai_failed" and "应做 3 题" in r["report"]["draft"]["sections"][0]["completion"]
    rid = r["id"]; ev = r["report"]["draft"]["evidence"]
    assert [e["status"] for e in ev] == ["correct"]                       # 语文: choice right, written still pending
    # Maths for 乙: wrong choice (旋转的意义), right choice, photo pending.
    r = client.post("/teacher/weekend/reports", headers=th, json={"studentId": b_id, "sessionIds": [m]}).json()
    bid, ev = r["id"], r["report"]["draft"]["evidence"]
    wrong = next(e for e in ev if e["status"] == "revise")
    assert wrong["knowledge"] == "旋转的意义" and wrong["knowledgeSource"] == "question" and wrong["answer"] == "B. 错"
    issues = r["report"]["draft"]["sections"][0]["issues"]
    assert "旋转的意义（题目任务：数学选择0）（第1题）：选择了「B. 错」，未选出正确答案；具体错因需教师核实。" in issues
    replies.append(json.dumps({"items": [{"key": wrong["key"], "knowledge": "别的考点", "cause": "把顺时针看成逆时针"}]}, ensure_ascii=False))
    r = client.post("/teacher/weekend/reports", headers=th, json={"studentId": b_id, "sessionIds": [m], "useAi": True, "replace": True, "revision": 1}).json()
    assert r["source"] == "ai"
    got = next(e for e in r["report"]["draft"]["evidence"] if e["key"] == wrong["key"])
    assert got["knowledge"] == "旋转的意义" and got["cause"] == "把顺时针看成逆时针" and got["causeSource"] == "ai"   # question knowledge never replaced
    assert "把顺时针看成逆时针" not in r["report"]["draft"]["sections"][0]["issues"]                                   # unconfirmed: not shown
    assert prompts and "乙同学" not in prompts[-1] and "周末五年级" not in prompts[-1]
    rep = r["report"]
    saved = client.put(f"/teacher/weekend/reports/{bid}", headers=th, json={"revision": rep["draft"]["revision"], "sections": rep["draft"]["sections"],
        "comment": "", "evidence": [{"key": wrong["key"], "knowledge": "旋转的意义", "cause": "能判断旋转中心，但把顺时针看成了逆时针", "confirmed": True}]}).json()
    regen = client.post("/teacher/weekend/reports", headers=th, json={"studentId": b_id, "sessionIds": [m], "replace": True,
                                                                      "revision": saved["draft"]["revision"]}).json()["report"]
    assert "选择了「B. 错」，未选出正确答案；能判断旋转中心，但把顺时针看成了逆时针。" in regen["draft"]["sections"][0]["issues"]
    with legacy.SessionLocal() as db:
        assert counts(db) == before
    print("OK")
''')


def test_teacher_and_parent_pages_wire_the_report_entry(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
with TestClient(app) as client:
    control = client.get("/v1/weekend").text
    assert "课后总结与家长反馈" in control and "/v1/weekend-report?s=" in control
    page = client.get("/v1/weekend-report")
    assert page.status_code == 200
    html = page.text
    for text in ("/summary", "/teacher/weekend/reports", "/publish", "report.docx", "/report-sessions?date=",
                 "预览家长看到的内容", "发布给家长", "按最新数据重新生成", "待批", "未提交", "需订正",
                 "/practice/generate", "/practice/assign", "审核确认并布置给", "考点与表现依据", "已核实", "删除这题", "查看作答与批改"):
        assert text in html, text
    parent = client.get("/v1/weekend-brief").text
    assert "周末课学情反馈" in parent and "d.reports" in parent and "老师发布后会显示在这里" in parent
    top = client.get("/classic?legacy=1&unified=1&page=childProgress").text
    assert "cy-wkr-band" in top and "/v1/weekend-brief?child=" in top
    print("OK")
''')


def test_variant_practice_is_per_pupil_reviewed_then_assigned_once_through_homework(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + SETUP + r'''
    # 丙's Chinese short answer is marked "revise" with a concrete teacher note.
    w = client.get(f"/teacher/weekend/sessions/{ch}/written", headers=th).json()["items"]
    c_cw = next(i for i in w if i["studentId"] == c_id)
    client.post(f"/teacher/weekend/sessions/{ch}/written/review-batch", headers=th,
                json={"items": [{"id": c_cw["id"], "revision": c_cw["revision"], "result": "revise", "comment": "只写了“爱国”，缺少原文依据"}]})
    def assignments():
        with legacy.SessionLocal() as db:
            return db.scalar(select(func.count()).select_from(legacy.Assignment))
    n0 = assignments()

    # ---- 乙 (maths): one wrong choice question -> one weak point, 2 variants by default
    rb = client.post("/teacher/weekend/reports", headers=th, json={"studentId": b_id, "sessionIds": [m]}).json()["report"]
    groups = rb["practiceGroups"]
    assert len(groups) == 1 and groups[0]["count"] == 2 and groups[0]["topic"] == "旋转的意义"
    gkey = groups[0]["key"]
    replies.append(json.dumps({"groups": [{"key": gkey, "questions": [
        {"question_type": "single_choice", "level": 1, "text": "数学选择0", "options": ["对", "错", "不确定", "都不是"], "correct_index": 0},   # the original
        {"question_type": "single_choice", "level": 1, "text": "数学选择7", "options": ["对", "错", "不确定", "都不是"], "correct_index": 0},   # only a number changed
        {"question_type": "fill_blank", "level": 1, "text": "钟面上的分针从12走到3，绕中心按什么方向旋转了多少度？", "answer": "顺时针90度",
         "accepted_answers": ["顺时针旋转90度"], "explanation": "从12到3是四分之一圈", "knowledge": "旋转的意义"},
        {"question_type": "single_choice", "level": 2, "text": "风车叶片绕中心逆时针旋转90°后，原来朝上的叶片会朝向哪里？",
         "options": ["朝左", "朝右", "朝下", "不变"], "correct_index": 0, "explanation": "逆时针旋转四分之一圈", "knowledge": "旋转的意义"},
        {"question_type": "single_choice", "level": 3, "text": "如图，三角形绕点O旋转后……", "options": ["甲", "乙", "丙", "丁"], "correct_index": 1}]}]},
        ensure_ascii=False))
    g = client.post(f"/teacher/weekend/reports/{rb['id']}/practice/generate", headers=th, json={"revision": rb["draft"]["revision"]})
    assert g.status_code == 200, g.text
    rb = g.json()["report"]
    qs = rb["draft"]["practice"]["groups"][0]["questions"]
    assert [q["text"][:4] for q in qs] == ["钟面上的", "风车叶片"]                                  # copy, number-swap and figure-less rejected
    assert rb["draft"]["practice"]["state"] == "review" and qs[0]["answer"] == "顺时针90度" and qs[1]["explanation"]
    assert "B. 错" in prompts[-1] and "旋转的意义" in prompts[-1] and "乙同学" not in prompts[-1] and "过程不完整" not in prompts[-1]
    assert "数学选择0" in rb["draft"]["practice"]["groups"][0]["basis"]
    assert assignments() == n0                                                                     # generating assigns nothing

    # ---- 丙 (语文): a different weak point and a different set; reading material is required
    rc = client.post("/teacher/weekend/reports", headers=th, json={"studentId": c_id, "sessionIds": [ch]}).json()["report"]
    cg = rc["practiceGroups"]
    assert len(cg) == 1 and cg[0]["topic"] == "「说说你的理解」" and cg[0]["key"] != gkey
    assert "阅读材料《文章》—题目任务「说说你的理解」（第3题）：答案需要订正；老师批注：只写了“爱国”，缺少原文依据。" in rc["draft"]["sections"][0]["issues"]
    passage = "阅读短文：外公是一名老兵。每年国庆，他都早早换上旧军装，站在阳台上看升旗直播，眼里含着泪。他常说：“没有国，哪有家。”他把攒下的退休金捐给了家乡的学校。"
    replies.append(json.dumps({"groups": [{"key": cg[0]["key"], "knowledge": "结合人物言行说明人物品质", "questions": [
        {"question_type": "single_choice", "level": 1, "text": "外公看升旗时眼里含着泪，说明了什么？", "options": ["爱国", "怕冷", "生气", "无聊"], "correct_index": 0},
        {"question_type": "single_choice", "level": 2, "text": passage + "\n下列哪句话最能作为“外公热爱祖国”的原文依据？",
         "options": ["“没有国，哪有家。”", "外公是一名老兵。", "他站在阳台上。", "每年国庆。"], "correct_index": 0, "explanation": "直接表达观点的语言描写",
         "knowledge": "结合人物言行说明人物品质"},
        {"question_type": "fill_blank", "level": 3, "text": passage + "\n外公把退休金捐给了家乡的____，这一行为表现了他热爱家乡。", "answer": "学校",
         "explanation": "原文最后一句"}]}]}, ensure_ascii=False))
    gc = client.post(f"/teacher/weekend/reports/{rc['id']}/practice/generate", headers=th,
                     json={"revision": rc["draft"]["revision"], "counts": {cg[0]["key"]: 3}}).json()                # teacher raised the count
    cq = gc["report"]["draft"]["practice"]["groups"][0]["questions"]
    assert len(cq) == 2 and all(passage in q["text"] for q in cq) and any("阅读材料" in p for p in gc["problems"])
    assert "缺少原文依据" in prompts[-1] and "说说你的理解" in prompts[-1] and "B. 错" not in prompts[-1]
    assert {q["text"] for q in qs}.isdisjoint({q["text"] for q in cq})                              # not one generic set for everyone

    # ---- a failed generation keeps the report and existing questions
    replies.append(RuntimeError("model down"))
    before_fail = client.get(f"/teacher/weekend/reports/{rb['id']}", headers=th).json()
    fail = client.post(f"/teacher/weekend/reports/{rb['id']}/practice/generate", headers=th, json={"revision": before_fail["draft"]["revision"]})
    assert fail.status_code == 502 and "生成失败" in fail.json()["detail"] and "未改动" in fail.json()["detail"]
    after_fail = client.get(f"/teacher/weekend/reports/{rb['id']}", headers=th).json()
    assert after_fail["draft"]["revision"] == before_fail["draft"]["revision"] and after_fail["draft"]["practice"]["groups"][0]["questions"] == qs

    # ---- teacher edits / deletes under the same rules
    bad = [{**qs[0], "text": "如图，求旋转角。"}]
    assert client.put(f"/teacher/weekend/reports/{rb['id']}/practice", headers=th,
                      json={"revision": after_fail["draft"]["revision"], "groups": [{"key": gkey, "questions": bad}]}).status_code == 400
    edited = [{**qs[0], "text": "钟面上的时针从12走到3，绕中心按什么方向旋转了多少度？"}, qs[1]]
    rb = client.put(f"/teacher/weekend/reports/{rb['id']}/practice", headers=th,
                    json={"revision": after_fail["draft"]["revision"], "groups": [{"key": gkey, "questions": edited}]}).json()
    assert rb["draft"]["practice"]["groups"][0]["questions"][0]["text"].startswith("钟面上的时针")

    # ---- parents see the review state only after the report is published, never answers
    pub = client.post(f"/teacher/weekend/reports/{rb['id']}/publish", headers=th, json={"revision": rb["draft"]["revision"]}).json()
    assert assignments() == n0                                                                     # publishing does not assign
    pr = client.get(f"/parent/children/{b_id}/weekend-briefs", headers=pb_h).json()["reports"][0]["practice"]
    assert pr == {"state": "review", "label": "待教师审核"}

    # ---- assign once, only to 乙, through the existing targeted-practice homework
    rev = pub["draft"]["revision"]
    first = client.post(f"/teacher/weekend/reports/{rb['id']}/practice/assign", headers=th, json={"revision": rev})
    assert first.status_code == 200, first.text
    again = client.post(f"/teacher/weekend/reports/{rb['id']}/practice/assign", headers=th, json={"revision": rev})
    assert again.status_code == 409
    rb = first.json()
    assert assignments() == n0 + 1 and rb["draft"]["practice"]["state"] == "assigned"
    aid = rb["draft"]["practice"]["assignments"][0]["assignmentId"]
    with legacy.SessionLocal() as db:
        recips = db.scalars(select(legacy.AssignmentRecipient.student_id).where(legacy.AssignmentRecipient.assignment_id == aid)).all()
        assert list(recips) == [b_id]
        assert db.scalar(select(func.count()).select_from(legacy.ReinforcementLink).where(legacy.ReinforcementLink.assignment_id == aid)) == 1
    assert client.post(f"/teacher/weekend/reports/{rb['id']}/practice/generate", headers=th,
                       json={"revision": rb["draft"]["revision"]}).status_code == 409                  # assigned questions are locked
    assert all(x["id"] != aid for x in client.get("/student/assignments", headers=c_h).json())
    mine = next(x for x in client.get("/student/assignments", headers=b_h).json() if x["id"] == aid)
    paper = client.get(f"/papers/{mine['paperID']}/questions", headers=b_h).json()
    assert len(paper) == 2 and all("correct_index" not in q and "explanation" not in q and "answer_json" not in q for q in paper)
    parent = client.get(f"/parent/children/{b_id}/weekend-briefs", headers=pb_h).json()["reports"][0]["practice"]
    assert parent["state"] == "assigned" and parent["label"] == "已布置" and len(parent["groups"][0]["questions"]) == 2
    ptext = json.dumps(parent, ensure_ascii=False)
    assert "顺时针90度" not in ptext and "四分之一圈" not in ptext and "correct_index" not in ptext

    # ---- the pupil answers in the existing homework; results return to the teacher and parent
    answers = [{"question_id": q["id"], "text_answer": "顺时针90度"} if q["questionType"] == "fill_blank" else {"question_id": q["id"], "selected_index": 1}
               for q in paper]
    done = client.post(f"/student/assignments/{aid}/submit", headers=b_h, json={"answers": answers})
    assert done.status_code == 200, done.text
    view = client.get(f"/teacher/weekend/reports/{rb['id']}", headers=th).json()["draft"]["practice"]
    assert view["state"] == "graded" and view["assignments"][0]["correct"] == 1 and view["assignments"][0]["total"] == 2
    subs = client.get(f"/teacher/assignments/{aid}/submissions", headers=th).json()
    assert subs[0]["studentID"] == b_id and subs[0]["correct"] == 1
    parent = client.get(f"/parent/children/{b_id}/weekend-briefs", headers=pb_h).json()["reports"][0]["practice"]
    assert parent["label"] == "已批改" and parent["assignments"][0]["correct"] == 1
    d = client.get(f"/teacher/weekend/reports/{rb['id']}/report.docx?version=published", headers=th)
    xml = zipfile.ZipFile(io.BytesIO(d.content)).read("word/document.xml").decode()
    assert "针对性练习（已批改）" in xml and "风车叶片" in xml and "顺时针90度" not in xml
    with legacy.SessionLocal() as db:
        md = legacy.Base.metadata.tables
        assert db.scalar(select(func.count()).select_from(md["weekend_answers"])) == before["weekend_answers"]
        assert db.scalar(select(func.count()).select_from(md["weekend_awards"])) == before["weekend_awards"]
    print("OK")
''')
