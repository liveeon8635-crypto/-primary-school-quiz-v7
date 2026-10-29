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
    assert "prompt(" not in KNOWLEDGE_MAP_JS                       # adding a point uses the in-page form
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


AI_FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    node = next(n for n in d["map"]["nodes"] if n["key"] == "4-3")
    url = f"/teacher/knowledge-maps/{mid}/nodes/4-3/ai"
    assert client.post(url, headers=th, json={"level": "很难"}).status_code == 400
    assert client.post(url, headers=sh, json={"level": "medium"}).status_code == 403

    def q(kind, text, steps, expression="", answer="", options=None, ci=-1, angle="两步求解"):
        return {"question_type": kind, "text": text, "steps": steps, "expression": expression, "answer": answer,
                "options": options or [], "correct_index": ci, "explanation": "解析", "knowledge": "旋转", "angle": angle}

    # Mixed types for 中等: the drafts are checked here, not just passed on.
    replies.append(json.dumps({"questions": [
        q("single_choice", "钟面上的指针从 12 绕中心顺时针旋转 90°，指向几？", ["一大格 30°", "90÷30=3"], "90÷30", options=["3", "6", "9", "12"], ci=0, angle="确定运动后位置"),
        q("fill_blank", "指针从 12 顺时针转到 6，转了（　）度。", ["每格 30°", "6×30=180"], "6×30", "180", angle=" 两步求解 "),
        q("true_false", "指针从 12 顺时针旋转 90° 后指向 3。", ["90° 是 3 大格", "12 往后 3 格是 3"], options=["正确", "错误"], ci=0, angle="找错并改正"),
        q("fill_blank", "指针从 12 顺时针转到 4，转了（　）度。", ["每格 30°", "4×30=120"], "4×30", "120", angle="两步求解"),  # same angle again
        q("fill_blank", "指针从 12 顺时针转到 2，转了（　）度。", ["每格 30°", "2×30=60"], "2×30", "60", angle="数格读位置"),   # a 基础 angle
        q("calculation", "指针从 3 顺时针转到 9，转了多少度？", ["相差 6 格", "6×30"], "6×30", "120"),          # wrong answer
        q("short_answer", "指针从 12 逆时针转 90°，指向几？", ["只有一步"], "12-3", "9"),                       # one step only
        q("fill_blank", "指针从 12 顺时针转到 9，转了（　）度。", ["数格子", "乘 30"], "", "270", angle="描述运动过程"),  # shapes: kept unchecked
    ]}, ensure_ascii=False))
    replies.append(json.dumps({"questions": []}))      # the generator's own follow-up for the remainder
    r = client.post(url, headers=th, json={"level": "medium", "count": 5, "questionType": "mixed"})
    assert r.status_code == 200, r.text
    r = r.json()
    assert len(r["items"]) == 4 and r["short"] == 1 and r["verified"] == 2
    assert {x["question_type"] for x in r["items"]} == {"single_choice", "fill_blank", "true_false"}
    assert r["dropped"] == {"验算不对": 1, "步骤太少（中等至少 2 步、提高至少 3 步）": 1, "命题角度不属于这一难度": 1}
    assert {x["angle"] for x in r["items"]} == {"确定运动后位置", "找错并改正", "两步求解", "描述运动过程"}
    first = prompts[-2]
    for t in ("旋转的三要素", "题干不能依赖图片", "图形的运动", '"steps"', '"expression"', "题型要多样", "中等", "【命题角度】", "每道题用不同的角度", "确定运动后位置", "真正用到这个知识点本身", '"angle"', "最多两位小数"):
        assert t in first, t

    # The teacher keeps them; each type is saved as itself, then levelled.
    keep = []
    for it in r["items"]:
        row = {**it, "knowledge": node["bankKeys"][0]}
        for k in ("steps", "expression", "verified", "angle"):
            row.pop(k, None)
        keep.append(row)
    saved = client.post("/ai/questions/save", headers=th, json={"questions": keep}).json()["items"]
    assert {x["questionType"] for x in saved} == {"single_choice", "fill_blank", "true_false"}
    assert next(x for x in saved if x["questionType"] == "fill_blank")["answer"] == "180"
    d = client.put(f"/teacher/knowledge-maps/{mid}/nodes/4-3/levels", headers=th,
                   json={"levels": {str(x["id"]): "medium" for x in saved}, "revision": rev}).json()
    n = next(x for x in d["map"]["nodes"] if x["key"] == "4-3")
    assert n["coverage"]["counts"] == {"basic": 0, "medium": 4, "hard": 0}

    # The next request lists what the point already has; a draft repeating one of them is skipped.
    replies.append(json.dumps({"questions": [
        q("fill_blank", "指针从 12 顺时针转到 6，转了（　）度。", ["每格 30°", "6×30=180"], "6×30", "180", angle="两步求解"),
        q("fill_blank", "指针从 3 顺时针转到 5，转了（　）度。", ["相差 2 格", "2×30=60"], "2×30", "60", angle="两步求解"),
    ]}, ensure_ascii=False))
    replies.append(json.dumps({"questions": []}))
    r = client.post(url, headers=th, json={"level": "medium", "count": 2}).json()
    assert [x["text"] for x in r["items"]] == ["指针从 3 顺时针转到 5，转了（　）度。"]
    assert "已有题目（不要重复这些题" in prompts[-2] and "指针从 12 顺时针转到 6" in prompts[-2]

    page = client.get("/v1/knowledge-map").text
    for t in ("kmAIGen(", "/ai',{json:{level:", "/ai/questions/save", "存入题库并分为", "混合题型（推荐）", "已验算", "答案待核对", "考法：", "km-draft", ".km-draft>label{display:block"):
        assert t in page, t
