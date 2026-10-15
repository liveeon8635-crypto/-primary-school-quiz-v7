"""周末课页面:老师控制条 + 大屏 (static HTML, ES5)."""

from __future__ import annotations

from changying.web.classroom_window_handoff import PAGE_AUTH_JS
from changying.web.homework_assistant_pages import PAGE_CSS
from changying.web.weekend_written_pages import WRITTEN_JS

COMMON_JS = r"""
__PAGE_AUTH__
var el=function(tag,attrs){
  var n=document.createElement(tag);
  Object.keys(attrs||{}).forEach(function(k){
    if(k==='class')n.className=attrs[k];else if(k==='text')n.textContent=attrs[k];
    else if(k.slice(0,2)==='on')n.addEventListener(k.slice(2),attrs[k]);
    else if(attrs[k]===true)n.setAttribute(k,'');else if(attrs[k]!==false&&attrs[k]!=null)n.setAttribute(k,attrs[k]);
  });
  for(var i=2;i<arguments.length;i++){var c=arguments[i];if(c==null)continue;n.appendChild(typeof c==='string'?document.createTextNode(c):c)}
  return n;
};
var root=document.getElementById('app'),TOKEN='';
function api(path,opts){
  opts=opts||{};opts.headers=Object.assign({Authorization:'Bearer '+TOKEN},opts.headers||{});opts.cache='no-store';
  if(opts.json!==undefined){opts.method=opts.method||'POST';opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(opts.json);delete opts.json}
  return fetch(path,opts).then(function(r){return r.json().catch(function(){return {}}).then(function(d){
    if(!r.ok){var e=new Error((d&&d.detail&&typeof d.detail==='string'&&d.detail)||('请求失败（'+r.status+'）'));e.status=r.status;throw e}return d})});
}
function fmt(sec){var neg=sec<0,s=Math.abs(sec),m=Math.floor(s/60),r=s%60;return (neg?'超时 ':'')+(m<10?'0':'')+m+':'+(r<10?'0':'')+r}
function msg(text){root.textContent='';root.appendChild(el('div',{class:'card'},el('h2',{text:text})))}
function boot(run){
  obtainToken().then(function(t){TOKEN=t;if(!TOKEN){msg('请先登录后再打开');return}
    return api('/session').then(function(s){if(s.role!=='teacher'){msg('只有老师可以使用');return}run()})}).catch(function(e){msg(e.message||'打不开')});
}
"""

