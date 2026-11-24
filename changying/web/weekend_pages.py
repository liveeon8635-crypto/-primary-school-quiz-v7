"""周末课页面:老师控制条 + 大屏 (static HTML, ES5)."""

from __future__ import annotations

from changying.web.design_system import apply_surface

from changying.web.classroom_window_handoff import OPEN_WINDOW_JS, PAGE_AUTH_JS
from changying.web.homework_assistant_pages import PAGE_CSS
from changying.web.weekend_written_pages import WRITTEN_JS
from changying.web.weekend_backup_pages import BACKUP_JS
from changying.web.weekend_report_pages import MARK_JS, PARENT_JS, REPORT_JS
from changying.web.weekend_courseware_pages import COURSEWARE_JS, COURSEWARE_PLAN_JS

COMMON_JS = r"""
__PAGE_AUTH__
function growTextarea(n){if(!n||!n.isConnected)return;n.style.height='auto';n.style.height=Math.max(64,n.scrollHeight+2)+'px';n.style.overflowY='hidden'}
function questionFigureImg(fig){
  if(!fig||fig.type!=='uploaded_image'||!/^data:image\/(jpeg|png);base64,/.test(String(fig.data_url||'')))return null;
  return el('img',{src:fig.data_url,alt:fig.alt||'原卷插图',style:'display:block;max-width:100%;max-height:320px;object-fit:contain;margin:8px 0;border:1px solid #e5e8f0;border-radius:8px'});
}
function renderQuestionFigure(box,fig,big){
  if(!box||!fig||!fig.type)return false;
  if(!big&&fig.type==='uploaded_image'){var img=questionFigureImg(fig);if(img){box.appendChild(img);return true}return false}
  if(typeof cwFigure==='function'){cwFigure(box,fig,!!big,{step:0},false,0);return true}
  var fallback=questionFigureImg(fig);if(fallback){box.appendChild(fallback);return true}
  return false;
}
var el=function(tag,attrs){
  var n=document.createElement(tag);
  Object.keys(attrs||{}).forEach(function(k){
    if(k==='class')n.className=attrs[k];else if(k==='text')n.textContent=attrs[k];
    else if(k.slice(0,2)==='on')n.addEventListener(k.slice(2),attrs[k]);
    else if(attrs[k]===true)n.setAttribute(k,'');else if(attrs[k]!==false&&attrs[k]!=null)n.setAttribute(k,attrs[k]);
  });
  for(var i=2;i<arguments.length;i++){var c=arguments[i];if(c==null)continue;n.appendChild(typeof c==='string'?document.createTextNode(c):c)}
  if(tag==='textarea'){n.addEventListener('input',function(){growTextarea(n)});requestAnimationFrame(function(){growTextarea(n)})}
  return n;
};
var root=document.getElementById('app'),TOKEN='';
function api(path,opts){
  opts=opts||{};opts.headers=Object.assign({Authorization:'Bearer '+TOKEN},opts.headers||{});opts.cache='no-store';
  if(opts.json!==undefined){opts.method=opts.method||'POST';opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(opts.json);delete opts.json}
  return fetch(path,opts).then(function(r){return r.json().catch(function(){return {}}).then(function(d){
    if(!r.ok){var e=new Error((d&&d.detail&&typeof d.detail==='string'&&d.detail)||('请求失败（'+r.status+'）'));e.status=r.status;throw e}return d})});
}
function chooseWeekendClass(save){
  var overlay=el('div',{class:'card',role:'dialog','aria-label':'选择上课班级',style:'position:fixed;inset:10vh 10vw;z-index:10000;overflow:auto;background:white;box-shadow:0 0 0 100vmax #0008'}),out=el('div'),feedback=el('div',{role:'status'});
  overlay.appendChild(el('h2',{text:'选择本次上课的班级'}));overlay.appendChild(el('p',{text:'只添加所选班级的学生，课堂练习、批改和积分都使用这份名单。'}));overlay.appendChild(out);overlay.appendChild(feedback);
  overlay.appendChild(el('button',{text:'取消',onclick:function(){overlay.remove()}}));document.body.appendChild(overlay);
  api('/teacher/weekend/classes').then(function(d){
    if(!d.items.length){feedback.textContent='还没有班级，请先在“我的班级”创建班级并添加学生';return}
    d.items.forEach(function(c){var b=el('button',{text:c.name+'（'+c.studentCount+'人）',disabled:!c.studentCount,onclick:function(){
      Array.prototype.forEach.call(out.querySelectorAll('button'),function(x){x.disabled=true});feedback.textContent='正在添加班级…';
      Promise.resolve().then(function(){return save(c.id)}).then(function(){overlay.remove()}).catch(function(e){feedback.textContent=e.message;Array.prototype.forEach.call(out.querySelectorAll('button'),function(x){x.disabled=false})});
    }});out.appendChild(el('div',{class:'row'},b))});
  }).catch(function(e){feedback.textContent=e.message});
}
function createWeekendClassroom(lessonId){
  function openChooser(){
    chooseWeekendClass(function(classId){return api('/teacher/weekend/sessions',{json:{lessonId:lessonId,classId:classId,requireReady:true}}).then(function(d){location.href='/v1/weekend?s='+d.id})});
  }
  api('/teacher/weekend/lessons/'+lessonId+'/questions').then(function(q){
    var s=q&&q.summary;
    if(s&&(s.courseType==='reading'||s.courseType==='writing')&&s.canStart===false){
      alert('不能开课：'+(s.startReasons||[]).join('；'));return;
    }
    if(s&&s.coursewareApproved===false){
      var cwState=s.coursewareStatus?'待审核':'未生成';
      if(!confirm('本节课的互动课件尚未审核通过（状态：'+cwState+'）。建议先在“审改 → 互动课件”中核对通过后再开课；确定仍要继续开课吗？'))return;
    }
    openChooser();
  },openChooser);
}
function fmt(sec){var neg=sec<0,s=Math.abs(sec),m=Math.floor(s/60),r=s%60;return (neg?'超时 ':'')+(m<10?'0':'')+m+':'+(r<10?'0':'')+r}
function msg(text){root.textContent='';root.appendChild(el('div',{class:'card'},el('h2',{text:text})))}
function boot(run){
  obtainToken().then(function(t){TOKEN=t;if(!TOKEN){msg('请先登录后再打开');return}
    return api('/session').then(function(s){if(s.role!=='teacher'){msg('只有老师可以使用');return}run()})}).catch(function(e){msg(e.message||'打不开')});
}
"""

