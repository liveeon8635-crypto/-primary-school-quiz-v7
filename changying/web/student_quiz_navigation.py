"""Patch the legacy student quiz into a revisable, non-linear answer flow."""

from __future__ import annotations

from types import ModuleType


MARKER = "changying_student_quiz_navigation_v1"


def patch_student_quiz_navigation(html: str) -> str:
    if MARKER in html:
        return html
    start = html.find("function startQuiz(qs,title,aid){")
    end = html.find("async function progress(){", start)
    if start < 0 or end < 0:
        raise RuntimeError("legacy student quiz function not found")

    replacement = r'''function startQuiz(qs,title,aid){
 if(!qs.length){toast("没有可用题目");return}
 let i=0,done=false,correct=0,submitting=false;
 const onlineServerGraded=!state.offline,answersById=new Map(),offlineChecked=new Set(),offlineCorrect=new Set();
 const choiceLike=q=>["single_choice","choice","true_false"].includes(String(q.questionType||"").toLowerCase()) || (((q.options||[]).length>0)&&!["fill_blank","calculation","short_answer"].includes(String(q.questionType||"").toLowerCase()));
 const responseFor=q=>answersById.get(Number(q.id))||null;
 const hasResponse=q=>{const r=responseFor(q);return choiceLike(q)?!!(r&&Number.isInteger(r.selected_index)):!!(r&&String(r.text_answer||"").trim())};
 const answeredCount=()=>qs.reduce((n,q)=>n+(hasResponse(q)?1:0),0);
 const saveChoice=(q,index)=>answersById.set(Number(q.id),{question_id:q.id,selected_index:index});
 const saveText=(q,value)=>{const text=String(value||"").trim();if(text)answersById.set(Number(q.id),{question_id:q.id,text_answer:text});else answersById.delete(Number(q.id))};
 const orderedAnswers=()=>qs.map(q=>responseFor(q)).filter(Boolean);
 const goQuestion=next=>{if(next<0||next>=qs.length||submitting)return;i=next;done=offlineChecked.has(Number(qs[i].id));render()};
 const finishOnline=async()=>{
   if(submitting)return;
   if(answeredCount()!==qs.length){toast("还有未作答题目，请完成后再提交");return}
   submitting=true;render();
   try{
     const answers=orderedAnswers();
     const r=aid?await api("/student/assignments/"+aid+"/submit",{method:"POST",body:JSON.stringify({answers})}):await api("/student/practice-submit",{method:"POST",body:JSON.stringify({title,answers})});
     const learning=Number(r.learningPointsAwarded||0),learningMax=Number(r.learningPointMax||r.total||0);
     $("#page").innerHTML=head(aid?"作业已提交":"练习完成",title)+'<div class="card empty"><div style="font-size:62px">🏆</div><h1 style="color:var(--primary)">'+r.score+'分</h1><p>答对 '+r.correct+' 题，答错 '+(r.total-r.correct)+' 题</p><p><span class="badge green">本次获得 +'+learning+' 学习积分</span></p><p class="muted">本卷最高 '+learningMax+' 学习积分 · 每答对1题获得1积分</p>'+(aid?'<p class="muted">成绩已回传教师端。</p>':"")+'<button id="backQuiz" class="btn primary">返回</button></div>';
     $("#backQuiz").onclick=()=>go(aid?"assignments":"practice");
   }catch(e){submitting=false;render();toast(e.message)}
 };
 const render=()=>{
  const q=qs[i],isChoice=choiceLike(q),typeName=questionTypeName(q.questionType),figure=renderQuestionFigure(q.figure||{}),r=responseFor(q);
  const sel=r&&Number.isInteger(r.selected_index)?r.selected_index:null,textAnswer=r&&r.text_answer!=null?String(r.text_answer):"";
  const checked=offlineChecked.has(Number(q.id));
  const questionMeta=[q.textbook,q.unit,q.knowledge].map(x=>String(x||"").trim()).filter(Boolean).join(" · ");
  const choiceHtml=isChoice?(q.options||[]).map((o,n)=>'<button class="option '+(sel===n?"selected ":"")+((!onlineServerGraded&&checked&&n===q.correctIndex)?"correct ":"")+((!onlineServerGraded&&checked&&sel===n&&n!==q.correctIndex)?"wrong ":"")+'" data-i="'+n+'"><span class="letter">'+String.fromCharCode(65+n)+'</span>'+esc(o)+'</button>').join(""):"";
  const textHtml=isChoice?"":'<label style="margin-top:12px">填写答案</label>'+(String(q.questionType||"")==="short_answer"?'<textarea id="quizTextAnswer" rows="3" placeholder="请输入简短答案">'+esc(textAnswer)+'</textarea>':'<input id="quizTextAnswer" inputmode="'+(String(q.questionType||"")==="calculation"?"decimal":"text")+'" value="'+esc(textAnswer)+'" placeholder="请输入答案">');
  let localAnswer="";
  if(!onlineServerGraded&&checked){
   if(isChoice)localAnswer='<div class="answer"><b>'+(offlineCorrect.has(Number(q.id))?"✅ 正确":"❌ 错误")+'</b><br>正确答案：'+esc((q.options||[])[q.correctIndex]||"")+'<br><span class="muted">'+esc(q.explanation||"")+'</span></div>';
   else localAnswer='<div class="answer"><span class="muted">本地模式暂不判定文本答案。</span></div>';
  }
  const count=onlineServerGraded?answeredCount():offlineChecked.size;
  const nav=onlineServerGraded?'<div style="display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center;margin-top:14px"><button id="quizPrev" class="btn secondary" '+(i===0||submitting?"disabled":"")+'>上一题</button><span class="muted" style="text-align:center;white-space:nowrap">已答 '+count+'/'+qs.length+'</span><button id="quizForward" class="btn secondary" '+(i===qs.length-1||submitting?"disabled":"")+'>下一题</button></div><button id="quizSubmit" class="btn primary full" style="margin-top:10px" '+(count!==qs.length||submitting?"disabled":"")+'>'+(submitting?"正在提交…":"提交整份答卷")+'</button>':'<button id="quizNext" class="btn primary full" '+(!hasResponse(q)&&!checked?"disabled":"")+'>'+(checked?(i===qs.length-1?"完成练习":"下一题"):"提交答案")+'</button>';
  $("#page").innerHTML=head(title,"第 "+(i+1)+"/"+qs.length+" 题"+(onlineServerGraded?" · 可前后切换 · 服务器判分":""),'<button class="btn secondary" id="quitQuiz">退出</button>')+
  '<div class="card"><div class="progress"><i style="width:'+pct(count,qs.length)+'%"></i></div>'+
  '<div style="margin-top:12px"><span class="badge">'+esc(questionMeta)+'</span> <span class="badge">'+esc(typeName)+'</span> <span class="badge green">本题 '+esc(q.learningPoints||1)+' 学习积分</span></div>'+
  '<div class="question">'+esc(q.text)+'</div>'+figure+choiceHtml+textHtml+localAnswer+
  (onlineServerGraded&&aid?'<div class="note">答案会在本机暂存，可自由切换上下题；正式提交前不会显示正确答案或解析。</div>':"")+nav+'</div>';
  $("#quitQuiz").onclick=()=>go(aid?"assignments":"practice");
  $$(".option").forEach(b=>b.onclick=()=>{if(checked&&!onlineServerGraded)return;saveChoice(q,+b.dataset.i);render()});
  if(!isChoice){const input=$("#quizTextAnswer");if(input)input.oninput=()=>{saveText(q,input.value);if(onlineServerGraded){const submit=$("#quizSubmit");if(submit)submit.disabled=answeredCount()!==qs.length||submitting}else{const next=$("#quizNext");if(next)next.disabled=!hasResponse(q)}}}
  if(onlineServerGraded){
    $("#quizPrev").onclick=()=>goQuestion(i-1);
    $("#quizForward").onclick=()=>goQuestion(i+1);
    $("#quizSubmit").onclick=finishOnline;
    return;
  }
  $("#quizNext").onclick=()=>{
    if(!checked){
      offlineChecked.add(Number(q.id));
      if(isChoice&&sel===q.correctIndex)offlineCorrect.add(Number(q.id));
      done=true;render();return;
    }
    if(i<qs.length-1){i++;done=offlineChecked.has(Number(qs[i].id));render();return}
    correct=offlineCorrect.size;
    const score=pct(correct,qs.length);
    $("#page").innerHTML=head("练习完成",title)+'<div class="card empty"><div style="font-size:62px">🏆</div><h1 style="color:var(--primary)">'+score+'分</h1><p>答对 '+correct+' 题，答错 '+(qs.length-correct)+' 题</p><button id="backQuiz" class="btn primary">返回</button></div>';
    $("#backQuiz").onclick=()=>go("practice");
  };
 };render()
}
'''
    style = f'<meta name="{MARKER}" content="1">'
    patched = html[:start] + replacement + html[end:]
    if "</head>" in patched:
        patched = patched.replace("</head>", style + "</head>", 1)
    else:
        patched = style + patched
    return patched


def install_student_quiz_navigation(implementation: ModuleType) -> None:
    if getattr(implementation, "_student_quiz_navigation_installed", False):
        return
    implementation.INDEX_HTML = patch_student_quiz_navigation(implementation.INDEX_HTML)
    implementation._student_quiz_navigation_installed = True


__all__ = ["MARKER", "install_student_quiz_navigation", "patch_student_quiz_navigation"]
