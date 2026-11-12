"""The teacher's original-question correspondence table must not hide the worked examples."""

from __future__ import annotations

import json

from changying.services.weekend_presentation import lesson_deck, literal_numbered_questions


def test_twenty_three_real_questions_override_four_ai_examples_without_reimport():
    # DOCX table extraction turns cells into independent paragraphs.  Each of
    # the 23 source-table entries repeats the real question number.
    table = "原题对应表\n题号\n原练习页码·题号\n" + "\n".join(
        f"第{i}题\n第 1 课时·{i}(1)" for i in range(1, 24)
    )
    chapters = ["第一部分 诊断与面积概念", "第二部分 平行四边形面积探究与应用",
                "第三部分 公顷和平方千米", "第四部分 三角形面积推导与应用",
                "第五部分 转化方法与当堂检测"]
    parts = []
    for i in range(1, 24):
        if i in (1, 5, 11, 15, 21):
            parts.append(chapters[(1, 5, 11, 15, 21).index(i)])
        parts.append(
            f"第{i}题    {'2' if i < 5 else '4'}分\n"
            f"操作｜考点{i}\n"
            f"（1）原教材第{i}道操作题。画图并说明为什么面积保持不变。\n"
            f"考点提醒：对应底高。\n答案：{i}。\n解析：这是教师专用的解答。"
        )
    source = table + "\n" + "\n".join(parts) + "\n课堂小结与板书\n第1题\n自检材料"
    originals = literal_numbered_questions(source)
    assert len(originals) == 23
    assert "原教材第1道操作题" in originals[0]
    assert "原教材第23道操作题" in originals[-1]
    assert not any("答案：" in page or "解析：" in page or "原练习页码" in page for page in originals)

    lesson = {"reading_plan": source, "examples_json": json.dumps(["AI例题"+str(i) for i in range(4)])}
    pages = lesson_deck(lesson, 3)
    assert len(pages) == 23
    assert all("AI例题" not in page for page in pages)


def test_repeated_unnumbered_sources_still_fail_closed():
    source = ("第1题\n第一问\n第2题\n第二问\n"
              "第1题\n重复内容\n第2题\n另一处重复")
    assert literal_numbered_questions(source) == []


def test_normal_numbered_source_retains_existing_behavior():
    source = ("第1题 2分\n计算：1＋1＝？\n考点提醒：加法\n答案：2\n"
              "第2题 3分\n计算：2＋2＝？\n答案：4")
    pages = literal_numbered_questions(source)
    assert len(pages) == 2
    assert "1＋1" in pages[0] and "2＋2" in pages[1]


def test_revised_23_question_student_layout_does_not_fall_back_to_one_ai_page():
    # The final handout puts difficulty, points and task type on the same line
    # as the numbered heading. The old strict regex recognized none of them.
    levels = ("基础", "进阶", "提升")
    source = "数学·第11次课\n一、诊断与面积概念\n" + "\n".join(
        f"第{i}题  [{levels[i % 3]}]  4分  ·  操作·面积\n"
        f"学生独立完成第{i}题，在原图画对应的底和高。\n"
        "作答：___________________"
        for i in range(1, 24)
    ) + "\n作答检查\n课后总结不是第23题题干"
    pages = lesson_deck({
        "reading_plan": source,
        "examples_json": json.dumps(["旧版唯一例题"], ensure_ascii=False),
    }, 3)
    assert len(pages) == 23
    assert all(f"第{i}题" in pages[i-1] for i in range(1, 24))
    assert all("旧版唯一例题" not in p and "作答检查" not in p for p in pages)


def test_revised_teacher_copy_never_puts_answers_or_reveal_in_exercise_deck():
    levels = ("基础", "进阶", "提升")
    source = "数学第11次课\n一、诊断与面积概念\n" + "\n".join(
        f"第{i}题  【{levels[i % 3]}】  4分  ·  画高\n"
        f"求第{i}题的面积，并说明理由。\n"
        f"【参考答案】第{i}题答案为{i}平方厘米。\n"
        "【解析与错因】教师单独讲解。\n"
        "【分步赋分】每步1分。\n"
        "【课件分镜】教师提交后揭示正确图。"
        for i in range(1, 24)
    ) + "\n附录A｜教师专用评分清单"
    pages = literal_numbered_questions(source)
    assert len(pages) == 23
    assert all("【" not in page or "【基础】" in page or "【进阶】" in page or "【提升】" in page for page in pages)
    assert all("【参考答案】" not in page and "【解析与错因】" not in page
               and "【课件分镜】" not in page and "附录A" not in page for page in pages)


def test_revised_source_table_followed_by_chinese_sections_is_not_duplicated():
    table = "原题对应表\n" + "\n".join(f"第{i}题\n第1课时·{i}" for i in range(1, 24))
    exercises = "一、诊断与面积概念\n" + "\n".join(
        f"第{i}题  [基础]  2分  ·  填空\n已知第{i}题的底和高，求面积。\n作答：____"
        for i in range(1, 24)
    )
    pages = literal_numbered_questions(table + "\n" + exercises)
    assert len(pages) == 23
    assert "原题对应表" not in "".join(pages)
    assert all("已知" in page for page in pages)


def test_failed_source_extraction_is_detected_before_generating_wrong_one_page():
    from types import SimpleNamespace
    from changying.web.weekend_courseware import source_page_mismatch

    # A future template variation may not yet be recognized by the parser.
    # Count the numbered source headings independently and fail visibly.
    source = "\n".join(
        f"第{i}题：题干在标题同行，需修订适配\n继续画图"
        for i in range(1, 24)
    )
    lesson = SimpleNamespace(subject="数学", reading_plan=source,
                             examples_json=json.dumps(["一页旧版AI摘要"]), ppt_json="[]")
    assert source_page_mismatch(lesson) == (23, True)
    assert len(lesson_deck({"reading_plan": source, "examples_json": lesson.examples_json}, 3)) == 1


def test_long_numbered_question_stays_one_slot_for_figure_and_review_binding():
    source = "\n".join(
        f"第{i}题  [提升]  8分  ·  推导\n"
        + ("说明割补前后面积为什么保持不变，独立画图并标出底和高。" * 18)
        for i in range(1, 24)
    )
    pages = lesson_deck({"reading_plan": source, "examples_json": "[]"}, 3)
    assert len(pages) == 23
    assert all(page.startswith(f"第{i}题") for i, page in enumerate(pages, 1))
    assert all(len(page) > 360 for page in pages)

