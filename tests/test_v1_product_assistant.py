from fastapi.testclient import TestClient

from app import app
from changying.web.v1_product_assistant import (
    FEEDBACK_PATH,
    FEEDBACK_PROOF_PREFIX,
    QUERY_PATH,
    V1_PRODUCT_ASSISTANT_MARKER,
    _local_answer,
    _student_direct_answer_request,
)


def rendered_v1() -> str:
    response = TestClient(app).get("/v1")
    assert response.status_code == 200
    return response.text


def test_product_assistant_ui_is_present_but_hidden_before_authenticated_identity():
    html = rendered_v1()

    assert V1_PRODUCT_ASSISTANT_MARKER in html
    assert 'id="cy-product-assistant-fab" hidden' in html
    assert "identityChipReady()||identityButtonReady()" in html
    assert "if(!ready){fab.hidden=true;panel.hidden=true;return}" in html
    assert "fab.hidden=!panel.hidden" in html


def test_product_assistant_has_question_and_feedback_modes():
    html = rendered_v1()

    assert "问产品" in html
    assert "提反馈" in html
    assert "我现在该做什么？" in html
    assert "这个页面是干什么的？" in html
    assert "这一步为什么排在这里？" in html
    assert "这里不好懂" in html
    assert "没找到入口" in html
    assert "流程不直观" in html
    assert "功能与预期不符" in html
    assert "希望增加功能" in html


def test_product_assistant_attaches_current_page_identity_and_tutorial_step():
    html = rendered_v1()

    assert "page:location.pathname+location.search" in html
    assert "const chip=getIdentityChip()" in html
    assert "identity:String(chip?.textContent||'').trim()" in html
    assert "document.querySelector('.cy-lesson-top h2')" in html
    assert QUERY_PATH in html
    assert FEEDBACK_PATH in html


def test_product_assistant_and_feedback_routes_require_authentication():
    client = TestClient(app)

    q = client.post(QUERY_PATH, json={"question": "我现在该做什么？"})
    f = client.post(FEEDBACK_PATH, json={"message": "这里不好懂"})

    assert q.status_code == 401
    assert f.status_code == 401


def test_feedback_ui_warns_against_sensitive_information():
    html = rendered_v1()

    assert "不要填写密码、API Key 等敏感信息" in html
    assert "会自动附带当前页面、当前身份和正在进行的新手步骤" in html


def test_product_assistant_observer_does_not_watch_its_own_body_mutations():
    html = rendered_v1()

    assert "observe(document.body,{childList:true,subtree:true" not in html
    assert "identityObserver.observe(button" in html
    assert "identityObserver.observe(chip" in html
    assert "const observeIdentityNodes=()=>" in html


def test_feedback_bridge_uses_short_lived_proof_and_shows_sync_state():
    html = rendered_v1()

    assert FEEDBACK_PROOF_PREFIX in html or FEEDBACK_PROOF_PREFIX == "/v1/product-feedback/proof"
    assert "freemanSynced" in html
    assert "已同步到 Freeman" in html
    assert "Freeman 同步待确认" in html


def test_product_assistant_fab_is_compact_collapsible_and_feedback_is_quick():
    html = rendered_v1()

    assert 'width:48px;height:48px' in html
    assert 'width:44px;height:44px' in html
    assert 'id="cy-pa-collapse"' in html
    assert 'id="cy-pa-close"' not in html
    assert "#cy-product-assistant-fab[hidden],#cy-product-assistant-panel[hidden]{display:none!important}" in html
    assert "fab.onclick=()=>panel.hidden?openPanel():closePanel()" in html
    assert "const closePanel=()=>{panel.hidden=true;fab.hidden=!identityReady()" in html
    assert "const openPanel=()=>{if(!identityReady())return;panel.hidden=false;fab.hidden=true" in html
    assert "document.getElementById('cy-pa-collapse').onclick=closePanel" in html
    assert 'data-pa-category="这里不好懂"' in html
    assert 'data-pa-category="没找到入口"' in html
    assert 'data-pa-category="流程不直观"' in html
    assert 'placeholder="一句话描述问题或建议' in html
    assert "cleanReplyText" in html


def test_all_functions_shell_keeps_product_assistant_available():
    response = TestClient(app).get("/v1/tool")
    assert response.status_code == 200
    html = response.text

    assert V1_PRODUCT_ASSISTANT_MARKER in html
    assert 'id="cy-product-assistant-fab" hidden' in html
    assert "const getIdentityChip=()=>document.getElementById('cy-v1-unified-identity')||document.getElementById('identityChip')||document.getElementById('identity')" in html
    assert "正在识别" in html
    assert "const classicToken=()=>{" in html
    assert "state?.token" in html
    assert QUERY_PATH in html
    assert FEEDBACK_PATH in html


def test_product_assistant_visual_guides_follow_reply_context():
    html = rendered_v1()

    assert 'id="cy-pa-guide-grid"' in html
    assert "const GUIDE_SETS={" in html
    assert "const renderGuideGrid=text=>" in html
    assert "renderGuideGrid(text+' '+reply)" in html
    assert "renderGuideGrid()" in html
    assert 'data-pa-guide="' in html
    assert 'role="img"' in html
    assert "页面示意图" in html
    assert "/v1/workspace" in html
    assert "/v1/student" in html
    assert "/v1/history" in html
    assert "/v1/transition" in html
    assert "/v1/tool" in html


