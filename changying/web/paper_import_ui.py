"""Classic 组卷与作业 page: 导入试卷 (past paper / 真题 import).

Adds an 导入试卷 button next to ＋布置作业. Flow: choose source (paste text,
.pdf/.docx/.txt, or up to four photos) -> AI transcription -> teacher reviews
and edits every question (answer source is shown; missing answers must be
filled) -> save as a paper, optionally assigned to a class. Backend:
changying/web/paper_import_routes.py.
"""

from __future__ import annotations

PAPER_IMPORT_MARKER = "changying_paper_import_v1"

PAPER_IMPORT_SCRIPT = r"""
<script id="changying_paper_import_v1-script">
(()=>{
const TYPE_NAMES={single_choice:"单选",true_false:"判断",fill_blank:"填空",calculation:"计算",short_answer:"简答",non_choice:"主观题"};
let importItems=[],importScope={},importClasses=[],importMode="paper";
const readFileBase64=file=>new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result||"").split(",")[1]||"");r.onerror=()=>reject(new Error("文件读取失败"));r.readAsDataURL(file)});
const compressPhoto=file=>new Promise((resolve,reject)=>{const url=URL.createObjectURL(file),img=new Image();img.onload=()=>{try{const scale=Math.min(1,1800/Math.max(img.naturalWidth,img.naturalHeight));const c=document.createElement("canvas");c.width=Math.round(img.naturalWidth*scale);c.height=Math.round(img.naturalHeight*scale);c.getContext("2d").drawImage(img,0,0,c.width,c.height);let data=c.toDataURL("image/jpeg",0.8);for(let q=0.7;data.length>1900000&&q>=0.4;q-=0.1)data=c.toDataURL("image/jpeg",q);if(data.length>1900000)throw new Error("照片太大，请裁剪后重试");resolve(data)}catch(e){reject(e)}finally{URL.revokeObjectURL(url)}};img.onerror=()=>{URL.revokeObjectURL(url);reject(new Error("无法读取这张照片"))};img.src=url});
// Cut each question's figure out of its photo/scan (feedback #357 r2). The box is
// in fractions of the image; a little margin keeps labels at the edge of the figure.
const loadImage=src=>new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error("无法读取原卷图片"));img.src=src});
async function cropFigures(result){
 const cache={};
 for(const q of result.items||[]){
  const r=q.figureRegion,src=r&&((result.sourceImages||{})[String(r.image)]||(result.localImages||[])[r.image]);
  if(!src)continue;
  try{
   const img=cache[r.image]||(cache[r.image]=await loadImage(src));
   const W=img.naturalWidth,H=img.naturalHeight,pad=0.015;
   const x0=Math.max(0,r.box[0]-pad)*W,y0=Math.max(0,r.box[1]-pad)*H,x1=Math.min(1,r.box[2]+pad)*W,y1=Math.min(1,r.box[3]+pad)*H;
   const scale=Math.min(1,900/Math.max(x1-x0,y1-y0)),c=document.createElement("canvas");
   c.width=Math.max(1,Math.round((x1-x0)*scale));c.height=Math.max(1,Math.round((y1-y0)*scale));
   const ctx=c.getContext("2d");ctx.fillStyle="#fff";ctx.fillRect(0,0,c.width,c.height);ctx.drawImage(img,x0,y0,x1-x0,y1-y0,0,0,c.width,c.height);
   let data=c.toDataURL("image/jpeg",0.85);for(let k=0.75;data.length>690000&&k>=0.4;k-=0.1)data=c.toDataURL("image/jpeg",k);
   if(data.length<=690000)q.figure={type:"uploaded_image",data_url:data,alt:"题目插图"};
  }catch(e){/* keep the question; the teacher sees it has no figure */}
 }
 return result;
}
const figureEditor=(q,i)=>q.figure?`<div style="margin:6px 0"><img src="${q.figure.data_url}" alt="题目插图" style="display:block;max-width:100%;max-height:260px;object-fit:contain;border:1px solid var(--line);border-radius:8px"><label style="display:flex;gap:6px;align-items:center"><input type="checkbox" data-pi-figure="${i}" checked>保留这张插图（从原卷裁出，裁得不对可取消勾选）</label></div>`:(q.figureRegion?'<small class="muted">这道题需要插图，但没能从原卷裁出；保存后可在题库中补拍照片。</small>':"");
// The toast sits under an open dialog, so errors are also shown inside it (feedback #370: "no prompt").
function piError(msg){
 const box=$("#piErr");if(box){box.textContent=msg||"";box.style.display=msg?"block":"none";if(msg&&box.scrollIntoView)box.scrollIntoView({block:"nearest"})}
 if(msg)toast(msg);
}
const piErrBox='<div id="piErr" role="alert" style="display:none;margin:8px 0;padding:8px 10px;border-radius:8px;background:#fdecee;color:#d6485e;font-weight:600"></div>';
// Where did the import go? (feedback #370: teachers could not find a saved paper.)
function savedNotice(saved,title,count){
 const unit=esc(importScope.unit||"导入试卷"),name=esc(saved.title||title);
 modal("已保存",`<p><b>试卷《${name}》</b>已保存到「组卷与作业」，共 ${count} 道题。</p>
 ${saved.assignment?"<p>已布置给所选班级，学生会在作业里看到它。</p>":"<p>还没有布置给学生，可以在「组卷与作业」里布置。</p>"}
 <p class=\"muted\">这些题同时进了「教材题库」（单元：${unit}），之后组卷、出题也能抽到。${saved.reusedCount?`其中 ${saved.reusedCount} 道题库里已有完全相同的题，直接沿用，没有重复保存。`:""}</p>
 <button class=\"btn primary full\" id=\"piSavedOk\">知道了</button>`);
 const ok=$("#piSavedOk");if(ok)ok.onclick=()=>closeModal();
}
const sourceBadge=q=>q.needsAnswer?'<span class="badge red">缺答案，请补全</span>':q.answerSource==="paper"?'<span class="badge green">试卷答案</span>':'<span class="badge">AI 解答，请核对</span>';
function answerEditor(q,i){
 if(q.question_type==="single_choice")return `<div class="form-grid">${q.options.map((o,j)=>`<div><label>选项 ${String.fromCharCode(65+j)}</label><input data-pi-opt="${i}:${j}" value="${esc(o)}"></div>`).join("")}<div><label>正确答案</label><select data-pi-correct="${i}"><option value="-1">请选择</option>${q.options.map((_,j)=>`<option value="${j}" ${j===q.correct_index?"selected":""}>${String.fromCharCode(65+j)}</option>`).join("")}</select></div></div>`;
 if(q.question_type==="true_false")return `<label>判断结果</label><select data-pi-correct="${i}"><option value="-1">请选择</option><option value="0" ${q.correct_index===0?"selected":""}>正确</option><option value="1" ${q.correct_index===1?"selected":""}>错误</option></select>`;
 if(q.question_type==="non_choice")return `<label>参考答案（教师审核评分）</label><textarea data-pi-ref="${i}">${esc(q.reference_answer||"")}</textarea><label>评分要点（每行一条，可选）</label><textarea data-pi-points="${i}">${esc((q.scoring_points||[]).join("\n"))}</textarea>`;
 return `<div class="form-grid"><div><label>标准答案</label><input data-pi-answer="${i}" value="${esc(q.answer||"")}"></div><div><label>等价答案（用 | 隔开，可选）</label><input data-pi-accepted="${i}" value="${esc((q.accepted_answers||[]).join(" | "))}"></div></div>`;
}
function collectEdits(){
 return importItems.map((q,i)=>{
  if(!document.querySelector(`[data-pi-pick="${i}"]`)?.checked)return null;
  const v=sel=>document.querySelector(sel)?.value??"";
  const out={...q,text:v(`[data-pi-text="${i}"]`).trim()};delete out.figureRegion;
  if(!document.querySelector(`[data-pi-figure="${i}"]`)?.checked)delete out.figure;
  if(q.question_type==="single_choice")out.options=q.options.map((_,j)=>v(`[data-pi-opt="${i}:${j}"]`).trim());
  if(q.question_type==="single_choice"||q.question_type==="true_false")out.correct_index=+v(`[data-pi-correct="${i}"]`);
  if(["fill_blank","calculation","short_answer"].includes(q.question_type)){out.answer=v(`[data-pi-answer="${i}"]`).trim();out.accepted_answers=v(`[data-pi-accepted="${i}"]`).split("|").map(x=>x.trim()).filter(Boolean)}
  if(q.question_type==="non_choice"){out.reference_answer=v(`[data-pi-ref="${i}"]`).trim();out.scoring_points=v(`[data-pi-points="${i}"]`).split(/\n+/).map(x=>x.trim()).filter(Boolean)}
  return out;
 }).filter(Boolean);
}
function reviewImport(result){
 importItems=result.items||[];
 const skipped=(result.skipped||[]).map(x=>`第${esc(x.number||"?")}题：${esc(x.reason||"未录入")}`).join("；");
 const classOptions=importClasses.map(c=>`<option value="${c.id}">${esc(c.name)}（${c.studentCount||0}人）</option>`).join("");
 modal("核对导入的题目",`<p class="muted">${esc(result.notice||"")}</p>${skipped?`<p class="muted">未录入：${skipped}</p>`:""}
 <div class="list">${importItems.map((q,i)=>`<div class="item" style="display:block"><label style="display:flex;gap:8px;align-items:center"><input type="checkbox" data-pi-pick="${i}" checked><b>${esc(q.number?("第"+q.number+"题"):("第"+(i+1)+"题"))}</b><span class="badge">${TYPE_NAMES[q.question_type]||q.question_type}</span>${sourceBadge(q)}</label>
 <label>题干</label><textarea data-pi-text="${i}">${esc(q.text)}</textarea>${figureEditor(q,i)}${answerEditor(q,i)}<small class="muted">知识点：${esc(q.knowledge||"")}</small></div>`).join("")}</div>
 ${importMode==="bank"?`<small class="muted">勾选的题目会保存到教材题库，之后布置作业时按题型均衡抽题。</small>`:`<label>试卷名称</label><input id="piTitle" value="${esc(importScope.title||"")}">
 <div class="form-grid"><div><label>布置给班级（可选）</label><select id="piClass"><option value="">只保存为试卷，暂不布置</option>${classOptions}</select></div><div><label>截止日期</label><input type="date" id="piDue"></div></div>
 <small class="muted">含主观题的试卷会改为拍照提交、教师评分；其余题型在线自动判分。</small>`}
 ${piErrBox}
 <button class="btn primary full" id="piSave">${importMode==="bank"?"确认已核对，保存到题库":"确认保存"}</button>`);
 $("#piSave").onclick=async()=>{const btn=$("#piSave");if(btn.disabled)return;piError("");try{
  const questions=collectEdits();if(!questions.length)throw new Error("请至少勾选 1 道题");
  const missing=questions.findIndex(q=>(["single_choice","true_false"].includes(q.question_type)&&!(q.correct_index>=0))||(["fill_blank","calculation","short_answer"].includes(q.question_type)&&!q.answer)||(q.question_type==="non_choice"&&!q.reference_answer)||!q.text);
  if(missing>=0)throw new Error("还有题目缺少题干或答案，请补全（勾选的第 "+(missing+1)+" 题）");
  if(importMode==="bank"){
   if(!confirm(`确认已核对这 ${questions.length} 道题的答案，并保存到教材题库？`))return;
   btn.disabled=true;btn.textContent="正在保存…";
   const saved=await api("/teacher/papers/import/save",{method:"POST",body:JSON.stringify({...importScope,title:"题库导入",questions,create_paper:false})});
   closeModal();toast("已保存 "+(saved.savedCount??questions.length)+" 道题到教材题库，单元：「"+(importScope.unit||"导入试卷")+"」"+(saved.reusedCount?"；另有 "+saved.reusedCount+" 道题库里已有，未重复保存":"")+(saved.typeSummary?"（"+saved.typeSummary+"）":""));go("catalog");return;
  }
  const title=$("#piTitle").value.trim();if(!title)throw new Error("请填写试卷名称");
  const classValue=$("#piClass").value;
  if(!confirm(`确认已核对这 ${questions.length} 道题的答案${classValue?"，并布置给所选班级":""}？`))return;
  btn.disabled=true;btn.textContent="正在保存…";
  const saved=await api("/teacher/papers/import/save",{method:"POST",body:JSON.stringify({...importScope,title,questions,class_id:classValue?+classValue:null,due_date:$("#piDue").value||""})});
  closeModal();go("papers");savedNotice(saved,title,questions.length);
 }catch(e){piError("未保存："+(e.message||"请重试"))}finally{if(document.body.contains(btn)){btn.disabled=false;btn.textContent=importMode==="bank"?"确认已核对，保存到题库":"确认保存"}}};
}
// 教材题库: change the 单元 / 教材 of the ticked questions (feedback #370: old imports sit under "导入试卷").
window.catalogPickAll=function(){const boxes=[...document.querySelectorAll("[data-qpick]")];const on=boxes.some(b=>!b.checked);boxes.forEach(b=>{b.checked=on})};
window.catalogEditUnit=function(reload){
 const ids=[...document.querySelectorAll("[data-qpick]:checked")].map(b=>+b.dataset.qpick);
 if(!ids.length){toast("请先勾选要修改的题目");return}
 modal("修改题目的单元",`<p>已选 <b>${ids.length}</b> 道题。只能修改你自己导入或创建的题目。</p>
 <label>单元（必填）</label><input id="euUnit" placeholder="例如：第三单元 小数除法">
 <label>教材（可选，不填则不改）</label><input id="euBook" placeholder="例如：人教版">
 ${piErrBox}<button class="btn primary full" id="euSave">保存修改</button>`);
 $("#euSave").onclick=async()=>{const btn=$("#euSave");if(btn.disabled)return;piError("");try{
  const unit=$("#euUnit").value.trim();if(!unit)throw new Error("请填写单元");
  const book=$("#euBook").value.trim();
  btn.disabled=true;btn.textContent="正在保存…";
  const r=await api("/teacher/questions/unit",{method:"POST",body:JSON.stringify({ids,unit,textbook:book||null})});
  closeModal();toast("已修改 "+r.updated+" 道题"+(r.skipped?"；"+r.skipped+" 道不是你创建的，未修改":""));if(reload)reload();
 }catch(e){piError("未修改："+(e.message||"请重试"))}finally{if(document.body.contains(btn)){btn.disabled=false;btn.textContent="保存修改"}}};
};
window.catalogAnswerBadge=function(q){
 const t=q.questionType||"single_choice",name=TYPE_NAMES[t]||t;
 if(t==="single_choice"||t==="true_false")return name+" · "+((q.options||[])[q.correctIndex]??"");
 if(t==="non_choice")return name+" · 教师评分";
 return name+" · "+(q.answer||"");
};
window.importPaperForm=function(classes,opts={}){
 importClasses=classes||[];importMode=opts.mode==="bank"?"bank":"paper";
 const bank=importMode==="bank";
 const grades=[1,2,3,4,5,6].map(g=>`<option value="${g}" ${g===5?"selected":""}>${g}年级</option>`).join("");
 modal(bank?"拍照 / 导入新增题目":"导入试卷 / 真题",`<p class="muted">${bank?"拍下练习册、试卷或板书上的题目（最多 4 张），也可以粘贴文字或上传 PDF/Word/文本。AI 自动识别题目和题型（单选、判断、填空、计算、简答、主观题），由你核对后保存到题库。":"粘贴试卷文字、上传 PDF/Word/文本（扫描版 PDF 最多 4 页），或拍照上传（最多 4 张）。拍照和扫描版会把题目插图一起裁下来。AI 逐题录入后由你核对，核对前不会保存。"}</p>
 <div class="form-grid"><div><label>年级</label><select id="piGrade">${grades}</select></div><div><label>学科</label><select id="piSubject"><option>数学</option><option>语文</option><option>英语</option><option>科学</option></select></div>
 <div><label>教材（必填）</label><input id="piTextbook" value="人教版" placeholder="例如：人教版"></div><div><label>学期</label><select id="piSemester"><option>上册</option><option>下册</option></select></div><div><label>单元（必填，题目按单元归入教材题库）</label><input id="piUnit" placeholder="例如：第二单元"></div>${bank?"":`<div><label>试卷名称</label><input id="piName" placeholder="例如：2025 期中真题"></div>`}</div>
 ${bank?`<label>拍照识别（最多 4 张）</label><input type="file" id="piPhotos" accept="image/*" multiple>`:""}
 <label>${bank?"或粘贴题目文字":"粘贴试卷文字"}</label><textarea id="piText" rows="${bank?5:8}" placeholder="${bank?"粘贴题目（含答案更好）":"把试卷内容（含答案更好）粘贴到这里"}"></textarea>
 <label>或上传文件（.pdf / .docx / .txt）</label><input type="file" id="piFile" accept=".pdf,.docx,.txt,application/pdf">
 ${bank?"":`<label>或拍照导入（最多 4 张）</label><input type="file" id="piPhotos" accept="image/*" multiple>`}
 ${piErrBox}
 <button class="btn primary full" id="piParse">${bank?"识别题目":"识别试卷"}</button>`);
 $("#piParse").onclick=async()=>{const btn=$("#piParse");if(btn.disabled)return;piError("");try{
  importScope={grade:+$("#piGrade").value,subject:$("#piSubject").value,textbook:$("#piTextbook").value.trim(),semester:$("#piSemester").value,unit:$("#piUnit").value.trim(),title:($("#piName")?.value||"").trim()};
  if(!importScope.textbook)throw new Error("请先填写教材（如：人教版）：布置作业时按教材和单元从题库取题");
  if(!importScope.unit)throw new Error("请先填写单元：导入的题目按单元归入教材题库");
  const body={...importScope,text:$("#piText").value};delete body.title;
  const file=$("#piFile").files?.[0];if(file){if(file.size>5*1024*1024)throw new Error("文件超过 5MB");body.file_name=file.name;body.file_base64=await readFileBase64(file)}
  const photos=[...($("#piPhotos").files||[])];if(photos.length>4)throw new Error("最多上传 4 张照片");
  body.images=[];for(const p of photos)body.images.push(await compressPhoto(p));
  if(!body.text.trim()&&!body.file_base64&&!body.images.length)throw new Error("请粘贴试卷文字、上传文件或拍照");
  btn.disabled=true;btn.textContent="AI 正在逐题录入，约需 1 分钟…";
  const result=await api("/teacher/papers/import/parse",{method:"POST",body:JSON.stringify(body)});
  if(!importScope.title)importScope.title=(importScope.unit||importScope.subject)+" 导入试卷";
  result.localImages=body.images;  // photos are numbered first, then PDF scans
  await cropFigures(result);
  reviewImport(result);
 }catch(e){piError("识别失败："+(e.message||"请重试"))}finally{if(document.body.contains(btn)){btn.disabled=false;btn.textContent=bank?"识别题目":"识别试卷"}}};
};
})();
</script>
"""


