import re
import subprocess

from changying.web.v1 import v1_html
from changying.web.v22_evidence_coverage_view import patch_v22_evidence_coverage_view
from changying.web.v2_learning_evidence_recording_view import (
    patch_v2_learning_evidence_recorder,
)


def test_coverage_links_missing_manual_dimensions_to_focused_recorder():
    html = patch_v22_evidence_coverage_view(v1_html())
    assert "focus=evidence&evidenceType=" in html
    assert "['independent','retention','transfer']" in html
    assert "记录'+esc(dimName[d]||d)" in html
    assert "学习表现：等待作业/测验自动形成" in html
    assert "待补充记录：" in html


def test_performance_is_never_offered_as_manual_record_action():
    html = patch_v22_evidence_coverage_view(v1_html())
    assert "missingDims.filter(d=>['independent','retention','transfer'].includes(d))" in html
    assert "evidenceType=performance" not in html


def test_recorder_reads_requested_dimension_and_focus_query():
    html = patch_v2_learning_evidence_recorder(v1_html())
    assert "params.get('evidenceType')" in html
    assert "params.get('focus')==='evidence'" in html
    assert "typeSelect.value=requestedType" in html
    assert "scrollIntoView({behavior:'smooth',block:'start'})" in html


def test_final_combined_scripts_are_valid_javascript():
    html = patch_v22_evidence_coverage_view(
        patch_v2_learning_evidence_recorder(v1_html())
    )
    for script_id in (
        "changying_v22_evidence_coverage_v1-script",
        "changying_v2_evidence_recorder_v1-script",
    ):
        match = re.search(
            rf'<script id="{script_id}">(?P<script>.*?)</script>',
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
