import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "structured_written_figure_helpers", ROOT / "tests" / "test_homework_solve.py"
)
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_structured_import_keeps_written_question_figure(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r"""
picture = "data:image/jpeg;base64,/9j/2Q=="
payload = {
    "schemaVersion": 1,
    "subject": "数学",
    "dryRun": False,
    "onConflict": "overwrite",
    "items": [{
        "lessonNo": 12,
        "title": "带原图的梯形练习",
        "coreTarget": "辨认底和高",
        "teacherPlan": "先观察原图，再计算。",
        "ppt": ["找平行底和垂直高"],
        "examples": ["一个梯形怎么求面积？"],
        "closureTraining": "订正错题",
        "questions": [],
        "writtenQuestions": [{
            "type": "short_answer",
            "material": "",
            "stem": "第1题 根据原图求梯形面积。",
            "reference": "先找对应底和高。",
            "hints": ["先找平行底。", "再找垂直高。", "最后检查单位。"],
            "figure": {
                "type": "uploaded_image",
                "data_url": picture,
                "alt": "原卷梯形图",
                "question_no": 1,
            },
        }],
    }],
}

with TestClient(app) as client:
    th, _sh, _sid, _school = setup(client)
    imported = client.post(
        "/teacher/weekend/lessons/import/structured",
        headers=th,
        json=payload,
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["imported"] == 1, imported.text
    lesson_id = imported.json()["items"][0]["lessonId"]
    questions = client.get(
        f"/teacher/weekend/lessons/{lesson_id}/written/questions",
        headers=th,
    )
    assert questions.status_code == 200, questions.text
    item = questions.json()["items"][0]
    assert item["figure"] == {
        "type": "uploaded_image",
        "data_url": picture,
        "alt": "原卷梯形图",
        "question_no": 1,
    }
    assert not calls
print("OK")
""",
        {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    )
