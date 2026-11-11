"""Read-only bulk quality scan tests: 23 lesson pages, no production database."""
from changying.services.weekend_courseware_quality import audit_example_pages
from changying.web.weekend_courseware import required_visual_type


def make_item(index, *, approved=True, figure=None, steps=None, answer="x"):
    params = {
        "figure": figure if figure is not None else {"type": "segment"},
        "steps": steps if steps is not None else [
            "先观察图示", "试着比较数量", "独立表示数量关系", "解释你的判断"
        ],
        "answer": answer,
    }
    return {
        "stage": 3, "page": index, "kind": "steps",
        "status": "approved" if approved else "draft",
        "approved": params if approved else None,
        "params": params,
    }


def test_scan_23_pages_in_order_and_never_claim_automatic_acceptance():
    pages = ["例题%d：观察线段并判断数量关系" % i for i in range(1, 24)]
    items = [make_item(i) for i in range(23)]
    report = audit_example_pages(pages, items, required_visual_type)
    assert report["totalPages"] == 23
    assert report["configured"] == 23
    assert report["manualReviewRequired"] == 23
    assert len(report["pages"]) == 23
    assert [p["page"] for p in report["pages"]] == list(range(23))
    assert all(p["status"] == "needs_teacher_review" for p in report["pages"])
    assert all(p["manualReviewRequired"] for p in report["pages"])


def test_missing_mismatched_and_answer_leaking_pages_are_flagged():
    pages = [
        "月历框形辨析：哪一种错误？",
        "第15题 3×3方框圈九个数，九数和2016",
        "图形变化规律",
        "方桌1张可坐8人，2张拼起来可坐12人",
    ]
    items = [
        make_item(0, figure={"type": "table"}, steps=["答案是C", "第二步", "第三步", "第四步"], answer="C"),
        make_item(1, figure={"type": "table"}, approved=False),
        make_item(3, figure={}, steps=["直接给出答案"], answer="12"),
    ]
    report = audit_example_pages(pages, items, required_visual_type)
    assert report["flagged"] >= 3
    assert report["pages"][0]["expectedFigureType"] == "calendar_compare"
    assert any("不匹配" in issue for issue in report["pages"][0]["issues"])
    assert any("答案" in issue for issue in report["pages"][0]["issues"])
    assert report["pages"][1]["status"] == "needs_fix"
    assert report["pages"][2]["status"] == "missing"
    assert any("教学图示" in issue for issue in report["pages"][3]["issues"])


def test_changed_source_is_flagged_without_overwriting_saved_courseware():
    page = "原题：求图形周长"
    item = make_item(0)
    item["pageText"] = "修改前的题目"
    item["approvedPageText"] = "更旧版本的题目"
    original = item.copy()
    report = audit_example_pages([page], [item], required_visual_type)
    assert sum("原题" in issue for issue in report["pages"][0]["issues"]) == 2
    assert item == original


def test_unrecognised_types_are_not_certified_as_correct():
    item = make_item(0)
    report = audit_example_pages(["一个尚无专用规则的新题型"], [item], required_visual_type)
    assert report["pages"][0]["status"] == "needs_teacher_review"
    assert "保留现有课件" in "".join(report["pages"][0]["warnings"])


def test_legacy_text_table_leaks_answer_even_if_steps_are_guiding():
    item = make_item(
        0,
        figure={"type": "table", "rows": [
            ["选项", "日期关系", "判断"],
            ["A", "横差1", "正确"], ["C", "竖差10", "错误"],
        ]},
    )
    report = audit_example_pages(["月历框形辨析：哪一种错误？"], [item], required_visual_type)
    assert any("直接判断结论" in issue for issue in report["pages"][0]["issues"])


def test_first_step_rule_statement_requires_more_guidance():
    item = make_item(0, steps=[
        "月历同一行相邻两数相差1，同一列相差7。",
        "比较图示", "用x表示", "验证",
    ])
    report = audit_example_pages(["月历规律"], [item], required_visual_type)
    assert any("直接讲出规律" in warning for warning in report["pages"][0]["warnings"])
    item["params"]["steps"][0] = "观察月历：同一行相邻日期差多少？"
    other = audit_example_pages(["月历规律"], [item], required_visual_type)
    assert not any("直接讲出规律" in warning for warning in other["pages"][0]["warnings"])


def test_known_example_repairs_do_not_invent_other_question_answers():
    from changying.web.weekend_courseware import _repair_courseware_visual
    from changying.services import weekend_courseware as cw

    nine = _repair_courseware_visual(
        {"figure": {}, "steps": []},
        "3×3方框圈九个数，九数和为180，中心数是多少？",
    )
    assert "180÷9=20" in nine["steps"][-1]
    assert not any("2016" in line for line in nine["steps"])
    unknown = _repair_courseware_visual(
        {"figure": {}, "steps": []},
        "3×3方框圈九个数，中心数如何表示？",
    )
    assert not any("224" in line for line in unknown["steps"])
    rectangles = _repair_courseware_visual(
        {"figure": {}, "steps": []},
        "正方形边长a，长方形长a宽b，求周长和面积公式",
    )
    assert not any("n=17" in line for line in rectangles["steps"])
    prompt = cw.generation_prompt("数学", {
        "title": "数学", "coreTarget": "表达数学关系", "pageText": "例题",
    })
    assert "首步只提出观察或操作问题" in prompt
    assert "不得把选择题的正确/错误判断表" in prompt


def test_live_view_sync_omits_private_preview_objects():
    from changying.web.weekend_courseware_pages import COURSEWARE_JS
    assert "if(k.charAt(0)!=='_')publicState[k]=view[k]" in COURSEWARE_JS
    assert "json:{view:publicState}" in COURSEWARE_JS


