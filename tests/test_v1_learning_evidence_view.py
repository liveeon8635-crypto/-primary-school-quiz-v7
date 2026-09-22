import re
import subprocess

from changying.web.v1_learning_evidence_view import (
    V1_LEARNING_EVIDENCE_VIEW_MARKER,
    patch_v1_learning_evidence_view,
)


def test_patch_is_optional_and_fact_only():
    fixture = """<html><body><script>
    async function studentPage(){const profile={};const content=`before<section class="section"><div class="section-head"><div><h2>历史时间线</h2>after`;}</script></body></html>"""
    html = patch_v1_learning_evidence_view(fixture)
    assert V1_LEARNING_EVIDENCE_VIEW_MARKER in html
    assert "function learningEvidenceSection(profile)" in html
    assert "if(!e)return '';" in html
    assert "标准化学习证据" in html
    assert "只展示已记录事实" in html
    assert "masteryInferred 固定为 false" in html
    assert "教师端保留来源标识以便追溯" in html
    assert "可追溯" in html
    assert "sourceId" in html
    assert "slice(0,12)" in html
    assert "${learningEvidenceSection(profile)}<section" in html
    assert "自动生成掌握、薄弱或教学结论" in html


def test_patch_does_not_replace_existing_growth_sections():
    fixture = """<html><body><script>
    async function studentPage(){const profile={};const content=`作业情况 薄弱内容 / 错题 需要关注 / 下一步教学<section class="section"><div class="section-head"><div><h2>历史时间线</h2>`;}</script></body></html>"""
    html = patch_v1_learning_evidence_view(fixture)
    assert "作业情况" in html
    assert "薄弱内容 / 错题" in html
    assert "需要关注 / 下一步教学" in html
    assert "历史时间线" in html


def test_production_v1_html_contains_valid_optional_evidence_view():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert V1_LEARNING_EVIDENCE_VIEW_MARKER in html
    assert html.count('id="learningEvidence"') == 1
    assert "profile&&profile.learningEvidence" in html
    assert "${learningEvidenceSection(profile)}" in html

    match = re.search(
        r'<script id="changying_v1_20260915-script">(?P<script>.*?)</script>',
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


def test_patch_is_idempotent():
    fixture = """<html><body><script>
    async function studentPage(){const profile={};const content=`<section class="section"><div class="section-head"><div><h2>历史时间线</h2>`;}</script></body></html>"""
    once = patch_v1_learning_evidence_view(fixture)
    twice = patch_v1_learning_evidence_view(once)
    assert once == twice
    assert twice.count(V1_LEARNING_EVIDENCE_VIEW_MARKER) == 1