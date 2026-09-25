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


def test_login_page_is_not_replaced_by_pre_auth_tutorial():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "体验虚拟演示账号" not in script
    assert "loginDemo" not in script
    assert "showHub(" not in script


def test_tutorial_maps_authenticated_identity_to_its_own_role_flow():
    html = rendered_guide()
    script = tutorial_script(html)

    for mapping in (
        "学校教师",
        "机构老师",
        "学校管理员",
        "机构管理员",
        "家长",
        "学生",
    ):
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
    assert "startPersona(persona.id)" in script


def test_tutorial_is_sequential_not_a_free_step_picker():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "步骤路线仅用于查看进度，系统会按顺序引导" in html
    assert 'data-step-index' not in script
    assert "cy-step-item" in script
    assert "完成本步并继续" in html
    assert "跳过本步" in html
    assert "上一步" in html
    assert "退出并保存" in html


def test_teacher_tutorial_covers_full_learning_and_classroom_loop():
    html = rendered_guide()

    for label in (
        "先认识长缨解决什么问题",
        "建立第一个班级",
        "添加学生账号",
        "打开学生连续档案",
        "组一份真实感作业",
        "审核题目并确认积分",
        "布置给班级或个人",
        "切到学生视角完成一次作答",
        "查看结果如何回流",
        "生成下一轮针对性练习",
        "把全班数据变成课堂复盘",
        "用互动课堂把问题讲透",
        "理解积分和课堂评价",
        "把结束的教学放进历史",
        "处理升年级和升学衔接",
        "认识全部功能并进入真实使用",
    ):
        assert label in html


def test_student_parent_and_admin_tutorials_cover_role_specific_workflows():
    html = rendered_guide()

    for label in (
        "平台总览",
        "账号管理",
        "积分奖励规则",
        "全校审计",
        "系统设置",
        "进入课堂",
        "查看作业",
        "逐题作答",
        "提交与查看结果",
        "做针对性练习",
        "查看学情",
        "查看积分与表现",
        "查看孩子课程",
        "查看孩子作业",
        "查看孩子学情",
        "查看课堂表现",
        "我的与账号",
    ):
        assert label in html


def test_every_step_can_be_done_or_skipped_and_progress_resumes_per_identity():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "s.status[stepId]='done'" in script
    assert "s.status[stepId]='skipped'" in script
    assert "localStorage.setItem(STATE_KEY" in script
    assert "localStorage.getItem(STATE_KEY)" in script
    assert "firstIncomplete" in script
    assert "seenKey=id=>'cyV1RoleTutorialSeenV7:'+id" in script
    assert "重新开始本身份教学" in html


def test_demo_actions_remain_virtual_and_do_not_write_business_data():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "这一关你要做" in html
    assert "练习操作已完成 ✓" in html
    assert "虚拟演示 · " in html
    assert "以下均为演示数据" in html
    assert "0 条真实业务写入" in html
    assert "method:'POST'" not in script
    assert "method:'PUT'" not in script
    assert "method:'DELETE'" not in script
    assert "fetch(" not in script


def test_guide_screen_observer_is_idempotent_on_v1_guide():
    html = rendered_guide()
    script = tutorial_script(html)

    assert 'data-guide-version="v7"' in script
    assert "existing?.dataset?.guideVersion==='v7'" in script
    assert "screen.querySelector('#cy-v1-product-guide-page[data-guide-version=\"v7\"]')" in script
    assert "if(location.pathname!=='/v1/guide')return" in script


def test_onboarding_reacts_to_post_login_identity_selection_and_shows_once_per_login_session():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "SESSION_SHOWN_KEY='cyV1RoleTutorialShownThisLoginV7'" in script
    assert "if(!ready){clearSessionShown();return}" in script
    assert "if(sessionShownFor()!==persona.id)" in script
    assert "markSessionShown(persona.id)" in script
    assert "identityObserver.observe(identityButton" in script
    assert "identityObserver.observe(identityChip" in script


def test_teacher_tutorial_is_practice_led_and_customizable_without_business_writes():
    html = rendered_guide()
    script = tutorial_script(html)

    assert 'data-demo-field="className"' in script
    assert 'data-demo-field="studentName"' in script
    assert 'data-demo-field="studentAccount"' in script
    assert 'data-demo-field="questionCount"' in script
    assert 'data-demo-field="knowledge"' in script
    assert "demoState=id=>" in script
    assert "updatePersona(persona.id" in script
    assert "method:'POST'" not in script
    assert "fetch(" not in script


def test_generic_teacher_identity_label_still_maps_to_teacher_onboarding():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "label.includes('教师')||label.includes('老师')" in script
    assert "label.includes('管理员')" in script
    assert "assistantPanel.hidden=true" in script
