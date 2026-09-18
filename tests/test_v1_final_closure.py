import subprocess
import sys
import textwrap

from changying.web.v1_final_closure import (
    V1_FINAL_CLOSURE_MARKER,
    patch_v1_final_closure,
)


FIXTURE = """<!doctype html><body>
<script>
window.__cyV1PeopleLoadWarnings=[];
async function studentIndex(){let people=[];try{people=await loadPeople()}catch(err){}return people}
async function workspace(){try{await loadPeople()}catch(err){if(err.status===428){await openClassic('/v1/tool?page=account');return}}}
</script>
<script id="changying_v1_membership_reliability_v1-script"></script>
<!-- changying_v1_membership_reliability_v1 -->
</body>"""


def patched_fixture() -> str:
    return patch_v1_final_closure(FIXTURE)


def test_all_v1_routes_render_after_final_closure_in_isolated_runtime():
    # Importing app installs a stack of presentation monkey-patches. Run the
    # integration acceptance in a fresh interpreter so this test cannot leak
    # that global state into unit tests collected in the same pytest process.
    code = textwrap.dedent(
        """
        from fastapi.testclient import TestClient
        from app import app
        from changying.web.v1 import V1_PATHS
        from changying.web.v1_final_closure import V1_FINAL_CLOSURE_MARKER
        from changying.web.v1_membership_reliability import V1_MEMBERSHIP_RELIABILITY_MARKER

        client = TestClient(app)
        for path in V1_PATHS:
            response = client.get(path)
            assert response.status_code == 200, (path, response.status_code)
            assert V1_FINAL_CLOSURE_MARKER in response.text, path
            assert V1_MEMBERSHIP_RELIABILITY_MARKER in response.text, path
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_top_level_roster_and_workspace_failures_are_explicit():
    html = patched_fixture()

    assert "学生列表读取失败：" in html
    assert "工作台读取失败：" in html
    assert "window.__cyV1PeopleLoadWarnings=['学生列表读取失败：'" in html
    assert "window.__cyV1PeopleLoadWarnings=['工作台读取失败：'" in html


def test_unexpected_browser_read_failures_offer_a_generic_retry():
    html = patched_fixture()

    assert "页面读取出现异常，当前显示可能不完整" in html
    assert "这不代表学生、班级或教学记录不存在" in html
    assert "data-cy-v1-retry" in html
    assert "window.addEventListener('unhandledrejection'" in html
    assert "window.addEventListener('error'" in html


def test_final_closure_patch_is_idempotent_and_read_only():
    once = patched_fixture()
    twice = patch_v1_final_closure(once)

    assert twice == once
    assert once.count(V1_FINAL_CLOSURE_MARKER) >= 1
    for verb in ("method:'POST'", 'method:"POST"', "method:'PUT'", "method:'DELETE'", "method:'PATCH'"):
        assert once.count(verb) == FIXTURE.count(verb)
