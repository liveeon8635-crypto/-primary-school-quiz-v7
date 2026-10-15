"""Make the existing student classroom entry reflect available live activities."""
from __future__ import annotations

STUDENT_SYNC_JS = r'''
async function syncLearning(){
 const [d,quickChecks,invitations,current]=await Promise.all([
  api('/student/teaching/overview').catch(()=>null),
  api('/student/classroom-quick-checks').catch(()=>[]),
  api('/student/classroom-invitations').catch(()=>[]),
  api('/student/weekend/current').catch(()=>({loadError:true}))
 ]);
 const lessons=d&&d.gradeMatch?(d.lessons||[]).filter(l=>l.published):[];
 const tests=d&&d.gradeMatch?(d.tests||[]).filter(t=>t.available&&t.status==='not_started'):[];
 const checks=(quickChecks||[]).filter(x=>x.status==='open');
 const invites=(invitations||[]).filter(x=>['invited','accepted','presenting'].includes(x.status));
 $('#page').innerHTML=head('同步课堂','查看本班当前课堂和老师已发布的学习内容')+
  '<div id="student-current-class" class="section card" style="color:#1f2738;background:#fff"></div>'+
  (invites.length?'<div class="section card"><h2>课堂讲解邀请</h2><p>'+invites.map(x=>esc(x.knowledgeKey)).join('、')+'</p><button class="btn primary full openClassroomInvitation">查看课堂讲解邀请</button></div>':'')+
  (checks.length?'<div class="section card"><h2>正在进行的课堂互动</h2>'+checks.map(q=>'<button class="btn primary full openClassroomQuickCheck" data-id="'+Number(q.id)+'">进入随堂检测 · '+esc(q.knowledgeKey)+'</button>').join('')+'</div>':'')+
  (lessons.length?'<div class="section"><h2>老师已发布的课时</h2><div class="list">'+lessons.map(l=>'<div class="item"><div class="item-main"><b>'+esc(l.subject)+' · '+esc(l.title)+'</b><small>'+esc(l.coreTarget||'')+'</small></div><button class="btn primary small enterSyncLesson" data-id="'+Number(l.id)+'">进入学习</button></div>').join('')+'</div></div>':'')+
  (tests.length?'<div class="section"><h2>可参加的测评</h2><div class="grid2">'+tests.map(t=>'<div class="card"><b>'+esc(t.subject)+' · '+esc(t.stageName)+'</b><button class="btn primary full startStageTest" data-stage="'+esc(t.stage)+'" data-subject="'+esc(t.subject)+'">开始测评</button></div>').join('')+'</div></div>':'');
 const panel=document.getElementById('student-current-class');
 function paintCurrent(c){
  if(document.getElementById('student-current-class')!==panel)return;
  panel.innerHTML=c.loadError?'<h2>当前课堂</h2><p>课堂状态暂时读取失败，请刷新重试。</p>':c.active?
   '<h2>'+esc(c.title)+'</h2><p>'+esc(c.className||'本班课堂')+' · '+esc(c.stageName||'正在上课')+'</p><p>'+esc(c.message||(c.practice?'老师已开放随堂练习，请按本节题目要求作答。':'老师正在讲解，请先听讲。'))+'</p><a class="btn primary" href="/v1/weekend-practice?s='+Number(c.sessionId)+'">'+(c.practice?'进入本节课堂练习':'查看本节课堂')+'</a>':
   '<h2>当前没有正在上的周末课</h2><p>老师开始本班课堂后，这里会自动显示入口。其他班级的课堂不会加入。</p>';
  const refresh=document.createElement('button');refresh.className='btn secondary';refresh.textContent='刷新课堂状态';refresh.onclick=refreshCurrent;panel.appendChild(refresh);
 }
 function refreshCurrent(){return api('/student/weekend/current').then(paintCurrent).catch(()=>paintCurrent({loadError:true}))}
 paintCurrent(current);
 if(window.__cyStudentClassTimer)clearInterval(window.__cyStudentClassTimer);
 window.__cyStudentClassTimer=setInterval(()=>{if(document.getElementById('student-current-class')!==panel){clearInterval(window.__cyStudentClassTimer);return}if(!document.hidden)refreshCurrent()},5000);
 document.querySelectorAll(".openClassroomInvitation").forEach(b=>b.onclick=()=>classroomInvitationsClassic());
 document.querySelectorAll(".openClassroomQuickCheck").forEach(b=>b.onclick=()=>classroomQuickChecksClassic(+b.dataset.id));
 document.querySelectorAll(".enterSyncLesson").forEach(b=>b.onclick=()=>{state.teachingLessonID=+b.dataset.id;go('syncLesson')});
 document.querySelectorAll(".startStageTest").forEach(b=>b.onclick=()=>startTeachingAdaptive({stage:b.dataset.stage,subject:b.dataset.subject}));
}
'''


def patch_student_sync_dashboard(html: str) -> str:
    start=html.find('async function syncLearning(){')
    if start<0:return html
    end=html.find('\n}\n',start)
    if end<0:raise ValueError('Student classroom function boundary missing')
    return html[:start]+STUDENT_SYNC_JS.strip()+html[end+2:]
