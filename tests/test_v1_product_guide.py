from fastapi.testclient import TestClient

from app import app
from changying.web.v1_product_guide import GUIDE_PATH, V1_PRODUCT_GUIDE_MARKER


def rendered_guide() -> str:
    response = TestClient(app).get(GUIDE_PATH)
    assert response.status_code == 200
    return response.text


def tutorial_script(html: str) -> str:
    start = html.index('id="changying_v1_product_guide_v7-script"')
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


def test_authenticated_identity_maps_to_its_live_training_role():
    html = rendered_guide()
    script = tutorial_script(html)

    for mapping in ("学校教师", "机构老师", "学校管理员", "机构管理员", "家长", "学生"):
        assert mapping in script

    for persona_id in (
        "school_teacher",
        "institution_teacher",
        "school_admin",
        "institution_admin",
        "parent",
        "student",
    ):
        assert persona_id in script

    assert "showCurrentIntro({firstVisit:true})" in script
    assert "location.href='/v1/training'" in script


def test_onboarding_uses_only_live_sandbox_not_legacy_fake_lesson_engine():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "进入同身份实操沙盒" in html
    assert "不是看说明图" in html
    assert "真实操作" in html
    assert "跨角色可选" in html
    assert "可反复重练" in html

    for legacy in (
        "teacherSteps",
        "adminSteps",
        "studentSteps",
        "parentSteps",
        "roleCards",
        "startPersona",
        "renderLesson",
        "showCompletion",
        "customizerHtml",
        "cyV1RoleTutorialStateV7",
        "练习操作已完成 ✓",
        "虚拟演示 · ",
        "以下均为演示数据",
    ):
        assert legacy not in script


def test_product_guide_never_writes_business_data_itself():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "method:'POST'" not in script
    assert "method:'PUT'" not in script
    assert "method:'DELETE'" not in script
    assert "fetch(" not in script
    assert "localStorage" not in script


def test_persistent_guide_delegates_start_and_reset_to_training_workbench():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "当前身份 · 实操沙盒" in html
    assert "进入 / 继续实操沙盒" in html
    assert "清空训练进度后进入" in html
    assert "正式数据 0 写入" in html
    assert "sessionStorage.removeItem('cyTrainingSandboxSessionV1')" in script
    assert "sessionStorage.setItem('cyTrainingStepIndexV1','0')" in script
    assert script.count("location.href='/v1/training'") >= 2


def test_guide_screen_observer_is_idempotent_on_v1_guide():
    html = rendered_guide()
    script = tutorial_script(html)

    assert 'data-guide-version="v7"' in script
    assert "existing?.dataset?.guideVersion==='v7'" in script
    assert """screen.querySelector('#cy-v1-product-guide-page[data-guide-version="v7"]')""" in script
    assert "if(location.pathname!=='/v1/guide')return" in script


def test_onboarding_reacts_to_post_login_identity_selection_and_shows_once_per_session():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "SESSION_SHOWN_KEY='cyV1RoleTutorialShownThisLoginV7'" in script
    assert "if(!ready)return" in script
    assert "shouldAutoOpenTutorial(ready,persona.id,feedbackReview,sessionShownFor())" in script
    assert "markSessionShown(persona.id)" in script
    assert "identityObserver.observe(identityButton" in script
    assert "identityObserver.observe(identityChip" in script


def test_generic_identity_labels_still_map_and_assistant_yields_to_onboarding():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "label.includes('教师')||label.includes('老师')" in script
    assert "label.includes('管理员')" in script
    assert "assistantPanel.hidden=true" in script


def test_product_guide_inline_script_parses_in_node(tmp_path):
    import subprocess

    html = rendered_guide()
    script = tutorial_script(html)
    script_text = script.split(">", 1)[1]
    js = tmp_path / "product-guide.js"
    js.write_text(script_text, encoding="utf-8")
    checked = subprocess.run(
        ["node", "--check", str(js)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr


def test_feedback_acceptance_bypasses_first_login_onboarding_overlay():
    from pathlib import Path
    source = Path("changying/web/v1_product_guide.py").read_text(encoding="utf-8")
    assert "params.get('cy_feedback_review')" in source
    assert "params.get('reviewed')" in source
    assert "params.get('from')==='feedback'" in source
    assert "tab==='feedback-records'" in source
    assert "tab==='feedback'" in source
    assert "params.get('focus')" in source
    assert "if(!ready)return" in source
    assert "if(feedbackReview){markSessionShown(persona.id);return}" in source


def test_internal_navigation_does_not_reset_first_login_tutorial_session():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "if(!ready)return" in script
    assert "hasAuthToken" not in script
    assert "localStorage" not in script
    assert "if(!ready){if(!feedbackReview)clearSessionShown();return}" not in script


def test_real_logout_can_still_reset_tutorial_session():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "const clearSessionShown=()=>sessionStorage.removeItem(SESSION_SHOWN_KEY)" in script
    assert "if(!ready)return" in script
