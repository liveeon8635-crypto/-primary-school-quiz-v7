"""展开图图形题：1-4-1 型展开图，相对面由位置决定。"""
from __future__ import annotations

from changying.services import net_figures as nf
from changying.services import visual_questions as vq


def test_opposite_faces_follow_the_layout():
    # 横排里隔一格相对，上下盖相对
    assert nf._OPPOSITE["B"] == "D" and nf._OPPOSITE["D"] == "B"
    assert nf._OPPOSITE["C"] == "E" and nf._OPPOSITE["E"] == "C"
    assert nf._OPPOSITE["A"] == "F" and nf._OPPOSITE["F"] == "A"
    # 互相对称且没有自反
    for k, v in nf._OPPOSITE.items():
        assert k != v and nf._OPPOSITE[v] == k


def test_question_marks_one_face_and_answers_its_opposite():
    for seed in range(12):
        q = nf.make_question("basic", seed)
        assert q["check"]["opposite"] == nf._OPPOSITE[q["check"]["marked"]]
        assert q["options"][q["answer"]] == q["check"]["opposite"]
        assert len(q["options"]) == 4 and len(set(q["options"])) == 4


def test_figure_is_a_valid_gridshape_with_six_faces():
    q = nf.make_question("basic", 1)
    assert nf.sanitize(q["figure"]), "gridshape 拒绝了这张图"
    labels = sorted(s["label"] for s in q["figure"]["shapes"])
    assert labels == ["A", "B", "C", "D", "E", "F"]


def test_grade3_route_reaches_the_net_family():
    assert vq.supports("rj2026-g3-math-up", "1-2") is True
    items = vq.generate("1-2", "basic", 3, 5, "rj2026-g3-math-up")
    assert len(items) == 3 and all(x["figure"]["type"] == "gridshape" for x in items)
    # 三年级其余节点仍然被拒
    assert vq.supports("rj2026-g3-math-up", "2-1") is False