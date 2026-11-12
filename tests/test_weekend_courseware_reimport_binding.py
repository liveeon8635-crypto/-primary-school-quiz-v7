"""Regression: revised student/teacher lesson headings and safe courseware re-import."""
from __future__ import annotations

import json

from changying.services.weekend_presentation import lesson_deck, literal_numbered_questions
from changying.services.weekend_courseware_binding import rebind_unchanged_pages


def reviewed_source(n=23):
    parts = ["数学第11次课", "原题对应表"]
    parts += [f"第{i}题\n原课时对应{i}" for i in range(1, n + 1)]
    parts.append("第一部分 诊断与面积概念")
    for i in range(1, n + 1):
        parts.extend([
            f"第{i}题  [基础]  4分  ·  作图·面积",
            f"第{i}题的学生任务：画出底高，解释面积为何不变。",
            "【参考答案】不允许上大屏",
            "【解析与错因】教师解释不允许上大屏",
            "【分步赋分】2分操作、2分表达",
            "【教师专用：结果图】",
        ])
    parts.extend(["课堂小结与板书", "第1题", "教师备注"])
    return "\n".join(parts)


def test_revised_lesson_keeps_all_twenty_three_pages_and_strips_answers():
    source = reviewed_source()
    pages = literal_numbered_questions(source)
    assert len(pages) == 23
    assert [int(page.split("题", 1)[0].replace("第", "")) for page in pages] == list(range(1, 24))
    assert all("学生任务" in page for page in pages)
    assert all("参考答案" not in page and "解析与错因" not in page
               and "分步赋分" not in page and "教师专用" not in page for page in pages)
    result = lesson_deck({"reading_plan": source, "examples_json": json.dumps(["旧AI例题"])}, 3)
    assert len(result) == 23


def test_identical_reimport_preserves_approval_but_changed_page_is_invalidated():
    old = ["第1题\n画高", "第2题\n求面积", "第3题\n画图"]
    items = [
        {"stage": 3, "page": i, "pageText": value, "approvedPageText": value,
         "approved": {"answer": i}, "status": "approved", "writtenTask": False}
        for i, value in enumerate(old)
    ]
    assert len(rebind_unchanged_pages(items, {3: old}, {3: old})) == 3
    current = ["第1题\n画高", "第2题\n求面积（数据已改）", "第3题\n画图"]
    kept = rebind_unchanged_pages(items, {3: old}, {3: current})
    assert [item["page"] for item in kept] == [0, 2]
    assert all(item["approved"] is not None for item in kept)


def test_reordered_pages_rebind_by_unique_text_not_position():
    old = ["第一题", "第二题"]
    items = [{"stage": 3, "page": 0, "pageText": "第一题", "approvedPageText": "第一题",
              "approved": {"safe": True}, "writtenTask": False}]
    kept = rebind_unchanged_pages(items, {3: old}, {3: old[::-1]})
    assert len(kept) == 1 and kept[0]["page"] == 1
    # A written task has a stage:page ID; never silently move its binding.
    items[0]["writtenTask"] = True
    assert rebind_unchanged_pages(items, {3: old}, {3: old[::-1]}) == []


def test_duplicate_or_stale_source_never_reuses_prior_approval():
    old = ["同题", "同题"]
    item = {"stage": 3, "page": 0, "pageText": "同题",
            "approvedPageText": "同题", "approved": {"answer": 1}}
    assert rebind_unchanged_pages([item], {3: old}, {3: old}) == []
    item["pageText"] = "旧题"
    assert rebind_unchanged_pages([item], {3: ["同题"]}, {3: ["同题"]}) == []
