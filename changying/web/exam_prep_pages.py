"""应试专项页面 (static HTML, ES5)：教师（考试目标、模拟卷、失分点、专项、再测、趋势、报告）、学生限时作答、家长提分报告."""

from __future__ import annotations

from changying.web.cube_figures_js import CUBES_JS
from changying.web.weekend_pages import _page

COMMON_EXAM_JS = r"""
function epTable(head,rows){
  var cell='padding:6px 8px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top',t=el('table',{style:'border-collapse:collapse;width:100%'});
  var hr=el('tr');head.forEach(function(h){hr.appendChild(el('th',{text:h,style:cell}))});t.appendChild(hr);
  rows.forEach(function(r){var tr=el('tr');r.forEach(function(c){tr.appendChild(el('td',{text:c==null?'':String(c),style:cell}))});t.appendChild(tr)});
  if(head.length>4)t.style.minWidth='640px';           // wide tables scroll sideways on a phone instead of squeezing
  return el('div',{style:'overflow-x:auto'},t);
}
function epBoot(role,run){
  obtainToken().then(function(t){TOKEN=t;if(!TOKEN){msg('请先登录后再打开');return}
    return api('/session').then(function(s){if(s.role!==role){msg(role==='student'?'这个页面给学生使用':(role==='parent'?'这个页面给家长使用':'只有老师可以使用'));return}run()})}).catch(function(e){msg(e.message||'打不开')});
}
"""

