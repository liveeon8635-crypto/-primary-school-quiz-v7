"""Teacher AI rich-question review UI patch."""

from __future__ import annotations

from types import ModuleType

RICH_GENERATION_MARKER = "changying_teacher_ai_rich_generation_v1"

_RICH_UI_SCRIPT = r'''
<script id="changying_teacher_ai_rich_generation_v1-script">
(()=>{
 if(window.__cyTeacherAIRichGenerationInstalled)return;
 window.__cyTeacherAIRichGenerationInstalled=true;

 function syncTypeSelector(){
  const el=document.getElementById('aqType'),subject=document.getElementById('aqSubject');
  if(!el)return;
  const previous=el.value||'auto',isMath=String(subject?.value||'').includes('数学');
  const signature=isMath?'math':'nonmath';
  if(el.dataset.richTypes===signature)return;
  const rows=[
   ['auto','自动选择合适题型'],['mixed','混合在线题型'],['single_choice','单选题'],
   ['true_false','判断题'],['fill_blank','填空题']
  ];
  if(isMath)rows.push(['calculation','计算题'],['short_answer','简短应用题']);
  rows.push(['non_choice','教师审核主观题']);
  el.innerHTML=rows.map(([v,n])=>'<option value="'+v+'">'+n+'</option>').join('');
  el.value=rows.some(x=>x[0]===previous)?previous:'auto';
  el.dataset.richTypes=signature;
 }
 document.addEventListener('change',event=>{if(event.target?.id==='aqSubject'){const el=document.getElementById('aqType');if(el)el.dataset.richTypes='';syncTypeSelector()}});
 new MutationObserver(syncTypeSelector).observe(document.documentElement,{childList:true,subtree:true});
 setTimeout(syncTypeSelector,0);

 aiQuestionNonChoice=function(q){return String(q?.question_type||'').toLowerCase()==='non_choice'};
 function aiChoiceLike(q){return ['single_choice','choice','true_false'].includes(String(q?.question_type||'').toLowerCase())}
 function aiTextAuto(q){return ['fill_blank','calculation','short_answer'].includes(String(q?.question_type||'').toLowerCase())}
 function aiTypeLabel(q){return aiQuestionNonChoice(q)?'教师审核主观题':questionTypeName(q?.question_type)}

 aiQuestionCopyText=function(q,i){
  const head=(i+1)+'. '+(q.text||'');
  if(aiQuestionNonChoice(q)){
   const pts=(q.scoring_points||[]).length?'\n评分要点：'+q.scoring_points.join('；'):'';
   return head+'\n参考答案：'+(q.reference_answer||'')+pts+(q.explanation?'\n解析：'+q.explanation:'');
  }
  if(aiTextAuto(q)){
   const accepted=(q.accepted_answers||[]).length?'\n等价答案：'+q.accepted_answers.join('；'):'';
   return head+'\n答案：'+(q.answer||'')+accepted+(q.explanation?'\n解析：'+q.explanation:'');
  }
  return head+'\n'+(q.options||[]).map((x,j)=>String.fromCharCode(65+j)+'. '+x).join('\n')+
   '\n答案：'+String.fromCharCode(65+(+q.correct_index||0))+(q.explanation?'\n解析：'+q.explanation:'');
 };

 renderAIQuestionDrafts=function(){
  const isTeacher=state.user?.role==='teacher',hasManual=aiGeneratedQuestions.some(aiQuestionNonChoice);
  $('#aiOutput').innerHTML='<div class="card"><div class="actions" style="justify-content:space-between;align-items:center">'+
   '<h2 style="margin:0">AI题目审核工作台（'+aiGeneratedQuestions.length+'题）</h2>'+
   '<div class="actions"><button class="btn secondary small" id="aiSelectAll">全选</button><button class="btn secondary small" id="aiSelectNone">全不选</button></div></div>'+
   '<div class="ai-warning">'+esc(aiQuestionNotice||'AI生成内容必须由教师审核后再保存或发布。')+
   (hasManual?'<br>只有“教师审核主观题”会走拍照/教师确认；填空、计算和简短应用题仍是在线作答。':'')+'</div>'+
   '<div class="actions" style="margin:10px 0"><button class="btn secondary" id="copySelectedAIQuestions">复制选中题目</button>'+
   '<button class="btn secondary" id="saveSelectedAIQuestions">保存选中到题库</button>'+
   (isTeacher?'<button class="btn primary" id="assignSelectedAIQuestions">选中题目直接布置作业</button>':'')+'</div>'+
   '<div class="list section">'+aiGeneratedQuestions.map((q,i)=>{
    const manual=aiQuestionNonChoice(q),textAuto=aiTextAuto(q),choiceLike=aiChoiceLike(q);
    const answer=manual
      ?'<div class="answer"><b>参考答案：</b>'+esc(q.reference_answer||'')+((q.scoring_points||[]).length?'<br><b>评分要点：</b>'+q.scoring_points.map(esc).join('；'):'')+'</div>'
      :textAuto
        ?'<div class="answer"><b>标准答案：</b>'+esc(q.answer||'')+((q.accepted_answers||[]).length?'<br><b>等价答案：</b>'+q.accepted_answers.map(esc).join('；'):'')+'</div>'
        :'<div class="opts">'+(q.options||[]).map((x,j)=>'<span class="'+(j===q.correct_index?'correct':'')+'">'+String.fromCharCode(65+j)+'. '+esc(x)+(j===q.correct_index?' ✓':'')+'</span>').join('')+'</div>';
    return '<div class="ai-question-card"><div class="actions" style="justify-content:space-between;align-items:flex-start">'+
     '<label style="display:flex;gap:8px;align-items:flex-start;flex:1"><input class="ai-q-pick" data-i="'+i+'" type="checkbox" checked style="width:auto;margin-top:3px">'+
     '<div><span class="badge '+(manual?'amber':'')+'">'+esc(aiTypeLabel(q))+'</span><b style="display:block;margin-top:6px">'+(i+1)+'. '+esc(q.text)+'</b></div></label>'+
     '<button class="btn secondary small aiEditQuestion" data-i="'+i+'">编辑</button></div>'+renderQuestionFigure(q.figure||{})+answer+
     '<small class="muted">知识点：'+esc(q.knowledge||'')+(q.explanation?' · 解析：'+esc(q.explanation):'')+'</small></div>';
   }).join('')+'</div></div>';

  $('#aiSelectAll').onclick=()=>document.querySelectorAll('.ai-q-pick').forEach(x=>x.checked=true);
  $('#aiSelectNone').onclick=()=>document.querySelectorAll('.ai-q-pick').forEach(x=>x.checked=false);
  $('#copySelectedAIQuestions').onclick=()=>{
   const rows=aiSelectedQuestionRows();if(!rows.length){toast('请至少勾选1道题');return}
   aiCopy(rows.map((q,i)=>aiQuestionCopyText(q,i)).join('\n\n'));
  };

  $$('.aiEditQuestion').forEach(btn=>btn.onclick=()=>{
   const i=+btn.dataset.i,q=aiGeneratedQuestions[i],manual=aiQuestionNonChoice(q),textAuto=aiTextAuto(q),type=String(q.question_type||'single_choice');
   if(manual){
    modal('编辑第 '+(i+1)+' 题（教师审核主观题）',
     '<label>题干</label><textarea id="aeText">'+esc(q.text)+'</textarea><label>参考答案</label><textarea id="aeRef">'+esc(q.reference_answer||'')+
     '</textarea><label>评分要点（每行一条）</label><textarea id="aePoints">'+esc((q.scoring_points||[]).join('\n'))+
     '</textarea><label>知识点</label><input id="aeKnowledge" value="'+esc(q.knowledge||'')+'"><label>解析</label><textarea id="aeExplain">'+esc(q.explanation||'')+
     '</textarea><button class="btn primary full" id="saveAIQuestionEdit">保存修改</button>');
    $('#saveAIQuestionEdit').onclick=()=>{
     const t=$('#aeText').value.trim(),a=$('#aeRef').value.trim();if(!t||!a){toast('题干和参考答案不能为空');return}
     aiGeneratedQuestions[i]={...q,question_type:'non_choice',text:t,options:[],correct_index:-1,answer:'',accepted_answers:[],
      reference_answer:a,scoring_points:$('#aePoints').value.split(/\n+/).map(x=>x.trim()).filter(Boolean),
      knowledge:$('#aeKnowledge').value.trim()||'AI生成',explanation:$('#aeExplain').value.trim()};
     closeModal();renderAIQuestionDrafts();toast('题目已修改');
    };
   }else if(textAuto){
    modal('编辑第 '+(i+1)+' 题（'+aiTypeLabel(q)+'）',
     '<label>题干</label><textarea id="aeText">'+esc(q.text)+'</textarea><label>标准答案</label><input id="aeAnswer" value="'+esc(q.answer||'')+
     '"><label>等价答案（每行一条）</label><textarea id="aeAccepted">'+esc((q.accepted_answers||[]).join('\n'))+
     '</textarea><label>知识点</label><input id="aeKnowledge" value="'+esc(q.knowledge||'')+'"><label>解析</label><textarea id="aeExplain">'+esc(q.explanation||'')+
     '</textarea><button class="btn primary full" id="saveAIQuestionEdit">保存修改</button>');
    $('#saveAIQuestionEdit').onclick=()=>{
     const t=$('#aeText').value.trim(),a=$('#aeAnswer').value.trim();if(!t||!a){toast('题干和标准答案不能为空');return}
     aiGeneratedQuestions[i]={...q,question_type:type,text:t,options:[],correct_index:-1,answer:a,
      accepted_answers:$('#aeAccepted').value.split(/\n+/).map(x=>x.trim()).filter(Boolean),reference_answer:'',scoring_points:[],
      knowledge:$('#aeKnowledge').value.trim()||'AI生成',explanation:$('#aeExplain').value.trim()};
     closeModal();renderAIQuestionDrafts();toast('题目已修改');
    };
   }else{
    const opts=(q.options||[]);
    modal('编辑第 '+(i+1)+' 题（'+aiTypeLabel(q)+'）',
     '<label>题干</label><textarea id="aeText">'+esc(q.text)+'</textarea><div class="form-grid">'+opts.map((x,j)=>'<div><label>选项 '+String.fromCharCode(65+j)+'</label><input id="aeOpt'+j+'" value="'+esc(x)+'"></div>').join('')+
     '<div><label>正确答案</label><select id="aeCorrect">'+opts.map((_,j)=>'<option value="'+j+'" '+(j===q.correct_index?'selected':'')+'>'+String.fromCharCode(65+j)+'</option>').join('')+
     '</select></div><div><label>知识点</label><input id="aeKnowledge" value="'+esc(q.knowledge||'')+'"></div></div><label>解析</label><textarea id="aeExplain">'+esc(q.explanation||'')+
     '</textarea><button class="btn primary full" id="saveAIQuestionEdit">保存修改</button>');
    $('#saveAIQuestionEdit').onclick=()=>{
     const t=$('#aeText').value.trim(),newOpts=opts.map((_,j)=>$('#aeOpt'+j).value.trim());
     if(!t||newOpts.some(x=>!x)){toast('题干和选项不能为空');return}
     aiGeneratedQuestions[i]={...q,question_type:type==='choice'?'single_choice':type,text:t,options:newOpts,
      correct_index:+$('#aeCorrect').value,answer:'',accepted_answers:[],reference_answer:'',scoring_points:[],
      knowledge:$('#aeKnowledge').value.trim()||'AI生成',explanation:$('#aeExplain').value.trim()};
     closeModal();renderAIQuestionDrafts();toast('题目已修改');
    };
   }
  });

  $('#saveSelectedAIQuestions').onclick=async()=>{
   const rows=aiSelectedQuestionRows();if(!rows.length){toast('请至少勾选1道题');return}
   if(!confirm('确认已人工审核选中的 '+rows.length+' 道题，并保存到题库？'))return;
   try{const d=await api('/ai/questions/save',{method:'POST',body:JSON.stringify({questions:rows})});toast('已保存 '+(d.items?.length||rows.length)+' 道到题库')}catch(e){toast(e.message)}
  };

  if(isTeacher)$('#assignSelectedAIQuestions').onclick=async()=>{
   const rows=aiSelectedQuestionRows();if(!rows.length){toast('请至少勾选1道题');return}
   try{
    const classes=await api('/teacher/classes');if(!classes.length){toast('请先建立班级');return}
    const first=rows[0],manual=rows.some(aiQuestionNonChoice),defaultTitle=((first.subject||'')+' '+(first.unit||first.knowledge||'AI练习')).trim();
    modal('AI题目直接布置作业',
     '<div class="note">选中的 '+rows.length+' 道题会保存到题库并生成试卷。'+
     (manual?'含教师审核主观题，整份作业将使用拍照/教师确认。':'全部题目可在线作答并由服务器判分。')+
     '</div><label>作业名称</label><input id="aqaTitle" value="'+esc(defaultTitle)+'"><div class="form-grid"><div><label>班级</label><select id="aqaClass">'+
     classes.map(c=>'<option value="'+c.id+'">'+esc(c.name)+' · '+c.grade+'年级 · '+(c.studentCount||0)+'人</option>').join('')+
     '</select></div><div><label>截止日期</label><input id="aqaDue" type="date" value="'+new Date(Date.now()+7*86400000).toISOString().slice(0,10)+
     '"></div></div><label>作业要求（可选）</label><textarea id="aqaInstructions"></textarea><button class="btn primary full" id="confirmAIAssignment">一键生成试卷并布置</button>');
    $('#confirmAIAssignment').onclick=async()=>{
     const b=$('#confirmAIAssignment');b.disabled=true;b.textContent='正在布置…';
     try{
      const d=await api('/ai/questions/assign',{method:'POST',body:JSON.stringify({questions:rows,title:$('#aqaTitle').value.trim()||defaultTitle,class_id:+$('#aqaClass').value,due_date:$('#aqaDue').value,instructions:$('#aqaInstructions').value.trim()})});
      closeModal();toast(d.submissionMode==='media'?'教师审核主观题作业已布置，接收 '+(d.recipientCount||0)+' 人':'在线作业已布置，接收 '+(d.recipientCount||0)+' 人');go('papers');
     }catch(e){b.disabled=false;b.textContent='一键生成试卷并布置';toast(e.message)}
    };
   }catch(e){toast(e.message)}
  };
 };
})();
</script>
'''


def patch_teacher_ai_rich_generation_html(html: str) -> str:
    if RICH_GENERATION_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("teacher AI rich generation patch: closing body marker not found")
    return html.replace(
        "</body>",
        _RICH_UI_SCRIPT + f"\n<!-- {RICH_GENERATION_MARKER} --></body>",
        1,
    )




def install_teacher_ai_rich_generation_ui(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "teacher_ai_rich_generation_ui_installed", False):
        return
    implementation.INDEX_HTML = patch_teacher_ai_rich_generation_html(implementation.INDEX_HTML)
    app.state.teacher_ai_rich_generation_ui_installed = True


__all__ = [
    "RICH_GENERATION_MARKER",
    "install_teacher_ai_rich_generation_ui",
    "patch_teacher_ai_rich_generation_html",
]
