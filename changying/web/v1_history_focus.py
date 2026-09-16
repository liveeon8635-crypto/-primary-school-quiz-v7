"""Make the V1 history page useful on mobile without eager profile fan-out.

The history tab is an archive doorway, not a second read-only product. Render
its shell immediately, load the already-aggregated visible roster in the
background, and open one student's continuous profile only when selected.
Historical facts remain protected while avoiding an expensive all-student
profile request on every visit.
"""

from __future__ import annotations

import re

from changying.web import v1 as v1_module

V1_HISTORY_FOCUS_MARKER = "changying_v1_history_focus_v1"

_HISTORY_PAGE = re.compile(
    r"    async function historyPage\(\)\{.*?\n    function transitionPage\(\)",
    re.DOTALL,
)
_ENHANCE_HISTORY = re.compile(
    r"  async function enhanceHistory\(\)\{.*?\n  function transitionName",
    re.DOTALL,
)


def patch_v1_history_focus(html: str) -> str:
    """Replace the conceptual/history-heavy view with a fast archive doorway."""
    if V1_HISTORY_FOCUS_MARKER in html:
        return html

    history_page = r'''    async function historyPage(){
      const content=heading('往期教学','这里用于查看已经结束的班级、学期或课程记录；学生始终还是同一份连续档案，不需要另外建立“历史档案”。','')+`<section class="card"><div class="section-head"><div><h2>按学生找往期记录</h2><p>选择学生后再读取该学生过去的班级变化、作业、成绩、课堂表现和跟进记录。</p></div></div><div class="field" style="margin-top:12px"><input id="historySearch" placeholder="搜索学生姓名或班级" autocomplete="off"></div><div class="list" id="historyStudents" style="margin-top:12px"><div class="empty">正在读取学生列表…</div></div></section><section class="section card"><div class="section-head"><div><h2>为什么保留往期记录</h2><p>换班、升年级或进入新学期后，过去发生过的教学事实继续留在原学生档案中，方便回看发展过程。</p></div></div><div class="grid cols-2"><div class="notice"><b>班级 / 教学归属</b><br>保留进入、调班、离开等历史。</div><div class="notice"><b>教学记录</b><br>作业、成绩、课堂表现和跟进继续挂在同一学生 ID 下。</div></div></section>`;
      screen.innerHTML=shell(content,'history')+`<style>#historyStudents .row-main{flex:1 1 auto;min-width:0;overflow:hidden}#historyStudents .row-action{flex:0 0 auto}#historySearch{width:100%;max-width:100%}#historyStudents .row{max-width:100%;overflow:hidden}#historyStudents .row-main small{display:block;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}</style>`;bindNav();
      const list=document.getElementById('historyStudents'),search=document.getElementById('historySearch');let people=[];
      const draw=()=>{const q=(search?.value||'').trim().toLowerCase();const rows=people.filter(p=>!q||String(p.name||'').toLowerCase().includes(q)||String(p.className||p.currentClassName||p.teachingAffiliations?.join(' ')||'').toLowerCase().includes(q));list.innerHTML=rows.map(p=>`<a class="row" data-student href="/v1/student?id=${p.id}"><span class="row-main"><b>${esc(p.name||'学生')}</b><small>${esc((p.teachingAffiliations||[]).join(' / ')||p.className||p.currentClassName||studentPosition(p)||'学生连续档案')}</small></span><span class="row-action">查看历史 →</span></a>`).join('')||'<div class="empty">没有匹配的学生档案</div>';list.querySelectorAll('[data-student]').forEach(a=>a.onclick=e=>{e.preventDefault();navigate(a.getAttribute('href'))})};
      if(search)search.oninput=draw;
      try{people=await loadPeople();draw()}catch(err){list.innerHTML=`<div class="notice error">学生列表读取失败：${esc(err.message||'请稍后重试')}</div>`}
    }
    function transitionPage()'''
    html, count = _HISTORY_PAGE.subn(lambda _match: history_page, html, count=1)
    if count != 1:
        raise RuntimeError("V1 history focus: historyPage marker not found")

    lightweight_enhance = r'''  async function enhanceHistory(){return}
  function transitionName'''
    html, count = _ENHANCE_HISTORY.subn(lightweight_enhance, html, count=1)
    if count != 1:
        raise RuntimeError("V1 history focus: enhanceHistory marker not found")

    return html.replace(
        "</body>",
        f"<!-- {V1_HISTORY_FOCUS_MARKER} --></body>",
        1,
    )


def install_v1_history_focus_patch() -> None:
    if getattr(v1_module, "_history_focus_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_history_focus(original())

    v1_module.v1_html = patched_v1_html
    v1_module._history_focus_patch_installed = True


__all__ = [
    "V1_HISTORY_FOCUS_MARKER",
    "install_v1_history_focus_patch",
    "patch_v1_history_focus",
]
