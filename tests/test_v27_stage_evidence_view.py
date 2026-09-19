import re
import subprocess

from changying.web.v1 import v1_html
from changying.web.v27_stage_evidence_view import (
    V27_STAGE_EVIDENCE_VIEW_MARKER,
    patch_v27_stage_evidence_view,
)


def test_stage_evidence_view_is_descriptive_only():
    html = patch_v27_stage_evidence_view(v1_html())

    assert V27_STAGE_EVIDENCE_VIEW_MARKER in html
    assert "阶段证据对比" in html
    assert "本阶段新增记录维度" in html
    assert "上一阶段有、本阶段尚无同类记录" in html
    assert "不自动判断进步、退步或掌握" in html
    assert "/stage-evidence-comparison" in html

    marker = f'<script id="{V27_STAGE_EVIDENCE_VIEW_MARKER}-script">'
    fragment = html[html.index(marker):html.index("</script>", html.index(marker))]
    for verb in ("method:'POST'", "method:'PUT'", "method:'PATCH'", "method:'DELETE'"):
        assert verb not in fragment


def test_stage_evidence_view_script_is_valid_javascript():
    html = patch_v27_stage_evidence_view(v1_html())
    match = re.search(
        rf'<script id="{V27_STAGE_EVIDENCE_VIEW_MARKER}-script">(?P<script>.*?)</script>',
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


def test_stage_evidence_view_patch_is_idempotent():
    once = patch_v27_stage_evidence_view(v1_html())
    twice = patch_v27_stage_evidence_view(once)
    assert once == twice


def test_production_v1_contains_stage_evidence_view():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert V27_STAGE_EVIDENCE_VIEW_MARKER in html
    assert "/v2/students/" in html
    assert "/stage-evidence-comparison" in html
