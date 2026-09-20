from changying.web.v1 import v1_html
from changying.web.v1_classic_unified_top import V1_CLASSIC_UNIFIED_SNIPPET
from changying.web.v1_unified_tools import unified_tool_html


def test_v1_native_shortcuts_are_scoped_by_account_role():
    html = v1_html()
    assert "function roleQuickNav()" in html
    assert "session?.role||'teacher'" in html

    for label, page in (
        ("同步课堂", "syncLearning"),
        ("我的作业", "assignments"),
        ("自主练习", "practice"),
        ("我的学情", "progress"),
        ("积分奖励", "rewards"),
    ):
        assert f"'{label}','/v1/tool?page={page}'" in html

    for label, page in (
        ("孩子课程", "childLearning"),
        ("孩子作业", "childAssignments"),
        ("孩子学情", "childProgress"),
        ("课堂表现", "childRewards"),
    ):
        assert f"'{label}','/v1/tool?page={page}'" in html

    for label, page in (
        ("平台总览", "admin"),
        ("账号管理", "users"),
        ("积分奖励", "pointsAdmin"),
        ("全校审计", "adminAudit"),
        ("系统设置", "system"),
    ):
        assert f"'{label}','/v1/tool?page={page}'" in html


def test_classic_top_level_shortcuts_follow_hydrated_role():
    html = V1_CLASSIC_UNIFIED_SNIPPET
    assert "var quickMenus=" in html
    assert "var quick=quickMenus[role]||quickMenus.teacher" in html
    assert "student:[['syncLearning','▦','同步课堂','syncLearning']" in html
    assert "['assignments','✓','我的作业','assignments']" in html
    assert "['practice','✎','自主练习','practice']" in html
    assert "['progress','◉','我的学情','progress']" in html
    assert "['rewards','★','积分奖励','rewards']" in html
    assert "parent:[['childLearning','▦','孩子课程','childLearning']" in html
    assert "admin:[['admin','▦','平台总览','admin']" in html
    assert "bottom.innerHTML=quick.map" in html


def test_unified_tool_shortcuts_use_same_role_contract():
    html = unified_tool_html()
    assert "const quickMenus=" in html
    assert "const quick=quickMenus[role]||quickMenus.teacher" in html
    assert "id=\"roleBottom\"" in html
    assert "renderRoleBottom(page)" in html
    assert "student:[['syncLearning','▦','同步课堂','syncLearning']" in html
    assert "parent:[['childLearning','▦','孩子课程','childLearning']" in html
    assert "admin:[['admin','▦','平台总览','admin']" in html


def test_teacher_shortcuts_keep_existing_teaching_navigation():
    html = v1_html()
    for label, path in (
        ("当前教学", "/v1/workspace"),
        ("学生", "/v1/student"),
        ("往期教学", "/v1/history"),
        ("升学衔接", "/v1/transition"),
        ("全部功能", "/v1/tool"),
    ):
        assert f"'{label}','{path}'" in html
