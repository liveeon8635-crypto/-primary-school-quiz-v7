from fastapi.testclient import TestClient

from app import app
from changying.web.v1_product_assistant import (
    FEEDBACK_PATH,
    FEEDBACK_PROOF_PREFIX,
    QUERY_PATH,
    V1_PRODUCT_ASSISTANT_MARKER,
    _PRODUCT_CONTEXT,
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
    assert "fab.hidden=!ready" in html


def test_product_assistant_has_question_and_feedback_modes():
    html = rendered_v1()

    assert ">提问</button>" in html
    assert ">反馈</button>" in html
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
    assert "sizeButton.onclick=()=>{panel.hidden=true}" in html


def test_product_assistant_and_feedback_routes_require_authentication():
    client = TestClient(app)

    q = client.post(QUERY_PATH, json={"question": "我现在该做什么？"})
    f = client.post(FEEDBACK_PATH, json={"message": "这里不好懂"})

    assert q.status_code == 401
    assert f.status_code == 401


def test_feedback_ui_warns_against_sensitive_information():
    html = rendered_v1()

    assert "不要填写密码、API Key" in html
    assert "自动带上当前页面、身份和新手步骤" in html


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


def test_product_assistant_collapses_to_bubble_and_uses_plain_text():
    html = rendered_v1()

    assert 'id="cy-product-assistant-fab" hidden aria-label="打开产品助手"' in html
    assert "width:44px;height:44px" in html
    assert 'id="cy-pa-size"' in html
    assert "sizeButton.onclick=()=>{panel.hidden=true}" in html
    assert "fab.onclick=()=>{panel.hidden=false;updateContext()}" in html
    assert "normalizeReply" in html
    assert "replace(/\\*\\*/g,'')" in html
    assert "不要使用 Markdown 粗体" in _PRODUCT_CONTEXT


def test_feedback_surface_is_short_and_clear():
    html = rendered_v1()

    assert "问题类型" in html
    assert "一句话说明问题或建议" in html
    assert "min-height:76px" in html
    assert "提交反馈" in html


def test_all_functions_shell_also_includes_product_assistant():
    response = TestClient(app).get("/v1/tool")
    assert response.status_code == 200
    html = response.text

    assert V1_PRODUCT_ASSISTANT_MARKER in html
    assert 'id="cy-product-assistant-fab" hidden' in html
    assert "document.getElementById('identityChip')||document.getElementById('identity')" in html
    assert QUERY_PATH in html
    assert FEEDBACK_PATH in html