EXAM_PREP_JS = COMMON_EXAM_JS + r"""
var EPMSG=null,EPBOX=null,EPDATA=null;
function epSay(text,bad){EPMSG.textContent=text||'';EPMSG.className=bad?'card warn':'muted'}
function epDays(n){return n>0?'距考试 '+n+' 天':(n===0?'今天考试':'已考完 '+(-n)+' 天')}
function epNewForm(box){
  box.textContent='';
  if(!EPDATA.maps.length){
    var base=EPDATA.baseline;
    box.appendChild(el('div',{class:'card'},el('h3',{text:base?'网站自带五上数学知识地图':'还没有可用知识地图'}),
      el('p',{text:base?'基础目录已备好：'+base.units.map(function(u){return u.name}).join('、')+'。先启用本校目录，即可按单元建立考试目标；发卷仍需要本校已审核的足量题目，学生地图不会自动发布。':'应试专项按知识地图的单元和知识点出题，请先在“知识地图”里创建并发布。'}),
      el('a',{class:'btn',href:'/v1/knowledge-map',text:base?'查看并启用基础目录':'去知识地图'})));return}
  if(!EPDATA.classes.length){box.appendChild(el('div',{class:'card'},el('p',{text:'还没有班级，请先在“我的班级”创建班级并添加学生。'})));return}
  var title=el('input',{value:'期末',maxlength:'60','aria-label':'考试名称'}),date=el('input',{type:'date','aria-label':'考试日期'}),
      cls=el('select',{'aria-label':'班级'}),map=el('select',{'aria-label':'知识地图'}),units=el('div',{class:'row'});
  EPDATA.maps.forEach(function(m){map.appendChild(el('option',{value:m.id,text:m.title}))});
  var scopeNote=el('p',{class:'muted'}),classNote=el('p',{class:'muted',role:'status'}),createButton;
  function paintUnits(){units.textContent='';var m=EPDATA.maps.filter(function(x){return String(x.id)===map.value})[0];
    scopeNote.textContent=m.published?'使用已发布的学校地图。':'使用网站五上基础目录建立目标；尚未发布给学生，发卷前须核对本校题库是否有足量的审核题。';
    var previous=cls.value,matching=EPDATA.classes.filter(function(c){return String(c.grade)===String(m.grade)});
    cls.textContent='';matching.forEach(function(c){cls.appendChild(el('option',{value:c.id,text:c.name}))});
    if(matching.length){cls.value=matching.some(function(c){return String(c.id)===previous})?previous:String(matching[0].id);
      classNote.textContent='只显示与知识地图相同年级的班级（'+m.grade+'年级）。';classNote.className='muted'}
    else{classNote.textContent='这份知识地图是'+m.grade+'年级，目前没有同年级班级。请先到“我的班级”建立'+m.grade+'年级班级，再创建考试目标。';classNote.className='card warn'}
    cls.disabled=!matching.length;if(createButton)createButton.disabled=!matching.length;
    m.units.forEach(function(u){units.appendChild(el('label',{},el('input',{type:'checkbox',value:u.key,checked:!!m.published}),' '+u.name))})}
  map.addEventListener('change',paintUnits);
  createButton=el('button',{class:'btn primary',text:'创建',onclick:function(){
      var keys=Array.prototype.filter.call(units.querySelectorAll('input'),function(i){return i.checked}).map(function(i){return i.value});
      if(!cls.value){epSay('请先到“我的班级”建立与知识地图同年级的班级',true);return}
      if(!date.value){epSay('请选择考试日期',true);return}if(!keys.length){epSay('请至少勾选一个单元',true);return}
      epSay('正在创建…');api('/teacher/exam-goals',{json:{title:title.value,examDate:date.value,classId:+cls.value,mapId:+map.value,unitKeys:keys}})
        .then(function(g){epSay('已创建');epGoal(g.id)}).catch(function(e){epSay(e.message,true)})}});
  paintUnits();
  box.appendChild(el('div',{class:'card'},el('h2',{text:'新建考试目标'}),
    el('div',{class:'row'},el('label',{},'考试名称 ',title)),el('div',{class:'row'},el('label',{},'考试日期 ',date)),
    el('div',{class:'row'},el('label',{},'班级 ',cls)),classNote,el('div',{class:'row'},el('label',{},'知识地图 ',map)),scopeNote,
    el('p',{class:'muted',text:'考试范围（勾选要考的单元）：'}),units,
    el('div',{class:'row'},createButton,
      el('button',{class:'btn',text:'取消',onclick:function(){box.textContent=''}}))));
}
function epFocus(x){return x.focus.length?x.focus.map(function(f){return f.name+'（失 '+f.lostMarks+'/'+f.marks+' 分）'}).join('；'):'全对，保持'}
function epEvidence(x){
  var ev=x.pointEvidence||{};var keys=Object.keys(ev);
  if(!keys.length)return '—';
  return keys.map(function(k){
    var arr=ev[k]||[];
    var name=k;
    (x.focus||[]).forEach(function(f){if(f.key===k)name=f.name});
    return name+'：'+arr.map(function(it){return it.source+'（'+(it.helpStatus||'未知')+'）'}).join('、');
  }).join('；');
}
function epTime(x){if(x.minutes==null)return '未计时';return x.minutes+' 分钟'+(x.overtime?'（超时 '+x.overtime+' 分钟）':'')}
function epDrill(x){if(!x.drill)return '—';return x.drill.questionCount+' 题 · '+(x.drill.handedIn?'已交，做对 '+x.drill.correct:'未交')}
function epReports(gid,p,box){
  box.textContent='';box.appendChild(el('p',{class:'muted',text:'正在生成草稿…'}));
  api('/teacher/exam-goals/'+gid+'/papers/'+p.id+'/reports',{json:{}}).then(function(d){
    box.textContent='';
    box.appendChild(el('p',{class:'muted',text:'草稿只用系统记录的结果生成，不排名、不和别人比；加上老师的话后逐个发布，家长在“孩子学情”里看到。'}));
    if(!d.items.length){box.appendChild(el('p',{text:'还没有学生交卷。'}));return}
    d.items.forEach(function(r){
      var note=el('textarea',{'aria-label':'老师的话'});note.value=r.note||'';var st=el('span',{class:'muted',role:'status'});
      var view=el('div');r.draft.lines.forEach(function(l){view.appendChild(el('p',{text:l}))});
      view.appendChild(el('p',{text:'现在是'+r.draft.stage+'阶段：'+r.draft.advice}));
      if(r.draft.change)view.appendChild(el('p',{text:'再测对比：'+r.draft.change.map(function(c){return c.name+' '+c.verdict}).join('；')}));
      st.textContent=r.published?('已发布 '+r.publishedAt+(r.changedSincePublish?' · 有改动未发布':'')):'未发布';
      box.appendChild(el('div',{class:'card','data-report':String(r.id)},el('b',{text:r.name}),view,el('label',{},'老师的话（可空） ',note),
        el('div',{class:'row'},
          el('button',{class:'btn',text:'保存',onclick:function(){api('/teacher/exam-reports/'+r.id,{method:'PUT',json:{note:note.value}}).then(function(x){st.textContent='已保存'+(x.published?' · 家长看到的还是上次发布的版本':'')}).catch(function(e){st.textContent=e.message})}}),
          el('button',{class:'btn primary',text:'保存并发布给家长',onclick:function(){api('/teacher/exam-reports/'+r.id,{method:'PUT',json:{note:note.value}}).then(function(){return api('/teacher/exam-reports/'+r.id+'/publish',{json:{}})}).then(function(x){st.textContent='已发布 '+x.publishedAt}).catch(function(e){st.textContent=e.message})}}),st)));
    });
  }).catch(function(e){box.textContent='';box.appendChild(el('p',{class:'warn',text:e.message}))});
}
function epAnalysis(gid,p,box){
  box.textContent='';box.appendChild(el('p',{class:'muted',text:'正在统计…'}));
  api('/teacher/exam-goals/'+gid+'/papers/'+p.id+'/analysis').then(function(d){
    box.textContent='';
    box.appendChild(el('p',{text:'已交 '+d.handedIn+' / '+d.classSize+' 人。卷面 '+d.paper.totalMarks+' 分（选择 2、判断 1、填空 2、计算 3、解决问题 5 分）；没做或没做对都算失分。每个学生只列失分最多的 3 个知识点。'}));
    if(d.points.length){box.appendChild(el('h4',{text:'全班：哪里丢分最多'}));
      box.appendChild(epTable(['知识点','全班失分题次','失分率（按分值）'],d.points.map(function(x){return [x.key+' '+x.name,x.lost+' / '+x.asked,x.rate+'%']})))}
    box.appendChild(el('h4',{text:'每个学生'}));
    var retest=d.paper.kind==='retest';
    var head=['学生','得分','用时','先补这几个知识点','失分点跨场景证据','专项练习'];if(retest){head.splice(2,0,'上次');head.push('上次失分点现在')}
    if(d.evidenceDisclaimer)box.appendChild(el('p',{class:'muted',text:d.evidenceDisclaimer}));
    box.appendChild(epTable(head,d.pupils.map(function(x){
      var row=[x.name,x.handedIn?x.score+' 分':'未交'];if(retest)row.push(x.before!=null?x.before+' 分':'—');
      row.push(x.handedIn?epTime(x):'—',x.handedIn?epFocus(x):'—',x.handedIn?epEvidence(x):'—',epDrill(x));
      if(retest)row.push(x.change?x.change.map(function(c){return c.name+'：'+c.verdict+(c.before!=null&&c.after!=null?'（失分率 '+c.before+'%→'+c.after+'%）':'')}).join('；'):'—');
      return row})));
    var res=el('div',{role:'status'}),per=el('input',{type:'number',min:'1',max:'6',value:'4','aria-label':'每个知识点几题'}),rpt=el('div');
    var acts=el('div',{class:'row'},el('label',{},'每个失分点 ',per,' 题'),
      el('button',{class:'btn primary',text:'给每个学生布置专项练习',onclick:function(){res.textContent='正在布置…';
        api('/teacher/exam-goals/'+gid+'/papers/'+p.id+'/drill',{json:{perPoint:+per.value}}).then(function(r){
          res.textContent=r.results.map(function(x){return x.name+'：'+(x.ok?'已布置 '+x.questionCount+' 题':x.reason)}).join('；');epAnalysis(gid,p,box)}).catch(function(e){res.textContent=e.message})}}));
    if(!retest)acts.appendChild(el('button',{class:'btn',text:'发再测卷（同样的知识点、新题）',onclick:function(){res.textContent='正在组卷…';
      api('/teacher/exam-goals/'+gid+'/papers/'+p.id+'/retest',{json:{timeLimit:p.timeLimit}}).then(function(r){res.textContent='已发出《'+r.title+'》：'+r.questionCount+' 题。'+(r.short?'没用过的题不够，题数比模拟卷少。':'');epGoal(gid)}).catch(function(e){res.textContent=e.message})}}));
    acts.appendChild(el('button',{class:'btn',text:'生成家长提分报告',onclick:function(){epReports(gid,p,rpt)}}));
    box.appendChild(acts);box.appendChild(res);box.appendChild(rpt);
  }).catch(function(e){box.textContent='';box.appendChild(el('p',{class:'warn',text:e.message}))});
}
function epTrend(gid,box){
  api('/teacher/exam-goals/'+gid+'/trend').then(function(d){box.textContent='';
    if(!d.papers.length){box.appendChild(el('p',{class:'muted',text:'还没有卷子。'}));return}
    box.appendChild(epTable(['学生'].concat(d.papers.map(function(p){return p.title.replace(/^.*· /,'')})),d.pupils.map(function(x){return [x.name].concat(x.scores.map(function(s){return s==null?'—':s+' 分'}))})));
  }).catch(function(e){box.textContent=e.message});
}
function epGoal(gid){
  api('/teacher/exam-goals/'+gid).then(function(g){
    EPBOX.textContent='';
    EPBOX.appendChild(el('div',{class:'row'},el('button',{class:'btn',text:'‹ 全部考试目标',onclick:epStart})));
    EPBOX.appendChild(el('div',{class:'card'},el('h2',{text:g.title+' · '+g.className}),
      el('p',{text:g.examDate+'　'+epDays(g.daysLeft)}),
      el('p',{class:'notice',text:'现在是'+g.plan.stage+'阶段：'+g.plan.advice}),
      el('p',{class:'muted',text:'范围：'+g.units.map(function(u){return u.name}).join('、')+'（共 '+g.points.length+' 个知识点，来自'+g.mapTitle+'）'})));
    var count=el('input',{type:'number',min:'6',max:'40',value:'20','aria-label':'题数'}),limit=el('input',{type:'number',min:'10',max:'120',value:'60','aria-label':'限时（分钟）'}),
        sample=el('select',{'aria-label':'参照样卷'}),res=el('div',{role:'status'});
    sample.appendChild(el('option',{value:'',text:'不参照（按知识点轮流）'}));
    (EPDATA&&EPDATA.samplePapers||[]).forEach(function(s){sample.appendChild(el('option',{value:s.id,text:s.title+'（'+s.questionCount+' 题）'}))});
    EPBOX.appendChild(el('div',{class:'card'},el('h3',{text:'发一份模拟卷'}),
      el('p',{class:'muted',text:'从范围内每个知识点已分档的题（和题库里同名知识点的题）中，按知识点轮流、难度以中等和基础为主组卷，作为全班作业发出。选了参照样卷（例如导入的往年真题），题型比例会照着样卷来。学生从首页“限时模拟卷”进入，开始后计时。'}),
      el('div',{class:'row'},el('label',{},'题数 ',count),el('label',{},'限时（分钟） ',limit)),el('div',{class:'row'},el('label',{},'参照样卷 ',sample)),
      el('div',{class:'row'},el('button',{class:'btn primary',text:'组卷并发给全班',onclick:function(){res.textContent='正在组卷…';
          var body={count:+count.value,timeLimit:+limit.value};if(sample.value)body.samplePaperId=+sample.value;
          api('/teacher/exam-goals/'+gid+'/mock',{json:body}).then(function(r){
            res.textContent='已发出《'+r.title+'》：'+r.questionCount+' 题，'+r.recipients+' 名学生。'+(r.short?'范围内的题不够，题数比你要的少。':'');epGoal(gid)})
            .catch(function(e){res.textContent=e.message})}})),res));
    var list=el('div',{class:'card'},el('h3',{text:'卷子与失分点'}));EPBOX.appendChild(list);
    if(!g.papers.length)list.appendChild(el('p',{class:'muted',text:'还没有发过模拟卷。'}));
    g.papers.forEach(function(p){var box=el('div');
      list.appendChild(el('div',{class:'card','data-paper':String(p.id)},el('b',{text:p.title}),el('span',{class:'muted',text:'　'+p.questionCount+' 题 · 限时 '+p.timeLimit+' 分钟 · 截止 '+p.dueDate+' · 已交 '+p.handedIn+' 人'+(p.drills?' · 专项练习 '+p.drills+' 人':'')}),
        el('div',{class:'row'},el('button',{class:'btn',text:'看失分点',onclick:function(){epAnalysis(gid,p,box)}})),box))});
    var tr=el('div');EPBOX.appendChild(el('div',{class:'card'},el('h3',{text:'成绩变化（只和自己比）'}),tr));epTrend(gid,tr);
  }).catch(function(e){epSay(e.message,true)});
}
function epStart(){
  root.textContent='';EPMSG=el('div',{class:'muted',role:'status'});EPBOX=el('div');root.appendChild(EPMSG);root.appendChild(EPBOX);
  api('/teacher/exam-goals').then(function(d){
    EPDATA=d;var form=el('div');
    EPBOX.appendChild(el('div',{class:'card'},el('h2',{text:'应试专项'}),
      el('p',{text:'为一次考试（期中、期末）建一个目标：发模拟卷摸底 → 找出每个学生失分最多的知识点 → 布置专项练习 → 发再测卷看有没有补上 → 给家长发提分报告。只和学生自己比，不排名。'}),
      el('button',{class:'btn primary',text:'新建考试目标',onclick:function(){epNewForm(form)}})));
    EPBOX.appendChild(form);
    if(!d.items.length){EPBOX.appendChild(el('p',{class:'muted',text:'还没有考试目标。'}));return}
    d.items.forEach(function(g){EPBOX.appendChild(el('div',{class:'card'},el('b',{text:g.title+' · '+g.className}),
      el('span',{class:'muted',text:'　'+g.examDate+' · '+epDays(g.daysLeft)+' · '+g.plan.stage+' · 卷子 '+g.papers.length+' 份'}),
      el('div',{class:'row'},el('button',{class:'btn',text:'打开',onclick:function(){epGoal(g.id)}}))))});
  }).catch(function(e){epSay(e.message,true)});
}
epBoot('teacher',epStart);
"""

