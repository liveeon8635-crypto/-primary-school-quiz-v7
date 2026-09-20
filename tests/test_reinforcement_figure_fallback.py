from types import SimpleNamespace

from changying.web.reinforcement_quality import (
    infer_reinforcement_figure,
    install_reinforcement_figure_fallback,
)


def test_infers_composite_geometry_for_obvious_area_problem():
    item = {
        "subject": "数学",
        "knowledge": "组合图形的面积",
        "text": "一个长12米、宽8米的大长方形剪去一个长5米、宽3米的小长方形（如图），求剩余面积。",
        "figure": {},
    }
    figure = infer_reinforcement_figure(item)
    assert figure["type"] == "geometry"
    assert figure["shape"] == "nested_rect"
    assert figure["labels"]["外长"] == "12米"
    assert figure["labels"]["内长"] == "5米"
    assert figure["title"] == "组合图形示意图"


def test_infers_line_segment_for_tree_planting_problem():
    item = {
        "subject": "数学",
        "knowledge": "植树问题",
        "text": "一条84米的小路每隔7米栽一棵树，两端都栽。",
        "figure": {},
    }
    figure = infer_reinforcement_figure(item)
    assert figure["type"] == "line_segment"
    assert len(figure["segments"]) == 4
    assert figure["title"] == "植树间隔示意图（不按间隔数量绘制）"
    assert "84÷7" not in figure["title"]


def test_infers_coordinate_grid_for_position_problem():
    item = {
        "subject": "数学",
        "knowledge": "用数对确定位置",
        "text": "在方格图中标出A(3,4)的位置。",
        "figure": {},
    }
    figure = infer_reinforcement_figure(item)
    assert figure["type"] == "coordinate_grid"
    assert figure["points"][0]["x"] == 3.0
    assert figure["points"][0]["y"] == 4.0


def test_existing_valid_figure_is_preserved_and_enriched():
    existing = {"type": "geometry", "shape": "trapezoid"}
    item = {
        "subject": "数学",
        "knowledge": "梯形的面积",
        "text": "一个梯形的上底是5.6厘米，下底是8.4厘米，高是6厘米，求面积。",
        "figure": existing,
    }
    figure = infer_reinforcement_figure(item)
    assert figure["type"] == "geometry"
    assert figure["shape"] == "trapezoid"
    assert figure["labels"]["上底"] == "5.6厘米"
    assert figure["labels"]["下底"] == "8.4厘米"
    assert figure["labels"]["高"] == "6厘米"
    assert "底" not in figure["labels"]


def test_route_patch_adds_missing_figure_and_preserves_answer():
    def original(*args, **kwargs):
        return {
            "items": [
                {
                    "subject": "数学",
                    "knowledge": "植树问题",
                    "text": "一条84米的小路每隔7米栽一棵树，两端都栽。",
                    "answer": "13",
                    "figure": {},
                }
            ]
        }

    route = SimpleNamespace(
        path="/teacher/students/{sid}/reinforcement/generate",
        methods={"POST"},
        dependant=SimpleNamespace(call=original),
        endpoint=original,
    )
    app = SimpleNamespace(routes=[route], state=SimpleNamespace())
    implementation = SimpleNamespace(app=app)

    install_reinforcement_figure_fallback(implementation)
    result = route.dependant.call()
    assert result["items"][0]["answer"] == "13"
    assert result["items"][0]["figure"]["type"] == "line_segment"
    assert result["figureFallback"] is True



def test_repairs_incomplete_ai_coordinate_point_from_question_text():
    item = {
        "subject": "数学",
        "knowledge": "用数对确定位置",
        "text": "在方格图中，点A的位置用数对表示是(2,3)。如果点A向右平移4格，求新位置。",
        "figure": {"type": "coordinate_grid", "points": [{"label": "A"}]},
    }
    figure = infer_reinforcement_figure(item)
    assert figure["points"] == [{"label": "A", "x": 2.0, "y": 3.0}]


def test_repairs_existing_tree_figure_to_stem_interval_count():
    item = {
        "subject": "数学",
        "knowledge": "植树问题",
        "text": "在一条长90米的小路一旁栽树，每隔9米栽一棵，两端都栽。",
        "figure": {
            "type": "line_segment",
            "segments": [{"label": "间隔", "ratio": 1} for _ in range(6)],
        },
    }
    figure = infer_reinforcement_figure(item)
    assert len(figure["segments"]) == 4
    assert figure["title"] == "植树间隔示意图（不按间隔数量绘制）"
    assert "90÷9" not in figure["title"]


def test_repairs_nested_rectangle_figure_from_stem_dimensions():
    item = {
        "subject": "数学",
        "knowledge": "组合图形的面积",
        "text": "一个长方形花坛长16米，宽9米，中间修一个长7米、宽4米的长方形水池，其余部分种花。",
        "figure": {
            "type": "geometry",
            "shape": "rectangle_with_inner_rectangle",
            "labels": {"长": "16米", "宽": "9米"},
        },
    }
    figure = infer_reinforcement_figure(item)
    assert figure["shape"] == "nested_rect"
    assert figure["labels"] == {
        "外长": "16米",
        "外宽": "9米",
        "内长": "7米",
        "内宽": "4米",
    }
