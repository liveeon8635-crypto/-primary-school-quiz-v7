from changying.web.v1_classic_embed_bootstrap import inject_v1_classic_embed
from changying.web.v1_unified_tools import unified_tool_html


def test_runtime_v1_student_assignment_has_real_start_action():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert "changying_v1_student_assignment_launch_v1" in html
    assert "开始答题" in html
    assert "/v1/tool?page=assignments&assignment=" in html
    assert "!x.completed&&!x.quizSubmitted" in html


def test_unified_tool_forwards_assignment_deep_link_once():
    html = unified_tool_html()
    assert "deepAssignment=params.get('assignment')" in html
    assert "deepAssignmentUsed=false" in html
    assert "page==='assignments'" in html
    assert "'&assignment='" in html
    assert "\\n  let deepAssignmentUsed" not in html


def test_embedded_classic_bootstrap_auto_opens_deep_linked_assignment():
    html = inject_v1_classic_embed("<html><body></body></html>")
    assert "deepAssignment=Number(params.get('assignment')" in html
    assert "startAssignment(deepAssignment)" in html
    assert "deepAssignmentOpened=true" in html
