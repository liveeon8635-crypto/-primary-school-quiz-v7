from changying.web.rubric_review_ui import (
    RUBRIC_REVIEW_UI_MARKER,
    inject_rubric_review_ui,
)


def test_rubric_review_ui_injection_is_idempotent():
    base = '<html><body><script>function aiIssueRows(result){return "base"}</script></body></html>'
    once = inject_rubric_review_ui(base)
    twice = inject_rubric_review_ui(once)
    assert once == twice
    assert RUBRIC_REVIEW_UI_MARKER in once
    assert "评分要点核对" in once
    assert "AI建议完成度" in once
    assert "已达到" in once
    assert "未达到" in once
    assert "需教师确认" in once
    assert "步骤部分得分" in once
    assert "评分点等权折算" in once
    assert "window.aiIssueRows=function" in once


def test_rubric_review_ui_uses_backend_confirmation_notice():
    base = '<html><body><script>toast("教师确认已保存，错题已归档")</script></body></html>'
    html = inject_rubric_review_ui(base)
    assert 'toast(x.notice||"教师确认已保存，错题与学习证据已更新")' in html


def test_runtime_classic_html_contains_rubric_review_ui():
    import app  # noqa: F401
    import app_v924 as legacy

    html = legacy.INDEX_HTML
    assert RUBRIC_REVIEW_UI_MARKER in html
    assert "评分要点核对" in html
    assert "rubric_results" in html
    assert "最终分数仍由教师确认" in html
    assert "步骤部分得分" in html
