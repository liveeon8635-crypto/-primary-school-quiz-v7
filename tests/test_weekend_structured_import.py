from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("structured_import_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_structured_import_is_deterministic_and_leaves_the_ai_out(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
from datetime import datetime

def plan(no, title, **extra):
    body = {"lessonNo": no, "title": title, "coreTarget": (title + "的目标") if title else "",
            "teacherPlan": "流程", "ppt": [], "examples": ["例1：半径2的圆"],
            "closureTraining": "课后练习\n1. 一题", "questions": [], "writtenQuestions": []}
    body.update(extra)
    return body

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    base = {"schemaVersion": 1, "subject": "数学"}

    # 1) dryRun reports readiness and writes nothing
    r = client.post("/teacher/weekend/lessons/import/structured", headers=th,
                    json={**base, "dryRun": True, "items": [plan(3, "圆的面积")]})
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["status"] == "ready" and r.json()["imported"] == 0
    rows = client.get("/teacher/weekend/schedule?subject=数学", headers=th).json()["items"]
    assert not any(row["lessonNo"] == 3 and row["hasPlan"] for row in rows)

    # 2) the real import stores the lesson, its choice question and its written question
    item = plan(3, "圆的面积",
                questions=[{"stem": "半径2的圆面积是多少", "options": ["6.28", "12.56"],
                            "correctIndex": 1, "explanation": "S=πr²", "knowledge": "圆的面积"}],
                writtenQuestions=[{"type": "简答", "stem": "说说推导过程", "reference": "拼成长方形"}])
    r = client.post("/teacher/weekend/lessons/import/structured", headers=th, json={**base, "items": [item]})
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["imported"] == 1 and got["items"][0]["status"] == "imported"
    lid = got["items"][0]["lessonId"]
    detail = client.get(f"/teacher/weekend/lessons/{lid}", headers=th).json()
    assert detail["title"] == "圆的面积" and detail["coreTarget"] == "圆的面积的目标"
    questions = client.get(f"/teacher/weekend/lessons/{lid}/questions", headers=th).json()["items"]
    assert len(questions) == 1 and questions[0]["options"][1] == "12.56"
    written = client.get(f"/teacher/weekend/lessons/{lid}/written/questions", headers=th).json()["items"]
    assert len(written) == 1 and written[0]["type"] == "short_answer"

    # 3) conflict semantics: ask / skip / overwrite
    r = client.post("/teacher/weekend/lessons/import/structured", headers=th,
                    json={**base, "onConflict": "ask", "items": [item]})
    assert r.json()["items"][0]["status"] == "conflict"
    r = client.post("/teacher/weekend/lessons/import/structured", headers=th,
                    json={**base, "onConflict": "skip", "items": [item]})
    assert r.json()["items"][0]["status"] == "skipped"
    r = client.post("/teacher/weekend/lessons/import/structured", headers=th,
                    json={**base, "onConflict": "overwrite", "items": [{**item, "title": "圆的面积（修订）"}]})
    assert r.json()["imported"] == 1
    assert client.get(f"/teacher/weekend/lessons/{lid}", headers=th).json()["title"] == "圆的面积（修订）"

    # 4) one invalid item never blocks the others
    bad = plan(4, "")
    bad["questions"] = [{"stem": "缺 correctIndex", "options": ["A", "B"]}]
    r = client.post("/teacher/weekend/lessons/import/structured", headers=th,
                    json={**base, "items": [bad, plan(5, "好的那节")]})
    body = r.json()
    assert body["imported"] == 1 and body["failed"] == 1
    assert body["items"][0]["status"] == "invalid" and "correctIndex" in body["items"][0]["error"]

    # 5) an unknown written type is rejected instead of being silently downgraded
    bad_type = plan(6, "题型未知", writtenQuestions=[{"type": "选择题", "stem": "x"}])
    r = client.post("/teacher/weekend/lessons/import/structured", headers=th,
                    json={**base, "items": [bad_type]})
    assert r.json()["items"][0]["status"] == "invalid"
    assert "type" in r.json()["items"][0]["error"]

    # 6) a lesson that already has a classroom record cannot be overwritten
    sessions = legacy.Base.metadata.tables["weekend_sessions"]
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        db.execute(sessions.insert().values(school_id=school_id, teacher_id=teacher.id, lesson_id=lid,
                                            title="已开课", status="planned", current_stage=0, covered=False,
                                            created_at=datetime.utcnow()))
        db.commit()
    r = client.post("/teacher/weekend/lessons/import/structured", headers=th,
                    json={**base, "onConflict": "overwrite", "items": [{**item, "title": "再改一次"}]})
    assert r.json()["items"][0]["status"] == "invalid" and "课堂" in r.json()["items"][0]["error"]
    assert client.get(f"/teacher/weekend/lessons/{lid}", headers=th).json()["title"] == "圆的面积（修订）"

    # 7) none of the above touched the model
    assert not calls, calls
print('OK')
''')


def test_markdown_import_parses_by_rule_and_reports_per_file(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
MD = """# 第07课：图形的运动

## 本节目标
认识平移和旋转。

## 教学流程
1. 观察生活中的平移

## 例题
1. 正方形向右平移三格，形状会变吗？
A. 会变
B. 不变
【答案】B
【解析】平移只改变位置。

## 课后练习
1. 用一个例子说说旋转。
【答案】风车转动。
2. 下面哪个是平移？
A. 电梯上下
B. 风扇转动
【答案】A
"""

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    unnamed = MD.replace("# 第07课：", "# ")
    files = [("files", ("第07课-图形的运动.md", MD.encode("utf-8"), "text/markdown")),
             ("files", ("没有编号.md", unnamed.encode("utf-8"), "text/markdown"))]
    r = client.post("/teacher/weekend/lessons/import/markdown", headers=th, data={"subject": "数学"}, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 1 and body["failed"] == 1, body
    assert body["items"][0]["status"] == "imported" and body["items"][0]["lessonNo"] == 7
    assert body["items"][1]["status"] == "invalid" and "课次" in body["items"][1]["error"]

    lid = body["items"][0]["lessonId"]
    detail = client.get(f"/teacher/weekend/lessons/{lid}", headers=th).json()
    assert detail["title"] == "图形的运动"
    assert "平移和旋转" in detail["coreTarget"]
    assert any("例题" in x or "正方形" in x for x in detail["examples"])
    assert "课后练习" in detail["closureTraining"]

    questions = client.get(f"/teacher/weekend/lessons/{lid}/questions", headers=th).json()["items"]
    assert len(questions) == 1 and questions[0]["stem"].startswith("下面哪个是平移")
    assert questions[0]["options"] == ["电梯上下", "风扇转动"] and questions[0]["correctIndex"] == 0
    written = client.get(f"/teacher/weekend/lessons/{lid}/written/questions", headers=th).json()["items"]
    assert len(written) == 1 and "旋转" in written[0]["stem"] and written[0]["reference"] == "风车转动。"

    # Dry run on the same file reports the conflict and writes nothing new.
    r = client.post("/teacher/weekend/lessons/import/markdown", headers=th,
                    data={"subject": "数学", "dryRun": "1"}, files=files[:1])
    assert r.json()["items"][0]["status"] == "conflict"
    assert not calls, calls
print('OK')
''')


