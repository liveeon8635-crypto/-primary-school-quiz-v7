"""Presentation-only V1.1 learning-evidence section for the student profile.

The API field is optional. When absent, the existing student detail remains
unchanged. When present, this patch renders observed evidence facts only and
does not derive mastery, weakness, diagnosis, or teaching recommendations.
"""

from __future__ import annotations

import re

from changying.web import v1 as v1_module


V1_LEARNING_EVIDENCE_VIEW_MARKER = "changying_v1_learning_evidence_view_v1"

_STUDENT_PAGE_ANCHOR = "    async function studentPage(){"
_HISTORY_ANCHOR = '<section class="section"><div class="section-head"><div><h2>历史时间线</h2>'

_HELPER = r"""
    function learningEvidenceSection(profile){
      const e=profile&&profile.learningEvidence;
      if(!e)return '';
      const names={performance:'学习表现',independent:'独立完成',retention:'跨时保持',transfer:'迁移应用'};
      const dims=(e.dimensions||[]).map(x=>names[x]||x).join(' · ')||'暂无标准化维度';
      const subjects=(e.subjects||[]).slice(0,4).map(x=>'<div class="row"><span class="row-main"><b>'+esc(x.subject||'未标注学科')+'</b><small>样本 '+esc(x.sampleCount||0)+' · 最近 '+esc((x.latestAt||'').slice(0,10))+'</small></span><span class="tag">观测均分 '+esc(x.averageObservedScore??'—')+'</span></div>').join('');
      const knowledge=(e.knowledge||[]).slice(0,6).map(x=>'<div class="row"><span class="row-main"><b>'+esc(x.knowledgeKey||'未标注知识点')+'</b><small>'+esc(x.subject||'')+' · 样本 '+esc(x.sampleCount||0)+' · '+esc((x.evidenceTypes||[]).map(y=>names[y]||y).join(' / '))+'</small></span><span class="tag">观测正确率 '+esc(x.observedSuccessRate??'—')+'%</span></div>').join('');
      const recent=(e.recentEvidence||[]).slice(0,6).map(x=>'<div class="event"><time>'+esc((x.occurredAt||'').slice(0,10))+'</time><b>'+esc((x.subject||'未标注学科')+(x.knowledgeKey?' · '+x.knowledgeKey:''))+'</b><p>'+esc(names[x.evidenceType]||x.evidenceType||'学习证据')+' · '+(x.score===null||x.score===undefined?'未记录分数':esc(x.score)+'分')+' · 来源 '+esc(x.sourceType||'记录')+'</p></div>').join('');
      return '<section class="section" id="learningEvidence"><div class="section-head"><div><h2>标准化学习证据</h2><p>只展示已记录事实，不自动生成掌握、薄弱或教学结论</p></div><span class="tag">样本 '+esc(e.sampleCount||0)+'</span></div><div class="card"><div class="notice">证据维度：'+esc(dims)+'。当前区块仅用于连续档案中的事实回看；masteryInferred 固定为 false。</div><div class="grid cols-2" style="margin-top:14px"><div><h3>学科观测</h3><div class="list" style="margin-top:10px">'+(subjects||'<div class="empty">暂无学科证据</div>')+'</div></div><div><h3>知识点观测</h3><div class="list" style="margin-top:10px">'+(knowledge||'<div class="empty">暂无知识点证据</div>')+'</div></div></div><div style="margin-top:16px"><h3>最近证据</h3><div class="timeline" style="margin-top:10px">'+(recent||'<div class="empty">暂无标准化证据时间线</div>')+'</div></div></div></section>';
    }
"""


def patch_v1_learning_evidence_view(html: str) -> str:
    """Insert an optional descriptive evidence section into student detail."""
    if V1_LEARNING_EVIDENCE_VIEW_MARKER in html:
        return html
    if _STUDENT_PAGE_ANCHOR not in html:
        raise RuntimeError("V1 evidence view patch: studentPage anchor not found")
    if _HISTORY_ANCHOR not in html:
        raise RuntimeError("V1 evidence view patch: history anchor not found")

    html = html.replace(_STUDENT_PAGE_ANCHOR, _HELPER + "\n" + _STUDENT_PAGE_ANCHOR, 1)
    html = html.replace(_HISTORY_ANCHOR, "${learningEvidenceSection(profile)}" + _HISTORY_ANCHOR, 1)
    return html.replace(
        "</body>",
        f"<!-- {V1_LEARNING_EVIDENCE_VIEW_MARKER} --></body>",
        1,
    )


def install_v1_learning_evidence_view_patch() -> None:
    """Install the optional evidence section after all earlier V1 patches."""
    if getattr(v1_module, "_learning_evidence_view_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_learning_evidence_view(original())

    v1_module.v1_html = patched_v1_html
    v1_module._learning_evidence_view_patch_installed = True


__all__ = [
    "V1_LEARNING_EVIDENCE_VIEW_MARKER",
    "install_v1_learning_evidence_view_patch",
    "patch_v1_learning_evidence_view",
]