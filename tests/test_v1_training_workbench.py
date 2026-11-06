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


def test_training_actions_show_busy_and_error_feedback():
    html = training_workbench_html()
    assert "actionPending=false" in html
    assert "function setStageBusy(flag)" in html
    assert "function showActionError(error)" in html
    assert "这一步没有完成：" in html
    assert 'id="actionError"' in html
    assert "window.addEventListener('unhandledrejection'" in html
    assert '.stage[aria-busy="true"]' in html


def test_step_navigation_returns_mobile_view_to_top():
    html = training_workbench_html()
    assert "requestAnimationFrame(()=>window.scrollTo({top:0,behavior:'smooth'}))" in html


def test_teacher_tutorial_explains_paper_import_and_where_imported_questions_go():
    app = FastAPI()
    install_v1_training_workbench_route(app)
    response = TestClient(app).get(TRAINING_WORKBENCH_PATH)
    assert response.status_code == 200
    html = response.text

    for text in (
        "「导入试卷」把已有试卷或真题导入",
        "保存后试卷在「组卷与作业」，题目进入「教材题库」",
        "导入或拍照上传的题目也在这里",
        "单元就是导入时填写的单元",
        "题库里已有完全相同的题（带插图的题除外）会直接沿用、不重复保存，仍在它原来的单元下",
        "勾选题目后可批量修改单元或教材（老师只能改自己导入或创建的题目，管理员可改本校所有题目）",
    ):
        assert text in html

    # the entry names the tutorial points at must exist in the real classic page
    from changying.web import paper_import_routes, paper_import_ui

    source = open(paper_import_ui.__file__, encoding="utf-8").read()
    assert 'id="importPaper">导入试卷</button>' in source
    assert "已保存到「组卷与作业」" in source
    # 教材题库 batch edit that the tutorial mentions: ticked questions + 修改单元 button + endpoint
    assert 'data-qpick="${q.id}"' in source
    assert 'id="editUnitQ"' in source
    assert 'window.catalogEditUnit=function' in source
    assert '"/teacher/questions/unit"' in source
    # duplicate questions are reused (not re-filed under the new unit), as the tutorial now says
    routes = open(paper_import_routes.__file__, encoding="utf-8").read()
    assert "reusedCount" in routes and "is reused instead of saved a second time" in routes
    # questions with a figure are always saved as new rows, so the tutorial excludes them from 沿用
    assert 'if key in known and not item.get("figure")' in routes
    # unit edit permission: teachers only their own questions, admin any question of the school
    assert 'editable = [row for row in rows if u.role == "admin" or row.creator_id == u.id]' in routes

    from changying.web.v1_training_sandbox import STEP_RELATIONSHIPS

    assert "新导入的题目按导入时填写的单元归类" in STEP_RELATIONSHIPS["teacher_catalog"]["communication_tip"]



def test_training_explains_the_follow_up_pilot_quota_rules():
    """待跟进（试点）的口径要写进沙盒导览，并且和真实路由里的名额常量一致。"""
    from changying.web.homework_help import FOLLOW_UP_DAILY_LIMIT
    from changying.web.v1_training_sandbox import ROLE_FLOW, STEP_RELATIONSHIPS

    assert FOLLOW_UP_DAILY_LIMIT == 5, "名额改了，导览里的“每个班每天最多 5 条”也要一起改"

    teacher = [step["id"] for step in ROLE_FLOW["teacher"]]
    assert teacher.index("teacher_homework") < teacher.index("teacher_follow_ups") < teacher.index("hub")
    step = next(s for s in ROLE_FLOW["teacher"] if s["id"] == "teacher_follow_ups")
    assert step["page"] == "/v1/homework"

    rel = STEP_RELATIONSHIPS["teacher_follow_ups"]
    assert all(rel[k] for k in ("who", "creates", "visible_to", "other_role_sees", "communication_tip", "next"))
    tip = rel["communication_tip"]
    for text in ("每个班每天最多 5 条", "同一学生当天最多 1 条", "都不返还名额", "同时占两个班的名额",
                 "不改变求助本身的状态", "学生主动求助", "AI 解答验算未通过", "已讲解，尚无独立巩固结果",
                 "尚无独立验证", "练习尚未通过", "无法判定是否已验证"):
        assert text in tip, text
    assert "看不到" in rel["other_role_sees"]

    # 走真实的 /v1/training 路由，确认教师讲解随页面下发
    app = FastAPI()
    install_v1_training_workbench_route(app)
    html = TestClient(app).get(TRAINING_WORKBENCH_PATH).text
    assert "teacher_follow_ups:'在“晚托作业助手”顶部的“待跟进”标签" in html
    assert "同时占两个班的名额" in html
    assert "“待跟进”标签每个班每天最多推 5 条、同一学生当天 1 条" in html
