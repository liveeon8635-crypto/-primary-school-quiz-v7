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
    assert "/v1/workspace?focus=capabilities" in html
    assert "全部功能" in html
    assert "a[data-cy-capability]" in html
    assert "'/v1/tool?page='+encodeURIComponent(page)" in html
    assert "在统一界面打开 →" in html


def test_tool_shell_keeps_v1_chrome_around_mature_workflows():
    html = unified_tool_html()

    assert "统一功能工作区" in html
    assert "全部功能" in html
    assert "/classic?legacy=1&embedded=1&from=v1&page=" in html
    assert ".sidebar,.mobile-header,.bottom-nav{display:none!important}" in html
    assert "continueSessionBtn" in html
    assert "班级学生" in html
    assert "孩子作业" in html
    assert "平台总览" in html
    assert "当前教学" in html
    assert "升学衔接" in html


def test_runtime_installs_unified_tool_route_and_final_patch():
    run_isolated(
        """
        from fastapi.testclient import TestClient
        from app import app
        from changying.web.v1_unified_tools import V1_UNIFIED_TOOLS_MARKER

        client = TestClient(app)
        v1 = client.get('/v1')
        assert v1.status_code == 200
        assert V1_UNIFIED_TOOLS_MARKER in v1.text
        assert '/v1/workspace?focus=capabilities' in v1.text

        tool = client.get('/v1/tool?page=classes')
        assert tool.status_code == 200
        assert tool.headers['X-Changying-V1'] == V1_UNIFIED_TOOLS_MARKER
        assert '统一功能工作区' in tool.text
        assert '/classic?legacy=1&embedded=1&from=v1&page=' in tool.text
        """
    )
