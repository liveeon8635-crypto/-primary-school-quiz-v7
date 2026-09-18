import re
import subprocess

from changying.web.v1 import v1_html
from changying.web.v1_transition_facts_view import (
    V1_TRANSITION_FACTS_MARKER,
    patch_v1_transition_facts_view,
)


def test_transition_view_is_factual_and_read_only():
    html = patch_v1_transition_facts_view(v1_html())
    assert V1_TRANSITION_FACTS_MARKER in html
    assert "/transition-snapshot" in html
    assert "真实衔接事实" in html
    assert "不自动诊断或分流" in html
    assert "尚无记录" in html
    assert "学生能力缺口" not in html

    marker = f'<script id="{V1_TRANSITION_FACTS_MARKER}-script">'
    fragment = html[html.index(marker):html.index("</script>", html.index(marker))]
    for verb in ("method:'POST'", "method:'PUT'", "method:'PATCH'", "method:'DELETE'"):
        assert verb not in fragment


def test_transition_view_script_is_valid_javascript():
    html = patch_v1_transition_facts_view(v1_html())
    match = re.search(
        rf'<script id="{V1_TRANSITION_FACTS_MARKER}-script">(?P<script>.*?)</script>',
        html,
        re.S,
    )
    assert match
    result = subprocess.run(
        ["node", "--check", "-"],
        input=match.group("script"),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_transition_view_patch_is_idempotent():
    once = patch_v1_transition_facts_view(v1_html())
    twice = patch_v1_transition_facts_view(once)
    assert once == twice


def test_production_v1_contains_transition_facts_view():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert V1_TRANSITION_FACTS_MARKER in html
    assert "/v1/students/" in html
    assert "/transition-snapshot" in html