print("OK")
'''


def test_ai_drafts_for_a_node_are_reviewed_saved_and_levelled(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + AI_FLOW, {"KNOWLEDGE_MAP": "1"})


BANK_FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    with legacy.SessionLocal() as db:
        other = legacy.School(name="别校", code="OTHER-BANK"); db.add(other); db.flush()
        def q(text, knowledge, unit="第一单元", qtype="fill_blank", figure="{}", school=school_id):
            row = legacy.Question(school_id=school, grade=5, subject="数学", unit=unit, knowledge=knowledge, text=text, options_json="[]",
                                  correct_index=-1, question_type=qtype, answer_json=json.dumps({"answer": "①③④"}), figure_json=figure)
            db.add(row); db.flush(); return row.id
        front = q("从前面看是图A的有（ ）。", "从前面观察简单组合体")
        top = q("从上面看是图B的有（ ）。", "从上面观察简单组合体")
        draw = q("在方格纸上画出从前面、上面和左面看到的图形。", "画简单组合体的三视图", qtype="non_choice")
        drawn = q("看图填空", "从左面观察简单组合体", figure=json.dumps({"type": "geometry", "shape": "cube"}))
        q("0.3×0.2=（ ）", "小数乘小数", unit="第二单元")
        q("外校题：从前面看", "从前面观察简单组合体", school=other.id)
        db.commit()

    base = f"/teacher/knowledge-maps/{mid}/bank"
    assert client.get(base, headers=sh).status_code == 403
    first = client.get(base, headers=th).json()
    assert first["items"] == [] and {"第一单元", "第二单元"} <= set(first["units"])
    by_unit = client.get(base, headers=th, params={"unit": "第一单元"}).json()
    assert [x["id"] for x in by_unit["items"]] == [front, top, draw, drawn] and by_unit["total"] == 4
    notes = {x["id"]: x["note"] for x in by_unit["items"]}
    assert notes[front] == "" and "批改" in notes[draw] and "图示" in notes[drawn]
    assert "外校" not in json.dumps(by_unit, ensure_ascii=False)
    by_word = client.get(base, headers=th, params={"q": "前面"}).json()
    assert {x["id"] for x in by_word["items"]} == {front, draw}            # text or knowledge name

    # Picked into 1-1 whatever their knowledge names; the node lists them with the notes, the bank shows where they went.
    d = client.put(f"/teacher/knowledge-maps/{mid}/nodes/1-1/levels", headers=th,
                   json={"levels": {str(front): "basic", str(top): "medium", str(draw): "hard"}, "revision": rev}).json()
    n11 = next(n for n in d["map"]["nodes"] if n["key"] == "1-1")
    assert n11["coverage"]["counts"] == {"basic": 1, "medium": 1, "hard": 1}
    listed = client.get(f"/teacher/knowledge-maps/{mid}/nodes/1-1/questions", headers=th).json()["items"]
    assert [(x["id"], x["level"]) for x in listed] == [(front, "basic"), (top, "medium"), (draw, "hard")]
    assert "批改" in next(x for x in listed if x["id"] == draw)["note"]
    again = client.get(base, headers=th, params={"unit": "第一单元"}).json()
    assert next(x for x in again["items"] if x["id"] == front)["placed"] == ["1-1", "basic"]
    assert next(x for x in again["items"] if x["id"] == drawn)["placed"] is None
    page = client.get("/v1/knowledge-map").text
    for t in ("kmBankPick(", "/bank?unit=", "从题库挑题", "把选中的题归到这个知识点"):
        assert t in page, t
print("OK")
'''


