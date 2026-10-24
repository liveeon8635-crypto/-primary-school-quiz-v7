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


FLOW = r'''
from sqlalchemy import func
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        cls = legacy.SchoolClass(school_id=school_id, name="周末五年级", grade=5, teacher_id=teacher.id); db.add(cls); db.flush()
        db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid))
        math = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=95, title="图形的旋转", core_target="会画旋转后的图形",
                                     teacher_plan="例题：三角形绕点旋转90度")
        chin = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="语文", lesson_no=94, title="阅读·家国情怀", core_target="提取文本依据",
                                     reading_plan=SOURCE)
        db.add_all([math, chin]); db.flush()
        for lesson in (math, chin):
            db.add(legacy.TeachingQuestion(school_id=school_id, program_id=p.id, level="C", lesson_id=lesson.id, subject=lesson.subject,
                                           stem="热身题", options_json='["甲","乙"]', correct_index=0, active=True, knowledge="热身"))
        db.commit(); mid, cid, cls_id = math.id, chin.id, cls.id

    # ---- preparation: AI fills template parameters; invalid output is rejected and nothing is saved
    replies.append(json.dumps({"width": 10, "height": 10, "shape": [[2, 2], [5, 2], [2, 4]], "center": [2, 2], "direction": "cw", "angle": 45}))
    bad = client.post(f"/teacher/weekend/lessons/{mid}/courseware/generate", headers=th, json={"stageNo": 3})
    assert bad.status_code == 502 and "未通过校验" in bad.json()["detail"]
    assert client.get(f"/teacher/weekend/lessons/{mid}/courseware", headers=th).json()["item"] is None
    replies.append(json.dumps({"title": "<script>alert(1)</script>三角形旋转", "width": 10, "height": 10, "shape": [[4, 4], [7, 4], [4, 6]],
                               "center": [4, 4], "direction": "cw", "angle": 90, "steps": ["找中心", "看方向", "定角度"], "question": "写出旋转后的坐标",
                               "reference": "A′(4,4)"}, ensure_ascii=False))
    d = client.post(f"/teacher/weekend/lessons/{mid}/courseware/generate", headers=th, json={"stageNo": 3}).json()
    assert d["item"]["status"] == "draft" and d["item"]["params"]["rotated"] == [[4, 4], [4, 1], [6, 4]]
    assert d["item"]["params"]["title"].startswith("<script>")          # kept as plain text; templates render with textContent
    assert "A(4,4)、B(7,4)、C(4,6)" in d["item"]["writtenTask"]["stem"] and "A′(4,4)、B′(4,1)、C′(6,4)" in d["item"]["writtenTask"]["reference"]
    assert client.get(f"/teacher/weekend/lessons/{mid}/courseware", headers=sh).status_code == 403
    # teacher edit, then approve
    edited = {**d["item"]["params"], "title": "三角形绕点O旋转"}
    assert client.put(f"/teacher/weekend/lessons/{mid}/courseware", headers=th, json={"stageNo": 3, "params": {**edited, "angle": 45}}).status_code == 400
    d = client.put(f"/teacher/weekend/lessons/{mid}/courseware", headers=th, json={"stageNo": 3, "params": edited}).json()
    assert d["item"]["status"] == "draft" and d["item"]["params"]["title"] == "三角形绕点O旋转"

    def classroom(lid):
        s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": lid, "classId": cls_id}).json()["id"]
        client.post(f"/teacher/weekend/sessions/{s}/start", headers=th)
        return s, f"/teacher/weekend/sessions/{s}"

    # a draft never reaches a classroom
    s0, b0 = classroom(mid)
    client.post(b0 + "/goto", headers=th, json={"stage": 3})
    assert "courseware" not in client.get(b0 + "/board", headers=th).json()
    client.post(b0 + "/finish", headers=th)

    a = client.post(f"/teacher/weekend/lessons/{mid}/courseware/approve", headers=th).json()
    assert a["item"]["status"] == "approved" and a["item"]["templateId"]
    t = client.get(f"/teacher/weekend/lessons/{mid}/written/questions", headers=th).json()["items"]
    assert any(q["id"] == a["item"]["templateId"] and q["approved"] and q["courseware"] == a["item"]["id"] for q in t)

    # ---- class: stage 3 shows it on the board; dragging and turning store screen state only, no AI
    s1, b1 = classroom(mid)
    client.post(b1 + "/goto", headers=th, json={"stage": 2})
    assert "courseware" not in client.get(b1 + "/board", headers=th).json()
    client.post(b1 + "/goto", headers=th, json={"stage": 3})
    board = client.get(b1 + "/board", headers=th).json()["courseware"]
    assert board["kind"] == "rotation" and board["view"]["angle"] == 0 and "reference" not in board["params"]
    ai_calls = len(calls)
    v = client.post(b1 + "/courseware/view", headers=th, json={"view": {"angle": 45, "showResult": False, "step": 2}}).json()["view"]
    assert v["angle"] == 45 and v["step"] == 2
    assert client.post(b1 + "/courseware/view", headers=th, json={"view": {"angle": 999}}).json()["view"]["angle"] == 90
    assert client.get(b1 + "/board", headers=th).json()["courseware"]["view"]["angle"] == 90
    client.post(b1 + "/slide", headers=th, json={"delta": 1})
    assert len(calls) == ai_calls
    assert client.post(b1 + "/courseware/view", headers=sh, json={"view": {}}).status_code == 403
    client.post(b1 + "/cover", headers=th, json={"covered": True})
    assert "courseware" not in client.get(b1 + "/board", headers=th).json()
    client.post(b1 + "/cover", headers=th, json={"covered": False})

    # ---- pupils answer the courseware task in the existing written flow; the reference stays hidden until released
    client.post(b1 + "/goto", headers=th, json={"stage": 4})
    assert client.post(b1 + "/courseware/view", headers=th, json={"view": {}}).status_code == 409
    mine = client.get(f"/student/weekend/sessions/{s1}/written", headers=sh).json()
    task = next(q for q in mine["questions"] if "绕点 O(4,4) 顺时针旋转 90°" in q["stem"])
    assert "A′(4,1)" not in json.dumps(mine, ensure_ascii=False) and "reference" not in json.dumps(mine)
    r = client.post(f"/student/weekend/sessions/{s1}/written/{task['id']}", headers=sh, data={"text": "A′(4,4) B′(4,1) C′(6,4)", "revision": "0"})
    assert r.status_code == 200, r.text
    items = client.get(b1 + "/written", headers=th).json()["items"]
    sub = next(i for i in items if i["questionId"] == task["id"])
    assert sub["result"] == "pending"                                    # no keyword auto-marking; the teacher reviews
    ok = client.post(b1 + "/written/review-batch", headers=th, json={"items": [{"id": sub["id"], "revision": sub["revision"], "result": "correct", "comment": ""}]})
    assert ok.status_code == 200
    client.post(b1 + "/finish", headers=th)

    # ---- 语文: the passage must be the lesson's own text; evidence and reference never reach the board
    replies.append(json.dumps({"passage": "一段编造的文字，原文里没有这一句，也没有那一句。还要再长一点才够四十个字呢，是的。", "question": "?", "evidence": [0]}, ensure_ascii=False))
    assert client.post(f"/teacher/weekend/lessons/{cid}/courseware/generate", headers=th, json={"stageNo": 2}).status_code == 502
    replies.append(json.dumps({"title": "找文本依据", "passage": PASSAGE, "question": "哪句话最能说明外公热爱祖国？", "evidence": [2],
                               "material": "老兵：曾经服过兵役的人。", "writingPrompt": "摘录原文并说明理由。", "reference": "语言描写直接表达"}, ensure_ascii=False))
    d = client.post(f"/teacher/weekend/lessons/{cid}/courseware/generate", headers=th, json={"stageNo": 2}).json()
    assert d["item"]["params"]["evidence"] == [2]
    client.post(f"/teacher/weekend/lessons/{cid}/courseware/approve", headers=th)
    s2, b2 = classroom(cid)
    client.post(b2 + "/goto", headers=th, json={"stage": 2})
    c = client.get(b2 + "/board", headers=th).json()["courseware"]
    assert c["kind"] == "reading" and len(c["params"]["sentences"]) == 3 and "evidence" not in c["params"] and "reference" not in c["params"]
    v = client.post(b2 + "/courseware/view", headers=th, json={"view": {"highlight": [2, 2, 99], "showMaterial": True}}).json()["view"]
    assert v == {"highlight": [2], "showMaterial": True, "showPrompt": False}
    client.post(b2 + "/goto", headers=th, json={"stage": 4})
    mine = client.get(f"/student/weekend/sessions/{s2}/written", headers=sh).json()
    task = next(q for q in mine["questions"] if PASSAGE in q["stem"])
    assert "语言描写直接表达" not in json.dumps(mine, ensure_ascii=False) and "文本依据：" not in json.dumps(mine, ensure_ascii=False)
    assert client.post(f"/student/weekend/sessions/{s2}/written/{task['id']}", headers=sh, data={"text": "依据：没有国，哪有家。", "revision": "0"}).status_code == 200
    assert next(i for i in client.get(b2 + "/written", headers=th).json()["items"] if i["questionId"] == task["id"])["result"] == "pending"

    # ---- pages are wired: plan entry, control controls, board renderer
    plan = client.get("/v1/weekend-plan").text
    assert "生成互动课件" in plan and "/courseware/generate" in plan and "审核通过，用于课堂" in plan and "cwPlan(" in plan
    control = client.get("/v1/weekend").text
    assert "cwControl(cwBox,d.courseware,SID)" in control and "/courseware/view" in control
    assert "cwRender(body,d.courseware" in client.get("/v1/weekend-board").text
    print("OK")
'''


def test_courseware_preparation_class_play_and_written_answers(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + f"SOURCE = {SOURCE!r}\nPASSAGE = {PASSAGE!r}\n" + FLOW)
