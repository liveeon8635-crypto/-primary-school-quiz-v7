from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_teacher_ai_generation_returns_standard_rich_types_and_ui_support(tmp_path):
    db_path = tmp_path / "teacher-ai-rich-generation.sqlite3"
    script = r'''
import json
from fastapi.testclient import TestClient
import app_v924 as legacy
from app import app

def login_and_change(client, username, old_password, new_password):
    r = client.post("/login", json={"username": username, "password": old_password, "remember": False})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    r = client.post(
        "/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": old_password, "new_password": new_password, "remember": False},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]

with TestClient(app) as client:
    teacher_token = login_and_change(client, "teacher1", "123456", "Teacher1234")
    th = {"Authorization": f"Bearer {teacher_token}"}

    def fake_ai_call(db, user, feature, prompt, images=None, timeout=90):
        assert feature in {"question_generation", "question_generation_repair"}
        assert "【题型硬性要求】" in prompt
        assert "single_choice" in prompt and "fill_blank" in prompt
        return json.dumps({
            "questions": [
                {
                    "question_type": "single_choice",
                    "text": "2+3等于多少？",
                    "options": ["4","5","6","7"],
                    "correct_index": 1,
                    "knowledge": "加法",
                    "explanation": "2+3=5"
                },
                {
                    "question_type": "true_false",
                    "text": "0.5等于1/2。",
                    "options": ["正确","错误"],
                    "correct_index": 0,
                    "knowledge": "小数",
                    "explanation": "两者相等"
                },
                {
                    "question_type": "fill_blank",
                    "text": "3.0可以写成____。",
                    "answer": "3",
                    "accepted_answers": ["3.0"],
                    "knowledge": "小数",
                    "explanation": "小数末尾0可省略"
                },
                {
                    "question_type": "calculation",
                    "text": "计算2.5×4。",
                    "answer": "10",
                    "accepted_answers": ["10.0"],
                    "knowledge": "小数乘法",
                    "explanation": "2.5×4=10"
                },
                {
                    "question_type": "short_answer",
                    "text": "每袋5千克，2袋共多少千克？",
                    "answer": "10千克",
                    "accepted_answers": ["10", "10kg"],
                    "knowledge": "应用题",
                    "explanation": "5×2=10"
                },
                {
                    "question_type": "fill_blank",
                    "text": "10千克也可以写成____kg。",
                    "answer": "10",
                    "accepted_answers": ["10.0"],
                    "knowledge": "单位换算",
                    "explanation": "千克与kg是同一单位表达"
                },
            ]
        }, ensure_ascii=False)

    legacy._ai_call = fake_ai_call
    generated = client.post(
        "/ai/questions/generate",
        headers=th,
        json={
            "grade": 5,
            "subject": "数学",
            "textbook": "人教版",
            "semester": "上册",
            "unit": "综合",
            "knowledge": "综合",
            "difficulty": "中等",
            "count": 6,
            "question_type": "mixed",
            "notes": "题型丰富",
            "resource_ids": [],
        },
    )
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["qualityGuard"] == "authentic-school-exam-v3-rich-types"
    assert body["questionType"] == "mixed"
    assert [x["question_type"] for x in body["items"]] == [
        "single_choice", "true_false", "fill_blank", "calculation", "short_answer", "fill_blank"
    ]
    assert body["items"][1]["options"] == ["正确", "错误"]
    assert body["items"][2]["answer"] == "3"
    assert body["items"][2]["accepted_answers"] == ["3.0"]
    assert body["items"][4]["accepted_answers"] == ["10", "10kg"]
    assert body["items"][5]["answer"] == "10"
    assert all(x["question_type"] != "non_choice" for x in body["items"])

    science = client.post(
        "/ai/questions/generate",
        headers=th,
        json={
            "grade": 5,
            "subject": "科学",
            "textbook": "学校实际科学教材",
            "semester": "上册",
            "unit": "实验",
            "knowledge": "观察",
            "difficulty": "中等",
            "count": 2,
            "question_type": "short_answer",
            "notes": "",
            "resource_ids": [],
        },
    )
    assert science.status_code == 400
    assert "科学" in science.json()["detail"]

assert legacy.app.state.teacher_ai_rich_generation_installed is True
html = legacy.INDEX_HTML
assert "changying_teacher_ai_rich_generation_v1" in html
for value in (
    "['single_choice','单选题']",
    "['true_false','判断题']",
    "['fill_blank','填空题']",
    "['calculation','计算题']",
    "['short_answer','简短应用题']",
    "['non_choice','教师审核主观题']",
):
    assert value in html
assert "只有“教师审核主观题”会走拍照/教师确认" in html
assert "全部题目可在线作答并由服务器判分" in html
'''

    env = os.environ.copy()
    env.update({
        "DATABASE_URL": f"sqlite:///{db_path}",
        "JWT_SECRET": "x" * 64,
        "COMMERCIAL_ADMIN_KEY": "y" * 40,
        "ENABLE_DEMO_SEED": "1",
        "PYTHONPATH": str(ROOT),
    })
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, (
        "teacher AI rich generation integration subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