CONTROL_JS = BACKUP_JS + r"""
var SID=+(new URLSearchParams(location.search).get('s')||0),timer=null,remain=null,tick=null;
function control(){
  root.textContent='';
  if(!SID){picker();return}
  var back=document.querySelector('header a');if(back){back.href='/v1/weekend';back.textContent='返回周末课'}
  var head=el('div',{class:'card'}),stagesBox=el('div',{class:'card'}),content=el('div',{class:'card'}),msgBox=el('div'),
      progBox=el('div',{class:'card'}),hintBox=el('div',{class:'card'}),peerBox=el('div',{class:'card'}),scoreBox=el('div',{class:'card'});
  root.appendChild(head);root.appendChild(stagesBox);root.appendChild(content);root.appendChild(progBox);root.appendChild(peerBox);root.appendChild(el('div',{class:'card'},el('h2',{text:'课后总结与家长反馈'}),el('div',{class:'muted',text:'用本节已有的提交与批改记录查看全班汇总，为每位学生生成学情草稿，编辑、预览后再发布给家长；不会结算积分或公布答案。'}),
    el('a',{class:'btn primary',href:'/v1/weekend-report?s='+SID,text:'打开课后总结与家长反馈'})));root.appendChild(scoreBox);root.appendChild(hintBox);root.appendChild(msgBox);
  var hintDetails=el('details',{},el('summary',{text:'提示准备（课前使用）'}));hintBox.appendChild(hintDetails);hintsCard(hintDetails);
  var peerDetails=el('details',{},el('summary',{text:'请同学讲解（复盘时使用）'}));peerBox.appendChild(peerDetails);peerCard(peerDetails);
  var scoreDetails=el('details',{},el('summary',{text:'课后积分结算'}));scoreBox.appendChild(scoreDetails);scoreCard(scoreDetails);
  var writtenBox=el('div',{class:'card'});root.appendChild(writtenBox);var updateWritten=writtenTeacher(writtenBox);
  var backupBox=el('div',{class:'card'});root.appendChild(backupBox);backupTeacher(backupBox);
  function post(path,body){return api('/teacher/weekend/sessions/'+SID+'/'+path,{json:body||{}}).then(paint).catch(function(e){msgBox.textContent='';msgBox.appendChild(el('div',{class:'notice error',text:e.message}))})}
  var lastHeadKey='',lastStagesKey='',lastContentKey='',activeCwBox=null,clockNode=null;
  function paint(d){
    remain=d.remainingSeconds;progress(progBox,d);
    var running=d.status==='running';updateWritten(d.status,d.class?d.class.id:0);
    var headKey=JSON.stringify({title:d.title||'',cls:d.class||null,status:d.status||'',currentStage:d.currentStage||0,stageCount:d.stageCount||0,stageName:d.stageName||'',goal:d.goal||'',covered:!!d.covered});
    if(headKey!==lastHeadKey){
      head.textContent='';
      head.appendChild(el('h2',{text:d.title}));
      head.appendChild(el('div',{class:d.class?'notice ok':'notice warn',text:d.class?'上课班级：'+d.class.name+' · '+d.class.studentCount+'人':'本节课尚未指定班级，请先选择班级'}));
      head.appendChild(el('button',{text:d.class?'更换上课班级':'选择上课班级',onclick:function(){chooseWeekendClass(function(classId){return api('/teacher/weekend/sessions/'+SID+'/class',{method:'PUT',json:{classId:classId}}).then(paint)})}}));
      clockNode=el('div',{style:'font-size:44px;font-weight:700;line-height:1.2',id:'clock',text:running&&remain!=null?fmt(remain):'--:--'});
      head.appendChild(el('div',{class:'muted',text:d.status==='planned'?'还没开始':d.status==='finished'?'已结束':'第 '+d.currentStage+'/'+d.stageCount+' 环节：'+d.stageName+' · '+d.goal}));
      head.appendChild(clockNode);
      var row=el('div',{class:'row'});
      if(d.status==='planned')row.appendChild(el('button',{class:'primary',text:'开始上课',disabled:!d.class,onclick:function(){post('start')}}));
      if(running){
        row.appendChild(el('button',{text:'‹ 上一环节',onclick:function(){post('prev')}}));
        row.appendChild(el('button',{class:'primary',text:d.currentStage>=d.stageCount?'结束这节课':'下一环节 ›',onclick:function(){post('next')}}));
        row.appendChild(el('button',{text:'延长 5 分钟',onclick:function(){post('extend',{minutes:5})}}));
        row.appendChild(el('button',{class:d.covered?'on':'',text:d.covered?'大屏已遮盖（点击恢复）':'遮盖大屏',onclick:function(){post('cover',{covered:!d.covered})}}));
        row.appendChild(el('button',{text:'提前结束',onclick:function(){if(confirm('确定提前结束这节课？'))post('finish')}}));
      }
      row.appendChild(el('a',{class:'btn',href:'/v1/weekend-board?s='+SID,target:'_blank','data-cy-open-window':'1',text:'打开大屏'}));
      head.appendChild(row);
      head.appendChild(el('details',{},el('summary',{text:'投影与异屏控制怎么用'}),el('p',{text:'同一台电脑：将显示模式设为“扩展”，把大屏窗口拖到投影／第二显示器并全屏，老师控制页留在电脑上。'}),el('p',{text:'手机／平板控制另一台电脑：两台设备各自登录同一老师账号，进入同一节课堂；电脑打开大屏，手机／平板操作控制页。翻页、环节和遮盖约3秒内同步，网络延迟时可能更久。'})));
      lastHeadKey=headKey;
    }else if(clockNode){
      clockNode.textContent=running&&remain!=null?fmt(remain):'--:--';
    }
    var stagesKey=JSON.stringify({status:d.status||'',currentStage:d.currentStage||0,stages:d.stages||[]});
    if(stagesKey!==lastStagesKey){
      stagesBox.textContent='';
      stagesBox.appendChild(el('h2',{text:'环节'}));
      d.stages.forEach(function(s){
        var b=el('button',{class:s.no===d.currentStage&&running?'on':'',text:s.no+'. '+s.name+'（'+(s.minutes+s.extendMin)+'分）'+(s.visited&&s.no!==d.currentStage?' ✓':''),
          onclick:function(){if(running)post('goto',{stage:s.no})}});
        stagesBox.appendChild(el('div',{class:'row'},b,el('span',{class:'muted',text:s.goal})));
      });
      lastStagesKey=stagesKey;
    }
    var cw=d.courseware||null;
    var canNextStage=running&&d.currentStage<d.stageCount;
    var contentKey=JSON.stringify({
      status:d.status||'',covered:!!d.covered,currentStage:d.currentStage||0,canNextStage:canNextStage,
      answerRelease:d.answerRelease||null,pendingPracticeSync:d.pendingPracticeSync||0,
      deck:d.deck||null,content:d.content||[],coursewareNotice:d.coursewareNotice||'',
      practiceFigure:d.practiceFigure||null,
      cw:cw?{id:cw.id||null,kind:cw.kind||'',kindLabel:cw.kindLabel||'',stageNo:cw.stageNo,page:cw.page===undefined?null:cw.page,params:cw.params||null}:null
    });
    if(contentKey!==lastContentKey){
      content.textContent='';activeCwBox=null;
      content.appendChild(el('h2',{text:'当前环节大屏内容'}));
      if(running&&d.answerRelease&&d.answerRelease.currentQuestion){
        var release=d.answerRelease,current=release.currentQuestion;
        content.appendChild(el('div',{class:'notice',text:'已公布 '+release.published+' / '+release.total+' 题；只停止已公布题目的提交，其他题继续作答。'}));
        var actRow=el('div',{class:'row'});
        if(!release.currentPublished&&release.currentOpen===false){
          actRow.appendChild(el('button',{class:'primary',text:'开放第 '+current+' 题给学生作答',onclick:function(){post('practice-question',{question:current})}}));
        }
        actRow.appendChild(el('button',{class:release.currentOpen===false?'':'primary',text:release.currentPublished?'第 '+current+' 题答案已公布':'统一公布第 '+current+' 题答案',disabled:!!release.currentPublished||current!==release.nextQuestion,onclick:function(){if(confirm('公布第 '+current+' 题答案后，仅本题停止接收提交，其他题可继续作答。确定公布吗？'))post('publish-answers',{question:current})}}));
        if(release.nextQuestion&&current!==release.nextQuestion)actRow.appendChild(el('button',{text:'继续第 '+release.nextQuestion+' 题',onclick:function(){post('practice-question',{question:release.nextQuestion})}}));
        content.appendChild(actRow);
        if(!release.currentPublished&&release.currentOpen===false)content.appendChild(el('div',{class:'notice warn',text:'第 '+current+' 题尚未开放给学生，点击“开放第 '+current+' 题给学生作答”后学生端即可同步看到本题。'}));
      }
      if(d.pendingPracticeSync>0&&d.status!=='finished'){
        var syncBtn=el('button',{class:'primary','data-sync-practice':'1',text:'同步新增练习（+'+d.pendingPracticeSync+' 题）',onclick:function(){
          syncBtn.disabled=true;
          api('/teacher/weekend/sessions/'+SID+'/sync-practice',{json:{}}).then(function(res){
            msgBox.textContent='';msgBox.appendChild(el('div',{class:'notice',text:res.message||'已同步新增练习'}));
            paint(res);
          }).catch(function(e){syncBtn.disabled=false;msgBox.textContent='';msgBox.appendChild(el('div',{class:'notice error',text:e.message}))});
        }});
        content.appendChild(el('div',{class:'row'},syncBtn,el('span',{class:'muted',text:'仅把新通过的练习补进本节课堂，已有作答与记录保持不变'})));
      }
      var isSlideDeckCw=!!(d.courseware&&d.courseware.kind==='slide'&&(d.courseType==='reading'||d.courseType==='writing'||(d.deck&&d.deck.total<=1)));
      if(d.deck&&!isSlideDeckCw){
        content.appendChild(el('div',{class:'row'},el('button',{text:'‹ 上一页',disabled:d.deck.index<=0,onclick:function(){post('slide',{delta:-1})}}),
          el('b',{text:'第 '+(d.deck.index+1)+' / '+d.deck.total+' 页'}),el('button',{class:'primary',text:'下一页 ›',disabled:d.deck.index>=d.deck.total-1,onclick:function(){post('slide',{delta:1})}})));
      }
      if(!d.content.length&&!d.courseware)content.appendChild(el('div',{class:'muted',text:running?(d.covered?'大屏遮盖中':'这个环节没有内容'):'开始上课后显示'}));
      if(d.content.length){
        if(isSlideDeckCw){
          var rawDet=el('details',{style:'margin:4px 0 8px'},el('summary',{class:'muted',style:'cursor:pointer;font-size:13px',text:'查看本环节原始教案文字（仅教师参考）'}));
          d.content.forEach(function(x){rawDet.appendChild(el('p',{style:'margin:6px 0;white-space:pre-wrap',text:x}))});
          content.appendChild(rawDet);
        }else{
          d.content.forEach(function(x){content.appendChild(el('p',{text:x}))});
        }
      }
      if(d.coursewareNotice)content.appendChild(el('div',{class:'notice warn',text:d.coursewareNotice}));
      if(d.courseware){var cwBox=el('div');content.appendChild(cwBox);activeCwBox=cwBox;cwControl(cwBox,d.courseware,SID,{canNextStage:canNextStage,onNextStage:function(){post('next')}})}
      else if(d.practiceFigure){var pfBox=el('div',{style:'margin:8px 0'});content.appendChild(pfBox);renderQuestionFigure(pfBox,d.practiceFigure,false)}
      if(running&&d.currentStage===6){
        var s6Wrap=el('div',{style:'margin-top:10px'}),s6Filter='pending',s6Data=null;content.appendChild(s6Wrap);
        function renderStage6(s6){
          s6Data=s6;s6Wrap.textContent='';
          s6Wrap.appendChild(el('h3',{text:'第 6 环节 · 逐题讨论达标确认'}));
          s6Wrap.appendChild(el('div',{class:'notice',text:'共 '+s6.total+' 道待巩固题 · 已达标 '+s6.mastered+' · 留入课后 '+s6.homework+' · 待讨论 '+s6.pending+(s6.doubtCount?' · 学生提问 '+s6.doubtCount+' 人次':'')}));
          if(!s6.items.length){s6Wrap.appendChild(el('div',{class:'notice ok',text:'本节所有随堂题均已当堂掌握，无需留入课后练习。'}));return}
          if(s6Filter==='pending'&&!s6.pending)s6Filter='all';
          var tabs=el('div',{class:'tabs',style:'margin:8px 0'});
          [['pending','待讨论（'+s6.pending+'）'],['all','全部（'+s6.total+'）'],['mastered','已达标（'+s6.mastered+'）'],['homework','留入课后（'+s6.homework+'）']].forEach(function(f){
            tabs.appendChild(el('button',{class:s6Filter===f[0]?'on':'',text:f[1],onclick:function(){s6Filter=f[0];renderStage6(s6Data)}}));
          });
          s6Wrap.appendChild(tabs);
          var list=s6.items.filter(function(it){
            if(s6Filter==='all')return true;
            if(s6Filter==='pending')return !it.teacherStatus;
            return it.teacherStatus===s6Filter;
          });
          if(!list.length)s6Wrap.appendChild(el('div',{class:'muted',text:'当前筛选下没有题目，可切换上方标签查看。'}));
          list.forEach(function(it){
            var card=el('div',{class:'card'});
            card.appendChild(el('b',{style:'display:block;overflow-wrap:anywhere',text:'第 '+it.no+' 题：'+it.stem}));
            if(it.wrongStudents&&it.wrongStudents.length)card.appendChild(el('div',{class:'muted',text:'待巩固同学：'+it.wrongStudents.join('、')}));
            (it.studentFeedback||[]).forEach(function(fb){
              card.appendChild(el('div',{class:fb.status==='doubt'?'notice warn':'notice ok',style:'margin:4px 0',text:fb.name+'：'+(fb.status==='doubt'?'还是不懂（留课后/提问）':'已听懂 ✓')+(fb.note?' — '+fb.note:'')}));
            });
            var rowBtn=el('div',{class:'row',style:'margin-top:6px'});
            var mBtn=el('button',{class:it.teacherStatus==='mastered'?'primary':'',text:it.teacherStatus==='mastered'?'讨论后已达标 ✓':'标记讨论后已达标',onclick:function(){mBtn.disabled=true;hBtn.disabled=true;mBtn.textContent='保存中…';markS6(it.questionKey,'mastered')}});
            var hBtn=el('button',{class:it.teacherStatus==='homework'?'primary':'',text:it.teacherStatus==='homework'?'已留入课后练习 ✓':'仍有疑问 → 留入课后练习',onclick:function(){mBtn.disabled=true;hBtn.disabled=true;hBtn.textContent='保存中…';markS6(it.questionKey,'homework')}});
            rowBtn.appendChild(mBtn);rowBtn.appendChild(hBtn);card.appendChild(rowBtn);
            s6Wrap.appendChild(card);
          });
          s6Wrap.appendChild(el('button',{text:'刷新学生提问与达标进度',onclick:loadStage6}));
        }
        function markS6(qkey,st){api('/teacher/weekend/sessions/'+SID+'/stage6-checks',{json:{questionKey:qkey,status:st}}).then(function(res){renderStage6(res);load()}).catch(function(e){alert(e.message);loadStage6()})}
        function loadStage6(){api('/teacher/weekend/sessions/'+SID+'/stage6-checks').then(renderStage6).catch(function(){})}
        loadStage6();
      }
      if(running&&d.currentStage>=7){
        var s7Summary=el('div',{class:'muted',style:'margin-top:6px',text:'正在汇总第 6 环节遗留错题…'});
        content.appendChild(el('div',{class:'notice ok',style:'margin-top:10px'},
          el('div',{text:'个性化课后练习已自动排除第 5 环节订正正确与第 6 环节已确认达标的题目，仅针对五六环节仍未解决的个人遗留错题生成带图衍生练习：'}),
          s7Summary,
          el('div',{class:'row',style:'margin-top:8px'},el('a',{class:'btn primary',href:'/v1/weekend-report?s='+SID,text:'按遗留错题生成并布置个性化课后练习'}))));
        api('/teacher/weekend/sessions/'+SID+'/stage6-checks').then(function(s6){
          s7Summary.textContent='第 6 环节汇总：共 '+s6.total+' 道待巩固题 · 已确认达标 '+s6.mastered+' 题 · 留入课后 '+s6.homework+' 题 · 待讨论 '+s6.pending+' 题'+(s6.doubtCount?' · 学生提问 '+s6.doubtCount+' 人次':'');
        }).catch(function(){s7Summary.textContent=''});
      }
      lastContentKey=contentKey;
    }else if(cw&&activeCwBox&&activeCwBox._cwSyncView){
      activeCwBox._cwSyncView(cw.view);
    }
  }
  var pollBusy=false;
  function load(){if(pollBusy)return;pollBusy=true;var version=CW_VERSION;api('/teacher/weekend/sessions/'+SID).then(function(d){pollBusy=false;if(!CW_PENDING&&version===CW_VERSION)paint(d)}).catch(function(e){pollBusy=false;msgBox.textContent='';msgBox.appendChild(el('div',{class:'notice error',text:e.message}))})}
  load();
  if(tick)clearInterval(tick);
  tick=setInterval(function(){if(remain!=null){remain-=1;if(clockNode)clockNode.textContent=fmt(remain)}},1000);
  if(timer)clearInterval(timer);
  timer=setInterval(function(){if(!document.hidden){load()}},15000);
  if(typeof document!=='undefined'&&document.addEventListener)document.addEventListener('visibilitychange',function(){if(!document.hidden){load()}});
}
function progress(box,d){
  if(!d.class){box.textContent='';return}
  if(d.status!=='running'&&d.status!=='finished'){box.textContent='';return}
  api('/teacher/weekend/sessions/'+SID+'/progress').then(function(p){
    if(p.items.length&&!p.items.some(function(i){return i.total>0})){box.textContent='';box.appendChild(el('p',{class:'muted',text:'本节没有选择题。文字／照片答案请在“学生作答与批改”中查看，也可在“请同学讲解”中选择已提交的同学。'}));return}
    box.textContent='';box.appendChild(el('h2',{text:'选择题进度（班级正确率 '+p.classCompletionRate+'%）'}));
    if(!p.items.length){box.appendChild(el('div',{class:'muted',text:'本节课没有学生，请检查所选班级的名单。'}));return}
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
  box.appendChild(el('div',{class:'muted',text:'先选一道题，再选同学讲解。文字／照片题按提交及批改状态列出，老师可请已提交的同学讲思路；选择题保留做对同学讲解及后续巩固规则。'}));
  var out=el('div'),msg=el('div'),go=el('button',{text:'查看可以讲的题',onclick:function(){load()}});
  box.appendChild(go);box.appendChild(out);box.appendChild(msg);
  function load(){
    out.textContent='';msg.textContent='';
    api('/teacher/weekend/sessions/'+SID+'/peer-suggest').then(function(d){
      out.appendChild(el('div',{class:'notice ok',text:d.message}));
      d.questions.forEach(function(q){
        var row=el('div',{class:'card'},el('b',{text:'第 '+q.no+' 题：'+q.stem}),
          el('div',{class:'muted',text:q.questionType==='written'?'文字／照片题 · '+q.submitted.map(function(x){return x.name+'（'+({pending:'待批改',correct:'正确',partial:'部分正确',revise:'需订正'}[x.result]||'已提交')+'）'}).join('、'):'做对：'+q.right.map(function(x){return x.name}).join('、')+'　·　没做对：'+q.wrong.map(function(x){return x.name}).join('、')}));
        var act=el('div',{class:'row'});
        var evalBox=el('div',{style:'margin-top:8px'});
        function renderFinishControl(r){
          var holder=el('div',{class:'row',style:'margin-top:6px;align-items:center;flex-wrap:wrap;gap:6px'});
          if(r.explainReview&&r.explainReview.finished){
            holder.appendChild(el('span',{class:'tag ok',text:r.name+' 已结束讲解 · '+r.explainReview.label+' · 讲题积分 +'+r.explainReview.points+(r.explainReview.comment?'（'+r.explainReview.comment+'）':'')}));
            evalBox.appendChild(holder);return;
          }
          if(r.explainResponse&&r.explainResponse.decision==='decline'){
            holder.appendChild(el('span',{class:'tag warn',text:r.name+'：'+r.explainResponse.label+'（可改请其他同学）'}));
          }else if(r.explainResponse&&r.explainResponse.decision==='accept'){
            holder.appendChild(el('span',{class:'tag ok',text:r.name+'：'+r.explainResponse.label}));
          }
          var sel=el('select');
          [['clear','思路清晰（+2分）'],['basic','基本讲清（+1分）'],['guided','需引导·鼓励参与（+1分）']].forEach(function(opt){sel.appendChild(el('option',{value:opt[0],text:opt[1]}))});
          var cmt=el('input',{placeholder:'给 '+r.name+' 的简短评语（选填）',maxlength:300,style:'min-width:180px'});
          var doneBtn=el('button',{class:'primary',text:'结束 '+r.name+' 讲解并评价',onclick:function(){
            doneBtn.disabled=true;msg.textContent='';
            api('/teacher/weekend/sessions/'+SID+'/explain/finish',{json:{tutorId:r.studentId,questionId:q.questionId,questionType:q.questionType||'choice',rating:sel.value,comment:cmt.value}}).then(function(res){
              msg.appendChild(el('div',{class:'notice ok',text:res.message}));
              r.explainReview=res.review;holder.textContent='';
              holder.appendChild(el('span',{class:'tag ok',text:r.name+' 已结束讲解 · '+res.review.label+' · 讲题积分 +'+res.review.points+(res.review.comment?'（'+res.review.comment+'）':'')}));
            }).catch(function(e){msg.appendChild(el('div',{class:'notice error',text:e.message}));doneBtn.disabled=false});
          }});
          holder.appendChild(el('span',{class:'muted',text:r.name+' 讲题中：'}));holder.appendChild(sel);holder.appendChild(cmt);holder.appendChild(doneBtn);
          evalBox.appendChild(holder);
        }
        (q.questionType==='written'?q.submitted:q.right).forEach(function(r){
          var b=el('button',{text:r.asked?'已请 '+r.name+' 讲过':'请 '+r.name+' 来讲',disabled:r.asked,onclick:function(){
            b.disabled=true;msg.textContent='';
            api('/teacher/weekend/sessions/'+SID+'/explain',{json:{tutorId:r.studentId,questionId:q.questionId,questionType:q.questionType||"choice"}}).then(function(res){msg.appendChild(el('div',{class:'notice ok',text:res.message}));b.textContent='已请 '+r.name+' 讲过';r.asked=true;renderFinishControl(r)})
              .catch(function(e){msg.appendChild(el('div',{class:'notice error',text:e.message}));b.disabled=false});
          }});
          act.appendChild(b);
          if(r.asked)renderFinishControl(r);
        });
        row.appendChild(act);row.appendChild(evalBox);out.appendChild(row);
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
      var expDetails=((i.why&&i.why.tutor&&i.why.tutor.explained)||[]).map(function(x){return '讲题('+x.label+' +'+x.points+'分'+(x.comment?'：'+x.comment:'')+')'}).join('、');
      var extra=expDetails?(' · '+expDetails):'';
      out.appendChild(el('div',{class:'row'},el('b',{text:i.name+'  共 '+i.total+' 分'}),el('span',{class:'muted',text:parts+extra+(i.why.progress.reason&&i.why.progress.reason!=='ok'?' · '+i.why.progress.reason:'')})));
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
  var scopeBox=el('div',{class:'muted',text:'正在加载本班学生范围…'}),scopeChecks=[];
  box.appendChild(scopeBox);
  function selectedHintSids(){
    return scopeChecks.filter(function(c){return c.checked}).map(function(c){return Number(c.value)});
  }
  api('/teacher/weekend/sessions/'+SID+'/progress').then(function(p){
    scopeBox.textContent='';
    var items=(p&&p.items)||[];
    if(!items.length){scopeBox.textContent='当前暂无已入班学生；可手动填写提示并审核通过。';return}
    scopeBox.appendChild(el('span',{text:'AI 生成适用学生：'}));
    items.forEach(function(it){
      var cb=el('input',{type:'checkbox',value:String(it.studentId),checked:true});
      scopeChecks.push(cb);
      scopeBox.appendChild(el('label',{style:'margin-right:8px'},cb,document.createTextNode(it.name||('学生'+it.studentId))));
    });
  }).catch(function(){scopeBox.textContent='请手动填写提示或确认学生授权范围'});
  var list=el('div');box.appendChild(list);
  api('/teacher/weekend/sessions/'+SID+'/questions').then(function(d){
    if(!d.items.length){list.appendChild(el('div',{class:'muted',text:'本节没有选择题提示。简答／写作题请在备课页审核题目及提示。'}));return}
    d.items.forEach(function(q){
      var tas=[0,1,2].map(function(i){var t=el('textarea',{class:'s',placeholder:'第'+(i+1)+'级：'+q.levelNames[i]});t.value=q.hints[i]||'';return t});
      var m=el('div'),tag=el('span',{class:'tag'});
      function lab(st){tag.className='tag '+(st==='approved'?'ok':'warn');tag.textContent=st==='approved'?'已审核':st==='auto'?'待审核':st==='draft'?'草稿':'未准备'}lab(q.hintStatus);
      function vals(){return tas.map(function(t){return t.value})}
      var body=el('div',{hidden:true});
      var ai=el('button',{text:'AI 写草稿',onclick:function(){m.textContent='';ai.disabled=true;
        api('/teacher/weekend/hints/generate',{json:{questionId:q.id,studentIds:selectedHintSids()}}).then(function(r){r.hints.forEach(function(h,i){tas[i].value=h});lab('draft');m.appendChild(el('div',{class:'notice ok',text:'已生成草稿，请核对后审核通过'}))})
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
    var isChinese=HSUBJ==='语文';
    var ready=x.hasPlan&&(isChinese?!(x.pendingMaterials>0)&&!!x.courseType&&!!x.coursewareApproved:x.practiceReady>0);
    stepsBox.appendChild(step(!!x.schoolUnit,'① 填学校进度','让系统知道这一周学校讲到哪里；学校调课可以一键顺延',go('去填')));
    stepsBox.appendChild(step(x.hasPlan,'② 准备教案','没有教案就点“AI 备课草稿”，生成后你改一改',go('去备课')));
    if(isChinese){
      stepsBox.appendChild(step(!!x.coursewareApproved,'③ 核对六环节课件','查看每个环节的素材与草稿，核对原文后逐页审核；生成不等于审核通过',go('去预览')));
    }else{
      stepsBox.appendChild(step(x.practiceReady>0,'③ 准备习题（可用练习 '+x.practiceReady+' 道'+(x.draftQuestions?'，待审核 '+x.draftQuestions+' 道':'')+'）','AI 出的题是草稿，逐题点“通过”且不与例题重复后学生才能做',go('去审核')));
    }
    var start=el('button',{class:'primary',text:'④ 开课',disabled:!ready,onclick:function(){
      createWeekendClassroom(x.lessonId);
    }});
    stepsBox.appendChild(step(false,'④ 开课','点开后进入上课页：开始上课、按 '+(isChinese?'6':'7')+' 个环节推进、打开大屏。'+(ready?'':'（先完成上面三步）'),start));
    stepsBox.appendChild(el('div',{class:'muted',text:'下课后在同一个上课页点“预览得分→确认结算”；在“课后总结与家长反馈”为每位学生生成、审核并发布学情反馈。'}));
    if(x.weakKnowledge.length)stepsBox.appendChild(el('div',{class:'notice warn',text:'班里近期错得最多：'+x.weakKnowledge.map(function(w){return w.knowledge+'（'+w.count+' 次）'}).join('、')+'，备课时可以重点安排。'}));
  }).catch(function(e){stepsBox.appendChild(el('div',{class:'notice error',text:e.message}))});
  recent.appendChild(el('h2',{text:'最近的课堂'}));
  var rlist=el('div');recent.appendChild(rlist);
  api('/teacher/weekend/sessions').then(function(d){
    if(!d.items.length){rlist.appendChild(el('div',{class:'muted',text:'还没有。'}));return}
    d.items.forEach(function(s){rlist.appendChild(el('div',{class:'row'},el('a',{href:'/v1/weekend?s='+s.id,text:s.title}),el('span',{class:'muted',text:s.createdAt+' · '+(s.status==='finished'?'已结束':s.status==='running'?'进行中':'未开始')}),
      s.status==='planned'?null:el('a',{class:'btn',href:'/v1/weekend-report?s='+s.id,text:'课后总结与家长反馈'})))});
  }).catch(function(e){rlist.appendChild(el('div',{class:'notice error',text:e.message||'加载失败'}))});
  recent.appendChild(el('hr'));
  recent.appendChild(el('div',{class:'row'},el('a',{class:'btn',href:'/v1/weekend-plan',text:'18 次课进度表与备课'}),el('a',{class:'btn',href:'/v1/knowledge',text:'知识点讲解卡片（学生搜索、错题讲解）'})));
}
boot(control);
"""

