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
        "线段中点问题",
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
    assert "人工确认" in "".join(report["pages"][0]["warnings"])
