"""Regression: the imported main question number must not be confused with its subpart."""
from __future__ import annotations

from changying.services.lesson_written import lesson_question_number, numbered_student_stem


SOURCE = (
    "第 1 题　2 分\n"
    "（1）观察下面平行四边形变成长方形的过程，填一填。\n"
    "（2）下面的方法中，也能推导出平行四边形面积公式的有（ ）。\n"
    "第 2 题　2 分\n"
    "画出斜边作为底边时对应的高，并标出垂足。\n"
    "第 4 题　2 分\n"
    "哪项场地面积最接近1公顷？\n"
)


def test_numbered_subparts_share_main_number_but_remain_independent():
    first = "（1）观察下面平行四边形变成长方形的过程，填一填。"
    second = "（2）下面的方法中，也能推导出平行四边形面积公式的有（ ）。"
    a, b = lesson_question_number(SOURCE, first), lesson_question_number(SOURCE, second)
    assert (a["originalNumber"], a["partNumber"]) == (1, 1)
    assert (b["originalNumber"], b["partNumber"]) == (1, 2)
    assert a["sourcePosition"] < b["sourcePosition"]
    assert numbered_student_stem(SOURCE, first).startswith("第1题（1）　观察")
    assert numbered_student_stem(SOURCE, second).startswith("第1题（2）　下面")
    # The stored stems, approvals, IDs and point records are never modified.
    assert first.startswith("（1）") and second.startswith("（2）")


def test_explicit_main_number_and_choice_stay_at_original_number():
    q = "第4题 2分｜哪项场地面积最接近1公顷？"
    m = lesson_question_number(SOURCE, q)
    assert (m["originalNumber"], m["partNumber"]) == (4, None)
    assert numbered_student_stem(SOURCE, q) == q


def test_unknown_or_ambiguous_does_not_invent_main_number():
    text = "面积单位的练习应该先读懂题意，找出条件，再选择单位。"
    assert lesson_question_number("", text)["originalNumber"] is None
    repeated = "第1题\n" + text + "\n第2题\n" + text
    assert lesson_question_number(repeated, text)["originalNumber"] is None
    assert numbered_student_stem(repeated, text) == text


def test_reading_material_stays_in_student_question_and_no_answer_is_added():
    material = "阅读材料一\n文字介绍\n\n"
    stem = material + "（2）下面的方法中，也能推导出平行四边形面积公式的有（ ）。"
    marked = numbered_student_stem(SOURCE, stem)
    assert marked.startswith(material + "第1题（2）　下面")
    assert "答案：" not in marked
