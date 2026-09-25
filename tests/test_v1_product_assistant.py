from fastapi.testclient import TestClient

from app import app
from changying.web.v1_product_assistant import (
    FEEDBACK_PATH,
    FEEDBACK_PROOF_PREFIX,
    QUERY_PATH,
    V1_PRODUCT_ASSISTANT_MARKER,
)


def rendered_v1() -> str:
    response = TestClient(app).get("/v1")
    assert response.status_code == 200
    return response.text


def test_product_assistant_ui_is_present_but_hidden_before_authenticated_identity():
    html = rendered_v1()

    assert V1_PRODUCT_ASSISTANT_MARKER in html
    assert 'id="cy-product-assistant-fab" hidden' in html
    assert "readToken()&&(identityButton?identityButton.hidden===false" in html
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
    assert "identity:String(identityChip?.textContent||'').trim()" in html
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
    assert "identityObserver.observe(identityButton" in html
    assert "identityObserver.observe(identityChip" in html


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
    assert "document.getElementById('identityChip')||document.getElementById('cy-v1-unified-identity')||document.getElementById('identity')" in html
    assert "正在识别" in html
    assert "const classicToken=()=>{" in html
    assert "state?.token" in html
    assert QUERY_PATH in html
    assert FEEDBACK_PATH in html


def test_product_assistant_rechecks_auth_after_classic_refresh_hydration():
    html = rendered_v1()

    assert "authReadyPoll=setInterval(syncUntilReady,400)" in html
    assert "setTimeout(()=>{if(authReadyPoll){clearInterval(authReadyPoll);authReadyPoll=null}sync()},12000)" in html
    assert "window.addEventListener('focus',sync)" in html
    assert "document.addEventListener('visibilitychange'" in html
