"""Regression coverage for feedback #335 against the real Classic assignment UI."""

from fastapi.testclient import TestClient

from app import app as production_app
from changying.web.classic_ui import patch_classic_paper_submit_flow


def assignment_fragment():
    return (
        'function assignmentForm(classes){'
        '$("#saveAssignment").onclick=async()=>{try{'
        'const o=$("#ac").selectedOptions[0],grade=+o.dataset.grade,class_id=+o.value,'
        'studentCount=+o.dataset.count,subject=$("#as").value,textbook=$("#ab").value,'
        'unit=$("#au").value,mode=$("#am").value,instructions=$("#ai").value.trim();'
        'await api("/teacher/papers",{method:"POST",body:JSON.stringify({title:$("#at").value})});'
        'await api("/teacher/assignments",{method:"POST",body:JSON.stringify({title:$("#at").value})});'
        '}catch(e){toast(e.message)}};'
        '}async function fetchHomeworkMediaBlob(id){}'
    )


def test_classic_assignment_submit_is_validated_single_flight_and_retryable():
    patched = patch_classic_paper_submit_flow(assignment_fragment())

    assert "changying_feedback_335_submit_v1" in patched
    assert "if(submitInFlight)return" in patched
    assert 'submitButton.disabled=true' in patched
    assert 'submitButton.textContent="正在提交作业…"' in patched
    assert '请选择要布置作业的班级' in patched
    assert '请填写作业名称' in patched
    assert '作业未布置：' in patched
    assert 'submitButton.disabled=false' in patched
    assert 'api("/teacher/papers"' in patched
    assert 'api("/teacher/assignments"' in patched
    assert patch_classic_paper_submit_flow(patched) == patched


def test_production_classic_papers_page_has_the_recoverable_submit_flow():
    response = TestClient(production_app).get(
        "/classic?legacy=1&unified=1&page=papers",
        headers={"Accept-Encoding": "identity"},
    )

    assert response.status_code == 200
    assert "changying_feedback_335_submit_v1" in response.text
    assert 'submitButton.textContent="正在提交作业…"' in response.text
    assert 'api("/teacher/assignments"' in response.text
