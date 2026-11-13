"""例题、随堂练习要各归各位：练习不能把例题原样再出一遍。

老师审核时也要先看见“这道题和例1重复”，不能让他一点“通过”就发给学生。
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
from pathlib import Path

from changying.services import weekend_question_gen as qg
from changying.web import weekend_plan_views as views

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("role_separation_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_same_question_ignores_question_number_and_punctuation():
    assert qg.same_question("第4题 甲乙两地相距120千米……", "4、甲乙两地相距120千米…")
    assert qg.same_question("第4题 甲乙两地相距120千米，一辆车每小时行60千米。", "（4）甲乙两地相距120千米 一辆车每小时行60千米")


def test_same_question_ignores_spacing_full_width_and_option_letters():
    assert qg.same_question("计算 3.5+1.2=?", "计算３．５ ＋ １．２ ＝ ？")
    assert qg.same_question("A. 0.06", "（A）0.06")


def test_same_options_ignores_order_but_not_content():
    assert qg.same_options(["0.06", "0.6", "6", "0.006"], ["6", "0.006", "0.06", "0.6"])
    assert not qg.same_options(["0.06", "0.6", "6", "0.006"], ["0.06", "0.6", "6", "0.6"])
    assert not qg.same_options([], [])


def test_same_question_keeps_different_numbers():
    assert not qg.same_question("甲乙两地相距120千米，一辆车每小时行60千米。", "甲乙两地相距150千米，一辆车每小时行60千米。")
    assert not qg.same_question("2.5×4=？", "2.5×5=？")


def test_same_question_keeps_triangle_vertex_names():
    # 顶点名不是选项标签：两道不同顶点的几何题不能判成同一道。
    assert not qg.same_question("三角形ABC中，AB=7厘米，BC=15厘米，画出BC边上的高。",
                                "三角形DEF中，DE=7厘米，EF=15厘米，画出EF边上的高。")


def test_example_stems_reads_text_and_object_examples():
    raw = json.dumps(["例1：2.5×4=？", {"title": "例2", "stem": "0.5×6=？"},
                      {"title": "例3", "answer": "1/2"}], ensure_ascii=False)
    got = views.example_stems(raw)
    assert [x["label"] for x in got] == ["例1", "例2", "例3"]
    assert got[0]["stem"] == "例1：2.5×4=？" and got[1]["stem"] == "0.5×6=？"
    assert "1/2" in got[2]["stem"]


def test_existing_stems_include_examples_for_minimal_lesson():
    lesson = {"examples_json": json.dumps(["例1：2.5×4=？"], ensure_ascii=False)}
    assert views.merge_example_stems(["已经通过的题"], lesson) == ["已经通过的题", "例1：2.5×4=？"]
    # 生产里的 existing_stems 必须真的调用这个合并函数，不能只在测试里用。
    assert "merge_example_stems(stems, lesson)" in inspect.getsource(views.install_weekend_plan)


def test_review_panel_marks_duplicates_and_disables_approve():
    source = (ROOT / "changying" / "web" / "weekend_pages.py").read_text(encoding="utf-8")
    for needle in ("duplicateOf", "'⚠ 与'+q.duplicateOf+'重复'", "disabled:!!q.duplicateOf", "不能通过（重复）"):
        assert needle in source, needle


FLOW = r'''
import json
from sqlalchemy import select
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    # 用真实导入路由建课，保证 lesson / program 的关系和生产一致。
    md = "# 第17课：例题隔离\n\n## 本节目标\n会算小数乘法。\n\n## 教学流程\n1. 复习\n"
    r = client.post("/teacher/weekend/lessons/import/markdown", headers=th,
                    data={"subject": "数学", "onConflict": "overwrite"},
                    files=[("files", ("第17课.md", md.encode("utf-8"), "text/markdown"))])
    assert r.status_code == 200, r.text
    lid = next(x for x in client.get("/teacher/weekend/schedule?subject=数学", headers=th).json()["items"]
               if x["lessonNo"] == 17)["lessonId"]

    with legacy.SessionLocal() as db:
        lesson = db.get(legacy.TeachingLesson, lid)
        lesson.examples_json = json.dumps(["例1：2.5×4=？"], ensure_ascii=False)
        def q(stem, options, active):
            return legacy.TeachingQuestion(school_id=lesson.school_id, program_id=lesson.program_id, lesson_id=lid,
                stage="lesson", subject="数学", level="C", knowledge="小数乘法", stem=stem,
                options_json=json.dumps(options, ensure_ascii=False), correct_index=0, explanation="", active=active)
        example_dup = q("2.5 × 4 = ？", [], False)
        approved = q("0.3×0.2 的积是多少？", ["0.06", "0.6", "6", "0.006"], True)
        option_dup = q("下面哪道题的结果是 0.06？", ["6", "0.006", "0.06", "0.6"], False)
        clean = q("1.2×5=？", [], False)
        db.add_all([example_dup, approved, option_dup, clean])
        db.commit()
        ids = {"example": example_dup.id, "approved": approved.id, "option": option_dup.id, "clean": clean.id}

    items = client.get(f"/teacher/weekend/lessons/{lid}/questions", headers=th).json()["items"]
    by_id = {x["id"]: x for x in items}
    assert by_id[ids["example"]]["duplicateOf"] == "例1", by_id[ids["example"]]
    assert by_id[ids["option"]]["duplicateOf"] == "本课习题", by_id[ids["option"]]
    assert by_id[ids["clean"]]["duplicateOf"] == "", by_id[ids["clean"]]

    url = f"/teacher/weekend/lessons/{lid}/questions"
    r = client.post(url, headers=th, json={"approve": [ids["example"]]})
    assert r.status_code == 409, r.text
    assert "例1" in r.json()["detail"] and "换一道同考点新题" in r.json()["detail"], r.text
    r = client.post(url, headers=th, json={"approve": [ids["option"]]})
    assert r.status_code == 409, r.text
    assert "重复" in r.json()["detail"] and "换一道同考点新题" in r.json()["detail"], r.text
    assert client.post(url, headers=th, json={"approve": [ids["clean"]]}).status_code == 200
    items = client.get(url, headers=th).json()["items"]
    assert next(x for x in items if x["id"] == ids["clean"])["active"] is True
    assert next(x for x in items if x["id"] == ids["example"])["active"] is False

    html = client.get("/v1/weekend-plan").text
    for t in ("duplicateOf", "不能通过（重复）", "⚠ 与"):
        assert t in html, t
print("OK")
'''


def test_decide_questions_blocks_example_and_practice_duplicates(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {})
