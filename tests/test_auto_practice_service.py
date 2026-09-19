from types import SimpleNamespace

from changying.services.auto_practice import question_catalog, select_auto_practice_questions


def q(qid, knowledge, *, grade=5, subject="数学", options=None, correct=0):
    return SimpleNamespace(
        id=qid,
        grade=grade,
        subject=subject,
        knowledge=knowledge,
        unit="测试单元",
        options_json=__import__("json").dumps(options or ["A", "B"]),
        correct_index=correct,
    )


def test_comprehensive_selection_spreads_across_knowledge_modules():
    rows = [
        q(1, "模块A"),
        q(2, "模块A"),
        q(3, "模块B"),
        q(4, "模块B"),
        q(5, "模块C"),
    ]
    selected = select_auto_practice_questions(
        rows, mode="comprehensive", count=4
    )
    assert [x.id for x in selected] == [1, 3, 5, 2]
    assert len({x.knowledge for x in selected[:3]}) == 3


def test_knowledge_selection_is_exact_and_excludes_invalid_online_questions():
    rows = [
        q(1, "分数"),
        q(2, "分数"),
        q(3, "小数"),
        q(4, "分数", options=["only"], correct=0),
    ]
    selected = select_auto_practice_questions(
        rows, mode="knowledge", knowledge="分数", count=10
    )
    assert [x.id for x in selected] == [1, 2]


def test_catalog_reports_grade_subject_and_module_counts():
    rows = [
        q(1, "分数"),
        q(2, "分数"),
        q(3, "小数"),
        q(4, "单词", subject="英语"),
    ]
    catalog = question_catalog(rows)
    math = next(x for x in catalog if x["subject"] == "数学")
    assert math["grade"] == 5
    assert math["questionCount"] == 3
    assert math["modules"] == [
        {"name": "分数", "questionCount": 2},
        {"name": "小数", "questionCount": 1},
    ]
