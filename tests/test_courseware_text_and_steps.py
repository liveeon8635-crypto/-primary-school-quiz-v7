"""服务层：文本转义还原、步骤清洁、钝角三角形画高校验。"""
from __future__ import annotations

import pytest

from changying.services import weekend_courseware as cw


def test_text_restores_literal_unicode_escapes():
    # 模型把“白砖”写成了字面量 \u767d\u7816，要还原成真正的中文。
    assert cw._text(r"\u767d\u7816", 20) == "白砖"
    assert cw._text(r"白砖", 20) == "白砖"


def test_text_restores_double_escaped_unicode_without_breaking_chinese():
    # 双重转义：文本里是两个反斜杠加 u84dd。
    assert cw._text(r"\\u84dd", 20) == "蓝"
    assert cw._text("钝角三角形的高", 20) == "钝角三角形的高"


def test_text_still_cleans_control_characters_and_truncates():
    assert cw._text("\x00 蓝\x1b ", 20) == "蓝"
    assert cw._text("钝角三角形", 2) == "钝角"


@pytest.mark.parametrize(
    "steps",
    [
        ["第1步……", "第2步……"],
        ["第1步", "第2步"],
        ["观察题目（第1步，点下一步显示）", "第2步，点下一步显示"],
    ],
)
def test_clean_steps_rejects_placeholder_steps(steps):
    with pytest.raises(ValueError, match="真实的讲解步骤"):
        cw.clean_steps({"steps": steps, "answer": "7.5"})


def test_clean_steps_accepts_four_real_steps_and_removes_template_tail():
    params = cw.clean_steps({
        "title": "钝角三角形画高",
        "steps": [
            "先观察底边和斜边的位置。",
            "把底边向右延长（第2步，点下一步显示）",
            "从顶点向延长线画垂线，标出垂足。",
            "用高和底边算出面积，再检验结果。",
        ],
        "answer": "面积是 26.25 平方厘米。",
        "figure": {},
    })
    assert len(params["steps"]) == 4
    assert params["steps"][1] == "把底边向右延长"
    assert all("点下一步显示" not in step for step in params["steps"])


def test_clean_steps_keeps_numbered_steps_that_have_real_content():
    params = cw.clean_steps({
        "steps": [
            "第1步：在3×3方框中定位中心数a。",
            "第2步：同一行相邻两数差1。",
            "第3步：同一列相邻两数差10。",
            "第4步：把九个数相加，检验结果。",
        ],
        "answer": "9a",
        "figure": {},
    })
    assert len(params["steps"]) == 4
    assert params["steps"][0] == "第1步：在3×3方框中定位中心数a。"


def test_obtuse_triangle_height_requires_four_steps():
    with pytest.raises(ValueError, match="至少 4 步"):
        cw.clean_steps({
            "steps": ["先看底边。", "再画高。"],
            "answer": "26.25",
            "figure": {"type": "obtuse_triangle_height", "base": 7, "side": 15, "height": 7.5},
        })


def test_clean_figure_accepts_obtuse_triangle_height():
    figure = cw.clean_figure({"type": "obtuse_triangle_height", "base": 7, "side": 15, "height": 7.5})
    assert figure == {"type": "obtuse_triangle_height", "base": 7.0, "side": 15.0, "height": 7.5, "unit": "cm"}
    assert cw.clean_figure({"type": "obtuse_triangle_height", "base": 7, "side": 15,
                            "height": 7.5, "unit": "厘米"})["unit"] == "厘米"


@pytest.mark.parametrize(
    "raw",
    [
        {"type": "obtuse_triangle_height", "base": 7, "side": 3.5, "height": 7.5},
        {"type": "obtuse_triangle_height", "base": -7, "side": 15, "height": 7.5},
        {"type": "obtuse_triangle_height", "base": "7", "side": 15, "height": 7.5},
        {"type": "obtuse_triangle_height", "base": 7, "side": 15, "height": 101},
        {"type": "obtuse_triangle_height", "base": 7, "side": 15, "height": 7.5, "unit": "米"},
    ],
)
def test_clean_figure_rejects_bad_obtuse_triangle_values(raw):
    with pytest.raises(ValueError):
        cw.clean_figure(raw)


def test_clean_view_truncates_step_to_the_number_of_real_steps():
    params = cw.clean_steps({
        "steps": ["先观察哪些条件？", "怎样比较/操作？", "怎样表示规律？", "怎样检验结果？"],
        "answer": "7.5",
        "figure": {},
    })
    assert cw.clean_view("steps", params, {"step": 99})["step"] == len(params["steps"]) == 4
