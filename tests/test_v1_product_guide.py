from fastapi.testclient import TestClient

from app import app
from changying.web.v1_product_guide import (
    CLASSIC_GUIDE_RESUME_MARKER,
    GUIDE_PATH,
    V1_PRODUCT_GUIDE_MARKER,
)


def rendered_guide() -> str:
    response = TestClient(app).get(GUIDE_PATH)
    assert response.status_code == 200
    return response.text


def tutorial_script(html: str) -> str:
    start = html.index('id="changying_v1_product_guide_v5-script"')
    end = html.index("</script>", start)
    return html[start:end]


def test_role_tutorial_is_hidden_until_login_and_identity_selection():
    html = rendered_guide()
    script = tutorial_script(html)

    assert V1_PRODUCT_GUIDE_MARKER in html
    assert 'id="tutorialButton" hidden' in html
    assert '>新手教学</button>' in html
    assert "const identityReady=()=>Boolean(identityButton&&identityButton.hidden===false&&currentPersonaId())" in script
    assert "tutorialButton.hidden=!ready" in script


def test_generic_teacher_identity_from_real_ui_is_recognized():
    script = tutorial_script(rendered_guide())

    assert "label.includes('教师')||label.includes('老师')" in script
    assert "label.includes('管理员')" in script
    assert "institution_teacher" in script
    assert "institution_admin" in script


def test_onboarding_is_bound_to_each_real_login_token_not_only_role():
    script = tutorial_script(rendered_guide())

    assert "SESSION_SHOWN_KEY='cyV1RoleTutorialShownThisLoginV7'" in script
    assert "const authToken=()" in script
    assert "const loginMarker=()=>currentPersonaId()+':'+authToken().slice(-24)" in script
    assert "if(sessionShownFor()!==loginMarker())" in script
    assert "markSessionShown()" in script


def test_teacher_tutorial_starts_with_product_value_then_real_setup_workflow():
    html = rendered_guide()

    for label in (
        "先认识长缨解决什么问题",
        "建立第一个班级",
        "添加学生账号并加入班级",
        "按需绑定家长",
        "准备教材与教学资料",
        "准备题目：题库或 AI 出题",
        "组卷并布置作业",
        "理解学生实际会经历什么",
        "查看提交、错题和学情反馈",
        "生成并审核 AI 针对性练习",
        "把练习反馈带回课堂",
        "理解积分与教师评价",
        "学会回看往期教学",
        "处理升年级与升学衔接",
        "学会边用边反馈",
    ):
        assert label in html

    for route in (
        "/v1/tool?page=classes",
        "/v1/tool?page=resources",
        "/v1/tool?page=ai",
        "/v1/tool?page=papers",
        "/v1/tool?page=classPoints",
        "/v1/student",
        "/v1/history",
        "/v1/transition",
    ):
        assert route in html


def test_student_parent_and_admin_tutorials_are_role_specific_and_actionable():
    html = rendered_guide()

    for label in (
        "建立教师/家长等账号",
        "建立班级与教学归属",
        "按需配置 AI 能力",
        "学会用审计追溯操作",
        "先认识学生端是做什么的",
        "逐题作答并检查输入方式",
        "使用错题本",
        "查看长期学情",
        "先认识家长端能做什么",
        "查看孩子课程",
        "查看孩子作业",
        "查看孩子学情",
        "检查自己的账号与关联",
    ):
        assert label in html


def test_live_coaching_can_jump_to_real_feature_and_resume_later():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "边用边学" in html
    assert "去真实页面边用边学 →" in script
    assert "location.href=liveRoute" in script
    assert "ACTIVE_PERSONA_KEY='cyV1RoleTutorialActivePersonaV5'" in script
    assert "tutorial=1" in script
    assert "new URLSearchParams(location.search).get('resume')==='1'" in script
    assert "queueMicrotask(()=>startPersona(persona.id))" in script


def test_every_step_can_be_done_skipped_and_revisited():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "s.status[stepId]='done'" in script
    assert "s.status[stepId]='skipped'" in script
    assert "暂时跳过" in html
    assert "我已理解/完成，继续" in html
    assert "上一步" in html
    assert "退出并保存" in html
    assert "firstIncomplete" in script
    assert "localStorage.setItem(STATE_KEY" in script
    assert "重新开始本身份教学" in html


def test_tutorial_feedback_opens_product_assistant_with_current_step():
    script = tutorial_script(rendered_guide())

    assert "cy:open-product-feedback" in script
    assert "detail:{step:step[1]}" in script
    assert "这一步不清楚 / 提建议" in script


def test_tutorial_never_writes_business_data_itself():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "教学本身不自动写业务数据" in html
    assert "是否保存真实数据由你自己决定" in html
    assert "method:'POST'" not in script
    assert "method:'PUT'" not in script
    assert "method:'DELETE'" not in script
    assert "fetch(" not in script


def test_guide_screen_observer_is_idempotent_on_v1_guide():
    script = tutorial_script(rendered_guide())

    assert 'data-guide-version="v7"' in script
    assert "existing?.dataset?.guideVersion==='v7'" in script
    assert "screen.querySelector('#cy-v1-product-guide-page[data-guide-version=\"v7\"]')" in script
    assert "if(location.pathname!=='/v1/guide')return" in script


def test_all_functions_runtime_has_resume_entry_for_learning_by_doing():
    client = TestClient(app)
    response = client.get("/classic?legacy=1&unified=1&from=v1&page=classes")

    assert response.status_code == 200
    assert CLASSIC_GUIDE_RESUME_MARKER in response.text
    assert 'id="cy-live-guide-resume"' in response.text
    assert '/v1/guide?resume=1' in response.text
