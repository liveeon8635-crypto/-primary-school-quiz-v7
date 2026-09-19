from pathlib import Path
from types import SimpleNamespace

import app_v924 as legacy


ROOT = Path(__file__).resolve().parents[1]


def test_mixed_reinforcement_question_helpers():
    assert {"single_choice", "true_false", "fill_blank", "calculation", "short_answer"} <= legacy.AUTO_GRADED_QUESTION_TYPES
    assert legacy._text_answer_matches("10棵", "10", ["10棵"])
    assert legacy._text_answer_matches("1.140", "1.14", [])
    assert not legacy._text_answer_matches("4", "5", ["5个"])

    fig = legacy._sanitize_figure(
        {
            "type": "coordinate_grid",
            "xMax": 6,
            "yMax": 6,
            "points": [{"x": 2, "y": 3, "label": "A"}],
            "segments": [{"x1": 2, "y1": 3, "x2": 4, "y2": 3}],
            "unsafe": "ignored",
        }
    )
    assert fig["type"] == "coordinate_grid"
    assert fig["points"][0]["label"] == "A"
    assert fig["segments"][0]["x2"] == 4
    assert "unsafe" not in fig


def test_student_question_payload_hides_answer_key():
    row = SimpleNamespace(
        id=1,
        grade=5,
        subject="数学",
        textbook="人教版",
        semester="上册",
        unit="植树问题",
        knowledge="植树问题",
        text="72米小路每8米栽一棵，两端都栽，共多少棵？",
        options_json="[]",
        correct_index=-1,
        explanation="",
        question_type="short_answer",
        answer_json='{"answer":"10","accepted":["10棵"]}',
        figure_json='{"type":"line_segment","segments":[{"label":"8米","ratio":1}]}',
    )
    public = legacy.qj_public(row)
    teacher = legacy.qj(row)
    assert public["questionType"] == "short_answer"
    assert public["figure"]["type"] == "line_segment"
    assert "answer" not in public
    assert "correctIndex" not in public
    assert teacher["answer"] == "10"
    assert teacher["acceptedAnswers"] == ["10棵"]


def test_v1_renders_mixed_question_types_and_figures():
    source = (ROOT / "app_v924.py").read_text(encoding="utf-8")
    assert "function renderQuestionFigure(fig)" in source
    assert "function questionTypeName(t)" in source
    assert "quizTextAnswer" in source
    assert "系统会根据知识点选择合适题型" in source
    assert "至少使用 3 种题型" in source
