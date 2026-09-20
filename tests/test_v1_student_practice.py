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
    question_type="",
    answer="",
):
    values = ["A", "B"] if options is None else options
    return SimpleNamespace(
        id=qid,
        knowledge=knowledge,
        unit=unit,
        textbook=textbook,
        options_json=__import__("json").dumps(values, ensure_ascii=False),
        correct_index=correct_index,
        question_type=question_type,
        answer_json=__import__("json").dumps(
            {"answer": answer, "accepted": []} if answer else {},
            ensure_ascii=False,
        ),
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


def test_selector_round_robins_supported_question_types():
    rows = [
        q(1, "A"),
        q(2, "B", options=["正确", "错误"], question_type="true_false"),
        q(
            3,
            "C",
            options=[],
            correct_index=-1,
            question_type="fill_blank",
            answer="3.5",
        ),
        q(
            4,
            "D",
            options=[],
            correct_index=-1,
            question_type="calculation",
            answer="12",
        ),
        q(5, "E"),
    ]

    chosen = select_student_practice_questions(
        rows,
        kind="comprehensive",
        count=5,
    )

    assert [row.id for row in chosen[:4]] == [1, 2, 3, 4]
    assert {
        row.question_type or "single_choice"
        for row in chosen
    } >= {"single_choice", "true_false", "fill_blank", "calculation"}


def test_selector_skips_text_questions_without_server_answer_metadata():
    rows = [
        q(
            1,
            "A",
            options=[],
            correct_index=-1,
            question_type="fill_blank",
            answer="",
        ),
        q(2, "A"),
    ]

    chosen = select_student_practice_questions(
        rows,
        kind="module",
        knowledge="A",
        count=10,
    )

    assert [row.id for row in chosen] == [2]


def test_student_practice_patch_is_idempotent_and_exposes_both_modes():
    once = patch_v1_student_practice_html(v1_html())
    twice = patch_v1_student_practice_html(once)

    assert once == twice
    assert V1_STUDENT_PRACTICE_MARKER in once
    assert "＋ 添加测试 / 练习" in once
    assert "AI 针对性练习" in once
    assert "/teacher/students/'+sid+'/reinforcement/generate" in once
    assert "/teacher/students/'+sid+'/reinforcement/assign" in once
    assert "assessmentContext" in once
    assert "该科目综合测试" in once
    assert "知识模块练习" in once
    assert "人教版（当前最新版）" in once
    assert "当前核定教材题库" in once
    assert "主动混排可自动判分的单选、判断、填空、计算等题型" in once
    assert "语文使用统编版（人民教育出版社）" in once
    assert "cy-p-textbook" in once
    assert "selectedTextbook" in once
    assert "textbook:body.querySelector('#cy-p-textbook').value" in once
    assert "/teacher/students/'+student.id+'/auto-practice" in once
    assert "s.role!=='teacher'" in once
    assert "状态：未布置 · 当前仅为教师审核预览，学生端不会看到。" in once
    assert "审核无误，布置给该学生" in once
    assert "状态：已布置 · AI 针对性练习已在学生端可见。" in once
    assert "cy-ai-assign-box" in once
    assert "bottom:calc(8px + env(safe-area-inset-bottom))" in once
    assert ".toISOString().slice(0,10)" not in once
    assert "if(btn.disabled)return" in once
    assert "已添加成功" in once
    assert "请勿重复添加" in once
    assert "scrollIntoView" in once


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



def test_teacher_ai_preview_places_nested_rectangle_dimensions_on_edges():
    html = patch_v1_student_practice_html(v1_html())

    assert "外长 '+esc(labels['外长'])" in html
    assert "外宽 '+esc(labels['外宽'])" in html
    assert "内长 '+esc(labels['内长'])" in html
    assert "内宽 '+esc(labels['内宽'])" in html



def _materialized_rows_from_specs(specs):
    import json

    rows = []
    for i, spec in enumerate(specs, start=1000):
        rows.append(
            SimpleNamespace(
                id=i,
                knowledge=spec["knowledge"],
                unit=spec["unit"],
                textbook=spec["textbook"],
                options_json=json.dumps(spec.get("options") or [], ensure_ascii=False),
                correct_index=int(spec.get("correct_index", -1)),
                question_type=str(spec.get("question_type") or ""),
                answer_json=json.dumps(spec.get("answer_json") or {}, ensure_ascii=False),
            )
        )
    return rows


def test_current_english_comprehensive_test_is_mixed_type():
    from changying.services.builtin_question_bank import built_in_question_specs

    textbook = "人教版（PEP·当前最新版）"
    rows = _materialized_rows_from_specs(
        built_in_question_specs(5, "英语", textbook)
    )
    chosen = select_student_practice_questions(
        rows,
        kind="comprehensive",
        count=10,
        textbook=textbook,
    )
    types = {_online_type.question_type or "single_choice" for _online_type in chosen}

    assert len(chosen) == 10
    assert {"single_choice", "true_false", "fill_blank"} <= types


def test_current_chinese_comprehensive_test_is_mixed_type():
    from changying.services.builtin_question_bank import built_in_question_specs

    textbook = "统编版（人民教育出版社）"
    rows = _materialized_rows_from_specs(
        built_in_question_specs(5, "语文", textbook)
    )
    chosen = select_student_practice_questions(
        rows,
        kind="comprehensive",
        count=10,
        textbook=textbook,
    )
    types = {_online_type.question_type or "single_choice" for _online_type in chosen}

    assert len(chosen) == 10
    assert {"single_choice", "true_false", "fill_blank"} <= types


def test_auto_practice_server_fallback_uses_school_local_date():
    import inspect
    import changying.web.v1_student_practice as module

    source = inspect.getsource(module.install_v1_student_practice_routes)
    assert "datetime.now(implementation.SCHOOL_TZ)" in source
    assert "datetime.utcnow() + timedelta(days=7)" not in source
