import inspect
import json
from types import SimpleNamespace

from changying.services.rubric_evidence_closure import (
    _grading_assist_call,
    manual_question_meta,
    structured_manual_answer_json,
)


def test_structured_non_choice_metadata_round_trips():
    body = SimpleNamespace(
        reference_answer="因为人物连续三次回头，说明他舍不得离开。",
        scoring_points=["抓住“三次回头”", "指出“依依不舍”"],
    )
    payload = json.loads(structured_manual_answer_json(body))
    assert payload == {
        "grading": "teacher_review",
        "reference_answer": "因为人物连续三次回头，说明他舍不得离开。",
        "scoring_points": ["抓住“三次回头”", "指出“依依不舍”"],
    }

    question = SimpleNamespace(
        question_type="non_choice",
        answer_json=json.dumps(payload, ensure_ascii=False),
        explanation="",
        options_json="[]",
        correct_index=-1,
    )
    meta = manual_question_meta(question)
    assert meta["manual"] is True
    assert meta["grading"] == "teacher_review"
    assert meta["scoring_points"] == ["抓住“三次回头”", "指出“依依不舍”"]


def test_legacy_explanation_rubric_still_parses():
    question = SimpleNamespace(
        question_type="",
        answer_json="{}",
        explanation=(
            "参考答案：人物舍不得离开小院。\n"
            "评分要点：结合动作；指出依依不舍\n"
            "解析：从动作体会感情。"
        ),
        options_json="[]",
        correct_index=-1,
    )
    meta = manual_question_meta(question)
    assert meta["manual"] is True
    assert meta["reference_answer"] == "人物舍不得离开小院。"
    assert meta["scoring_points"] == ["结合动作", "指出依依不舍"]


def test_grading_assist_replacement_preserves_legacy_dependency_names():
    fn = _grading_assist_call(SimpleNamespace())
    assert list(inspect.signature(fn).parameters) == ["b", "u", "db"]


def test_runtime_installs_rubric_evidence_closure():
    import app  # noqa: F401
    import app_v924 as legacy

    assert legacy.app.state.rubric_evidence_closure_installed is True

    grade_route = next(
        route
        for route in legacy.app.routes
        if getattr(route, "path", None) == "/ai/homework/grade-assist"
        and "POST" in getattr(route, "methods", set())
    )
    assert grade_route.dependant.call.__name__ == "grade_assist"

    save_route = next(
        route
        for route in legacy.app.routes
        if getattr(route, "path", None) == "/ai/questions/save"
        and "POST" in getattr(route, "methods", set())
    )
    assert hasattr(save_route.dependant.call, "__wrapped__")
