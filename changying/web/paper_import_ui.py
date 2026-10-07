"""Classic 组卷与作业 page: 导入试卷 (past paper / 真题 import).

Adds an 导入试卷 button next to ＋布置作业. Flow: choose source (paste text,
.txt/.docx/.pdf, or up to four photos) -> AI transcription -> teacher reviews
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
let importItems=[],importScope={},importClasses=[];
const readFileBase64=file=>new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result||"").split(",")[1]||"");r.onerror=()=>reject(new Error("文件读取失败"));r.readAsDataURL(file)});
const compressPhoto=file=>new Promise((resolve,reject)=>{const url=URL.createObjectURL(file),img=new Image();img.onload=()=>{try{const scale=Math.min(1,1800/Math.max(img.naturalWidth,img.naturalHeight));const c=document.createElement("canvas");c.width=Math.round(img.naturalWidth*scale);c.height=Math.round(img.naturalHeight*scale);c.getContext("2d").drawImage(img,0,0,c.width,c.height);let data=c.toDataURL("image/jpeg",0.8);for(let q=0.7;data.length>1900000&&q>=0.4;q-=0.1)data=c.toDataURL("image/jpeg",q);if(data.length>1900000)throw new Error("照片太大，请裁剪后重试");resolve(data)}catch(e){reject(e)}finally{URL.revokeObjectURL(url)}};img.onerror=()=>{URL.revokeObjectURL(url);reject(new Error("无法读取这张照片"))};img.src=url});
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
  const out={...q,text:v(`[data-pi-text="${i}"]`).trim()};
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
 <label>题干</label><textarea data-pi-text="${i}">${esc(q.text)}</textarea>${answerEditor(q,i)}<small class="muted">知识点：${esc(q.knowledge||"")}</small></div>`).join("")}</div>
 <label>试卷名称</label><input id="piTitle" value="${esc(importScope.title||"")}">
 <div class="form-grid"><div><label>布置给班级（可选）</label><select id="piClass"><option value="">只保存为试卷，暂不布置</option>${classOptions}</select></div><div><label>截止日期</label><input type="date" id="piDue"></div></div>
 <small class="muted">含主观题的试卷会改为拍照提交、教师评分；其余题型在线自动判分。</small>
 <button class="btn primary full" id="piSave">确认已核对，保存</button>`);
 $("#piSave").onclick=async()=>{const btn=$("#piSave");if(btn.disabled)return;try{
  const questions=collectEdits();if(!questions.length)throw new Error("请至少勾选 1 道题");
  const missing=questions.findIndex(q=>(["single_choice","true_false"].includes(q.question_type)&&!(q.correct_index>=0))||(["fill_blank","calculation","short_answer"].includes(q.question_type)&&!q.answer)||(q.question_type==="non_choice"&&!q.reference_answer)||!q.text);
  if(missing>=0)throw new Error("还有题目缺少题干或答案，请补全（勾选的第 "+(missing+1)+" 题）");
  const title=$("#piTitle").value.trim();if(!title)throw new Error("请填写试卷名称");
  const classValue=$("#piClass").value;
  if(!confirm(`确认已核对这 ${questions.length} 道题的答案${classValue?"，并布置给所选班级":""}？`))return;
  btn.disabled=true;btn.textContent="正在保存…";
  const saved=await api("/teacher/papers/import/save",{method:"POST",body:JSON.stringify({...importScope,title,questions,class_id:classValue?+classValue:null,due_date:$("#piDue").value||""})});
  closeModal();toast((saved.assignment?"试卷已导入并布置":"试卷已导入")+(saved.typeSummary?"（"+saved.typeSummary+"）":""));go("papers");
 }catch(e){toast("未保存："+(e.message||"请重试"))}finally{if(document.body.contains(btn)){btn.disabled=false;btn.textContent="确认已核对，保存"}}};
}
window.importPaperForm=function(classes){
 importClasses=classes||[];
 const grades=[1,2,3,4,5,6].map(g=>`<option value="${g}" ${g===5?"selected":""}>${g}年级</option>`).join("");
 modal("导入试卷 / 真题",`<p class="muted">粘贴试卷文字、上传 Word/PDF/文本，或拍照上传（最多 4 张）。AI 逐题录入后由你核对，核对前不会保存。</p>
 <div class="form-grid"><div><label>年级</label><select id="piGrade">${grades}</select></div><div><label>学科</label><select id="piSubject"><option>数学</option><option>语文</option><option>英语</option><option>科学</option></select></div>
 <div><label>教材</label><input id="piTextbook" placeholder="例如：人教版"></div><div><label>学期</label><select id="piSemester"><option>上册</option><option>下册</option></select></div><div><label>单元（可选）</label><input id="piUnit" placeholder="例如：第二单元"></div><div><label>试卷名称</label><input id="piName" placeholder="例如：2025 期中真题"></div></div>
 <label>粘贴试卷文字</label><textarea id="piText" rows="8" placeholder="把试卷内容（含答案更好）粘贴到这里"></textarea>
 <label>或上传文件（.docx / .pdf / .txt）</label><input type="file" id="piFile" accept=".docx,.pdf,.txt">
 <label>或拍照导入（最多 4 张）</label><input type="file" id="piPhotos" accept="image/*" multiple>
 <button class="btn primary full" id="piParse">识别试卷</button>`);
 $("#piParse").onclick=async()=>{const btn=$("#piParse");if(btn.disabled)return;try{
  importScope={grade:+$("#piGrade").value,subject:$("#piSubject").value,textbook:$("#piTextbook").value.trim(),semester:$("#piSemester").value,unit:$("#piUnit").value.trim(),title:$("#piName").value.trim()};
  const body={...importScope,text:$("#piText").value};delete body.title;
  const file=$("#piFile").files?.[0];if(file){if(file.size>5*1024*1024)throw new Error("文件超过 5MB");body.file_name=file.name;body.file_base64=await readFileBase64(file)}
  const photos=[...($("#piPhotos").files||[])];if(photos.length>4)throw new Error("最多上传 4 张照片");
  body.images=[];for(const p of photos)body.images.push(await compressPhoto(p));
  if(!body.text.trim()&&!body.file_base64&&!body.images.length)throw new Error("请粘贴试卷文字、上传文件或拍照");
  btn.disabled=true;btn.textContent="AI 正在逐题录入，约需 1 分钟…";
  const result=await api("/teacher/papers/import/parse",{method:"POST",body:JSON.stringify(body)});
  if(!importScope.title)importScope.title=(importScope.unit||importScope.subject)+" 导入试卷";
  reviewImport(result);
 }catch(e){toast("识别失败："+(e.message||"请重试"))}finally{if(document.body.contains(btn)){btn.disabled=false;btn.textContent="识别试卷"}}};
};
})();
</script>
"""


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