def test_bank_search_picks_questions_whatever_their_knowledge_name(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + BANK_FLOW, {"KNOWLEDGE_MAP": "1"})


def test_restore_unit_adds_back_missing_points_and_their_links_only():
    tmpl = km.template("rj2026-g5-math-up")
    m = km.clean_map(copy.deepcopy(tmpl))
    gone = {"1-1", "1-2", "1-3", "1-4"}
    m["nodes"] = [n for n in m["nodes"] if n["key"] not in gone]
    for n in m["nodes"]:
        n["prereqs"] = [p for p in n["prereqs"] if p not in gone]
    next(n for n in m["nodes"] if n["key"] == "2-1")["name"] = "小数乘整数（老师改过）"
    next(n for n in m["nodes"] if n["key"] == "2-2")["levels"] = {"7": "basic"}
    next(n for n in m["nodes"] if n["key"] == "2-6")["prereqs"] = ["2-2"]        # a deliberate teacher edit
    out, restored = km.restore_unit(m, tmpl, "U1")
    out = km.clean_map(out)
    assert restored == ["1-1", "1-2", "1-3", "1-4"]
    by = {n["key"]: n for n in out["nodes"]}
    assert by["1-3"]["prereqs"] == ["1-1", "1-2"] and by["1-4"]["prereqs"] == ["1-3"]
    assert {"1-3", "1-4"} <= set(by["8-3"]["prereqs"])
    assert by["2-1"]["name"] == "小数乘整数（老师改过）" and by["2-2"]["levels"] == {"7": "basic"}
    assert by["2-6"]["prereqs"] == ["2-2"]                                          # links not touching U1 are left alone
    assert km.restore_unit(out, tmpl, "U1")[1] == []