CONTROL_JS = r"""
var SID=+(new URLSearchParams(location.search).get('s')||0),timer=null,remain=null,tick=null;
function control(){
  root.textContent='';
  if(!SID){picker();return}
  var back=document.querySelector('header a');if(back){back.href='/v1/weekend';back.textContent='返回周末课'}
  var head=el('div',{class:'card'}),stagesBox=el('div',{class:'card'}),content=el('div',{class:'card'}),msgBox=el('div'),
      progBox=el('div',{class:'card'}),hintBox=el('div',{class:'card'}),peerBox=el('div',{class:'card'}),scoreBox=el('div',{class:'card'}),archBox=el('div',{class:'card'});
  root.appendChild(head);root.appendChild(stagesBox);root.appendChild(content);root.appendChild(progBox);root.appendChild(peerBox);root.appendChild(scoreBox);root.appendChild(archBox);root.appendChild(hintBox);root.appendChild(msgBox);
  hintsCard(hintBox);peerCard(peerBox);scoreCard(scoreBox);archiveCard(archBox);
  var writtenBox=el('div',{class:'card'});root.appendChild(writtenBox);writtenTeacher(writtenBox);
  function post(path,body){return api('/teacher/weekend/sessions/'+SID+'/'+path,{json:body||{}}).then(paint).catch(function(e){msgBox.textContent='';msgBox.appendChild(el('div',{class:'notice error',text:e.message}))})}
  function paint(d){
    head.textContent='';stagesBox.textContent='';content.textContent='';remain=d.remainingSeconds;progress(progBox,d);
    var running=d.status==='running';
    head.appendChild(el('h2',{text:d.title}));
    var clock=el('div',{style:'font-size:44px;font-weight:700;line-height:1.2',id:'clock',text:running&&remain!=null?fmt(remain):'--:--'});
    head.appendChild(el('div',{class:'muted',text:d.status==='planned'?'还没开始':d.status==='finished'?'已结束':'第 '+d.currentStage+'/'+d.stageCount+' 环节：'+d.stageName+' · '+d.goal}));
    head.appendChild(clock);
    var row=el('div',{class:'row'});
    if(d.status==='planned')row.appendChild(el('button',{class:'primary',text:'开始上课',onclick:function(){post('start')}}));
    if(running){
      row.appendChild(el('button',{text:'‹ 上一环节',onclick:function(){post('prev')}}));
      row.appendChild(el('button',{class:'primary',text:d.currentStage>=d.stageCount?'结束这节课':'下一环节 ›',onclick:function(){post('next')}}));
      row.appendChild(el('button',{text:'延长 5 分钟',onclick:function(){post('extend',{minutes:5})}}));
      row.appendChild(el('button',{class:d.covered?'on':'',text:d.covered?'大屏已遮盖（点击恢复）':'遮盖大屏',onclick:function(){post('cover',{covered:!d.covered})}}));
      row.appendChild(el('button',{text:'提前结束',onclick:function(){if(confirm('确定提前结束这节课？'))post('finish')}}));
    }
    row.appendChild(el('a',{class:'btn',href:'/v1/weekend-board?s='+SID,target:'_blank',text:'打开大屏'}));
    head.appendChild(row);
    stagesBox.appendChild(el('h2',{text:'环节'}));
    d.stages.forEach(function(s){
      var b=el('button',{class:s.no===d.currentStage&&running?'on':'',text:s.no+'. '+s.name+'（'+(s.minutes+s.extendMin)+'分）'+(s.visited&&s.no!==d.currentStage?' ✓':''),
        onclick:function(){if(running)post('goto',{stage:s.no})}});
      stagesBox.appendChild(el('div',{class:'row'},b,el('span',{class:'muted',text:s.goal})));
    });
    content.appendChild(el('h2',{text:'当前环节大屏内容'}));
    if(d.deck){
      content.appendChild(el('div',{class:'row'},el('button',{text:'‹ 上一页',disabled:d.deck.index<=0,onclick:function(){post('slide',{delta:-1})}}),
        el('b',{text:'第 '+(d.deck.index+1)+' / '+d.deck.total+' 页'}),el('button',{class:'primary',text:'下一页 ›',disabled:d.deck.index>=d.deck.total-1,onclick:function(){post('slide',{delta:1})}})));
    }
    if(!d.content.length)content.appendChild(el('div',{class:'muted',text:running?(d.covered?'大屏遮盖中':'这个环节没有内容'):'开始上课后显示'}));
    d.content.forEach(function(x){content.appendChild(el('p',{text:x}))});
  }
  function load(){api('/teacher/weekend/sessions/'+SID).then(paint).catch(function(e){msgBox.textContent='';msgBox.appendChild(el('div',{class:'notice error',text:e.message}))})}
  load();
  if(tick)clearInterval(tick);
  tick=setInterval(function(){if(remain!=null){remain-=1;var c=document.getElementById('clock');if(c)c.textContent=fmt(remain)}},1000);
  if(timer)clearInterval(timer);
  timer=setInterval(load,15000);
}
function progress(box,d){
  if(d.status!=='running'&&d.status!=='finished'){box.textContent='';return}
  api('/teacher/weekend/sessions/'+SID+'/progress').then(function(p){
    box.textContent='';box.appendChild(el('h2',{text:'选择题进度（班级正确率 '+p.classCompletionRate+'%）'}));
    if(!p.items.length){box.appendChild(el('div',{class:'muted',text:'没有学生。学生要在“我的班级”里属于你的班级。'}));return}
    p.items.forEach(function(i){
      box.appendChild(el('div',{class:'row'},el('b',{text:i.name}),
        el('span',{class:'tag',text:'做完 '+i.answered+'/'+i.total}),el('span',{class:'tag',text:'做对 '+i.correct}),
        el('span',{class:'tag '+(i.hintMax>=2?'warn':''),text:'提示最高 '+i.hintMax+' 级 · 平均 '+i.hintAvg}),
        el('span',{class:'muted',text:'正确率 '+i.completionRate+'%'})));
    });
  }).catch(function(){});
}
function peerCard(box){
  box.appendChild(el('h2',{text:'请同学讲解（复盘环节）'}));
  box.appendChild(el('div',{class:'muted',text:'像课堂互动一样：选一道题，请做对的同学来讲。大屏会显示“请 XX 同学来讲”，TA 的页面会收到题目和解析；讲完，没做对的同学会收到一道类似的小题，做对了讲解的同学加分。'}));
  var out=el('div'),msg=el('div'),go=el('button',{text:'查看可以讲的题',onclick:function(){load()}});
  box.appendChild(go);box.appendChild(out);box.appendChild(msg);
  function load(){
    out.textContent='';msg.textContent='';
    api('/teacher/weekend/sessions/'+SID+'/peer-suggest').then(function(d){
      out.appendChild(el('div',{class:'notice ok',text:d.message}));
      d.questions.forEach(function(q){
        var row=el('div',{class:'card'},el('b',{text:'第 '+q.no+' 题：'+q.stem}),
          el('div',{class:'muted',text:'做对：'+q.right.map(function(x){return x.name}).join('、')+'　·　没做对：'+q.wrong.map(function(x){return x.name}).join('、')}));
        var act=el('div',{class:'row'});
        q.right.forEach(function(r){
          var b=el('button',{text:r.asked?'已请 '+r.name+' 讲过':'请 '+r.name+' 来讲',disabled:r.asked,onclick:function(){
            b.disabled=true;msg.textContent='';
            api('/teacher/weekend/sessions/'+SID+'/explain',{json:{tutorId:r.studentId,questionId:q.questionId}}).then(function(res){msg.appendChild(el('div',{class:'notice ok',text:res.message}));b.textContent='已请 '+r.name+' 讲过'})
              .catch(function(e){msg.appendChild(el('div',{class:'notice error',text:e.message}));b.disabled=false});
          }});
          act.appendChild(b);
        });
        row.appendChild(act);out.appendChild(row);
      });
    }).catch(function(e){out.appendChild(el('div',{class:'notice error',text:e.message}))});
  }
}
var PART={progress:'进步',completion:'完成率',tutor:'小老师',team:'团队'};
function scoreCard(box){
  box.appendChild(el('h2',{text:'结算积分'}));
  box.appendChild(el('div',{class:'muted',text:'课后点一次。先预览每人为什么得分，确认后写入积分（只能结算一次）。进步只和自己最近 3 次课比，退步不扣分。'}));
  var out=el('div'),msg=el('div');
  var pre=el('button',{text:'预览得分',onclick:function(){preview()}});
  box.appendChild(pre);box.appendChild(out);box.appendChild(msg);
  function paint(d){
    out.textContent='';
    out.appendChild(el('div',{class:'muted',text:'班级完成率 '+d.preRate+'% → 巩固后 '+d.postRate+'%'+(d.prevPostRate==null?'（首次课，没有上一次可比）':'（上一次 '+d.prevPostRate+'%）')+' · 团队分 '+d.teamPoints}));
    d.items.forEach(function(i){
      var parts=Object.keys(PART).map(function(k){return i.parts[k]?PART[k]+' +'+i.parts[k]:null}).filter(Boolean).join('，')||'本节没有加分';
      out.appendChild(el('div',{class:'row'},el('b',{text:i.name+'  共 '+i.total+' 分'}),el('span',{class:'muted',text:parts+(i.why.progress.reason&&i.why.progress.reason!=='ok'?' · '+i.why.progress.reason:'')})));
    });
    if(d.settled){out.appendChild(el('div',{class:'notice ok',text:'已结算，积分已写入。'}));return}
    if(d.pendingFollowups>0)out.appendChild(el('div',{class:'notice warn',text:'还有 '+d.pendingFollowups+' 位同学的巩固题没做完。现在结算，小老师这部分的分会拿不到（只能结算一次），建议等他们做完再结算。'}));
    out.appendChild(el('button',{class:'primary',text:'确认结算并写入积分',onclick:function(){
      msg.textContent='';
      api('/teacher/weekend/sessions/'+SID+'/settle',{method:'POST',json:{}}).then(function(r){paint(r);msg.appendChild(el('div',{class:'notice ok',text:'已写入积分'}))}).catch(function(e){msg.appendChild(el('div',{class:'notice error',text:e.message}))});
    }}));
  }
  function preview(){out.textContent='';api('/teacher/weekend/sessions/'+SID+'/settle-preview').then(paint).catch(function(e){out.appendChild(el('div',{class:'notice error',text:e.message}))})}
}
function hintsCard(box){
  box.appendChild(el('h2',{text:'本节习题的 3 级提示'}));
  box.appendChild(el('div',{class:'muted',text:'提示由 AI 写草稿，你审核后才是正式提示；没审核的题，学生求助时 AI 会临时生成（标记“待审核”）。'}));
  var list=el('div');box.appendChild(list);
  api('/teacher/weekend/sessions/'+SID+'/questions').then(function(d){
    if(!d.items.length){list.appendChild(el('div',{class:'muted',text:'这节课还没有习题，请先在“定制教学”里添加。'}));return}
    d.items.forEach(function(q){
      var tas=[0,1,2].map(function(i){var t=el('textarea',{class:'s',placeholder:'第'+(i+1)+'级：'+q.levelNames[i]});t.value=q.hints[i]||'';return t});
      var m=el('div'),tag=el('span',{class:'tag'});
      function lab(st){tag.className='tag '+(st==='approved'?'ok':'warn');tag.textContent=st==='approved'?'已审核':st==='auto'?'待审核':st==='draft'?'草稿':'未准备'}lab(q.hintStatus);
      function vals(){return tas.map(function(t){return t.value})}
      var body=el('div',{hidden:true});
      var ai=el('button',{text:'AI 写草稿',onclick:function(){m.textContent='';ai.disabled=true;
        api('/teacher/weekend/hints/generate',{json:{questionId:q.id}}).then(function(r){r.hints.forEach(function(h,i){tas[i].value=h});lab('draft');m.appendChild(el('div',{class:'notice ok',text:'已生成草稿，请核对后审核通过'}))})
          .catch(function(e){m.appendChild(el('div',{class:'notice error',text:e.message}))}).then(function(){ai.disabled=false})}});
      var ok=el('button',{class:'primary',text:'审核通过',onclick:function(){m.textContent='';
        api('/teacher/weekend/hints/'+q.id,{method:'PUT',json:{levels:vals(),approve:true}}).then(function(){lab('approved');m.appendChild(el('div',{class:'notice ok',text:'已审核'}))})
          .catch(function(e){m.appendChild(el('div',{class:'notice error',text:e.message}))})}});
      tas.forEach(function(t){body.appendChild(t)});body.appendChild(el('div',{class:'row'},ai,ok));body.appendChild(m);
      list.appendChild(el('div',{class:'item'},el('span',{class:'t'},el('div',{class:'row'},el('b',{text:q.stem.slice(0,60)}),tag,el('button',{text:'展开/收起',onclick:function(){body.hidden=!body.hidden}})),body)));
    });
  }).catch(function(e){list.appendChild(el('div',{class:'notice error',text:e.message}))});
}
var HSUBJ='数学';
function picker(){
  root.textContent='';
  var tabs=el('div',{class:'tabs'}),stepsBox=el('div',{class:'card'}),recent=el('div',{class:'card'}),msg=el('div');
  ['数学','语文'].forEach(function(x){tabs.appendChild(el('button',{class:x===HSUBJ?'on':'',text:x,onclick:function(){HSUBJ=x;picker()}}))});
  root.appendChild(tabs);root.appendChild(stepsBox);root.appendChild(msg);root.appendChild(recent);
  function step(ok,title,hint,btn){
    return el('div',{class:'item'},el('span',{style:'font-size:22px;width:30px;flex:none',text:ok?'✅':'⬜'}),el('span',{class:'t'},el('b',{text:title}),el('span',{class:'muted',text:hint})),btn||null);
  }
  api('/teacher/weekend/next').then(function(d){
    var x=d.items.filter(function(i){return i.subject===HSUBJ})[0];
    stepsBox.textContent='';
    if(!x||x.done){stepsBox.appendChild(el('h2',{text:'18 次课都上完了'}));return}
    stepsBox.appendChild(el('h2',{text:HSUBJ+' 第 '+x.lessonNo+' 次课'}));
    stepsBox.appendChild(el('div',{class:'muted',text:(x.schoolWeek?'学校第 '+x.schoolWeek+' 周 · ':'')+(x.schoolUnit||'学校进度还没填')+(x.plannedDate?' · '+x.plannedDate:'')}));
    var go=function(text){return el('a',{class:'btn',href:'/v1/weekend-plan',text:text})};
    var ready=x.hasPlan&&x.approvedQuestions>0;
    stepsBox.appendChild(step(!!x.schoolUnit,'① 填学校进度','让系统知道这一周学校讲到哪里；学校调课可以一键顺延',go('去填')));
    stepsBox.appendChild(step(x.hasPlan,'② 准备教案','没有教案就点“AI 备课草稿”，生成后你改一改',go('去备课')));
    stepsBox.appendChild(step(x.approvedQuestions>0,'③ 准备习题（已通过 '+x.approvedQuestions+' 道'+(x.draftQuestions?'，待审核 '+x.draftQuestions+' 道':'')+'）','AI 出的题是草稿，逐题点“通过”后学生才能做',go('去审核')));
    var start=el('button',{class:'primary',text:'④ 开课',disabled:!ready,onclick:function(){
      start.disabled=true;
      api('/teacher/weekend/sessions',{json:{lessonId:x.lessonId}}).then(function(s){location.href='/v1/weekend?s='+s.id}).catch(function(e){msg.textContent='';msg.appendChild(el('div',{class:'notice error',text:e.message}));start.disabled=false});
    }});
    stepsBox.appendChild(step(false,'④ 开课','点开后进入上课页：开始上课、按 7 个环节推进、打开大屏。'+(ready?'':'（先完成上面三步）'),start));
    stepsBox.appendChild(el('div',{class:'muted',text:'下课后在同一个上课页点“预览得分→确认结算”，再发布家长简报。'}));
    if(x.weakKnowledge.length)stepsBox.appendChild(el('div',{class:'notice warn',text:'班里近期错得最多：'+x.weakKnowledge.map(function(w){return w.knowledge+'（'+w.count+' 次）'}).join('、')+'，备课时可以重点安排。'}));
  }).catch(function(e){stepsBox.appendChild(el('div',{class:'notice error',text:e.message}))});
  recent.appendChild(el('h2',{text:'最近的课堂'}));
  var rlist=el('div');recent.appendChild(rlist);
  api('/teacher/weekend/sessions').then(function(d){
    if(!d.items.length){rlist.appendChild(el('div',{class:'muted',text:'还没有。'}));return}
    d.items.forEach(function(s){rlist.appendChild(el('div',{class:'row'},el('a',{href:'/v1/weekend?s='+s.id,text:s.title}),el('span',{class:'muted',text:s.createdAt+' · '+(s.status==='finished'?'已结束':s.status==='running'?'进行中':'未开始')})))});
  });
  recent.appendChild(el('hr'));
  recent.appendChild(el('div',{class:'row'},el('a',{class:'btn',href:'/v1/weekend-plan',text:'18 次课进度表与备课'}),el('a',{class:'btn',href:'/v1/knowledge',text:'知识点讲解卡片（学生搜索、错题讲解）'})));
}
boot(control);
"""

