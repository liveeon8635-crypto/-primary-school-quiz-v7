from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chinese_choice_like_fill_renders_and_grades_as_choice(tmp_path):
    db_path = tmp_path / "chinese-control.sqlite3"
    script = r'''
import json

import app_v924 as legacy
from app import app  # noqa: F401

with legacy.SessionLocal() as db:
    student = db.scalar(
        legacy.select(legacy.User).where(legacy.User.username == "student1")
    )
    assert student is not None

    question = legacy.Question(
        school_id=student.school_id,
        grade=5,
        subject="语文",
        textbook="统编版（人民教育出版社）",
        semester="上册",
        unit="全册基础 · 句段表达",
        knowledge="病句辨析",
        text="请直接填写答案：下列句子没有语病的一项是？",
        options_json="[]",
        correct_index=-1,
        explanation="",
        question_type="fill_blank",
        answer_json=json.dumps(
            {"answer": "经过努力，小组终于完成了实验记录。", "accepted": []},
            ensure_ascii=False,
        ),
        figure_json="{}",
        creator_id=student.id,
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    public = legacy.qj_public(question)
    assert public["questionType"] == "single_choice"
    assert public["text"] == "下列句子没有语病的一项是？"
    assert len(public["options"]) == 4
    assert public["options"][0] == "经过努力，小组终于完成了实验记录。"
    assert "correctIndex" not in public
    assert "answer" not in public

    answer = legacy.AnswerItem(
        question_id=question.id,
        selected_index=0,
        text_answer="",
    )
    normalized, correct, total, score = legacy.grade_answers(
        db,
        student,
        [answer],
        allowed_question_ids=[question.id],
        require_all=True,
    )
    assert correct == 1
    assert total == 1
    assert score == 100
    assert normalized[0]["correct"] is True
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "chinese-control-signing-material-0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "chinese-control-operator-material-012345",
            "ENABLE_DEMO_SEED": "1",
            "PYTHONPATH": str(ROOT),
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )

    assert result.returncode == 0, (
        "Chinese control compatibility subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
