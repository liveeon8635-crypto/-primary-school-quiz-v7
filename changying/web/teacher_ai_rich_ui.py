"""Teacher AI rich-question review UI patch."""

from __future__ import annotations

from types import ModuleType


TEACHER_AI_RICH_UI_MARKER = "changying_teacher_ai_rich_ui_v1"


def patch_teacher_ai_rich_ui(html: str) -> str:
    if TEACHER_AI_RICH_UI_MARKER in html:
        return html

    old_select = '<select id="aqType"><option value="auto">自动识别要求</option><option value="choice">选择题</option><option value="non_choice">非选择题</option><option value="mixed">混合题型</option></select>'
    new_select = '<select id="aqType"><option value="auto">自动混合（推荐）</option><option value="mixed">混合在线题型</option><option value="single_choice">单选题</option><option value="true_false">判断题</option><option value="fill_blank">填空题</option><option value="calculation">计算题</option><option value="short_answer">简短应用/作答题</option><option value="non_choice">教师审核主观题（拍照）</option></select>'
    if old_select not in html:
        raise RuntimeError("teacher AI rich UI patch: question type selector not found")
    html = html.replace(old_select, new_select, 1)

    script = r'''
<script id="changying_teacher_ai_rich_ui_v1-script">
(()=>{
 if(window.__cyTeacherAIRichUIInstalled)return;
 window.__cyTeacherAIRichUIInstalled=true;
 const typeName=q=>({
  choice:'单选题',single_choice:'单选题',true_false:'判断题',fill_blank:'填空题',
  calculation:'计算题',short_answer:'简短应用/作答题',non_choice:'教师审核主观题'
 })[String(q?.question_type||'').toLowerCase()]||'题目';
 const choiceLike=q=>['choice','single_choice','true_false'].includes(String(q?.question_type||'').toLowerCase());

 window.aiQuestionNonChoice=q=>{
  const t=String(q?.question_type||'').toLowerCase();
  if(t)return t==='non_choice';
  return ((q?.options||[]).length===0&&+q?.correct_index<0);
 };

 window.aiQuestionCopyText=(q,i)=>{
  const head=`${i+1}. ${q.text||''}`;
  if(aiQuestionNonChoice(q)){
   const pts=(q.scoring_points||[]).length?`\n评分要点：${q.scoring_points.join('；')}`:'';
   return `${head}\n参考答案：${q.reference_answer||''}${pts}${q.explanation?`\n解析：${q.explanation}`:''}`;
  }
  if(choiceLike(q)){
   return `${head}\n${(q.options||[]).map((x,j)=>`${String.fromCharCode(65+j)}. ${x}`).join('\n')}\n答案：${String.fromCharCode(65+(+q.correct_index||0))}${q.explanation?`\n解析：${q.explanation}`:''}`;
  }
  const accepted=(q.accepted_answers||[]).length?`\n可接受答案：${q.accepted_answers.join(' / ')}`:'';
  return `${head}\n标准答案：${q.answer||''}${accepted}${q.explanation?`\n解析：${q.explanation}`:''}`;
 };

 function editRichQuestion(i){
  const q=aiGeneratedQuestions[i],manual=aiQuestionNonChoice(q),choice=choiceLike(q),label=typeName(q);
  if(manual){
   modal(`编辑第 ${i+1} 题（${label}）`,`<label>题干</label><textarea id="aeText">${esc(q.text)}</textarea><label>参考答案</label><textarea id="aeRef">${esc(q.reference_answer||'')}</textarea><label>评分要点（每行一条）</label><textarea id="aePoints">${esc((q.scoring_points||[]).join('\n'))}</textarea><label>知识点</label><input id="aeKnowledge" value="${esc(q.knowledge||'')}"><label>解析</label><textarea id="aeExplain">${esc(q.explanation||'')}</textarea><button class="btn primary full" id="saveAIQuestionEdit">保存修改</button>`);
   $('#saveAIQuestionEdit').onclick=()=>{
    const text=$('#aeText').value.trim(),ref=$('#aeRef').value.trim(),points=$('#aePoints').value.split(/\n+/).map(x=>x.trim()).filter(Boolean);
    if(!text||!ref||!points.length){toast('题干、参考答案和评分要点不能为空');return}
    aiGeneratedQuestions[i]={...q,question_type:'non_choice',text,options:[],correct_index:-1,answer:'',accepted_answers:[],reference_answer:ref,scoring_points:points,knowledge:$('#aeKnowledge').value.trim()||'AI生成',explanation:$('#aeExplain').value.trim()};
    closeModal();renderAIQuestionDrafts();toast('题目已修改');
   };
   return;
  }
  if(choice){
   const tf=String(q.question_type||'').toLowerCase()==='true_false',opts=tf?['正确','错误']:(q.options||[]);
   modal(`编辑第 ${i+1} 题（${label}）`,`<label>题干</label><textarea id="aeText">${esc(q.text)}</textarea><div class="form-grid">${tf?'':opts.map((x,j)=>`<div><label>选项 ${String.fromCharCode(65+j)}</label><input id="aeOpt${j}" value="${esc(x)}"></div>`).join('')}<div><label>正确答案</label><select id="aeCorrect">${opts.map((x,j)=>`<option value="${j}" ${j===q.correct_index?'selected':''}>${tf?esc(x):String.fromCharCode(65+j)}</option>`).join('')}</select></div><div><label>知识点</label><input id="aeKnowledge" value="${esc(q.knowledge||'')}"></div></div><label>解析</label><textarea id="aeExplain">${esc(q.explanation||'')}</textarea><button class="btn primary full" id="saveAIQuestionEdit">保存修改</button>`);
   $('#saveAIQuestionEdit').onclick=()=>{
    const text=$('#aeText').value.trim(),newOpts=tf?['正确','错误']:[0,1,2,3].map(j=>$('#aeOpt'+j).value.trim());
    if(!text||newOpts.some(x=>!x)){toast('题干和选项不能为空');return}
    aiGeneratedQuestions[i]={...q,question_type:tf?'true_false':'single_choice',text,options:newOpts,correct_index:+$('#aeCorrect').value,answer:'',accepted_answers:[],reference_answer:'',scoring_points:[],knowledge:$('#aeKnowledge').value.trim()||'AI生成',explanation:$('#aeExplain').value.trim()};
    closeModal();renderAIQuestionDrafts();toast('题目已修改');
   };
   return;
  }
  modal(`编辑第 ${i+1} 题（${label}）`,`<label>题干</label><textarea id="aeText">${esc(q.text)}</textarea><label>标准答案</label><input id="aeAnswer" value="${esc(q.answer||'')}"><label>可接受等价答案（每行一条）</label><textarea id="aeAccepted">${esc((q.accepted_answers||[]).join('\n'))}</textarea><label>知识点</label><input id="aeKnowledge" value="${esc(q.knowledge||'')}"><label>解析</label><textarea id="aeExplain">${esc(q.explanation||'')}</textarea><div class="note">当前图示会原样保留；如图示有误，请取消勾选后重新生成该题。</div><button class="btn primary full" id="saveAIQuestionEdit">保存修改</button>`);
  $('#saveAIQuestionEdit').onclick=()=>{
   const text=$('#aeText').value.trim(),answer=$('#aeAnswer').value.trim();
   if(!text||!answer){toast('题干和标准答案不能为空');return}
   aiGeneratedQuestions[i]={...q,text,options:[],correct_index:-1,answer,accepted_answers:$('#aeAccepted').value.split(/\n+/).map(x=>x.trim()).filter(Boolean),reference_answer:'',scoring_points:[],knowledge:$('#aeKnowledge').value.trim()||'AI生成',explanation:$('#aeExplain').value.trim()};
   closeModal();renderAIQuestionDrafts();toast('题目已修改');
  };
 }

 window.renderAIQuestionDrafts=()=>{
  const isTeacher=state.user?.role==='teacher',hasManual=aiGeneratedQuestions.some(aiQuestionNonChoice);
  const cards=aiGeneratedQuestions.map((q,i)=>{
   const manual=aiQuestionNonChoice(q),choice=choiceLike(q),fig=renderQuestionFigure(q.figure||{}),label=typeName(q);
   let answer='';
   if(manual)answer=`<div class="answer"><b>参考答案：</b>${esc(q.reference_answer||'')}${(q.scoring_points||[]).length?`<br><b>评分要点：</b>${(q.scoring_points||[]).map(esc).join('；')}`:''}</div>`;
   else if(choice)answer=`<div class="opts">${(q.options||[]).map((x,j)=>`<span class="${j===q.correct_index?'correct':''}">${String.fromCharCode(65+j)}. ${esc(x)}${j===q.correct_index?' ✓':''}</span>`).join('')}</div>`;
   else answer=`<div class="answer"><b>标准答案：</b>${esc(q.answer||'')}${(q.accepted_answers||[]).length?`<br><span class="muted">可接受：${esc(q.accepted_answers.join(' / '))}</span>`:''}</div>`;
   return `<div class="ai-question-card"><div class="actions" style="justify-content:space-between;align-items:flex-start"><label style="display:flex;gap:8px;align-items:flex-start;flex:1"><input class="ai-q-pick" data-i="${i}" type="checkbox" checked style="width:auto;margin-top:3px"><div><span class="badge ${manual?'amber':''}">${esc(label)}</span><b style="display:block;margin-top:6px">${i+1}. ${esc(q.text)}</b></div></label><button class="btn secondary small aiEditQuestion" data-i="${i}">编辑</button></div>${fig}${answer}<small class="muted">知识点：${esc(q.knowledge||'')}${q.explanation?` · 解析：${esc(q.explanation)}`:''}</small></div>`;
  }).join('');

  $('#aiOutput').innerHTML=`<div class="card"><div class="actions" style="justify-content:space-between;align-items:center"><h2 style="margin:0">AI题目审核工作台（${aiGeneratedQuestions.length}题）</h2><div class="actions"><button class="btn secondary small" id="aiSelectAll">全选</button><button class="btn secondary small" id="aiSelectNone">全不选</button></div></div><div class="ai-warning">${esc(aiQuestionNotice||'AI生成内容必须由教师审核后再保存或发布。')}${hasManual?'<br>仅“教师审核主观题”会切换为拍照/视频提交；判断、填空、计算和简短应用题仍在线作答并由服务器判分。':''}</div><div class="actions" style="margin:10px 0"><button class="btn secondary" id="copySelectedAIQuestions">复制选中题目</button><button class="btn secondary" id="saveSelectedAIQuestions">保存选中到题库</button>${isTeacher?'<button class="btn primary" id="assignSelectedAIQuestions">选中题目直接布置作业</button>':''}</div><div class="list section">${cards}</div></div>`;

  $('#aiSelectAll').onclick=()=>document.querySelectorAll('.ai-q-pick').forEach(x=>x.checked=true);
  $('#aiSelectNone').onclick=()=>document.querySelectorAll('.ai-q-pick').forEach(x=>x.checked=false);
  $('#copySelectedAIQuestions').onclick=()=>{const rows=aiSelectedQuestionRows();if(!rows.length){toast('请至少勾选1道题');return}aiCopy(rows.map((q,i)=>aiQuestionCopyText(q,i)).join('\n\n'))};
  $$('.aiEditQuestion').forEach(btn=>btn.onclick=()=>editRichQuestion(+btn.dataset.i));
  $('#saveSelectedAIQuestions').onclick=async()=>{const rows=aiSelectedQuestionRows();if(!rows.length){toast('请至少勾选1道题');return}if(!confirm(`确认已人工审核选中的 ${rows.length} 道题，并保存到题库？`))return;try{const d=await api('/ai/questions/save',{method:'POST',body:JSON.stringify({questions:rows})});toast(`已保存 ${d.items?.length||rows.length} 道到题库`)}catch(e){toast(e.message)}};

  if(isTeacher)$('#assignSelectedAIQuestions').onclick=async()=>{
   const rows=aiSelectedQuestionRows();if(!rows.length){toast('请至少勾选1道题');return}
   try{
    const classes=await api('/teacher/classes');if(!classes.length){toast('请先建立班级');return}
    const first=rows[0],manual=rows.some(aiQuestionNonChoice),defaultTitle=`${first.subject||''} ${first.unit||first.knowledge||'AI练习'}`.trim();
    modal('AI题目直接布置作业',`<div class="note">选中的 ${rows.length} 道题会保存到题库并生成试卷。${manual?'含教师审核主观题，整份作业将使用拍照/视频提交。':'判断、填空、计算等标准题型均可在线完成并由服务器判分。'}</div><label>作业名称</label><input id="aqaTitle" value="${esc(defaultTitle)}"><div class="form-grid"><div><label>班级</label><select id="aqaClass">${classes.map(c=>`<option value="${c.id}">${esc(c.name)} · ${c.grade}年级 · ${c.studentCount||0}人</option>`).join('')}</select></div><div><label>截止日期</label><input id="aqaDue" type="date" value="${new Date(Date.now()+7*86400000).toISOString().slice(0,10)}"></div></div><label>作业要求（可选）</label><textarea id="aqaInstructions" placeholder="${manual?'例如：写清思考过程，完成后拍照上传。':'例如：认真审题，完成后检查。'}"></textarea><button class="btn primary full" id="confirmAIAssignment">一键生成试卷并布置</button>`);
    $('#confirmAIAssignment').onclick=async()=>{
     const b=$('#confirmAIAssignment');b.disabled=true;b.textContent='正在布置…';
     try{
      const d=await api('/ai/questions/assign',{method:'POST',body:JSON.stringify({questions:rows,title:$('#aqaTitle').value.trim()||defaultTitle,class_id:+$('#aqaClass').value,due_date:$('#aqaDue').value,instructions:$('#aqaInstructions').value.trim()})});
      closeModal();toast(d.submissionMode==='media'?`教师审核主观题作业已布置，接收 ${d.recipientCount||0} 人`:`在线多题型作业已布置，接收 ${d.recipientCount||0} 人`);go('papers');
     }catch(e){b.disabled=false;b.textContent='一键生成试卷并布置';toast(e.message)}
    };
   }catch(e){toast(e.message)}
  };
 };
})();
</script>
'''
    if "</body>" not in html:
        raise RuntimeError("teacher AI rich UI patch: closing body marker not found")
    return html.replace(
        "</body>",
        script + f"\n<!-- {TEACHER_AI_RICH_UI_MARKER} --></body>",
        1,
    )


def install_teacher_ai_rich_ui(implementation: ModuleType) -> None:
    if getattr(implementation.app.state, "teacher_ai_rich_ui_installed", False):
        return
    implementation.INDEX_HTML = patch_teacher_ai_rich_ui(implementation.INDEX_HTML)
    implementation.app.state.teacher_ai_rich_ui_installed = True


__all__ = [
    "TEACHER_AI_RICH_UI_MARKER",
    "install_teacher_ai_rich_ui",
    "patch_teacher_ai_rich_ui",
]
