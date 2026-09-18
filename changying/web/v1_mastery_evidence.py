"""Conservative V1 evidence-status display.

V1.1 now exposes a standardized learningEvidence section. This patch makes
that evidence state the only source for the status card. Average score,
submission count, overdue work and weakKnowledge remain visible elsewhere but
never promote a student into a mastery label.
"""

from __future__ import annotations

import re

from changying.web import v1 as v1_module


V1_MASTERY_EVIDENCE_MARKER = "changying_v1_mastery_evidence_v1"

_STAGE_RULE = re.compile(
    r"const s=profile\.student\|\|\{\},a=profile\.academic\|\|\{\},weak=a\.weakKnowledge\|\|\[\],assignments=a\.recentAssignments\|\|\[\],timeline=profile\.timeline\|\|\[\],suggestions=profile\.suggestions\|\|\[\];const stage=\(a\.avgScore>=90\?3:a\.avgScore>=75\?2:a\.submissionCount>0\?1:0\);"
)

_OLD_MASTERY = """<div class=\"section-head\"><div><h2>掌握状态</h2><p>由事实记录逐步表达变化</p></div></div><div class=\"mastery\">${['不会','学习中','基本掌握','稳定掌握'].map((x,i)=>`<span class=\"${i<=stage?'on':''}\">${x}</span>`).join('')}</div><div class=\"notice warn\" style=\"margin-top:14px\">当前为 V1 展示规则，尚未作为智能诊断结论。</div>"""

_NEW_MASTERY = """<div class=\"section-head\"><div><h2>学习证据状态</h2><p>展示标准化证据覆盖程度，不等同于掌握结论</p></div></div><div class=\"mastery\">${['证据不足','单项证据','基础证据','稳定证据集'].map((x,i)=>`<span class=\"${i===evidenceStage?'on':''}\">${x}</span>`).join('')}</div><div class=\"notice\" style=\"margin-top:14px\"><b>当前状态：${esc(evidenceStateLabel)}</b><br>标准化样本 ${esc(evidenceSampleCount)} · 已记录维度 ${esc(evidenceDimensionText)}。</div><div class=\"notice warn\" style=\"margin-top:10px\">这里描述的是“系统已经记录了哪些证据”，不是“学生已经掌握到什么程度”。平均分、作业数量、逾期情况和薄弱项均不会自动提升证据状态，也不会生成掌握结论。</div>"""


def patch_v1_mastery_evidence(html: str) -> str:
    """Replace the score-only ladder with a conservative evidence display."""

    if V1_MASTERY_EVIDENCE_MARKER in html:
        return html

    stage_rule = (
        "const s=profile.student||{},a=profile.academic||{},weak=a.weakKnowledge||[],"
        "assignments=a.recentAssignments||[],timeline=profile.timeline||[],"
        "suggestions=profile.suggestions||[];"
        "const evidence=profile.learningEvidence||null,"
        "evidenceState=evidence?.state||'evidence_insufficient',"
        "evidenceSampleCount=Number(evidence?.sampleCount||0),"
        "evidenceDimensions=Array.isArray(evidence?.dimensions)?evidence.dimensions:[],"
        "evidenceStage=evidenceState==='stable_evidence_available'?3:"
        "evidenceState==='basic_evidence_available'?2:"
        "evidenceState==='learning_evidence_available'?1:0,"
        "evidenceStateLabel=evidenceState==='stable_evidence_available'?'稳定证据集可用':"
        "evidenceState==='basic_evidence_available'?'基础证据可用':"
        "evidenceState==='learning_evidence_available'?'已有学习证据':'证据不足',"
        "evidenceDimensionText=evidenceDimensions.length?evidenceDimensions.join(' / '):'暂无标准化维度';"
    )
    html, count = _STAGE_RULE.subn(stage_rule, html, count=1)
    if count != 1:
        raise RuntimeError("V1 mastery evidence patch: stage rule marker not found")

    if _OLD_MASTERY not in html:
        raise RuntimeError("V1 mastery evidence patch: mastery card marker not found")
    html = html.replace(_OLD_MASTERY, _NEW_MASTERY, 1)

    return html.replace("</body>", f"<!-- {V1_MASTERY_EVIDENCE_MARKER} --></body>", 1)


def install_v1_mastery_evidence_patch() -> None:
    """Install the display-only patch once before V1 routes are registered."""

    if getattr(v1_module, "_mastery_evidence_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_mastery_evidence(original())

    v1_module.v1_html = patched_v1_html
    v1_module._mastery_evidence_patch_installed = True


__all__ = [
    "V1_MASTERY_EVIDENCE_MARKER",
    "install_v1_mastery_evidence_patch",
    "patch_v1_mastery_evidence",
]
