import base64
import hashlib

import pytest
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import app
from changying.web.v1_product_assistant import (
    FEEDBACK_PATH,
    FEEDBACK_PROOF_PREFIX,
    QUERY_PATH,
    V1_PRODUCT_ASSISTANT_MARKER,
    ProductAssistantBody,
    ProductFeedbackBody,
    _decode_feedback_attachment,
    _decode_assistant_image,
    _image_failure_reason,
    _PRODUCT_CONTEXT,
    _active_question_context,
    _clean_assistant_reply,
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
    assert "我的错题 / 自主练习 / 我的学情 / 同步课堂" in _PRODUCT_CONTEXT
    assert "如果学生在作业、练习、测验场景索要最终答案" in _PRODUCT_CONTEXT


def test_student_direct_answer_requests_are_guarded_deterministically():
    assert _student_direct_answer_request("直接告诉我答案", "/v1/tool?page=assignments")
    assert _student_direct_answer_request("这题正确答案选哪个？", "/v1/tool?page=practice")
    assert not _student_direct_answer_request("为什么分母不能直接相加？", "/v1/tool?page=practice")
    assert not _student_direct_answer_request("这几个功能我应该选哪个？", "/v1/tool?page=progress")

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
    assert "先说一个具体事实或进步" in _PRODUCT_CONTEXT
    assert "不拿孩子和其他学生比较" in _PRODUCT_CONTEXT
    assert "孩子学情 / 孩子作业 / 课堂表现 / 孩子课程" in _PRODUCT_CONTEXT


def test_assistant_sends_selected_child_context_without_exposing_answer_keys():
    html = rendered_v1()

    assert "const selectedChildID=()=>{" in html
    assert "child_id:selectedChildID()" in html
    assert "ROLE_COPY={" in html
    assert "applyRoleCopy()" in html
    assert "不包含任何题目标准答案" not in html  # server-only context must not be exposed in client markup


def test_student_assistant_detects_the_current_visible_quiz_question():
    html = rendered_v1()

    assert "const currentQuestionContext=()=>{" in html
    assert "selectors=['.question','[data-question-text]','.question-text','.question-stem','.stem']" in html
    assert "const assessmentSignals=options.length>0||Boolean(textInput)" in html
    assert "root.querySelector('.progress,#quizNext,#quitQuiz')" in html
    assert "active_assessment:true" in html
    assert "active_question_text:String(question.textContent||'').trim().slice(0,1600)" in html
    assert "active_question_options:options" in html
    assert "active_question_figure:[figureTitle,...figureTexts]" in html
    assert "active_question_response:response.slice(0,600)" in html
    assert "已关联当前题目" in html


def test_student_assistant_current_question_ui_becomes_contextual():
    html = rendered_v1()

    assert "帮我看当前题" in html
    assert "针对当前这题只给我一条提示，不要给答案。" in html
    assert "画个简图" in html
    assert "我已经关联到你正在做的当前题目" in html
    assert "不读取正确答案或解析" in html


def test_active_question_context_contains_only_student_visible_fields():
    body = ProductAssistantBody(
        question="这题怎么想？",
        page="/v1/tool?page=assignments",
        identity="小明 · 学生",
        active_assessment=True,
        active_question_text="一根绳子长12米，用去1/3，还剩多少米？",
        active_question_options=["A. 4米", "B. 8米", "C. 9米", "D. 11米"],
        active_question_meta="数学 · 分数应用",
        active_question_figure="外长 12 · 外宽 8",
        active_question_position="第 2/5 题",
        active_question_response="B. 8米",
    )
    value = _active_question_context(body)

    assert "一根绳子长12米" in value
    assert "B. 8米" in value
    assert "第 2/5 题" in value
    assert "外长 12 · 外宽 8" in value
    assert "不含正确答案或解析" in value
    assert "不得确认、暗示或排除某个选项是否正确" in value


def test_direct_answer_guard_treats_active_quiz_as_assessment_even_without_page_hint():
    assert _student_direct_answer_request(
        "告诉我结果",
        "/v1/tool",
        active_assessment=True,
    )
    assert not _student_direct_answer_request(
        "帮我找出这题的已知条件",
        "/v1/tool",
        active_assessment=True,
    )


def test_current_question_dom_capture_does_not_read_answer_keys():
    html = rendered_v1()
    start = html.index("const currentQuestionContext=()=>{")
    end = html.index("const context=()=>", start)
    snippet = html[start:end]

    assert "correctIndex" not in snippet
    assert "explanation" not in snippet
    assert "correctAnswer" not in snippet


def test_assistant_reply_normalizer_removes_common_model_formatting_noise():
    raw = "### 提示\n**先看条件**\n---\n- 找已知量\n\n\n\`\`\`text\n再试一步\n\`\`\`\n"
    cleaned = _clean_assistant_reply(raw)

    assert "###" not in cleaned
    assert "**" not in cleaned
    assert "---" not in cleaned
    assert "\`" not in cleaned
    assert "• 找已知量" in cleaned
    assert "\n\n\n" not in cleaned
    assert "先看条件" in cleaned
    assert "再试一步" in cleaned


def test_student_assistant_has_rule_based_learning_visuals_for_current_question():
    html = rendered_v1()

    assert "const questionVisualSpec=ctx=>" in html
    assert "type:'fraction'" in html
    assert "type:'bar'" in html
    assert "type:'shape'" in html
    assert "type:'numberline'" in html
    assert "const addLearningVisual=spec=>" in html
    assert "理解小图" in html
    assert "maybeAddLearningVisual(text,askContext)" in html


def test_learning_visuals_use_only_current_visible_question_context():
    html = rendered_v1()
    start = html.index("const questionVisualSpec=ctx=>")
    end = html.index("const addLearningVisual=spec=>", start)
    snippet = html[start:end]

    assert "active_question_text" in snippet
    assert "correctIndex" not in snippet
    assert "explanation" not in snippet
    assert "correctAnswer" not in snippet


def test_fraction_learning_visual_explains_structure_without_answer_key():
    html = rendered_v1()

    assert "把一个整体平均分成" in html
    assert "先看题目说的是其中哪" in html
    assert "正确答案" not in html[html.index("const addLearningVisual=spec=>"):html.index("const maybeAddLearningVisual=", html.index("const addLearningVisual=spec=>"))]


def test_client_reply_cleaner_handles_markdown_and_invisible_noise():
    html = rendered_v1()

    assert "replace(/[\\u200B\\uFEFF\\uFFFD]/g,'')" in html
    assert "replace(/^\\s*#{1,6}\\s*/gm,'')" in html
    assert "replace(/^\\s*[-*+]\\s+/gm,'• ')" in html
    assert "replace(/\\n{3,}/g,'\\n\\n')" in html


def test_current_question_detection_does_not_require_one_specific_next_button():
    html = rendered_v1()
    start = html.index("const currentQuestionContext=()=>{")
    end = html.index("const context=()=>", start)
    snippet = html[start:end]

    assert "if(!question||!next)" not in snippet
    assert "const assessmentSignals=" in snippet
    assert "提交答案|保存并下一题|提交整份|下一题" in snippet


def test_current_question_context_captures_visible_figure_labels_only():
    html = rendered_v1()
    start = html.index("const currentQuestionContext=()=>{")
    end = html.index("const context=()=>", start)
    snippet = html[start:end]

    assert 'svg[aria-label="题目图示"] text' in snippet
    assert "active_question_figure:" in snippet
    assert "correctIndex" not in snippet
    assert "explanation" not in snippet


def test_feedback_attachment_ui_and_product_copy():
    html = rendered_v1()
    assert 'id="cy-pa-feedback-file"' in html
    assert 'accept="image/jpeg,image/png,image/webp,application/pdf,text/plain"' in html
    assert "readFeedbackFile(file)" in html
    assert "attachment_data:await readFeedbackFile(file)" in html
    assert "产品反馈页可附一张照片或一个小文件" in _PRODUCT_CONTEXT


def test_feedback_attachment_validates_bytes_and_mime():
    raw = b"%PDF-1.4\\nsmall example"
    body = ProductFeedbackBody(
        message="PDF 预览异常", attachment_name="example.pdf",
        attachment_type="application/pdf", attachment_size=len(raw),
        attachment_data=base64.b64encode(raw).decode("ascii"),
    )
    assert _decode_feedback_attachment(body) == (raw, "example.pdf", "application/pdf")

    body.attachment_type = "image/png"
    with pytest.raises(HTTPException) as error:
        _decode_feedback_attachment(body)
    assert error.value.status_code == 422

    body.attachment_type = "application/pdf"
    body.attachment_size += 1
    with pytest.raises(HTTPException):
        _decode_feedback_attachment(body)


def test_feedback_attachment_rejects_missing_data_and_unsafe_file():
    with pytest.raises(HTTPException):
        _decode_feedback_attachment(ProductFeedbackBody(message="问题", attachment_name="x.pdf"))

    raw = b"not really a PDF"
    with pytest.raises(HTTPException):
        _decode_feedback_attachment(ProductFeedbackBody(
            message="问题", attachment_name="../x.pdf", attachment_type="application/pdf",
            attachment_size=len(raw), attachment_data=base64.b64encode(raw).decode("ascii"),
        ))


def test_feedback_attachment_is_saved_and_transferred_through_proof(monkeypatch):
    import app_v924 as implementation
    from changying.web import v1_product_assistant as assistant

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    attachment_table = implementation.Base.metadata.tables["product_feedback_attachments"]
    implementation.Base.metadata.create_all(
        engine, tables=[implementation.AuditLog.__table__, attachment_table]
    )
    session_factory = sessionmaker(bind=engine)
    user = SimpleNamespace(id=42, school_id=7, role="teacher")
    def db_override():
        with session_factory() as db:
            yield db
    app.dependency_overrides[implementation.current_user] = lambda: user
    app.dependency_overrides[implementation.get_db] = db_override
    monkeypatch.setattr(assistant.requests, "post", lambda *args, **kwargs: Mock(ok=True))
    raw = b"%PDF-1.4\\nfeedback"
    try:
        client = TestClient(app)
        posted = client.post(FEEDBACK_PATH, json={
            "message": "附件无法打开", "attachment_name": "problem.pdf",
            "attachment_type": "application/pdf", "attachment_size": len(raw),
            "attachment_data": base64.b64encode(raw).decode("ascii"),
        })
        assert posted.status_code == 200
        assert posted.json()["freemanSynced"] is True
        with session_factory() as db:
            audit = db.scalar(select(implementation.AuditLog).where(
                implementation.AuditLog.action == "product.feedback"
            ))
            assert audit is not None
            assert base64.b64encode(raw).decode("ascii") not in audit.detail
            token = __import__("json").loads(audit.detail)["transferToken"]
            saved = db.execute(select(attachment_table)).mappings().one()
            assert saved["file_data"] == raw
            assert saved["audit_id"] == audit.id
        proof = client.get(FEEDBACK_PROOF_PREFIX + "/" + token)
        assert proof.status_code == 200
        attachment = proof.json()["feedback"]["attachment"]
        assert attachment["name"] == "problem.pdf"
        assert base64.b64decode(attachment["data"]) == raw
        downloaded = client.get(FEEDBACK_PROOF_PREFIX + "/" + token + "/attachment")
        assert downloaded.status_code == 200
        assert downloaded.content == raw
        assert downloaded.headers["content-type"] == "application/pdf"
        assert 'filename="problem.pdf"' in downloaded.headers["content-disposition"]
        assert downloaded.headers["x-attachment-sha256"] == hashlib.sha256(raw).hexdigest()

        invalid = client.get(FEEDBACK_PROOF_PREFIX + "/" + ("x" * 24) + "/attachment")
        assert invalid.status_code == 404
    finally:
        app.dependency_overrides.pop(implementation.current_user, None)
        app.dependency_overrides.pop(implementation.get_db, None)
        engine.dispose()

def test_product_assistant_image_ui_and_request_path():
    html = rendered_v1()
    assert 'id="cy-pa-query-image"' in html
    assert 'accept="image/jpeg,image/png,image/webp"' in html
    assert "image_data:attachment.attachment_data" in html
    assert "cy-pa-sent-image" in html
    assert "if(!data.ok)throw new Error" in html


def test_product_assistant_image_validation_and_ai_handoff(monkeypatch):
    import app_v924 as implementation

    raw = b"\x89PNG\r\n\x1a\n" + b"test image"
    encoded = base64.b64encode(raw).decode("ascii")
    body = ProductAssistantBody(
        question="这张图是什么？", image_name="sample.png",
        image_type="image/png", image_size=len(raw), image_data=encoded,
    )
    assert _decode_assistant_image(body) == "data:image/png;base64," + encoded
    body.image_type = "application/pdf"
    with pytest.raises(HTTPException):
        _decode_assistant_image(body)
    body.image_type = "image/png"
    body.image_size += 1
    with pytest.raises(HTTPException):
        _decode_assistant_image(body)

    received = {}
    def fake_ai(db, user, feature, prompt, images=None, timeout=90):
        received.update(feature=feature, prompt=prompt, images=images)
        return "图片里是测试图。"
    monkeypatch.setattr(implementation, "_ai_call", fake_ai)
    app.dependency_overrides[implementation.current_user] = lambda: SimpleNamespace(
        id=42, school_id=7, role="teacher"
    )
    app.dependency_overrides[implementation.get_db] = lambda: None
    try:
        response = TestClient(app).post(QUERY_PATH, json={
            "question": "这张图是什么？", "image_name": "sample.png",
            "image_type": "image/png", "image_size": len(raw), "image_data": encoded,
        })
        assert response.status_code == 200
        assert response.json()["reply"] == "图片里是测试图。"
        assert received["feature"] == "product_assistant"
        assert received["images"] == ["data:image/png;base64," + encoded]
    finally:
        app.dependency_overrides.pop(implementation.current_user, None)
        app.dependency_overrides.pop(implementation.get_db, None)


def test_product_assistant_image_failure_does_not_claim_to_see_it(monkeypatch):
    import app_v924 as implementation

    def unavailable(*args, **kwargs):
        raise HTTPException(502, "model has no vision")
    monkeypatch.setattr(implementation, "_ai_call", unavailable)
    app.dependency_overrides[implementation.current_user] = lambda: SimpleNamespace(
        id=42, school_id=7, role="teacher"
    )
    app.dependency_overrides[implementation.get_db] = lambda: None
    raw = b"\x89PNG\r\n\x1a\n" + b"test image"
    try:
        response = TestClient(app).post(QUERY_PATH, json={
            "question": "看这张图", "image_name": "sample.png",
            "image_type": "image/png", "image_size": len(raw),
            "image_data": base64.b64encode(raw).decode("ascii"),
        })
        assert response.status_code == 200
        assert response.json()["ok"] is False
        assert response.json()["source"] == "image_unavailable"
        assert response.json()["reason"] == "vision_model_unsupported"
        assert "图片暂时无法识别" in response.json()["reply"]
    finally:
        app.dependency_overrides.pop(implementation.current_user, None)
        app.dependency_overrides.pop(implementation.get_db, None)


@pytest.mark.parametrize(("error", "reason"), [
    (HTTPException(503, "尚未配置 AI 模型"), "ai_not_configured"),
    (HTTPException(429, "hourly limit"), "hourly_limit"),
    (HTTPException(502, "insufficient_quota"), "provider_quota"),
    (HTTPException(502, "invalid_api_key"), "provider_auth"),
    (HTTPException(504, "timeout"), "provider_timeout"),
    (RuntimeError("unexpected"), "internal_error"),
])
def test_assistant_image_failure_reason_excludes_provider_detail(error, reason):
    assert _image_failure_reason(error) == reason