# 大屏排版：不改教案文字和分页，只按每行开头自动分层——考点/知识点（黄色标题的知识卡）、规则行冒号后的例子（浅蓝）、
# 示例/例题（浅色例题卡，带空括号的题排成整齐的格子）、易错/注意（红色提醒）。宽屏时知识卡在左、例题卡在右。
BOARD_LAYOUT_JS = r"""
var BL_HEAD=/^(考点|知识点|重点|难点|方法|规律|结论)[一二三四五六七八九十0-9]*\s*[：:、．.\s]/;
var BL_EXAMPLE=/^(示例|例题|例\s*[0-9一二三四五六七八九十]|练一练|试一试|做一做|想一想)/;
var BL_WARN=/^(易错|注意|提醒|易混|误区)[点：:\s]/;
var BL_ANSWER=/^(?:【\s*(?:参考答案|答案|解答|解析)\s*】|((参考答案|答案|解答)([／\/][^：:]{1,6})?|答)\s*[：:])/,BL_SHOWN={},BL_COVER=true;     // cover answers only while explaining (stages 2-3)
var BL_QUESTION=/^(选择题|判断题|填空题|计算题|文字／照片题|第\s*[0-9一二三四五六七八九十]+\s*题)/;
var BL_BLANK=/[（(][\s　_＿]*[）)]|_{2,}|＿{2,}/;
function blMath(t){return /[=＝×÷+＋−\-<>＜＞]/.test(t)&&/[0-9a-zA-Z²³]/.test(t)}
function blParse(texts){
  var blocks=[],cur=null;
  function open(kind,title){cur={kind:kind,title:title,lines:[]};blocks.push(cur);return cur}
  texts.forEach(function(text){String(text||'').split('\n').forEach(function(raw){
    var line=raw.replace(/\s+$/,'').replace(/^\s+/,'');if(!line)return;
    if(BL_HEAD.test(line)){var k=line.search(/[：:]/);open('know',k>0&&k<16?line.slice(0,k)+'　'+line.slice(k+1).trim():line);return}
    if(BL_EXAMPLE.test(line)){
      var rest=line.replace(/^示例\s*[：:]\s*/,''),cut=-1,re=/[：:]/g,m;
      while((m=re.exec(rest))){if(BL_BLANK.test(rest.slice(m.index+1))||blMath(rest.slice(m.index+1))){cut=m.index;break}}
      if(cut<0){var k2=rest.search(/[：:]/);if(k2>0&&k2<=20)cut=k2}      // "例题13 中点问题：点B是…" -> short title, problem as text
      var b=open('example',cut>0?rest.slice(0,cut).replace(/\s*[|｜]\s*/,'　'):rest.replace(/\s*[|｜]\s*/,'　'));
      if(cut>0)b.lines.push(rest.slice(cut+1).trim());
      return;
    }
    if(!cur)cur=open('plain','');
    cur.lines.push(line);
  })});
  return blocks;
}
function blItems(line){
  // "当a＝2.5时，求下面各式的值：5×a＝（ ）1.2a＝（ ）…" -> the lead-in as text, then one short item per blank,
  // so a question never breaks in the middle. Long items (a sentence with a blank) are not put in the grid.
  if(!BL_BLANK.test(line))return null;
  var out=[],re=/[（(][\s　_＿]*[）)]|_{2,}|＿{2,}/g,last=0,m,lead='';
  while((m=re.exec(line))){var stem=line.slice(last,m.index).trim();if(!stem&&!out.length)return null;out.push(stem);last=m.index+m[0].length}
  if(out.length<2)return null;
  var k=Math.max(out[0].lastIndexOf('：'),out[0].lastIndexOf(':'));
  if(k>=0){lead=out[0].slice(0,k+1).trim();out[0]=out[0].slice(k+1).trim()}
  if(out.some(function(q){return !q||q.length>14||!/[=＝]$|[×÷+＋−\-]/.test(q)}))return null;   // only short calculations go in the grid
  return {lead:lead,items:out,tail:line.slice(last).trim().replace(/^[；;，,]\s*/,'')};
}
function blParts(line){
  // "（1）…；（2）…；（3）…" on one line -> one line per part, so each part starts on its own row.
  if(!/[（(]1[）)]/.test(line))return [line];
  return line.split(/[；;]?\s*(?=[（(][2-9][）)])/).map(function(x){return x.trim()}).filter(Boolean);
}
function blBlanks(box,line,color){
  // Text with its blanks drawn as underlines, wrapping normally.
  var row=el('div',{style:'margin:.3em 0'}),re=/[（(][\s　_＿]*[）)]|_{2,}|＿{2,}/g,last=0,m;
  while((m=re.exec(line))){row.appendChild(el('span',{text:line.slice(last,m.index)}));row.appendChild(el('span',{style:'display:inline-block;width:3.2em;border-bottom:.12em solid '+color+';margin:0 .2em'}));last=m.index+m[0].length}
  row.appendChild(el('span',{text:line.slice(last)}));box.appendChild(row);
}
function blLine(line,number){
  if(BL_WARN.test(line))return el('div',{style:'color:#fca5a5;font-weight:700;margin:.35em 0',text:'⚠ '+line});
  var k=line.search(/[：:]/),row=el('div',{style:'display:flex;gap:.5em;align-items:baseline;margin:.3em 0'});
  if(number)row.appendChild(el('span',{style:'flex:none;background:#fbbf24;color:#0f172a;border-radius:50%;width:1.35em;height:1.35em;line-height:1.35em;text-align:center;font-weight:800;font-size:.8em',text:String(number)}));
  var body=el('span',{});row.appendChild(body);
  if(BL_QUESTION.test(line))k=-1;                      // "选择题 1：…" is a question, not a rule with an example
  var eg=k>0?line.slice(k+1).trim():'',steps=eg.split(/[；;]/).map(function(x){return x.trim()}).filter(Boolean);
  if(k>0&&k<20&&eg.length>30&&steps.length>=3){
    // "四步走：写式子；把字母换成数…；…" -> the steps one under another, in white; only short examples are blue.
    body.appendChild(el('span',{style:'font-weight:700',text:line.slice(0,k)}));
    steps.forEach(function(x){body.appendChild(el('div',{style:'margin:.15em 0 0 .2em',text:'· '+x.replace(/[。.]$/,'')}))});
  }else if(k>0&&blMath(eg)){body.appendChild(el('span',{text:line.slice(0,k)+'　'}));body.appendChild(el('span',{style:'color:#7dd3fc'+(eg.length<=24?';white-space:nowrap':''),text:eg}))}
  else body.appendChild(el('span',{text:line}));
  return row;
}
function blExampleLine(box,line){
  if(BL_ANSWER.test(line)){box.appendChild(blAnswer(line,false));return}
  blParts(line).forEach(function(part){
    var it=blItems(part);
    if(BL_WARN.test(part)){box.appendChild(el('div',{style:'color:#b42318;font-weight:700;margin:.3em 0',text:'⚠ '+part}));return}
    if(!it){if(BL_BLANK.test(part))blBlanks(box,part,'#0369a1');else box.appendChild(el('div',{style:'margin:.3em 0',text:part}));return}
    if(it.lead)box.appendChild(el('div',{style:'margin:.3em 0',text:it.lead}));
    var grid=el('div',{style:'display:grid;grid-template-columns:repeat(auto-fill,minmax(9em,1fr));gap:.4em 1.2em;margin:.3em 0 .3em 1em'});
    it.items.forEach(function(q){grid.appendChild(el('div',{style:'white-space:nowrap'},el('span',{text:q}),el('span',{style:'display:inline-block;width:3.2em;border-bottom:.12em solid #0369a1;margin-left:.2em'})))});
    box.appendChild(grid);if(it.tail)box.appendChild(el('div',{style:'margin:.3em 0',text:it.tail}));
  });
}
function blAnswer(line,dark){
  if(!BL_COVER)return el('div',{style:'font-weight:700;margin:.4em 0;color:'+(dark?'#86efac':'#15803d'),text:line});
  // Covered until the teacher clicks; stays open across the 3-second refresh (kept per answer text).
  var box=el('div',{style:'margin:.4em 0'}),shown=!!BL_SHOWN[line];
  var text=el('div',{style:'font-weight:700;color:'+(dark?'#86efac':'#15803d')+(shown?'':';display:none'),text:line});
  var btn=el('button',{type:'button',style:'font:inherit;font-size:.8em;padding:.2em .8em;border-radius:.4em;border:1px solid '+(dark?'#86efac':'#15803d')+';background:transparent;color:'+(dark?'#86efac':'#15803d')+';cursor:pointer',
    text:shown?'隐藏答案':'显示答案',onclick:function(){BL_SHOWN[line]=!BL_SHOWN[line];text.style.display=BL_SHOWN[line]?'':'none';btn.textContent=BL_SHOWN[line]?'隐藏答案':'显示答案';if(window.blRefit)window.blRefit()}});
  box.appendChild(btn);box.appendChild(text);return box;
}
function boardLayout(body,texts,wide){
  var blocks=blParse(texts),know=[],examples=[],plain=[];
  blocks.forEach(function(b){
    if(b.kind==='know'){
      var card=el('div',{style:'background:#13284a;border-left:.3em solid #fbbf24;border-radius:.5em;padding:.5em .8em;margin:0 0 .6em'},el('div',{style:'color:#fbbf24;font-weight:800;font-size:1.15em;margin-bottom:.2em',text:b.title}));
      var n=0,lines=[];
      // "加法交换律：a＋b＝b＋a；加法结合律：…；…" -> one numbered rule per law.
      b.lines.forEach(function(l){var parts=l.split(/[；;]/).map(function(x){return x.trim()}).filter(Boolean);
        if(parts.length>=2&&parts.every(function(x){var k=x.search(/[：:]/);return k>0&&k<=12&&blMath(x.slice(k+1))}))lines=lines.concat(parts);else lines.push(l)});
      lines.forEach(function(l){if(BL_ANSWER.test(l)){card.appendChild(blAnswer(l,true));return}var rule=!BL_WARN.test(l)&&!BL_QUESTION.test(l)&&l.search(/[：:]/)>0&&blMath(l.slice(l.search(/[：:]/)+1));card.appendChild(blLine(l,rule?++n:0))});
      know.push(card);
    }else if(b.kind==='example'){
      var ex=el('div',{style:'background:#e0f2fe;color:#0f172a;border-radius:.5em;padding:.5em .8em;margin:0 0 .6em'},el('div',{style:'color:#0369a1;font-weight:800;font-size:1.05em;margin-bottom:.2em',text:b.title}));
      b.lines.forEach(function(l){blExampleLine(ex,l)});examples.push(ex);
    }else{var box=el('div',{style:'margin:0 0 .4em'});b.lines.forEach(function(l){
      // The lesson title is already in the header: keep it, quietly.
      if(BL_ANSWER.test(l)){box.appendChild(blAnswer(l,true));return}
      box.appendChild(/^课题[：:]/.test(l)?el('div',{style:'opacity:.6;font-size:.7em;margin:.2em 0',text:l}):blLine(l,0))});plain.push(box)}
  });
  body.style.whiteSpace='normal';
  plain.forEach(function(x){body.appendChild(x)});
  if(wide&&know.length&&examples.length){
    var cols=el('div',{style:'display:grid;grid-template-columns:1fr 1fr;gap:1.2em;align-items:start'}),left=el('div'),right=el('div');
    know.forEach(function(x){left.appendChild(x)});examples.forEach(function(x){right.appendChild(x)});cols.appendChild(left);cols.appendChild(right);body.appendChild(cols);
  }else{
    var ki=0,ei=0;            // narrow screen, or only one kind: the teacher's order
    blocks.forEach(function(b){if(b.kind==='know')body.appendChild(know[ki++]);else if(b.kind==='example')body.appendChild(examples[ei++])});
  }
  return {know:know.length,examples:examples.length};
}
"""

BOARD_JS = r"""
var SID=+(new URLSearchParams(location.search).get('s')||0);
function board(){
  if(!SID){msg('缺少课堂编号');return}
  document.body.style.background='#0f172a';document.body.style.overflow='hidden';
  var wrap=el('div',{style:'color:#fff;padding:1.2vh 2.2vw;height:100vh;box-sizing:border-box;display:flex;flex-direction:column;gap:0.9vh;overflow:hidden'});root.textContent='';root.style.maxWidth='none';root.style.margin='0';root.style.padding='0';document.body.style.margin='0';root.appendChild(wrap);
  var remain=null,lastRenderKey='',lastViewKey='',scrollBody=null,clockNode=null,activeCwBox=null,lastAudioPlaying=null;
  function boardCoursewareKey(cw){
    if(!cw)return null;
    if(cw.kind!=='slide')return cw;
    var viewCopy={};
    if(cw.view){
      Object.keys(cw.view).forEach(function(k){
        if(k!=='audioPlaying')viewCopy[k]=cw.view[k];
      });
    }
    return {
      id:cw.id||null,kind:cw.kind,kindLabel:cw.kindLabel||'',
      stageNo:cw.stageNo,page:cw.page===undefined?null:cw.page,
      params:cw.params||null,view:viewCopy
    };
  }
  function renderKey(d){
    return JSON.stringify({
      title:d.title||'',status:d.status||'',covered:!!d.covered,
      currentStage:d.currentStage||0,stageName:d.stageName||'',goal:d.goal||'',
      deck:d.deck||null,content:d.content||[],courseware:boardCoursewareKey(d.courseware),
      practiceFigure:d.practiceFigure||null,
      answersPublished:!!d.answersPublished,answerRelease:d.answerRelease||null
    });
  }
  function viewKey(d){
    var title=d.courseware&&d.courseware.params?d.courseware.params.title||'':'';
    return JSON.stringify([d.status||'',d.currentStage||0,d.deck?d.deck.index:null,title]);
  }
  function updateClock(){
    if(clockNode&&remain!=null)clockNode.textContent=fmt(remain);
  }
  function syncBoardAudio(d){
    if(!d||!d.courseware||d.courseware.kind!=='slide'||!activeCwBox)return;
    var wantPlay=!!(d.courseware.view&&d.courseware.view.audioPlaying);
    if(wantPlay===lastAudioPlaying)return;
    lastAudioPlaying=wantPlay;
    var au=activeCwBox.querySelector?activeCwBox.querySelector('audio'):null;
    if(!au)return;
    if(wantPlay){
      try{var pr=au.play();if(pr&&pr.catch)pr.catch(function(){})}catch(_e){}
    }else{
      try{au.pause()}catch(_e2){}
    }
  }
  function boardCoursewareContent(d){
    var lines=Array.isArray(d.content)?d.content.slice():[];
    var params=d.courseware&&d.courseware.params||{};
    var keys=[params.sourceProblem,params.question,params.title].map(function(x){return String(x||'').replace(/\s+/g,'')})
      .filter(function(x){return x.length>0});
    return lines.filter(function(line){
      var text=String(line||'').replace(/\s+/g,'');
      if(!text)return false;
      return !keys.some(function(key){
        if(text===key)return true;
        if(text.length<16||key.length<16)return false;
        var shorter=Math.min(text.length,key.length),longer=Math.max(text.length,key.length);
        return shorter/longer>=0.72&&(key.indexOf(text)>=0||text.indexOf(key)>=0);
      });
    });
  }
  function fitText(box){
    var size=Math.min(48,Math.max(20,window.innerHeight*.045));box.style.fontSize=size+'px';
    while(size>14&&(box.scrollHeight>box.clientHeight||box.scrollWidth>box.clientWidth)){size-=1;box.style.fontSize=size+'px'}
  }
  function paint(d,force){
    var nextKey=renderKey(d);
    if(!force&&nextKey===lastRenderKey){updateClock();syncBoardAudio(d);return}
    var keepScroll=!!scrollBody&&viewKey(d)===lastViewKey;
    var oldScroll=keepScroll?scrollBody.scrollTop:0;
    var keepFocus=keepScroll&&document.activeElement===scrollBody;
    wrap.textContent='';scrollBody=null;clockNode=null;activeCwBox=null;lastAudioPlaying=null;
    if(d.status==='planned'||d.status==='finished'||d.covered){
      wrap.appendChild(el('div',{style:'opacity:.75;font-size:2.2vh',text:d.title}));
      var waitText=d.status==='planned'?'马上开始上课':d.status==='finished'?'下课了，谢谢大家':'请看老师';
      wrap.appendChild(el('div',{style:'font-size:6vh;margin-top:24vh;text-align:center',text:waitText}));
      lastRenderKey=nextKey;lastViewKey=viewKey(d);return;
    }
    clockNode=el('div',{id:'bclock',style:'font-size:2.8vh;font-weight:700;font-variant-numeric:tabular-nums;color:#f8fafc;white-space:nowrap',text:remain==null?'':fmt(remain)});
    var headLeft=el('div',{style:'display:flex;align-items:center;gap:0.9vw;min-width:0;flex:1;overflow:hidden'});
    headLeft.appendChild(el('span',{style:'font-size:2.1vh;font-weight:700;padding:0.3vh 0.85vw;border-radius:999px;background:rgba(59,130,246,.22);border:1px solid rgba(147,197,253,.45);color:#e0f2fe;white-space:nowrap;flex:none',text:d.currentStage+'. '+d.stageName}));
    headLeft.appendChild(el('span',{style:'font-size:2vh;font-weight:600;color:rgba(255,255,255,.9);white-space:nowrap;overflow:hidden;text-overflow:ellipsis',text:d.title}));
    if(d.goal)headLeft.appendChild(el('span',{style:'font-size:1.7vh;color:rgba(255,255,255,.55);white-space:nowrap;overflow:hidden;text-overflow:ellipsis',text:'· '+d.goal}));
    var headRight=el('div',{style:'display:flex;align-items:center;gap:0.9vw;flex:none'});
    if(d.deck)headRight.appendChild(el('span',{style:'font-size:1.85vh;color:rgba(255,255,255,.82);background:rgba(255,255,255,.1);padding:0.25vh 0.8vw;border-radius:999px;white-space:nowrap',text:'第 '+(d.deck.index+1)+' / '+d.deck.total+' 页'}));
    headRight.appendChild(clockNode);
    wrap.appendChild(el('div',{class:'board-topbar',style:'display:flex;justify-content:space-between;align-items:center;gap:1.2vw;padding-bottom:0.7vh;border-bottom:1px solid rgba(255,255,255,.14);flex:none'},headLeft,headRight));
    var body=el('div',{tabindex:'0',role:'region','aria-label':'课堂投影内容',style:'flex:1;min-height:0;white-space:pre-wrap;word-wrap:break-word;overflow-wrap:anywhere;line-height:1.45'});
    body.style.overflow='auto';
    wrap.appendChild(body);
    if(keepFocus)body.focus();
    BL_COVER=d.currentStage===2||d.currentStage===3;   // practice answers appear only once the teacher has released them
    if(d.courseware){
      // The approved courseware already prints its title and source problem. Suppress an identical
      // slide line so the question is not repeated and the diagram stays above the fold.
      body.style.display='flex';body.style.flexDirection='column';
      var topContent=boardCoursewareContent(d);
      if(topContent.length){var top=el('div',{style:'font-size:1.85vh;margin-bottom:0.6vh;flex:none'});body.appendChild(top);boardLayout(top,topContent,false)}
      var cwBox=el('div',{style:d.courseware.kind==='slide'?'flex:0 0 auto;width:100%':'flex:1;min-height:0;display:flex;flex-direction:column'});body.appendChild(cwBox);cwRender(cwBox,d.courseware,d.courseware.view,true,false);
      activeCwBox=cwBox;lastAudioPlaying=!!(d.courseware.view&&d.courseware.view.audioPlaying);
      scrollBody=body;lastRenderKey=nextKey;lastViewKey=viewKey(d);
      if(keepScroll)body.scrollTop=oldScroll;
      updateClock();return;
    }
    if(d.practiceFigure){
      body.style.display='flex';body.style.flexDirection='column';body.style.gap='1vh';
      var qTop=el('div',{style:'font-size:2.4vh;line-height:1.45;flex:none'});body.appendChild(qTop);boardLayout(qTop,d.content,false);
      var figBox=el('div',{style:'flex:1;min-height:0;display:flex;align-items:center;justify-content:center;background:#fff;border-radius:12px;padding:12px;overflow:auto'});
      body.appendChild(figBox);renderQuestionFigure(figBox,d.practiceFigure,true);
      scrollBody=body;lastRenderKey=nextKey;lastViewKey=viewKey(d);
      if(keepScroll)body.scrollTop=oldScroll;
      updateClock();return;
    }
    // Side by side when it fits; when the two columns would make the text smaller, stack them (the larger text wins).
    function laid(wide){body.textContent='';boardLayout(body,d.content,wide);fitText(body);return parseFloat(body.style.fontSize)||0}
    window.blRefit=function(){fitText(body)};          // a shown answer makes the page longer: fit it again
    boardLayout(body,d.content,false);
    scrollBody=body;lastRenderKey=nextKey;lastViewKey=viewKey(d);
    if(keepScroll)body.scrollTop=oldScroll;
    requestAnimationFrame(function(){
      if(window.innerWidth<1000)fitText(body);
      else{var two=laid(true),one=laid(false);if(two>=one)laid(true)}
      if(keepScroll)body.scrollTop=oldScroll;
    });
    updateClock();
  }
  var last=null,requestNo=0,boardBusy=false;
  function load(){if(boardBusy)return;boardBusy=true;var request=++requestNo;api('/teacher/weekend/sessions/'+SID+'/board').then(function(d){boardBusy=false;if(request!==requestNo)return;last=d;remain=d.remainingSeconds;paint(d,false)}).catch(function(e){boardBusy=false;if(request===requestNo&&!last)msg(e.message)})}
  window.addEventListener('resize',function(){if(last&&!(last.courseware&&last.courseware.kind==='slide'))paint(last,true)});
  load();setInterval(function(){if(!document.hidden){load()}},4000);
  if(typeof document!=='undefined'&&document.addEventListener)document.addEventListener('visibilitychange',function(){if(!document.hidden){load()}});
  setInterval(function(){if(remain!=null){remain-=1;updateClock()}},1000);
}
boot(board);
"""

