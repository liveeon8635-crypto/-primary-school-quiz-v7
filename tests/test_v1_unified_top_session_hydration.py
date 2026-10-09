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
    for label in ("当前教学", "全部功能", "操作记录"):
        assert label in html
    # 学生 / 往期教学 / 升学衔接 now live inside the V1 全部功能 view, not the chrome.
    assert "['students','◉','学生'" not in html


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


def test_mobile_student_nav_keeps_core_learning_tabs_and_moves_secondary_tools_to_more():
    html = inject_v1_classic_unified("<html><body></body></html>")
    assert "student:[['syncLearning','▦','课堂','syncLearning']" in html
    assert "['assignments','✓','作业','assignments']" in html
    assert "['practice','✎','练习','practice']" in html
    assert "['progress','◉','学情','progress']" in html
    assert "['tools','☰','更多','#']" in html
    assert "#cy-v1-unified-picker{display:none!important}" in html
    assert "#cy-v1-unified-identity{display:inline-flex" in html


def test_unified_student_assignment_cards_show_assigned_due_submit_and_learning_context():
    legacy = """<html><body>
    <small>${esc(a.assignedClassName||"")} · ${esc(a.submissionModeName||"在线答题")} · 截止 ${esc(a.dueDate)}${a.score!==null?` · 成绩 ${a.score}分`:""}</small>
    <p>${esc(latest.title||"最近练习")} · ${esc(latest.submittedAt||"")}</p>
    </body></html>"""
    html = inject_v1_classic_unified(legacy)
    assert "布置 ${esc(a.assignedAt||\"时间未记录\")}" in html
    assert "截止 ${esc(a.dueDate||\"未设置\")}" in html
    assert "提交 ${esc(a.quizSubmittedAt)}" in html
    assert "a.paper?.subject" in html
    assert "a.paper?.textbook" in html
    assert "a.paper?.questionIDs" in html
    assert "latest.subject" in html
    assert "latest.textbook" in html
    assert "提交 ${esc(latest.submittedAt||\"时间未记录\")}" in html
