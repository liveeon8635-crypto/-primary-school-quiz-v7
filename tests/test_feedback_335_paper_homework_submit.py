"""Regression test for feedback #335: 组卷作业提交不了作业.

Teacher 钟老师 reported on /classic?legacy=1&unified=1&page=papers that the
组卷作业 (paper/homework) could not be submitted. The product assistant must
expose a guidance card that explains the required preconditions (saved paper,
selected class/course, at least one question) so the teacher can recover.
"""

from changying.web import v1_product_assistant as assistant


def test_homework_submit_guidance_card_present():
    keys = [card["key"] for card in assistant._GUIDANCE_CARDS]
    assert "homework_submit" in keys


def test_homework_submit_card_points_to_papers_page():
    card = next(c for c in assistant._GUIDANCE_CARDS if c["key"] == "homework_submit")
    assert card["path"] == "/v1/tool?page=papers"
    assert "提交不了作业" in card["keywords"]
    assert "组卷作业提交" in card["keywords"]


def test_homework_submit_card_explains_preconditions():
    card = next(c for c in assistant._GUIDANCE_CARDS if c["key"] == "homework_submit")
    desc = card["description"]
    assert "班级" in desc
    assert "试卷" in desc
