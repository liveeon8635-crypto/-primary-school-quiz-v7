from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hw_solve_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules["hw_solve_helpers"] = helpers
spec.loader.exec_module(helpers)


def test_cards_are_hidden_until_approved_and_link_to_wrong_questions(tmp_path):
    helpers.run_isolated(
        tmp_path,
        helpers.COMMON
        + r'''
import base64

KP = "测试知识点乙"
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    with legacy.SessionLocal() as db:
        student = db.get(legacy.User, sid)
        grade = student.grade or 3
        student.grade = grade
        db.add(legacy.WrongQuestionRecord(school_id=school_id, student_id=sid, subject="数学", knowledge=KP, problem_text="x", status="active"))
        db.add(legacy.WrongQuestionRecord(school_id=school_id, student_id=sid, subject="数学", knowledge=KP, problem_text="y", status="active"))
        db.commit()

    # page
    assert client.get("/v1/knowledge").status_code == 200

    # students cannot use teacher routes; teachers cannot use student routes
    assert client.get("/teacher/kp-cards", headers=sh).status_code == 403
    assert client.get("/student/kp-cards", headers=th).status_code == 403

    body = {"grade": grade, "subject": "数学", "knowledge": KP, "summary": "一句话", "steps": ["第一步", "第二步"], "mistakes": ["别忘了"], "examples": []}
    card = client.post("/teacher/kp-cards", headers=th, json=body).json()
    assert card["status"] == "draft"
    cid = card["id"]

    # draft: invisible to the student in search, direct fetch, and the wrong-question link
    assert client.get("/student/kp-cards", headers=sh).json()["items"] == []
    assert client.get(f"/student/kp-cards/{cid}", headers=sh).status_code == 404
    wrong = client.get("/student/kp-wrong", headers=sh).json()["items"]
    assert wrong == [{"subject": "数学", "knowledge": KP, "wrongCount": 2, "lastAt": wrong[0]["lastAt"], "cardId": None, "aiAssisted": False}]

    # an empty card cannot be published
    empty = client.post("/teacher/kp-cards", headers=th, json={**body, "knowledge": "空卡", "summary": "", "steps": []}).json()
    assert client.post(f"/teacher/kp-cards/{empty['id']}/approve", headers=th, json={"approved": True}).status_code == 400

    # image: only jpeg/png data URLs, hidden from the student until approval
    png = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
    assert client.post(f"/teacher/kp-cards/{cid}/images", headers=th, json={"data": "data:text/html;base64,AAAA"}).status_code == 400
    iid = client.post(f"/teacher/kp-cards/{cid}/images", headers=th, json={"data": png}).json()["id"]
    assert client.get(f"/kp-cards/images/{iid}", headers=sh).status_code == 404
    assert client.get(f"/kp-cards/images/{iid}", headers=th).status_code == 200

    # approve -> visible, searchable, linked
    assert client.post(f"/teacher/kp-cards/{cid}/approve", headers=th, json={"approved": True}).json()["status"] == "approved"
    found = client.get("/student/kp-cards?q=" + "乙", headers=sh).json()["items"]
    assert [c["id"] for c in found] == [cid] and found[0]["images"] == [iid] and found[0]["steps"] == ["第一步", "第二步"]
    assert client.get("/student/kp-cards?q=不存在的词", headers=sh).json()["items"] == []
    assert client.get(f"/kp-cards/images/{iid}", headers=sh).status_code == 200
    wrong = client.get("/student/kp-wrong", headers=sh).json()["items"]
    assert wrong[0]["cardId"] == cid and wrong[0]["wrongCount"] == 2

    # a card of another grade is not shown
    other = client.post("/teacher/kp-cards", headers=th, json={**body, "grade": 6 if grade != 6 else 5, "knowledge": "别的年级"}).json()
    client.post(f"/teacher/kp-cards/{other['id']}/approve", headers=th, json={"approved": True})
    assert client.get(f"/student/kp-cards/{other['id']}", headers=sh).status_code == 404
    assert all(c["id"] != other["id"] for c in client.get("/student/kp-cards", headers=sh).json()["items"])

    # editing takes the card back to draft
    edited = client.put(f"/teacher/kp-cards/{cid}", headers=th, json={**body, "summary": "改了"}).json()
    assert edited["status"] == "draft"
    assert client.get(f"/student/kp-cards/{cid}", headers=sh).status_code == 404

    # AI draft is written as a draft and never auto-approved
    replies.append(json.dumps({"summary": "AI 摘要", "steps": ["一", "二", "三"], "mistakes": ["错"], "examples": ["例"]}, ensure_ascii=False))
    drafted = client.post(f"/teacher/kp-cards/{cid}/ai-draft", headers=th).json()
    assert drafted["status"] == "draft" and drafted["summary"] == "AI 摘要" and drafted["steps"] == ["一", "二", "三"]
    assert calls[-1]["feature"] == "kp_card_draft"
    replies.append("not json at all")
    assert client.post(f"/teacher/kp-cards/{cid}/ai-draft", headers=th).status_code == 502
    assert client.get(f"/student/kp-cards/{cid}", headers=sh).status_code == 404

    # seed creates blank drafts from the question bank, idempotently
    first = client.post("/teacher/kp-cards/seed", headers=th, json={"grade": grade}).json()["created"]
    assert client.post("/teacher/kp-cards/seed", headers=th, json={"grade": grade}).json()["created"] == 0
    assert first >= 0
    print("OK")
''',
    )
