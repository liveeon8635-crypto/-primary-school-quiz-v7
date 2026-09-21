from fastapi.testclient import TestClient

from app import app


def test_classic_student_sync_surfaces_live_classroom_quick_check():
    response = TestClient(app).get(
        "/classic?legacy=1&unified=1&page=syncLearning",
        headers={"Accept-Encoding": "identity"},
    )
    assert response.status_code == 200
    html = response.text
    assert 'api("/student/classroom-quick-checks")' in html
    assert "课堂互动进行中" in html
    assert "enterClassroomQuickCheck" in html
    assert "function studentLiveQuickCheckModal(q)" in html
    assert "/student/classroom-quick-checks/${q.id}/respond" in html
    assert "不会自动加分" in html
    assert "不会自动改写长期知识掌握记录" in html
