"""课后反馈优化：文字题考点标一次全班通用、课后题、家长“一眼看懂”、和自己上次比、晚托提示、全班操作。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from changying.services.lesson_written import lesson_goals, suggest_knowledge
from changying.services import weekend_reports as wr

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tests" / file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


helpers = _load("feedback_upgrade_helpers", "test_homework_solve.py")
reports_test = _load("feedback_upgrade_reports", "test_weekend_reports.py")


def test_suggestions_come_from_the_lesson_plan_headings_and_goals():
    assert suggest_knowledge("例题 1 | 省略乘号 写出下面各式的结果：5×m=") == "省略乘号"
    assert suggest_knowledge("材料\n\n第 18 题 | 字母的取值范围 等腰三角形的底角是 a°") == "字母的取值范围"
    for only_type in ("诊断题 1 | 填空 （1）a×1.5", "第 20 题 | 填空（6 分）", "诊断题 3 | 选择（1）省略乘号", "写出旋转过程"):
        assert suggest_knowledge(only_type) == "", only_type
    assert lesson_goals("（1）能按规则省略乘号，正确写出 5a。 （2）会代入求值且不漏单位") == ["能按规则省略乘号", "会代入求值且不漏单位"]
    assert lesson_goals("会用旋转解决问题") == []


def test_compare_is_only_with_the_pupils_own_previous_lesson():
    before = {"date": "2026-10-24", "lessonTitle": "第1课", "counts": {"submitted": 10, "correct": 5, "revise": 2, "partial": 1}}
    now = {"counts": {"submitted": 12, "correct": 9, "revise": 1, "partial": 0}}
    text = wr.compare_text(before, now)
    assert text == "和孩子自己上次（2026-10-24《第1课》）比：完全正确 5/10 题 → 9/12 题；需要订正或补全 3 题 → 1 题。"
    assert wr.compare_text({"counts": {"submitted": 0}}, now) == ""
    for word in ("排名", "平均", "同学"):
        assert word not in text


FLOW = r'''
    written_t = legacy.Base.metadata.tables["weekend_written_questions"]
    with legacy.SessionLocal() as db:
        tid = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        db.get(legacy.TeachingLesson, math_id).core_target = "（1）会用旋转解决问题，说清方向。（2）会画旋转后的图形"
        for lid, stem in ((math_id, "阅读条件\n\n写出旋转过程"), (chin_id, "文章\n\n说说你的理解")):
            db.execute(written_t.insert().values(school_id=school_id, lesson_id=lid, session_id=0, teacher_id=tid, stem=stem,
                                                 reference="r", hints_json=json.dumps({"approved": True, "type": "short_answer", "hints": []})))
        db.commit()
    lw = client.get(f"/teacher/weekend/lessons/{math_id}/written/questions", headers=th).json()
    assert lw["goals"] == ["会用旋转解决问题", "会画旋转后的图形"]
    tpl = next(q for q in lw["items"] if q["stem"] == "阅读条件\n\n写出旋转过程")
    assert tpl["suggestedKnowledge"] == "" and tpl["approved"] is True
    # Before marking: the written question has no 考点 and the summary offers to mark it.
    s0 = client.get(f"/teacher/weekend/sessions/{m}/summary", headers=th).json()
    assert s0["lessonId"] == math_id and s0["goals"] == lw["goals"]
    assert s0["marks"] == [{"no": 3, "templateId": tpl["id"], "knowledge": "", "afterClass": False, "suggestedKnowledge": ""}]
    # Mark once on the lesson template: approval stays, every class of the lesson gets it.
    r = client.put(f"/teacher/weekend/lessons/{math_id}/written/questions/{tpl['id']}/marks", headers=th, json={"knowledge": "旋转的方向"})
    assert r.status_code == 200 and r.json() == {"id": tpl["id"], "knowledge": "旋转的方向", "afterClass": False}
    assert client.put(f"/teacher/weekend/lessons/{math_id}/written/questions/{tpl['id']}/marks", headers=a_h, json={"knowledge": "x"}).status_code == 403
    again = next(q for q in client.get(f"/teacher/weekend/lessons/{math_id}/written/questions", headers=th).json()["items"] if q["id"] == tpl["id"])
    assert again["approved"] is True and again["knowledge"] == "旋转的方向"
    s1 = client.get(f"/teacher/weekend/sessions/{m}/summary", headers=th).json()
    assert any(k["knowledge"] == "旋转的方向" for k in s1["summary"]["knowledge"]) and s1["marks"][0]["knowledge"] == "旋转的方向"
    a1 = next(p for p in s1["students"] if p["studentId"] == a_id)
    assert next(i for i in a1["items"] if i["kind"] == "written")["knowledge"] == "旋转的方向"

    # 课后题: a question nobody in class had to hand in is outside the denominator until it is handed in.
    ctpl = next(q for q in client.get(f"/teacher/weekend/lessons/{chin_id}/written/questions", headers=th).json()["items"] if q["stem"].endswith("说说你的理解"))
    client.put(f"/teacher/weekend/lessons/{chin_id}/written/questions/{ctpl['id']}/marks", headers=th, json={"knowledge": "", "afterClass": True})
    sc = client.get(f"/teacher/weekend/sessions/{ch}/summary", headers=th).json()
    ac = next(p for p in sc["students"] if p["studentId"] == a_id)["counts"]
    assert ac["later"] == 1 and ac["unsubmitted"] == 0 and ac["total"] == 2 and ac["submitted"] == 2
    cc = next(p for p in sc["students"] if p["studentId"] == c_id)["counts"]
    assert cc["later"] == 0 and cc["total"] == 3                                    # 丙 handed it in: it counts for him

    # 晚托: 甲 asked the AI about this point and has not consolidated it yet.
    hk = legacy.Base.metadata.tables["homework_ai_knowledge"]
    with legacy.SessionLocal() as db:
        db.execute(hk.insert().values(school_id=school_id, student_id=a_id, help_id=99001, grade=5, subject="数学", knowledge_key="旋转的方向",
                                      raw_knowledge="旋转的方向", matched=True, question_excerpt="q", verify_status="ok", created_at=datetime.utcnow()))
        db.commit()
    rep = client.post("/teacher/weekend/reports", headers=th, json={"studentId": a_id, "sessionIds": [m]}).json()["report"]
    g = rep["glance"][0]
    assert g["good"] == ["旋转的意义"] and g["weak"] == ["旋转的方向"] and g["compare"] == ""
    hw = rep["draft"]["sections"][0]["homework"]
    assert "晚托写作业时也请 AI 讲过" in hw and hw.splitlines()[-1].startswith("家长配合")
    pub = client.post(f"/teacher/weekend/reports/{rep['id']}/publish", headers=th, json={"revision": rep["draft"]["revision"]})
    assert pub.status_code == 200, pub.text
    briefs = client.get(f"/parent/children/{a_id}/weekend-briefs", headers=pa_h).json()
    shown = next(x for x in briefs["reports"] if x["id"] == rep["id"])
    assert shown["glance"][0]["weak"] == ["旋转的方向"] and "过程不完整" not in json.dumps(shown["glance"], ensure_ascii=False)
    print("OK")
'''


def test_marks_once_after_class_glance_and_after_school_hint(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + reports_test.SETUP + FLOW)


def test_pages_carry_the_new_teacher_and_parent_controls():
    import app  # noqa: F401
    from changying.web.weekend_pages import PLAN_JS, report_page_html, brief_page_html
    from changying.web.weekend_written_pages import WRITTEN_JS

    assert "采用全部考点建议" in PLAN_JS and "function markBox" in PLAN_JS and "/marks'" in PLAN_JS
    assert "全部标为正确" in WRITTEN_JS
    html = report_page_html()
    for text in ("为全班生成草稿", "发布全部草稿", "逐题统计（文字题可在这里标考点）", "一眼看懂", "课后题未交"):
        assert text in html, text
    assert "一眼看懂" in brief_page_html() and "innerHTML" not in html
