import inspect

from fastapi.testclient import TestClient

from app import app
import app_v924 as legacy


def rendered_v1() -> str:
    return TestClient(app).get("/v1").text


def test_student_mobile_shell_has_persistent_account_switch_and_compact_bottom_nav():
    html = rendered_v1()

    assert "changying_v1_student_mobile_polish_v1" in html
    assert 'id="cy-v1-account-switch"' in html or "cy-v1-account-switch" in html
    assert "切换账号" in html
    assert "不会删除任何学习记录" in html
    assert "left:0!important;right:0!important;bottom:0!important" in html
    assert ".bottom a.active:before" in html


def test_single_identity_button_can_stay_hidden_because_account_switch_is_separate():
    html = rendered_v1()

    assert "identityButton.hidden=choices.length<=1" in html
    assert "cy-v1-account-switch" in html


def test_student_record_polish_reads_real_assignment_metadata_and_submission_times():
    html = rendered_v1()

    assert "renderAssignments(rows)" in html
    assert "renderTimeline(rows)" in html
    assert "x.assignedAt||x.createdAt" in html
    assert "x.submittedAt||x.quizSubmittedAt||x.mediaSubmittedAt" in html
    assert "questionCount" in html
    assert "AI 针对性练习" in html


def test_student_assignment_api_exposes_detail_needed_by_mobile_record():
    source = inspect.getsource(legacy.sassign)

    assert '"assignedAt":school_local_iso(assigned_at)' in source
    assert '"createdAt":school_local_iso(a.created_at)' in source
    assert '"subject":paper.get("subject","")' in source
    assert '"textbook":paper.get("textbook","")' in source
    assert '"questionCount":len(paper.get("questionIDs") or [])' in source
