"""周末课页面:老师控制条 + 大屏 (static HTML, ES5)."""

from __future__ import annotations

from changying.web.classroom_window_handoff import PAGE_AUTH_JS
from changying.web.homework_assistant_pages import PAGE_CSS

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
  var head=el('div',{class:'card'}),stagesBox=el('div',{class:'card'}),content=el('div',{class:'card'}),msgBox=el('div'),
      progBox=el('div',{class:'card'}),hintBox=el('div',{class:'card'});
  root.appendChild(head);root.appendChild(stagesBox);root.appendChild(content);root.appendChild(progBox);root.appendChild(hintBox);root.appendChild(msgBox);
  hintsCard(hintBox);
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
    box.textContent='';box.appendChild(el('h2',{text:'随堂练习进度（班级完成率 '+p.classCompletionRate+'%）'}));
    if(!p.items.length){box.appendChild(el('div',{class:'muted',text:'没有学生。学生要在“我的班级”里属于你的班级。'}));return}
    p.items.forEach(function(i){
      box.appendChild(el('div',{class:'row'},el('b',{text:i.name}),
        el('span',{class:'tag',text:'做完 '+i.answered+'/'+i.total}),el('span',{class:'tag',text:'做对 '+i.correct}),
        el('span',{class:'tag '+(i.hintMax>=2?'warn':''),text:'提示最高 '+i.hintMax+' 级 · 平均 '+i.hintAvg}),
        el('span',{class:'muted',text:'完成率 '+i.completionRate+'%'})));
    });
  }).catch(function(){});
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
function picker(){
  var sel=el('select'),list=el('div'),go=el('button',{class:'primary',text:'创建这节课堂',onclick:function(){
    if(!sel.value)return;api('/teacher/weekend/sessions',{json:{lessonId:+sel.value}}).then(function(d){location.href='/v1/weekend?s='+d.id}).catch(function(e){alert(e.message)})}});
  root.appendChild(el('div',{class:'card'},el('h2',{text:'周末课：选择今天的课'}),
    el('div',{class:'muted',text:'课时来自“定制教学”里的教案；每节课固定 7 个环节、共 120 分钟。'}),el('div',{class:'row'},sel,go)));
  root.appendChild(el('div',{class:'card'},el('h2',{text:'最近的课堂'}),list));
  api('/teacher/weekend/lessons').then(function(d){
    if(!d.items.length){sel.appendChild(el('option',{value:'',text:'还没有课时，请先在“定制教学”里建立'}));return}
    d.items.forEach(function(l){sel.appendChild(el('option',{value:l.id,text:l.subject+' 第'+l.lessonNo+'课 '+l.title}))});
  });
  api('/teacher/weekend/sessions').then(function(d){
    if(!d.items.length){list.appendChild(el('div',{class:'muted',text:'还没有。'}));return}
    d.items.forEach(function(s){list.appendChild(el('div',{class:'row'},el('a',{href:'/v1/weekend?s='+s.id,text:s.title}),el('span',{class:'muted',text:s.createdAt+' · '+(s.status==='finished'?'已结束':s.status==='running'?'进行中':'未开始')})))});
  });
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
    d.content.forEach(function(x){wrap.appendChild(el('p',{style:'font-size:4vh;line-height:1.5;margin:1.5vh 0',text:x}))});
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
  load();
  wait=setInterval(function(){if(!document.hidden)load()},20000);
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


def _page(title: str, js: str, with_header: bool) -> str:
    html = PAGE_HTML.replace("__TITLE__", title).replace("__CSS__", PAGE_CSS + EXTRA_CSS)
    if with_header:
        html = html.replace("<body>", f'<body><header><h1>{title}</h1><a href="/v1">返回首页</a></header>', 1)
    return html.replace("__JS__", (COMMON_JS + js).replace("__PAGE_AUTH__", PAGE_AUTH_JS))


STUDENT_BOOT = r"""
function boot_student(run){
  obtainToken().then(function(t){TOKEN=t;if(!TOKEN){msg('请先登录后再打开');return}
    return api('/session').then(function(s){if(s.role!=='student'){msg('这个页面给学生使用');return}run()})}).catch(function(e){msg(e.message||'打不开')});
}
"""


def practice_page_html() -> str:
    return _page("课堂练习", STUDENT_BOOT + PRACTICE_JS, True)


def control_page_html() -> str:
    return _page("周末课控制台", CONTROL_JS, True)


def board_page_html() -> str:
    return _page("课堂大屏", BOARD_JS, False)


__all__ = ["board_page_html", "control_page_html", "practice_page_html"]
