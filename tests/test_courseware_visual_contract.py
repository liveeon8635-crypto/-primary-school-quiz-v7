from __future__ import annotations

from changying.services import weekend_courseware as cw
from changying.web.weekend_courseware import (
    _repair_courseware_visual,
    figure_semantic_issue,
    missing_visual_reason,
    required_visual_figure,
    required_visual_type,
)

OBTUSE = "钝角三角形底边7cm，斜边15cm，高7.5cm，请画出底边上的高并求面积。"


def obtuse_figure(base=7.0, side=15.0, height=7.5):
    return {"type": "obtuse_triangle_height", "base": base, "side": side, "height": height, "unit": "cm"}


def test_obtuse_question_needs_height_figure():
    assert required_visual_type(OBTUSE) == "obtuse_triangle_height"
    # “作高”“高线”“延长线”也都要认出来
    assert required_visual_type("钝角三角形ABC，请作高。") == "obtuse_triangle_height"
    assert required_visual_type("钝角三角形画高线，底边要延长线。") == "obtuse_triangle_height"


def test_obtuse_figure_reads_base_side_height():
    figure = required_visual_figure(OBTUSE)
    assert figure == {"type": "obtuse_triangle_height", "base": 7.0, "side": 15.0, "height": 7.5, "unit": "cm"}
    # 三个数都是浮点数，单位统一为厘米
    assert all(isinstance(figure[key], float) for key in ("base", "side", "height"))
    assert cw.clean_figure(figure) == figure


def test_obtuse_figure_uses_defaults_when_numbers_are_missing():
    figure = required_visual_figure("钝角三角形，请画出底边上的高。")
    assert figure == {"type": "obtuse_triangle_height", "base": 7.0, "side": 15.0, "height": 7.5, "unit": "cm"}


def test_seating_people_mismatch_is_reported():
    page = "1张方桌可坐8人，2张方桌可坐10人，3张方桌可坐12人。"
    figure = required_visual_figure(page)
    issue = figure_semantic_issue(figure, page)
    assert issue, "题干人数不是每档多4人，必须提示待确认"
    assert "4" in issue


def test_seating_round_table_is_reported():
    page = "圆桌旁坐人，1张圆桌坐8人，2张圆桌坐12人，3张圆桌坐16人。"
    issue = figure_semantic_issue({"type": "seating_pattern", "sampleCounts": [8, 12, 16]}, page)
    assert issue
    assert "圆桌" in issue


def test_tile_counts_mismatch_is_reported():
    page = "地砖排列：第1幅5块白地砖4块蓝地砖，第2幅8块白地砖7块蓝地砖。"
    figure = {"type": "tile_pattern", "whiteCounts": [5, 9], "blueCounts": [4, 7]}
    issue = figure_semantic_issue(figure, page)
    assert issue
    assert "白" in issue


def test_running_speed_mismatch_is_reported():
    page = "跑道一圈400米，丽丽每分钟跑180米，丙丙每分钟跑140米，多久再次相遇？"
    figure = {"type": "running_track", "fastSpeed": 200, "slowSpeed": 140, "distanceSymbol": "s"}
    issue = figure_semantic_issue(figure, page)
    assert issue
    assert "速度" in issue


def test_obtuse_figure_numbers_must_match_question():
    issue = figure_semantic_issue(obtuse_figure(base=9.0), OBTUSE)
    assert issue
    assert "底" in issue


def test_consistent_figures_have_no_issue():
    page = "地砖排列：第1幅5块白地砖4块蓝地砖，第2幅8块白地砖7块蓝地砖。"
    figure = required_visual_figure(page)
    assert figure["type"] == "tile_pattern"
    assert figure_semantic_issue(figure, page) == ""
    running = "跑道一圈400米，丽丽每分钟跑180米，丙丙每分钟跑140米，多久超过一圈？"
    assert figure_semantic_issue({"type": "running_track", "fastSpeed": 180, "slowSpeed": 140,
                                  "distanceSymbol": "s"}, running) == ""
    assert figure_semantic_issue(obtuse_figure(), OBTUSE) == ""


def test_missing_figure_reason_only_when_the_page_needs_a_picture():
    assert missing_visual_reason("如下图，求阴影部分的面积。", {}) != ""
    assert missing_visual_reason("如图，数一数一共有几个角。", {"type": "unsupported_unknown"}) != ""
    assert missing_visual_reason("12＋8＝几？", {}) == ""


def test_seating_counts_come_from_the_question():
    page = "1张方桌可坐8人，2张方桌可坐12人，3张方桌可坐16人，4张方桌坐多少人？"
    assert required_visual_figure(page)["sampleCounts"] == [8, 12, 16]
    odd = "1张方桌可坐6人，2张方桌可坐10人，3张方桌可坐14人。"
    figure = required_visual_figure(odd)
    assert figure["sampleCounts"] == [6, 10, 14]
    assert figure_semantic_issue(figure, odd) != ""


def test_unreadable_tile_question_does_not_fake_a_figure():
    page = "用白地砖和蓝地砖铺成一个图案，第1幅到第2幅有什么规律？"
    assert required_visual_type(page) == "tile_pattern"
    assert required_visual_figure(page) == {}
    marked = _repair_courseware_visual({"figure": {}, "steps": []}, page)
    assert marked["figureUnverified"] is True
    assert "缺少配图" in marked["figureNotice"]


