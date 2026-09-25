from fastapi.testclient import TestClient

from app import app
from changying.web.v1_product_guide import GUIDE_PATH, V1_PRODUCT_GUIDE_MARKER


def rendered_guide() -> str:
    response = TestClient(app).get(GUIDE_PATH)
    assert response.status_code == 200
    return response.text


def tutorial_script(html: str) -> str:
    start = html.index('id="changying_v1_product_guide_v3-script"')
    end = html.index('</script>', start)
    return html[start:end]


def test_role_tutorial_is_routable_and_persistently_reachable():
    html = rendered_guide()

    assert V1_PRODUCT_GUIDE_MARKER in html
    assert 'id="tutorialButton"' in html
    assert '>新手教学</button>' in html
    assert 'cy-v1-product-guide-page' in html
    assert '新手教学中心' in html


def test_login_demo_entry_is_upgraded_to_virtual_account_tutorial():
    html = rendered_guide()

    script = tutorial_script(html)
    assert "loginDemo.textContent='体验虚拟演示账号'" in script
    assert 'showHub({firstVisit:true})' in script


def test_tutorial_has_separate_virtual_accounts_for_all_supported_identity_types():
    html = rendered_guide()

    for label in (
        '机构老师',
        '学校教师',
        '机构管理员',
        '学校管理员',
        '学生',
        '家长',
    ):
        assert label in html

    for account in (
        '演示账号 · 周老师',
        '演示账号 · 林老师',
        '演示账号 · 机构负责人',
        '演示账号 · 教务管理员',
        '演示账号 · 小禾',
        '演示账号 · 小禾家长',
    ):
        assert account in html


def test_teacher_tutorial_covers_full_learning_and_classroom_loop():
    html = rendered_guide()

    for label in (
        '进入当前教学',
        '打开学生连续档案',
        '生成综合测试',
        '审核并布置',
        '查看学生提交',
        '生成针对性练习',
        '生成课堂复盘讲义',
        '开展互动课堂',
        '查看积分与课堂评价',
        '查询往期教学',
        '处理升年级衔接',
        '认识全部功能中心',
    ):
        assert label in html


def test_student_parent_and_admin_tutorials_cover_role_quick_navigation():
    html = rendered_guide()

    for label in (
        '平台总览',
        '账号管理',
        '积分奖励规则',
        '全校审计',
        '系统设置',
        '进入课堂',
        '查看作业',
        '逐题作答',
        '提交与查看结果',
        '做针对性练习',
        '查看学情',
        '查看积分与表现',
        '查看孩子课程',
        '查看孩子作业',
        '查看孩子学情',
        '查看课堂表现',
        '我的与账号',
    ):
        assert label in html


def test_every_step_can_be_done_or_skipped_and_progress_is_resumable():
    html = rendered_guide()

    for label in (
        '完成本步并继续',
        '跳过本步',
        '上一步',
        '切换演示账号',
        '退出并保存',
        '查看并补做步骤',
        '体验其他身份',
    ):
        assert label in html

    script = tutorial_script(html)
    assert "s.status[stepId]='done'" in script
    assert "s.status[stepId]='skipped'" in script
    assert "localStorage.setItem(STATE_KEY" in script
    assert "localStorage.getItem(STATE_KEY)" in script
    assert 'firstIncomplete' in script


def test_demo_actions_are_game_like_and_do_not_write_business_data():
    html = rendered_guide()
    script = tutorial_script(html)

    assert '这一关你要做' in html
    assert '演示操作已完成 ✓' in html
    assert '虚拟演示 · ' in html
    assert '以下均为演示数据' in html
    assert '0 条真实业务写入' in html
    assert "method:'POST'" not in script
    assert "method:'PUT'" not in script
    assert "method:'DELETE'" not in script
    assert 'fetch(' not in script


def test_tutorial_progress_is_per_persona_and_can_be_reset():
    html = rendered_guide()
    script = tutorial_script(html)

    assert "const STATE_KEY='cyV1RoleTutorialStateV3'" in script
    assert 'personaState=id=>' in script
    assert "localStorage.removeItem(STATE_KEY)" in script
    assert '各身份进度' in html
