from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("question_difficulty_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

BODY = """{"grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
        "unit": "小数乘法", "knowledge": "小数乘整数", "count": 2,
        "question_type": "choice", "notes": ""}"""

STUB = r'''
import json

import app_v924 as legacy

captured = {}


def fake_call(db, user, feature, prompt, *args, **kwargs):
    captured[feature] = prompt
    return json.dumps({"questions": [{
        "question_type": "choice",
        "text": "0.75 × 4 的结果是多少？",
        "options": ["0.3", "3", "30", "300"],
        "correct_index": 1,
        "explanation": "0.75 × 4 = 3",
        "knowledge": "小数乘整数",
    }]}, ensure_ascii=False)


legacy._ai_call = fake_call

BODY = ''' + BODY + r'''
'''


def test_generated_questions_carry_a_real_difficulty_rule(tmp_path):
    """'中等' used to reach the model as a bare word; the prompt now defines it."""
    helpers.run_isolated(tmp_path, helpers.COMMON + STUB + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    r = client.post("/ai/questions/generate", headers=th, json={**BODY, "difficulty": "中等"})
    assert r.status_code == 200, r.text
    prompt = captured["question_generation"]
    assert "【难度硬性要求】" in prompt
    assert "两步以上" in prompt                      # 中等 = two or more steps
    assert "只有「基础」难度允许" in prompt           # recall-only stems banned above 基础
    assert "具体数值" in prompt                       # maths must ask for a computed result
    assert "干扰项要来自学生真实会犯的错误" in prompt

    r = client.post("/ai/questions/generate", headers=th, json={**BODY, "difficulty": "提高"})
    assert r.status_code == 200, r.text
    assert "逆向思考" in captured["question_generation"]

    r = client.post("/ai/questions/generate", headers=th, json={**BODY, "difficulty": "基础"})
    assert r.status_code == 200, r.text
    assert "一步完成" in captured["question_generation"]
print('OK')
''')


def test_recall_only_questions_are_rejected_above_basic(tmp_path):
    """Prompt wording is not enough: a stem with no number or operator is filtered out."""
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import json

import app_v924 as legacy


def fake_call(db, user, feature, prompt, *args, **kwargs):
    return json.dumps({"questions": [{
        "question_type": "choice",
        "text": "下面各题中，可以用竖式表示的是（　）",
        "options": ["甲种情形", "乙种情形", "丙种情形", "丁种情形"],
        "correct_index": 0,
        "explanation": "略",
        "knowledge": "小数乘整数",
    }]}, ensure_ascii=False)


legacy._ai_call = fake_call

BODY = ''' + BODY + r'''

with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    r = client.post("/ai/questions/generate", headers=th, json={**BODY, "difficulty": "中等"})
    assert r.status_code == 502, r.text
    assert "记忆" in r.json()["detail"] or "辨认" in r.json()["detail"]

    r = client.post("/ai/questions/generate", headers=th, json={**BODY, "difficulty": "基础"})
    assert r.status_code == 200, r.text
print('OK')
''')


def test_reviewed_bank_questions_become_the_style_reference(tmp_path):
    """Same knowledge point, already reviewed by this school, used as few-shot examples."""
    helpers.run_isolated(tmp_path, helpers.COMMON + STUB + r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)

    # 1) An empty bank adds nothing to the prompt.
    r = client.post("/ai/questions/generate", headers=th, json={**BODY, "difficulty": "中等"})
    assert r.status_code == 200, r.text
    assert "本校已审核的同类题" not in captured["question_generation"]

    # 2) One reviewed question for the same knowledge point becomes the example.
    with legacy.SessionLocal() as db:
        db.add(legacy.Question(school_id=school_id, grade=5, subject="数学", knowledge="小数乘整数",
                               text="0.6 × 7 的积是多少？",
                               options_json='["0.42", "4.2", "42", "420"]',
                               correct_index=1, explanation="0.6 × 7 = 4.2"))
        db.commit()

    captured.clear()
    r = client.post("/ai/questions/generate", headers=th, json={**BODY, "difficulty": "中等"})
    assert r.status_code == 200, r.text
    prompt = captured["question_generation"]
    assert "本校已审核的同类题" in prompt
    assert "0.6 × 7 的积是多少？" in prompt
    assert "答案 B" in prompt
    assert "不要照抄" in prompt
print('OK')
''')
