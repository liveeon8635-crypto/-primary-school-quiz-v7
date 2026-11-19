from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "bundle_import_helpers", ROOT / "tests" / "test_homework_solve.py"
)
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_one_json_file_imports_plan_questions_and_pending_practice_courseware(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
STEMS = [
    "第1题　梯形上底4厘米、下底8厘米、高5厘米，求面积。",
    "第2题　梯形上底6厘米、下底10厘米、高4厘米，求面积。",
]


def page(stage, index, text, answer):
    frame = {
        "type": "uploaded_image",
        "data_url": "data:image/jpeg;base64,/9j/2Q==",
        "alt": "分步图",
    }
    return {
        "stageNo": stage,
        "page": index,
        "expectedPageText": text,
        "kind": "steps",
        "writtenTask": False,
        "params": {
            "title": "分步讲解",
            "problem": text,
            "steps": ["先找对应的底和高", "代入梯形面积公式并检查单位"],
            "answer": answer,
            "stepFigures": [frame, frame, frame],
        },
    }


bundle = {
    "schemaVersion": 1,
    "subject": "数学",
    "dryRun": True,
    "onConflict": "overwrite",
    "items": [{
        "lessonNo": 12,
        "title": "梯形面积同步课",
        "coreTarget": "认识梯形对应的底和高，能分步计算面积。",
        "teacherPlan": "先辨认底高，再推导公式，最后完成两道随堂练习。",
        "ppt": ["梯形的底和高：高必须垂直于两条平行底。"],
        "examples": [
            "例1 上底3厘米、下底5厘米、高4厘米，求面积。\n【答案】16平方厘米。",
            "例2 上底2厘米、下底6厘米、高3厘米，求面积。\n【答案】12平方厘米。",
        ],
        "closureTraining": "订正课堂错题。",
        "questions": [],
        "writtenQuestions": [
            {"type": "short_answer", "material": "", "stem": STEMS[0],
             "reference": "(4+8)×5÷2=30平方厘米。", "hints": []},
            {"type": "short_answer", "material": "", "stem": STEMS[1],
             "reference": "(6+10)×4÷2=32平方厘米。", "hints": []},
        ],
    }],
    "courseware": {
        "dryRun": True,
        "replaceExisting": True,
        "pages": [
            page(2, 0, "梯形的底和高：高必须垂直于两条平行底。", "高⊥底。"),
            page(4, 0, STEMS[0], "30平方厘米。"),
            page(4, 1, STEMS[1], "32平方厘米。"),
        ],
    },
}

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    url = "/teacher/weekend/lessons/import"

    broken = json.loads(json.dumps(bundle))
    broken["courseware"]["pages"][1]["expectedPageText"] = "不存在的题目"
    failed = client.post(
        url,
        headers=th,
        data={"subject": "数学", "lessonNo": "12", "force": "0"},
        files={"file": ("第12课-整包.json", json.dumps(broken, ensure_ascii=False).encode("utf8"), "application/json")},
    )
    assert failed.status_code == 409, failed.text
    schedule = client.get("/teacher/weekend/schedule?subject=数学", headers=th).json()
    assert not schedule["items"][11]["hasPlan"]

    imported = client.post(
        url,
        headers=th,
        data={"subject": "数学", "lessonNo": "12", "force": "0"},
        files={"file": ("第12课-整包.json", json.dumps(bundle, ensure_ascii=False).encode("utf8"), "application/json")},
    )
    assert imported.status_code == 200, imported.text
    result = imported.json()
    assert result["questionsFound"] == 2
    assert result["coursewarePagesFound"] == 3
    lid = result["lessonId"]

    written = client.get(f"/teacher/weekend/lessons/{lid}/written/questions", headers=th).json()
    assert [q["stem"] for q in written["items"]] == STEMS
    courseware = client.get(f"/teacher/weekend/lessons/{lid}/courseware", headers=th).json()
    assert {(i["stage"], i["page"]) for i in courseware["items"]} == {(2, 0), (4, 0), (4, 1)}
    assert all(i["status"] == "draft" and i["approved"] is None for i in courseware["items"])
    assert all(not i["params"].get("figureUnverified") for i in courseware["items"])

    approved = client.post(
        f"/teacher/weekend/lessons/{lid}/written/questions",
        headers=th,
        json={"approve": [q["id"] for q in written["items"]]},
    )
    assert approved.status_code == 200, approved.text
    courseware = client.get(f"/teacher/weekend/lessons/{lid}/courseware", headers=th).json()
    stage4 = [i for i in courseware["items"] if i["stage"] == 4]
    assert len(stage4) == 2 and all(not i["needsSync"] for i in stage4)
    approved_page = client.post(
        f"/teacher/weekend/lessons/{lid}/courseware/approve",
        headers=th,
        json={"stageNo": 4, "page": 0},
    )
    assert approved_page.status_code == 200, approved_page.text
print("OK")
''',
    )