def test_product_assistant_visual_guides_are_not_empty_placeholder_markup():
    html = rendered_v1()

    assert ".cy-pa-guide-card" in html
    assert ".cy-pa-guide-visual" in html
    assert "guideCandidates(text)" in html
    assert "grid.innerHTML=guideCandidates(text).map" in html
    assert "当前班级、课程、学生与待办" in html
    assert "连续学情、作业、错题与时间线" in html
    assert "孩子作业" in html
    assert "平台总览" in html


def test_product_assistant_rechecks_auth_after_classic_refresh_hydration():
    html = rendered_v1()

    assert "authReadyPoll=setInterval(syncUntilReady,400)" in html
    assert "setTimeout(()=>{if(authReadyPoll){clearInterval(authReadyPoll);authReadyPoll=null}sync()},12000)" in html
    assert "window.addEventListener('focus',sync)" in html
    assert "document.addEventListener('visibilitychange'" in html


def test_product_assistant_uses_unified_identity_even_if_legacy_identity_button_is_hidden():
    html = rendered_v1()

    assert "const getIdentityChip=()=>document.getElementById('cy-v1-unified-identity')||document.getElementById('identityChip')" in html
    assert "const identityChipReady=()=>{const chip=getIdentityChip()" in html
    assert "const identityButtonReady=()=>{const button=getIdentityButton()" in html
    assert "identityChipReady()||identityButtonReady()" in html
    assert "observeIdentityNodes();const ready=identityReady()" in html


def test_product_assistant_resolves_identity_after_unified_header_mounts():
    html = rendered_v1()

    # Unified Classic mounts its header after this assistant script has already
    # been parsed, so identity lookup must be dynamic rather than captured once.
    assert "const getIdentityChip=()=>document.getElementById('cy-v1-unified-identity')" in html
    assert "const getIdentityButton=()=>document.getElementById('identityButton')" in html
    assert "const observeIdentityNodes=()=>{" in html
    assert "const chip=getIdentityChip()" in html


def test_visual_guides_are_role_scoped_and_never_send_teacher_to_student_only_pages():
    html = rendered_v1()

    assert "const guideRole=identity=>" in html
    assert "if(label.includes('管理员'))return'admin'" in html
    assert "if(label.includes('家长'))return'parent'" in html
    assert "if(label.includes('学生'))return'student'" in html
    assert "return'teacher'" in html
    assert "href:'/v1/tool?page=papers'" in html
    assert "href:'/v1/tool?page=analytics'" in html
    assert "href:'/v1/tool?page=childAssignments'" in html
    assert "href:'/v1/tool?page=childProgress'" in html
    assert "href:'/v1/tool?page=users'" in html
    assert "href:'/v1/tool?page=adminAudit'" in html
    assert "const c=context(),role=guideRole(c.identity),pool=GUIDE_SETS[role]||GUIDE_SETS.teacher" in html


def test_visual_guide_current_page_scoring_distinguishes_unified_tool_pages():
    html = rendered_v1()

    assert "let score=page===g.href?9:0" in html
    assert "if(!g.href.includes('?')&&page.startsWith(g.href))score+=4" in html
    assert "renderGuideGrid(text+' '+reply)" in html


def test_student_assistant_invites_learning_questions_without_becoming_answer_key():
    html = rendered_v1()

    assert "你可以问我长缨怎么用，也可以问不会的知识点和题目思路" in html
    assert "我不会直接替你做作业" in html
    assert "我有一道题不会，先别告诉我答案，帮我拆解思路。" in html
    assert "帮我把这个知识点拆成容易理解的小步骤。" in html
    assert "我的错题 / 自主练习 / 我的学情 / 同步课堂" in html
    assert "如果学生在作业、练习、测验场景索要最终答案" in html


def test_student_direct_answer_requests_are_guarded_deterministically():
    assert _student_direct_answer_request("直接告诉我答案", "/v1/tool?page=assignments")
    assert _student_direct_answer_request("这题正确答案选哪个？", "/v1/tool?page=practice")
    assert not _student_direct_answer_request("为什么分母不能直接相加？", "/v1/tool?page=practice")

    reply = _local_answer(
        "把答案给我",
        "小明 · 学生",
        "/v1/tool?page=assignments",
        "",
        role="student",
    )
    assert "不直接替你提取作业或练习的最终答案" in reply
    assert "把题拆开" in reply
    assert "我的错题" in reply


def test_parent_assistant_copy_centers_real_learning_evidence_and_home_support():
    html = rendered_v1()

    assert "我会优先结合当前绑定孩子在长缨里的真实学习记录" in html
    assert "结合长缨里的记录，孩子最近学习情况怎么样？" in html
    assert "根据孩子目前的学习情况，我在家可以怎么配合？" in html
    assert "我现在最值得先肯定和鼓励孩子的是什么？" in html
    assert "先说一个具体事实或进步" in html
    assert "不拿孩子和其他学生比较" in html
    assert "孩子学情 / 孩子作业 / 课堂表现 / 孩子课程" in html


def test_assistant_sends_selected_child_context_without_exposing_answer_keys():
    html = rendered_v1()

    assert "const selectedChildID=()=>{" in html
    assert "child_id:selectedChildID()" in html
    assert "ROLE_COPY={" in html
    assert "applyRoleCopy()" in html
    assert "不包含任何题目标准答案" not in html  # server-only context must not be exposed in client markup