BOARD_JS = r"""
var SID=+(new URLSearchParams(location.search).get('s')||0);
function board(){
  if(!SID){msg('缺少课堂编号');return}
  document.body.style.background='#0f172a';
  var wrap=el('div',{style:'color:#fff;padding:3vh 5vw;min-height:92vh'});root.textContent='';root.style.maxWidth='none';root.appendChild(wrap);
  var remain=null;
  function paint(d){
    wrap.textContent='';
    wrap.appendChild(el('div',{style:'opacity:.7;font-size:2.4vh',text:d.title}));
    if(d.status==='planned'){wrap.appendChild(el('div',{style:'font-size:6vh;margin-top:20vh;text-align:center',text:'马上开始上课'}));return}
    if(d.status==='finished'){wrap.appendChild(el('div',{style:'font-size:6vh;margin-top:20vh;text-align:center',text:'下课了，谢谢大家'}));return}
    if(d.covered){wrap.appendChild(el('div',{style:'font-size:6vh;margin-top:20vh;text-align:center',text:'请看老师'}));return}
    wrap.appendChild(el('div',{style:'display:flex;justify-content:space-between;align-items:baseline'},
      el('div',{style:'font-size:6vh;font-weight:700',text:d.currentStage+'. '+d.stageName}),
      el('div',{id:'bclock',style:'font-size:6vh;font-weight:700',text:remain==null?'':fmt(remain)})));
    wrap.appendChild(el('div',{style:'font-size:3vh;opacity:.8;margin:1vh 0 3vh',text:d.goal}));
    if(d.deck)wrap.appendChild(el('div',{style:'opacity:.6;font-size:2.4vh',text:'第 '+(d.deck.index+1)+' / '+d.deck.total+' 页'}));
    d.content.forEach(function(x){wrap.appendChild(el('p',{style:'font-size:'+(d.deck?'5.5vh':'4vh')+';line-height:1.5;margin:1.5vh 0',text:x}))});
  }
  var last=null;
  function load(){api('/teacher/weekend/sessions/'+SID+'/board').then(function(d){last=d;remain=d.remainingSeconds;paint(d)}).catch(function(e){if(!last)msg(e.message)})}
  load();setInterval(load,3000);
  setInterval(function(){if(remain!=null){remain-=1;var c=document.getElementById('bclock');if(c)c.textContent=fmt(remain)}},1000);
}
boot(board);
"""