CATALOG_PHOTO_IMPORT_MARKER = "changying_catalog_photo_import_v1"


def patch_classic_catalog_photo_import(html: str) -> str:
    """教材题库: 拍照/导入新增题目 (feedback #337) and a type-aware answer badge."""

    if CATALOG_PHOTO_IMPORT_MARKER in html or PAPER_IMPORT_MARKER not in html:
        return html
    replacements = (
        (
            '?`<button class="btn primary" id="addQ">＋新增题目</button>`:""',
            '?`<button class="btn secondary" id="importQ" data-marker="' + CATALOG_PHOTO_IMPORT_MARKER + '">拍照/导入新增题目</button>'
            '<button class="btn primary" id="addQ">＋新增题目</button>`:""',
        ),
        (
            'if($("#addQ"))$("#addQ").onclick=()=>questionForm();',
            'if($("#addQ"))$("#addQ").onclick=()=>questionForm();'
            'if($("#importQ"))$("#importQ").onclick=()=>window.importPaperForm([],{mode:"bank"});',
        ),
        (
            '<span class="badge">${esc(q.options[q.correctIndex])}</span>',
            '<span class="badge">${esc(window.catalogAnswerBadge(q))}</span>',
        ),
    )
    for before, _ in replacements:
        if html.count(before) != 1:
            return html
    for before, after in replacements:
        html = html.replace(before, after, 1)
    return html


