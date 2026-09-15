"""Remove silent V1 read truncation while keeping requests bounded.

The V1 operational layer originally capped several native panels to the first
8/10/12 records.  That was useful while the shell was being proven, but it can
hide real students or teaching affiliations once the product is used beyond a
small demo cohort.  This patch keeps the same protected read APIs, fetches the
complete visible set in small concurrent batches, and leaves preview cards
intentionally compact.

This module is presentation/read-path only: it creates no tables, writes no
student data, and changes no authorization behavior.
"""

from __future__ import annotations

import re

from changying.web import v1 as v1_module


V1_FULL_VISIBILITY_MARKER = "changying_v1_full_visibility_v1"

_OPERATIONAL_READERS = re.compile(
    r"  async function classesAndStudents\(filter=''\)\{.*?\n  function studentLink",
    re.DOTALL,
)

_HISTORY_BLOCK = re.compile(
    r"  async function enhanceHistory\(\)\{.*?\n  function transitionName",
    re.DOTALL,
)

_REPLACEMENT_READERS = r'''  async function mapBatches(items,size,fn){
    const out=[];for(let i=0;i<items.length;i+=size){out.push(...await Promise.all(items.slice(i,i+size).map(fn)))}return out;
  }
  async function classesAndStudents(filter=''){
    const classes=await readJson('/teacher/classes');const needle=filter.trim();const selected=needle?classes.filter(c=>String(c.name||'').includes(needle)):classes;const use=selected.length?selected:classes;
    return await mapBatches(use,8,async c=>{let students=[];try{students=await readJson('/teacher/classes/'+c.id+'/students')}catch{}return {class:c,students}});
  }
  async function visibleStudents(){
    const rows=await classesAndStudents('');const map=new Map();for(const item of rows){for(const s of item.students||[]){if(s?.active===false)continue;const key=String(s.id);if(!map.has(key))map.set(key,{...s,teachingAffiliations:[],classIDs:[]});const p=map.get(key);const name=item.class?.name||'';if(name&&!p.teachingAffiliations.includes(name))p.teachingAffiliations.push(name);const classID=item.class?.id;if(classID&&!p.classIDs.includes(classID))p.classIDs.push(classID)}}return [...map.values()];
  }
  async function studentProfiles(){
    const students=await visibleStudents();return await mapBatches(students,6,async s=>{try{return {student:s,profile:await readJson('/teacher/students/'+s.id+'/growth-profile')}}catch{return {student:s,profile:null}}});
  }
  function studentLink'''

_REPLACEMENT_HISTORY = r'''  async function enhanceHistory(){
    if(location.pathname!='/v1/history'||document.getElementById('cy-op-history'))return;
    try{
      const students=await visibleStudents();if(!students.length)return;
      const records=(await mapBatches(students,6,async student=>{try{const p=await readJson('/teacher/students/'+student.id+'/growth-profile'),h=p.classHistory||[],t=p.timeline||[],s=p.student||{};return{id:student.id,name:s.name||student.name||'学生',history:h,last:h[0]||null,timeline:t}}catch{return null}})).filter(Boolean);
      if(!records.length)return;
      const content=`<section class="section card" id="cy-op-history"><div class="section-head"><div><h2>真实历史摘要</h2><p>从全部当前可见学生的班级历史与时间线分批读取，不再静默只取前几名学生。</p></div></div><div class="cy-feature-note">已读取 ${esc(records.length)} 名当前可见学生的连续档案摘要；历史事实仍只来自现有受保护数据。</div><div class="cy-op-list">${records.map(r=>`<a class="cy-op-row" href="/v1/student?id=${r.id}"><span><b>${esc(r.name)}</b><small>${r.history.length} 条班级历史 · ${r.timeline.length} 条时间线</small></span><small>${esc(r.last?.className||r.last?.name||'打开连续档案')}</small></a>`).join('')}</div></section>`;visibleScreen()?.insertAdjacentHTML('beforeend',content)
    }catch{}
  }
  function transitionName'''


def patch_v1_full_visibility(html: str) -> str:
    """Expand operational read panels to the complete currently visible set."""

    if V1_FULL_VISIBILITY_MARKER in html:
        return html

    html, count = _OPERATIONAL_READERS.subn(_REPLACEMENT_READERS, html, count=1)
    if count != 1:
        raise RuntimeError("V1 full visibility patch: operational reader markers not found")

    # Detail panels should not silently omit students/classes.  Compact homepage
    # previews remain intentionally capped elsewhere and still link to full views.
    if "x.students.slice(0,8).map" not in html:
        raise RuntimeError("V1 full visibility patch: class student cap marker not found")
    html = html.replace("x.students.slice(0,8).map", "x.students.map", 1)

    if "studentProfiles(10)" not in html:
        raise RuntimeError("V1 full visibility patch: student profile cap marker not found")
    html = html.replace("studentProfiles(10)", "studentProfiles()", 1)

    # Applies to the native teacher workbench detail and the school facts detail.
    html = html.replace("rows.slice(0,12).map", "rows.map")

    html, count = _HISTORY_BLOCK.subn(_REPLACEMENT_HISTORY, html, count=1)
    if count != 1:
        raise RuntimeError("V1 full visibility patch: history marker not found")

    return html.replace("</body>", f"<!-- {V1_FULL_VISIBILITY_MARKER} --></body>", 1)


def install_v1_full_visibility_patch() -> None:
    """Install the bounded full-read patch once before V1 routes are bound."""

    if getattr(v1_module, "_full_visibility_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_full_visibility(original())

    v1_module.v1_html = patched_v1_html
    v1_module._full_visibility_patch_installed = True


__all__ = [
    "V1_FULL_VISIBILITY_MARKER",
    "install_v1_full_visibility_patch",
    "patch_v1_full_visibility",
]