PRACTICE_JS = r"""
var LETTERS='ABCDEFGH',wait=null;
function practice(){
  root.textContent='';
  var box=el('div');root.appendChild(box);
  function load(){
    api('/student/weekend/current').then(paint).catch(function(e){box.textContent='';box.appendChild(el('div',{class:'card'},el('div',{class:'notice error',text:e.message})))});
  }
  function paint(d){
    var open=document.querySelector('textarea:focus');
    box.textContent='';
    if(!d.active||!d.practice){
      box.appendChild(el('div',{class:'card'},el('h2',{text:d.title||'课堂练习'}),el('div',{class:'muted',text:d.message||''})));
      return;
    }
    box.appendChild(el('div',{class:'card'},el('h2',{text:d.title}),el('div',{class:'muted',text:'随堂练习：自己先想，卡住了再点“要提示”。每道题只能提交一次。'})));
    d.questions.forEach(function(q,qi){
      var card=el('div',{class:'card'}),out=el('div'),hintsOut=el('div');
      card.appendChild(el('b',{text:(qi+1)+'. '+q.stem}));
      var chosen=-1,opts=el('div');
      q.options.forEach(function(o,i){
        var b=el('button',{style:'display:block;width:100%;text-align:left;margin:6px 0',text:LETTERS[i]+'. '+o});
        if(q.answered){
          if(i===q.correctIndex)b.className='primary';
          else if(i===q.selected)b.style.borderColor='#b42318';
          b.disabled=true;
        }else b.addEventListener('click',function(){chosen=i;Array.prototype.forEach.call(opts.children,function(x,j){x.className=j===i?'on':''})});
        opts.appendChild(b);
      });
      card.appendChild(opts);
      if(q.answered){
        out.appendChild(el('div',{class:'notice '+(q.correct?'ok':'error'),text:q.correct?'答对了':'答错了，正确答案是 '+LETTERS[q.correctIndex]}));
        if(q.explanation)out.appendChild(el('div',{class:'muted',text:q.explanation}));
      }else{
        var hintBtn=el('button',{text:q.hintUsed>=3?'提示已用完':'要提示（已用 '+q.hintUsed+'/3）',disabled:q.hintUsed>=3,onclick:function(){
          hintBtn.disabled=true;
          api('/student/weekend/hint',{json:{sessionId:d.sessionId,questionId:q.id}}).then(function(h){
            hintsOut.appendChild(el('div',{class:'notice warn',text:'提示'+h.level+'（'+h.name+'）：'+h.text}));
            q.hintUsed=h.level;hintBtn.textContent=h.last?'提示已用完':'要提示（已用 '+h.level+'/3）';hintBtn.disabled=!!h.last;
          }).catch(function(e){hintsOut.appendChild(el('div',{class:'notice error',text:e.message}));hintBtn.disabled=false});
        }});
        var submit=el('button',{class:'primary',text:'提交答案',onclick:function(){
          if(chosen<0){alert('先选一个答案');return}
          submit.disabled=true;
          api('/student/weekend/answer',{json:{sessionId:d.sessionId,questionId:q.id,selected:chosen}}).then(load).catch(function(e){alert(e.message);submit.disabled=false});
        }});
        card.appendChild(el('div',{class:'row'},hintBtn,submit));
        (q.hintTexts||[]).forEach(function(t,i){hintsOut.appendChild(el('div',{class:'notice warn',text:'提示'+(i+1)+'（'+q.levelNames[i]+'）：'+t}))});
      }
      card.appendChild(hintsOut);card.appendChild(out);box.appendChild(card);
    });
  }
  var ebox=el('div');root.insertBefore(ebox,box);
  function explain(){
    api('/student/weekend/explain').then(function(d){
      ebox.textContent='';
      d.items.forEach(function(q){
        var card=el('div',{class:'card'});
        card.appendChild(el('h2',{text:'老师请你给大家讲这道题'}));
        card.appendChild(el('b',{text:q.stem}));
        card.appendChild(el('div',{class:'muted',text:'正确答案：'+LETTERS[q.correctIndex]+'. '+(q.options[q.correctIndex]||'')}));
        if(q.explanation)card.appendChild(el('div',{text:'解析：'+q.explanation}));
        card.appendChild(el('div',{class:'muted',text:'用自己的话讲：先说第一步做什么，为什么这样做，最后得到什么。'}));
        ebox.appendChild(card);
      });
    }).catch(function(){});
  }
  var fbox=el('div');root.insertBefore(fbox,box);
  function followup(){
    api('/student/weekend/followup').then(function(f){
      fbox.textContent='';if(!f.active)return;
      var card=el('div',{class:'card'}),chosen=-1,out=el('div'),opts=el('div');
      card.appendChild(el('h2',{text:'巩固小题：刚讲过的方法，再试一道'}));card.appendChild(el('b',{text:f.stem}));
      f.options.forEach(function(o,i){opts.appendChild(el('button',{style:'display:block;width:100%;text-align:left;margin:6px 0',text:LETTERS[i]+'. '+o,onclick:function(){chosen=i;Array.prototype.forEach.call(opts.children,function(x,j){x.className=j===i?'on':''})}}))});
      card.appendChild(opts);
      var sub=el('button',{class:'primary',text:'提交',onclick:function(){
        if(chosen<0){alert('先选一个答案');return}sub.disabled=true;
        api('/student/weekend/followup',{json:{peerHelpId:f.peerHelpId,selected:chosen}}).then(function(r){
          out.appendChild(el('div',{class:'notice '+(r.correct?'ok':'error'),text:r.correct?'答对了':'答错了，正确答案是 '+LETTERS[r.correctIndex]}));if(r.explanation)out.appendChild(el('div',{class:'muted',text:r.explanation}));
        }).catch(function(e){alert(e.message);sub.disabled=false});
      }});
      card.appendChild(el('div',{class:'row'},sub));card.appendChild(out);fbox.appendChild(card);
    }).catch(function(){});
  }
  var writtenBox=el('div',{class:'card'});root.appendChild(writtenBox);writtenStudent(writtenBox);
  load();followup();explain();
  wait=setInterval(function(){if(!document.hidden){load();explain();if(!fbox.firstChild)followup()}},20000);
}
boot_student(practice);
"""

