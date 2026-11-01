"""方向与距离图形题：方向/距离由坐标算出，图形能被 gridshape 接受。"""
from __future__ import annotations

import math

from changying.services import bearing_figures as bear
from changying.services import visual_questions as vq


def test_direction_and_distance_match_the_coordinates():
    for seed in range(30):
        q = bear.make_question("medium", seed)
        chk = q["check"]
        dx, dy = chk["dx"], chk["dy"]
        assert chk["dist"] == int(round(math.hypot(dx, dy)))
        if dx == 0:
            assert chk["dir"] in ("正北", "正南")
        elif dy == 0:
            assert chk["dir"] in ("正东", "正西")
        else:
            ang = int(round(math.degrees(math.atan2(abs(dx), abs(dy)))))
            assert str(ang) in chk["dir"]
        assert q["options"][q["answer"]] == f"{chk['dir']}，{chk['dist']} 格"


def test_figure_is_a_valid_gridshape():
    q = bear.make_question("basic", 1)
    assert bear.sanitize(q["figure"]), "gridshape 拒绝了这张图"
    labels = [s["label"] for s in q["figure"]["shapes"] if s.get("label")]
    assert labels == ["O", "A"]


def test_grade6_position_nodes_are_routed():
    for key in ("1-1", "1-2", "1-3"):
        assert vq.supports("rj2026-g6-math-up", key) is True
    # 没有图形路由的节点仍然被拒
    assert vq.supports("rj2026-g6-math-up", "3-1") is False
    # 五年级不受影响
    assert vq.supports("rj2026-g5-math-up", "1-4") is True
