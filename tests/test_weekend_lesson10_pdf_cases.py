"""23 worked examples transcribed from teacher PDF dated 2026-11-07.

Checks cover data shape and identity, not an assertion of teacher acceptance.
"""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from changying.services import weekend_courseware as cw

CASES = json.loads(
    (Path(__file__).parents[1] / "changying" / "services" / "weekend_lesson10_teacher_reference.json").read_text("utf-8")
)

def test_exact_23_questions_and_chapter_positions():
    assert [item["number"] for item in CASES] == list(range(1, 24))
    assert [item["sourcePage"] for item in CASES] == [
        1,2,2,2,2,3,3,3,4,4,4,5,5,6,6,6,7,7,7,8,8,8,9
    ]
    assert all(item["source"] and item["problem"] and item["answer"] for item in CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda c: "example-%02d" % c["number"])
def test_every_pdf_case_validates_as_a_classroom_step_slide(case):
    raw = {
        "title": case["title"], "problem": case["problem"],
        "answer": case["answer"], "steps": case["steps"],
        "figure": case["figure"],
    }
    params = cw.clean_steps(raw)
    assert len(params["steps"]) == 4
    assert params["figure"].get("type") == case["figure"].get("type")
    assert params["answer"] == case["answer"]
    assert "reference" not in cw.public_params("steps", params)


def test_known_source_image_gaps_are_disclosed():
    missing = next(case for case in CASES if case["number"] == 9)
    assert "没有给出" in missing["notes"] and missing["sourcePage"] == 4
    nine = next(case for case in CASES if case["number"] == 15)
    assert nine["figure"]["nineGrid"] and nine["figure"]["center"] == 224
    assert cw.clean_figure(nine["figure"])["center"] == 224
    geo = next(case for case in CASES if case["number"] == 20)
    assert "上排2个大正方形" in geo["notes"]


def test_nine_grid_metadata_validation():
    good = next(case["figure"] for case in CASES if case["number"] == 15)
    assert cw.clean_figure(good)["nineGrid"] is True
    with pytest.raises(ValueError):
        cw.clean_figure({**good, "center": 225})
    with pytest.raises(ValueError):
        cw.clean_figure({**good, "rows": [["1","2"],["3","4"]]})
