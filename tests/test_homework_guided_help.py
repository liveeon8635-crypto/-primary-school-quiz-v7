"""晚托作业助手：引导式讲解，从学生知识地图上已经会的知识出发。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from changying.services.homework_guidance import check_steps, exam_line, map_lines, pick_node
from changying.services.homework_prompts import build_solve_prompt, clean_solution
from changying.services import knowledge_maps as km

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("guided_help_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_guided_steps_are_cleaned_and_only_checked_numbers_are_asked():
    raw = {"method": "先算总数", "knowledgePoint": "小数乘法解决问题", "nodeKey": "2-6", "start": "你已经会小数乘整数。", "life": "买 3 支笔",
           "steps": [{"kind": "choice", "ask": "这道题求什么？", "options": ["一共多少米", "还剩多少米"], "correct": 0, "hint": "看问题", "text": "求一共。"},
                     {"kind": "number", "ask": "0.8×3 等于多少？", "answer": "2.4", "expression": "0.8×3", "hint": "先算 8×3", "text": "0.8×3=2.4"},
                     {"kind": "number", "ask": "再加多少？", "answer": "5", "expression": "2+2", "text": "算错的一步"},
                     {"kind": "choice", "ask": "选哪个？", "options": ["a"], "correct": 0, "text": "只有一个选项"},
                     {"kind": "number", "ask": "没写算式", "answer": "3", "text": "没法核对"}],
           "answer": "2.4米", "expression": "0.8*3"}
    s = clean_solution(raw)
    assert [x["kind"] for x in s["steps"]] == ["choice", "number", "number", "read", "number"]
    assert s["nodeKey"] == "2-6" and s["start"] and s["life"]
    out = check_steps(s, final_ok=True)
    assert [x["kind"] for x in out["steps"]] == ["choice", "number", "read", "read", "read"]
    assert out["steps"][1]["check"]["value"] == 2.4 and "check" not in out["steps"][2]
    assert abs(out["finalCheck"]["value"] - 2.4) < 1e-9
    assert "finalCheck" not in check_steps(s, final_ok=False)            # an unchecked final answer is never compared
    # Old plain steps still work: they are read-only.
    assert [x["kind"] for x in clean_solution({"steps": [{"n": 1, "text": "先算"}], "answer": "7"})["steps"]] == ["read"]
    # A rounded answer accepts the rounding it states.
    near = check_steps(clean_solution({"steps": [{"text": "t"}], "answer": "0.33", "expression": "1/3"}), final_ok=True)["finalCheck"]
    assert abs(near["value"] - 0.33) < 1e-9 and near["tol"] >= 0.005


def test_prompt_asks_first_and_carries_only_the_map_and_mastery():
    m = km.clean_map(km.template("rj2026-g5-math-up"))
    lines = map_lines(m, {"2-2": {"level": "pass"}, "2-3": {"level": "weak"}})
    assert "2-2 小数乘小数｜先学：2-1｜已会" in lines and "2-3 积的近似数｜先学：2-2｜薄弱" in lines and "2-6 小数乘法解决问题｜先学：2-2、2-3、2-5｜未测" in lines
    prompt = build_solve_prompt(5, "一根绳子长 0.8 米……", known_map=lines)
    assert "先问学生一个小问题" in prompt and "hint" in prompt and "不要直接说出整道题的最终答案" in prompt
    assert "nodeKey" in prompt and "已会" in prompt and lines in prompt
    assert "掌握情况" not in build_solve_prompt(5, "题目")                   # no map: grade and question only
    assert pick_node(m, "2-6", "")["key"] == "2-6"
    assert pick_node(m, "", "小数乘法解决问题")["key"] == "2-6" and pick_node(m, "9-9", "天气") is None
    from datetime import date
    assert exam_line("期中考试", "2026-11-09", date(2026, 10, 30)) == "这个知识点在「期中考试」的考试范围里，离考试还有 10 天。"
    assert exam_line("期中考试", "2026-10-29", date(2026, 10, 30)) == ""


FLOW = r'''
from datetime import datetime, timedelta

def guided(node="2-6", answer="2.4米", expression="0.8*3", kp="小数乘法解决问题"):
    return json.dumps({"method": "先想求什么", "knowledgePoint": kp, "nodeKey": node,
                       "start": "你已经会小数乘小数，这道题就是用它解决问题。", "life": "就像买 3 支 0.8 元的笔。",
                       "steps": [{"n": 1, "kind": "choice", "ask": "这道题求什么？", "options": ["一共多长", "还剩多长"], "correct": 0, "hint": "读最后一句", "text": "求一共多长。"},
                                 {"n": 2, "kind": "number", "ask": "0.8×3 先按整数算，8×3 等于多少？", "answer": "24", "expression": "8*3", "hint": "乘法口诀", "text": "8×3=24。"},
                                 {"n": 3, "kind": "number", "ask": "这一步写错了算式", "answer": "5", "expression": "2+2", "hint": "", "text": "数一数小数位数。"}],
                       "answer": answer, "expression": expression}, ensure_ascii=False)


def later():
    """Move earlier requests and model calls back a few minutes: the per-minute limits are not under test here."""
    helps = legacy.Base.metadata.tables["help_requests"]
    with legacy.SessionLocal() as db:
        db.execute(helps.update().values(created_at=helps.c.created_at - timedelta(minutes=5)))
        for log in db.scalars(select(legacy.AIUsageLog)):
            log.created_at = log.created_at - timedelta(minutes=5)
        db.commit()


with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        db.get(legacy.User, sid).grade = 5
        db.commit()
    d = client.post("/teacher/knowledge-maps", headers=th, json={"template": "rj2026-g5-math-up"}).json()
    mid, rev = d["id"], d["revision"]
    ids = {}
    with legacy.SessionLocal() as db:
        for n in [n for n in d["map"]["nodes"] if n["assessed"]]:
            for i, level in enumerate(("basic", "basic", "medium", "medium", "hard", "hard")):
                q = legacy.Question(school_id=school_id, grade=5, subject="数学", unit=n["unit"], knowledge=n["name"],
                                    text=f"{n['key']} 第{i + 1}题", options_json="[]", correct_index=0, question_type="fill_blank",
                                    answer_json=json.dumps({"answer": "7"}))
                db.add(q); db.flush(); ids.setdefault(n["key"], []).append((q.id, level))
        db.commit()
    for key, qs in ids.items():
        rev = client.put(f"/teacher/knowledge-maps/{mid}/nodes/{key}/levels", headers=th,
                         json={"levels": {str(q): lv for q, lv in qs}, "revision": rev}).json()["revision"]
    client.post(f"/teacher/knowledge-maps/{mid}/publish", headers=th, json={"revision": rev})
    # 2-2 learned (three right first time), 2-3 weak (three wrong), 2-5 and 2-6 never tried.
    q22, q23 = [q for q, _ in ids["2-2"]], [q for q, _ in ids["2-3"]]
    sub = [{"question_id": q, "text_answer": "7"} for q in q22[:3]] + [{"question_id": q, "text_answer": "9"} for q in q23[:3]]
    assert client.post("/student/practice-submit", headers=sh, json={"answers": sub}).status_code == 200
    # The pupil's class prepares for an exam on unit 2 in ten days.
    goals = legacy.Base.metadata.tables["exam_goals"]
    with legacy.SessionLocal() as db:
        cid = db.scalar(select(legacy.ClassStudent.class_id).where(legacy.ClassStudent.student_id == sid))
        day = (datetime.now(legacy.SCHOOL_TZ).date() + timedelta(days=10)).isoformat()
        db.execute(goals.insert().values(school_id=school_id, teacher_id=1, map_id=mid, class_id=cid, title="期中考试", exam_date=day,
                                         unit_keys_json=json.dumps(["U2", "U3"]), created_at=datetime.utcnow()))
        db.commit()

    hid = make_help(client, sh, "一根绳子 0.8 米，3 根一共多长？", grade=5)
    replies.append(guided())
    r = client.post(f"/student/homework/help/{hid}/solve", headers=sh)
    assert r.status_code == 200, r.text
    body = r.json()
    s = body["solution"]
    prompt = prompts[-1]
    assert "2-2 小数乘小数｜先学：2-1｜已会" in prompt and "2-3 积的近似数｜先学：2-2｜薄弱" in prompt and "2-6 小数乘法解决问题" in prompt
    for secret in ("student1", "Student1234", "teacher1", "期中考试", "第1题"):     # no account, exam or question text of his
        assert secret not in prompt, secret
    assert [x["kind"] for x in s["steps"]] == ["choice", "number", "read"]
    assert s["steps"][1]["check"]["value"] == 24 and all("expression" not in x for x in s["steps"])
    assert s["finalCheck"]["value"] == 2.4 and "expression" not in s and "verify" not in s
    assert s["start"].startswith("你已经会") and s["life"]
    L = s["layer"]
    assert L["node"] == {"key": "2-6", "name": "小数乘法解决问题", "state": "", "stateText": "还没测"}
    assert L["known"] == ["2-2 小数乘小数"] and L["weak"] == ["2-3 积的近似数"]
    assert L["solved"] == {"text": "2-2 第1题", "from": "2-2 小数乘小数"}
    assert L["exam"] == "这个知识点在「期中考试」的考试范围里，离考试还有 10 天。" and L["quiz"] is True
    assert client.get(f"/student/homework/help/{hid}", headers=sh).json()["solution"]["layer"] == L

    # How far he got on his own is kept once; the teacher sees it with the conversation.
    p = client.post(f"/student/homework/help/{hid}/progress", headers=sh,
                    json={"selfSolved": True, "finalChecked": True, "wrongTries": 2, "stepsAnswered": 2})
    assert p.status_code == 200 and p.json()["progress"]["selfSolved"] is True
    again = client.post(f"/student/homework/help/{hid}/progress", headers=sh, json={"revealed": True, "finalChecked": True})
    assert again.json()["progress"]["selfSolved"] is True and again.json()["progress"]["wrongTries"] == 2
    assert client.post(f"/student/homework/help/{hid}/progress", headers=th, json={}).status_code == 403
    assert client.post(f"/student/homework/help/{hid}/escalate", headers=sh, json={"note": "第三步不懂"}).status_code == 200
    talk = client.get(f"/teacher/homework/help/{hid}", headers=th).json()["conversation"]
    text = json.dumps(talk, ensure_ascii=False)
    assert "问：这道题求什么？" in text and "开头：你已经会小数乘小数" in text
    assert "（引导结果）自己算出了答案；回答了 2 个小问题，答错 2 次" in text

    later()
    # A question the map cannot place: still a guide, no map card; an unchecked final answer is not compared.
    hid2 = make_help(client, sh, "《静夜思》的作者是谁？", grade=5)
    replies.append(guided(node="", answer="李白", expression="", kp="古诗作者"))
    s2 = client.post(f"/student/homework/help/{hid2}/solve", headers=sh).json()["solution"]
    assert s2["layer"] is None and s2["finalCheck"] is None and s2["steps"][0]["kind"] == "choice"

    later()
    # A grade without a published map: grade and question only, as before.
    hid3 = make_help(client, sh, "小明有 12 个苹果，吃了 5 个，还剩几个？", grade=3)
    replies.append(sol())
    s3 = client.post(f"/student/homework/help/{hid3}/solve", headers=sh).json()["solution"]
    assert "掌握情况" not in prompts[-1] and s3["layer"] is None and s3["finalCheck"]["value"] == 7
    later()
    pending = make_help(client, sh, "还没讲的题", grade=3)
    assert client.post(f"/student/homework/help/{pending}/progress", headers=sh, json={}).status_code == 409

    later()
    # Reading the map must never cost the pupil his answer.
    real_figure = legacy.question_figure
    legacy.question_figure = lambda q: (_ for _ in ()).throw(RuntimeError("broken"))
    hid4 = make_help(client, sh, "一根绳子 0.6 米，3 根一共多长？", grade=5)
    replies.append(guided(answer="1.8米", expression="0.6*3"))
    r4 = client.post(f"/student/homework/help/{hid4}/solve", headers=sh)
    legacy.question_figure = real_figure
    assert r4.status_code == 200 and r4.json()["state"] == "answered" and r4.json()["solution"]["layer"] is None
print("OK")
'''


def test_guide_starts_from_the_pupils_map_and_keeps_how_far_he_got(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})


def test_pages_run_the_guide_and_open_the_point_on_the_map():
    import app  # noqa: F401
    from changying.web.homework_assistant_pages import homework_page_html
    from changying.web.knowledge_map_pages import student_map_page_html

    html = homework_page_html()
    for text in ("这一步不会", "再想想：", "最后：自己写出这道题的答案", "还是不会，看答案", "写好了，对答案", "/progress",
                 "这道题在你的知识地图上", "你已经会：", "你以前做对过一道相关的题", "/v1/my-knowledge-map#node=", "去做同类题", "看下一步"):
        assert text in html, text
    assert "innerHTML" not in html
    assert "[#&]node=" in student_map_page_html()
