"""Feedback #337: 教材题库 — photograph questions, AI recognises them (any type),
teacher reviews, questions go straight into the question bank."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_catalog_page_offers_photo_import_and_typed_answer_badges():
    import app_v924 as legacy
    from changying.web.classic_ui import inject_classic_ui
    from changying.web.paper_import_ui import CATALOG_PHOTO_IMPORT_MARKER, patch_classic_catalog_photo_import

    html = inject_classic_ui(legacy.INDEX_HTML)
    catalog = html[html.find("async function catalog(){"):html.find("function questionForm(){")]
    assert CATALOG_PHOTO_IMPORT_MARKER in catalog and 'id="importQ"' in catalog
    assert 'window.importPaperForm([],{mode:"bank"})' in catalog
    assert "window.catalogAnswerBadge(q)" in catalog and "q.options[q.correctIndex]" not in catalog
    assert "create_paper:false" in html and 'go("catalog")' in html
    assert inject_classic_ui(html) == html
    # The catalog entry relies on the import script; without it the page is left untouched.
    assert patch_classic_catalog_photo_import(legacy.INDEX_HTML) == legacy.INDEX_HTML


RUNTIME = r"""
import json
from fastapi.testclient import TestClient
import app_v924 as legacy
from app import app

AI_REPLY = json.dumps({"questions": [
    {"question_type": "fill_blank", "text": "一个数的 3 倍是 27，这个数是____", "answer": "9", "answer_source": "ai", "knowledge": "倍数"},
    {"question_type": "true_false", "text": "两个奇数的和一定是偶数。", "correct_index": 0, "answer_source": "ai",
     "figure": {"image": 2, "box": [0.1, 0.1, 0.4, 0.4]}},
    {"question_type": "calculation", "text": "如图，长方形的周长是多少厘米？", "answer": "20", "answer_source": "paper",
     "figure": {"image": 0, "box": [0.1, 0.2, 0.6, 0.5]}},
    {"question_type": "single_choice", "text": "下面是质数的是", "options": ["9", "15", "17"], "correct_index": 2},
]}, ensure_ascii=False)
calls = []
legacy._ai_call = lambda db, u, feature, prompt, images=None, timeout=90: calls.append((feature, len(images or []))) or AI_REPLY

def headers_for(db, username):
    user = db.scalar(legacy.select(legacy.User).where(legacy.User.username == username))
    sec = legacy.security_for(db, user); sec.must_change_password = False; db.commit()
    return {"Authorization": "Bearer " + legacy.make_token(user, sec, False)}