def test_repair_fills_placeholder_steps_even_when_a_correct_figure_exists():
    repaired = _repair_courseware_visual({"figure": obtuse_figure(), "steps": ["第1步……", "第2步……"]}, OBTUSE)
    assert len(repaired["steps"]) >= 4
    assert all("点下一步显示" not in step for step in repaired["steps"])
    assert repaired["figure"] == obtuse_figure()
    assert "figureUnverified" not in repaired


def test_repair_marks_a_figure_that_does_not_match_the_question():
    repaired = _repair_courseware_visual({"figure": obtuse_figure(base=9.0), "steps": [], "approved": {"steps": []}}, OBTUSE)
    assert repaired["figureUnverified"] is True
    assert repaired["figureNotice"].startswith("图示待确认：")
    assert "底" in repaired["figureNotice"]


def test_tile_counts_accept_both_word_orders():
    first = "按规律排列白地砖和蓝地砖，白地砖每边依次是5块、8块，蓝地砖每边依次是4块、7块，第n幅各多少块？"
    second = "第1幅用5块白砖和4块蓝砖，第2幅用8块白砖和7块蓝砖，第10幅蓝砖多少块？"
    for page in (first, second):
        figure = required_visual_figure(page)
        assert figure["whiteCounts"] == [5, 8]
        assert figure["blueCounts"] == [4, 7]
        assert figure_semantic_issue(figure, page) == ""


def test_track_speeds_accept_common_phrasings():
    pages = [
        "环形跑道一圈s米，甲每分钟180米，乙每分钟140米，同地同向出发，甲再次追上乙要几分钟？",
        "跑道长s米，小明每分钟跑180米，小红每分钟跑140米，同地同向出发，几分钟后小明多跑一圈？",
        "环形跑道长s米，甲的速度是180米/分，乙的速度是140米/分，同地同向出发，甲追上乙要几分钟？",
    ]
    for page in pages:
        figure = required_visual_figure(page)
        assert figure["fastSpeed"] == 180
        assert figure["slowSpeed"] == 140
        assert figure_semantic_issue(figure, page) == ""


def test_tile_figure_without_counts_is_marked_unverified():
    page = "按规律排列白地砖和蓝地砖，白地砖每边依次是5块、8块，蓝地砖每边依次是4块、7块。"
    issue = figure_semantic_issue({"type": "tile_pattern"}, page)
    assert issue
    repaired = _repair_courseware_visual({"figure": {"type": "tile_pattern"}, "steps": []}, page)
    assert repaired["figureUnverified"] is True


REAL_FIVE_STEPS = [
    "先观察：哪条边是 7 cm 的底？高应从哪个顶点向哪条直线作？",
    "比较垂线与底边所在直线的位置，判断垂足会落在底边上还是其延长线上。",
    "过顶点向 7 cm 底边所在直线作垂线，用直角符号标出垂足，并标出 7.5 cm 的高。",
    "面积用底×高÷2，代入 7 和 7.5，注意高要与 7 cm 底边对应。",
    "检查垂线是否垂直、垂足位置是否正确，面积单位写成 cm²。",
]


def test_saved_legacy_figure_is_replaced_by_the_standard_one():
    """存量课件里存的是旧的 generic 三角形图，显示时要以标准钝角图画高为准。"""
    params = {"steps": REAL_FIVE_STEPS, "figure": {"type": "shape", "shape": "triangle", "labels": {}}}
    repaired = _repair_courseware_visual(params, OBTUSE)
    assert repaired["figure"]["type"] == "obtuse_triangle_height"
    assert repaired["figure"]["height"] == 7.5
    assert "请老师核对后确认" in (repaired.get("figureNotice") or "")
    assert not repaired.get("figureUnverified")


def test_replaced_scan_is_kept_as_comparison():
    """老师上传过的扫描图被标准图取代时，原图仍然保留在“对照”里。"""
    photo = {"type": "uploaded_image", "data_url": "data:image/png;base64,AAAA", "alt": "原卷插图"}
    repaired = _repair_courseware_visual({"steps": REAL_FIVE_STEPS, "figure": photo}, OBTUSE)
    assert repaired["figure"]["type"] == "obtuse_triangle_height"
    assert repaired["sourceFigure"]["data_url"] == photo["data_url"]


def test_standard_figure_is_not_redrawn_again():
    """已经是标准图时不再重复覆盖，也不再提示重画。"""
    repaired = _repair_courseware_visual({"steps": REAL_FIVE_STEPS, "figure": obtuse_figure()}, OBTUSE)
    assert repaired["figure"]["type"] == "obtuse_triangle_height"
    assert "figureNotice" not in repaired
    assert "figureUnverified" not in repaired


def test_seating_page_with_a_wrong_saved_figure_is_redrawn():
    """方桌题存的是线段图时，改成方桌拼接图，避免“方桌画成线段/圆桌”。"""
    page = "1张方桌可坐8人，2张方桌可坐12人，3张方桌可坐16人。"
    params = {"steps": ["看一张桌子坐几人。", "两张拼起来多了几个座位？", "三张再多数一数。", "写出 4m+4。"],
              "figure": {"type": "segment", "rows": []}}
    repaired = _repair_courseware_visual(params, page)
    assert repaired["figure"]["type"] == "seating_pattern"
    assert repaired["figure"]["sampleCounts"] == [8, 12, 16]
