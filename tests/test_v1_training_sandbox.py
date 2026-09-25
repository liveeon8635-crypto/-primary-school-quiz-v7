from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from changying.web.v1_training_sandbox import (
    ROLE_FLOW,
    ROLE_MENU_PAGE_IDS,
    SCENARIO_PRESETS,
    STEP_RELATIONSHIPS,
    SandboxSession,
    TrainingSandboxStore,
    apply_training_action,
    install_v1_training_sandbox_routes,
)




def _correct_answers(paper):
    return {
        str(q["id"]): q["correctIndex"] if q.get("answerKind") == "choice" else q.get("correctAnswer", "")
        for q in paper["questions"]
    }

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
    client = TestClient(app)

    started = client.post("/v1/training-sandbox/start", json={"linked_mode": "choose"})
    assert started.status_code == 200
    payload = started.json()
    assert payload["training"] is True
    assert payload["persistent"] is False

    session_id = payload["sessionID"]
    assert client.get(f"/v1/training-sandbox/{session_id}").status_code == 200
    assert client.post(
        f"/v1/training-sandbox/{session_id}/action",
        json={"action": "visit_step", "payload": {"step": "teacher_dashboard", "status": "done"}},
    ).status_code == 200
    assert client.post(f"/v1/training-sandbox/{session_id}/reset", json={}).status_code == 200


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
    answers = _correct_answers(paper)
    apply_training_action(s, "student_submit", {"answers": answers})

    submission = s.data["submissions"][0]
    assert submission["correct"] == 4
    assert submission["total"] == 4
    assert submission["score"] == 100
    assert submission["source"] == "manual_virtual_student"


def test_student_role_is_seeded_with_real_upstream_context_and_can_submit():
    store = TrainingSandboxStore(ttl_seconds=3600, max_sessions=10)
    s = store.create(2, "student")
    assert s.data["classes"]
    assert s.data["students"]
    assert s.data["assignments"]
    assert s.data["submissions"] == []

    paper = s.data["papers"][0]
    answers = _correct_answers(paper)
    apply_training_action(s, "student_submit_self", {"answers": answers})
    assert s.data["submissions"][0]["score"] == 100
    assert s.data["targeted_practices"]
    assert s.progress["answer"] == "done"
    assert s.progress["result"] == "done"

    apply_training_action(s, "complete_student_practice", {})
    assert s.data["targeted_practices"][0]["status"] == "completed"


def test_parent_role_gets_read_only_linked_child_context():
    store = TrainingSandboxStore(ttl_seconds=3600, max_sessions=10)
    s = store.create(3, "parent")
    assert s.data["students"][0]["name"] == "小禾"
    assert s.data["guardian_links"]
    assert s.data["assignments"]
    assert s.data["submissions"]
    assert s.data["points"]
    assert s.data["history"]


def test_admin_role_can_practice_account_class_points_and_system_settings():
    store = TrainingSandboxStore(ttl_seconds=3600, max_sessions=10)
    s = store.create(4, "admin")
    initial_accounts = len(s.data["accounts"])
    apply_training_action(s, "admin_create_account", {"name": "林老师", "username": "teacher02", "role": "teacher"})
    assert len(s.data["accounts"]) == initial_accounts + 1

    apply_training_action(s, "admin_create_class", {"name": "五年级二班", "grade": 5})
    assert any(x["name"] == "五年级二班" for x in s.data["classes"])

    apply_training_action(s, "admin_set_point_rule", {"name": "课堂参与", "points": 3})
    assert any(x["name"] == "课堂参与" and x["points"] == 3 for x in s.data["point_rules"])

    apply_training_action(s, "admin_set_system", {"key": "trainingFeature", "value": "开启"})
    assert s.data["system_settings"]["trainingFeature"] == "开启"
    assert len(s.data["audit"]) >= 4


def test_teacher_can_rewind_one_training_step_without_losing_upstream_context():
    s = teacher_session()
    apply_training_action(s, "create_class", {"name": "练习班", "grade": 5})
    apply_training_action(s, "add_student", {"name": "小禾", "username": "xiaohe01"})
    apply_training_action(s, "create_paper", {"questionCount": 4})
    apply_training_action(s, "review_paper", {})
    apply_training_action(s, "assign", {})
    apply_training_action(s, "simulate_student_submission", {"correct": 3})
    apply_training_action(s, "rewind_step", {"step": "student_submission"})
    assert s.data["assignments"]
    assert s.data["submissions"] == []
    assert s.data["points"] == []


