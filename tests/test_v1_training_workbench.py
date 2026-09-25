from fastapi import FastAPI
from fastapi.testclient import TestClient

from changying.web.v1_training_workbench import (
    TRAINING_WORKBENCH_MARKER,
    TRAINING_WORKBENCH_PATH,
    install_v1_training_workbench_route,
    training_workbench_html,
)


def test_training_workbench_registers_cache_safe_route():
    app = FastAPI()
    install_v1_training_workbench_route(app)
    response = TestClient(app).get(TRAINING_WORKBENCH_PATH)
    assert response.status_code == 200
    assert response.headers["x-changying-v1-training"] == TRAINING_WORKBENCH_MARKER
    assert "no-store" in response.headers["cache-control"]


def test_training_workbench_is_interactive_not_static_screenshot_tutorial():
    html = training_workbench_html()
    for text in (
        "角色实操沙盒",
        "创建学生账号",
        "组卷 / 自动出题",
        "布置作业",
        "亲自体验学生端",
        "自动模拟关联数据",
        "结果与学习证据",
        "AI 针对性练习",
        "课堂复盘",
        "互动课堂与随堂检测",
        "积分与课堂评价",
        "往期教学",
        "升年级与升学衔接",
        "全部功能关系图",
    ):
        assert text in html

    assert "/v1/training-sandbox/start" in html
    assert "/v1/training-sandbox/" in html
    assert "student_submit" in html
    assert "simulate_student_submission" in html
    assert "switch_to_student" in html
    assert "return_primary_role" in html
    assert "load_scenario" in html
    assert "/v1/product-assistant/query" in html
    assert "/v1/product-feedback" in html
    assert "角色关系不清楚" in html


def test_training_workbench_supports_progress_review_and_reset_controls():
    html = training_workbench_html()
    for text in (
        "训练地图",
        "上一步",
        "跳过",
        "角色关系",
        "重做本步",
        "下一步",
        "从已布置作业开始",
        "从已有学生提交开始",
        "从课堂复盘开始",
        "清空本次实操沙盒并从头重新练习",
    ):
        assert text in html


def test_training_workbench_never_posts_to_production_business_routes():
    html = training_workbench_html()
    forbidden = (
        "fetch('/teacher/",
        'fetch("/teacher/',
        "fetch('/student/",
        'fetch("/student/',
        "fetch('/admin/",
        'fetch("/admin/',
    )
    for item in forbidden:
        assert item not in html


def test_all_roles_have_actionable_training_pages():
    html = training_workbench_html()
    for text in (
        "我的作业",
        "逐题作答",
        "我的学情",
        "我的错题",
        "家长端重点是理解孩子发生了什么",
        "家长只查看状态",
        "平台总览",
        "账号管理",
        "班级与教学归属",
        "积分规则",
        "全校审计",
        "系统设置",
    ):
        assert text in html

    for action in (
        "student_submit_self",
        "complete_student_practice",
        "admin_create_account",
        "admin_create_class",
        "admin_set_point_rule",
        "admin_set_system",
    ):
        assert action in html


def test_workbench_explains_auxiliary_pages_instead_of_falling_back_to_wrong_role_screen():
    html = training_workbench_html()
    for text in (
        "教材、教案和课件",
        "浏览题库不等于给学生布置任务",
        "班级排行用于激励",
        "套餐和功能授权",
        "AI 服务和学生数据授权边界",
        "批量导入账号和基础关系",
        "学习首页只负责汇总今天要做什么",
        "家长端重点是理解孩子发生了什么",
    ):
        assert text in html

    assert "views[step.id]||(()=>auxiliaryPage(step,'教师'" in html
    assert "adminAuxDetail(step.id)" in html


def test_training_workbench_inline_script_parses_in_node(tmp_path):
    import subprocess

    html = training_workbench_html()
    assert "<script>" in html and "</script>" in html
    script_text = html.split("<script>", 1)[1].split("</script>", 1)[0]
    script = tmp_path / "training-workbench.js"
    script.write_text(script_text, encoding="utf-8")
    checked = subprocess.run(
        ["node", "--check", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr


def test_mobile_training_navigation_is_compact_and_recoverable():
    html = training_workbench_html()
    assert 'id="moreBtn"' in html
    assert "function openMobileMore()" in html
    assert "连接超时，请重试" in html
    assert "练习环境没有启动" in html
    assert 'id="retryTraining"' in html
    assert ".bottom #skipBtn,.bottom #relationBtn,.bottom #resetStepBtn{display:none}" in html
    assert "grid-template-columns:minmax(0,1fr) auto minmax(0,1.25fr)" in html
    assert "progressText.textContent='未连接'" in html


def test_training_navigation_is_disabled_before_session_loads():
    html = training_workbench_html()
    assert 'id="prevBtn" disabled' in html
    assert 'id="skipBtn" disabled' in html
    assert 'id="relationBtn" disabled' in html
    assert 'id="resetStepBtn" disabled' in html
    assert 'id="nextBtn" disabled' in html


def test_training_flow_gates_future_steps_and_keeps_review_available():
    html = training_workbench_html()
    assert "function stepSettled(id)" in html
    assert "function firstUnsettledIndex()" in html
    assert "i<=frontier||stepSettled(s.id)" in html
    assert "step:not(:disabled)" in html
    assert "next.disabled=!settled||index===session.flow.length-1" in html
    assert "先完成本步" in html
    assert "完成后“下一步”会自动解锁" in html


def test_mobile_training_hides_verbose_relationship_cards_until_requested():
    html = training_workbench_html()
    assert ".rail.open{display:block}.relation{display:none}.form-grid" in html
    assert "角色关系" in html
    assert "mobileRelation" in html


def test_training_answer_ui_matches_question_type_and_pages_one_question_at_a_time():
    html = training_workbench_html()
    assert "function questionPager(" in html
    assert "function questionControl(" in html
    assert "answerKind==='choice'" in html
    assert "answer-input" in html
    assert "填写答案（含单位）" in html
    assert 'id="questionPrev"' in html
    assert 'id="questionNext"' in html
    assert "bindQuestionPager('answerOption','answerInput')" in html
    assert "bindQuestionPager('studentSelfOption','studentSelfInput')" in html
