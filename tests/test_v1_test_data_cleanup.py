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


def test_training_cleanup_store_is_owner_scoped_and_never_touches_other_users():
    from changying.web.v1_training_sandbox import TrainingSandboxStore

    store = TrainingSandboxStore()
    first = store.create(1001, "teacher")
    second = store.create(1001, "teacher")
    other = store.create(2002, "teacher")

    assert first.session_id != second.session_id
    assert store.count_for_owner(1001) == 2
    assert store.count_for_owner(2002) == 1

    assert store.clear_for_owner(1001) == 2
    assert store.count_for_owner(1001) == 0
    assert store.count_for_owner(2002) == 1
    assert store.get(other.session_id, 2002).session_id == other.session_id


def test_training_cleanup_routes_preview_then_clear_only_ephemeral_sessions():
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from changying.web.v1_training_sandbox import STORE, install_v1_training_sandbox_routes

    owner_id = 9306
    STORE.clear_for_owner(owner_id)
    app = FastAPI()

    def current_user():
        return SimpleNamespace(id=owner_id, role="teacher")

    install_v1_training_sandbox_routes(SimpleNamespace(app=app, current_user=current_user))
    client = TestClient(app)

    assert client.post("/v1/training-sandbox/start", json={"linked_mode": "choose"}).status_code == 200
    assert client.post("/v1/training-sandbox/start", json={"linked_mode": "choose"}).status_code == 200

    preview = client.get("/v1/training-sandbox/cleanup-preview").json()
    assert preview == {
        "ok": True,
        "marker": "changying_v1_training_cleanup_v1",
        "scope": "ephemeral_training_sessions_only",
        "eligibleSessionCount": 2,
        "productionDataAffected": False,
        "requiresConfirmation": True,
    }

    cleared = client.post("/v1/training-sandbox/cleanup-all", json={}).json()
    assert cleared["ok"] is True
    assert cleared["clearedSessionCount"] == 2
    assert cleared["productionDataAffected"] is False

    after = client.get("/v1/training-sandbox/cleanup-preview").json()
    assert after["eligibleSessionCount"] == 0
    assert after["requiresConfirmation"] is False


def test_training_ui_exposes_cleanup_with_production_data_safety_copy():
    from changying.web.v1_training_workbench import training_workbench_html

    html = training_workbench_html()
    assert "正式使用前 · 清空演示数据" in html
    assert "/v1/training-sandbox/cleanup-preview" in html
    assert "/v1/training-sandbox/cleanup-all" in html
    assert "真实班级、学生、作业、积分或学习证据" in html