RESTORE_FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid = d["id"]
    m = d["map"]
    m["nodes"] = [n for n in m["nodes"] if n["unit"] != "U1"]
    for n in m["nodes"]:
        n["prereqs"] = [p for p in n["prereqs"] if not p.startswith("1-")]
    d = client.put(f"/teacher/knowledge-maps/{mid}", headers=th, json={"map": m, "revision": d["revision"]}).json()
    assert not [n for n in d["map"]["nodes"] if n["unit"] == "U1"]
    base = f"/teacher/knowledge-maps/{mid}/units"
    assert client.post(base + "/U1/restore", headers=th, json={"revision": d["revision"] - 1}).status_code == 409   # stale
    assert client.post(base + "/U9/restore", headers=th, json={"revision": d["revision"]}).status_code == 404
    assert client.post(base + "/U1/restore", headers=sh, json={"revision": d["revision"]}).status_code == 403
    r = client.post(base + "/U1/restore", headers=th, json={"revision": d["revision"]}).json()
    assert r["restored"] == ["1-1", "1-2", "1-3", "1-4"] and r["summary"]["assessed"] == 19
    assert {"1-3", "1-4"} <= set(next(n for n in r["map"]["nodes"] if n["key"] == "8-3")["prereqs"])
    again = client.post(base + "/U1/restore", headers=th, json={"revision": r["revision"]})
    assert again.status_code == 409 and "都还在" in again.json()["detail"]
    page = client.get("/v1/knowledge-map").text
    for t in ("按模板恢复本单元知识点", "kmAddForm(", "/restore", "已经有了"):
        assert t in page, t
