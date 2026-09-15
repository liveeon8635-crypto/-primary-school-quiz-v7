from changying.web.v1 import v1_html
from changying.web.v1_mastery_evidence import (
    V1_MASTERY_EVIDENCE_MARKER,
    patch_v1_mastery_evidence,
)


def test_high_average_score_does_not_auto_mark_stable_mastery():
    html = patch_v1_mastery_evidence(v1_html())

    assert V1_MASTERY_EVIDENCE_MARKER in html
    assert "a.avgScore>=90?3" not in html
    assert "sampleCount>=2&&hasScore&&scoreRaw>=75&&overdue===0?2:1" in html
    assert "i===stage?'on':''" in html
    assert "学习证据状态" in html
    assert "基本掌握（当前证据）" in html
    assert "稳定掌握”不会仅凭一次成绩或平均分自动点亮" in html
    assert "跨时间保留、独立完成，以及迁移或新情境中的证据" in html


def test_no_evidence_is_not_mislabeled_as_cannot_do():
    html = patch_v1_mastery_evidence(v1_html())

    assert "const stage=!hasEvidence?-1:" in html
    assert "stage===1?'学习中':'证据不足'" in html
    assert "当前生产数据尚未把这些维度标准化落表" in html


def test_mastery_evidence_patch_is_idempotent():
    once = patch_v1_mastery_evidence(v1_html())
    twice = patch_v1_mastery_evidence(once)

    assert twice == once
    assert twice.count(V1_MASTERY_EVIDENCE_MARKER) == 1