PHOTO = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ=="
with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        th, ah, sh = headers_for(db, "teacher1"), headers_for(db, "admin"), headers_for(db, "student1")
        papers_before = db.scalar(legacy.select(legacy.func.count()).select_from(legacy.Paper))
    scope = {"grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册", "unit": "因数与倍数"}

    parsed = client.post("/teacher/papers/import/parse", headers=th, json={**scope, "images": [PHOTO]})
    assert parsed.status_code == 200, parsed.text
    assert calls == [("paper_import", 1)]
    items = parsed.json()["items"]
    assert [x["question_type"] for x in items] == ["fill_blank", "true_false", "calculation", "single_choice"]
    # Feedback #357 r2: figure questions are kept with a crop box; only the photos they point into come back.
    assert items[2]["figureRegion"] == {"image": 0, "box": [0.1, 0.2, 0.6, 0.5]}
    assert "figureRegion" not in items[1]  # there is no image 2 in this import
    assert parsed.json()["sourceImages"] == {}  # the browser still has its own photo 0
    assert parsed.json()["summary"]["figures"] == 1 and "裁出插图" in parsed.json()["notice"]
    CROP = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ=="
    items[2]["figure"] = {"type": "uploaded_image", "data_url": CROP, "alt": "题目插图"}
    items[0]["figure"] = {"type": "uploaded_image", "data_url": "data:text/html;base64,PGI+"}  # never stored

    saved = client.post("/teacher/papers/import/save", headers=th, json={**scope, "title": "题库导入", "questions": items, "create_paper": False})
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["savedCount"] == 4 and body["typeSummary"] == "单选1 · 判断1 · 填空1 · 计算1"
    assert "id" not in body and "assignment" not in body
    bank = {q["id"]: q for q in client.get("/questions?grade=5&subject=数学&unit=因数与倍数", headers=th).json()}
    assert {bank[i]["questionType"] for i in body["questionIDs"]} == {"fill_blank", "true_false", "calculation", "single_choice"}
    assert bank[body["questionIDs"][0]]["answer"] == "9"
    assert bank[body["questionIDs"][2]]["figure"] == {"type": "uploaded_image", "data_url": CROP, "alt": "题目插图"}
    assert bank[body["questionIDs"][0]]["figure"] == {}
    with legacy.SessionLocal() as db:
        assert db.scalar(legacy.select(legacy.func.count()).select_from(legacy.Paper)) == papers_before

    # The new questions feed balanced composition right away.
    composed = client.post("/teacher/papers/compose", headers=th, json={**scope, "title": "因数与倍数练习", "count": 4})
    assert composed.status_code == 200 and len(composed.json()["typeDistribution"]) == 4, composed.text

    assert client.post("/teacher/papers/import/parse", headers=ah, json={**scope, "text": "1. 2+2=__ 答案 4"}).status_code == 200
    admin_bank = client.post("/teacher/papers/import/save", headers=ah, json={**scope, "questions": [{**items[0], "text": items[0]["text"] + "（新）"}], "create_paper": False})
    assert admin_bank.status_code == 200 and admin_bank.json()["savedCount"] == 1, admin_bank.text
    same_again = client.post("/teacher/papers/import/save", headers=ah, json={**scope, "questions": [items[0]], "create_paper": False})
    assert same_again.json()["savedCount"] == 0 and same_again.json()["reusedCount"] == 1, same_again.text  # #370: no duplicate
    # feedback #370: change the 单元 (and 教材) of imported questions
    mine = body["questionIDs"][:2]
    admins = admin_bank.json()["questionIDs"]
    assert client.post("/teacher/questions/unit", headers=th, json={"ids": mine, "unit": " "}).status_code == 400
    assert client.post("/teacher/questions/unit", headers=th, json={"ids": [], "unit": "测试用新单元"}).status_code == 400
    assert client.post("/teacher/questions/unit", headers=sh, json={"ids": mine, "unit": "测试用新单元"}).status_code == 403
    edited = client.post("/teacher/questions/unit", headers=th, json={"ids": mine + admins, "unit": "测试用新单元", "textbook": "北师大版"})
    assert edited.status_code == 200 and edited.json() == {"updated": 2, "skipped": 1}, edited.text  # the admin's question is not theirs
    moved = {q["id"]: q for q in client.get("/questions?grade=5&subject=数学&unit=测试用新单元", headers=th).json()}
    assert set(moved) == set(mine) and all(q["textbook"] == "北师大版" for q in moved.values())
    admin_edit = client.post("/teacher/questions/unit", headers=ah, json={"ids": mine + admins, "unit": "测试用新单元二"})
    assert admin_edit.json() == {"updated": 3, "skipped": 0}
    assert client.post("/teacher/questions/unit", headers=ah, json={"ids": mine, "unit": "测试用新单元二", "textbook": ""}).status_code == 400
    assert client.post("/teacher/papers/import/save", headers=ah, json={**scope, "title": "x", "questions": [items[0]]}).status_code == 403
    assert client.post("/teacher/papers/import/save", headers=th, json={**scope, "questions": [items[0]], "create_paper": False, "class_id": 1}).status_code == 400
    assert client.post("/teacher/papers/import/parse", headers=sh, json={**scope, "text": "x"}).status_code == 403

    # Feedback #357: a scanned PDF reaches the AI as page images, alongside any photos.
    import os
    calls.clear()
    pdf = client.post("/teacher/papers/import/parse", headers=th,
                      json={**scope, "file_name": "期中扫描.pdf", "file_base64": os.environ["SCANNED_PDF_B64"], "images": [PHOTO]})
    assert pdf.status_code == 200, pdf.text
    assert calls == [("paper_import", 3)]
    # image 0 is the teacher's photo (kept in the browser); image 2 is a PDF scan, so only it comes back
    assert sorted(pdf.json()["sourceImages"]) == ["2"]
    assert pdf.json()["sourceImages"]["2"].startswith("data:image/jpeg;base64,/9j/")
    too_many = client.post("/teacher/papers/import/parse", headers=th,
                           json={**scope, "file_name": "期中扫描.pdf", "file_base64": os.environ["SCANNED_PDF_B64"], "images": [PHOTO] * 3})
    assert too_many.status_code == 400 and "最多识别 1 页" in too_many.json()["detail"], too_many.text
print("CATALOG_PHOTO_IMPORT_OK")
"""


def test_runtime_photo_questions_saved_to_bank_without_a_paper(tmp_path):
    env = os.environ.copy()
    from tests.test_paper_import import JPEG, _pdf

    env.update({"DATABASE_URL": f"sqlite:///{tmp_path / 'catalog.sqlite3'}", "ENABLE_DEMO_SEED": "1", "PYTHONPATH": str(ROOT),
                "SCANNED_PDF_B64": base64.b64encode(_pdf([("jpeg", JPEG), ("jpeg", JPEG)])).decode()})
    result = subprocess.run([sys.executable, "-c", RUNTIME], cwd=ROOT, env=env, capture_output=True, text=True, timeout=240, check=False)
    assert result.returncode == 0 and "CATALOG_PHOTO_IMPORT_OK" in result.stdout, (
        f"catalog photo import runtime failed\nstdout:\n{result.stdout[-4000:]}\nstderr:\n{result.stderr[-6000:]}"
    )
