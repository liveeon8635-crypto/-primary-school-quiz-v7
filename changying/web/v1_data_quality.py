"""Read-only V1 data-quality patch for student continuity.

The legacy database may contain more than one student row with the same display
name and may use teaching-project names where V1 previously said "当前班级".
This patch deliberately does not merge, delete, or rewrite production data. It
aggregates teaching affiliations for the same stable student id and surfaces
same-name/different-id records as candidates for human identity review.
"""

from __future__ import annotations

import re

from changying.web import v1 as v1_module


_STUDENT_POSITION = re.compile(
    r"    const studentPosition=p=>\{.*?\};\n",
)
_LOAD_PEOPLE = re.compile(
    r"    async function loadPeople\(\)\{.*?\n    async function workspace\(\)",
    re.DOTALL,
)


def patch_v1_html(html: str) -> str:
    """Return the V1 shell with read-only continuity auditing installed."""

    if "const teachingAffiliationsFor=" in html and "const duplicateAuditHtml=" in html:
        return html

    helpers = """    const teachingAffiliationsFor=p=>{const raw=Array.isArray(p?.teachingAffiliations)?p.teachingAffiliations:[p?.className||p?.currentClassName].filter(Boolean);return [...new Set(raw.map(x=>String(x||'').trim()).filter(Boolean))]};
    const studentPosition=p=>{const grade=p?.grade?`档案年级：${p.grade}年级`:'';const affiliations=teachingAffiliationsFor(p);const current=affiliations.length?`当前教学归属：${affiliations.join(' / ')}`:'当前教学归属待完善';return[grade,current].filter(Boolean).join(' · ')};
    const normalizedStudentName=p=>String(p?.name||'').replace(/\\s+/g,'').trim().toLocaleLowerCase();
    const duplicateNameGroups=people=>{const groups=new Map();for(const p of people||[]){const key=normalizedStudentName(p);if(!key)continue;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(p)}return [...groups.values()].filter(group=>new Set(group.map(p=>String(p.id))).size>1)};
    const duplicateAuditHtml=people=>{const groups=duplicateNameGroups(people);if(!groups.length)return'';return `<section class=\"section\"><div class=\"notice warn\"><b>发现 ${groups.length} 组同名多档案，暂不自动合并。</b><div style=\"margin-top:6px\">请先依据档案编号、年级与教学归属核对是否为同一名学生；确认前系统不会删除或合并真实记录。</div>${groups.map(group=>`<div style=\"margin-top:8px\"><b>${esc(group[0].name)}</b>：${group.map(p=>`档案 #${esc(p.id)}（${esc(studentPosition(p))}）`).join('；')}</div>`).join('')}</div></section>`};
"""
    html, count = _STUDENT_POSITION.subn(lambda _match: helpers, html, count=1)
    if count != 1:
        raise RuntimeError("V1 data-quality patch: studentPosition marker not found")

    load_people = """    async function loadPeople(){if(session.role==='admin'){const users=await api('/admin/users');return users.filter(x=>x.role==='student')}if(session.role==='teacher'){const classes=await api('/teacher/classes');const byId=new Map();for(const c of classes.slice(0,30)){try{const rows=await api('/teacher/classes/'+c.id+'/students');for(const x of rows){const key=String(x.id);if(!byId.has(key))byId.set(key,{...x,teachingAffiliations:[],classIDs:[]});const p=byId.get(key);if(c.name&&!p.teachingAffiliations.includes(c.name))p.teachingAffiliations.push(c.name);if(c.id&&!p.classIDs.includes(c.id))p.classIDs.push(c.id)}}catch{}}return [...byId.values()]}if(session.role==='parent')return await api('/parent/children');return[{id:session.userID||session.id,name:session.name,grade:session.grade,role:'student'}]}
    async function workspace()"""
    html, count = _LOAD_PEOPLE.subn(lambda _match: load_people, html, count=1)
    if count != 1:
        raise RuntimeError("V1 data-quality patch: loadPeople marker not found")

    workspace_marker = "</div></section><section class=\"section\"><div class=\"section-head\"><div><h2>当前学生</h2>"
    workspace_replacement = "</div></section>${duplicateAuditHtml(people)}<section class=\"section\"><div class=\"section-head\"><div><h2>当前学生</h2>"
    if workspace_marker not in html:
        raise RuntimeError("V1 data-quality patch: workspace student-list marker not found")
    html = html.replace(workspace_marker, workspace_replacement, 1)

    student_marker = "const content=heading('学生','打开学生的长期连续发展档案。','<span class=\"tag\">学生是独立实体</span>')+`<div class=\"list\">"
    student_replacement = "const content=heading('学生','打开学生的长期连续发展档案。','<span class=\"tag\">学生是独立实体</span>')+duplicateAuditHtml(people)+`<div class=\"list\">"
    if student_marker not in html:
        raise RuntimeError("V1 data-quality patch: student-index marker not found")
    html = html.replace(student_marker, student_replacement, 1)

    return html


def install_v1_data_quality_patch() -> None:
    """Patch V1 rendering once; this changes presentation only, never storage."""

    if getattr(v1_module, "_data_quality_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._data_quality_patch_installed = True


__all__ = ["install_v1_data_quality_patch", "patch_v1_html"]
