from changying.web.v1_completion import (
    V1_COMPLETION_MARKER,
    patch_v1_completion_html,
)


def test_completion_patch_is_idempotent_and_read_only():
    html = patch_v1_completion_html("<html><body><div id='screen'></div></body></html>")

    assert V1_COMPLETION_MARKER in html
    assert "cy-cmp-student-q" in html
    assert "cy-cmp-history-project" in html
    assert "cy-cmp-transition-readiness" in html
    assert "STEP ${String(i+1).padStart(2,'0')}" in html
    assert "readJson('/teacher/students/'" in html
    assert "method:'POST'" not in html
    assert "method: 'POST'" not in html
    assert patch_v1_completion_html(html) == html


def test_completion_patch_keeps_truthful_history_boundary():
    html = patch_v1_completion_html("<html><body></body></html>")

    assert "还没有标准化的“学年/学期”字段" in html
    assert "不伪造学年数据" in html
    assert "不会被此页面自动修改" in html
    assert "计划保存、自动分析和年级变更仍未开放" in html


def test_completion_patch_requires_body_marker():
    try:
        patch_v1_completion_html("<html></html>")
    except RuntimeError as exc:
        assert "closing body marker" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_completion_view_uses_shared_remember_aware_auth_storage():
    from changying.web import v1_completion
    snippet = v1_completion._COMPLETION_SNIPPET
    assert "v717Remember" in snippet
    assert "sessionStorage.getItem('v717Token')" in snippet
    assert "localStorage.getItem('v717Token')" in snippet
