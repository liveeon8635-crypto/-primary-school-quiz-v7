import re
import subprocess

from changying.web.v1 import v1_html
from changying.web.v2_teaching_evidence_context import build_teaching_evidence_context
from changying.web.v2_teaching_evidence_context_view import (
    V21_TEACHING_EVIDENCE_CONTEXT_MARKER,
    patch_v21_teaching_evidence_context_view,
)


def test_context_builder_is_descriptive_not_prescriptive():
    snapshot = {
        "state": "basic_evidence_available",
        "sampleCount": 3,
        "dimensions": ["performance", "independent"],
        "subjects": [{"subject": "数学", "sampleCount": 3}],
        "knowledge": [
            {
                "subject": "数学",
                "knowledgeKey": "分数加法",
                "sampleCount": 2,
                "averageObservedScore": 85.0,
                "observedSuccessRate": 100.0,
                "latestAt": "2026-09-19T01:00:00+00:00",
                "evidenceTypes": ["performance", "independent"],
            }
        ],
        "recentEvidence": [],
    }
    context = build_teaching_evidence_context(snapshot)

    assert context["availableDimensions"] == ["independent", "performance"]
    assert context["missingDimensions"] == ["retention", "transfer"]
    assert context["decisionRequiredByTeacher"] is True
    assert context["automaticDiagnosis"] is False
    assert context["automaticRecommendation"] is False
    assert context["automaticPlacementDecision"] is False
    assert "不等于学生存在能力缺口" in context["boundary"]


def test_planning_context_view_is_teacher_only_and_read_only():
    html = patch_v21_teaching_evidence_context_view(v1_html())
    assert V21_TEACHING_EVIDENCE_CONTEXT_MARKER in html
    assert "教师备课事实参考" in html
    assert "不生成自动教学结论" in html
    assert "/v2/students/" in html
    assert "/teaching-evidence-context" in html
    assert "/v1/tool?page=teaching" in html

    marker = f'<script id="{V21_TEACHING_EVIDENCE_CONTEXT_MARKER}-script">'
    start = html.index(marker)
    fragment = html[start:html.index("</script>", start)]
    for verb in ("method:'POST'", "method:'PUT'", "method:'PATCH'", "method:'DELETE'"):
        assert verb not in fragment


def test_planning_context_view_script_is_valid_javascript():
    html = patch_v21_teaching_evidence_context_view(v1_html())
    match = re.search(
        rf'<script id="{V21_TEACHING_EVIDENCE_CONTEXT_MARKER}-script">(?P<script>.*?)</script>',
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


def test_production_v1_contains_planning_facts_view():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert V21_TEACHING_EVIDENCE_CONTEXT_MARKER in html
    assert "教师备课事实参考" in html
