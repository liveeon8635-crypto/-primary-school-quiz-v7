from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from changying.services import weekend_courseware as cw
from changying.web.weekend_courseware_pages import COURSEWARE_JS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("weekend_courseware_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

SOURCE = "第一段。外公是一名老兵。每年国庆，他都早早换上旧军装，站在阳台上看升旗直播，眼里含着泪。他常说：“没有国，哪有家。”他把攒下的退休金捐给了家乡的学校。\n第二段。"
PASSAGE = "外公是一名老兵。每年国庆，他都早早换上旧军装，站在阳台上看升旗直播，眼里含着泪。他常说：“没有国，哪有家。”"


def test_rotation_template_is_exact_and_bounded():
    assert cw.rotate_point([5, 2], [2, 2], "cw", 90) == [2, -1] and cw.rotate_point([5, 2], [2, 2], "cw", 270) == [2, 5]
    with pytest.raises(ValueError, match="超出网格"):        # B′(2,-1) would leave the grid
        cw.clean_rotation({"width": 10, "height": 10, "shape": [[2, 2], [5, 2], [2, 4]], "center": [2, 2], "direction": "cw", "angle": 90})
    assert cw.rotate_point([5, 2], [2, 2], "ccw", 90) == [2, 5] and cw.rotate_point([5, 2], [2, 2], "cw", 180) == [-1, 2]


def test_rotation_rejects_bad_parameters():
    base = {"width": 10, "height": 10, "shape": [[4, 4], [7, 4], [4, 6]], "center": [4, 4], "direction": "cw", "angle": 90}
    assert cw.clean_rotation(base)["rotated"] == [[4, 4], [4, 1], [6, 4]]
    for change, reason in ((dict(angle=45), "90°"), (dict(direction="up"), "方向"), (dict(shape=[[1, 1], [2, 2]]), "3—6"),
                           (dict(shape=[[1.5, 1], [2, 2], [3, 1]]), "整数"), (dict(center=[9, 9]), "超出网格"),
                           (dict(width=30), "6—12")):
        with pytest.raises(ValueError, match=reason):
            cw.clean_rotation({**base, **change})


def test_reading_template_keeps_the_original_text_and_hides_answers():
    p = cw.clean_reading({"passage": PASSAGE, "question": "哪句话能说明外公热爱祖国？", "evidence": [2], "reference": "抓语言描写"}, SOURCE)
    assert len(p["sentences"]) == 3 and p["sentences"][2] == "他常说：“没有国，哪有家。”"
    with pytest.raises(ValueError, match="原文"):
        cw.clean_reading({"passage": PASSAGE.replace("老兵", "军人"), "question": "?", "evidence": [0]}, SOURCE)
    with pytest.raises(ValueError, match="文本依据"):
        cw.clean_reading({"passage": PASSAGE, "question": "?", "evidence": []}, SOURCE)
    public = cw.public_params("reading", p)
    assert "evidence" not in public and "reference" not in public
    stem, reference = cw.written_question("reading", p)
    assert PASSAGE in stem and "没有国，哪有家" in reference and "抓语言描写" not in stem


def test_template_code_never_renders_markup():
    assert "innerHTML" not in COURSEWARE_JS and "insertAdjacentHTML" not in COURSEWARE_JS and "eval(" not in COURSEWARE_JS


def test_clock_and_steps_templates():
    c = cw.clean_clock({"start": 2, "direction": "cw", "angle": 120})
    assert c["end"] == 6 and cw.clean_clock({"start": 2, "direction": "ccw", "angle": 150})["end"] == 9
    for change, reason in (({"angle": 45}, "30°"), ({"start": 13}, "1—12"), ({"direction": "x"}, "方向")):
        with pytest.raises(ValueError, match=reason):
            cw.clean_clock({"start": 2, "direction": "cw", "angle": 120, **change})
    st = cw.clean_steps({"steps": ["找中心", "定方向", "数大格"], "answer": "6", "problem": "钟面题"})
    assert st["answer"] == "6" and cw.clean_view("steps", st, {"step": 9, "showAnswer": True}) == {"step": 3, "showAnswer": True}
    with pytest.raises(ValueError, match="2—6"):
        cw.clean_steps({"steps": ["只有一步"], "answer": "6"})
    stem, ref = cw.written_question("clock", c)
    assert "从数字 2 出发，顺时针旋转 120°" in stem and "指向数字 6" in ref and "6" not in stem.replace("120", "")
    stem, ref = cw.written_question("steps", st, "例题：钟面题\n答案6")
    assert stem.startswith("钟面题") and "答案6" not in stem and "答案：6" in ref and "答案：" not in stem
    with pytest.raises(ValueError, match="题目原文"):
        cw.written_question("steps", {**st, "problem": ""}, "例题：钟面题\n答案6")


ALL = r"""
from sqlalchemy import func
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    examples = [{"title": "例题1 | 旋转方向与角度", "question": "钟面上的指针从数字2出发，顺时针旋转120°，指向数字几？", "answer": "6"},
                {"title": "例题2 | 方格中旋转作图", "question": "三角形ABC的顶点A(4,4)、B(7,4)、C(4,6)，绕点A逆时针旋转90°，画出旋转后的图形。", "answer": "见图"},
                {"title": "例题3 | 解决问题", "question": "风车每分钟转4圈，转一圈要多少秒？", "answer": "15秒"}]
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        cls = legacy.SchoolClass(school_id=school_id, name="周末五年级", grade=5, teacher_id=teacher.id); db.add(cls); db.flush()
        db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid))
        math = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=93, title="分层综合提升：旋转",
                                     core_target="旋转三要素", teacher_plan="讲例题", examples_json=json.dumps(examples, ensure_ascii=False))
        chin = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="语文", lesson_no=94, title="阅读·家国情怀", core_target="提取文本依据",
                                     reading_plan=SOURCE)
        db.add_all([math, chin]); db.flush()
        for lesson in (math, chin):
            db.add(legacy.TeachingQuestion(school_id=school_id, program_id=p.id, level="C", lesson_id=lesson.id, subject=lesson.subject,
                                           stem="热身题", options_json='["甲","乙"]', correct_index=0, active=True, knowledge="热身"))
        db.commit(); mid, cid, cls_id = math.id, chin.id, cls.id
    base = f"/teacher/weekend/lessons/{mid}/courseware"
    info = client.get(base, headers=th).json()
    assert info["templates"] == ["rotation", "clock", "steps"] and len(info["pages"]["3"]) == 3 and info["items"] == []
    assert client.get(base, headers=sh).status_code == 403
    assert client.post(base + "/generate", headers=th, json={"stageNo": 3}).status_code == 400          # paged stage needs a page

    # ---- every example page gets its own courseware; the model picks a reviewed template per page
    replies.append(json.dumps({"template": "clock", "title": "钟面指针", "start": 2, "direction": "cw", "angle": 120, "steps": ["每格30°", "顺时针数4格"]}, ensure_ascii=False))
    replies.append(json.dumps({"template": "rotation", "title": "绕点A旋转", "width": 10, "height": 10, "shape": [[4, 4], [7, 4], [4, 6]],
                               "center": [4, 4], "direction": "ccw", "angle": 90}, ensure_ascii=False))
    replies.append(json.dumps({"template": "html", "html": "<script>alert(1)</script>"}))                         # not a template
    replies.append(json.dumps({"template": "steps", "title": "转一圈要几秒", "steps": ["1分钟=60秒", "60÷4=15"], "answer": "15秒"}, ensure_ascii=False))
    manual = [json.loads(reply) for reply in replies[:2]]
    gen = [client.post(base + "/generate", headers=th, json={"stageNo": 3, "page": i}) for i in (0, 1, 2)]
    assert [g.status_code for g in gen] == [502, 502, 502] and "第 3 页" in gen[2].json()["detail"]
    assert "钟面上的指针从数字2出发" in prompts[-3] and "三角形ABC" in prompts[-2] and "钟面上的指针" not in prompts[-2]
    assert client.get(base, headers=th).json()["items"] == []
    for i, params in enumerate(manual):
        saved = client.put(base, headers=th, json={"stageNo": 3, "page": i, "kind": params["template"], "params": params})
        assert saved.status_code == 200, saved.text
    d = client.post(base + "/generate", headers=th, json={"stageNo": 3, "page": 2}).json()
    kinds = {i["page"]: (i["kind"], i["status"]) for i in d["items"]}
    assert kinds == {0: ("clock", "draft"), 1: ("rotation", "draft"), 2: ("steps", "draft")}
    assert next(i for i in d["items"] if i["page"] == 0)["params"]["end"] == 6
    assert all(not i["writtenTask"] for i in d["items"])                                                        # no homework flood by default

    # ---- drafts never reach the classroom; approve page by page
    def classroom():
        s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": mid, "classId": cls_id}).json()["id"]
        b = f"/teacher/weekend/sessions/{s}"
        client.post(b + "/start", headers=th); client.post(b + "/goto", headers=th, json={"stage": 3})
        return s, b
    s0, b0 = classroom()
    assert "courseware" not in client.get(b0 + "/board", headers=th).json()
    client.post(b0 + "/finish", headers=th)
    step_page = next(i for i in d["items"] if i["page"] == 2)
    client.put(base, headers=th, json={"stageNo": 3, "page": 2, "kind": "steps", "params": step_page["params"], "writtenTask": True})
    no_problem = client.post(base + "/approve", headers=th, json={"stageNo": 3, "page": 2})
    assert no_problem.status_code == 400 and "题目原文" in no_problem.json()["detail"]     # the board page carries the answer
    client.put(base, headers=th, json={"stageNo": 3, "page": 2, "kind": "steps", "writtenTask": True,
                                       "params": {**step_page["params"], "problem": "风车每分钟转4圈，转一圈要多少秒？"}})
    for i in (0, 1, 2):
        assert client.post(base + "/approve", headers=th, json={"stageNo": 3, "page": i}).status_code == 200
    templates = [q for q in client.get(f"/teacher/weekend/lessons/{mid}/written/questions", headers=th).json()["items"] if q.get("courseware")]
    assert len(templates) == 1 and "风车每分钟转4圈" in templates[0]["stem"] and "15秒" in templates[0]["reference"]

    # ---- in class: each page shows its own courseware under the page's text; turning pages never calls AI
    s1, b1 = classroom()
    seen = []
    ai_calls = len(calls)
    for i in range(3):
        board = client.get(b1 + "/board", headers=th).json()
        seen.append((board["deck"]["index"], board["courseware"]["kind"], board["courseware"]["page"]))
        assert board["courseware"]["view"]["step"] == 0
        assert client.get(b1, headers=th).json()["courseware"]["view"] == board["courseware"]["view"]
        assert examples[i]["question"][:6] in board["content"][0]
        client.post(b1 + "/slide", headers=th, json={"delta": 1})
    assert seen == [(0, "clock", 0), (1, "rotation", 1), (2, "steps", 2)] and len(calls) == ai_calls
    v = client.post(b1 + "/courseware/view", headers=th, json={"view": {"step": 1, "showAnswer": True}}).json()["view"]
    assert v == {"step": 1, "showAnswer": True}
    assert client.get(b1 + "/board", headers=th).json()["courseware"]["view"] == v
    assert client.get(b1, headers=th).json()["courseware"]["view"] == v
    # An old approved item can be repaired for display with more steps than its saved version.
    import changying.web.weekend_courseware as courseware_web
    repair = courseware_web._repair_courseware_visual
    def expanded(params, text):
        result = dict(repair(params, text))
        result["steps"] = list(result["steps"]) + ["额外讲解一", "额外讲解二"]
        return result
    courseware_web._repair_courseware_visual = expanded
    displayed = client.get(b1 + "/board", headers=th).json()["courseware"]
    last_step = len(displayed["params"]["steps"])
    assert last_step > len(step_page["params"]["steps"])
    response = client.post(b1 + "/courseware/view", headers=th, json={"stageNo": 3, "page": 2, "view": {"step": last_step}})
    assert response.status_code == 200 and response.json()["view"]["step"] == last_step
    assert client.get(b1 + "/board", headers=th).json()["courseware"]["view"]["step"] == last_step
    courseware_web._repair_courseware_visual = repair
    client.post(b1 + "/courseware/view", headers=th, json={"stageNo": 3, "page": 2, "view": v})
    client.post(b1 + "/slide", headers=th, json={"delta": -2})
    assert client.get(b1 + "/board", headers=th).json()["courseware"]["view"]["angle"] == 0                    # page 1 keeps its own state
    stale = client.post(b1 + "/courseware/view", headers=th, json={"stageNo": 3, "page": 2, "view": {"step": 2, "showAnswer": True}})
    assert stale.status_code == 409
    assert client.get(b1 + "/board", headers=th).json()["courseware"]["view"]["angle"] == 0
    assert client.post(b1 + "/courseware/view", headers=th, json={"view": {"angle": 999}}).json()["view"]["angle"] == 120
    client.post(b1 + "/slide", headers=th, json={"delta": 2})
    assert client.get(b1 + "/board", headers=th).json()["courseware"]["view"]["showAnswer"] is True
    reset = client.post(b1 + "/courseware/view", headers=th, json={"stageNo": 3, "page": 2, "view": {"step": 0, "showAnswer": False}})
    assert reset.json()["view"] == {"step": 0, "showAnswer": False}
    assert client.get(b1 + "/board", headers=th).json()["courseware"]["view"] == reset.json()["view"]
    client.post(b1 + "/goto", headers=th, json={"stage": 4})
    # This scenario explicitly opens its exercises before testing student work.
    for ordinal in range(1, client.get(b1, headers=th).json()['answerRelease']['total'] + 1):
        assert client.post(b1+'/practice-question', headers=th, json={'question':ordinal}).status_code == 200
    mine = client.get(f"/student/weekend/sessions/{s1}/written", headers=sh).json()
    # A task copied verbatim from a worked example is not an eligible practice item.
    assert all("风车每分钟转4圈" not in q["stem"] for q in mine["questions"])
    assert "15秒" not in json.dumps(mine, ensure_ascii=False)
    teacher_tasks = client.get(b1 + "/written", headers=th).json()["questions"]
    task = next(q for q in teacher_tasks if "风车每分钟转4圈" in q["stem"])
    task_url = f"/student/weekend/sessions/{s1}/written/{task['id']}"
    assert client.post(task_url + "/hint", headers=sh).status_code == 404
    assert client.post(task_url, headers=sh, data={"text": "60÷4=15秒", "revision": "0"}).status_code == 404
    client.post(b1 + "/finish", headers=th)

    # A new classroom never reuses the prior session's screen state.
    new_session, new_base = classroom()
    client.post(new_base + "/slide", headers=th, json={"delta": 2})
    assert client.get(new_base + "/board", headers=th).json()["courseware"]["view"] == {"step": 0, "showAnswer": False}
    client.post(new_base + "/finish", headers=th)

    # ---- removing a page's courseware hides it; the other pages stay
    client.post(base + "/remove", headers=th, json={"stageNo": 3, "page": 1})
    s2, b2 = classroom()
    client.post(b2 + "/slide", headers=th, json={"delta": 1})
    st = client.get(b2, headers=th).json()
    assert "courseware" not in st and "第 1、3 页有互动课件" in st["coursewareNotice"]
    client.post(b2 + "/finish", headers=th)

    # ---- a pilot row (one courseware) is read as one item and keeps working
    t = legacy.Base.metadata.tables["weekend_courseware"]
    pilot = cw.clean_rotation({"width": 10, "height": 10, "shape": [[4, 4], [7, 4], [4, 6]], "center": [4, 4], "direction": "cw", "angle": 90})
    with legacy.SessionLocal() as db:
        db.execute(t.update().where(t.c.lesson_id == mid).values(kind="rotation", stage_no=3, status="approved", approved_stage=3,
            params_json=json.dumps({**pilot, "page": 1}), approved_json=json.dumps({**pilot, "page": 1}), template_id=None))
        db.commit()
    legacy_items = client.get(base, headers=th).json()["items"]
    assert [(i["page"], i["kind"], i["status"]) for i in legacy_items] == [(1, "rotation", "approved")]
    s3, b3 = classroom()
    client.post(b3 + "/slide", headers=th, json={"delta": 1})
    assert client.get(b3 + "/board", headers=th).json()["courseware"]["kind"] == "rotation"
    client.post(b3 + "/finish", headers=th)

    # ---- 语文: the reading template still keeps the original text and hides the evidence
    cbase = f"/teacher/weekend/lessons/{cid}/courseware"
    assert client.get(cbase, headers=th).json()["templates"] == ["reading", "steps"]
    replies.append(json.dumps({"template": "clock", "start": 1, "direction": "cw", "angle": 30}))           # not allowed for 语文
    assert client.post(cbase + "/generate", headers=th, json={"stageNo": 2}).status_code == 502
    replies.append(json.dumps({"template": "reading", "title": "找文本依据", "passage": PASSAGE, "question": "哪句话最能说明外公热爱祖国？",
                               "evidence": [2], "reference": "语言描写"}, ensure_ascii=False))
    d = client.post(cbase + "/generate", headers=th, json={"stageNo": 2}).json()
    assert d["items"][0]["page"] is None and d["items"][0]["kind"] == "reading"
    client.post(cbase + "/approve", headers=th, json={"stageNo": 2})
    s4 = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": cid, "classId": cls_id}).json()["id"]
    client.post(f"/teacher/weekend/sessions/{s4}/start", headers=th); client.post(f"/teacher/weekend/sessions/{s4}/goto", headers=th, json={"stage": 2})
    c = client.get(f"/teacher/weekend/sessions/{s4}/board", headers=th).json()["courseware"]
    assert c["kind"] == "reading" and "evidence" not in c["params"] and "reference" not in c["params"]

    plan = client.get("/v1/weekend-plan").text
    for text in ("为本环节全部", "全部草稿审核通过", "包括已有课件的页", "审核后同时生成学生书面作答题", "/courseware/remove", "cwPlan("):
        assert text in plan, text
    board = client.get("/v1/weekend-board").text
    assert "cwClock(" in board and "cwSteps(" in board and "cwRender(cwBox,d.courseware" in board
    print("OK")
"""


def test_every_example_page_gets_its_own_reviewed_courseware(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + f"SOURCE = {SOURCE!r}\nPASSAGE = {PASSAGE!r}\nimport changying.services.weekend_courseware as cw\n" + ALL)
