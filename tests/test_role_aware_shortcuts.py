from changying.web.v1 import v1_html
from changying.web.v1_classic_unified_top import V1_CLASSIC_UNIFIED_SNIPPET
from changying.web.v1_unified_tools import unified_tool_html


def test_v1_native_shortcuts_are_scoped_by_account_role():
    html = v1_html()
    assert "function roleQuickNav()" in html
    assert "session?.role||'teacher'" in html

    for label, page in (
        ("课堂", "syncLearning"),
        ("作业", "assignments"),
        ("练习", "practice"),
        ("学情", "progress"),
        ("更多", "__hub__"),
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
    assert "student:[['syncLearning','▦','课堂','syncLearning']" in html
    assert "['assignments','✓','作业','assignments']" in html
    assert "['practice','✎','练习','practice']" in html
    assert "['progress','◉','学情','progress']" in html
    assert "['tools','☰','更多','#']" in html
    assert "parent:[['childLearning','▦','孩子课程','childLearning']" in html
    assert "admin:[['admin','▦','平台总览','admin']" in html
    assert "bottom.innerHTML=quick.map" in html
    assert "data-classic-page" in html
    assert "u.searchParams.delete('from')" in html
    assert "/classic?legacy=1&unified=1&from=v1&page=" not in html


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
        ("全部功能", "/v1/workspace?view=all"),
    ):
        assert f"'{label}','{path}'" in html
    # The sidebar is gone: navigation is one capsule rendered by shell().
    assert '<aside class="side">' not in html
    assert 'class="cy-seg"' in html


def test_all_recognized_roles_have_explicit_quick_navigation_on_both_surfaces():
    native = v1_html()
    classic = V1_CLASSIC_UNIFIED_SNIPPET
    unified = unified_tool_html()

    # Every production account role must have an explicit menu before the
    # teacher fallback is considered. This protects student/parent/admin
    # navigation after a cross-context session handoff.
    for surface in (classic, unified):
        for role in ("student", "parent", "admin"):
            assert f"{role}:[" in surface
        assert "quickMenus[role]||quickMenus.teacher" in surface

    # Native V1 must also branch explicitly for the same non-teacher roles.
    for role in ("student", "parent", "admin"):
        assert f"if(role==='{role}')return[" in native

    # Lock representative role-only destinations so a recognized identity
    # cannot silently inherit teacher shortcuts.
    role_targets = {
        "student": ("syncLearning", "assignments", "practice", "progress"),
        "parent": ("childLearning", "childAssignments", "childProgress", "childRewards"),
        "admin": ("admin", "users", "pointsAdmin", "adminAudit"),
    }
    for targets in role_targets.values():
        for target in targets:
            assert target in classic
            assert target in unified
