"""Conservative V1 mastery display based only on currently available evidence.

The production growth profile does not yet store retention, independent
reconstruction, or transfer/novel-context evidence as standardized fields.
Therefore V1 must not infer "稳定掌握" from a high average score alone.

This patch is presentation-only: it changes the student card's display rule and
adds an explicit evidence boundary. It does not write student data or create a
second diagnosis model.
"""

from __future__ import annotations

import re

from changying.web import v1 as v1_module


V1_MASTERY_EVIDENCE_MARKER = "changying_v1_mastery_evidence_v1"

_STAGE_RULE = re.compile(
    r"const s=profile\.student\|\|\{\},a=profile\.academic\|\|\{\},weak=a\.weakKnowledge\|\|\[\],assignments=a\.recentAssignments\|\|\[\],timeline=profile\.timeline\|\|\[\],suggestions=profile\.suggestions\|\|\[\];const stage=\(a\.avgScore>=90\?3:a\.avgScore>=75\?2:a\.submissionCount>0\?1:0\);"
)

_OLD_MASTERY = """<div class=\"section-head\"><div><h2>掌握状态</h2><p>由事实记录逐步表达变化</p></div></div><div class=\"mastery\">${['不会','学习中','基本掌握','稳定掌握'].map((x,i)=>`<span class=\"${i<=stage?'on':''}\">${x}</span>`).join('')}</div><div class=\"notice warn\" style=\"margin-top:14px\">当前为 V1 展示规则，尚未作为智能诊断结论。</div>"""

_NEW_MASTERY = """<div class=\"section-head\"><div><h2>学习证据状态</h2><p>只依据当前已记录事实给出保守提示</p></div></div><div class=\"mastery\">${['不会','学习中','基本掌握','稳定掌握'].map((x,i)=>`<span class=\"${i===stage?'on':''}\">${x}</span>`).join('')}</div><div class=\"notice\" style=\"margin-top:14px\"><b>当前提示：${esc(masteryState)}</b><br>证据摘要：记录样本 ${esc(sampleCount)} · 阶段成绩 ${hasScore?esc(scoreRaw):'—'} · 薄弱项 ${esc(weak.length)} · 逾期 ${esc(overdue)}。</div><div class=\"notice warn\" style=\"margin-top:10px\">“稳定掌握”不会仅凭一次成绩或平均分自动点亮。它还需要跨时间保留、独立完成，以及迁移或新情境中的证据。当前生产数据尚未把这些维度标准化落表，因此这里不自动判定稳定掌握。</div>"""


def patch_v1_mastery_evidence(html: str) -> str:
    """Replace the score-only ladder with a conservative evidence display."""

    if V1_MASTERY_EVIDENCE_MARKER in html:
        return html

    stage_rule = (
        "const s=profile.student||{},a=profile.academic||{},weak=a.weakKnowledge||[],"
        "assignments=a.recentAssignments||[],timeline=profile.timeline||[],"
        "suggestions=profile.suggestions||[];"
        "const sampleCount=Number(a.submissionCount||0),scoreRaw=Number(a.avgScore),"
        "hasScore=a.avgScore!==null&&a.avgScore!==undefined&&a.avgScore!==''&&Number.isFinite(scoreRaw),"
        "hasEvidence=sampleCount>0||hasScore||assignments.length>0||weak.length>0,"
        "overdue=Number(a.overdueAssignments||0);"
        "const stage=!hasEvidence?-1:(sampleCount>=2&&hasScore&&scoreRaw>=75&&overdue===0?2:1);"
        "const masteryState=stage===2?'基本掌握（当前证据）':stage===1?'学习中':'证据不足';"
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
