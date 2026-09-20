from changying.web.v1_classic_unified_top import inject_v1_classic_unified


def test_unified_top_hydrates_from_existing_v1_session():
    html = inject_v1_classic_unified("<html><body></body></html>")
    assert "function v1Token()" in html
    assert "fetch('/session'" in html
    assert "Authorization:'Bearer '+t" in html
    assert "state.token=t" in html
    assert "state.user=u" in html
    assert "validateSavedSession" in html


def test_unified_top_only_posts_to_bounded_auth_handoff_and_adds_no_business_writes():
    html = inject_v1_classic_unified("<html><body></body></html>")
    assert "password" not in html.lower()
    assert html.count("method:'POST'") == 1
    assert "fetch('/v1/auth-handoff/consume',{method:'POST'" in html
    assert "method:'PUT'" not in html
    assert "method:'PATCH'" not in html
    assert "method:'DELETE'" not in html


def test_unified_top_keeps_chinese_navigation():
    html = inject_v1_classic_unified("<html><body></body></html>")
    for label in ("当前教学", "学生", "往期教学", "升学衔接", "全部功能", "操作记录"):
        assert label in html


def test_unified_top_fallback_respects_remember_storage_contract():
    html = inject_v1_classic_unified("<html><body></body></html>")
    assert "v717Remember" in html
    assert "remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token')" in html
    assert "sessionStorage.getItem('v717Token')" in html
    assert "localStorage.getItem('v717Token')" in html
    assert "sessionStorage.getItem('v6Token')" in html
    assert "localStorage.getItem('v6Token')" in html


def test_unified_top_validates_saved_state_instead_of_leaving_login_screen_visible():
    html = inject_v1_classic_unified("<html><body></body></html>")
    handoff_index = html.index("if(fromV1)bridge=await consumeV1Handoff()")
    saved_index = html.index("else if(stateReady())")
    assert handoff_index < saved_index
    assert "var savedOk=await Promise.resolve(validateSavedSession())" in html
    assert "else if(typeof enter==='function'){enter()}" in html
    assert "if(stateReady()){clearV1FromMarker();return true}" not in html



def test_unified_top_all_functions_is_not_a_self_redirect_and_has_account_switch():
    html = inject_v1_classic_unified("<html><body></body></html>")
    assert "function showToolHub()" in html
    assert "data-tool-hub" in html
    assert "function switchAccount()" in html
    assert "id=\"cy-v1-switch-account\"" in html
    assert "切换账号" in html
    assert "location.replace('/v1')" in html
    assert "localStorage.removeItem('cyV1Identity')" in html


def test_unified_top_opens_requested_hub_after_session_hydration():
    html = inject_v1_classic_unified("<html><body></body></html>")
    assert "params.get('page')==='__hub__'" in html
    assert "showToolHub()" in html
