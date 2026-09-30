"""Student-specific automatic tests and knowledge-module practice for V1.

The feature deliberately reuses the existing Question -> Paper -> Assignment ->
AssignmentRecipient pipeline.  It adds no schema and keeps every generated
activity attached to the student's existing long-term record.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from changying.services.builtin_question_bank import (
    built_in_subjects,
    built_in_textbooks,
    ensure_built_in_questions,
    potential_question_catalog,
)
from changying.services.language_question_quality import (
    language_choice_repair,
    language_semantic_family,
)
from changying.services.question_type_fit import (
    question_type_fit_score,
    question_type_is_acceptable,
)
from changying.services.textbook_registry import (
    TextbookRegistryError,
    normalize_textbook,
    require_textbook,
)
from changying.web import v1 as v1_module


V1_STUDENT_PRACTICE_MARKER = "changying_v1_student_practice_v1"


# 人教版（2024 修订）五年级数学知识模块名称对齐表。
# 旧版教材中的“简易方程”“位置”等模块在最新人教版中已调整表述与编排，
# 这里把历史题库中的模块键映射到当前教材使用的模块名称，保证“知识模块练习”
# 展示与组卷都使用最新版本，而不是旧版单元名。
_GRADE5_MATH_MODULE_ALIASES = {
    "简易方程": "用字母表示数与方程",
    "方程": "用字母表示数与方程",
    "位置": "位置（用数对确定位置）",
    "用数对确定位置": "位置（用数对确定位置）",
}


def normalize_knowledge_module(grade: int, subject: str, knowledge: str) -> str:
    """把历史题库中的知识模块名对齐到当前人教版教材使用的模块名。

    仅对五年级数学做映射，其他年级/科目原样返回，避免影响既有题库。
    """
    key = (knowledge or "").strip()
    if not key:
        return key
    if int(grade or 0) == 5 and (subject or "").strip() == "数学":
        return _GRADE5_MATH_MODULE_ALIASES.get(key, key)
    return key


class StudentPracticeCreateBody(BaseModel):
    grade: int
    subject: str
    textbook: str = ""
    kind: str = "comprehensive"
    knowledge: str = ""
    difficulty: str = ""
    question_count: int = 10
    due_date: str = ""
    class_id: int | None = None


_ONLINE_QUESTION_TYPE_ORDER = (
    "single_choice",
    "true_false",
    "fill_blank",
    "calculation",
    "short_answer",
)


def _online_question_type(row: Any) -> str:
    # Selection must use the effective student-facing control, not only the
    # historical database tag. Unsafe language fills restored to choices by the
    # serializer belong in the choice bucket during mixed-type composition too.
    if language_choice_repair(row):
        return "single_choice"

    try:
        options = json.loads(getattr(row, "options_json", "[]") or "[]")
    except Exception:
        options = []
    if not isinstance(options, list):
        options = []

    raw = str(getattr(row, "question_type", "") or "").strip().lower()
    if not raw:
        try:
            if len(options) >= 2 and 0 <= int(getattr(row, "correct_index", -1)) < len(options):
                return "single_choice"
        except Exception:
            return ""
        return ""

    if raw in {"single_choice", "true_false"}:
        try:
            return raw if len(options) >= 2 and 0 <= int(getattr(row, "correct_index", -1)) < len(options) else ""
        except Exception:
            return ""

    if raw in {"fill_blank", "calculation", "short_answer"}:
        try:
            meta = json.loads(getattr(row, "answer_json", "{}") or "{}")
        except Exception:
            meta = {}
        return raw if isinstance(meta, dict) and str(meta.get("answer") or "").strip() else ""

    return ""


def _is_online_question(row: Any) -> bool:
    return bool(_online_question_type(row))


def _semantic_question_family(row: Any) -> str:
    """Return a source-aware content family for one selectable question."""
    subject = str(getattr(row, "subject", "") or "").strip()
    if subject in {"语文", "英语"}:
        return language_semantic_family(row)

    try:
        options = json.loads(getattr(row, "options_json", "[]") or "[]")
    except Exception:
        options = []
    if not isinstance(options, list):
        options = []
    try:
        meta = json.loads(getattr(row, "answer_json", "{}") or "{}")
    except Exception:
        meta = {}
    answer = str(meta.get("answer") or "").strip() if isinstance(meta, dict) else ""
    text = re.sub(r"\s+", "", str(getattr(row, "text", "") or "")).rstrip("。.!?！？")
    return "|".join(
        [
            subject,
            str(getattr(row, "knowledge", "") or "").strip(),
            text,
            json.dumps([str(x) for x in options], ensure_ascii=False),
            answer,
        ]
    )

def _select_type_diverse_questions(rows: list[Any], limit: int) -> list[Any]:
    """Round-robin types while prioritizing unique source content.

    Knowledge coverage remains the primary ordering goal.  Within the same
    knowledge pressure, a question whose semantic family is unique to its type
    is preferred, leaving shared source families available for scarcer types.
    Once a family is selected, all re-skinned variants of that same content are
    excluded from the current paper.
    """

    buckets: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        question_type = _online_question_type(row)
        subject = str(getattr(row, "subject", "") or "").strip()
        knowledge = str(getattr(row, "knowledge", "") or "").strip()
        if question_type and question_type_is_acceptable(subject, knowledge, question_type):
            buckets[question_type].append(row)
    for bucket in buckets.values():
        bucket.sort(key=lambda row: int(row.id))

    active_types = [
        question_type
        for question_type in _ONLINE_QUESTION_TYPE_ORDER
        if buckets.get(question_type)
    ]
    family_types: dict[str, set[str]] = defaultdict(set)
    for question_type in active_types:
        for row in buckets[question_type]:
            family_types[_semantic_question_family(row)].add(question_type)

    knowledge_hits: dict[str, int] = defaultdict(int)
    used_families: set[str] = set()
    chosen: list[Any] = []
    while len(chosen) < limit:
        added = False
        for question_type in active_types:
            bucket = buckets[question_type]
            candidates = [
                row
                for row in bucket
                if _semantic_question_family(row) not in used_families
            ]
            if not candidates:
                continue
            row = min(
                candidates,
                key=lambda item: (
                    question_type_fit_score(
                        str(getattr(item, "subject", "") or "").strip(),
                        str(getattr(item, "knowledge", "") or "").strip(),
                        _online_question_type(item),
                    ),
                    knowledge_hits[
                        (getattr(item, "knowledge", "") or getattr(item, "unit", "") or "综合").strip()
                        or "综合"
                    ],
                    1 if len(family_types[_semantic_question_family(item)]) > 1 else 0,
                    int(item.id),
                ),
            )
            bucket.remove(row)
            chosen.append(row)
            used_families.add(_semantic_question_family(row))
            knowledge_key = (
                (getattr(row, "knowledge", "") or getattr(row, "unit", "") or "综合").strip()
                or "综合"
            )
            knowledge_hits[knowledge_key] += 1
            added = True
            if len(chosen) >= limit:
                break
        if not added:
            break
    return chosen


def select_student_practice_questions(
    rows: list[Any],
    *,
    kind: str,
    knowledge: str = "",
    count: int = 10,
    textbook: str = "",
) -> list[Any]:
    """Choose deterministic, valid quiz questions for one student activity.

    Comprehensive tests round-robin across knowledge modules so one large module
    cannot crowd out the rest.  Module practice keeps the exact knowledge key.
    """

    limit = max(1, min(int(count or 10), 50))
    selected_textbook = (textbook or "").strip()
    eligible = [row for row in rows if _is_online_question(row)]
    if selected_textbook:
        eligible = [
            row
            for row in eligible
            if str(row.textbook or "").strip() == selected_textbook
        ]
    eligible.sort(key=lambda row: int(row.id))

    if kind == "module":
        key = (knowledge or "").strip()
        if not key:
            return []
        module_rows = [
            row for row in eligible if (getattr(row, "knowledge", "") or "").strip() == key
        ]
        return _select_type_diverse_questions(module_rows, limit)

    if kind != "comprehensive":
        return []

    return _select_type_diverse_questions(eligible, limit)


def _practice_patch_html() -> str:
    return r'''
<style id="changying_v1_student_practice_v1-style">
.cy-student-practice-launch,.cy-student-ai-practice-launch{margin-top:14px;margin-right:8px;border:1px solid rgba(255,255,255,.55);background:#fff;color:#173c78;border-radius:12px;padding:10px 13px;font-weight:900}
.cy-student-ai-practice-launch{background:#173c78;color:#fff;border-color:#173c78}
.cy-ai-feedback{display:grid;gap:8px;margin-top:12px}.cy-ai-feedback-row{display:flex;justify-content:space-between;gap:12px;padding:9px 10px;border-radius:10px;background:#fff;border:1px solid #dce5f0;font-size:12px}
.cy-ai-question{margin-top:10px;padding:12px;border-radius:12px;background:#fff;border:1px solid #dce5f0}.cy-ai-question b{display:block;line-height:1.55}.cy-ai-question small{display:block;color:#667085;line-height:1.55;margin-top:6px}.cy-ai-qmeta{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:7px}.cy-ai-qtag{display:inline-flex;padding:4px 7px;border:1px solid #d9e3f2;border-radius:999px;background:#f7f9fc;color:#526178;font-size:11px;font-weight:800}.cy-ai-figure{margin:10px 0;padding:8px;border:1px solid #e5e7eb;border-radius:12px;background:#fff}.cy-ai-figure svg{width:100%;max-width:420px;display:block;margin:auto}
.cy-practice-layer{position:fixed;inset:0;z-index:96;background:rgba(15,23,42,.42);display:flex;align-items:flex-end;justify-content:center;padding:18px}
.cy-practice-sheet{width:min(760px,100%);max-height:min(90dvh,920px);overflow:auto;background:#f7f9fc;border-radius:24px;padding:18px;box-shadow:0 30px 90px rgba(15,23,42,.3)}
.cy-practice-head{position:sticky;top:-18px;z-index:2;display:flex;justify-content:space-between;gap:12px;align-items:center;background:rgba(247,249,252,.96);padding:18px 0 12px}
.cy-practice-head h2{margin:0}.cy-practice-close{border:1px solid #d8e0ec;background:#fff;border-radius:12px;padding:9px 12px;font-weight:800}
.cy-practice-note{padding:11px 12px;border-radius:12px;background:#eef6ff;border:1px solid #d4e7ff;color:#285078;font-size:12px;line-height:1.6}
.cy-practice-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}
.cy-practice-field{display:grid;gap:6px}.cy-practice-field label{font-size:12px;font-weight:800}
.cy-practice-field input,.cy-practice-field select{width:100%;border:1px solid #cfd7e5;border-radius:11px;background:#fff;padding:10px 11px;font:inherit}
.cy-practice-submit{width:100%;margin-top:14px;border:0;background:#173c78;color:#fff;border-radius:12px;padding:12px;font-weight:900}
.cy-practice-ok{margin-top:12px;padding:12px;border-radius:12px;background:#ecfdf3;color:#166534;border:1px solid #bbf7d0}
.cy-practice-error{margin-top:12px;padding:12px;border-radius:12px;background:#fff1f1;color:#991b1b;border:1px solid #fecaca}
.cy-ai-assign-box{margin:12px 0;position:sticky;top:0;z-index:4}
@media(max-width:720px){.cy-practice-layer{padding:0}.cy-practice-sheet{max-height:92dvh;border-radius:24px 24px 0 0;padding:16px 14px calc(28px + env(safe-area-inset-bottom))}.cy-practice-grid{grid-template-columns:1fr}.cy-ai-assign-box{top:auto;bottom:calc(8px + env(safe-area-inset-bottom));z-index:8;box-shadow:0 10px 34px rgba(23,60,120,.18)}.cy-ai-assign-box .cy-practice-submit{margin-top:10px}}
</style>
<script id="changying_v1_student_practice_v1-script">
(()=>{
 if(window.__cyStudentPracticeInstalled)return;window.__cyStudentPracticeInstalled=true;
 const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
 const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
 async function api(url,opt={}){const t=token();if(!t||t==='demo')throw new Error('演示会话不会写入真实教学数据');const headers={Authorization:'Bearer '+t,...(opt.headers||{})};if(opt.body&&!headers['Content-Type'])headers['Content-Type']='application/json';const method=String(opt.method||'GET').toUpperCase(),retrySafe=method==='GET'||url.includes('/reinforcement/generate');let r=null,lastErr=null;for(let attempt=0;attempt<(retrySafe?2:1);attempt++){try{r=await fetch(url,{...opt,headers,cache:'no-store'});lastErr=null;break}catch(err){lastErr=err;if(attempt===0&&retrySafe)await new Promise(resolve=>setTimeout(resolve,900))}}if(lastErr||!r){throw new Error('网络连接刚刚中断，请稍后再试')}if(!r.ok){let msg='操作失败 '+r.status;try{const d=await r.json();msg=d.detail||d.message||msg}catch{}throw new Error(msg)}return r.status===204?null:await r.json()}
 function close(){document.getElementById('cy-practice-layer')?.remove();document.body.style.overflow=''}
 function dueDefault(){const d=new Date();d.setDate(d.getDate()+7);const pad=n=>String(n).padStart(2,'0');return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())}
 async function loadOptions(sid,grade,subject,textbook){const p=new URLSearchParams();if(grade)p.set('grade',grade);if(subject)p.set('subject',subject);if(textbook)p.set('textbook',textbook);return api('/teacher/students/'+sid+'/practice-options?'+p.toString())}
 function optionRows(values,current){return values.map(v=>'<option value="'+esc(v)+'" '+(String(v)===String(current)?'selected':'')+'>'+esc(v)+'</option>').join('')}
 function renderForm(layer,data){
   const body=layer.querySelector('#cy-practice-body');const student=data.student||{};const grade=data.selectedGrade||student.grade||5;const subject=data.selectedSubject||data.subjects?.[0]||'数学';const textbooks=data.textbooks||[];const textbook=data.selectedTextbook||textbooks[0]||'';
   const modules=data.modules||[];const classes=data.classes||[];
   body.innerHTML='<div class="cy-practice-note">综合测试会主动混排可自动判分的单选、判断、填空、计算等题型，并尽量覆盖不同知识模块；知识模块练习也会优先混排该模块已有题型。教材严格使用当前核定版本：数学使用人教版；语文使用统编版（人民教育出版社）；英语使用人教版（PEP·当前最新版）；不混用旧教材单元或其他出版社教材。当前年级科目可用约 '+esc(data.availableQuestionCount||0)+' 题；系统标准题只会在你确认添加时补入现有题库。</div>'+
   '<form id="cy-practice-form"><div class="cy-practice-grid">'+
   '<div class="cy-practice-field"><label>学生</label><input value="'+esc(student.name||'学生')+'" disabled></div>'+
   '<div class="cy-practice-field"><label>教学班级</label><select id="cy-p-class">'+classes.map(c=>'<option value="'+c.id+'" '+(Number(c.id)===Number(data.defaultClassID)?'selected':'')+'>'+esc(c.name)+' · '+esc(c.grade)+'年级</option>').join('')+'</select></div>'+
   '<div class="cy-practice-field"><label>年级</label><select id="cy-p-grade">'+[1,2,3,4,5,6].map(g=>'<option value="'+g+'" '+(Number(g)===Number(grade)?'selected':'')+'>'+g+'年级</option>').join('')+'</select></div>'+
   '<div class="cy-practice-field"><label>科目</label><select id="cy-p-subject">'+optionRows(data.subjects||[],subject)+'</select></div>'+
   '<div class="cy-practice-field"><label>教材</label><input value="'+esc(textbook==='人教版'?'人教版（当前最新版）':textbook||'暂无可用教材')+'" disabled><input id="cy-p-textbook" type="hidden" value="'+esc(textbook)+'"></div>'+((textbook&&modules.length)?'':'<div class="cy-practice-note" style="background:#fff7ed;border-color:#fed7aa;color:#9a3412">该学生当前年级/科目暂无可用教材或知识模块练习明细。请先在上方切换年级或科目，或确认题库中已导入对应教材题目；系统会在你确认添加时自动补入标准题。</div>')+
   '<div class="cy-practice-field"><label>内容类型</label><select id="cy-p-kind"><option value="comprehensive">该科目综合测试</option><option value="module">知识模块练习</option></select></div>'+
   '<div class="cy-practice-field" id="cy-p-module-wrap" style="display:none"><label>知识模块</label><select id="cy-p-module">'+modules.map(m=>'<option value="'+esc(m.knowledge)+'">'+esc((m.unit?m.unit+' · ':'')+m.knowledge+'（'+m.count+'题）')+'</option>').join('')+'</select></div>'+
   '<div class="cy-practice-field"><label>题数</label><input id="cy-p-count" type="number" min="1" max="50" value="20"></div>'+
   '<div class="cy-practice-field"><label>截止日期</label><input id="cy-p-due" type="date" value="'+dueDefault()+'"></div>'+
   '</div><button class="cy-practice-submit" type="submit">自动添加给学生</button><div id="cy-practice-result"></div></form>';
   const kind=body.querySelector('#cy-p-kind'),moduleWrap=body.querySelector('#cy-p-module-wrap'),moduleEl=body.querySelector('#cy-p-module'),countEl=body.querySelector('#cy-p-count'),resultBox=body.querySelector('#cy-practice-result');
   const clearResult=()=>{resultBox.innerHTML=''};
   const syncCount=()=>{moduleWrap.style.display=kind.value==='module'?'grid':'none';const selected=modules.find(m=>m.knowledge===moduleEl?.value);const available=kind.value==='module'?Number(selected?.count||0):Number(data.availableQuestionCount||0);const max=Math.max(1,Math.min(50,available||50));countEl.max=String(max);const current=Number(countEl.value)||0;if(current<1||current>max)countEl.value=String(Math.min(kind.value==='module'?10:20,max));clearResult()};
   kind.onchange=syncCount;if(moduleEl)moduleEl.onchange=syncCount;countEl.oninput=clearResult;body.querySelector('#cy-p-due').onchange=clearResult;body.querySelector('#cy-p-class').onchange=clearResult;syncCount();
   async function refreshOptions(){try{const next=await loadOptions(student.id,body.querySelector('#cy-p-grade').value,body.querySelector('#cy-p-subject').value,body.querySelector('#cy-p-textbook')?.value||'');renderForm(layer,next)}catch(err){resultBox.innerHTML='<div class="cy-practice-error">'+esc(err.message)+'</div>'}}
   body.querySelector('#cy-p-grade').onchange=async()=>{try{const next=await loadOptions(student.id,body.querySelector('#cy-p-grade').value,'','');renderForm(layer,next)}catch(err){body.querySelector('#cy-practice-result').innerHTML='<div class="cy-practice-error">'+esc(err.message)+'</div>'}};
   body.querySelector('#cy-p-subject').onchange=async()=>{try{const next=await loadOptions(student.id,body.querySelector('#cy-p-grade').value,body.querySelector('#cy-p-subject').value,'');renderForm(layer,next)}catch(err){resultBox.innerHTML='<div class="cy-practice-error">'+esc(err.message)+'</div>'}};
   body.querySelector('#cy-practice-form').onsubmit=async e=>{e.preventDefault();const btn=e.submitter;if(btn.disabled)return;let succeeded=false;btn.disabled=true;btn.textContent='正在自动组卷…';const result=body.querySelector('#cy-practice-result');try{const payload={grade:Number(body.querySelector('#cy-p-grade').value),subject:body.querySelector('#cy-p-subject').value,textbook:body.querySelector('#cy-p-textbook').value,kind:kind.value,knowledge:kind.value==='module'?(body.querySelector('#cy-p-module')?.value||''):'',question_count:Number(body.querySelector('#cy-p-count').value)||10,due_date:body.querySelector('#cy-p-due').value,class_id:Number(body.querySelector('#cy-p-class').value)||null};const created=await api('/teacher/students/'+student.id+'/auto-practice',{method:'POST',body:JSON.stringify(payload)});succeeded=true;result.innerHTML='<div class="cy-practice-ok"><b>已添加成功：</b>'+esc(created.assignment?.title||'测试/练习')+' · '+esc(created.questionCount)+'题。学生端现在可见；请勿重复添加。<br><button type="button" class="cy-practice-close" id="cy-practice-refresh" style="margin-top:9px">返回学生档案</button></div>';body.querySelector('#cy-practice-refresh').onclick=()=>location.reload();requestAnimationFrame(()=>result.scrollIntoView({behavior:'smooth',block:'center'}))}catch(err){result.innerHTML='<div class="cy-practice-error">'+esc(err.message)+'</div>';requestAnimationFrame(()=>result.scrollIntoView({behavior:'smooth',block:'center'}))}finally{if(succeeded){btn.disabled=true;btn.textContent='已添加成功'}else{btn.disabled=false;btn.textContent='自动添加给学生'}}};
 }
 async function open(sid){close();const layer=document.createElement('div');layer.id='cy-practice-layer';layer.className='cy-practice-layer';layer.innerHTML='<section class="cy-practice-sheet"><div class="cy-practice-head"><div><h2>添加测试 / 练习</h2><small style="color:#667085">按学生、年级、科目与当前核定教材题库组卷</small></div><button class="cy-practice-close" type="button">关闭</button></div><div id="cy-practice-body">正在读取题库与学生信息…</div></section>';document.body.appendChild(layer);document.body.style.overflow='hidden';layer.querySelector('.cy-practice-close').onclick=close;layer.onclick=e=>{if(e.target===layer)close()};try{renderForm(layer,await loadOptions(sid,'','',''))}catch(err){layer.querySelector('#cy-practice-body').innerHTML='<div class="cy-practice-error">'+esc(err.message)+'</div>'}}

 function cyQuestionTypeLabel(type){
   const t=String(type||'').toLowerCase();
   return ({single_choice:'单选题',choice:'单选题',true_false:'判断题',fill_blank:'填空题',calculation:'计算题',short_answer:'应用简答题'})[t]||'练习题';
 }
 function cyChoiceLike(q){
   const t=String(q?.question_type||'').toLowerCase();
   return ['single_choice','choice','true_false'].includes(t)||(((q?.options||[]).length>0)&&!['fill_blank','calculation','short_answer'].includes(t));
 }
 function cyRenderQuestionFigure(fig){
   if(!fig||!fig.type)return '';
   const type=String(fig.type||'').toLowerCase(),w=320,h=210,m=28,num=(v,d=0)=>Number.isFinite(+v)?+v:d;
   let body='';
   if(type==='coordinate_grid'){
     const xm=Math.max(1,Math.min(12,num(fig.xMax,8))),ym=Math.max(1,Math.min(12,num(fig.yMax,8))),sx=(w-2*m)/xm,sy=(h-2*m)/ym;
     for(let x=0;x<=xm;x++){const px=m+x*sx;body+='<line x1="'+px+'" y1="'+m+'" x2="'+px+'" y2="'+(h-m)+'" stroke="#d8dee9" stroke-width="1"/><text x="'+px+'" y="'+(h-m+17)+'" text-anchor="middle" font-size="10">'+x+'</text>'}
     for(let y=0;y<=ym;y++){const py=h-m-y*sy;body+='<line x1="'+m+'" y1="'+py+'" x2="'+(w-m)+'" y2="'+py+'" stroke="#d8dee9" stroke-width="1"/><text x="'+(m-9)+'" y="'+(py+3)+'" text-anchor="middle" font-size="10">'+y+'</text>'}
     (fig.segments||[]).forEach(seg=>{if(['x1','y1','x2','y2'].every(k=>Number.isFinite(+seg[k])))body+='<line x1="'+(m+num(seg.x1)*sx)+'" y1="'+(h-m-num(seg.y1)*sy)+'" x2="'+(m+num(seg.x2)*sx)+'" y2="'+(h-m-num(seg.y2)*sy)+'" stroke="#4b5563" stroke-width="2"/>'});
     (fig.points||[]).forEach(p=>{const px=m+num(p.x)*sx,py=h-m-num(p.y)*sy;body+='<circle cx="'+px+'" cy="'+py+'" r="4" fill="#111827"/><text x="'+(px+7)+'" y="'+(py-7)+'" font-size="12">'+esc(p.label||p.name||'')+'</text>'});
   }else if(type==='geometry'){
     const shape=String(fig.shape||'rectangle').toLowerCase(),labels=fig.labels||{};
     const txt=(key,x,y,anchor='middle')=>{if(labels[key])body+='<text x="'+x+'" y="'+y+'" text-anchor="'+anchor+'" font-size="12" font-weight="600">'+esc(labels[key])+'</text>'};
     if(shape==='triangle'){body='<polygon points="65,170 255,170 160,45" fill="none" stroke="#374151" stroke-width="3"/>';txt('底',160,190);if(labels['高']){body+='<line x1="160" y1="45" x2="160" y2="170" stroke="#64748b" stroke-width="1.5" stroke-dasharray="5 4"/>';txt('高',170,112,'start')}}
     else if(shape==='trapezoid'){body='<polygon points="85,55 225,55 270,170 45,170" fill="none" stroke="#374151" stroke-width="3"/>';txt('上底',155,45);txt('下底',155,190);if(labels['高']){body+='<line x1="155" y1="55" x2="155" y2="170" stroke="#64748b" stroke-width="1.5" stroke-dasharray="5 4"/>';txt('高',165,116,'start')}}
     else if(shape==='parallelogram'){body='<polygon points="90,55 260,55 225,170 55,170" fill="none" stroke="#374151" stroke-width="3"/>';txt('底',140,190);if(labels['高']){body+='<line x1="90" y1="55" x2="90" y2="170" stroke="#64748b" stroke-width="1.5" stroke-dasharray="5 4"/>';txt('高',100,116,'start')}}
     else if(shape==='nested_rect'||shape==='rectangle_with_inner_rectangle'){body='<rect x="55" y="45" width="210" height="125" fill="none" stroke="#374151" stroke-width="3"/><rect x="115" y="82" width="90" height="50" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5 4"/>';if(labels['外长'])body+='<text x="160" y="34" text-anchor="middle" font-size="11">外长 '+esc(labels['外长'])+'</text>';if(labels['外宽'])body+='<text x="272" y="111" font-size="11">外宽 '+esc(labels['外宽'])+'</text>';if(labels['内长'])body+='<text x="160" y="76" text-anchor="middle" font-size="11">内长 '+esc(labels['内长'])+'</text>';if(labels['内宽'])body+='<text x="210" y="109" font-size="11">内宽 '+esc(labels['内宽'])+'</text>'}
     else if(shape==='composite_rect'){body='<path d="M55 45 H265 V170 H145 V110 H55 Z" fill="none" stroke="#374151" stroke-width="3"/>';let y=198;Object.keys(labels).slice(0,4).forEach(k=>{body+='<text x="'+m+'" y="'+y+'" font-size="11">'+esc(k)+'：'+esc(labels[k])+'</text>';y-=15})}
     else {body='<rect x="55" y="50" width="210" height="120" fill="none" stroke="#374151" stroke-width="3"/>';txt('长',160,42);txt('宽',276,114,'start')}
   }else if(type==='line_segment'){
     const segs=(fig.segments||[]).length?fig.segments:[{label:'线段',ratio:1}],total=segs.reduce((sum,x)=>sum+Math.max(.1,num(x.ratio,1)),0);let x=m;
     segs.forEach((seg,idx)=>{const ww=(w-2*m)*Math.max(.1,num(seg.ratio,1))/total;body+='<line x1="'+x+'" y1="105" x2="'+(x+ww)+'" y2="105" stroke="#374151" stroke-width="4"/><line x1="'+x+'" y1="96" x2="'+x+'" y2="114" stroke="#374151" stroke-width="2"/><text x="'+(x+ww/2)+'" y="88" text-anchor="middle" font-size="12">'+esc(seg.label||('第'+(idx+1)+'段'))+'</text>';x+=ww});body+='<line x1="'+x+'" y1="96" x2="'+x+'" y2="114" stroke="#374151" stroke-width="2"/>';
   }else if(type==='bar_chart'){
     const bars=(fig.bars||[]).slice(0,8),max=Math.max(1,...bars.map(x=>num(x.value,0))),bw=Math.max(18,(w-2*m)/Math.max(1,bars.length)-10);
     body+='<line x1="'+m+'" y1="'+(h-m)+'" x2="'+(w-m)+'" y2="'+(h-m)+'" stroke="#374151"/>';
     bars.forEach((bar,idx)=>{const bh=(h-2*m)*num(bar.value,0)/max,x=m+idx*((w-2*m)/Math.max(1,bars.length))+5,y=h-m-bh;body+='<rect x="'+x+'" y="'+y+'" width="'+bw+'" height="'+bh+'" fill="#9ca3af"/><text x="'+(x+bw/2)+'" y="'+(h-m+15)+'" text-anchor="middle" font-size="10">'+esc(bar.name||bar.label||'')+'</text><text x="'+(x+bw/2)+'" y="'+(y-5)+'" text-anchor="middle" font-size="10">'+num(bar.value,0)+'</text>'});
   }else if(type==='object_group'){
     const groups=(fig.groups||[]).slice(0,6);let y=48;groups.forEach(g=>{const count=Math.max(0,Math.min(12,Math.round(num(g.count,0)))),symbol=esc(g.symbol||'●');body+='<text x="25" y="'+y+'" font-size="13">'+esc(g.label||g.name||'')+'：</text><text x="105" y="'+y+'" font-size="18">'+Array(count).fill(symbol).join(' ')+'</text>';y+=28});
   }else{return ''}
   const title=fig.title?'<div style="text-align:center;color:#667085;font-size:12px;margin-bottom:4px">'+esc(fig.title)+'</div>':'';
   return '<div class="cy-ai-figure">'+title+'<svg viewBox="0 0 '+w+' '+h+'" role="img" aria-label="题目图示">'+body+'</svg></div>';
 }

 async function openAIPractice(sid){
   close();const layer=document.createElement('div');layer.id='cy-practice-layer';layer.className='cy-practice-layer';
   layer.innerHTML='<section class="cy-practice-sheet"><div class="cy-practice-head"><div><h2>AI 针对性练习</h2><small style="color:#667085">自动关联最近综合测试、模块练习、知识点正确率与错题</small></div><button class="cy-practice-close" type="button">关闭</button></div><div id="cy-practice-body"><div class="cy-practice-note">AI 只读取该学生已有教学反馈；生成结果必须由教师审核后才会布置。</div><form id="cy-ai-practice-form"><div class="cy-practice-grid"><div class="cy-practice-field"><label>生成题数</label><input id="cy-ai-count" type="number" min="1" max="12" value="8"></div><div class="cy-practice-field"><label>难度</label><select id="cy-ai-difficulty"><option>基础</option><option selected>中等</option><option>提高</option></select></div></div><button class="cy-practice-submit" type="submit">读取反馈并生成针对性练习</button><div id="cy-ai-result"></div></form></div></section>';
   document.body.appendChild(layer);document.body.style.overflow='hidden';layer.querySelector('.cy-practice-close').onclick=close;layer.onclick=e=>{if(e.target===layer)close()};
   const form=layer.querySelector('#cy-ai-practice-form'),result=layer.querySelector('#cy-ai-result');
   form.onsubmit=async e=>{e.preventDefault();const btn=e.submitter;btn.disabled=true;btn.textContent='正在关联测试反馈并生成…';result.innerHTML='';
     try{
       const draft=await api('/teacher/students/'+sid+'/reinforcement/generate',{method:'POST',body:JSON.stringify({count:Number(layer.querySelector('#cy-ai-count').value)||8,difficulty:layer.querySelector('#cy-ai-difficulty').value,notes:'综合关联该学生最近综合测试与知识模块练习反馈，优先针对薄弱知识点；保持年级、科目和教材版本一致；5题以上至少使用3种题型并包含非选择题；坐标位置、平面图形面积、植树线段关系、统计图等确实需要图示时必须返回结构化figure'})});
       const ctx=draft.assessmentContext||{},weak=(ctx.weakKnowledge||[]).slice(0,6),draftSubject=String(ctx.primary?.subject||draft.items?.[0]?.subject||'').trim();
       const feedback=weak.length?'<div class="cy-ai-feedback">'+weak.map(x=>'<div class="cy-ai-feedback-row"><span>'+esc((x.textbook?x.textbook+' · ':'')+(x.knowledge||'知识点'))+'</span><b>'+esc(x.accuracy)+'% · '+esc(x.answered)+'题</b></div>').join('')+'</div>':'';
       const questions=(draft.items||[]).map((q,i)=>{
         const options=q.options||[],choice=cyChoiceLike(q),type=cyQuestionTypeLabel(q.question_type),fig=cyRenderQuestionFigure(q.figure||{});
         const optionHtml=choice&&options.length?'<div style="margin-top:7px;color:#667085;line-height:1.65">'+options.map((x,j)=>String.fromCharCode(65+j)+'. '+esc(x)).join('<br>')+'</div>':'';
         const answer=choice?(String.fromCharCode(65+Number(q.correct_index||0))+' · '+esc(options[Number(q.correct_index||0)]||'')):esc(q.answer||'');
         const accepted=(q.accepted_answers||[]).length?' <span style="color:#667085">可接受：'+esc((q.accepted_answers||[]).join(' / '))+'</span>':'';
         return '<div class="cy-ai-question"><div class="cy-ai-qmeta"><span class="cy-ai-qtag">'+esc(type)+'</span><span class="cy-ai-qtag">'+esc(q.knowledge||'知识点')+'</span></div><b>'+(i+1)+'. '+esc(q.text)+'</b>'+fig+optionHtml+'<small>'+esc(q.textbook||'')+(q.textbook&&q.knowledge?' · ':'')+esc(q.knowledge||'')+'<br><b style="display:inline">参考答案：</b>'+answer+accepted+(q.explanation?' · '+esc(q.explanation):'')+'</small></div>';
       }).join('');
       const assignBox='<div class="cy-practice-ok cy-ai-assign-box"><b>状态：未布置 · 当前仅为教师审核预览，学生端不会看到。</b><div style="margin-top:8px">确认题目、答案和图示无误后，点击下面按钮才会真正布置给学生。</div><div class="cy-practice-grid" style="margin-top:10px"><div class="cy-practice-field"><label>截止日期</label><input id="cy-ai-due" type="date" value="'+dueDefault()+'"></div></div><button type="button" class="cy-practice-submit" id="cy-ai-assign">审核无误，布置给该学生</button></div>';
       result.innerHTML='<div class="cy-practice-ok"><b>反馈关联完成：</b>'+esc(draft.notice||'已根据学习反馈生成。')+'</div>'+feedback+assignBox+questions;
       layer.querySelector('#cy-ai-assign').onclick=async ev=>{const ab=ev.currentTarget;ab.disabled=true;ab.textContent='正在布置…';try{const assigned=await api('/teacher/students/'+sid+'/reinforcement/assign',{method:'POST',body:JSON.stringify({questions:draft.items,title:(draftSubject?draftSubject+' AI 针对性练习':'AI 针对性练习'),due_date:layer.querySelector('#cy-ai-due').value,wrong_ids:draft.wrongIDs||[],instructions:'根据最近综合测试、知识模块练习和知识点反馈生成的针对性练习。完成后结果继续进入学生连续学习档案。'})});result.innerHTML='<div class="cy-practice-ok"><b>状态：已布置 · '+esc(draftSubject?draftSubject+' AI 针对性练习':'AI 针对性练习')+'已在学生端可见。</b>共 '+esc(assigned.questionIDs?.length||draft.items?.length||0)+' 题，只发送给当前学生。<br><button type="button" class="cy-practice-close" id="cy-ai-back" style="margin-top:9px">返回学生档案</button></div>';layer.querySelector('#cy-ai-back').onclick=()=>location.reload()}catch(err){result.insertAdjacentHTML('afterbegin','<div class="cy-practice-error">'+esc(err.message)+'</div>');ab.disabled=false;ab.textContent='审核无误，布置给该学生'}};
     }catch(err){result.innerHTML='<div class="cy-practice-error">'+esc(err.message)+'</div>'}
     finally{btn.disabled=false;btn.textContent='读取反馈并生成针对性练习'}
   };
 }
 let checking=false;
 async function mount(){if(checking||!location.pathname.includes('/v1/student'))return;const sid=Number(new URLSearchParams(location.search).get('id')||0);const head=document.querySelector('.student-head');if(!sid||!head||head.querySelector('.cy-student-practice-launch'))return;checking=true;try{const s=await api('/session');if(s.role!=='teacher')return;const b=document.createElement('button');b.type='button';b.className='cy-student-practice-launch';b.textContent='＋ 添加测试 / 练习';b.onclick=()=>open(sid);head.appendChild(b);const ai=document.createElement('button');ai.type='button';ai.className='cy-student-ai-practice-launch';ai.textContent='✨ AI 针对性练习';ai.onclick=()=>openAIPractice(sid);head.appendChild(ai)}catch(_){}finally{checking=false}}
 const observer=new MutationObserver(()=>mount());observer.observe(document.documentElement,{subtree:true,childList:true});window.addEventListener('popstate',mount);setTimeout(mount,0);
})();
</script>
'''


def patch_v1_student_practice_html(html: str) -> str:
    if V1_STUDENT_PRACTICE_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 student practice patch: closing body marker not found")
    return html.replace("</body>", _practice_patch_html() + "\n</body>", 1)


def install_v1_student_practice_patch() -> None:
    if getattr(v1_module, "_student_practice_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_student_practice_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._student_practice_patch_installed = True


def install_v1_student_practice_routes(implementation: Any) -> None:
    app = implementation.app
    if getattr(app.state, "v1_student_practice_routes_installed", False):
        return

    User = implementation.User
    Question = implementation.Question
    Paper = implementation.Paper
    Assignment = implementation.Assignment
    AssignmentSubmissionSetting = implementation.AssignmentSubmissionSetting
    SchoolClass = implementation.SchoolClass
    ClassStudent = implementation.ClassStudent
    current_user = implementation.current_user
    get_db = implementation.get_db
    Session = implementation.Session
    router = APIRouter()

    def teacher_student_context(db, user, sid: int) -> tuple[Any, list[Any]]:
        implementation.need(user, "teacher")
        student = db.scalar(
            select(User).where(
                User.id == sid,
                User.school_id == user.school_id,
                User.role == "student",
                User.active == True,
            )
        )
        if not student:
            raise HTTPException(404, "学生不存在或已归档")
        classes = list(
            db.scalars(
                select(SchoolClass)
                .join(ClassStudent, ClassStudent.class_id == SchoolClass.id)
                .where(
                    ClassStudent.student_id == sid,
                    SchoolClass.school_id == user.school_id,
                    SchoolClass.teacher_id == user.id,
                )
                .order_by(SchoolClass.id.desc())
            ).all()
        )
        if not classes:
            raise HTTPException(403, "该学生不在你的在读班级")
        return student, classes

    @router.get("/teacher/students/{sid}/practice-options")
    def student_practice_options(
        sid: int,
        grade: int | None = None,
        subject: str | None = None,
        textbook: str | None = None,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        student, classes = teacher_student_context(db, u, sid)
        selected_grade = int(grade or student.grade or classes[0].grade or 5)
        if selected_grade not in range(1, 7):
            raise HTTPException(400, "年级必须为1-6")

        subjects = list(
            db.scalars(
                select(Question.subject)
                .where(
                    Question.school_id == u.school_id,
                    Question.grade == selected_grade,
                )
                .distinct()
                .order_by(Question.subject)
            ).all()
        )
        subjects = [str(x).strip() for x in subjects if str(x or "").strip()]
        subjects = sorted(set(subjects) | set(built_in_subjects(selected_grade)))
        selected_subject = (subject or "").strip()
        if not selected_subject or selected_subject not in subjects:
            selected_subject = subjects[0] if subjects else ""

        textbooks: list[str] = []
        selected_textbook = ""
        if selected_subject:
            # Automatic tests/practice use the school's current PEP line only.
            # Other publishers are distinct教材体系, not alternate "versions".
            textbooks = built_in_textbooks(selected_grade, selected_subject)
            try:
                requested_textbook = normalize_textbook(
                    selected_grade,
                    selected_subject,
                    (textbook or "").strip(),
                )
            except TextbookRegistryError:
                requested_textbook = ""
            if requested_textbook in textbooks:
                selected_textbook = requested_textbook
            else:
                selected_textbook = textbooks[0] if textbooks else ""

        modules: list[dict[str, Any]] = []
        available_count = 0
        if selected_subject and selected_textbook:
            rows = list(
                db.scalars(
                    select(Question)
                    .where(
                        Question.school_id == u.school_id,
                        Question.grade == selected_grade,
                        Question.subject == selected_subject,
                        Question.textbook == selected_textbook,
                    )
                    .order_by(Question.unit, Question.knowledge, Question.id)
                ).all()
            )
            modules, available_count = potential_question_catalog(
                rows,
                grade=selected_grade,
                subject=selected_subject,
                textbook=selected_textbook,
            )

        default_class = next(
            (c for c in classes if int(c.grade or 0) == int(student.grade or 0)),
            classes[0],
        )
        return {
            "student": {"id": student.id, "name": student.name, "grade": student.grade},
            "classes": [
                {"id": c.id, "name": c.name, "grade": c.grade}
                for c in classes
            ],
            "defaultClassID": default_class.id,
            "selectedGrade": selected_grade,
            "subjects": subjects,
            "selectedSubject": selected_subject,
            "textbooks": textbooks,
            "selectedTextbook": selected_textbook,
            "modules": modules,
            "availableQuestionCount": available_count,
        }

    @router.post("/teacher/students/{sid}/auto-practice")
    def create_student_practice(
        sid: int,
        body: StudentPracticeCreateBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        student, classes = teacher_student_context(db, u, sid)
        if body.grade not in range(1, 7):
            raise HTTPException(400, "年级必须为1-6")
        subject = (body.subject or "").strip()
        if not subject:
            raise HTTPException(400, "请选择科目")
        try:
            textbook = require_textbook(
                body.grade,
                subject,
                (body.textbook or "").strip(),
            )
        except TextbookRegistryError as exc:
            raise HTTPException(400, str(exc)) from exc
        allowed_textbooks = built_in_textbooks(body.grade, subject)
        if not textbook:
            raise HTTPException(400, "当前自动测试尚未匹配到可用的核定教材")
        if textbook not in allowed_textbooks:
            raise HTTPException(
                400,
                "当前自动测试只允许使用该年级科目已核定的教材版本",
            )
        kind = (body.kind or "comprehensive").strip().lower()
        if kind not in {"comprehensive", "module"}:
            raise HTTPException(400, "内容类型无效")
        count = max(1, min(int(body.question_count or 10), 50))

        class_row = None
        if body.class_id:
            class_row = next((c for c in classes if c.id == body.class_id), None)
            if not class_row:
                raise HTTPException(403, "所选班级不属于该学生或当前教师")
        else:
            class_row = next(
                (c for c in classes if int(c.grade or 0) == int(student.grade or 0)),
                classes[0],
            )

        ensure_built_in_questions(
            db,
            Question,
            school_id=u.school_id,
            creator_id=u.id,
            grade=body.grade,
            subject=subject,
            textbook=textbook,
        )
        rows = list(
            db.scalars(
                select(Question)
                .where(
                    Question.school_id == u.school_id,
                    Question.grade == body.grade,
                    Question.subject == subject,
                    Question.textbook == textbook,
                )
                .order_by(Question.id)
            ).all()
        )
        chosen = select_student_practice_questions(
            rows,
            kind=kind,
            knowledge=body.knowledge,
            count=count,
            textbook=textbook,
        )
        if not chosen:
            if kind == "module":
                raise HTTPException(400, "当前题库没有该知识模块可用于在线练习的题目")
            raise HTTPException(400, "当前题库没有该年级科目可用于综合测试的题目")

        if kind == "module":
            knowledge = (body.knowledge or "").strip()
            title = f"{body.grade}年级{subject}（{textbook}）· {knowledge}专项练习"
            unit = knowledge
            source = "student_module_practice"
        else:
            title = f"{body.grade}年级{subject}（{textbook}）综合测试"
            unit = "综合"
            source = "student_comprehensive_test"

        due_date = (body.due_date or "").strip() or (
            datetime.now(implementation.SCHOOL_TZ) + timedelta(days=7)
        ).date().isoformat()
        question_ids = [int(q.id) for q in chosen]
        paper = Paper(
            school_id=u.school_id,
            title=title[:160],
            grade=body.grade,
            subject=subject[:30],
            textbook=textbook[:80],
            unit=unit[:100],
            question_ids_json=json.dumps(question_ids),
            teacher_id=u.id,
        )
        db.add(paper)
        db.flush()
        assignment = Assignment(
            school_id=u.school_id,
            title=title[:160],
            class_id=class_row.id,
            paper_id=paper.id,
            due_date=due_date,
        )
        db.add(assignment)
        db.flush()
        db.add(
            AssignmentSubmissionSetting(
                school_id=u.school_id,
                assignment_id=assignment.id,
                mode="quiz",
                instructions=(
                    "完成后用于更新当前学生的学科与知识点学习记录。"
                    if kind == "comprehensive"
                    else "完成该知识模块练习，并根据结果继续安排针对性巩固。"
                ),
            )
        )
        implementation.ensure_recipient(
            db,
            assignment,
            student.id,
            source,
        )
        covered = sorted(
            {
                (q.knowledge or q.unit or "综合").strip() or "综合"
                for q in chosen
            }
        )
        implementation.audit(
            db,
            u,
            "student.practice.create",
            (
                f"student={student.id}:assignment={assignment.id}:"
                f"kind={kind}:grade={body.grade}:subject={subject}:"
                f"textbook={textbook}:"
                f"questions={len(question_ids)}"
            ),
        )
        db.commit()
        db.refresh(assignment)
        return {
            "ok": True,
            "student": {"id": student.id, "name": student.name},
            "assignment": implementation.aj(db, assignment),
            "paper": implementation.pj(paper),
            "kind": kind,
            "textbook": textbook,
            "questionCount": len(question_ids),
            "knowledgeCovered": covered,
            "recipientCount": 1,
        }

    app.include_router(router)
    app.state.v1_student_practice_routes_installed = True


__all__ = [
    "StudentPracticeCreateBody",
    "V1_STUDENT_PRACTICE_MARKER",
    "install_v1_student_practice_patch",
    "install_v1_student_practice_routes",
    "patch_v1_student_practice_html",
    "select_student_practice_questions",
]
