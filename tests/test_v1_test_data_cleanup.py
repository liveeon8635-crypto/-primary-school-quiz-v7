"""Regression tests for feedback #306: pre-launch test data cleanup.

Teachers need a safe, reversible way to clear test/demo data before
formal use. Real student records must never be eligible.
"""

from changying.web.v1_unified_tools_session_bridge import (
    V1_TEST_DATA_CLEANUP_MARKER,
    build_test_data_cleanup_plan,
    is_test_data_record,
    select_test_data_records,
)


def test_marker_present():
    assert V1_TEST_DATA_CLEANUP_MARKER == "changying_v1_test_data_cleanup_v1"


def test_real_student_record_not_eligible():
    assert is_test_data_record({"id": 1, "name": "\u5b9e\u9645\u5b66\u751f"}) is False


def test_explicit_flag_is_eligible():
    assert is_test_data_record({"id": 2, "isTestData": True}) is True
    assert is_test_data_record({"id": 3, "is_test_data": True}) is True


def test_source_flag_is_eligible():
    assert is_test_data_record({"id": 4, "source": "demo"}) is True
    assert is_test_data_record({"id": 5, "origin": "seed"}) is True


def test_select_filters_only_test_records():
    records = [
        {"id": 1, "name": "real"},
        {"id": 2, "isTestData": True},
        {"id": 3, "source": "test"},
    ]
    selected = select_test_data_records(records)
    assert [r["id"] for r in selected] == [2, 3]


def test_cleanup_plan_is_reversible_and_scoped():
    records = [
        {"id": 1, "name": "real"},
        {"id": 2, "isTestData": True},
    ]
    plan = build_test_data_cleanup_plan(records)
    assert plan["marker"] == V1_TEST_DATA_CLEANUP_MARKER
    assert plan["eligibleCount"] == 1
    assert plan["eligibleIds"] == [2]
    assert plan["reversible"] is True


def test_empty_input_yields_empty_plan():
    plan = build_test_data_cleanup_plan([])
    assert plan["eligibleCount"] == 0
    assert plan["eligibleIds"] == []
