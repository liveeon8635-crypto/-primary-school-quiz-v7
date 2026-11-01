"""三年级数学知识地图模板：按老师提供的教材目录核对，结构完整、前置不成环。"""
from __future__ import annotations

from changying.services import knowledge_maps as km


def test_grade3_template_exists_and_grade6_waits_for_catalog():
    grades = {v["grade"] for v in km.TEMPLATES.values()}
    assert 3 in grades and 5 in grades
    # 六年级目录尚未核对，暂不放进系统，避免建出错的图
    assert 6 not in grades


def test_grade3_units_match_the_textbook_contents():
    """单元名与顺序来自老师提供的教材目录页；改这里之前先对教材。"""
    names = [u["name"] for u in km.TEMPLATES["rj2026-g3-math-up"]["map"]["units"]]
    assert names == [
        "观察物体",
        "混合运算",
        "毫米、分米和千米",
        "曹冲称象的故事",
        "多位数乘一位数",
        "数字编码",
        "线和角",
        "分数的初步认识",
        "复习与关联",
    ]


def test_grade3_has_two_activity_units_and_one_review_unit():
    units = km.TEMPLATES["rj2026-g3-math-up"]["map"]["units"]
    kinds = {u["key"]: u["kind"] for u in units}
    assert kinds["UC"] == "activity"   # 曹冲称象的故事
    assert kinds["UD"] == "activity"   # 数字编码
    assert kinds["U7"] == "review"     # 复习与关联


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


def test_new_template_starts_unpublished_and_unlearned():
    """模板是草稿：所有单元默认未学，发布要靠老师手动发布。"""
    for unit in km.TEMPLATES["rj2026-g3-math-up"]["map"]["units"]:
        assert unit["learned"] is False, f"{unit['key']} 不应预置为已学"

def test_page_exposes_the_draft_import_button():
    """地图页要能一键导入预置草稿题，并提示"导入后仍需审核"。"""
    from changying.web.knowledge_map_pages import KNOWLEDGE_MAP_JS

    assert "导入预置题目草稿" in KNOWLEDGE_MAP_JS
    assert "/nodes/'+encodeURIComponent(n.key)+'/drafts" in KNOWLEDGE_MAP_JS
    assert "逐题审核" in KNOWLEDGE_MAP_JS
    assert "已导入 " in KNOWLEDGE_MAP_JS