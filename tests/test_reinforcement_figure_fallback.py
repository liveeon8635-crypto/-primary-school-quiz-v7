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
    assert figure["shape"] == "composite_rect"
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
    assert len(figure["segments"]) >= 2


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


def test_existing_valid_figure_is_preserved():
    existing = {"type": "geometry", "shape": "triangle"}
    item = {"subject": "数学", "knowledge": "三角形的面积", "text": "求面积", "figure": existing}
    assert infer_reinforcement_figure(item) is existing


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
