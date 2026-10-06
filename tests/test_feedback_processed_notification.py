"""Feedback #308: processed feedback must surface a direct verification CTA
in the live product-assistant feedback dropdown.
"""

from fastapi.testclient import TestClient

from app import app


def test_processed_feedback_dropdown_has_direct_acceptance_cta():
    response = TestClient(app).get("/v1/workspace")
    assert response.status_code == 200
    html = response.text
    assert "canConfirm=x.canConfirm===true" in html
    assert 'data-pa-dropdown-review="' in html
    assert "已处理 · 点击去验收" in html
    assert "feedbackReviewHref(x)" in html


def test_processed_feedback_cta_preserves_followup_and_record_actions():
    response = TestClient(app).get("/v1/workspace")
    assert response.status_code == 200
    html = response.text
    assert 'data-pa-dropdown-open="' in html
    assert 'data-pa-dropdown-followup="' in html
    assert "追加反馈（可传照片）" in html


def test_login_processed_notification_filters_and_opens_exact_record():
    import shutil
    import subprocess
    import pytest
    from changying.web.v1_product_assistant import _ASSISTANT_SNIPPET

    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the assistant notification behavior check")
    start = _ASSISTANT_SNIPPET.index("  // Login notification reads")
    end = _ASSISTANT_SNIPPET.index("  const observedIdentityNodes=", start)
    setup = "\nconst assert=require('node:assert/strict');\nlet token='user-a',ready=true,calls=0,opens=0,rows=[];\nconst notice={hidden:true,children:[],replaceChildren(){this.children=[]},appendChild(x){this.children.push(x)}};\nconst document={getElementById(){return notice},createElement(tag){return{tag,setAttribute(){}}}};\nconst location={origin:'https://school.example',search:''};\nconst panel={hidden:true};\nconst readToken=()=>token,identityReady=()=>ready,setTab=()=>{},openPanel=()=>{opens++;panel.hidden=false};\nconst fetch=async()=>{calls++;return{ok:true,json:async()=>({records:rows})}};\n"
    checks = "\n(async()=>{\n  rows=[{id:1,canConfirm:false},{id:2,canConfirm:true,terminalAccepted:true},{id:3,canConfirm:true,acknowledged:true},{id:4,canConfirm:true,userDecision:{status:'confirmed'}}];\n  await checkProcessedFeedbackNotice();assert.equal(notice.hidden,true);assert.equal(opens,0);\n  noticeCheckedAt=0;rows=[{id:325,canConfirm:true,message:'布置作业提交问题'}];\n  await checkProcessedFeedbackNotice();\n  assert.equal(notice.hidden,false);assert.equal(opens,0);\n  assert.equal(notice.children.length,1);assert.equal(notice.children[0].textContent,'反馈待验收 · 点击查看');\n  assert.equal(notice.children[0].href,'/v1/workspace?tab=feedback-records&focus=325');\n  await checkProcessedFeedbackNotice();assert.equal(calls,2);\n  noticeCheckedAt=0;await checkProcessedFeedbackNotice();assert.equal(opens,0);\n  token='user-b';rows=[];await checkProcessedFeedbackNotice();\n  assert.equal(notice.hidden,true);assert.equal(notice.children.length,0);\n  resetProcessedNotice();assert.equal(shownProcessedFeedback.size,0);\n  assert.equal(pendingProcessedFeedback([{id:'bad',canConfirm:true},{id:9,canConfirm:true}]).length,1);\n  console.log('login notification behavior passed');\n})().catch(error=>{console.error(error);process.exit(1)});\n"
    result = subprocess.run(
        [node], input=setup + _ASSISTANT_SNIPPET[start:end] + checks,
        text=True, capture_output=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "login notification behavior passed" in result.stdout


def test_login_notification_is_mounted_and_checked_after_identity_ready():
    html = TestClient(app).get("/v1/workspace").text
    assert 'id="cy-pa-processed-notice"' in html
    assert 'data-feedback-notification-revision="2"' in html
    assert "checkProcessedFeedbackNotice();openInitialAssistantRoute()" in html


def test_login_notification_is_a_compact_fab_bubble_without_motion_dependency():
    from changying.web.v1_product_assistant import _ASSISTANT_SNIPPET

    assert "position:fixed;right:70px" in _ASSISTANT_SNIPPET
    assert "cy-pa-notice-pulse" in _ASSISTANT_SNIPPET
    assert "prefers-reduced-motion:reduce" in _ASSISTANT_SNIPPET
    assert "if(panel.hidden&&tab!=='feedback-records'){setTab('ask');openPanel()}" not in _ASSISTANT_SNIPPET