CATALOG_FIND_MARKER = "changying_catalog_find_imported_v1"


def patch_classic_catalog_find_imported(html: str) -> str:
    """教材题库: filter by 单元 and show the newest questions first, so an import is easy to find (feedback #370)."""

    if CATALOG_FIND_MARKER in html or CATALOG_PHOTO_IMPORT_MARKER not in html:
        return html
    replacements = (
        (
            '<input id="fSearch" placeholder="搜索知识点或题目">',
            '<select id="fUnit" data-marker="' + CATALOG_FIND_MARKER + '"><option value="">全部单元</option>'
            '${[...new Set(qs.map(q=>q.unit))].map(x=>`<option>${esc(x)}</option>`).join("")}</select>'
            '<input id="fSearch" placeholder="搜索知识点或题目">',
        ),
        (
            'k=$("#fSearch").value.trim();',
            'k=$("#fSearch").value.trim(),un=$("#fUnit").value;',
        ),
        (
            '(!s||q.subject===s)&&(!b||q.textbook===b)&&(!k||',
            '(!s||q.subject===s)&&(!b||q.textbook===b)&&(!un||q.unit===un)&&(!k||',
        ),
        (
            'q.unit.includes(k)));',
            'q.unit.includes(k))).reverse();',
        ),
        (
            '["#fGrade","#fSubject","#fBook","#fSearch"]',
            '["#fGrade","#fSubject","#fBook","#fUnit","#fSearch"]',
        ),
    )
    for before, _ in replacements:
        if html.count(before) != 1:
            return html
    for before, after in replacements:
        html = html.replace(before, after, 1)
    return html


