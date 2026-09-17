from changying.web.v1_classic_unified_top import inject_v1_classic_unified


def test_unified_top_hydrates_from_existing_v1_session():
    html = inject_v1_classic_unified("<html><body></body></html>")
    assert "function v1Token()" in html
    assert "fetch('/session'" in html
    assert "Authorization:'Bearer '+t" in html
    assert "state.token=t" in html
    assert "state.user=u" in html
    assert "validateSavedSession" in html


def test_unified_top_does_not_add_credentials_or_writes():
    html = inject_v1_classic_unified("<html><body></body></html>")
    assert "password" not in html.lower()
    assert "method:'POST'" not in html
    assert "method:'PUT'" not in html
    assert "method:'PATCH'" not in html
    assert "method:'DELETE'" not in html


def test_unified_top_keeps_chinese_navigation():
    html = inject_v1_classic_unified("<html><body></body></html>")
    for label in ("当前教学", "学生", "往期教学", "升学衔接", "全部功能", "操作记录"):
        assert label in html
