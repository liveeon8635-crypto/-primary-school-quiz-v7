from __future__ import annotations

import importlib.util
import sys
from fractions import Fraction
from pathlib import Path

from changying.services import weekend_question_gen as qg

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("weekend_gen_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def row(**kw):
    base = {"type": "final_answer", "level": "中等", "stem": "一个数是 2.5 的 4 倍，再加 1.2，结果是多少？", "answer": "11.2",
            "expression": "2.5×4+1.2", "steps": ["2.5×4=10", "10+1.2=11.2"], "knowledge": "小数乘法"}
    return {**base, **kw}


def test_quotas_cover_every_type_and_a_third_hard():
    q = qg.quotas("数学", 12)
    assert q["types"] == {"choice": 3, "final_answer": 5, "short_answer": 4} and q["levels"]["提高"] == 4
    for subject in ("数学", "语文"):
        for n in qg.COUNTS:
            got = qg.quotas(subject, n)
            assert sum(got["types"].values()) == n == sum(got["levels"].values()) and min(got["types"].values()) >= 1


def test_arithmetic_is_evaluated_exactly_and_only_arithmetic():
    assert qg.evaluate("2.5×(3+1.2)") == Fraction("10.5") and qg.evaluate("0.1+0.2") == Fraction("0.3")
    assert qg.evaluate("3.6÷0.4−1".replace("−", "-")) == 8
    for bad in ("__import__('os')", "2**10", "1/0", "abc", ""):
        assert qg.evaluate(bad) is None
    assert qg.agrees(Fraction("3.14159"), Fraction("3.14"), "得数保留两位小数", "约3.14")
    assert not qg.agrees(Fraction("3.14159"), Fraction("3.14"), "求积", "3.14")             # rounding only when asked


def test_checks_keep_hard_checked_questions_and_drop_the_rest():
    ok, _ = qg.check(row(), "数学")
    assert ok["verified"] and ok["expression"] == "2.5×4+1.2"
    reasons = {why for _, why in (qg.check(row(answer="11.3"), "数学"),                              # wrong arithmetic
                                  qg.check(row(expression=""), "数学"),                              # 中等 fill-in without a check
                                  qg.check(row(level="提高", steps=["只有一步"]), "数学"),
                                  qg.check(row(stem="什么是小数乘法的意义呢？", answer="略"), "数学"),  # recall only above 基础
                                  qg.check(row(type="choice", options=["1", "2", "3"], correctIndex=0), "数学"),
                                  qg.check(row(level="很难"), "数学"))}
    assert reasons == {"验算不对", "数学答案没有可验算的算式", "提高题少于两步", "中等以上没有让学生计算", "选择题要 4 个不同的选项", "没写难度"}
    # A choice whose answer cannot be written as + − × ÷ is kept, marked as not checked.
    gcd, _ = qg.check(row(type="choice", level="基础", stem="8 和 12 的最大公因数是（　）", options=["2", "4", "6", "24"],
                          correctIndex=1, expression=""), "数学")
    assert gcd and not gcd["verified"] and gcd["answer"] == "4"
    essay, _ = qg.check({"type": "composition", "level": "提高", "stem": "以“我的周末”为题写一段话，不少于 200 字。",
                         "steps": ["确定内容", "按顺序写"]}, "语文")
    assert essay and essay["type"] == "composition"
    assert qg.check(row(type="composition"), "数学")[1] == "题型不对"


def test_select_fills_quotas_without_duplicates():
    want = {"types": {"choice": 1, "final_answer": 2}, "levels": {"基础": 1, "中等": 1, "提高": 1}}
    rows = [qg.check(r, "数学")[0] for r in (
        row(), row(stem="一个数是 2.5 的 4 倍，再加 1.2，结果是多少？ "),                         # duplicate of the first
        row(level="提高", stem="3 千克苹果 7.5 元，买 5 千克要多少元？", answer="12.5", expression="7.5÷3×5", steps=["7.5÷3=2.5", "2.5×5=12.5"]),
        row(level="基础", type="choice", stem="0.3×0.2=（　）", options=["0.06", "0.6", "6", "0.006"], correctIndex=0, answer="0.06", expression="0.3×0.2"))]
    got = qg.select(rows, want, existing=["已经有的题"])
    assert len(got) == 3 and {r["type"] for r in got} == {"choice", "final_answer"}
    assert qg.missing(want, got) == {"types": {"choice": 0, "final_answer": 0}, "levels": {"基础": 0, "中等": 0, "提高": 0}}
    assert qg.select(rows, want, existing=[rows[0]["stem"]]) and all(r["stem"] != rows[0]["stem"] for r in qg.select(rows, want, existing=[rows[0]["stem"]]))


def test_prompt_states_quotas_levels_and_material():
    want = qg.quotas("语文", 12)
    text = qg.prompt("语文", 5, "人教版", {"title": "落花生", "core_target": "x", "material": "我们家的后园有半亩空地"},
                     want, ["（提高）示例题｜答案：甲"], ["概括中心"], ["旧题一"])
    for part in ("一共出 12 道", "提高 4 道", "我们家的后园有半亩空地", "示例题", "旧题一", "概括中心", "4 个选项", '"level"'):
        assert part in text, part


FLOW = r'''
import json
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    # A lesson with a plan, imported by rule (no model call).
    md = "# 第05课：小数乘法\n\n## 本节目标\n会算小数乘法。\n\n## 教学流程\n1. 复习\n\n## 例题\n例1：2.5×4\n\n## 课后练习\n1. 0.5×6=？\n【答案】3\n"
    r = client.post("/teacher/weekend/lessons/import/markdown", headers=th, data={"subject": "数学", "onConflict": "overwrite"},
                    files=[("files", ("第05课.md", md.encode("utf-8"), "text/markdown"))])
    assert r.status_code == 200, r.text
    lid = next(x for x in client.get("/teacher/weekend/schedule?subject=数学", headers=th).json()["items"] if x["lessonNo"] == 5)["lessonId"]
    gen = f"/teacher/weekend/lessons/{lid}/questions/generate"
    assert client.post(gen, headers=th, json={"count": 10}).status_code == 400
    assert client.post(gen, headers=sh, json={"count": 8}).status_code == 403

    def item(t, level, stem, answer, expression="", steps=("第一步", "第二步"), options=None, ci=0):
        d = {"type": t, "level": level, "stem": stem, "answer": answer, "expression": expression, "steps": list(steps),
             "knowledge": "小数乘法", "explanation": "解析", "hints": ["方向", "第一步", "完整思路"]}
        if options:
            d.update(options=options, correctIndex=ci)
        return d

    first = [
        item("choice", "基础", "0.3×0.2=（　）", "0.06", "0.3×0.2", options=["0.06", "0.6", "6", "0.006"]),
        item("final_answer", "中等", "2.5×4+1.2=（　）", "11.2", "2.5×4+1.2"),
        item("final_answer", "中等", "1.5×0.4=（　）", "0.7", "1.5×0.4"),                    # wrong: 0.6
        item("final_answer", "中等", "小数乘法的意义是什么？", "略"),                          # recall only
        item("short_answer", "提高", "3 千克苹果 7.5 元，买 5 千克要多少元？", "12.5", "7.5÷3×5"),
        item("short_answer", "提高", "一根绳子长 4.2 米，剪去 1.5 米后，剩下的平均分成 3 段，每段长多少米？", "0.9", "(4.2-1.5)÷3"),
        item("choice", "中等", "0.25×4 的积是（　）", "1", "0.25×4", options=["1", "0.1", "10", "0.01"]),
    ]
    second = [
        item("final_answer", "基础", "0.5×6=（　）", "3", "0.5×6", steps=["0.5×6=3"]),
        item("short_answer", "中等", "每支笔 1.2 元，买 4 支要多少元？", "4.8", "1.2×4"),
        item("final_answer", "提高", "2.4×0.5+0.8=（　）", "2", "2.4×0.5+0.8"),
    ]
    replies.extend([json.dumps({"items": first}, ensure_ascii=False), json.dumps({"items": second}, ensure_ascii=False)])
    g = client.post(gen, headers=th, json={"count": 8})
    assert g.status_code == 200, g.text
    g = g.json()
    assert g["count"] == 8 and g["short"] == 0 and g["byType"] == {"choice": 2, "final_answer": 3, "short_answer": 3}
    assert g["byLevel"] == {"基础": 2, "中等": 3, "提高": 3} and g["verified"] == 8
    assert g["dropped"] == {"验算不对": 1, "中等以上没有让学生计算": 1}
    assert "一共出 8 道" in prompts[-2] and "小数乘法" in prompts[-2]
    assert "一共出" in prompts[-1] and "0.3×0.2" in prompts[-1]                 # the follow-up avoids what was kept
    qs = client.get(f"/teacher/weekend/lessons/{lid}/questions", headers=th).json()["items"]
    drafts = [q for q in qs if not q["active"]]
    assert {q["level"] for q in drafts} == {"基础", "中等"} and all(q["verified"] for q in drafts)
    assert all(q["explanation"].startswith("验算：") for q in drafts)
    ws = client.get(f"/teacher/weekend/lessons/{lid}/written/questions", headers=th).json()["items"]
    gen_ws = [w for w in ws if w.get("level")]
    assert len(gen_ws) == 6 and all(w["verified"] for w in gen_ws) and any("系统已验算" in w["reference"] for w in gen_ws)
    # Editing keeps the level; approving keeps it in the next round's "don't repeat" list.
    w = gen_ws[0]
    client.put(f"/teacher/weekend/lessons/{lid}/written/questions/{w['id']}", headers=th, json={"stem": w["stem"], "reference": w["reference"], "type": w["type"], "hints": []})
    assert next(x for x in client.get(f"/teacher/weekend/lessons/{lid}/written/questions", headers=th).json()["items"] if x["id"] == w["id"])["level"] == w["level"]
    client.post(f"/teacher/weekend/lessons/{lid}/questions", headers=th, json={"approve": [drafts[0]["id"]]})
    replies.extend([json.dumps({"items": []}), json.dumps({"items": []})])
    assert client.post(gen, headers=th, json={"count": 8}).status_code == 502          # nothing usable: the drafts stay as they were
    assert len(client.get(f"/teacher/weekend/lessons/{lid}/questions", headers=th).json()["items"]) == 2
    replies.append(json.dumps({"items": second}, ensure_ascii=False))
    replies.append(json.dumps({"items": []}))
    again = client.post(gen, headers=th, json={"count": 8}).json()
    assert again["count"] == 3 and again["short"] == 5 and drafts[0]["stem"] in prompts[-2]
    # The page wires the new generator, the count choice and the tags.
    html = client.get("/v1/weekend-plan").text
    for t in ("/questions/generate", "genSummary", "已验算", "答案待核对", "AI 出习题（多题型、分难度）"):
        assert t in html, t
print("OK")
'''


def test_generate_through_the_route(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {})
