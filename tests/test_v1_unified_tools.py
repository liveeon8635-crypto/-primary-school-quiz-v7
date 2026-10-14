import subprocess
import sys
import textwrap

from changying.web.v1 import v1_html
from changying.web.v1_unified_tools import (
    V1_UNIFIED_TOOLS_MARKER,
    patch_v1_unified_tools,
    unified_tool_html,
)


def run_isolated(code: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        text=True,
        capture_output=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_unified_patch_replaces_direct_classic_navigation():
    html = patch_v1_unified_tools(v1_html())
    assert V1_UNIFIED_TOOLS_MARKER in html
    assert "function roleQuickNav()" in html
    assert "['tools','⌘','全部功能','/v1/tool']" not in html
    assert "['assignments','✓','作业','/v1/tool?page=assignments']" in html
    assert "['tools','☰','更多','/v1/tool?page=__hub__']" in html
    assert "/v1/workspace?focus=capabilities" not in html
    assert "cy-capabilities" not in html
    assert "完整功能中心" not in html


def test_old_iframe_shell_is_kept_only_as_a_compatibility_helper():
    html = unified_tool_html()
    assert "统一功能工作区" in html
    assert "/classic?legacy=1&embedded=1&from=v1&page=" in html
    assert "班级学生" in html
    assert "孩子作业" in html
    assert "平台总览" in html


def test_runtime_installs_same_tab_unified_tool_route_and_final_patch():
    run_isolated(
        """
        from fastapi.testclient import TestClient
        from app import app
        from changying.web.v1_unified_tools import V1_UNIFIED_TOOLS_MARKER
        client = TestClient(app)
        v1 = client.get('/v1')
        assert v1.status_code == 200
        assert V1_UNIFIED_TOOLS_MARKER in v1.text
        assert 'function roleQuickNav()' in v1.text
        assert "['tools','⌘','全部功能','/v1/tool']" not in v1.text
        assert "['assignments','✓','作业','/v1/tool?page=assignments']" in v1.text
        tool = client.get('/v1/tool?page=classes', follow_redirects=False)
        assert tool.status_code == 307
        assert tool.headers['location'] == '/classic?legacy=1&unified=1&from=v1&page=classes'
        assert tool.headers['X-Changying-V1-Tool'] == 'changying_v1_classic_top_level_v1'
        unified = client.get(tool.headers['location'])
        assert unified.status_code == 200
        assert 'changying_v1_classic_unified_top_v1' in unified.text
        assert 'cy-v1-unified-picker' in unified.text
        """
    )


def test_workspace_no_longer_duplicates_all_functions_center():
    from fastapi.testclient import TestClient
    from app import app

    html = TestClient(app).get('/v1/workspace').text
    assert 'cy-capabilities' not in html
    assert '完整功能中心' not in html
    assert '/v1/tool' in html


def test_teacher_workspace_has_capsule_nav_all_view_and_deduplicated_cards():
    from fastapi.testclient import TestClient
    from app import app
    from changying.web.v1_tool_hub import TOOL_HUB_MENUS

    html = TestClient(app).get('/v1/workspace').text
    assert 'id="cy-seg"' in html
    assert '<aside class="side">' not in html
    assert 'class="bottom"' not in html
    assert "cy-ws-all" in html
    # Former sidebar entries now live inside the two capsule segments.
    assert "['students','◉','学生'" not in html
    for href, label in (("/v1/student", "学生"), ("/v1/history", "往期教学"), ("/v1/transition", "升学衔接")):
        assert f'["{href}", "{label}"' in html
    for _, label, _ in TOOL_HUB_MENUS["teacher"]:
        assert label in html
    assert "['晚托','周末课','今日/本周教学','课堂复盘','作业与错题','学习进度']" in html
    assert "'当前学生','今日/本周教学'" not in html
    assert "'待办事项']" not in html


def test_internal_feedback_status_panels_are_not_injected_into_pages():
    from fastapi.testclient import TestClient
    from app import app

    for path in ('/v1', '/v1/workspace', '/v1/student'):
        html = TestClient(app).get(path).text
        assert 'feedback-status-chain' not in html
        assert 'feedback-reward-panel' not in html
        assert 'exact-head CI 通过' not in html


def test_v1_header_is_horizontal_ribbon_banner_with_expanded_brand():
    from fastapi.testclient import TestClient
    from app import app

    html = TestClient(app).get('/v1/workspace').text
    assert '.top .brand>span:last-child{display:flex;align-items:baseline' in html
    assert 'class="cy-ribbon"' in html and 'id="cyDragonPath"' not in html
    # No title-sequence overlay any more: just the silk with a small shadow Nezha riding it.
    assert 'id="cy-cine"' not in html and 'cinematic' not in html.lower()
    assert '<animateMotion dur="18s"' in html and '<image href="data:image/webp;base64,' in html
    # Fixed header, 15% taller than before (88px -> 101px).
    assert 'position:fixed;left:0;right:0;top:0;z-index:50' in html and '.top{height:101px' in html
    assert '<a class="brand" href="/v1"><span>长缨辅学<small>学生连续发展档案 · V1</small></span></a>' in html
    assert '<span class="mark">长</span>' not in html


def test_v1_brand_uses_embedded_calligraphy_font_and_keeps_identity_chip():
    from fastapi.testclient import TestClient
    from app import app

    html = TestClient(app).get('/v1/workspace').text
    assert "font-family:CyBrand" in html and "data:font/woff2;base64," in html
    assert ".top .identity-chip{display:none}" not in html
    assert "cy-notice-hidden" not in html
    # The rail fills the viewport height and splits it between the two segments.
    assert "height:calc(100dvh - 125px)" in html
    assert "grid-template-rows:repeat(var(--n),1fr)" in html


def test_teaching_term_is_a_year_plus_dropdown_and_heading_notes_are_removed():
    from fastapi.testclient import TestClient
    from app import app

    html = TestClient(app).get('/v1/workspace').text
    assert 'id="termSelect"' in html
    assert "termOptions=['上学期','暑假','下学期','寒假']" in html
    assert 'data-cycle="winter"' not in html and 'class="mode-switch"' not in html
    assert '首页只展示当前教学周期，结束后统一进入往期教学。' not in html
    assert '晚托、周末课与寒暑假班按周期切换显示' not in html
    assert '每位学生始终指向同一份长期档案' not in html
    # Holiday terms read real teaching-cycle facts instead of reusing term data.
    assert "api('/v1/teaching-cycles')" in html
    # Year label keeps the heading size; the term picker is a themed custom dropdown.
    assert '.cy-term-year{font-size:clamp(25px,4vw,38px)' in html
    assert 'id="termBtn"' in html and 'class="cy-dd-menu"' in html and 'data-term="${t}"' in html
    assert '<select id="termSelect"' not in html
    # The duplicated 当前学生 KPI card is gone; the count sits on the list heading.
    assert '<section class="section grid cols-3"><div class="card kpi"><span>当前班级</span>' in html


def test_identity_notice_only_exists_for_demo_accounts():
    from fastapi.testclient import TestClient
    from app import app

    html = TestClient(app).get('/v1/workspace').text
    assert "const notice=session.demo?`<div class=\"notice warn\">" in html
    assert "现有数据按账号原有权限读取" not in html


def test_classic_unified_chrome_and_tool_hub_share_the_ribbon_theme():
    from fastapi.testclient import TestClient
    from app import app

    client = TestClient(app)
    classic = client.get('/classic?legacy=1&unified=1&page=papers').text
    assert 'cy-ribbon' in classic and 'id="cy-cine"' not in classic and '<animateMotion' in classic
    assert '--primary:#a8101c' in classic and 'font-family:CyBrand' in classic
    assert 'class="cy-v1-mark"' not in classic
    assert "['tools','⌘','全部功能','/v1/workspace?view=all']" in classic

    hub = client.get('/v1/tool').text
    assert 'cy-ribbon' in hub and '--navy:#a8101c' in hub and 'id="cy-cine"' not in hub


def test_assistant_button_is_the_nezha_avatar():
    from fastapi.testclient import TestClient
    from app import app

    html = TestClient(app).get('/v1/workspace').text
    button = html.split('id="cy-product-assistant-fab"', 1)[1].split('</button>', 1)[0]
    assert 'class="cy-pa-fab-img" src="data:image/png;base64,' in button
    assert '✦' not in button
    assert '/v1/assets/cinematic-nezha.webp' not in html


def test_classic_checkboxes_keep_their_natural_size():
    from fastapi.testclient import TestClient
    from app import app

    # The legacy stylesheet sets input{width:100%}; without this override the 教材题库
    # row picker stretched across the whole row and squeezed each question into one character column.
    for url in ('/classic?legacy=1&unified=1&page=catalog',):
        html = TestClient(app).get(url).text
        assert 'input[type="checkbox"],input[type="radio"]{width:auto!important;min-width:0;padding:0!important;flex:none}' in html


def test_assistant_can_be_hidden_and_restored():
    from fastapi.testclient import TestClient
    from app import app

    html = TestClient(app).get('/v1/workspace').text
    assert 'id="cy-pa-hide"' in html and 'id="cy-pa-restore"' in html
    assert 'html.cy-pa-off #cy-product-assistant-fab' in html
    assert "localStorage.setItem(PA_OFF_KEY,'1')" in html and "localStorage.removeItem(PA_OFF_KEY)" in html
    # Feedback-review deep links must still be able to open the assistant while it is hidden.
    assert 'setPaOff(false);panel.hidden=false;fab.hidden=true;initialAssistantRoutePending=false;' in html


def test_training_sandbox_and_guide_share_the_red_gold_theme():
    from fastapi.testclient import TestClient
    from app import app

    client = TestClient(app)
    training = client.get('/v1/training').text
    assert 'cy-ribbon' in training and 'font-family:CyBrand' in training
    assert '<div class="brand">长缨辅学</div>' in training and '<div class="brand">长</div>' not in training
    assert '--navy:#a8101c' in training and '#173c78' not in training

    guide = client.get('/v1/workspace').text.split('cy-onboarding-overlay{', 1)[1].split('}', 1)[0]
    assert 'rgba(60,8,14' in guide
