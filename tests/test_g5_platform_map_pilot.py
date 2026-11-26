"""The teacher can plan against the built-in G5 outline without exposing a pupil map."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("g5_pilot_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

FLOW = r'''
with TestClient(app) as client:
    teacher, student, sid, school_id = setup(client)
    assert client.get("/teacher/knowledge-maps/baseline", headers=student).status_code == 403
    baseline = client.get("/teacher/knowledge-maps/baseline", headers=teacher).json()
    assert baseline["key"] == "rj2026-g5-math-up"
    assert len(baseline["map"]["nodes"]) == 41
    assert not any(unit["learned"] for unit in baseline["map"]["units"])
    assert all(not node["levels"] for node in baseline["map"]["nodes"])
    assert "网站基础知识地图" in client.get("/v1/knowledge-map").text
    assert "/teacher/knowledge-maps/baseline" in client.get("/v1/knowledge-map").text
    assert "网站自带五上数学知识地图" in client.get("/v1/exam-prep").text
    goals = client.get("/teacher/exam-goals", headers=teacher).json()
    assert goals["maps"] == [] and goals["baseline"]["units"][1]["name"] == "小数乘法"

    created = client.post("/teacher/knowledge-maps", headers=teacher,
                          json={"template": baseline["key"], "baseline": True})
    assert created.status_code == 200, created.text
    school_map = created.json()
    assert school_map["summary"]["learnedUnits"] == 0
    assert school_map["summary"]["assessed"] == 0
    assert school_map["published"] is None
    assert client.get("/student/knowledge-map", headers=student).status_code == 404
    assert client.post("/teacher/knowledge-maps", headers=teacher,
                       json={"template": baseline["key"], "baseline": True}).status_code == 409

    goals = client.get("/teacher/exam-goals", headers=teacher).json()
    assert goals["baseline"] is None
    assert len(goals["maps"]) == 1 and goals["maps"][0]["published"] is False
    with legacy.SessionLocal() as db:
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id))
        cls.grade = 5
        class_id = cls.id
        db.get(legacy.User, sid).grade = 5
        db.commit()
    goal = client.post("/teacher/exam-goals", headers=teacher,
                       json={"mapId": school_map["id"], "classId": class_id, "title": "五上试点",
                             "examDate": "2027-06-01", "unitKeys": ["U2"]})
    assert goal.status_code == 200, goal.text
    # Planning is possible; publishing a paper still requires reviewed, usable questions.
    mock = client.post(f"/teacher/exam-goals/{goal.json()['id']}/mock", headers=teacher,
                       json={"count": 6, "timeLimit": 30})
    assert mock.status_code == 409 and "至少要 6 道" in mock.json()["detail"]
    with legacy.SessionLocal() as db:
        ids = []
        for i in range(6):
            q = legacy.Question(school_id=school_id, grade=5, subject="数学", textbook="人教版2026",
                                semester="上册", unit="小数乘法", knowledge="小数乘整数",
                                text=f"{i + 2}×3 等于多少？", options_json=json.dumps([str((i + 2) * 3), "1", "2", "3"]),
                                correct_index=0, question_type="single_choice", explanation="整数乘法")
            db.add(q); db.flush(); ids.append(q.id)
        db.commit()
    unreviewed = client.post(f"/teacher/exam-goals/{goal.json()['id']}/mock", headers=teacher,
                             json={"count": 6, "timeLimit": 30})
    assert unreviewed.status_code == 409  # merely matching a name does not review a question
    levels = dict(zip(map(str, ids), ["basic", "basic", "medium", "medium", "hard", "hard"]))
    review = client.put(f"/teacher/knowledge-maps/{school_map['id']}/nodes/2-1/levels", headers=teacher,
                        json={"levels": levels, "revision": school_map["revision"]})
    assert review.status_code == 200, review.text
    mock = client.post(f"/teacher/exam-goals/{goal.json()['id']}/mock", headers=teacher,
                       json={"count": 6, "timeLimit": 30})
    assert mock.status_code == 200 and mock.json()["questionCount"] == 6, mock.text
    assert client.get("/student/exam-papers", headers=student).json()["items"][0]["assignmentId"] == mock.json()["assignmentId"]
    assert client.get("/student/knowledge-map", headers=student).status_code == 404
    # Publishing the map must not promote old same-name bank questions into the paper.
    with legacy.SessionLocal() as db:
        for i in range(6):
            db.add(legacy.Question(school_id=school_id, grade=5, subject="数学", textbook="旧版人教版",
                                   semester="上册", unit="小数乘法", knowledge="小数乘整数",
                                   text=f"旧版题 {i}？", options_json=json.dumps(["3", "1", "2", "4"]),
                                   correct_index=0, question_type="single_choice", explanation="旧版题"))
        db.commit()
    latest = client.get(f"/teacher/knowledge-maps/{school_map['id']}", headers=teacher).json()
    draft = latest["map"]
    next(u for u in draft["units"] if u["key"] == "U2")["learned"] = True
    saved = client.put(f"/teacher/knowledge-maps/{school_map['id']}", headers=teacher,
                       json={"map": draft, "revision": latest["revision"]})
    assert saved.status_code == 200, saved.text
    published = client.post(f"/teacher/knowledge-maps/{school_map['id']}/publish", headers=teacher,
                            json={"revision": saved.json()["revision"]})
    assert published.status_code == 200, published.text
    after_publish = client.post(f"/teacher/exam-goals/{goal.json()['id']}/mock", headers=teacher,
                                json={"count": 12, "timeLimit": 30})
    assert after_publish.status_code == 200 and after_publish.json()["questionCount"] == 6, after_publish.text
    with legacy.SessionLocal() as db:
        assignment = db.get(legacy.Assignment, after_publish.json()["assignmentId"])
        assert set(json.loads(db.get(legacy.Paper, assignment.paper_id).question_ids_json)) == set(ids)
print("OK")
'''


def test_baseline_preview_and_exam_goal_without_student_publication(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW, {"KNOWLEDGE_MAP": "1"})
