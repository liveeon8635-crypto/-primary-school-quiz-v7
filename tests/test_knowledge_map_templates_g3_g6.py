"""三、六年级数学知识地图模板：结构完整、前置不成环、能被 clean_map 接受。"""
from __future__ import annotations

from changying.services import knowledge_maps as km


def _templates_of_grade(grade: int):
    return {k: v for k, v in km.TEMPLATES.items() if v["grade"] == grade and v["subject"] == "数学"}


def test_grade3_and_grade6_templates_exist():
    assert set(_templates_of_grade(3)) == {"rj2026-g3-math-up"}
    assert set(_templates_of_grade(6)) == {"rj2026-g6-math-up"}
    # 五年级地图及其模板不受影响
    assert set(_templates_of_grade(5)) == {"rj2026-g5-math-up"}


def _maps():
    for key, meta in km.TEMPLATES.items():
        yield key, meta["map"]


def test_no_duplicate_keys_or_names():
    for key, m in _maps():
        unit_keys = [u["key"] for u in m["units"]]
        node_keys = [n["key"] for n in m["nodes"]]
        assert len(set(unit_keys)) == len(unit_keys), key
        assert len(set(node_keys)) == len(node_keys), key
        names = [n["name"] for n in m["nodes"]]
        assert len(set(names)) == len(names), f"{key} 有重名知识点"


def test_prereqs_exist_and_are_acyclic():
    for key, m in _maps():
        node_keys = {n["key"] for n in m["nodes"]}

        for n in m["nodes"]:
            assert n["unit"] in {u["key"] for u in m["units"]}, f"{key}:{n['key']} 单元不存在"
            for p in n["prereqs"]:
                assert p in node_keys, f"{key}:{n['key']} 前置 {p} 不存在"

        graph = {n["key"]: [p for p in n["prereqs"] if p in node_keys] for n in m["nodes"]}
        state: dict[str, int] = {}

        def walk(k: str) -> None:
            state[k] = 1
            for nxt in graph[k]:
                assert state.get(nxt) != 1, f"{key}: 前置成环于 {k} -> {nxt}"
                if state.get(nxt, 0) == 0:
                    walk(nxt)
            state[k] = 2

        for k in graph:
            if state.get(k, 0) == 0:
                walk(k)


def test_every_unit_has_a_node_and_templates_pass_clean_map():
    for key, meta in km.TEMPLATES.items():
        m = meta["map"]
        units_with_nodes = {n["unit"] for n in m["nodes"]}
        assert all(u["key"] in units_with_nodes for u in m["units"]), f"{key} 有空单元"
        cleaned = km.clean_map(m)
        assert cleaned["nodes"], key


def test_new_templates_start_unpublished_and_unlearned():
    """模板是草稿：所有单元默认未学，发布要靠老师手动发布。"""
    for key in ("rj2026-g3-math-up", "rj2026-g6-math-up"):
        for unit in km.TEMPLATES[key]["map"]["units"]:
            assert unit["learned"] is False, f"{key} 的 {unit['key']} 不应预置为已学"