def test_student_can_rewind_answer_step_and_submit_again():
    store = TrainingSandboxStore(ttl_seconds=3600, max_sessions=10)
    s = store.create(22, "student")
    paper = s.data["papers"][0]
    answers = _correct_answers(paper)
    apply_training_action(s, "student_submit_self", {"answers": answers})
    assert s.data["submissions"]
    apply_training_action(s, "rewind_step", {"step": "answer"})
    assert s.data["submissions"] == []
    assert s.data["wrong_questions"] == []
    assert s.data["points"] == []
    apply_training_action(s, "student_submit_self", {"answers": answers})
    assert s.data["submissions"][0]["score"] == 100


def test_training_flow_covers_every_visible_role_menu_page():
    for role, page_ids in ROLE_MENU_PAGE_IDS.items():
        flow_pages = {step["page"].split("page=", 1)[1] for step in ROLE_FLOW[role] if "page=" in step["page"]}
        assert set(page_ids).issubset(flow_pages), (role, set(page_ids) - flow_pages)


def test_every_training_step_has_role_relationship_context_or_is_core_action():
    core_actions = {
        "create_class", "add_student", "student_profile", "paper", "review", "assign",
        "student_submission", "evidence", "targeted", "class_review", "interactive",
        "points", "history", "transition", "hub", "answer", "result", "practice",
        "progress", "rewards", "wrongbook", "users", "classes", "audit", "system",
    }
    for role, steps in ROLE_FLOW.items():
        for step in steps:
            assert step["id"] in STEP_RELATIONSHIPS or step["id"] in core_actions, (role, step["id"])


def test_training_paper_uses_mixed_types_and_matching_answer_modes():
    s = teacher_session()
    apply_training_action(s, "create_class", {"grade": 5})
    apply_training_action(s, "create_paper", {"subject": "数学", "knowledge": "小数乘法", "questionCount": 8})
    questions = s.data["papers"][0]["questions"]
    assert {"单选", "判断", "填空", "计算", "简短应用题"}.issubset({q["type"] for q in questions})
    assert all(q["answerKind"] in {"choice", "text"} for q in questions)
    assert all(("options" in q) == (q["answerKind"] == "choice") for q in questions)


def test_training_text_answers_accept_normalized_units_and_reject_missing_unit():
    s = teacher_session()
    apply_training_action(s, "create_class", {"grade": 5})
    apply_training_action(s, "add_student", {})
    apply_training_action(s, "create_paper", {"subject": "数学", "questionCount": 5})
    apply_training_action(s, "review_paper", {})
    apply_training_action(s, "assign", {})
    apply_training_action(s, "switch_to_student", {})
    paper = s.data["papers"][0]
    answers = _correct_answers(paper)
    app = next(q for q in paper["questions"] if q["type"] == "简短应用题")
    answers[str(app["id"])] = "10 元"
    apply_training_action(s, "student_submit", {"answers": answers})
    assert s.data["submissions"][0]["score"] == 100

    s2 = teacher_session()
    apply_training_action(s2, "create_class", {"grade": 5})
    apply_training_action(s2, "add_student", {})
    apply_training_action(s2, "create_paper", {"subject": "数学", "questionCount": 5})
    apply_training_action(s2, "review_paper", {})
    apply_training_action(s2, "assign", {})
    apply_training_action(s2, "switch_to_student", {})
    paper2 = s2.data["papers"][0]
    answers2 = _correct_answers(paper2)
    app2 = next(q for q in paper2["questions"] if q["type"] == "简短应用题")
    answers2[str(app2["id"])] = "10"
    apply_training_action(s2, "student_submit", {"answers": answers2})
    assert s2.data["submissions"][0]["score"] < 100


def test_training_subject_default_knowledge_stays_coherent():
    s = teacher_session()
    apply_training_action(s, "create_class", {"grade": 5})
    apply_training_action(s, "create_paper", {"subject": "英语", "knowledge": "小数乘法", "questionCount": 4})
    paper = s.data["papers"][0]
    assert paper["knowledge"] == "基础词汇与句型"
    assert all(q["knowledge"] == "基础词汇与句型" for q in paper["questions"])