CATALOG_EDIT_UNIT_MARKER = "changying_catalog_edit_unit_v1"


def patch_classic_catalog_edit_unit(html: str) -> str:
    """教材题库: tick questions and change their 单元 / 教材 (feedback #370)."""

    if CATALOG_EDIT_UNIT_MARKER in html or CATALOG_PHOTO_IMPORT_MARKER not in html:
        return html
    replacements = (
        (
            '拍照/导入新增题目</button>',
            '拍照/导入新增题目</button><button class="btn secondary" id="pickAllQ">全选/取消</button>'
            '<button class="btn secondary" id="editUnitQ" data-marker="' + CATALOG_EDIT_UNIT_MARKER + '">修改选中题目的单元</button>',
        ),
        (
            '<div class="item"><div class="item-main"><b>${esc(q.text)}</b>',
            '<div class="item"><input type="checkbox" data-qpick="${q.id}" aria-label="选择题目" style="margin:0 10px 0 0;flex:none">'
            '<div class="item-main"><b>${esc(q.text)}</b>',
        ),
        (
            'if($("#importQ"))$("#importQ").onclick=()=>window.importPaperForm([],{mode:"bank"});',
            'if($("#importQ"))$("#importQ").onclick=()=>window.importPaperForm([],{mode:"bank"});'
            'if($("#pickAllQ"))$("#pickAllQ").onclick=()=>window.catalogPickAll();'
            'if($("#editUnitQ"))$("#editUnitQ").onclick=()=>window.catalogEditUnit(()=>go("catalog"));',
        ),
    )
    for before, _ in replacements:
        if html.count(before) != 1:
            return html
    for before, after in replacements:
        html = html.replace(before, after, 1)
    return html


def patch_classic_paper_import(html: str) -> str:
    if PAPER_IMPORT_MARKER in html:
        return html
    replacements = (
        (
            '<button class="btn primary" id="newAssignment">＋布置作业</button>',
            '<button class="btn secondary" id="importPaper">导入试卷</button><button class="btn primary" id="newAssignment">＋布置作业</button>',
        ),
        (
            ' $("#newAssignment").onclick=()=>assignmentForm(cs);',
            ' $("#newAssignment").onclick=()=>assignmentForm(cs);$("#importPaper").onclick=()=>window.importPaperForm(cs);',
        ),
    )
    for before, after in replacements:
        if html.count(before) != 1:
            return html
    for before, after in replacements:
        html = html.replace(before, after, 1)
    if "</body>" in html:
        return html.replace("</body>", PAPER_IMPORT_SCRIPT + "\n</body>", 1)
    return html + PAPER_IMPORT_SCRIPT
