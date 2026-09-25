from types import SimpleNamespace

from fastapi import FastAPI, HTTPException

from changying.web.v1_training_sandbox import (
    ROLE_FLOW,
    SCENARIO_PRESETS,
    STEP_RELATIONSHIPS,
    SandboxSession,
    TrainingSandboxStore,
    apply_training_action,
    install_v1_training_sandbox_routes,
)


def teacher_session() -> SandboxSession:
    return SandboxSession(
        session_id="training-test",
        owner_user_id=101,
        primary_role="teacher",
        current_role="teacher",
    )


def test_training_routes_are_registered_without_new_schema():
    app = FastAPI()

    def current_user():
        return SimpleNamespace(id=1, role="teacher")

    implementation = SimpleNamespace(app=app, current_user=current_user)
    install_v1_training_sandbox_routes(implementation)
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    assert "/v1/training-sandbox/start" in paths
    assert "/v1/training-sandbox/{session_id}" in paths
    assert "/v1/training-sandbox/{session_id}/action" in paths
    assert "/v1/training-sandbox/{session_id}/reset" in paths


def test_role_flows_cover_each_identity_page_relationship():
    assert len(ROLE_FLOW["teacher"]) >= 16
    assert len(ROLE_FLOW["student"]) >= 8
    assert len(ROLE_FLOW["parent"]) >= 6
    assert len(ROLE_FLOW["admin"]) >= 7

    teacher_ids = {step["id"] for step in ROLE_FLOW["teacher"]}
    for step in (
        "create_class",
        "add_student",
        "paper",
        "assign",
        "student_submission",
        "evidence",
        "targeted",
        "class_review",
        "interactive",
        "points",
        "history",
        "transition",
    ):
        assert step in teacher_ids
        assert step in STEP_RELATIONSHIPS


def test_teacher_can_run_complete_simulated_linked_role_loop():
    s = teacher_session()
    apply_training_action(s, "create_class", {"name": "五年级实验班", "grade": 5})
    apply_training_action(s, "add_student", {"name": "小禾", "username": "xiaohe01"})
    apply_training_action(
        s,
        "create_paper",
        {"subject": "数学", "textbook": "人教版", "knowledge": "小数乘法", "questionCount": 8},
    )
    apply_training_action(s, "review_paper", {})
    apply_training_action(s, "assign", {"due": "本周五"})
    apply_training_action(s, "simulate_student_submission", {"correct": 6})
    apply_training_action(s, "create_targeted_practice", {"questionCount": 6})
    apply_training_action(s, "create_class_review", {})
    apply_training_action(s, "run_interactive_classroom", {"mode": "师生共讲"})
    apply_training_action(s, "review_points", {})
    apply_training_action(s, "archive_history", {})
    apply_training_action(s, "create_transition", {"from": "五年级", "to": "六年级"})

    assert s.current_role == "teacher"
    assert s.data["classes"][0]["name"] == "五年级实验班"
    assert s.data["students"][0]["classID"] == s.data["classes"][0]["id"]
    assert s.data["assignments"][0]["paperID"] == s.data["papers"][0]["id"]
    assert s.data["submissions"][0]["source"] == "simulated_linked_role"
    assert s.data["submissions"][0]["score"] == 75
    assert s.data["targeted_practices"][0]["basedOnSubmissionID"] == s.data["submissions"][0]["id"]
    assert s.data["history"][0]["status"] == "read_only"
    assert s.data["transitions"][0]["studentID"] == s.data["students"][0]["id"]


def test_teacher_can_switch_to_virtual_student_and_return_without_relogin():
    s = teacher_session()
    apply_training_action(s, "create_class", {"name": "练习班", "grade": 5})
    apply_training_action(s, "add_student", {"name": "小禾", "username": "xiaohe01"})
    apply_training_action(s, "create_paper", {"questionCount": 4})
    apply_training_action(s, "review_paper", {})
    apply_training_action(s, "assign", {})

    apply_training_action(s, "switch_to_student", {})
    assert s.primary_role == "teacher"
    assert s.current_role == "student"
    assert s.linked_mode == "switch"

    apply_training_action(s, "student_submit", {"correct": 3})
    assert s.data["submissions"][0]["source"] == "manual_virtual_student"

    apply_training_action(s, "return_primary_role", {})
    assert s.current_role == "teacher"


def test_student_submission_requires_switch_or_simulation():
    s = teacher_session()
    apply_training_action(s, "create_class", {"grade": 5})
    apply_training_action(s, "add_student", {})
    apply_training_action(s, "create_paper", {"questionCount": 4})
    apply_training_action(s, "review_paper", {})
    apply_training_action(s, "assign", {})

    try:
        apply_training_action(s, "student_submit", {"correct": 3})
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "切换到虚拟学生视角" in exc.detail
    else:
        raise AssertionError("student_submit must require linked-role switch")


def test_store_is_owner_isolated_and_reset_discards_training_business_data():
    store = TrainingSandboxStore(ttl_seconds=3600, max_sessions=10)
    s = store.create(1, "teacher")
    apply_training_action(s, "create_class", {"name": "临时班", "grade": 5})

    try:
        store.get(s.session_id, 2)
    except KeyError:
        pass
    else:
        raise AssertionError("sandbox session leaked across owners")

    reset = store.reset(s.session_id, 1)
    assert reset.data["classes"] == []
    assert reset.events == []
    assert reset.progress == {}
    assert reset.primary_role == "teacher"


def test_training_module_has_no_production_database_write_dependency():
    from pathlib import Path

    source = Path("changying/web/v1_training_sandbox.py").read_text(encoding="utf-8")
    assert "from sqlalchemy" not in source.lower()
    assert "import sqlalchemy" not in source.lower()
    assert "get_db" not in source
    assert "db.commit" not in source
    assert "LearningEvidenceEvent" not in source


def test_scenario_presets_support_resume_without_repeating_every_role_step():
    s = teacher_session()
    apply_training_action(s, "load_scenario", {"preset": "assigned"})
    assert s.data["classes"]
    assert s.data["students"]
    assert s.data["papers"][0]["reviewed"] is True
    assert s.data["assignments"]
    assert s.data["submissions"] == []

    apply_training_action(s, "load_scenario", {"preset": "submitted"})
    assert s.data["submissions"]
    assert s.progress["evidence"] == "done"

    apply_training_action(s, "load_scenario", {"preset": "classroom"})
    assert s.data["class_reviews"]


def test_relationship_map_explains_cross_role_visibility_and_communication():
    assert SCENARIO_PRESETS["empty"]["title"] == "从零开始"
    for step in ("assign", "student_submission", "evidence", "interactive", "points"):
        rel = STEP_RELATIONSHIPS[step]
        assert rel["visible_to"]
        assert rel["other_role_sees"]
        assert rel["communication_tip"]


def test_virtual_student_can_submit_real_question_choices():
    s = teacher_session()
    apply_training_action(s, "create_class", {"grade": 5})
    apply_training_action(s, "add_student", {"name": "小禾", "username": "xiaohe01"})
    apply_training_action(s, "create_paper", {"questionCount": 4})
    apply_training_action(s, "review_paper", {})
    apply_training_action(s, "assign", {})
    apply_training_action(s, "switch_to_student", {})

    paper = s.data["papers"][0]
    answers = {str(q["id"]): q["correctIndex"] for q in paper["questions"]}
    apply_training_action(s, "student_submit", {"answers": answers})

    submission = s.data["submissions"][0]
    assert submission["correct"] == 4
    assert submission["total"] == 4
    assert submission["score"] == 100
    assert submission["source"] == "manual_virtual_student"
