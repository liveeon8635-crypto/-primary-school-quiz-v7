from fastapi.testclient import TestClient

from app import app
from changying.web.v1_product_guide import GUIDE_PATH, V1_PRODUCT_GUIDE_MARKER


def rendered_guide() -> str:
    response = TestClient(app).get(GUIDE_PATH)
    assert response.status_code == 200
    return response.text


def tutorial_script(html: str) -> str:
    start = html.index('id="changying_v1_product_guide_v4-script"')
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
        "进入当前教学",
        "打开学生连续档案",
        "生成综合测试",
        "审核并布置",
        "查看学生提交",
        "生成针对性练习",
        "生成课堂复盘讲义",
        "开展互动课堂",
        "查看积分与课堂评价",
        "查询往期教学",
        "处理升年级衔接",
        "认识全部功能中心",
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
    assert "seenKey=id=>'cyV1RoleTutorialSeenV4:'+id" in script
    assert "重新开始本身份教学" in html


def test_demo_actions_remain_virtual_and_do_not_write_business_data():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "这一关你要做" in html
    assert "演示操作已完成 ✓" in html
    assert "虚拟演示 · " in html
    assert "以下均为演示数据" in html
    assert "0 条真实业务写入" in html
    assert "method:'POST'" not in script
    assert "method:'PUT'" not in script
    assert "method:'DELETE'" not in script
    assert "fetch(" not in script
