from changying.web.v1 import v1_html
from changying.web.v1_mastery_evidence import (
    V1_MASTERY_EVIDENCE_MARKER,
    patch_v1_mastery_evidence,
)


def test_score_thresholds_never_drive_evidence_status():
    html = patch_v1_mastery_evidence(v1_html())

    assert V1_MASTERY_EVIDENCE_MARKER in html
    assert "a.avgScore>=90?3" not in html
    assert "scoreRaw>=75" not in html
    assert "sampleCount>=2" not in html
    assert "基本掌握（当前证据）" not in html
    assert "const evidence=profile.learningEvidence||null" in html
    assert "evidenceState==='stable_evidence_available'?3" in html


def test_status_labels_describe_evidence_not_mastery():
    html = patch_v1_mastery_evidence(v1_html())

    assert "学习证据状态" in html
    assert "证据不足" in html
    assert "单项证据" in html
    assert "基础证据" in html
    assert "稳定证据集" in html
    assert "展示标准化证据覆盖程度，不等同于掌握结论" in html
    assert "不是“学生已经掌握到什么程度”" in html
    assert "平均分、作业数量、逾期情况和薄弱项均不会自动提升证据状态" in html


def test_missing_standardized_evidence_remains_evidence_insufficient():
    html = patch_v1_mastery_evidence(v1_html())

    assert "evidence?.state||'evidence_insufficient'" in html
    assert "evidenceSampleCount=Number(evidence?.sampleCount||0)" in html
    assert "暂无标准化维度" in html


def test_mastery_evidence_patch_is_idempotent():
    once = patch_v1_mastery_evidence(v1_html())
    twice = patch_v1_mastery_evidence(once)

    assert twice == once
    assert twice.count(V1_MASTERY_EVIDENCE_MARKER) == 1