PRACTICE_JS = r"""
var LETTERS='ABCDEFGH',wait=null;
function optText(i,o){return LETTERS[i]+'. '+String(o).replace(/^\s*[A-Da-d]\s*[．.、:：)）]\s*/,'')}   // imported options may carry their own letter
function invitationCard(q,sid,onResponded){
  var card=el('div',{class:'card'}),stem=String(q.stem||''),cut=stem.lastIndexOf('\n\n');
  card.appendChild(el('h2',{text:q.explainReview&&q.explainReview.finished?'本次讲题已完成':'老师请你给大家讲这道题'}));
  if(q.explainReview&&q.explainReview.finished){
    card.appendChild(el('div',{class:'notice ok',text:'老师评价：'+q.explainReview.label+' · 讲题积分 +'+q.explainReview.points+(q.explainReview.comment?' · 评语：'+q.explainReview.comment:'')}));
  }else if(sid){
    var respBox=el('div',{class:'row',style:'margin:6px 0'});
    function showResp(resp){
      respBox.textContent='';
      respBox.appendChild(el('div',{class:resp.decision==='accept'?'notice ok':'notice warn',text:resp.label}));
    }
    if(q.explainResponse&&q.explainResponse.decision){
      showResp(q.explainResponse);
    }else{
      var acceptBtn=el('button',{class:'primary',text:'我来讲（同意）',onclick:function(){sendResp('accept')}});
      var declineBtn=el('button',{text:'暂不讲解（拒绝）',onclick:function(){sendResp('decline')}});
      function sendResp(decision){
        acceptBtn.disabled=true;declineBtn.disabled=true;
        api('/student/weekend/explain/respond',{json:{sessionId:sid,questionId:q.questionId,questionType:q.questionType||'choice',decision:decision}}).then(function(r){
          showResp(r.explainResponse);
          if(typeof onResponded==='function')onResponded();
        }).catch(function(e){alert(e.message);acceptBtn.disabled=false;declineBtn.disabled=false});
      }
      respBox.appendChild(acceptBtn);respBox.appendChild(declineBtn);
    }
    card.appendChild(respBox);
  }
  function folded(title,text){return el('details',{},el('summary',{text:title}),el('div',{style:'white-space:pre-wrap;overflow-wrap:anywhere;font-weight:400;line-height:1.7',text:text}))}
  if(cut>0){card.appendChild(folded('阅读材料（展开查看）',stem.slice(0,cut)));card.appendChild(el('p',{style:'white-space:pre-wrap;overflow-wrap:anywhere',text:stem.slice(cut+2)}))}
  else if(stem.length>360)card.appendChild(folded('完整题目与阅读材料（展开查看）',stem));
  else card.appendChild(el('p',{style:'white-space:pre-wrap',text:stem}));
  if(q.questionType==='written'){
    card.appendChild(el('p',{style:'white-space:pre-wrap;overflow-wrap:anywhere',text:'你提交的答案：'+(q.answerText||'见答案照片')}));
    writtenPhoto(card,q.submission);
    if(q.reference)card.appendChild(folded('已公布参考答案与评分要点（展开查看）',q.reference));
  }else card.appendChild(el('div',{class:'muted',text:'正确答案：'+optText(q.correctIndex,q.options[q.correctIndex]||'')}));
  if(q.explanation)card.appendChild(folded('解析（展开查看）',q.explanation));
  card.appendChild(el('p',{class:'muted',text:'用自己的话讲清思路、依据和容易出错的地方。'}));
  return card;
}
function practiceMapEntry(holder){
  // 知识地图（开关打开且老师已发布时）：课前先做入门诊断，课后在地图上点知识点做 3～5 题小测。
  api('/student/knowledge-map').then(function(m){
    if(!m||!m.diagnosis)return;var before=m.diagnosis.status!=='submitted';
    holder.appendChild(el('div',{class:'card'},el('h3',{text:before?'课前诊断':'课后补测'}),
      el('p',{text:before?'上课前先做 12 道题的入门诊断，看看学过的单元掌握得怎么样。':'下课后打开知识地图，点今天学的知识点，做 3～5 题小测，看看掌握了没有。'}),
      el('a',{class:'btn primary',style:'text-decoration:none;display:inline-block',href:'/v1/my-knowledge-map',text:before?'去做入门诊断':'打开知识地图做小测'})));
  }).catch(function(){});
}
function practice(){
  root.textContent='';
  var box=el('div'),mapEntry=el('div'),lastPracticeSignature='',selectedAnswers={},currentSession=null,currentStage=null,loadNo=0,explainNo=0;root.appendChild(mapEntry);root.appendChild(box);practiceMapEntry(mapEntry);
  function load(){
    var request=++loadNo;api('/student/weekend/current').then(function(d){if(request!==loadNo)return;var sid=d.active?d.sessionId:null;if(sid!==currentSession){ebox.textContent='';fbox.textContent='';explainNo++}currentSession=sid;currentStage=d.stage;if(currentStage!==4&&currentStage!==5)fbox.textContent='';paint(d);explain();if(!fbox.firstChild)followup()}).catch(function(e){if(request!==loadNo)return;currentSession=null;explainNo++;ebox.textContent='';fbox.textContent='';lastPracticeSignature='';box.textContent='';box.appendChild(el('div',{class:'card'},el('div',{class:'notice error',text:e.message})))});
  }
  function paint(d){
    var signature=JSON.stringify(d);if(signature===lastPracticeSignature)return;lastPracticeSignature=signature;
    box.textContent='';
    if(!d.active||!d.practice){
      var info=el('div',{class:'card'},el('h2',{text:d.title||'课堂练习'}));
      if(d.active&&d.stage&&d.stageName)info.appendChild(el('div',{class:'tag ok',style:'display:inline-block;margin-bottom:6px',text:'第 '+d.stage+' 环节：'+d.stageName}));
      info.appendChild(el('div',{class:'muted',text:d.message||''}));
      if(Array.isArray(d.stageContent)&&d.stageContent.length){
        var scBox=el('div',{style:'margin-top:8px;padding-top:8px;border-top:1px solid #eef2f6'});
        d.stageContent.forEach(function(line){scBox.appendChild(el('p',{style:'margin:4px 0;white-space:pre-wrap',text:line}))});
        info.appendChild(scBox);
      }
      if(d.homeworkUrl){
        info.appendChild(el('div',{class:'row',style:'margin-top:10px'},el('a',{class:'btn primary',href:d.homeworkUrl,text:'前往首页“作业”查看专属课后练习'})));
      }
      box.appendChild(info);
      if(d.active&&d.stage===6&&d.sessionId){
        var s6Box=el('div');box.appendChild(s6Box);
        api('/student/weekend/sessions/'+d.sessionId+'/stage6-checks').then(function(s6){
          s6Box.textContent='';
          if(!s6.items||!s6.items.length){s6Box.appendChild(el('div',{class:'card muted',text:'本节待巩固题已全部达标！'}));return}
          s6.items.forEach(function(it){
            var c=el('div',{class:'card'});
            c.appendChild(el('b',{text:'第 '+it.no+' 题：'+it.stem}));
            if(typeof renderQuestionFigure==='function')renderQuestionFigure(c,it.figure,false);
            var stTag=it.teacherStatus==='mastered'?'老师已确认本节达标 ✓':it.teacherStatus==='homework'?'已留入课后巩固练习':'正在讨论中';
            c.appendChild(el('div',{class:'muted',style:'margin:4px 0',text:stTag}));
            var noteIn=el('input',{placeholder:'哪里还没懂？可简短写给老师（选填）',maxlength:300,style:'width:100%;box-sizing:border-box;margin:6px 0'});
            noteIn.value=it.myNote||'';
            var fbMsg=el('div',{role:'status'});
            if(it.myStatus)fbMsg.appendChild(el('div',{class:it.myStatus==='doubt'?'notice warn':'notice ok',text:it.myStatus==='doubt'?'已反馈：还是不懂（留入课后/向老师提问）':'已反馈：这道题我已经听懂了 ✓'}));
            function sendFb(statusVal){
              api('/student/weekend/sessions/'+d.sessionId+'/stage6-checks',{json:{questionKey:it.questionKey,status:statusVal,note:noteIn.value}}).then(function(){
                fbMsg.textContent='';fbMsg.appendChild(el('div',{class:statusVal==='doubt'?'notice warn':'notice ok',text:statusVal==='doubt'?'已提交疑问，老师会安排讲解或留入课后针对性练习':'已确认：这道题我已经听懂了 ✓'}));
              }).catch(function(e){alert(e.message)});
            }
            c.appendChild(noteIn);
            c.appendChild(el('div',{class:'row'},
              el('button',{class:it.myStatus==='understood'?'primary':'',text:'已听懂 ✓',onclick:function(){sendFb('understood')}}),
              el('button',{class:it.myStatus==='doubt'?'primary':'',text:'还是不懂（提问／留课后）',onclick:function(){sendFb('doubt')}})));
            c.appendChild(fbMsg);
            s6Box.appendChild(c);
          });
        }).catch(function(){});
      }
      return;
    }
    box.appendChild(el('div',{class:'card'},el('h2',{text:d.title}),el('div',{class:'muted',text:'按老师要求完成本节练习；各题的作答方式和提交状态显示在题目旁。'})));
    if(d.questions.length)box.appendChild(el('p',{class:'muted',text:'选择题：每题最多提交3次；老师公布本题答案后停止修改。'}));
    if(!d.questions.length){
      var availability=d.questionAvailability||{},choice=availability.choice||{},written=availability.written||{},emptyText='';
      if(written.open)emptyText='当前开放的是文字／照片题，请在下方“文字／照片作答”区逐题提交；课后针对性练习经老师审核布置后，请到学生首页“作业”完成。';
      else if(choice.total&&choice.open===0)emptyText='本课选择题已准备好，等待老师在大屏逐题开放；课后针对性练习经老师审核布置后，请到学生首页“作业”完成。';
      else if(written.total)emptyText='本课有文字／照片题，等待老师在大屏逐题开放；开放后可在下方输入答案或上传照片。课后练习请到学生首页“作业”查看。';
      else emptyText='本课还没有已同步开放的随堂题，请老师检查“习题审核”和“同步新增练习”；课后练习经老师审核布置后，请到学生首页“作业”查看。';
      box.appendChild(el('div',{class:'card notice',role:'status',text:emptyText}));
    }
    d.questions.forEach(function(q,qi){
      var locked=q.canSubmit===false||(q.attempts||0)>=3,card=el('div',{class:'card'}),out=el('div'),hintsOut=el('div');
      card.appendChild(el('b',{text:/^\s*第\s*\d+\s*题/.test(q.stem)?q.stem:(qi+1)+'. '+q.stem}));
      if(typeof renderQuestionFigure==='function')renderQuestionFigure(card,q.figure,false);
      var selectionKey=d.sessionId+':'+q.id,chosen=selectedAnswers[selectionKey]==null?(q.answered?q.selected:-1):selectedAnswers[selectionKey],opts=el('div');
      q.options.forEach(function(o,i){
        var b=el('button',{style:'display:block;width:100%;text-align:left;margin:6px 0',text:optText(i,o)});
        if(locked){
          if(i===q.selected)b.className='on';
          b.disabled=true;
        }else b.addEventListener('click',function(){chosen=i;selectedAnswers[selectionKey]=i;Array.prototype.forEach.call(opts.children,function(x,j){x.className=j===i?'on':''})});
        if(!locked&&chosen===i)b.className='on';
        opts.appendChild(b);
      });
      card.appendChild(opts);
      if(q.answered||q.canSubmit===false){
        out.appendChild(el('div',{class:'notice',text:q.answered?(q.answersPublished?'已提交，请看大屏核对答案并听老师讲评。':'已提交，请等待老师统一在大屏公布答案。'):'老师已公布答案，停止提交；请看大屏听讲评。'}));
      }
      if(!locked){
        var hintBtn=el('button',{text:q.hintUsed>=3?'提示已用完':'要提示（已用 '+q.hintUsed+'/3）',disabled:q.hintUsed>=3,onclick:function(){
          hintBtn.disabled=true;
          api('/student/weekend/hint',{json:{sessionId:d.sessionId,questionId:q.id}}).then(function(h){
            hintsOut.appendChild(el('div',{class:'notice warn',text:'提示'+h.level+'（'+h.name+'）：'+h.text}));
            q.hintUsed=h.level;hintBtn.textContent=h.last?'提示已用完':'要提示（已用 '+h.level+'/3）';hintBtn.disabled=!!h.last;
          }).catch(function(e){hintsOut.appendChild(el('div',{class:'notice error',text:e.message}));hintBtn.disabled=false});
        }});
        var submit=el('button',{class:'primary',text:q.answered?'修改并提交（已用'+q.attempts+'/3次）':'提交答案',onclick:function(){
          if(chosen<0){alert('先选一个答案');return}
          submit.disabled=true;
          api('/student/weekend/answer',{json:{sessionId:d.sessionId,questionId:q.id,selected:chosen,attempt:q.attempts||0}}).then(function(saved){if(!saved.submitted)throw Error('未收到保存回执，请刷新核对');return load()}).catch(function(e){alert(e.message);submit.disabled=false});
        }});
        hintBtn.hidden=!!q.answered;card.appendChild(el('div',{class:'row'},hintBtn,submit));
        (q.hintTexts||[]).forEach(function(t,i){hintsOut.appendChild(el('div',{class:'notice warn',text:'提示'+(i+1)+'（'+q.levelNames[i]+'）：'+t}))});
      }
      card.appendChild(hintsOut);card.appendChild(out);box.appendChild(card);
    });
  }
  var ebox=el('div'),lastExplainSignature='';root.insertBefore(ebox,box);
  function explain(force){
    var sid=currentSession,request=++explainNo;
    if(!sid||(currentStage!==4&&currentStage!==5)){lastExplainSignature='';ebox.textContent='';return}
    api('/student/weekend/explain?sessionId='+sid).then(function(d){
      if(request!==explainNo||sid!==currentSession||d.sessionId!==sid)return;
      var sig=sid+':'+JSON.stringify(d.items||[]);
      if(!force&&sig===lastExplainSignature)return;
      lastExplainSignature=sig;
      ebox.textContent='';d.items.forEach(function(q){ebox.appendChild(invitationCard(q,sid,function(){lastExplainSignature=''}))});
    }).catch(function(){if(request===explainNo&&!lastExplainSignature)ebox.textContent=''});
  }
  var fbox=el('div');root.insertBefore(fbox,box);
  function followup(){
    var sid=currentSession;if(!sid||(currentStage!==4&&currentStage!==5)){fbox.textContent='';return}
    api('/student/weekend/followup').then(function(f){
      if(sid!==currentSession||(currentStage!==4&&currentStage!==5))return;fbox.textContent='';if(!f.active||f.sessionId!==sid)return;
      var card=el('div',{class:'card'}),chosen=-1,out=el('div'),opts=el('div');
      card.appendChild(el('h2',{text:'巩固小题：刚讲过的方法，再试一道'}));card.appendChild(el('b',{text:f.stem}));
      f.options.forEach(function(o,i){opts.appendChild(el('button',{style:'display:block;width:100%;text-align:left;margin:6px 0',text:optText(i,o),onclick:function(){chosen=i;Array.prototype.forEach.call(opts.children,function(x,j){x.className=j===i?'on':''})}}))});
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
  load();
  wait=setInterval(function(){if(!document.hidden){load()}},8000);
  if(typeof document!=='undefined'&&document.addEventListener)document.addEventListener('visibilitychange',function(){if(!document.hidden){load()}});
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
    rendered = html.replace("__JS__", (COMMON_JS + js).replace("__PAGE_AUTH__", PAGE_AUTH_JS))
    if title in ("周末课备课", "周末课", "课堂大屏"):
        # An ordinary external ES5 file does not change any of the precompiled
        # Safari12 inline script fingerprints. It overrides only the known-bad
        # four-method lesson 11 drawing, not generic geometry.
        rendered = rendered.replace("</body>", '<script src="/v1/lesson11-methods-v2.js?v=20261115-lesson11-diagrams-r6"></script></body>')
    return apply_surface(rendered, "weekend" if with_header else "board")


PLAN_JS = MARK_JS + r"""
var SUBJ='数学';
function genSummary(g){
  var names={choice:'选择',final_answer:'填空／计算',short_answer:'解决问题／简答',composition:'写作'},parts=[],lv=[];
  Object.keys(g.byType||{}).forEach(function(k){if(g.byType[k])parts.push(names[k]+' '+g.byType[k])});
  Object.keys(g.byLevel||{}).forEach(function(k){if(g.byLevel[k])lv.push(k+' '+g.byLevel[k])});
  var drop=Object.keys(g.dropped||{}).map(function(k){return k+' '+g.dropped[k]});
  return '共 '+g.count+' 题（'+parts.join('、')+'；'+lv.join('、')+'）'+(g.verified?'，其中 '+g.verified+' 题数学答案已由系统验算':'')+'。'
    +(g.short?'还差 '+g.short+' 题没出够，可以再点一次。':'')+(drop.length?'不合格已丢弃：'+drop.join('、')+'。':'');
}
function batchItemTag(it){
  if(!it.ok)return {cls:'warn',text:'读不出文字：'+(it.error||'')};
  if(!it.lessonNo)return {cls:'warn',text:'文件名里看不出课次'};
  return {cls:'ok',text:'第 '+it.lessonNo+' 课'+(it.hasPlan?'（已有教案，会覆盖）':'')};
}
function batchForm(picked,force,courseType){
  var fd=new FormData();fd.append('subject',SUBJ);if(courseType)fd.append('courseType',courseType);
  if(force!=null)fd.append('force',force?'1':'0');
  picked.forEach(function(f){fd.append('files',f)});
  return fd;
}
function batchShowResult(r,panel){
  panel.textContent='';
  panel.appendChild(el('div',{class:'notice '+(r.failed?'warn':'ok'),text:r.message}));
  r.items.forEach(function(it){
    panel.appendChild(el('div',{class:'row'},el('span',{text:it.filename}),
      el('span',{class:'tag '+(it.ok?'ok':'warn'),text:it.ok?('第 '+it.lessonNo+' 课已导入'):('没导入：'+it.error)})));
  });
}
function batchPlanPanel(d,picked,panel,after){
  panel.textContent='';
  var ready=d.items.filter(function(i){return i.ok&&i.lessonNo});
  var over=d.items.filter(function(i){return i.ok&&i.lessonNo&&i.hasPlan});
  d.items.forEach(function(it){
    var tag=batchItemTag(it);
    panel.appendChild(el('div',{class:'row'},el('span',{text:it.filename}),el('span',{class:'tag '+tag.cls,text:tag.text})));
  });
  if(!ready.length){panel.appendChild(el('div',{class:'notice warn',text:'没有可以导入的文件：请确认文件名里有课次，并且文件能读出文字。'}));return null}
  var typeSel=null;
  if(SUBJ==='语文'){typeSel=el('select',{'aria-label':'本批中文课程类型'});typeSel.appendChild(el('option',{value:'',text:'先选择本批课型'}));typeSel.appendChild(el('option',{value:'reading',text:'阅读课'}));typeSel.appendChild(el('option',{value:'writing',text:'作文课'}));panel.appendChild(typeSel)}
  var go=el('button',{class:'primary',text:'确认导入 '+ready.length+' 节',onclick:function(){
    if(typeSel&&!typeSel.value){panel.appendChild(el('div',{class:'notice warn',text:'请先选择本批次课型；不同课型请分批导入。'}));return}
    if(over.length&&!confirm('有 '+over.length+' 节课已经有教案，导入会替换教案、草稿题和本课课件，已通过的习题保留。导入前的整份教案可在“审改”里恢复。确定导入吗？'))return;
    go.disabled=true;panel.appendChild(el('div',{class:'notice',text:'正在逐份导入，每份大约半分钟…'}));
    api('/teacher/weekend/lessons/import/batch',{method:'POST',body:batchForm(picked,over.length>0,typeSel&&typeSel.value)})
      .then(function(r){batchShowResult(r,panel);if(after)after(r)})
      .catch(function(e){panel.appendChild(el('div',{class:'notice error',text:e.message}));go.disabled=false});
  }});
  panel.appendChild(el('div',{class:'row'},go));
  return go;
}
function approveQuestionInPlace(path,q,button,actions,badge,feedback,refreshStatus,confirmMissing){
  if(button.disabled)return Promise.resolve();
  var buttons=actions.querySelectorAll('button');
  Array.prototype.forEach.call(buttons,function(b){b.disabled=true});
  feedback.textContent='';
  return api(path,{json:{approve:[q.id],confirmMissingFigure:!!confirmMissing}}).then(function(st){
    q.active=true;q.approved=true;
    badge.textContent='已通过';badge.className='tag ok';button.textContent='已通过';
    refreshStatus(st);
  }).catch(function(e){
    feedback.textContent=e.message;
    Array.prototype.forEach.call(buttons,function(b){b.disabled=false});
  });
}
function saveLessonEdits(url,payload,button,status,fields,onSaved){
  if(button.disabled)return Promise.resolve();
  button.disabled=true;button.textContent='正在保存…';
  fields.forEach(function(n){n.disabled=true});
  status.className='notice';status.textContent='正在保存，请稍候…';
  var written=false;
  return api(url,{method:'PUT',json:payload}).then(function(){
    written=true;return api(url);
  }).then(function(saved){
    var matches=Object.keys(payload).every(function(k){return JSON.stringify(saved[k])===JSON.stringify(payload[k])});
    if(!matches)throw new Error('服务器保存内容与当前填写内容不一致，请保留本页并核对后重试');
    status.className='notice ok';status.textContent='教案已保存，已核对服务器内容';if(onSaved)onSaved();
  }).catch(function(e){
    status.className='notice error';
    status.textContent=(written?'保存请求已完成，但回读核对未通过：':'保存未成功：')+e.message+'。本页填写内容已保留。';
  }).then(function(){
    button.disabled=false;button.textContent='保存教案';fields.forEach(function(n){n.disabled=false});
  });
}
function plan(){
  root.textContent='';
  var tabs=el('div',{class:'tabs'}),nextBox=el('div',{class:'card'}),toolBox=el('div',{class:'card'}),batchBox=el('div',{class:'card'}),list=el('div'),msg=el('div');
  ['数学','语文'].forEach(function(s){tabs.appendChild(el('button',{class:s===SUBJ?'on':'',text:s,onclick:function(){SUBJ=s;plan()}}))});
  root.appendChild(tabs);root.appendChild(nextBox);root.appendChild(toolBox);root.appendChild(batchBox);root.appendChild(msg);root.appendChild(list);
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

  toolBox.appendChild(el('div',{class:'notice ok',text:'备课方法：在下面每一次课的那一行，点“导入教案/整包”上传自己的 Word / PPT / PDF 教案，或上传一个 JSON 整包，一次带入教案、随堂题和互动课件草稿；没有教案时才用“AI 帮我写”。学校进度表只是用来对照学校讲到哪里，可以不填。'}));
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

  var batchPanel=el('div'),batchInput=el('input',{type:'file',accept:'.docx,.pptx,.pdf,.txt,.md',multiple:true,hidden:true});
  batchBox.appendChild(el('h2',{text:'批量导入教案'}));
  batchBox.appendChild(el('div',{class:'muted',text:'一次选一个单元的文件。文件名里写上第几课，例如「第03课-民间英雄.docx」「lesson-07.pdf」，系统按文件名判断课次；先预览，确认后再导入。'}));
  var batchBtn=el('button',{text:'选择多个文件',onclick:function(){batchInput.click()}});
  batchBox.appendChild(el('div',{class:'row'},batchBtn,el('span',{class:'muted',text:'一次最多 18 个'})));
  batchBox.appendChild(batchInput);batchBox.appendChild(batchPanel);
  batchInput.addEventListener('change',function(){
    var picked=Array.prototype.slice.call(batchInput.files||[]);batchInput.value='';
    if(!picked.length)return;
    batchBtn.disabled=true;batchPanel.textContent='';batchPanel.appendChild(el('div',{class:'notice',text:'正在读取 '+picked.length+' 个文件…'}));
    api('/teacher/weekend/lessons/import/preview',{method:'POST',body:batchForm(picked)})
      .then(function(d){batchPlanPanel(d,picked,batchPanel,function(r){if(r&&r.imported)load()})})
      .catch(function(e){batchPanel.textContent='';batchPanel.appendChild(el('div',{class:'notice error',text:e.message}))})
      .then(function(){batchBtn.disabled=false});
  });

  var state=[];
  function paintRows(rows){
    state=rows;list.textContent='';
    rows.forEach(function(r){
      var wk=el('input',{type:'text',value:r.schoolWeek==null?'':r.schoolWeek,placeholder:'学校周',style:'width:70px',oninput:function(e){r.schoolWeek=e.target.value===''?null:+e.target.value}}),
          un=el('input',{type:'text',value:r.schoolUnit||'',placeholder:'学校进度/单元',oninput:function(e){r.schoolUnit=e.target.value}}),
          dt=el('input',{type:'text',value:r.plannedDate||'',placeholder:'2026-09-12',style:'width:120px',oninput:function(e){r.plannedDate=e.target.value}});
      function lessonRowTagText(st){
        if(st.taught)return '已上';
        if(!st.hasPlan)return '未备课';
        if(SUBJ==='语文'){
          var cwText=st.coursewareApproved?'互动课件已就绪':(st.coursewareStatus?'互动课件待确认':'互动课件未生成');
          var qTotal=(st.practiceReady||0)+(st.draftQuestions||0);
          return (st.workflowLabel?st.workflowLabel+' · ':'')+'有教案 · '+cwText+(qTotal?' · 练习 '+qTotal+' 道':'');
        }
        return (st.workflowLabel?st.workflowLabel+' · ':'')+'有教案 · 例题 '+(st.exampleCount||0)+'（待审 '+(st.examplePending||0)+'）· 可用练习 '+(st.practiceReady||0)+'（待审 '+st.draftQuestions+'）';
      }
      var tag=el('span',{class:'tag '+(r.taught?'ok':r.hasPlan?'':'warn'),text:lessonRowTagText(r)});
      var workflowSelect=SUBJ==='语文'?el('select',{'aria-label':'语文课型',style:'width:auto;min-width:120px'},
        el('option',{value:'',text:'待选择课型',selected:!r.courseType}),
        el('option',{value:'reading',text:'阅读课',selected:r.courseType==='reading'}),
        el('option',{value:'writing',text:'作文课',selected:r.courseType==='writing'})):null;
      if(workflowSelect)workflowSelect.onchange=function(){
        var selected=workflowSelect.value;
        if(!selected){workflowSelect.value=r.courseType||'';return}
        if(r.courseType&&selected!==r.courseType&&!confirm('修改课型会改变后续备课的六环节，请重新核对素材与课件。已创建课堂和历史记录继续使用原课型。确认修改？')){workflowSelect.value=r.courseType;return}
        workflowSelect.disabled=true;
        api('/teacher/weekend/schedule/'+encodeURIComponent(SUBJ)+'/'+r.lessonNo+'/course-type',{method:'PUT',json:{courseType:selected,expectedRevision:r.workflowRevision||0}})
          .then(function(d){r.courseType=d.courseType;r.workflowRevision=d.workflowRevision;load();note('ok','已保存课型：'+d.workflowLabel);why.textContent=startReason(r)})
          .catch(function(e){workflowSelect.value=r.courseType||'';note('error',e.message)})
          .then(function(){workflowSelect.disabled=false});
      };
      var detail=el('div',{hidden:true});
      var fileIn=el('input',{type:'file',accept:'.docx,.pptx,.pdf,.txt,.md,.json,application/json',hidden:true});
      var impBtn=el('button',{class:r.hasPlan?'':'primary',text:'导入教案/整包',title:'支持 Word(.docx)、PPT(.pptx)、PDF、txt，或一个包含教案、习题和课件的 JSON 整包',onclick:function(){fileIn.click()}});
      // The page-level note sits above the list; a teacher scrolled to this row never sees it.
      // Every import result is therefore shown right here, next to the button that produced it.
      var importFeedback=el('div',{role:'status','aria-live':'polite','data-import-feedback':'1'});
      fileIn.addEventListener('change',function(){
        var f=fileIn.files&&fileIn.files[0];if(!f)return;
        if(r.hasPlan&&!confirm('这节课已有教案，导入会替换教案、草稿题和本课课件，已通过的习题保留。导入前的整份教案可在“审改”里恢复。确定导入吗？')){fileIn.value='';return}
        var fd=new FormData();fd.append('subject',SUBJ);fd.append('lessonNo',String(r.lessonNo));fd.append('force',r.hasPlan?'1':'0');if(r.courseType)fd.append('courseType',r.courseType);fd.append('file',f);
        impBtn.disabled=true;impBtn.textContent='正在导入…';
        importFeedback.className='muted';importFeedback.textContent='正在读取并整理你的教案（约半分钟）…';
        if(importFeedback.scrollIntoView)importFeedback.scrollIntoView({block:'nearest'});
        api('/teacher/weekend/lessons/import',{method:'POST',body:fd}).then(function(d){note('ok',d.message);load()}).catch(function(e){
          var status=e&&e.status?'（'+e.status+'）':'';
          importFeedback.className='notice error';
          importFeedback.textContent='导入失败'+status+'：'+(e&&e.message?e.message:'请重试')+'。你选的文件不会被改动，可以处理后再导入。';
          impBtn.disabled=false;impBtn.textContent='导入教案/整包';
          if(importFeedback.scrollIntoView)importFeedback.scrollIntoView({block:'center'});
        }).then(function(){fileIn.value=''});
      });
      var draftBtn=el('button',{text:r.hasPlan?'AI 重写':'没教案？AI 帮我写',onclick:function(){
        if(r.hasPlan&&!confirm('这节课已有教案，AI 重写会覆盖教案文字和未审核的草稿题，确定吗？'))return;
        draftBtn.disabled=true;note('ok','AI 正在备课，大约半分钟…');
        api('/teacher/weekend/lessons/draft',{json:{subject:SUBJ,lessonNo:r.lessonNo,force:r.hasPlan}}).then(function(d){
            note('ok','教案草稿已生成，正在按题型和难度出一整套习题（约一分钟）…');
            return api('/teacher/weekend/lessons/'+d.lessonId+'/questions/generate',{json:{count:12}}).then(function(g){note('ok','教案和习题草稿都已生成：'+genSummary(g)+' 请展开“审改”核对。')},
              function(e){note('error','教案已生成，但出题没成功：'+e.message+' 可以再点“AI 出习题”。')});
          }).then(load).catch(function(e){note('error',e.message);draftBtn.disabled=false});
      }});
      var qCount=r.hasPlan&&r.lessonId?el('select',{'aria-label':'题量'},el('option',{value:'8',text:'8 题'}),el('option',{value:'12',text:'12 题',selected:true}),el('option',{value:'16',text:'16 题'})):null;
      var qBtn=r.hasPlan&&r.lessonId?el('button',{text:'AI 出习题（多题型、分难度）',onclick:function(){
        qBtn.disabled=true;note('ok','AI 正在按题型和难度出题，数学答案会逐题验算，约一分钟…');
        api('/teacher/weekend/lessons/'+r.lessonId+'/questions/generate',{json:{count:+qCount.value}}).then(function(g){note('ok','习题草稿已生成：'+genSummary(g)+' 展开“审改”逐题通过后才会给学生。');load()}).catch(function(e){note('error',e.message);qBtn.disabled=false});
      }}):null;
      var titleLabel=el('span',{class:'muted',text:r.title||''});
      function refreshRow(st){Object.assign(r,st);titleLabel.textContent=r.title||'';var needsQ=SUBJ!=='语文';go.disabled=!(r.lessonId&&r.hasPlan&&(!needsQ||(r.practiceReady!=null?r.practiceReady:r.approvedQuestions)>0)&&!(r.pendingMaterials>0)&&(SUBJ!=='语文'||r.courseType)&&(SUBJ!=='语文'||r.coursewareApproved));why.textContent=startReason(r);tag.textContent=lessonRowTagText(r);if(cwBtn)cwBtn.textContent=SUBJ==='语文'?'六环节课件与审核':'互动课件预览'}
      var open=el('button',{text:'教案与题目审核',disabled:!r.lessonId,onclick:function(){detail.hidden=!detail.hidden;if(!detail.hidden)lessonDetail(r,detail,refreshRow)}});
      var materialReviewBtn=SUBJ==='语文'&&r.lessonId?el('button',{text:'导入素材审核',onclick:function(){detail.hidden=false;reviewImportedMaterials(r,detail,refreshRow)}}):null;
      var pairedImportBtn=SUBJ==='语文'&&r.lessonId?el('button',{text:'双文件成对导入与绑定',onclick:function(){detail.hidden=false;pairedImportPanel(r,detail)}}):null;
      var cwBtn=r.hasPlan&&r.lessonId?el('button',{text:SUBJ==='语文'?'六环节课件与审核':'互动课件预览',onclick:function(){detail.hidden=false;lessonDetail(r,detail,refreshRow,3)}}):null;
      var go=el('button',{class:'primary',text:'开课',title:SUBJ==='语文'?'需选择课型、核对并审核六环节课件':'需选择课型、完成教案和审核任务',disabled:!(r.lessonId&&r.hasPlan&&(SUBJ==='语文'||(r.practiceReady!=null?r.practiceReady:r.approvedQuestions)>0)&&!(r.pendingMaterials>0)&&(SUBJ!=='语文'||r.courseType)&&(SUBJ!=='语文'||r.coursewareApproved)),onclick:function(){
        createWeekendClassroom(r.lessonId)}});
      // Say why 开课 is grey right next to it: a tooltip is invisible on tablets and phones.
      var why=el('span',{class:'muted','data-start-reason':'1',style:'color:#b54708',text:startReason(r)});
      var deleteFeedback=el('div',{role:'status','aria-live':'polite'});
      var cancelDebugBtn=el('button',{text:'撤销调试课堂',disabled:!r.lessonId,onclick:function(){
        var subject=SUBJ,lid=r.lessonId;
        cancelDebugBtn.disabled=true;deleteFeedback.textContent='正在检查课堂是否有实际教学记录…';
        api('/teacher/weekend/lessons/'+lid+'/debug-classrooms').then(function(d){
          var items=d.items||[];
          if(!items.length){deleteFeedback.textContent='没有需要撤销的调试课堂；可以直接删除教案';return}
          var names=items.map(function(x){return '#'+x.id+' '+x.title}).join('\n');
          if(!confirm('确认以下 '+items.length+' 个课堂只是调试，没有实际上课？\n'+names+'\n撤销会清除这些课堂的计时、翻页、班级绑定和课堂习题副本，保留教案、备课习题及操作留痕。之后可另点“删除教案”。已有学生作答、提示、积分或反馈时禁止撤销。')){deleteFeedback.textContent='未撤销';return}
          return api('/teacher/weekend/lessons/'+lid+'/cancel-debug-classrooms',{method:'POST',json:{subject:subject,lessonNo:r.lessonNo,confirmed:true,sessionIds:items.map(function(x){return x.id})}}).then(function(result){
            deleteFeedback.textContent=result.message;
            if(typeof load==='function')load();
          });
        }).catch(function(e){
          if(e.message&&e.message.indexOf('不能按调试课堂撤销')>=0&&confirm(e.message+'\n\n是否强制作为测试课堂撤销？（将清除这些课堂的作答、积分、反馈与报告记录，保留教案、课件与已审核习题）')){
            return api('/teacher/weekend/lessons/'+lid+'/debug-classrooms?includeAll=1').then(function(d2){
              var items2=d2.items||[];
              if(!items2.length){deleteFeedback.textContent='没有可撤销的课堂记录';return}
              return api('/teacher/weekend/lessons/'+lid+'/cancel-debug-classrooms',{method:'POST',json:{subject:subject,lessonNo:r.lessonNo,confirmed:true,force:true,sessionIds:items2.map(function(x){return x.id})}}).then(function(result){
                deleteFeedback.textContent=result.message;
                if(typeof load==='function')load();
              });
            }).catch(function(e2){deleteFeedback.textContent=e2.message});
          }
          deleteFeedback.textContent=e.message;
        }).then(function(){cancelDebugBtn.disabled=false});
      }});
      var deleteBtn=el('button',{text:'删除教案',disabled:!r.lessonId,onclick:function(){
        var subject=SUBJ;
        if(impBtn.disabled||draftBtn.disabled||(qBtn&&qBtn.disabled)){deleteFeedback.textContent='请等待当前导入或生成完成后再删除';return}
        if(!confirm('确认删除【'+subject+' · 第 '+r.lessonNo+' 次课】《'+(r.title||'教案')+'》？\n将清除教案原文、教学内容、PPT、例题及本课全部习题（包括已通过的题）。课次和进度表保留。\n已有课堂或学生学习记录时将阻止删除。'))return;
        deleteBtn.disabled=true;deleteFeedback.textContent='正在删除教案…';
        api('/teacher/weekend/lessons/'+r.lessonId,{method:'DELETE',json:{subject:subject,lessonNo:r.lessonNo,confirmed:true}}).then(function(d){
          if(SUBJ===subject){note('ok',d.message);load()}
        }).catch(function(e){deleteFeedback.textContent=e.message;deleteBtn.disabled=false});
      }});
      var mainMaterialBtn=SUBJ==='语文'&&(r.pendingMaterials>0)?materialReviewBtn:null;
      var extraMaterialBtn=SUBJ==='语文'&&!(r.pendingMaterials>0)?materialReviewBtn:null;
      list.appendChild(el('div',{class:'card'},el('div',{class:'row'},el('b',{text:'第 '+r.lessonNo+' 次'}),wk,un,dt),
        el('div',{class:'row'},tag,workflowSelect,titleLabel,impBtn,fileIn,SUBJ==='语文'?null:open,mainMaterialBtn,cwBtn,go,why),el('details',{},el('summary',{text:'更多操作：AI 辅助与课堂维护'}),el('div',{class:'row'},draftBtn,SUBJ==='语文'?null:qCount,SUBJ==='语文'?null:qBtn,SUBJ==='语文'?open:null,extraMaterialBtn,pairedImportBtn,cancelDebugBtn,deleteBtn)),importFeedback,deleteFeedback,detail));
    });
    list.appendChild(el('button',{class:'primary',text:'保存进度表',onclick:function(){
      api('/teacher/weekend/schedule',{method:'PUT',json:{subject:SUBJ,rows:state.map(function(r){return {lessonNo:r.lessonNo,schoolWeek:r.schoolWeek,schoolUnit:r.schoolUnit||'',plannedDate:r.plannedDate||'',note:r.note||''}})}}).then(function(){note('ok','已保存');load()}).catch(function(e){note('error',e.message)})}}));
  }
  function reviewImportedMaterials(r,box,refreshStatus){
    box.textContent='';
    var status=el('div',{role:'status',text:'正在读取导入素材…'}),items=el('div');
    box.appendChild(el('h3',{text:'导入素材审核'}));box.appendChild(status);box.appendChild(items);
    function reload(){
      api('/teacher/weekend/lessons/'+r.lessonId+'/imported-materials').then(function(d){
        items.textContent='';status.textContent=(d.items||[]).length?'请核对来源并选择用途和环节。':'没有可审核的图片素材。';
        (d.items||[]).forEach(function(x){
          var rel=el('select',{'aria-label':'素材用途'}),stage=el('select',{'aria-label':'流程环节'}),order=el('input',{type:'number',min:'0',max:'999',value:String(x.sortOrder),'aria-label':'排序'});
          var types=r.courseType==='writing'?[['model_essay','范文配图'],['picture_writing','看图写话图片'],['writing_method','写作方法配图'],['task','任务素材'],['question_figure','题目配图']]:[['short_reading','短文配图'],['long_reading','长文配图'],['article_illustration','阅读文章配图'],['task','任务素材'],['question_figure','题目配图']];
          types.forEach(function(t){rel.appendChild(el('option',{value:t[0],text:t[1]}))});
          var names=r.courseType==='writing'?['点名与回顾','范文导览','看图写话','技法梳理','随堂练习','课后反馈']:['点名与回顾','短文阅读','长文阅读','考点总结','综合练习','课后反馈'];
          names.forEach(function(name,i){stage.appendChild(el('option',{value:String(i+1),text:name}))});
          if(x.relationship)rel.value=x.relationship;if(x.stageNo)stage.value=String(x.stageNo);
          var feedback=el('span',{role:'status'}),confirmBtn=el('button',{text:'确认用途'}),ignoreBtn=el('button',{text:'忽略'});
          function save(decision){confirmBtn.disabled=true;ignoreBtn.disabled=true;feedback.textContent='正在保存…';
            api('/teacher/weekend/lessons/'+r.lessonId+'/imported-materials/'+x.id,{method:'PUT',json:{status:decision,relationship:rel.value,stageNo:+stage.value,sortOrder:+order.value||0,expectedRevision:x.revision}}).then(function(){
              return api('/teacher/weekend/schedule?subject='+encodeURIComponent(SUBJ));
            }).then(function(s){var current=(s.items||[]).filter(function(v){return v.lessonId===r.lessonId})[0];if(current)refreshStatus(current);reload()}).catch(function(e){feedback.textContent=e.message;confirmBtn.disabled=false;ignoreBtn.disabled=false});
          }
          confirmBtn.addEventListener('click',function(){save('confirmed')});ignoreBtn.addEventListener('click',function(){save('ignored')});
          items.appendChild(el('div',{class:'card'},el('div',{text:'来源：'+x.sourceFile+' / '+x.sourcePart+' · 状态：'+x.status}),el('div',{class:'muted',text:'原始图片 SHA-256：'+x.sourceSha256}),questionFigureImg({type:'uploaded_image',data_url:x.dataUrl,alt:'导入图片预览'}),el('div',{class:'row'},rel,stage,order,confirmBtn,ignoreBtn,feedback)));
        });
      }).catch(function(e){status.textContent='读取失败：'+e.message});
    }
    reload();
  }
  function pairedImportPanel(r,box){
    box.textContent='';
    box.appendChild(el('h3',{text:'双文件成对导入与绑定审核（教师版 + 学生版 .docx）'}));
    var tIn=el('input',{type:'file',accept:'.docx','aria-label':'教师版原件'}),sIn=el('input',{type:'file',accept:'.docx','aria-label':'学生版原件'});
    var msg=el('div',{role:'status','aria-live':'polite'}),bodyBox=el('div');
    var upBtn=el('button',{class:'primary',text:'成对导入并识别',onclick:function(){
      if(!tIn.files[0]||!sIn.files[0]){msg.className='notice warn';msg.textContent='请同时选择教师版和学生版两个 .docx 文件';return}
      upBtn.disabled=true;msg.className='notice';msg.textContent='正在配对解析并核对哈希…';
      var fd=new FormData();fd.append('teacherFile',tIn.files[0]);fd.append('studentFile',sIn.files[0]);
      fetch('/teacher/weekend/lessons/'+r.lessonId+'/paired-import',{method:'POST',headers:TOKEN?{Authorization:'Bearer '+TOKEN}:{},body:fd})
        .then(function(res){return res.json().then(function(d){if(!res.ok)throw new Error(d.detail||'导入失败');return d})})
        .then(function(d){msg.className='notice ok';msg.textContent='成对导入完成，请逐项核对并绑定。';paintPaired(d)})
        .catch(function(e){msg.className='notice error';msg.textContent=e.message})
        .then(function(){upBtn.disabled=false});
    }});
    box.appendChild(el('div',{class:'row'},el('label',{},el('span',{text:'教师版：'}),tIn),el('label',{},el('span',{text:'学生版：'}),sIn),upBtn));
    box.appendChild(msg);box.appendChild(bodyBox);
    function paintPaired(d){
      bodyBox.textContent='';
      if(!d||!d.pair){bodyBox.appendChild(el('p',{class:'muted',text:'尚未上传成对文件；请先选择教师版与学生版 .docx。'}));return}
      bodyBox.appendChild(el('div',{class:'notice',text:'教师版：'+d.pair.teacherFile+'（图 '+d.pair.teacherMediaCount+'） · 学生版：'+d.pair.studentFile+'（图 '+d.pair.studentMediaCount+'）'}));
      var targets=(d.bindings||[]).filter(function(b){return b.itemType==='article'||b.itemType==='question'});
      var stageNames=r.courseType==='writing'?['点名与回顾','范文导览','看图写话','技法梳理','随堂练习','课后反馈']:['点名与回顾','短文阅读','长文阅读','考点总结','综合练习','课后反馈'];
      (d.bindings||[]).forEach(function(b){
        var card=el('div',{class:'card'});
        card.appendChild(el('div',{text:b.itemKey+' · '+b.itemType+' · 来源 '+b.sourceFile+' ('+b.sourcePart+') · 置信度 '+b.confidence+' · 状态 '+b.status}));
        if(b.pendingReason)card.appendChild(el('div',{class:'muted',style:'color:#b54708',text:'待确认原因：'+b.pendingReason}));
        if(b.payload&&b.payload.dataUrl)card.appendChild(questionFigureImg({type:'uploaded_image',data_url:b.payload.dataUrl,alt:b.itemKey}));
        var txt=b.payload&&b.payload.text!=null?el('textarea',{class:'s'}):null;if(txt)txt.value=b.payload.text;
        if(txt)card.appendChild(txt);
        var stSel=el('select',{'aria-label':'环节'});stageNames.forEach(function(n,i){stSel.appendChild(el('option',{value:String(i+1),text:(i+1)+'. '+n}))});stSel.value=String(b.stageNo||2);
        var tgtSel=el('select',{'aria-label':'绑定目标'});tgtSel.appendChild(el('option',{value:'',text:'（未绑定目标）'}));
        targets.forEach(function(t){tgtSel.appendChild(el('option',{value:t.itemKey,text:t.itemKey+'：'+String((t.payload&&t.payload.text)||'').slice(0,28)}))});
        tgtSel.value=b.targetKey||'';
        var fb=el('span',{role:'status'});
        function saveB(st){
          fb.textContent='保存中…';
          api('/teacher/weekend/lessons/'+r.lessonId+'/bindings/'+b.id,{method:'PUT',json:{status:st,stageNo:+stSel.value,targetKey:tgtSel.value,text:txt?txt.value:null,expectedRevision:b.revision}})
            .then(function(){return api('/teacher/weekend/lessons/'+r.lessonId+'/paired-import')}).then(paintPaired)
            .catch(function(e){fb.textContent=e.message});
        }
        card.appendChild(el('div',{class:'row'},stSel,tgtSel,el('button',{class:'primary',text:'确认绑定',onclick:function(){saveB('confirmed')}}),el('button',{text:'忽略',onclick:function(){saveB('ignored')}}),fb));
        bodyBox.appendChild(card);
      });
      if((d.errata||[]).length){
        var errBox=el('details',{},el('summary',{text:'勘误与修改留痕（'+d.errata.length+' 条）'}));
        d.errata.forEach(function(e){errBox.appendChild(el('div',{class:'muted',text:'#'+e.bindingId+' ['+e.fieldName+'] '+e.oldValue.slice(0,30)+' → '+e.newValue.slice(0,30)+' ('+e.editedAt+')'}))});
        bodyBox.appendChild(errBox);
      }
    }
    api('/teacher/weekend/lessons/'+r.lessonId+'/paired-import').then(paintPaired).catch(function(e){msg.textContent=e.message});
  }
  function startReason(r){
    if(r.pendingMaterials>0)return '待审核：还有 '+r.pendingMaterials+' 项导入素材未确认；请打开“导入素材审核”。';
    if(SUBJ==='语文'&&!r.courseType)return '还差：先选择并保存“阅读课”或“作文课”';
    if(!r.lessonId||!r.hasPlan)return '还差：先导入教案或让 AI 写教案，才能开课';
    if(SUBJ==='语文'){
      if(r.startReasons&&r.startReasons.length)return '还差：'+r.startReasons.join('；');
      if(!r.coursewareApproved)return '还差：先在“互动课件”逐页核对并通过审核（生成不等于审核通过），才能开课';
      return '';
    }
    var ready=r.practiceReady!=null?r.practiceReady:r.approvedQuestions;
    if(!(ready>0)){
      if(r.approvedQuestions>0)return '不能开课：第4环节实际可用的随堂练习为 0 道（已通过的题都与本课例题重复），请在“习题审核”里通过至少 1 道不重复的练习';
      return '还差：在“习题审核”里至少通过 1 道习题'+(r.draftQuestions?'（现有 '+r.draftQuestions+' 道草稿待审）':'，可先导入练习或点“AI 出习题”');
    }
    return '';
  }
  function lessonDetail(r,box,refreshStatus,startTab){
    box.textContent='';
    api('/teacher/weekend/lessons/'+r.lessonId).then(function(L){
      var title=el('input',{type:'text',value:L.title}),tgt=el('textarea',{class:'s'}),plan=el('textarea',{class:'s'}),ppt=el('textarea',{class:'s'}),ex=el('textarea',{class:'s'}),cl=el('textarea',{class:'s'}),source=el('textarea',{class:'s',readonly:true,'aria-label':'导入原文'});
      tgt.value=L.coreTarget;plan.value=L.teacherPlan;ppt.value=L.ppt.join('\n\n');ex.value=L.examples.join('\n');cl.value=L.closureTraining;source.value=L.sourceText||'';
      function ls(t){return t.value.split('\n').map(function(x){return x.trim()}).filter(Boolean)}
      var nav=el('div',{class:'row',role:'tablist','aria-label':'教案内容分区'}),editPane=el('div'),questionPane=el('div'),originalPane=el('div'),coursewarePane=el('div');
      var panes=[editPane,questionPane,originalPane,coursewarePane],tabButtons=[],coursewareLoaded=false;
      ['教案编辑','习题审核','原文核对','互动课件'].forEach(function(label,i){
        var b=el('button',{role:'tab',text:label,'aria-selected':i===0?'true':'false',onclick:function(){
          panes.forEach(function(p,j){p.hidden=i!==j;tabButtons[j].setAttribute('aria-selected',i===j?'true':'false')});
          if(i===3&&!coursewareLoaded){coursewareLoaded=true;cwPlan(coursewarePane,r.lessonId,function(){api('/teacher/weekend/schedule?subject='+encodeURIComponent(SUBJ)).then(function(d){var st=d.items.filter(function(x){return x.lessonId===r.lessonId})[0];if(st)refreshStatus(st)})})}
          Array.prototype.forEach.call(panes[i].querySelectorAll('textarea'),growTextarea);
        }});tabButtons.push(b);nav.appendChild(b);
      });
      box.appendChild(nav);panes.forEach(function(p,i){p.hidden=i!==0;box.appendChild(p)});if(startTab)tabButtons[startTab].click();
      originalPane.appendChild(el('p',{class:'muted',text:'原文完整保留，含阅读文章、全部题目和教师评分细则；不会整份发给学生。'}));
      originalPane.appendChild(el('pre',{style:'white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;line-height:1.8',text:source.value||'本教案没有导入原文。'}));
      editPane.appendChild(el('div',{class:'muted',text:'课题'}));editPane.appendChild(title);
      editPane.appendChild(el('div',{class:'muted',text:'本节目标'}));editPane.appendChild(tgt);
      editPane.appendChild(el('p',{class:'muted',text:'阅读文章和全部原题请切换“原文核对”；课堂题请切换“习题审核”。'}));
      editPane.appendChild(el('div',{class:'muted',text:'教学流程'}));editPane.appendChild(plan);
      var sectionppt=el('details',{class:'card'},el('summary',{text:'大屏讲解内容（用空行分隔页面）'}),ppt);sectionppt.addEventListener('toggle',function(){if(sectionppt.open)growTextarea(ppt)});editPane.appendChild(sectionppt);
      var sectionex=el('details',{class:'card'},el('summary',{text:'例题（每行一条）'}),ex);sectionex.addEventListener('toggle',function(){if(sectionex.open)growTextarea(ex)});editPane.appendChild(sectionex);
      var sectioncl=el('details',{class:'card'},el('summary',{text:'课后练习'}),cl);sectioncl.addEventListener('toggle',function(){if(sectioncl.open)growTextarea(cl)});editPane.appendChild(sectioncl);
      var saveStatus=el('div',{role:'status','aria-live':'polite'});
      var saveButton=el('button',{text:'保存教案',onclick:function(){
        saveLessonEdits('/teacher/weekend/lessons/'+r.lessonId,{title:title.value.trim(),coreTarget:tgt.value,teacherPlan:plan.value,closureTraining:cl.value,examples:ls(ex),ppt:ppt.value.split(/\n\s*\n/).map(function(x){return x.trim()}).filter(Boolean)},saveButton,saveStatus,[title,tgt,plan,ppt,ex,cl],function(){api('/teacher/weekend/schedule?subject='+encodeURIComponent(SUBJ)).then(function(d){var st=d.items.filter(function(x){return x.lessonId===r.lessonId})[0];if(st)refreshStatus(st)})});
      }});
      editPane.appendChild(saveButton);editPane.appendChild(saveStatus);
      if(L.previousImportId){
        var undo=el('button',{text:'恢复重新导入前的整份教案',onclick:function(){
          if(!confirm('恢复上一次导入前的教案、习题和互动课件？当前未保存的编辑将丢失。'))return;
          undo.disabled=true;
          api('/teacher/weekend/lessons/'+r.lessonId+'/import-history/'+L.previousImportId+'/restore',{json:{}}).then(function(st){
            refreshStatus(st);lessonDetail(r,box,refreshStatus);note('ok','已恢复导入前的整份教案。');
          }).catch(function(e){saveStatus.textContent=e.message;undo.disabled=false});
        }});
        editPane.appendChild(undo);
      }
      var qbox=el('div'),wbox=el('div'),exampleBox=el('div',{class:'card'}),reviewList=el('div',{'data-review-list':'true'}),reviewNote=el('p',{class:'muted'}),choiceCards=[],writtenCards=[];
      var summaryLine=el('div',{class:'notice','data-practice-summary':'1'});
      questionPane.appendChild(el('h2',{text:SUBJ==='语文'?'课堂练习管理（可选）':'习题审核'}));
      questionPane.appendChild(summaryLine);
      if(SUBJ==='语文'){
        questionPane.appendChild(el('p',{text:'阅读课和作文课的第5环节使用已审核任务；请核对题目和教师参考答案。课件审核与题目审核分开进行，生成草稿不代表可以开课。'}));
      }else{
        questionPane.appendChild(el('p',{text:'例题讲解只用于老师讲解（第3环节）；随堂练习由学生独立作答（第4环节）。例题和练习各有各的审核，一项通过不代表另一项也通过。'}));
        questionPane.appendChild(el('p',{class:'muted',text:'课堂建好后再通过的选择题会立即出现在第4环节；填空/简答/写作题在开课时复制一份进课堂，开课后新通过的这类题要新建课堂才生效。重新导入或修改教案后，例题会提示重新审核；已有课堂记录和学生作答不会被改动。'}));
      }
      questionPane.appendChild(el('h3',{text:SUBJ==='语文'?'例题与考点解析（仅教师讲解，不发题）':'例题讲解（第3环节，只讲不发题）'}));
      questionPane.appendChild(exampleBox);
      questionPane.appendChild(el('h3',{text:SUBJ==='语文'?'第5环节练习候选（可选，通过后发给学生）':'随堂练习候选（审核通过后进入第4环节）'}));
      questionPane.appendChild(practiceImportPanel());
      questionPane.appendChild(materialGroupPanel());
      questionPane.appendChild(qbox);questionPane.appendChild(wbox);questionPane.appendChild(reviewNote);questionPane.appendChild(reviewList);
      // The two APIs keep different question types in separate tables. Recover only
      // reliable source positions; never infer a cross-type order from database IDs.
      function renderSummary(s){
        if(!s)return;
        summaryLine.textContent='';
        if(SUBJ==='语文'){
          summaryLine.appendChild(el('span',{text:'可用练习 '+s.practiceReady+' 道 · 待确认练习 '+s.practiceDraft+' 道 · 互动课件'+(s.coursewareApproved?'已就绪':(s.coursewareStatus?'待确认':'未生成'))}));
        }else{
          summaryLine.appendChild(el('span',{text:'例题 '+s.exampleCount+' 道（待审核 '+s.examplePending+'）· 可用练习 '+s.practiceReady+' 道 · 待审核练习 '+s.practiceDraft+' 道 · 互动课件'+(s.coursewareApproved?'已通过':(s.coursewareStatus?'待审核':'未生成'))}));
          if(!s.practiceReady)summaryLine.appendChild(el('div',{class:'muted',text:'第4环节现在没有可发放的练习：还没有“已通过、又不与例题重复”的题。请通过几道练习，或单独导入随堂练习。'}));
        }
      }
      function reviewExamples(payload,btn,fb){
        if(btn)btn.disabled=true;
        api('/teacher/weekend/lessons/'+r.lessonId+'/examples/review',{json:payload}).then(function(d){
          note('ok',d.message);
          if(refreshStatus&&d.status)refreshStatus(d.status);
          renderSummary(d.summary);renderExamples(d);
        }).catch(function(e){
          if(btn)btn.disabled=false;
          if(fb){fb.className='notice error';fb.textContent=e.message}else note('error',e.message);
        });
      }
      function renderExamples(d){
        exampleBox.textContent='';
        var list=d.workedExamples||[];
        if(!list.length){
          exampleBox.appendChild(el('p',{class:'muted',text:'第3环节没有可识别的例题页：在“教案编辑 → 例题（每行一条）”里填写后，这里会出现逐题审核。'}));
          return;
        }
        var pending=list.filter(function(e){return e.status!=='approved'&&e.status!=='legacy'}).length;
        var head=el('div',{class:'row'},el('b',{text:'共 '+list.length+' 道例题'}),pending?el('span',{class:'tag warn',text:'待审核 '+pending}):el('span',{class:'tag ok',text:'全部已通过'}));
        if(pending)head.appendChild(el('button',{text:'全部标记为已通过（'+list.length+' 道）',onclick:function(){
          if(!confirm('确认已逐题核对这 '+list.length+' 道例题的题干、答案和配图？'))return;
          reviewExamples({approveAll:true},null,exampleBox);
        }}));
        exampleBox.appendChild(head);
        list.forEach(function(example){
          var fb=el('div',{role:'status','aria-live':'polite'}),act=el('div',{class:'row'});
          var cls=example.status==='approved'?'ok':(example.status==='legacy'?'':'warn');
          var item=el('div',{class:'item','data-example-index':String(example.pageIndex)},
            el('b',{text:example.label+'（讲解用）'}),el('span',{class:'tag '+cls,'data-example-status':example.status,text:example.statusText}),
            el('p',{text:example.stem}),act,fb);
          if(example.status==='approved'){
            act.appendChild(el('button',{text:'撤回审核',onclick:function(){reviewExamples({retract:[example.pageIndex]},null,fb)}}));
          }else if(example.status==='legacy'){
            // 旧课没有审核记录可撤回：撤回会变回“历史·已通过”，按钮会像没反应，所以只说明。
            act.appendChild(el('span',{class:'muted',text:'这节课在上线前就在，例题按“历史·已通过”显示；改动例题内容会要求重新审核。'}));
          }else{
            act.appendChild(el('button',{class:'primary',text:'核对通过',onclick:function(){reviewExamples({approve:[example.pageIndex]},null,fb)}}));
            if(example.status==='changed')act.appendChild(el('span',{class:'muted',text:'内容改过了，请重新核对题干、答案和配图'}));
          }
          exampleBox.appendChild(item);
        });
      }
      function practiceImportPanel(){
        var detail=el('details',{class:'card','data-practice-import':'1'},el('summary',{text:'单独导入随堂练习（不动教案和例题）'}));
        var text=el('textarea',{maxlength:20000,placeholder:'把练习题目粘贴到这里，例如：\n第1题（4分）一个平行四边形底 6 厘米、高 4 厘米，面积是多少？\nA．12 平方厘米  B．24 平方厘米  C．10 平方厘米\n第2题 计算下面图形的面积……'});
        var file=el('input',{type:'file',accept:'.docx,.pptx,.pdf,.txt,.md'});
        var run=el('button',{class:'primary',text:'导入到随堂练习候选'}),out=el('div',{role:'status','aria-live':'polite'});
        detail.addEventListener('toggle',function(){if(detail.open)growTextarea(text)});
        run.addEventListener('click',function(){
          if(!text.value.trim()&&!file.files.length){out.className='notice error';out.textContent='请先粘贴题目或选择一个文件。';return}
          var fd=new FormData();fd.append('text',text.value);
          if(file.files.length)fd.append('file',file.files[0]);
          run.disabled=true;out.className='muted';out.textContent='正在识别题目（约半分钟）…';
          api('/teacher/weekend/lessons/'+r.lessonId+'/practice/import',{method:'POST',body:fd}).then(function(d){
            out.className='notice';out.textContent=d.message;
            note('ok',d.message);text.value='';file.value='';run.disabled=false;
            if(refreshStatus&&d.status)refreshStatus(d.status);
            renderSummary(d.summary);loadQ();loadWritten();
          }).catch(function(e){out.className='notice error';out.textContent='导入失败：'+e.message;run.disabled=false});
        });
        detail.appendChild(el('p',{class:'muted',text:'第4环节要用的练习可以单独传上来或粘贴进来。识别出的题只进“随堂练习候选”，逐题通过后才发给学生；与本节例题重复的题会自动略过。'}));
        detail.appendChild(text);detail.appendChild(el('div',{class:'row'},file,run));detail.appendChild(out);
        return detail;
      }
      function materialGroupPanel(){
        var detail=el('details',{class:'card','data-material-group':'1'},el('summary',{text:'导入混合资料并分组（例题讲解／随堂练习）'}));
        var text=el('textarea',{maxlength:20000,placeholder:'把包含例题和练习的资料粘贴到这里，系统会按标题和题号提出分组建议；不确定条目会标为“待定”。'});
        var file=el('input',{type:'file',accept:'.docx,.pptx,.pdf,.txt,.md'});
        var previewBtn=el('button',{text:'识别并提出分组建议'}),applyBtn=el('button',{class:'primary',text:'一键确认当前分组并导入',hidden:true});
        var previewBox=el('div'),out=el('div',{role:'status','aria-live':'polite'}),grouped=[];
        detail.addEventListener('toggle',function(){if(detail.open)growTextarea(text)});
        function paintGrouped(){
          previewBox.textContent='';
          if(!grouped.length){applyBtn.hidden=true;return}
          applyBtn.hidden=false;
          var roleText={example:'例题讲解',practice:'随堂练习',pending:'待定（不入库）'};
          grouped.forEach(function(item){
            var badge=el('span',{class:'tag '+(item.role==='pending'?'warn':item.role==='example'?'ok':''),text:roleText[item.role]||'待定'});
            var toggle=el('button',{text:item.role==='example'?'改为随堂练习':'改为例题讲解',onclick:function(){
              item.role=item.role==='example'?'practice':'example';
              paintGrouped();
            }});
            var row=el('div',{class:'item','data-group-index':String(item.index)},
              el('div',{class:'row'},el('b',{text:'条目 '+item.index}),badge,toggle,el('span',{class:'muted',text:item.reason||''})),
              el('p',{style:'white-space:pre-wrap',text:item.text}));
            previewBox.appendChild(row);
          });
        }
        previewBtn.addEventListener('click',function(){
          if(!text.value.trim()&&!file.files.length){out.className='notice error';out.textContent='请先粘贴资料或选择一个文件。';return}
          var fd=new FormData();fd.append('text',text.value);
          if(file.files.length)fd.append('file',file.files[0]);
          previewBtn.disabled=true;out.className='muted';out.textContent='正在识别分组建议…';
          api('/teacher/weekend/lessons/'+r.lessonId+'/materials/preview',{method:'POST',body:fd}).then(function(d){
            grouped=d.items||[];paintGrouped();
            out.className='notice';out.textContent='已提出分组建议：例题 '+d.counts.example+' 条、练习 '+d.counts.practice+' 条、待定 '+d.counts.pending+' 条（待定条目不会自动塞入练习）。';
            previewBtn.disabled=false;
          }).catch(function(e){out.className='notice error';out.textContent=e.message;previewBtn.disabled=false});
        });
        applyBtn.addEventListener('click',function(){
          applyBtn.disabled=true;out.className='muted';out.textContent='正在按当前分组导入…';
          api('/teacher/weekend/lessons/'+r.lessonId+'/materials/apply',{json:{items:grouped.map(function(x){return {text:x.text,role:x.role}})}}).then(function(d){
            out.className='notice';out.textContent=d.message;
            note('ok',d.message);grouped=[];paintGrouped();text.value='';file.value='';applyBtn.disabled=false;
            if(refreshStatus&&d.status)refreshStatus(d.status);
            renderSummary(d.summary);loadQ();loadWritten();
          }).catch(function(e){out.className='notice error';out.textContent=e.message;applyBtn.disabled=false});
        });
        detail.appendChild(el('p',{class:'muted',text:'系统按标题、题号提出分组建议，不确定的内容标为“待定”；老师可逐题切换“例题讲解／随堂练习”，再一键确认导入。'}));
        detail.appendChild(text);detail.appendChild(el('div',{class:'row'},file,previewBtn,applyBtn));detail.appendChild(previewBox);detail.appendChild(out);
        return detail;
      }
      function reviewOrder(stem){
        var title=String(stem||''),direct=/^\s*第\s*(\d{1,3})\s*题/.exec(title);
        if(direct)return parseInt(direct[1],10);
        var source=String(L.sourceText||'').replace(/\s+/g,''),tail=title.split('\n').pop().replace(/\s+/g,'');
        if(!source||tail.length<14)return null;
        var hits={},segment,at,before,heading,no,offset;
        // Several unique 14-character matches guard against matching a generic
        // phrase in another question. Never guess when the source is ambiguous.
        for(offset=0;offset+14<=tail.length&&offset<120;offset+=7){
          segment=tail.slice(offset,offset+18);
          if(segment.length<14)continue;
          at=source.indexOf(segment);
          if(at<0||source.indexOf(segment,at+1)>=0)continue;
          before=source.slice(0,at);
          var re=/第(\d{1,3})题/g;
          no=null;
          while((heading=re.exec(before))!==null)no=parseInt(heading[1],10);
          if(no!==null)hits[no]=(hits[no]||0)+1;
        }
        var keys=Object.keys(hits).sort(function(a,b){return hits[b]-hits[a]});
        if(keys.length===1||(keys.length>1&&hits[keys[0]]>hits[keys[1]]))return Number(keys[0]);
        return null;
      }
      function reviewIdentity(q){
        var number=Object.prototype.hasOwnProperty.call(q,'originalNumber')?q.originalNumber:reviewOrder(q.stem);
        var last=String(q.stem||'').split('\n').pop();
        var partMatch=/^\s*(?:第\s*\d{1,3}\s*题\s*(?:\d+(?:\.\d+)?\s*分)?\s*[｜|]?\s*)?[（(]\s*(\d{1,2})\s*[）)]/.exec(last);
        var part=Object.prototype.hasOwnProperty.call(q,'partNumber')?q.partNumber:(partMatch?parseInt(partMatch[1],10):null);
        return {order:number==null?null:Number(number),part:part==null?null:Number(part),sourcePos:q.sourcePosition==null?null:Number(q.sourcePosition)};
      }
      function reviewLabel(meta,stem){
        if(meta.order===null)return '原题号待核对';
        var score=String(stem||'').match(/^\s*第\s*\d{1,3}\s*题\s*(\d+(?:\.\d+)?)\s*分/);
        return '第 '+meta.order+' 题'+(meta.part!==null?'（'+meta.part+'）':'')+(score?'　'+score[1]+' 分':'');
      }
      function reviewLine(stem,meta){
        var line=String(stem||'').split('\n').pop();
        line=line.replace(/^\s*第\s*\d{1,3}\s*题\s*(?:\d+(?:\.\d+)?\s*分)?\s*[｜|]?\s*/,'');
        if(meta.part!==null)line=line.replace(/^\s*[（(]\s*\d{1,2}\s*[）)]\s*/,'');
        return line.trim()||String(stem||'').split('\n').pop();
      }
      function renderReview(){
        var cards=choiceCards.concat(writtenCards);
        cards.sort(function(a,b){
          if(a.order!==null&&b.order!==null&&a.order!==b.order)return a.order-b.order;
          if(a.order!==null&&b.order===null)return -1;
          if(a.order===null&&b.order!==null)return 1;
          if(a.part!==null&&b.part!==null&&a.part!==b.part)return a.part-b.part;
          if(a.sourcePos!==null&&b.sourcePos!==null&&a.sourcePos!==b.sourcePos)return a.sourcePos-b.sourcePos;
          return a.seq-b.seq;
        });
        var dups=cards.filter(function(item){return item.duplicateOf});
        reviewList.textContent='';
        // 已有课件里如果例题和随堂练习是同一道题，这里先汇总成一条，老师不用逐条翻。
        if(dups.length){
          reviewList.appendChild(el('div',{class:'notice error','data-review-duplicates':String(dups.length),
            text:'本课有 '+dups.length+' 道随堂练习与例题或已通过的习题重复，不能当新题用：请在下面标红“⚠ 与…重复”的题上换一道同考点新题后再点通过；已经通过的旧题可以点“撤回通过（已上过的课不动）”。'}));
        }
        var totals={},groups={};
        cards.forEach(function(item){if(item.order!==null)totals[item.order]=(totals[item.order]||0)+1});
        cards.forEach(function(item){
          if(item.order!==null&&totals[item.order]>1){
            if(!groups[item.order]){
              groups[item.order]=el('section',{class:'card','data-review-group':String(item.order)},
                el('h3',{text:'第 '+item.order+' 题（'+totals[item.order]+'个审核条目，按小问分别审核）'}));
              reviewList.appendChild(groups[item.order]);
            }
            groups[item.order].appendChild(item.node);
          }else reviewList.appendChild(item.node);
        });
        var unknown=cards.filter(function(item){return item.order===null}).length;
        reviewNote.textContent=unknown?'按原教案题号排序；'+unknown+'道题未能可靠识别原文序号，暂排在末尾，请教师核对。':'按原教案题号顺序展示（题型不改变教学顺序）。';
      }
      function loadQ(){
        qbox.textContent='';choiceCards=[];
        api('/teacher/weekend/lessons/'+r.lessonId+'/questions').then(function(d){
          renderSummary(d.summary);renderExamples(d);
          if(!d.items.length){qbox.appendChild(el('p',{class:'muted',text:'暂时没有选择题候选。可以直接用上面的“单独导入随堂练习”，或让 AI 出习题。'}));renderReview();return}
          d.items.forEach(function(q,i){
            var meta=reviewIdentity(q);
            var opts=q.options.map(function(o,i){return 'ABCD'[i]+'. '+o+(i===q.correctIndex?' ✓':'')}).join('　');
            var levelTag=q.level?el('span',{class:'tag'+(q.level==='提高'?' warn':''),text:q.level}):null,
                checkTag=q.verified?el('span',{class:'tag ok',text:'已验算'}):(q.level&&SUBJ==='数学'?el('span',{class:'tag warn',text:'答案待核对'}):null);
            // 和例题或已通过习题重复的题不能直接通过：先给老师一个看得懂的红色提示。
            var dupTag=q.duplicateOf?el('span',{class:'tag',style:'background:#fef3f2;color:#b42318;border:1px solid #fda29b',text:'⚠ 与'+q.duplicateOf+'重复'}):null;
            var fig=typeof questionFigureImg==='function'?questionFigureImg(q.figure):null;
            var row=el('div',{class:'item'},el('span',{class:'t'},levelTag,checkTag,dupTag,el('b',{text:reviewLine(q.stem,meta)}),fig,el('div',{class:'muted',text:opts}),el('div',{class:'muted',text:q.explanation||''})));
            var badge=el('span',{class:'tag '+(q.active?'ok':'warn'),text:q.active?'已通过':'草稿'}),act=el('div',{class:'row'},badge),feedback=el('div',{role:'status','aria-live':'polite'});
            if(!q.active){
              var needFig=!!(q.mentionsFigure&&!fig),figConfirm=null;
              if(needFig){
                figConfirm=el('input',{type:'checkbox'});
                act.appendChild(el('label',{class:'row'},figConfirm,el('span',{class:'muted',text:'题干提到图示但无配图，确认仍通过'})));
              }
              var approve=el('button',{text:q.duplicateOf?'不能通过（重复）':'通过',disabled:!!q.duplicateOf,
                title:q.duplicateOf?'这道题与'+q.duplicateOf+'重复，请换一道同考点新题后再通过':'',
                onclick:function(){
                  if(q.duplicateOf){feedback.textContent='这道题与'+q.duplicateOf+'重复，请换一道同考点新题后再通过';return}
                  if(needFig&&!figConfirm.checked){feedback.textContent='题干提到了图示但当前缺少配图，请先补充配图或勾选“确认仍通过”。';return}
                  approveQuestionInPlace('/teacher/weekend/lessons/'+r.lessonId+'/questions',q,approve,act,badge,feedback,refreshStatus,figConfirm&&figConfirm.checked);
                }});
              act.appendChild(approve);
              act.appendChild(el('button',{text:'删除',onclick:function(){api('/teacher/weekend/lessons/'+r.lessonId+'/questions',{json:{remove:[q.id]}}).then(function(st){refreshStatus(st);loadQ()})}}));
            }
            if(q.active&&q.duplicateOf){
              // 旧课里已经通过的重复题：给一条退路，撤回后不再发放。选择题是每次现查“已通过”的题，
              // 所以已经上过的课的报告和成绩会按剩下的题重算；正在上课的课直接不给撤回。
              var retractChoice=el('button',{text:'撤回通过',onclick:function(){
                if(!window.confirm('撤回后这节课不再向学生发放这道题。选择题是每次现查已通过的题，已经上过的课如果用过这道题，报告和成绩会按剩下的题重算；正在上课的课不能撤回。'))return;
                retractChoice.disabled=true;
                api('/teacher/weekend/lessons/'+r.lessonId+'/questions',{json:{retract:[q.id]}}).then(function(st){refreshStatus(st);loadQ()}).catch(function(e){feedback.textContent=e.message;retractChoice.disabled=false});
              }});
              act.appendChild(retractChoice);
            }
            var order=meta.order,choiceCard=el('div',{class:'card','data-review-number':order===null?'':String(order)});
            choiceCard.appendChild(el('div',{class:'row'},el('b',{text:reviewLabel(meta,q.stem)})));
            choiceCard.appendChild(row);choiceCard.appendChild(act);choiceCard.appendChild(feedback);
            choiceCards.push({node:choiceCard,order:order,part:meta.part,sourcePos:meta.sourcePos,seq:i,duplicateOf:q.duplicateOf||''});
          });
          renderReview();
        }).catch(function(e){qbox.appendChild(el('div',{class:'notice error',text:e.message}));renderReview()});
      }
      function loadWritten(){
        wbox.textContent='';writtenCards=[];
        api('/teacher/weekend/lessons/'+r.lessonId+'/written/questions').then(function(d){
          wbox.appendChild(el('h2',{text:'填答案、阅读简答与写作（'+d.items.length+' 题）'}));
          var todo=d.items.filter(function(q){return !q.knowledge&&q.suggestedKnowledge});
          if(d.items.length)wbox.appendChild(el('p',{class:'muted',text:'每道题标一个考点（标一次，这节课的所有班级通用），课后总结和家长报告会按考点写；课后才做的题勾“课后题”，没交不算课堂未提交。'}));
          if(todo.length){var all=el('button',{text:'采用全部考点建议（'+todo.length+' 题）',onclick:function(){
            all.disabled=true;var chain=Promise.resolve();
            todo.forEach(function(q){chain=chain.then(function(){return api('/teacher/weekend/lessons/'+r.lessonId+'/written/questions/'+q.id+'/marks',{method:'PUT',json:{knowledge:q.suggestedKnowledge,afterClass:!!q.afterClass}})})});
            chain.then(loadWritten).catch(function(e){alert(e.message);all.disabled=false});
          }});wbox.appendChild(all)}
          if(!d.items.length)wbox.appendChild(el('p',{class:'muted',text:'还没有此类题目。重新导入原教案可提取原有简答／写作题，或使用 AI 出习题。'}));
          d.items.forEach(function(q,i){
            var meta=reviewIdentity(q),order=meta.order;
            var labels={short_answer:'阅读简答／过程题',final_answer:'填最终答案',composition:'写作／复述'},card=el('div',{class:'card','data-review-number':order===null?'':String(order)});
            var badge=el('span',{class:'tag '+(q.approved?'ok':'warn'),text:q.approved?'已通过':'草稿'}),
                dupTag=q.duplicateOf?el('span',{class:'tag',style:'background:#fef3f2;color:#b42318;border:1px solid #fda29b',text:'⚠ 与'+q.duplicateOf+'重复'}):null;
            card.appendChild(el('div',{class:'row'},el('b',{text:reviewLabel(meta,q.stem)}),el('span',{class:'tag',text:labels[q.type]||'简答题'}),q.level?el('span',{class:'tag'+(q.level==='提高'?' warn':''),text:q.level}):null,q.verified?el('span',{class:'tag ok',text:'已验算'}):(SUBJ==='数学'&&q.level&&q.type!=='composition'?el('span',{class:'tag warn',text:'答案待核对'}):null),dupTag,badge));
            var parts=q.stem.split('\n'),questionLine=parts.pop();
            card.appendChild(el('p',{style:'white-space:pre-wrap;font-weight:600',text:reviewLine(questionLine,meta)}));
            var wfig=typeof questionFigureImg==='function'?questionFigureImg(q.figure):null;if(wfig)card.appendChild(wfig);
            if(parts.length)card.appendChild(el('details',{},el('summary',{text:'展开阅读材料／题目全文'}),el('pre',{style:'white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;line-height:1.7',text:parts.join('\n')})));
            var edit=el('details'),stem=el('textarea',{maxlength:20000}),ref=el('textarea',{maxlength:4000}),hs=[];
            edit.appendChild(el('summary',{text:'修改题目、评分要点与提示'}));stem.value=q.stem;ref.value=q.reference||'';
            edit.appendChild(el('p',{text:'题目及阅读材料（学生可见）'}));edit.appendChild(stem);
            edit.appendChild(el('p',{text:'参考答案／评分要点（仅老师可见）'}));edit.appendChild(ref);
            ['方向提示','第一步提示','完整思路'].forEach(function(label,i){var h=el('textarea',{placeholder:label+'（可全留空；填写则需完整三级）',maxlength:300});h.value=(q.hints||[])[i]||'';hs.push(h);edit.appendChild(h)});
            edit.addEventListener('toggle',function(){if(edit.open)Array.prototype.forEach.call(edit.querySelectorAll('textarea'),growTextarea)});
            var state=el('div',{role:'status','aria-live':'polite'}),save=el('button',{text:'保存修改（需重新审核）',onclick:function(){
              save.disabled=true;var hints=hs.map(function(h){return h.value.trim()});
              api('/teacher/weekend/lessons/'+r.lessonId+'/written/questions/'+q.id,{method:'PUT',json:{stem:stem.value,reference:ref.value,type:q.type,hints:hints.some(Boolean)?hints:[]}}).then(function(st){refreshStatus(st);loadWritten()}).catch(function(e){state.textContent=e.message;save.disabled=false});
            }});edit.appendChild(save);edit.appendChild(state);card.appendChild(edit);
            var feedback=el('div',{role:'status','aria-live':'polite'}),actions=el('div',{class:'row'});
            if(!q.approved){
              var wNeedFig=!!(q.mentionsFigure&&!wfig),wFigConfirm=null;
              if(wNeedFig){
                wFigConfirm=el('input',{type:'checkbox'});
                actions.appendChild(el('label',{class:'row'},wFigConfirm,el('span',{class:'muted',text:'题干提到图示但无配图，确认仍通过'})));
              }
              var approveWritten=el('button',{text:q.duplicateOf?'不能通过（重复）':'通过',disabled:!!q.duplicateOf,
                title:q.duplicateOf?'这道题与'+q.duplicateOf+'重复，请换一道新题后再通过':'',
                onclick:function(){
                  if(q.duplicateOf){feedback.textContent='这道题与'+q.duplicateOf+'重复，请换一道新题后再通过';return}
                  if(wNeedFig&&!wFigConfirm.checked){feedback.textContent='题干提到了图示但当前缺少配图，请先补充配图或勾选“确认仍通过”。';return}
                  approveQuestionInPlace('/teacher/weekend/lessons/'+r.lessonId+'/written/questions',q,approveWritten,actions,badge,feedback,refreshStatus,wFigConfirm&&wFigConfirm.checked);
                }});
              actions.appendChild(approveWritten);
              var removeWritten=el('button',{text:'删除草稿',onclick:function(){
                removeWritten.disabled=true;
                api('/teacher/weekend/lessons/'+r.lessonId+'/written/questions',{json:{remove:[q.id]}}).then(function(st){refreshStatus(st);loadWritten()}).catch(function(e){feedback.textContent=e.message;removeWritten.disabled=false});
              }});
              actions.appendChild(removeWritten);
            }
            if(q.approved&&q.duplicateOf){
              // 与例题重复的旧题已经通过：撤回后不再发给学生。文字题在开课时复制一份进课堂，
              // 已上过的课用的是当时那份副本，不受撤回影响。
              var retractWritten=el('button',{text:'撤回通过',onclick:function(){
                if(!window.confirm('撤回后这节课不再向学生发放这道题。已经上过的课用的是开课时复制的那份，不受影响。'))return;
                retractWritten.disabled=true;
                api('/teacher/weekend/lessons/'+r.lessonId+'/written/questions',{json:{retract:[q.id]}}).then(function(st){refreshStatus(st);loadWritten()}).catch(function(e){feedback.textContent=e.message;retractWritten.disabled=false});
              }});
              actions.appendChild(retractWritten);
            }
            card.appendChild(markBox(r.lessonId,{templateId:q.id,knowledge:q.knowledge,afterClass:q.afterClass,suggestedKnowledge:q.suggestedKnowledge},d.goals));
            card.appendChild(actions);card.appendChild(feedback);
            writtenCards.push({node:card,order:order,part:meta.part,sourcePos:meta.sourcePos,seq:10000+i,duplicateOf:q.duplicateOf||''});
          });
          renderReview();
        }).catch(function(e){wbox.appendChild(el('div',{class:'notice error',text:e.message}));renderReview()});
      }
      loadQ();loadWritten();
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
    return _page("课堂练习", STUDENT_BOOT + COURSEWARE_JS + WRITTEN_JS + PRACTICE_JS, True)


def plan_page_html() -> str:
    return _page("周末课备课", COURSEWARE_JS + COURSEWARE_PLAN_JS + PLAN_JS, True, ("/v1/weekend", "返回周末课"))


def brief_page_html() -> str:
    return _page("周末课学情反馈", PARENT_JS, True)


def report_page_html() -> str:
    return _page("课后总结与家长反馈", WRITTEN_JS + REPORT_JS, True, ("/v1/weekend", "返回周末课"))


def control_page_html() -> str:
    return _page("周末课", OPEN_WINDOW_JS + WRITTEN_JS + COURSEWARE_JS + CONTROL_JS, True, ("/v1/workspace", "返回"))


def board_page_html() -> str:
    return _page("课堂大屏", COURSEWARE_JS + BOARD_LAYOUT_JS + BOARD_JS, False)


__all__ = ["board_page_html", "brief_page_html", "control_page_html", "plan_page_html", "practice_page_html", "report_page_html"]


