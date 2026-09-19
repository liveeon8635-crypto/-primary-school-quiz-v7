import re
import subprocess
from pathlib import Path

from changying.web.v1 import v1_html
from changying.web.v22_evidence_coverage_view import (
    V22_EVIDENCE_COVERAGE_MARKER,
    patch_v22_evidence_coverage_view,
)


def test_coverage_view_is_teacher_facing_read_only_and_non_diagnostic():
    html = patch_v22_evidence_coverage_view(v1_html())
    assert V22_EVIDENCE_COVERAGE_MARKER in html
    assert "班级学习证据覆盖" in html
    assert "不做能力排名或自动诊断" in html
    assert "尚无记录" in html
    assert "不等于能力不足" in html
    assert "/v2/teacher/evidence-coverage" in html
    assert "location.pathname!='/v1/student'" in html

    marker = f'<script id="{V22_EVIDENCE_COVERAGE_MARKER}-script">'
    start = html.index(marker)
    fragment = html[start:html.index("</script>", start)]
    for verb in ("method:'POST'", "method:'PUT'", "method:'PATCH'", "method:'DELETE'"):
        assert verb not in fragment


def test_coverage_view_script_is_valid_javascript():
    html = patch_v22_evidence_coverage_view(v1_html())
    match = re.search(
        rf'<script id="{V22_EVIDENCE_COVERAGE_MARKER}-script">(?P<script>.*?)</script>',
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


def test_coverage_view_patch_is_idempotent():
    once = patch_v22_evidence_coverage_view(v1_html())
    twice = patch_v22_evidence_coverage_view(once)
    assert once == twice


def test_backend_uses_bounded_batch_queries_not_per_student_queries():
    source = (
        Path(__file__).resolve().parents[1]
        / "changying"
        / "web"
        / "v22_evidence_coverage.py"
    ).read_text(encoding="utf-8")
    assert source.count("db.scalars(") == 5
    loop = source.split("for sid, student in student_by_id.items():", 1)[1]
    assert "db.scalars(" not in loop
    assert "db.scalar(" not in loop


def test_production_v1_contains_class_evidence_coverage():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert V22_EVIDENCE_COVERAGE_MARKER in html
    assert "班级学习证据覆盖" in html
