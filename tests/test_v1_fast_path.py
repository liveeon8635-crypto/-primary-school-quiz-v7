import subprocess
import sys
import textwrap


def run_isolated(code: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        text=True,
        capture_output=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_final_v1_uses_aggregate_teacher_reads_without_class_request_fanout():
    run_isolated(
        """
        from fastapi.testclient import TestClient
        from app import app
        from changying.web.v1_fast_path import V1_FAST_PATH_MARKER

        html = TestClient(app).get('/v1').text
        assert V1_FAST_PATH_MARKER in html
        assert "/teacher/v1-bootstrap" in html
        assert "/teacher/v1-roster" in html
        assert "/teacher/v1-profiles" in html
        assert "api('/teacher/classes/'+c.id+'/students')" not in html
        assert "readJson('/teacher/classes/'+c.id+'/students')" not in html
        assert "studentProfiles(){const data=await readJson('/teacher/v1-profiles')" in html
        assert "return await readJson('/teacher/workbench-summary',0)" in html
        assert "await fastWorkbench()" in html
        """
    )


def test_aggregate_routes_are_get_only_and_keep_authentication_boundary():
    run_isolated(
        """
        from fastapi.testclient import TestClient
        from app import app

        expected = {
            '/teacher/v1-roster',
            '/teacher/v1-bootstrap',
            '/teacher/v1-profiles',
        }
        routes = {r.path: set(r.methods or []) for r in app.routes if getattr(r, 'path', None) in expected}
        assert set(routes) == expected
        for path, methods in routes.items():
            assert methods == {'GET'}, (path, methods)

        client = TestClient(app)
        for path in expected:
            response = client.get(path)
            assert response.status_code in {401, 403}, (path, response.status_code, response.text)
        """
    )


def test_fast_path_reuses_student_detail_and_workspace_payloads():
    run_isolated(
        """
        from fastapi.testclient import TestClient
        from app import app

        html = TestClient(app).get('/v1').text
        assert "window.__cyV1Bootstrap" in html
        assert "window.__cyV1Roster" in html
        assert "window.__cyV1StudentProfile={id,profile}" in html
        assert "window.__cyV1StudentProfile?.id===id" in html
        assert (
            "汇总当前可见学生的历史教学与时间线记录。" in html
            or "不再一次性加载所有人的完整历史" in html
            or "这里用于查看已经结束的班级、学期或课程记录" in html
        )
        """
    )
