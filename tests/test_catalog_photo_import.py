"""Feedback #337: 教材题库 — photograph questions, AI recognises them (any type),
teacher reviews, questions go straight into the question bank."""

from __future__ import annotations

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
    {"question_type": "true_false", "text": "两个奇数的和一定是偶数。", "correct_index": 0, "answer_source": "ai"},
    {"question_type": "calculation", "text": "125×8", "answer": "1000", "answer_source": "paper"},
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

    saved = client.post("/teacher/papers/import/save", headers=th, json={**scope, "title": "题库导入", "questions": items, "create_paper": False})
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["savedCount"] == 4 and body["typeSummary"] == "单选1 · 判断1 · 填空1 · 计算1"
    assert "id" not in body and "assignment" not in body
    bank = {q["id"]: q for q in client.get("/questions?grade=5&subject=数学&unit=因数与倍数", headers=th).json()}
    assert {bank[i]["questionType"] for i in body["questionIDs"]} == {"fill_blank", "true_false", "calculation", "single_choice"}
    assert bank[body["questionIDs"][0]]["answer"] == "9"
    with legacy.SessionLocal() as db:
        assert db.scalar(legacy.select(legacy.func.count()).select_from(legacy.Paper)) == papers_before

    # The new questions feed balanced composition right away.
    composed = client.post("/teacher/papers/compose", headers=th, json={**scope, "title": "因数与倍数练习", "count": 4})
    assert composed.status_code == 200 and len(composed.json()["typeDistribution"]) == 4, composed.text

    assert client.post("/teacher/papers/import/parse", headers=ah, json={**scope, "text": "1. 2+2=__ 答案 4"}).status_code == 200
    admin_bank = client.post("/teacher/papers/import/save", headers=ah, json={**scope, "questions": [items[0]], "create_paper": False})
    assert admin_bank.status_code == 200 and admin_bank.json()["savedCount"] == 1, admin_bank.text
    assert client.post("/teacher/papers/import/save", headers=ah, json={**scope, "title": "x", "questions": [items[0]]}).status_code == 403
    assert client.post("/teacher/papers/import/save", headers=th, json={**scope, "questions": [items[0]], "create_paper": False, "class_id": 1}).status_code == 400
    assert client.post("/teacher/papers/import/parse", headers=sh, json={**scope, "text": "x"}).status_code == 403
print("CATALOG_PHOTO_IMPORT_OK")
"""


def test_runtime_photo_questions_saved_to_bank_without_a_paper(tmp_path):
    env = os.environ.copy()
    env.update({"DATABASE_URL": f"sqlite:///{tmp_path / 'catalog.sqlite3'}", "ENABLE_DEMO_SEED": "1", "PYTHONPATH": str(ROOT)})
    result = subprocess.run([sys.executable, "-c", RUNTIME], cwd=ROOT, env=env, capture_output=True, text=True, timeout=240, check=False)
    assert result.returncode == 0 and "CATALOG_PHOTO_IMPORT_OK" in result.stdout, (
        f"catalog photo import runtime failed\nstdout:\n{result.stdout[-4000:]}\nstderr:\n{result.stderr[-6000:]}"
    )