PAPER_JS = COMMON_EXAM_JS + r"""
var EXT=null,EXAID=+(new URLSearchParams(location.search).get('a')||0);
function exKey(aid){return 'cy-exam-'+aid}
function exLoad(aid){try{return JSON.parse(localStorage.getItem(exKey(aid))||'{}')}catch(_e){return {}}}
function exKeep(aid,v){try{localStorage.setItem(exKey(aid),JSON.stringify(v))}catch(_e){}}
function exList(){
  root.textContent='';
  api('/student/exam-papers').then(function(d){
    var open=d.items.filter(function(x){return !x.handedIn}),done=d.items.filter(function(x){return x.handedIn});
    root.appendChild(el('div',{class:'card'},el('h2',{text:'限时模拟卷'}),el('p',{text:'像真正考试一样：开始后计时，一次做完，不翻书、不问人。时间到了还没写完也可以交，老师会看到你用了多久。'})));
    if(!open.length)root.appendChild(el('div',{class:'card'},el('p',{text:'现在没有要做的模拟卷。'})));
    open.forEach(function(x){root.appendChild(el('div',{class:'card'},el('b',{text:x.title}),el('p',{class:'muted',text:x.questionCount+' 题 · 限时 '+x.timeLimit+' 分钟 · 截止 '+x.dueDate+(x.startedAt?' · 已开始':'')}),
      el('button',{class:'btn primary',text:x.startedAt?'继续作答':'开始（开始后计时）',onclick:function(){exStart(x)}})))});
    if(done.length)root.appendChild(el('div',{class:'card'},el('h3',{text:'已交'}),epTable(['卷子','得分'],done.map(function(x){return [x.title,x.score+' 分']}))));
    if(EXAID){var hit=open.filter(function(x){return x.assignmentId===EXAID})[0];if(hit)exStart(hit)}
  }).catch(function(e){msg(e.message)});
}
function exStart(x){
  api('/student/exam-papers/'+x.assignmentId+'/start',{json:{}}).then(function(s){
    var skew=Date.parse(s.now)-Date.now(),end=Date.parse(s.startedAt)+s.timeLimit*60000;
    return api('/papers/'+x.paperId+'/questions').then(function(qs){exPaper(x,qs,end,skew)});
  }).catch(function(e){msg(e.message)});
}
function exPaper(x,qs,end,skew){
  root.textContent='';var saved=exLoad(x.assignmentId),clock=el('div',{class:'card',role:'timer',style:'position:sticky;top:0;z-index:5;font-weight:700'}),form=el('div'),note=el('div',{role:'status'});
  root.appendChild(clock);root.appendChild(el('div',{class:'card'},el('h2',{text:x.title}),el('p',{class:'muted',text:'共 '+qs.length+' 题。写的答案会自动留在这台设备上，刷新也不会丢。'})));root.appendChild(form);
  function tick(){var left=Math.round((end-(Date.now()+skew))/1000);
    if(left>0){var m=Math.floor(left/60),s=left%60;clock.textContent='剩余 '+m+' 分 '+(s<10?'0':'')+s+' 秒';clock.className='card'}
    else{clock.textContent='时间到了：请尽快写完剩下的题交卷，超出的时间会记录给老师。';clock.className='card warn'}}
  tick();if(EXT)clearInterval(EXT);EXT=setInterval(tick,1000);
  qs.forEach(function(q,i){
    var box=el('div',{class:'card','data-q':String(q.id)},el('p',{text:(i+1)+'. '+q.text}));
    if(q.figure&&q.figure.type==='uploaded_image')box.appendChild(el('img',{src:q.figure.data_url,alt:q.figure.alt||'题目图片',style:'max-width:100%;max-height:260px'}));
    if(cyIsDrawnFigure(q.figure))box.appendChild(cyCubeSvgNode(q.figure));
    if(q.questionType==='single_choice'||q.questionType==='true_false'){
      (q.options||[]).forEach(function(o,k){var r=el('input',{type:'radio',name:'q'+q.id,value:String(k),checked:saved[q.id]===k});
        r.addEventListener('change',function(){saved[q.id]=k;exKeep(x.assignmentId,saved)});
        box.appendChild(el('label',{style:'display:block;margin:6px 0'},r,' '+String.fromCharCode(65+k)+'. '+o))});
    }else{var t=el('input',{'aria-label':'第'+(i+1)+'题答案',value:saved[q.id]!=null?String(saved[q.id]):''});
      t.addEventListener('input',function(){saved[q.id]=t.value;exKeep(x.assignmentId,saved)});box.appendChild(el('label',{},'答案 ',t))}
    form.appendChild(box);
  });
  root.appendChild(el('div',{class:'card'},el('button',{class:'btn primary',text:'交卷',onclick:function(){
    var miss=qs.filter(function(q){var v=saved[q.id];return v==null||String(v).trim()===''}).map(function(q){return qs.indexOf(q)+1});
    if(miss.length){note.textContent='还有第 '+miss.join('、')+' 题没写；每道题都写上答案才能交卷（不会的可以写上你的想法）。';return}
    note.textContent='正在交卷…';
    var answers=qs.map(function(q){return (q.questionType==='single_choice'||q.questionType==='true_false')?{question_id:q.id,selected_index:saved[q.id]}:{question_id:q.id,text_answer:String(saved[q.id])}});
    api('/student/assignments/'+x.assignmentId+'/submit',{json:{answers:answers}}).then(function(){
      if(EXT)clearInterval(EXT);exKeep(x.assignmentId,{});note.textContent='已交卷。';EXAID=0;exList()}).catch(function(e){note.textContent=e.message})}}),note));
}
epBoot('student',exList);
"""

