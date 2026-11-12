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
