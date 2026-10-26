from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

from changying.services import knowledge_maps as km
from changying.web.knowledge_map_pages import KNOWLEDGE_MAP_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("knowledge_map_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_rj2026_template_matches_the_confirmed_map():
    m = km.clean_map(km.template("rj2026-g5-math-up"))
    assert [u["name"] for u in m["units"]] == ["观察简单组合体", "小数乘法", "小数除法", "图形的运动", "用字母表示数和数量关系",
                                              "多边形的面积", "有趣的密铺", "可能性", "复习与关联"]
    assert [u["key"] for u in m["units"] if u["learned"]] == ["U1", "U2", "U3", "U4"]
    assert len(m["nodes"]) == 41
    now = [n["key"] for n in m["nodes"] if km.assessed(m, n)]
    assert len(now) == 19 and now[0] == "1-1" and now[-1] == "4-4"
    kinds = {n["key"]: n["kind"] for n in m["nodes"]}
    assert [k for k, v in kinds.items() if v == "optional"] == ["6-6", "7-4", "8-6"]
    assert [k for k, v in kinds.items() if v == "display"] == ["T-3"]
    assert [k for k, v in kinds.items() if v == "review"] == ["8-1", "8-2", "8-3", "8-4", "8-5"]
    after = km.dependents(m)
    assert sorted(after["2-2"]) == ["2-3", "2-4", "2-5", "2-6", "6-1", "8-1"]
    assert "T-2" in after["4-3"] and "6-1" in after["4-2"]


def test_clean_map_rejects_broken_maps():
    base = km.template("rj2026-g5-math-up")
    cases = []
    m = copy.deepcopy(base); m["nodes"][0]["prereqs"] = ["1-4"]; cases.append((m, "循环"))
    m = copy.deepcopy(base); m["nodes"][0]["prereqs"] = ["9-9"]; cases.append((m, "不存在"))
    m = copy.deepcopy(base); m["nodes"][1]["key"] = "1-1"; cases.append((m, "重复"))
    m = copy.deepcopy(base); m["nodes"][0]["unit"] = "U9"; cases.append((m, "单元不存在"))
    m = copy.deepcopy(base); m["nodes"][0]["levels"] = {"12": "easy"}; cases.append((m, "分档"))
    m = copy.deepcopy(base); m["nodes"][0]["name"] = " "; cases.append((m, "不能为空"))
    m = copy.deepcopy(base); m["nodes"][0]["key"] = "1/1"; cases.append((m, "只能用"))
    for bad, reason in cases:
        with pytest.raises(ValueError, match=reason):
            km.clean_map(bad)


def test_coverage_needs_six_questions_and_two_per_level():
    node = {"kind": "core", "levels": {"1": "basic", "2": "basic", "3": "medium", "4": "medium", "5": "hard", "6": "hard"}}
    assert km.coverage(node, {1, 2, 3, 4, 5, 6})["ready"] is True
    assert km.coverage(node, {1, 2, 3, 4, 5})["ready"] is False            # a deleted question no longer counts
    node["levels"]["6"] = "basic"
    assert km.coverage(node, {1, 2, 3, 4, 5, 6}) == {"counts": {"basic": 3, "medium": 2, "hard": 1}, "total": 6, "ready": False}


def test_page_code_never_renders_markup():
    assert "innerHTML" not in KNOWLEDGE_MAP_JS and "insertAdjacentHTML" not in KNOWLEDGE_MAP_JS and "eval(" not in KNOWLEDGE_MAP_JS


FLOW = r'''
kt = legacy.Base.metadata.tables["knowledge_maps"]
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    assert client.get("/knowledge-map/config").json() == {"enabled": True}
    assert client.get("/teacher/knowledge-maps", headers=sh).status_code == 403
    lst = client.get("/teacher/knowledge-maps", headers=th).json()
    assert lst["items"] == [] and [x["key"] for x in lst["templates"]] == ["rj2026-g5-math-up"]
    assert client.post("/teacher/knowledge-maps", headers=th, json={"template": "nope"}).status_code == 400

    # Bank questions named after nodes, one in another school (never listed or accepted).
    with legacy.SessionLocal() as db:
        other = legacy.School(name="别的学校", code="OTHER-KM"); db.add(other); db.flush()
        def q(name, text, school=school_id):
            row = legacy.Question(school_id=school, grade=5, subject="数学", unit="小数乘法", knowledge=name, text=text,
                                  options_json="[]", correct_index=0, question_type="fill_blank", answer_json="{}")
            db.add(row); db.flush(); return row.id
        mine = [q("小数乘小数", f"0.{i}×0.3=___") for i in range(1, 8)]
        legacy_name = q("小数乘法", "旧版题：2.5×4=___")
        foreign = q("小数乘小数", "外校题", other.id)
        db.commit()

    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    assert client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).status_code == 409
    assert d["summary"] == {"units": 9, "nodes": 41, "assessed": 19, "assessedReady": 0, "learnedUnits": 4}
    n22 = next(n for n in d["map"]["nodes"] if n["key"] == "2-2")
    assert n22["bankCount"] == 7 and n22["assessed"] and n22["coverage"]["ready"] is False
    assert d["published"] is None and d["dependents"]["2-2"]

    base = f"/teacher/knowledge-maps/{mid}"
    qs = client.get(base + "/nodes/2-2/questions", headers=th).json()
    assert [x["id"] for x in qs["items"]] == mine and "外校题" not in json.dumps(qs, ensure_ascii=False)
    assert client.get(base + "/nodes/T-3/questions", headers=th).status_code == 404       # display-only

    # Levels: only this school's questions, only the three levels, stale revision refused.
    assert client.put(base + "/nodes/2-2/levels", headers=th, json={"levels": {str(foreign): "basic"}, "revision": rev}).status_code == 400
    assert client.put(base + "/nodes/2-2/levels", headers=th, json={"levels": {str(mine[0]): "easy"}, "revision": rev}).status_code == 400
    levels = dict(zip(map(str, mine), ["basic", "basic", "medium", "medium", "hard", "hard"]))
    d = client.put(base + "/nodes/2-2/levels", headers=th, json={"levels": levels, "revision": rev}).json()
    assert d["revision"] == rev + 1
    assert client.put(base + "/nodes/2-2/levels", headers=th, json={"levels": {}, "revision": rev}).status_code == 409
    n22 = next(n for n in d["map"]["nodes"] if n["key"] == "2-2")
    assert n22["coverage"] == {"counts": {"basic": 2, "medium": 2, "hard": 2}, "total": 6, "ready": True}
    assert d["summary"]["assessedReady"] == 1
    d = client.put(base + "/nodes/2-2/levels", headers=th, json={"levels": {str(mine[5]): None}, "revision": d["revision"]}).json()
    assert next(n for n in d["map"]["nodes"] if n["key"] == "2-2")["coverage"]["ready"] is False

    # Structure edits: rename, old bank name, a broken prerequisite is refused, levels survive a structure save.
    m = d["map"]
    node = next(n for n in m["nodes"] if n["key"] == "2-1")
    node["bankKeys"] = ["小数乘整数", "小数乘法"]
    node["levels"] = {str(mine[0]): "hard"}                                           # ignored: levels have their own endpoint
    m["units"][4]["learned"] = True                                                    # 第五单元学完了
    opt = next(n for n in m["nodes"] if n["key"] == "8-6"); opt["enabled"] = True
    d2 = client.put(base, headers=th, json={"map": m, "revision": d["revision"]}).json()
    n21 = next(n for n in d2["map"]["nodes"] if n["key"] == "2-1")
    assert n21["bankCount"] == 1 and n21["levels"] == {}
    assert next(n for n in d2["map"]["nodes"] if n["key"] == "2-2")["coverage"]["total"] == 5
    assert d2["summary"]["assessed"] == 21 and d2["summary"]["learnedUnits"] == 5
    assert not next(n for n in d2["map"]["nodes"] if n["key"] == "8-6")["assessed"]   # 第八单元未学
    assert client.get(base + "/nodes/2-1/questions", headers=th).json()["items"][0]["id"] == legacy_name
    bad = d2["map"]; bad["nodes"][0]["prereqs"] = ["1-4"]
    r = client.put(base, headers=th, json={"map": bad, "revision": d2["revision"]})
    assert r.status_code == 400 and "循环" in r.json()["detail"]

    # Publish: students read only the published copy; later drafts show as unpublished edits.
    p = client.post(base + "/publish", headers=th, json={"revision": d2["revision"]}).json()
    assert p["published"]["upToDate"] is True
    with legacy.SessionLocal() as db:
        row = db.execute(select(kt).where(kt.c.id == mid)).first()
        assert json.loads(row.published_json)["units"][4]["learned"] is True and row.school_id == school_id
    m = p["map"]; m["units"][0]["name"] = "观察物体（三）"
    p2 = client.put(base, headers=th, json={"map": m, "revision": p["revision"]}).json()
    assert p2["published"]["upToDate"] is False
    with legacy.SessionLocal() as db:
        assert json.loads(db.execute(select(kt).where(kt.c.id == mid)).first().published_json)["units"][0]["name"] == "观察简单组合体"
    nolearn = p2["map"]
    for u in nolearn["units"]:
        u["learned"] = False
    p3 = client.put(base, headers=th, json={"map": nolearn, "revision": p2["revision"]}).json()
    r = client.post(base + "/publish", headers=th, json={"revision": p3["revision"]})
    assert r.status_code == 400 and "已学" in r.json()["detail"]

    # Page and workspace entry are wired.
    page = client.get("/v1/knowledge-map").text
    for text in ("知识地图", "kmStart", "/teacher/knowledge-maps", "题目分档", "发布知识地图", "开启这个选学内容"):
        assert text in page, text
    ws = client.get("/v1/workspace").text
    assert "/v1/knowledge-map" in ws and "/knowledge-map/config" in ws
print("OK")
'''


def test_teacher_builds_levels_and_publishes_a_map(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})


OFF = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    for path in ("/knowledge-map/config", "/v1/knowledge-map", "/teacher/knowledge-maps"):
        assert client.get(path, headers=th).status_code == 404, path
    assert client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).status_code == 404
    assert "knowledge_maps" in legacy.Base.metadata.tables
print("OK")
'''


def test_everything_is_off_without_the_flag(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + OFF)