def test_saved_teacher_courseware_is_never_replaced_by_default_diagram():
    from changying.web.weekend_courseware import _repair_courseware_visual
    import copy

    original = {
        "title": "老师已经调试的月历课件",
        "figure": {"type": "table", "rows": [["图形", "关系"], ["教师自定图", "观察"]]},
        "steps": ["观察自己画好的框", "移动框形", "比较日期", "说出结论"],
        "answer": "老师核对后的答案",
        "sourceFigure": {"type": "uploaded_image", "data_url": "test://do-not-modify"},
    }
    saved = copy.deepcopy(original)
    result = _repair_courseware_visual(original, "月历框形辨析：哪一种错误？")
    assert result == saved
    assert original == saved


def test_missing_diagram_repair_preserves_custom_teacher_steps():
    from changying.web.weekend_courseware import _repair_courseware_visual

    original = {"figure": {}, "steps": [
        "请先看原题", "让学生提出猜想", "小组讨论", "学生总结",
    ], "answer": "C"}
    fixed = _repair_courseware_visual(original, "月历框形辨析：哪一种错误？")
    assert fixed["figure"] == {"type": "calendar_compare"}
    assert fixed["steps"] == original["steps"]
    assert original["figure"] == {}


def test_legacy_answer_table_repaired_without_replacing_teacher_custom_steps():
    from changying.web.weekend_courseware import _repair_courseware_visual

    original = {"figure": {"type": "table", "rows": [
        ["框形", "月历关系", "判断"], ["A", "横向差1", "正确"],
        ["C", "竖列差10", "错误"],
    ]}, "steps": ["先让学生观察", "检查两种框", "再讨论分歧", "提出结论"], "answer": "C"}
    fixed = _repair_courseware_visual(original, "月历框形辨析：哪一种错误？")
    assert fixed["figure"]["type"] == "calendar_compare"
    assert fixed["steps"] == original["steps"]


def test_polished_brief_algebra_question_does_not_need_extra_diagram_or_four_steps():
    item = make_item(0, figure={}, steps=[
        "观察数位", "尝试表示", "独立验证",
    ])
    report = audit_example_pages(
        ["十位数字m、个位数字n，写出这个两位数"], [item],
        required_visual_type,
    )
    assert report["pages"][0]["issues"] == []
    assert not any("不足四步" in w for w in report["pages"][0]["warnings"])


def test_specialised_maths_without_figure_is_reported_without_changing_original():
    item = make_item(0, figure={}, steps=[
        "观察方桌边缘", "找座位变化", "尝试写式子", "验算",
    ])
    original = item["params"]["steps"].copy()
    report = audit_example_pages(
        ["方桌1张可坐8人，2张可坐12人"], [item], required_visual_type
    )
    assert report["pages"][0]["issues"]
    assert item["params"]["steps"] == original


def test_missing_diagram_for_example19_does_not_preveal_answer():
    from changying.web.weekend_courseware import required_visual_figure
    figure = required_visual_figure("a＋b² 易错辨析：当a=5，b=3，小明算成5+6")
    assert figure["type"] == "flow"
    assert "结果=14" not in "".join(figure["boxes"])


def test_original_pdf_example20_tiling_orientation_for_missing_diagram_only():
    from changying.web.weekend_courseware import required_visual_figure, _repair_courseware_visual
    source = "由2个大正方形和3个小正方形拼成长方形，大正方形边长m，小正方形边长n，求周长"
    default = required_visual_figure(source)
    assert default["rows"][1] == ["上排", "2个大正方形", "2m"]
    assert default["rows"][2] == ["下排", "3个小正方形", "3n"]
    polished = {"figure": {"type": "shape", "shape": "rectangle", "labels": {"top": "老师原图"}},
                "steps": ["观察", "归纳", "演算", "验证"]}
    assert _repair_courseware_visual(polished, source) == polished


def test_example11_program_diagram_is_optional_fallback_when_missing():
    from changying.web.weekend_courseware import required_visual_figure, _repair_courseware_visual
    source = "计算小程序：程序输入4、9、15，分别输出11、26、44"
    figure = required_visual_figure(source)
    assert figure == {"type": "flow", "boxes": ["输入 a", "×3", "−1", "输出 b"], "branches": []}
    own = {"figure": {"type": "flow", "boxes": ["教师优化的运算框", "学生验证框"], "branches": []},
           "steps": ["自定义观察", "自定义检验"]}
    assert _repair_courseware_visual(own, source) == own


def test_audit_uses_approved_snapshot_not_incomplete_draft():
    approved = {"figure": {"type": "seating_pattern", "sampleCounts": [8, 12, 16]},
                "steps": ["观察拼桌", "比较共用边", "归纳座位", "检验"],
                "answer": "4m+4"}
    item = {"stage": 3, "page": 0, "kind": "steps", "approved": approved,
            "params": {"figure": {}, "steps": ["未完成"], "answer": ""}}
    report = audit_example_pages(
        ["方桌1张可坐8人，2张可坐12人"], [item], required_visual_type
    )
    row = report["pages"][0]
    assert row["issues"] == []
    assert any("新草稿" in warn for warn in row["warnings"])
    assert row["figureType"] == "seating_pattern"


def test_teacher_save_and_approve_do_not_force_the_generic_diagram_type():
    from changying.web.weekend_courseware import install_weekend_courseware
    import inspect
    source = inspect.getsource(install_weekend_courseware)
    # Only an actually absent diagram receives a fallback, not a hand-tuned
    # figure of another type that has already passed schema validation.
    assert 'fallback_figure and not (params.get("figure") or {}).get("type")' in source
    assert 'required_figure and not saved_figure.get("type")' in source
    assert "月历判断表直接显示了正确/错误" in source
