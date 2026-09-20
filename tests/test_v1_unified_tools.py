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
    assert "['tools','⌘','全部功能','/v1/tool']" in html
    assert "['assignments','✓','我的作业','/v1/tool?page=assignments']" in html
    assert "/v1/workspace?focus=capabilities" not in html
    assert "全部功能" in html
    assert "a[data-cy-capability]" in html
    assert "'/v1/tool?page='+encodeURIComponent(page)" in html
    assert "在统一界面打开 →" in html


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
        assert "['tools','⌘','全部功能','/v1/tool']" in v1.text
        assert "['assignments','✓','我的作业','/v1/tool?page=assignments']" in v1.text
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
