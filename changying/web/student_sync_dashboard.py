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
  '<div id="student-knowledge-map" class="section card hidden"></div>'+
  '<div id="student-exam-papers" class="section card hidden"></div>'+
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
 // 知识地图：功能开启且老师发布了本年级的地图时才显示入口。
 api('/student/knowledge-map').then(m=>{const box=document.getElementById('student-knowledge-map');if(!box||!m||!m.title||!Array.isArray(m.nodes))return;const d=m.diagnosis||{};
  box.innerHTML='<h2>我的知识地图</h2><p>'+esc(m.title)+(d.status==='submitted'?' · 入门诊断已完成':' · 先做 12 道题的入门诊断')+'</p><a class="btn primary" href="/v1/my-knowledge-map">打开知识地图</a>';
  box.classList.remove('hidden')}).catch(()=>{});
 // 应试专项：有没交的限时模拟卷或再测卷时才显示入口。
 api('/student/exam-papers').then(d=>{const box=document.getElementById('student-exam-papers');if(!box||!d||!Array.isArray(d.items))return;const open=d.items.filter(x=>!x.handedIn);if(!open.length)return;
  box.innerHTML='<h2>限时模拟卷</h2><p>'+open.map(x=>esc(x.title)+'（'+Number(x.questionCount)+' 题，限时 '+Number(x.timeLimit)+' 分钟）').join('；')+'</p><a class="btn primary" href="/v1/exam-paper">开始限时作答</a>';
  box.classList.remove('hidden')}).catch(()=>{});
 if(window.__cyStudentClassTimer)clearInterval(window.__cyStudentClassTimer);
 window.__cyStudentClassTimer=setInterval(()=>{if(document.getElementById('student-current-class')!==panel){clearInterval(window.__cyStudentClassTimer);return}if(!document.hidden)refreshCurrent()},5000);
 document.querySelectorAll(".openClassroomInvitation").forEach(b=>b.onclick=()=>classroomInvitationsClassic());
 document.querySelectorAll(".openClassroomQuickCheck").forEach(b=>b.onclick=()=>classroomQuickChecksClassic(+b.dataset.id));
 document.querySelectorAll(".enterSyncLesson").forEach(b=>b.onclick=()=>{state.teachingLessonID=+b.dataset.id;go('syncLesson')});
 document.querySelectorAll(".startStageTest").forEach(b=>b.onclick=()=>startTeachingAdaptive({stage:b.dataset.stage,subject:b.dataset.subject}));
}
'''


STUDENT_PRACTICE_TAB_JS = r'''
async function practice(){
 if(state.offline){
  const qs=offlineBank||[];
  $("#page").innerHTML=head("离线练习","当前处于离线状态")+
   '<div class="card"><p class="muted">离线题库共 '+qs.length+' 题。</p><button class="btn primary full" id="startOfflineP">开始离线练习</button></div>';
  $("#startOfflineP").onclick=()=>startQuiz(qs.slice(0,10),"离线练习",null);
  return;
 }
 $("#page").innerHTML=head("自主练习","知识地图点亮与应试专项分级")+
  '<div class="card" id="practice-hub-loading"><p class="muted">正在加载数学、英语与语文练习进度…</p></div>';
 const [sm,sp,em,ep,cm,cp]=await Promise.all([
  api("/student/math-star-map").catch(()=>null),
  api("/student/math-sprints").catch(()=>null),
  api("/student/english-star-map").catch(()=>null),
  api("/student/english-sprints").catch(()=>null),
  api("/student/chinese-star-map").catch(()=>null),
  api("/student/chinese-sprints").catch(()=>null)
 ]);
 const ms=(sm&&sm.summary)||{totalNodes:24,litNodes:0,masteredNodes:0,repairNodes:0};
 const es=(em&&em.summary)||{totalNodes:16,litNodes:0,masteredNodes:0,repairNodes:0};
 const cs=(cm&&cm.summary)||{totalNodes:16,litNodes:0,masteredNodes:0,repairNodes:0};
 const mpts=(sm&&sm.points)||(sp&&sp.points)||{balance:0,todayEarned:0,dailyCap:30};
 const epts=(em&&em.points)||(ep&&ep.points)||{balance:mpts.balance||0,todayEarned:0,dailyCap:30};
 const cpts=(cm&&cm.points)||(cp&&cp.points)||{balance:mpts.balance||0,todayEarned:0,dailyCap:30};
 const mSpItems=(sp&&sp.items)||[];
 const eSpItems=(ep&&ep.sprints)||[];
 const cSpItems=(cp&&cp.sprints)||[];
 const pickBest=(arr)=>arr.reduce((acc,x)=>(x.bestTier&&(!acc||x.bestTier.rank>acc.rank)?x.bestTier:acc),null);
 const mBest=pickBest(mSpItems),eBest=pickBest(eSpItems),cBest=pickBest(cSpItems);
 const pctOf=(s)=>s.totalNodes?Math.round(s.litNodes/s.totalNodes*100):0;
 let curSubj=(window.__CY_PRACTICE_SUBJ__==='english'||window.__CY_PRACTICE_SUBJ__==='chinese')?window.__CY_PRACTICE_SUBJ__:'math';
 function renderPracticeHub(){
  window.__CY_PRACTICE_SUBJ__=curSubj;
  const conf={
   math:{name:'数学',s:ms,pts:mpts,best:mBest,mapHref:'/v1/math-star-map',spHref:'/v1/math-sprints',mapTitle:'数学知识地图',spTitle:'数学应试专项',
    mapDesc:'覆盖小学数学四大知识域，每个节点自带 5 题微测，答对 80% 即点亮。',
    spDesc:'多题型限时专项（含看图几何题），倒计时自动交卷，按 L1～L4 分级达标。'},
   english:{name:'英语',s:es,pts:epts,best:eBest,mapHref:'/v1/english-star-map',spHref:'/v1/english-sprints',mapTitle:'英语知识地图',spTitle:'英语听说读写专项',
    mapDesc:'按语音自然拼读、核心词汇、语法句型、语篇交际四大知识点域闯关，不限时轻微测，答对 80% 即点亮。',
    spDesc:'按听 / 说 / 读 / 写四大能力独立开考（听/说单题限时，读/写整体倒计时），按 L1～L4 分级达标。'},
   chinese:{name:'语文',s:cs,pts:cpts,best:cBest,mapHref:'/v1/chinese-star-map',spHref:'/v1/chinese-sprints',mapTitle:'语文知识地图',spTitle:'语文四大板块专项',
    mapDesc:'按字词语音、句子修辞、古诗文积累、阅读方法四大知识点域闯关，含普通话朗诵与字块默写，答对 80% 即点亮。',
    spDesc:'覆盖基础字词句（单题限时）、古诗文默写、现代文阅读与微写作（AI 实时点评），按 L1～L4 分级达标。'}
  }[curSubj];
  const s=conf.s,pts=conf.pts,best=conf.best,pct=pctOf(s);
  $("#page").innerHTML=head("自主练习","不限教材版本 · 语数英各科独立每日 30 分上限 · 积分同步计入全站账本")+
   '<div class="card" style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:14px 18px">'+
    '<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">'+
     '<div style="display:inline-flex;background:#efe6dc;border-radius:10px;padding:3px;gap:4px">'+
      '<button type="button" id="phSubjMath" class="btn '+(curSubj==='math'?'primary':'ghost')+'" style="padding:6px 14px;min-height:auto;font-size:13.5px">数学</button>'+
      '<button type="button" id="phSubjEng" class="btn '+(curSubj==='english'?'primary':'ghost')+'" style="padding:6px 14px;min-height:auto;font-size:13.5px">英语</button>'+
      '<button type="button" id="phSubjChi" class="btn '+(curSubj==='chinese'?'primary':'ghost')+'" style="padding:6px 14px;min-height:auto;font-size:13.5px">语文</button>'+
     '</div>'+
     '<div><b>'+conf.name+'练习概览</b><div class="muted" style="margin-top:4px">已点亮 '+Number(s.litNodes)+'/'+Number(s.totalNodes)+'（'+pct+'%）'+(s.repairNodes?' · 待修补 '+Number(s.repairNodes)+' 个':'')+'</div></div>'+
    '</div>'+
    '<span class="badge" style="background:#fdf1f0;color:#a8101c;border:1px solid #f2c6c2;font-weight:700">全站积分 '+Number(pts.balance||0)+'（本科今日 +'+Number(pts.todayEarned||0)+'/'+Number(pts.dailyCap||30)+'）</span>'+
   '</div>'+
   '<div class="grid2" style="margin-top:12px;padding-bottom:84px">'+
    '<div class="card" style="display:flex;flex-direction:column;justify-content:space-between;gap:12px">'+
     '<div><h2 style="margin:0 0 6px">'+conf.mapTitle+'</h2><p class="muted" style="margin:0;line-height:1.6">'+conf.mapDesc+(s.repairNodes?' 当前有 '+Number(s.repairNodes)+' 个专项失分点待修补。':'')+'</p></div>'+
     '<a class="btn primary full" href="'+conf.mapHref+'" style="text-align:center;text-decoration:none">进入'+conf.mapTitle+'</a>'+
    '</div>'+
    '<div class="card" style="display:flex;flex-direction:column;justify-content:space-between;gap:12px">'+
     '<div><h2 style="margin:0 0 6px">'+conf.spTitle+'</h2><p class="muted" style="margin:0;line-height:1.6">'+conf.spDesc+(best?' 当前最高：'+esc(best.code+' '+best.name)+'。':' 可直接开考，无需前置。')+'</p></div>'+
     '<a class="btn secondary full" href="'+conf.spHref+'" style="text-align:center;text-decoration:none">进入'+conf.spTitle+'</a>'+
    '</div>'+
   '</div>';
  const bm=$("#phSubjMath"),be=$("#phSubjEng"),bc=$("#phSubjChi");
  if(bm)bm.onclick=()=>{curSubj='math';renderPracticeHub()};
  if(be)be.onclick=()=>{curSubj='english';renderPracticeHub()};
  if(bc)bc.onclick=()=>{curSubj='chinese';renderPracticeHub()};
 }
 renderPracticeHub();
}
'''


def patch_student_sync_dashboard(html: str) -> str:
    start=html.find('async function syncLearning(){')
    if start>=0:
        end=html.find('\n}\n',start)
        if end<0:raise ValueError('Student classroom function boundary missing')
        html=html[:start]+STUDENT_SYNC_JS.strip()+html[end+2:]
    p_start=html.find('async function practice(){')
    if p_start>=0:
        p_end=html.find('\n}\n',p_start)
        if p_end>=0:
            html=html[:p_start]+STUDENT_PRACTICE_TAB_JS.strip()+html[p_end+2:]
    return html
