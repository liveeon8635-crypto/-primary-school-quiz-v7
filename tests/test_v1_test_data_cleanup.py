"""Regression test for feedback #306: pre-launch test data cleanup.

Teachers must be able to clear test/demo data before formal use without
risking real student history. The cleanup entry point is guarded and
reversible: only records explicitly flagged as test/demo are eligible.
"""

from changying.web.v1_unified_tools_session_bridge import (
    V1_TEST_DATA_CLEANUP_MARKER,
    build_test_data_cleanup_plan,
    handle_test_data_cleanup_request,
    is_test_data_record,
    select_test_data_records,
)


def test_real_student_records_are_never_eligible():
    real = {"id": "s1", "name": "\u771f\u5b9e\u5b66\u751f", "source": "production"}
    assert is_test_data_record(real) is False
    assert select_test_data_records([real]) == []


def test_explicit_test_flag_is_eligible():
    test_rec = {"id": "t1", "isTestData": True}
    assert is_test_data_record(test_rec) is True
    assert select_test_data_records([test_rec]) == [test_rec]


def test_cleanup_plan_is_reversible_and_lists_only_test_ids():
    records = [
        {"id": "t1", "isTestData": True},
        {"id": "s1", "source": "production"},
        {"id": "t2", "source": "demo"},
    ]
    plan = build_test_data_cleanup_plan(records)
    assert plan["marker"] == V1_TEST_DATA_CLEANUP_MARKER
    assert plan["eligibleCount"] == 2
    assert set(plan["eligibleIds"]) == {"t1", "t2"}
    assert plan["reversible"] is True


def test_cleanup_request_handler_previews_without_deleting():
    records = [{"id": "t1", "isTestData": True}, {"id": "s1", "source": "production"}]
    result = handle_test_data_cleanup_request(
        {"action": "preview_test_data_cleanup"}, records
    )
    assert result["ok"] is True
    assert result["marker"] == V1_TEST_DATA_CLEANUP_MARKER
    assert result["plan"]["eligibleIds"] == ["t1"]
    assert result["requiresConfirmation"] is True
    assert result["destructive"] is False


def test_cleanup_request_handler_rejects_unknown_action():
    result = handle_test_data_cleanup_request({"action": "delete_everything"}, [])
    assert result["ok"] is False
    assert result["error"] == "unsupported_action"
