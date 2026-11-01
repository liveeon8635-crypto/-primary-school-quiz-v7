"""数对图形题：图形能被 gridshape 校验接受，答案与图中标 A 的格子同源。"""
from __future__ import annotations

from changying.services import coord_figures as coord
from changying.services import grid_figures as gf
from changying.services import visual_questions as vq


def test_figure_round_trips_through_gridshape():
    q = coord.make_question("basic", 11)
    cleaned = coord.sanitize(q["figure"])
    assert cleaned, "gridshape 拒绝了这张图"
    assert cleaned["type"] == "gridshape"
    assert gf.sanitize(q["figure"]), "gf.sanitize 也应接受"


def test_answer_matches_the_highlighted_cell():
    for seed in range(20):
        q = coord.make_question("medium", seed)
        assert q["options"][q["answer"]] == f"（{q['check']['col']}, {q['check']['row']}）"
        # 标 A 的格子是最后一个 shape，它的右上角坐标应落在 (col, row) 上
        cell = q["figure"]["shapes"][-1]
        assert cell["label"] == "A" and cell["tone"] == "a"
        x, y = cell["points"][0]
        assert x == q["check"]["col"] - 1


def test_grade6_route_uses_the_coordinate_family():
    assert vq.supports("rj2026-g6-math-up", "1-1") is True
    # 六年级其它节点没有图形路由，不能被放行
    assert vq.supports("rj2026-g6-math-up", "2-1") is False
    # 五年级行为不变
    assert vq.supports("rj2026-g5-math-up", "1-1") is True
    items = vq.generate("1-1", "basic", 3, 9, "rj2026-g6-math-up")
    assert len(items) == 3 and all(x["figure"]["type"] == "gridshape" for x in items)
