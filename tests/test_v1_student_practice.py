from types import SimpleNamespace

from changying.web.v1 import v1_html
from changying.web.v1_student_practice import (
    V1_STUDENT_PRACTICE_MARKER,
    patch_v1_student_practice_html,
    select_student_practice_questions,
)


def q(
    qid,
    knowledge,
    unit="第一单元",
    *,
    options=None,
    correct_index=0,
    textbook="人教版",
):
    return SimpleNamespace(
        id=qid,
        knowledge=knowledge,
        unit=unit,
        textbook=textbook,
        options_json=__import__("json").dumps(options or ["A", "B"], ensure_ascii=False),
        correct_index=correct_index,
    )


def test_comprehensive_selector_balances_knowledge_modules():
    rows = [
        q(1, "A"),
        q(2, "A"),
        q(3, "B"),
        q(4, "B"),
        q(5, "C"),
    ]

    chosen = select_student_practice_questions(
        rows,
        kind="comprehensive",
        count=4,
    )

    assert [row.id for row in chosen] == [1, 3, 5, 2]


def test_module_selector_keeps_exact_knowledge_and_skips_invalid_online_questions():
    rows = [
        q(1, "分数加法"),
        q(2, "分数加法", options=["only"], correct_index=0),
        q(3, "分数减法"),
        q(4, "分数加法"),
    ]

    chosen = select_student_practice_questions(
        rows,
        kind="module",
        knowledge="分数加法",
        count=10,
    )

    assert [row.id for row in chosen] == [1, 4]


def test_student_practice_patch_is_idempotent_and_exposes_both_modes():
    once = patch_v1_student_practice_html(v1_html())
    twice = patch_v1_student_practice_html(once)

    assert once == twice
    assert V1_STUDENT_PRACTICE_MARKER in once
    assert "＋ 添加测试 / 练习" in once
    assert "该科目综合测试" in once
    assert "知识模块练习" in once
    assert "教材版本" in once
    assert "cy-p-textbook" in once
    assert "selectedTextbook" in once
    assert "textbook:body.querySelector('#cy-p-textbook').value" in once
    assert "/teacher/students/'+student.id+'/auto-practice" in once
    assert "s.role!=='teacher'" in once


def test_runtime_registers_student_practice_routes():
    from app import app

    routes = {(route.path, tuple(sorted(route.methods or []))) for route in app.routes}
    assert (
        "/teacher/students/{sid}/practice-options",
        ("GET",),
    ) in routes
    assert (
        "/teacher/students/{sid}/auto-practice",
        ("POST",),
    ) in routes


def test_selector_never_mixes_textbook_versions():
    rows = [
        q(1, "小数乘法", textbook="人教版"),
        q(2, "小数乘法", textbook="北师大版"),
        q(3, "位置", textbook="人教版"),
        q(4, "位置", textbook="北师大版"),
    ]

    chosen = select_student_practice_questions(
        rows,
        kind="comprehensive",
        count=10,
        textbook="北师大版",
    )

    assert {row.id for row in chosen} == {2, 4}
    assert {row.textbook for row in chosen} == {"北师大版"}