def test_batch_import_detects_the_markdown_convention_and_skips_the_model(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
MD = """# 第08课：分数的意义

## 本节目标
理解分数的意义。

## 课后练习
1. 三分之一表示什么？
【答案】把一个整体平均分成三份取一份。
"""

PLAIN = ("第09课 教案\n本节目标：认识分数。\n教学流程\n一、导入新课。\n"
         "课后练习\n1. 用自己的话说说分数的意义。\n") * 3

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    files = [("files", ("第08课-分数的意义.md", MD.encode("utf-8"), "text/markdown")),
             ("files", ("第09课-普通教案.txt", PLAIN.encode("utf-8"), "text/plain"))]

    # The preview says which engine each file will use, without calling the model.
    r = client.post("/teacher/weekend/lessons/import/preview", headers=th, data={"subject": "数学"}, files=files)
    assert r.status_code == 200, r.text
    assert [i["engine"] for i in r.json()["items"]] == ["markdown", "ai"]
    assert not calls

    replies.append(json.dumps({"title": "分数的初步认识", "coreTarget": "认识分数", "teacherPlan": "导入",
                               "ppt": [], "examples": ["例1"], "closureTraining": "课后练习",
                               "questions": [], "writtenQuestions": []}, ensure_ascii=False))
    r = client.post("/teacher/weekend/lessons/import/batch", headers=th, data={"subject": "数学"}, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 2, body
    by_name = {i["filename"]: i for i in body["items"]}
    assert by_name["第08课-分数的意义.md"]["engine"] == "markdown"
    assert by_name["第09课-普通教案.txt"]["engine"] == "ai"
    assert len(calls) == 1, "only the free-form file may reach the model"

    lid = by_name["第08课-分数的意义.md"]["lessonId"]
    written = client.get(f"/teacher/weekend/lessons/{lid}/written/questions", headers=th).json()["items"]
    assert len(written) == 1 and "三分之一" in written[0]["stem"]
print('OK')
''')
