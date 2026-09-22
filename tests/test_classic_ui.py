from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.testclient import TestClient

from changying.web.classic_ui import (
    CLASSIC_UI_MARKER,
    inject_classic_ui,
    patch_classic_local_due_dates,
    install_classic_ui_patch,
    is_classic_html_path,
)


def test_classic_ui_path_detection_is_narrow():
    assert is_classic_html_path("/classic")
    assert not is_classic_html_path("/")
    assert not is_classic_html_path("/health")
    assert not is_classic_html_path("/admin/overview")


def test_inject_classic_ui_preserves_original_html_and_is_idempotent():
    html = "<html><head><title>旧系统</title></head><body><main>legacy</main></body></html>"

    once = inject_classic_ui(html)
    twice = inject_classic_ui(once)

    assert "<main>legacy</main>" in once
    assert "长缨辅学 V1" in once
    assert "今日教学快捷入口" in once
    assert "学生管理" in once
    assert "题库组卷" in once
    assert "成绩分析" in once
    assert "data-cy-action" in once
    assert CLASSIC_UI_MARKER in once
    assert once == twice


def test_classic_ui_middleware_enhances_only_classic_html():
    app = FastAPI()

    @app.get("/classic")
    def classic():
        return HTMLResponse("<html><body><main>legacy-home</main></body></html>")

    @app.get("/admin/overview")
    def overview():
        return JSONResponse({"students": 2})

    install_classic_ui_patch(app)

    client = TestClient(app)
    classic_response = client.get("/classic")
    api_response = client.get("/admin/overview")

    assert classic_response.status_code == 200
    assert classic_response.headers["X-Changying-Classic-UI"] == CLASSIC_UI_MARKER
    assert "legacy-home" in classic_response.text
    assert "长缨辅学教学系统" in classic_response.text
    assert "今日教学快捷入口" in classic_response.text
    assert "/v1" in classic_response.text

    assert api_response.status_code == 200
    assert api_response.json() == {"students": 2}
    assert "X-Changying-Classic-UI" not in api_response.headers


def test_classic_ui_patch_install_is_idempotent():
    app = FastAPI()

    @app.get("/classic")
    def classic():
        return HTMLResponse("<html><body>legacy</body></html>")

    install_classic_ui_patch(app)
    install_classic_ui_patch(app)

    response = TestClient(app).get("/classic")
    assert response.status_code == 200
    assert response.text.count(CLASSIC_UI_MARKER) >= 1

def test_classic_ui_middleware_preserves_gzip_encoded_html():
    app = FastAPI()

    @app.get("/classic")
    def classic():
        return HTMLResponse("<html><body><main>legacy-compressed</main></body></html>")

    app.add_middleware(GZipMiddleware, minimum_size=1)
    install_classic_ui_patch(app)

    response = TestClient(app).get("/classic", headers={"Accept-Encoding": "gzip"})

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert "legacy-compressed" in response.text
    assert "X-Changying-Classic-UI" not in response.headers



def test_classic_assignment_defaults_use_local_calendar_dates():
    html = """
    <script>
    const a=new Date(Date.now()+7*86400000).toISOString().slice(0,10);
    const b=new Date(Date.now()+3*86400000).toISOString().slice(0,10);
    </script>
    """
    patched = patch_classic_local_due_dates(html)
    assert "Date.now()+7*86400000" not in patched
    assert "Date.now()+3*86400000" not in patched
    assert "toISOString().slice(0,10)" not in patched
    assert "d.setDate(d.getDate()+7)" in patched
    assert "d.setDate(d.getDate()+3)" in patched
    assert "d.getFullYear()" in patched


def test_classic_local_date_patch_runs_even_after_ui_marker_is_present():
    html = f"<html><body>{CLASSIC_UI_MARKER}<script>const due=new Date(Date.now()+7*86400000).toISOString().slice(0,10)</script></body></html>"
    patched = inject_classic_ui(html)
    assert "Date.now()+7*86400000" not in patched
    assert "d.setDate(d.getDate()+7)" in patched


def test_production_classic_html_has_no_utc_assignment_default_expressions():
    from app import app as production_app

    response = TestClient(production_app).get(
        "/classic?legacy=1&unified=1&page=papers",
        headers={"Accept-Encoding": "identity"},
    )
    assert response.status_code == 200
    assert "Date.now()+7*86400000).toISOString().slice(0,10)" not in response.text
    assert "Date.now()+3*86400000).toISOString().slice(0,10)" not in response.text
    assert "function localDueDate(days=7)" in response.text
    assert "localDueDate(7)" in response.text
    assert "localDueDate(3)" in response.text


def test_production_classic_student_sync_exposes_open_classroom_quick_checks():
    from app import app as production_app

    response = TestClient(production_app).get(
        "/classic?legacy=1&unified=1&page=syncLearning",
        headers={"Accept-Encoding": "identity"},
    )

    assert response.status_code == 200
    assert 'api("/student/classroom-quick-checks")' in response.text
    assert "正在进行的课堂互动" in response.text
    assert "进入随堂检测" in response.text
    assert "classroomQuickChecksClassic" in response.text
    assert '"/student/classroom-quick-checks/"+b.dataset.id+"/respond"' in response.text
    assert "本次答案只用于当前课堂反馈，不会自动加分，也不会自动改写长期知识掌握记录。" in response.text


def test_production_classic_student_collection_bindings_use_query_selector_all():
    from app import app as production_app

    response = TestClient(production_app).get(
        "/classic?legacy=1&unified=1&page=syncLearning",
        headers={"Accept-Encoding": "identity"},
    )

    assert response.status_code == 200
    assert 'document.querySelectorAll(".openClassroomQuickCheck").forEach' in response.text
    assert 'document.querySelectorAll(".cy-classic-quick-submit").forEach' in response.text
    assert 'document.querySelectorAll(".enterSyncLesson").forEach' in response.text
    assert 'document.querySelectorAll(".startStageTest").forEach' in response.text
    assert '$(".openClassroomQuickCheck").forEach' not in response.text
    assert '$(".cy-classic-quick-submit").forEach' not in response.text



def test_production_classic_student_sync_exposes_presenter_invitations():
    from app import app as production_app

    response = TestClient(production_app).get(
        "/classic?legacy=1&unified=1&page=syncLearning",
        headers={"Accept-Encoding": "identity"},
    )

    assert response.status_code == 200
    assert 'api("/student/classroom-invitations")' in response.text
    assert "课堂讲解邀请" in response.text
    assert "查看课堂讲解邀请" in response.text
    assert "classroomInvitationsClassic" in response.text
    assert '"/student/classroom-invitations/"+b.dataset.id+"/respond"' in response.text
    assert 'JSON.stringify({response:"accepted"})' in response.text
    assert 'JSON.stringify({response:"declined"})' in response.text
    assert "婉拒不会扣分，也不会被记录为知识掌握不足" in response.text
    assert 'document.querySelectorAll(".openClassroomInvitation").forEach' in response.text
    assert 'document.querySelectorAll(".cy-classic-invite-accept").forEach' in response.text
    assert 'document.querySelectorAll(".cy-classic-invite-decline").forEach' in response.text