print("OK")
'''


def test_teacher_restores_a_deleted_unit_from_the_template(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + RESTORE_FLOW, {"KNOWLEDGE_MAP": "1"})


def test_ai_drafts_are_checked_and_mixed():
    from changying.services import knowledge_maps as km
    calc = {"question_type": "calculation", "text": "2.5×4+1.2=?", "answer": "11.2", "expression": "2.5×4+1.2", "steps": ["a", "b", "c"],
            "options": [], "correct_index": -1}
    assert km.check_ai_question({**calc, "angle": "多步综合"}, "hard", "数学")[0]["verified"]
    assert km.check_ai_question({**calc, "angle": "多步综合", "steps": ["a", "b"]}, "hard", "数学")[1].startswith("步骤太少")
    assert km.check_ai_question({**calc, "angle": "两步解决问题", "answer": "12"}, "medium", "数学")[1] == "验算不对"
    # 基础 keeps a draft it cannot check, marked as unchecked; 语文 answers are not computed.
    basic = km.check_ai_question({**calc, "angle": "直接求结果", "expression": "", "steps": ["a"]}, "basic", "数学")[0]
    assert basic and basic["verified"] is False
    assert km.check_ai_question({**calc, "answer": "春天", "expression": ""}, "medium", "语文")[0]["verified"] is False
    choice = {"question_type": "single_choice", "text": "0.3×0.2=?", "options": ["0.06", "0.6", "0.6", "6"], "correct_index": 0, "steps": ["a"], "angle": "直接求结果"}
    assert km.check_ai_question(choice, "basic", "数学")[1] == "选项有重复"
    # Types are taken in turn: four choices cannot crowd out the other types.
    items = [{"question_type": "single_choice", "verified": True}] * 4 + [{"question_type": "fill_blank", "verified": False},
                                                                          {"question_type": "true_false", "verified": False}]
    assert [x["question_type"] for x in km.pick_ai_drafts(items, 4)] == ["single_choice", "fill_blank", "true_false", "single_choice"]


def test_ai_angles_follow_the_level_and_do_not_repeat():
    from changying.services import knowledge_maps as km
    calc = {"question_type": "calculation", "text": "2.5×4+1.2=?", "answer": "11.2", "expression": "2.5×4+1.2", "steps": ["a", "b", "c"],
            "options": [], "correct_index": -1}
    # 提高 only takes its own angles: a 中等 way of asking is not a 提高 question.
    assert km.check_ai_question({**calc, "angle": "两步解决问题"}, "hard", "数学")[1] == "命题角度不属于这一难度"
    assert km.check_ai_question({**calc}, "hard", "数学")[1] == "命题角度不属于这一难度"
    assert km.check_ai_question({**calc, "angle": "逆向推理题"}, "hard", "数学")[0]["angle"] == "逆向推理"
    assert km.check_ai_question({**calc, "angle": ""}, "hard", "语文")[0]                 # 语文 has no angle list
    assert not {n for n, _ in km.MATH_ANGLES["medium"]} & {n for n, _ in km.MATH_ANGLES["hard"]}
    # One angle once per batch while the level has enough angles; a stem the point already has is skipped.
    items = [{"question_type": "calculation", "text": f"题{i}", "angle": a, "verified": True}
             for i, a in enumerate(["逆向推理", "逆向推理", "方案比较", "规律探究"])]
    got = km.pick_ai_drafts(items, 3, "hard", existing=["题 3"])
    assert [x["text"] for x in got] == ["题0", "题2"]
    assert km.angle_cap("basic", 10) == 3 and km.angle_cap("medium", 6) == 1
    assert "同一个角度最多用 3 次" in km.angle_brief("basic", 10) and "每道题用不同的角度" in km.angle_brief("hard", 6)
    assert km.angle_brief("hard", 6).count("\n- ") == len(km.MATH_ANGLES["hard"])


def test_ai_angles_follow_the_unit():
    from changying.services import knowledge_maps as km
    from changying.services import weekend_question_gen as qg
    assert km.math_angles("图形的运动") is km.SHAPE_ANGLES and km.math_angles("多边形的面积") is km.SHAPE_ANGLES
    assert km.math_angles("可能性") is km.CHANCE_ANGLES and km.math_angles("小数除法") is km.MATH_ANGLES
    # A shapes point does not take calculation angles, and a shapes answer such as 90° needs no expression.
    turn = {"question_type": "fill_blank", "text": "指针从 12 顺时针转到 3，转了（　）度。", "answer": "90°", "expression": "",
            "steps": ["一大格 30°", "3 大格"], "options": [], "correct_index": -1}
    assert km.check_ai_question({**turn, "angle": "两步解决问题"}, "medium", "数学", "图形的运动")[1] == "命题角度不属于这一难度"
    kept = km.check_ai_question({**turn, "angle": "确定运动后位置"}, "medium", "数学", "图形的运动")[0]
    assert kept and kept["verified"] is False
    assert km.check_ai_question({**turn, "angle": "两步解决问题"}, "medium", "数学", "小数除法")[1] == "数学答案没有可验算的算式"
    assert "描述运动过程" in km.angle_brief("medium", 6, "图形的运动") and "计算并验算" not in km.angle_brief("medium", 6, "图形的运动")
    # A grid point is not the number 51; 1,000 still is 1000.
    assert qg.number("(5,1)") is None and qg.number("1,000") == 1000


def test_ai_chance_questions_stay_qualitative():
    from changying.services import knowledge_maps as km
    draft = {"question_type": "fill_blank", "angle": "比较可能性大小", "steps": ["数一数", "比较"], "options": [], "correct_index": -1,
             "text": "袋里有 4 个红球、6 个蓝球，摸到哪种球的可能性大？", "answer": "蓝球", "expression": "", "explanation": "蓝球多，可能性大。"}
    assert km.check_ai_question(draft, "medium", "数学", "可能性")[0]
    for change in ({"text": "摸到蓝球的可能性比红球大多少？（用小数表示）", "answer": "0.1"},
                   {"explanation": "甲袋摸到红球的可能性是5÷10=0.5，乙袋是0.35。"},
                   {"text": "要使摸到红球的可能性为 0.35，应放几个红球？", "answer": "7"}):
        assert km.check_ai_question({**draft, **change}, "medium", "数学", "可能性")[1] == "可能性用数表示（小学只比较大小）"
    assert "不要用分数、小数、百分数表示可能性" in km.angle_brief("medium", 6, "可能性")
    assert "同一种情境不超过 2 道" in km.angle_brief("hard", 6, "可能性") and "不能据此断定" in km.angle_brief("hard", 6, "可能性")
    assert "不要用分数" not in km.angle_brief("medium", 6, "小数除法")

