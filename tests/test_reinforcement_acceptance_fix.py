from types import SimpleNamespace

from changying.web.reinforcement_quality import (
    infer_reinforcement_figure,
    install_reinforcement_figure_fallback,
)
from changying.web.v1_reinforcement_acceptance import (
    V1_REINFORCEMENT_FIX_MARKER,
    patch_v1_reinforcement_acceptance_html,
)


def test_infers_geometry_for_composite_area_problem():
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


def test_existing_valid_figure_is_preserved():
    existing = {"type": "coordinate_grid", "xMax": 6, "yMax": 6}
    item = {"subject": "数学", "knowledge": "位置", "text": "标出点A", "figure": existing}
    assert infer_reinforcement_figure(item) is existing


def test_route_patch_adds_missing_figure_without_changing_answer():
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


def test_v1_acceptance_patch_is_idempotent_and_contains_mixed_renderer():
    html = "<html><body><div class='cy-ai-question'></div></body></html>"
    patched = patch_v1_reinforcement_acceptance_html(html)
    assert V1_REINFORCEMENT_FIX_MARKER in patched
    assert "参考答案：" in patched
    assert "fill_blank" in patched
    assert "composite_rect" in patched
    assert patch_v1_reinforcement_acceptance_html(patched) == patched