PAGE_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>__TITLE__</title>
<style>__CSS__</style></head>
<body><main id="app"><div class="card muted">加载中…</div></main>
<script>__JS__</script></body></html>
"""


EXTRA_CSS = "textarea.s{min-height:64px}\n.tag.ok{background:#ecfdf3;color:#067647}.tag.warn{background:#fff4e5;color:#b54708}"


def _page(title: str, js: str, with_header: bool, back: tuple[str, str] = ("/v1", "返回首页")) -> str:
    html = PAGE_HTML.replace("__TITLE__", title).replace("__CSS__", PAGE_CSS + EXTRA_CSS)
    if with_header:
        html = html.replace("<body>", f'<body><header><h1>{title}</h1><a href="{back[0]}">{back[1]}</a></header>', 1)
    return html.replace("__JS__", (COMMON_JS + js).replace("__PAGE_AUTH__", PAGE_AUTH_JS))


PARENT_JS = r"""
function parentBoot(){
  obtainToken().then(function(t){TOKEN=t;if(!TOKEN){msg('请先登录后再打开');return}
    return api('/session').then(function(s){if(s.role!=='parent'){msg('这个页面给家长使用');return}return api('/parent/children').then(paintChildren)})}).catch(function(e){msg(e.message||'打不开')});
}
function paintChildren(list){
  root.textContent='';
  var items=Array.isArray(list)?list:(list.items||list.children||[]);
  if(!items.length){root.appendChild(el('div',{class:'card'},el('h2',{text:'还没有关联孩子'})));return}
  items.forEach(function(c){
    var id=c.id||c.studentID||c.studentId,box=el('div',{class:'card'},el('h2',{text:(c.name||'孩子')+' 的周末课简报'}));
    root.appendChild(box);
    api('/parent/children/'+id+'/weekend-briefs').then(function(d){
      if(!d.items.length){box.appendChild(el('div',{class:'muted',text:'老师发布后会显示在这里。'}));return}
      d.items.forEach(function(b){box.appendChild(el('div',{class:'item'},el('span',{class:'t'},el('b',{text:b.title+' · '+b.at}),el('div',{text:b.text}))))});
    }).catch(function(e){box.appendChild(el('div',{class:'notice error',text:e.message}))});
  });
}
parentBoot();
"""

PLAN_JS = r"""
var SUBJ='数学';
function plan(){
  root.textContent='';
  var tabs=el('div',{class:'tabs'}),nextBox=el('div',{class:'card'}),toolBox=el('div',{class:'card'}),list=el('div'),msg=el('div');
  ['数学','语文'].forEach(function(s){tabs.appendChild(el('button',{class:s===SUBJ?'on':'',text:s,onclick:function(){SUBJ=s;plan()}}))});
  root.appendChild(tabs);root.appendChild(nextBox);root.appendChild(toolBox);root.appendChild(msg);root.appendChild(list);
  function note(kind,text){msg.textContent='';msg.appendChild(el('div',{class:'notice '+kind,text:text}))}
  nextBox.appendChild(el('h2',{text:'下一次课怎么准备'}));
  api('/teacher/weekend/next').then(function(d){
    d.items.filter(function(x){return x.subject===SUBJ}).forEach(function(x){
      if(x.done){nextBox.appendChild(el('div',{class:'muted',text:'18 次课都上完了。'}));return}
      nextBox.appendChild(el('div',{class:'row'},el('b',{text:'第 '+x.lessonNo+' 次课'}),el('span',{class:'muted',text:(x.schoolWeek?'学校第 '+x.schoolWeek+' 周 · ':'')+(x.schoolUnit||'进度未填')+(x.plannedDate?' · '+x.plannedDate:'')})));
      if(x.weakKnowledge.length)nextBox.appendChild(el('div',{class:'muted',text:'班里近期错得最多：'+x.weakKnowledge.map(function(w){return w.knowledge+'（'+w.count+'）'}).join('、')+'，可以放进这节课。'}));
      x.tips.forEach(function(t){nextBox.appendChild(el('div',{class:'notice warn',text:t}))});
      if(!x.tips.length)nextBox.appendChild(el('div',{class:'notice ok',text:'教案和习题都准备好了。'}));
    });
  }).catch(function(e){nextBox.appendChild(el('div',{class:'notice error',text:e.message}))});

  toolBox.appendChild(el('div',{class:'notice ok',text:'备课方法：在下面每一次课的那一行，点“导入我的教案”上传你自己的 Word / PPT / PDF 教案，系统整理成上课用的内容；没有教案时才用“AI 帮我写”。学校进度表只是用来对照学校讲到哪里，可以不填。'}));
  toolBox.appendChild(el('h2',{text:'学校进度表（选填）'}));
  toolBox.appendChild(el('div',{class:'muted',text:'把学校发的进度安排粘贴进来，AI 帮你整理成 18 次课；也可以手动填。学校调课时，用“整体顺延”一次改完。'}));
  var paste=el('textarea',{placeholder:'粘贴学校的教学进度表文字'}),parseBtn=el('button',{text:'AI 识别进度',onclick:function(){
    parseBtn.disabled=true;note('ok','AI 正在整理…');
    api('/teacher/weekend/schedule/parse',{json:{subject:SUBJ,text:paste.value}}).then(function(r){
      api('/teacher/weekend/schedule').then(function(cur){
        r.rows.forEach(function(x){var row=cur.items[x.lessonNo-1];if(row){row.schoolWeek=x.schoolWeek;row.schoolUnit=x.schoolUnit}});
        paintRows(cur.items);note('ok',r.message+'（还没保存，点“保存进度表”）');
      });
    }).catch(function(e){note('error',e.message)}).then(function(){parseBtn.disabled=false});
  }});
  var fromNo=el('input',{type:'text',value:'1',style:'width:70px'}),weeks=el('input',{type:'text',value:'1',style:'width:70px'});
  var shiftBtn=el('button',{text:'整体顺延',onclick:function(){
    api('/teacher/weekend/schedule/shift',{json:{subject:SUBJ,fromLessonNo:+fromNo.value,weeks:+weeks.value}}).then(function(r){note('ok','已顺延 '+r.moved+' 次课');load()}).catch(function(e){note('error',e.message)})}});
  toolBox.appendChild(paste);
  toolBox.appendChild(el('div',{class:'row'},parseBtn,el('span',{class:'muted',text:'从第'}),fromNo,el('span',{class:'muted',text:'次课起，推迟'}),weeks,el('span',{class:'muted',text:'周'}),shiftBtn));

  var state=[];
  function paintRows(rows){
    state=rows;list.textContent='';
    rows.forEach(function(r){
      var wk=el('input',{type:'text',value:r.schoolWeek==null?'':r.schoolWeek,placeholder:'学校周',style:'width:70px',oninput:function(e){r.schoolWeek=e.target.value===''?null:+e.target.value}}),
          un=el('input',{type:'text',value:r.schoolUnit||'',placeholder:'学校进度/单元',oninput:function(e){r.schoolUnit=e.target.value}}),
          dt=el('input',{type:'text',value:r.plannedDate||'',placeholder:'2026-09-12',style:'width:120px',oninput:function(e){r.plannedDate=e.target.value}});
      var tag=el('span',{class:'tag '+(r.taught?'ok':r.hasPlan?'':'warn'),text:r.taught?'已上':r.hasPlan?'有教案·题 '+r.approvedQuestions+(r.draftQuestions?'+草稿'+r.draftQuestions:''):'未备课'});
      var detail=el('div',{hidden:true});
      var fileIn=el('input',{type:'file',accept:'.docx,.pptx,.pdf,.txt,.md',hidden:true});
      var impBtn=el('button',{class:r.hasPlan?'':'primary',text:'导入我的教案',title:'支持 Word(.docx)、PPT(.pptx)、PDF、txt',onclick:function(){fileIn.click()}});
      fileIn.addEventListener('change',function(){
        var f=fileIn.files&&fileIn.files[0];if(!f)return;
        if(r.hasPlan&&!confirm('这节课已有教案，导入会覆盖教案文字和未审核的草稿题（已通过的习题保留）。确定吗？')){fileIn.value='';return}
        var fd=new FormData();fd.append('subject',SUBJ);fd.append('lessonNo',String(r.lessonNo));fd.append('force',r.hasPlan?'1':'0');fd.append('file',f);
        impBtn.disabled=true;note('ok','正在读取并整理你的教案，约半分钟…');
        api('/teacher/weekend/lessons/import',{method:'POST',body:fd}).then(function(d){note('ok',d.message);load()}).catch(function(e){note('error',e.message);impBtn.disabled=false}).then(function(){fileIn.value=''});
      });
      var draftBtn=el('button',{text:r.hasPlan?'AI 重写':'没教案？AI 帮我写',onclick:function(){
        if(r.hasPlan&&!confirm('这节课已有教案，AI 重写会覆盖教案文字和未审核的草稿题，确定吗？'))return;
        draftBtn.disabled=true;note('ok','AI 正在备课，大约半分钟…');
        api('/teacher/weekend/lessons/draft',{json:{subject:SUBJ,lessonNo:r.lessonNo,force:r.hasPlan}}).then(function(){note('ok','草稿已生成，请展开“审改”核对后再用。');load()})
          .catch(function(e){note('error',e.message);draftBtn.disabled=false});
      }});
      var qBtn=(r.hasPlan&&r.approvedQuestions===0)?el('button',{text:'AI 出习题（保留教案）',onclick:function(){
        qBtn.disabled=true;note('ok','AI 正在出题…');
        api('/teacher/weekend/lessons/draft',{json:{subject:SUBJ,lessonNo:r.lessonNo,onlyQuestions:true}}).then(function(){note('ok','习题草稿已生成，展开“审改”逐题通过后才会给学生。');load()}).catch(function(e){note('error',e.message);qBtn.disabled=false});
      }}):null;
      var open=el('button',{text:'审改',disabled:!r.lessonId,onclick:function(){detail.hidden=!detail.hidden;if(!detail.hidden)lessonDetail(r,detail)}});
      var go=el('button',{class:'primary',text:'开课',title:'需要教案和已通过的习题',disabled:!(r.lessonId&&r.hasPlan&&r.approvedQuestions>0),onclick:function(){
        api('/teacher/weekend/sessions',{json:{lessonId:r.lessonId}}).then(function(d){location.href='/v1/weekend?s='+d.id}).catch(function(e){note('error',e.message)})}});
      list.appendChild(el('div',{class:'card'},el('div',{class:'row'},el('b',{text:'第 '+r.lessonNo+' 次'}),wk,un,dt),
        el('div',{class:'row'},tag,el('span',{class:'muted',text:r.title||''}),impBtn,fileIn,draftBtn,qBtn,open,go),detail));
    });
    list.appendChild(el('button',{class:'primary',text:'保存进度表',onclick:function(){
      api('/teacher/weekend/schedule',{method:'PUT',json:{subject:SUBJ,rows:state.map(function(r){return {lessonNo:r.lessonNo,schoolWeek:r.schoolWeek,schoolUnit:r.schoolUnit||'',plannedDate:r.plannedDate||'',note:r.note||''}})}}).then(function(){note('ok','已保存');load()}).catch(function(e){note('error',e.message)})}}));
  }
  function lessonDetail(r,box){
    box.textContent='';
    api('/teacher/weekend/lessons/'+r.lessonId).then(function(L){
      var title=el('input',{type:'text',value:L.title}),tgt=el('textarea',{class:'s'}),plan=el('textarea',{class:'s'}),ppt=el('textarea',{class:'s'}),ex=el('textarea',{class:'s'}),cl=el('textarea',{class:'s'});
      tgt.value=L.coreTarget;plan.value=L.teacherPlan;ppt.value=L.ppt.join('\n');ex.value=L.examples.join('\n');cl.value=L.closureTraining;
      function ls(t){return t.value.split('\n').map(function(x){return x.trim()}).filter(Boolean)}
      box.appendChild(el('div',{class:'muted',text:'课题'}));box.appendChild(title);
      box.appendChild(el('div',{class:'muted',text:'本节目标'}));box.appendChild(tgt);
      box.appendChild(el('div',{class:'muted',text:'教学流程'}));box.appendChild(plan);
      box.appendChild(el('div',{class:'muted',text:'PPT 页（每行一页标题）'}));box.appendChild(ppt);
      box.appendChild(el('div',{class:'muted',text:'例题（每行一条）'}));box.appendChild(ex);
      box.appendChild(el('div',{class:'muted',text:'课后练习'}));box.appendChild(cl);
      box.appendChild(el('button',{text:'保存教案',onclick:function(){
        api('/teacher/weekend/lessons/'+r.lessonId,{method:'PUT',json:{title:title.value,coreTarget:tgt.value,teacherPlan:plan.value,closureTraining:cl.value,examples:ls(ex),ppt:ls(ppt)}}).then(function(){note('ok','教案已保存')}).catch(function(e){note('error',e.message)})}}));
      var qbox=el('div');box.appendChild(el('h2',{text:'习题（AI 草稿需要你通过后才会给学生）'}));box.appendChild(qbox);
      function loadQ(){
        qbox.textContent='';
        api('/teacher/weekend/lessons/'+r.lessonId+'/questions').then(function(d){
          if(!d.items.length){qbox.appendChild(el('div',{class:'muted',text:'还没有习题。'}));return}
          d.items.forEach(function(q){
            var opts=q.options.map(function(o,i){return 'ABCD'[i]+'. '+o+(i===q.correctIndex?' ✓':'')}).join('　');
            var row=el('div',{class:'item'},el('span',{class:'t'},el('b',{text:q.stem}),el('div',{class:'muted',text:opts}),el('div',{class:'muted',text:q.explanation||''})));
            var act=el('div',{class:'row'},el('span',{class:'tag '+(q.active?'ok':'warn'),text:q.active?'已通过':'草稿'}));
            if(!q.active){
              act.appendChild(el('button',{text:'通过',onclick:function(){api('/teacher/weekend/lessons/'+r.lessonId+'/questions',{json:{approve:[q.id]}}).then(loadQ)}}));
              act.appendChild(el('button',{text:'删除',onclick:function(){api('/teacher/weekend/lessons/'+r.lessonId+'/questions',{json:{remove:[q.id]}}).then(loadQ)}}));
            }
            qbox.appendChild(row);qbox.appendChild(act);
          });
        });
      }
      loadQ();
    }).catch(function(e){box.appendChild(el('div',{class:'notice error',text:e.message}))});
  }
  function load(){api('/teacher/weekend/schedule?subject='+encodeURIComponent(SUBJ)).then(function(d){paintRows(d.items)}).catch(function(e){list.appendChild(el('div',{class:'notice error',text:e.message}))})}
  load();
}
boot(plan);
"""

STUDENT_BOOT = r"""
function boot_student(run){
  obtainToken().then(function(t){TOKEN=t;if(!TOKEN){msg('请先登录后再打开');return}
    return api('/session').then(function(s){if(s.role!=='student'){msg('这个页面给学生使用');return}run()})}).catch(function(e){msg(e.message||'打不开')});
}
"""


def practice_page_html() -> str:
    return _page("课堂练习", STUDENT_BOOT + WRITTEN_JS + PRACTICE_JS, True)


def plan_page_html() -> str:
    return _page("周末课备课", PLAN_JS, True, ("/v1/weekend", "返回周末课"))


def brief_page_html() -> str:
    return _page("周末课简报", PARENT_JS, True)


def control_page_html() -> str:
    return _page("周末课", WRITTEN_JS + CONTROL_JS, True, ("/v1/workspace", "返回"))


def board_page_html() -> str:
    return _page("课堂大屏", BOARD_JS, False)


__all__ = ["board_page_html", "brief_page_html", "control_page_html", "plan_page_html", "practice_page_html"]