REPORT_JS = COMMON_EXAM_JS + r"""
var CHILD=+(new URLSearchParams(location.search).get('child')||0);
function rpShow(list){
  root.textContent='';
  var items=Array.isArray(list)?list:(list.items||list.children||[]);
  if(CHILD)items=items.filter(function(c){return +(c.id||c.studentID||c.studentId)===CHILD});
  if(!items.length){root.appendChild(el('div',{class:'card'},el('h2',{text:'还没有关联孩子'})));return}
  items.forEach(function(c){
    var id=c.id||c.studentID||c.studentId,box=el('div',{class:'card'},el('h2',{text:(c.name||'孩子')+' 的考试提分报告'}));root.appendChild(box);
    api('/parent/children/'+id+'/exam-reports').then(function(d){
      if(!d.items.length){box.appendChild(el('p',{class:'muted',text:'老师发布后会显示在这里。'}));return}
      d.items.forEach(function(r){var card=el('div',{class:'card'},el('h3',{text:r.title}),el('p',{class:'muted',text:'发布于 '+r.publishedAt}));
        r.lines.forEach(function(l){card.appendChild(el('p',{text:l}))});
        if(r.change&&r.change.length)card.appendChild(el('p',{text:'再测对比：'+r.change.map(function(x){return x.name+' '+x.verdict}).join('；')}));
        card.appendChild(el('p',{text:'接下来（'+r.stage+'阶段）：'+r.advice}));
        if(r.note)card.appendChild(el('p',{text:'老师的话：'+r.note}));
        box.appendChild(card)});
    }).catch(function(e){box.appendChild(el('p',{class:'warn',text:e.message}))});
  });
}
epBoot('parent',function(){api('/parent/children').then(rpShow).catch(function(e){msg(e.message)})});
"""


def exam_prep_page_html() -> str:
    return _page("应试专项", EXAM_PREP_JS, True)


def exam_paper_page_html() -> str:
    return _page("限时模拟卷", CUBES_JS + PAPER_JS, True)


def exam_report_page_html() -> str:
    return _page("考试提分报告", REPORT_JS, True)


__all__ = ["EXAM_PREP_JS", "PAPER_JS", "REPORT_JS", "exam_paper_page_html", "exam_prep_page_html", "exam_report_page_html"]
