"""应试专项教师页 (static HTML, ES5)：建考试目标、发模拟卷、看每个学生的失分点."""

from __future__ import annotations

from changying.web.weekend_pages import _page

EXAM_PREP_JS = r"""
var EPMSG=null,EPBOX=null,EPDATA=null;
function epSay(text,bad){EPMSG.textContent=text||'';EPMSG.className=bad?'card warn':'muted'}
function epTable(head,rows){
  var cell='padding:6px 8px;border-bottom:1px solid #e5e7eb;text-align:left;vertical-align:top',t=el('table',{style:'border-collapse:collapse;width:100%'});
  var hr=el('tr');head.forEach(function(h){hr.appendChild(el('th',{text:h,style:cell}))});t.appendChild(hr);
  rows.forEach(function(r){var tr=el('tr');r.forEach(function(c){tr.appendChild(el('td',{text:c,style:cell}))});t.appendChild(tr)});
  return t;
}
function epDays(n){return n>0?'距考试 '+n+' 天':(n===0?'今天考试':'已考完 '+(-n)+' 天')}
function epNewForm(box){
  box.textContent='';
  if(!EPDATA.maps.length){box.appendChild(el('div',{class:'card'},el('p',{text:'还没有已发布的知识地图。应试专项按知识地图的单元和知识点出题，请先在“知识地图”里创建并发布。'}),el('a',{class:'btn',href:'/v1/knowledge-map',text:'去知识地图'})));return}
  if(!EPDATA.classes.length){box.appendChild(el('div',{class:'card'},el('p',{text:'还没有班级，请先在“我的班级”创建班级并添加学生。'})));return}
  var title=el('input',{value:'期末',maxlength:'60','aria-label':'考试名称'}),date=el('input',{type:'date','aria-label':'考试日期'}),
      cls=el('select',{'aria-label':'班级'}),map=el('select',{'aria-label':'知识地图'}),units=el('div',{class:'row'});
  EPDATA.classes.forEach(function(c){cls.appendChild(el('option',{value:c.id,text:c.name}))});
  EPDATA.maps.forEach(function(m){map.appendChild(el('option',{value:m.id,text:m.title}))});
  function paintUnits(){units.textContent='';var m=EPDATA.maps.filter(function(x){return String(x.id)===map.value})[0];
    m.units.forEach(function(u){units.appendChild(el('label',{},el('input',{type:'checkbox',value:u.key,checked:true}),' '+u.name))})}
  map.addEventListener('change',paintUnits);paintUnits();
  box.appendChild(el('div',{class:'card'},el('h2',{text:'新建考试目标'}),
    el('div',{class:'row'},el('label',{},'考试名称 ',title)),el('div',{class:'row'},el('label',{},'考试日期 ',date)),
    el('div',{class:'row'},el('label',{},'班级 ',cls)),el('div',{class:'row'},el('label',{},'知识地图 ',map)),
    el('p',{class:'muted',text:'考试范围（勾选要考的单元）：'}),units,
    el('div',{class:'row'},el('button',{class:'btn primary',text:'创建',onclick:function(){
      var keys=Array.prototype.filter.call(units.querySelectorAll('input'),function(i){return i.checked}).map(function(i){return i.value});
      if(!date.value){epSay('请选择考试日期',true);return}if(!keys.length){epSay('请至少勾选一个单元',true);return}
      epSay('正在创建…');api('/teacher/exam-goals',{json:{title:title.value,examDate:date.value,classId:+cls.value,mapId:+map.value,unitKeys:keys}})
        .then(function(g){epSay('已创建');epGoal(g.id)}).catch(function(e){epSay(e.message,true)})}}),
      el('button',{class:'btn',text:'取消',onclick:function(){box.textContent=''}}))));
}
function epAnalysis(gid,p,box){
  box.textContent='';box.appendChild(el('p',{class:'muted',text:'正在统计…'}));
  api('/teacher/exam-goals/'+gid+'/papers/'+p.id+'/analysis').then(function(d){
    box.textContent='';
    box.appendChild(el('p',{text:'已交 '+d.handedIn+' / '+d.classSize+' 人。没做或没做对的题都算失分；每个学生只列失分最多的 3 个知识点，先补这几个。'}));
    if(d.points.length){box.appendChild(el('h4',{text:'全班：哪里丢分最多'}));
      box.appendChild(epTable(['知识点','全班失分','失分率'],d.points.map(function(x){return [x.key+' '+x.name,x.lost+' / '+x.asked+' 题次',x.rate+'%']})))}
    box.appendChild(el('h4',{text:'每个学生'}));
    box.appendChild(epTable(['学生','得分','先补这几个知识点'],d.pupils.map(function(x){return [x.name,x.handedIn?x.score+' 分':'未交',
      !x.handedIn?'—':(x.focus.length?x.focus.map(function(f){return f.name+'（错 '+f.lost+'/'+f.asked+'）'}).join('；'):'全对，保持')]})));
  }).catch(function(e){box.textContent='';box.appendChild(el('p',{class:'warn',text:e.message}))});
}
function epGoal(gid){
  api('/teacher/exam-goals/'+gid).then(function(g){
    EPBOX.textContent='';
    EPBOX.appendChild(el('div',{class:'row'},el('button',{class:'btn',text:'‹ 全部考试目标',onclick:epStart})));
    EPBOX.appendChild(el('div',{class:'card'},el('h2',{text:g.title+' · '+g.className}),
      el('p',{text:g.examDate+'　'+epDays(g.daysLeft)}),
      el('p',{class:'muted',text:'范围：'+g.units.map(function(u){return u.name}).join('、')+'（共 '+g.points.length+' 个知识点，来自'+g.mapTitle+'）'})));
    var count=el('input',{type:'number',min:'6',max:'40',value:'20','aria-label':'题数'}),limit=el('input',{type:'number',min:'10',max:'120',value:'60','aria-label':'建议限时（分钟）'}),
        res=el('div',{role:'status'});
    EPBOX.appendChild(el('div',{class:'card'},el('h3',{text:'发一份模拟卷'}),
      el('p',{class:'muted',text:'从范围内每个知识点已分档的题（和题库里同名知识点的题）中，按知识点轮流、难度以中等和基础为主组卷，作为全班作业发出。学生在“作业”里完成，系统自动判分。'}),
      el('div',{class:'row'},el('label',{},'题数 ',count),el('label',{},'建议限时（分钟） ',limit),
        el('button',{class:'btn primary',text:'组卷并发给全班',onclick:function(){res.textContent='正在组卷…';
          api('/teacher/exam-goals/'+gid+'/mock',{json:{count:+count.value,timeLimit:+limit.value}}).then(function(r){
            res.textContent='已发出《'+r.title+'》：'+r.questionCount+' 题，'+r.recipients+' 名学生。'+(r.short?'范围内的题不够，题数比你要的少。':'');epGoal(gid)})
            .catch(function(e){res.textContent=e.message})}})),res));
    var list=el('div',{class:'card'},el('h3',{text:'模拟卷与失分点'}));EPBOX.appendChild(list);
    if(!g.papers.length)list.appendChild(el('p',{class:'muted',text:'还没有发过模拟卷。'}));
    g.papers.forEach(function(p){var box=el('div');
      list.appendChild(el('div',{class:'card'},el('b',{text:p.title}),el('span',{class:'muted',text:'　'+p.questionCount+' 题 · 建议 '+p.timeLimit+' 分钟 · 截止 '+p.dueDate+' · 已交 '+p.handedIn+' 人'}),
        el('div',{class:'row'},el('button',{class:'btn',text:'看失分点',onclick:function(){epAnalysis(gid,p,box)}})),box))});
  }).catch(function(e){epSay(e.message,true)});
}
function epStart(){
  root.textContent='';EPMSG=el('div',{class:'muted',role:'status'});EPBOX=el('div');root.appendChild(EPMSG);root.appendChild(EPBOX);
  api('/teacher/exam-goals').then(function(d){
    EPDATA=d;var form=el('div');
    EPBOX.appendChild(el('div',{class:'card'},el('h2',{text:'应试专项'}),
      el('p',{text:'为一次考试（期中、期末）建一个目标：先发模拟卷摸底，再按每个学生失分最多的知识点补练。只和学生自己比，不排名。'}),
      el('button',{class:'btn primary',text:'新建考试目标',onclick:function(){epNewForm(form)}})));
    EPBOX.appendChild(form);
    if(!d.items.length){EPBOX.appendChild(el('p',{class:'muted',text:'还没有考试目标。'}));return}
    d.items.forEach(function(g){EPBOX.appendChild(el('div',{class:'card'},el('b',{text:g.title+' · '+g.className}),
      el('span',{class:'muted',text:'　'+g.examDate+' · '+epDays(g.daysLeft)+' · 模拟卷 '+g.papers.length+' 份'}),
      el('div',{class:'row'},el('button',{class:'btn',text:'打开',onclick:function(){epGoal(g.id)}}))))});
  }).catch(function(e){epSay(e.message,true)});
}
boot(epStart);
"""


def exam_prep_page_html() -> str:
    return _page("应试专项", EXAM_PREP_JS, True)


__all__ = ["EXAM_PREP_JS", "exam_prep_page_html"]
