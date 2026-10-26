"""知识地图教师页 (static HTML, ES5)：单元、知识点、前置关系与题目分档."""

from __future__ import annotations

from changying.web.weekend_pages import _page

KNOWLEDGE_MAP_JS = r"""
var KM=null,KMBOX=null,KMMSG=null,QPANEL={};
function kmSay(text,bad){KMMSG.textContent=text||'';KMMSG.className=bad?'card warn':'muted'}
function kmKeys(text){return String(text||'').split(/[、,，;；\s]+/).filter(function(x){return x})}
function kmCopy(){return JSON.parse(JSON.stringify(KM.map))}
function kmSave(change,done){
  var m=kmCopy();var err=change(m);if(err){kmSay(err,true);return}
  kmSay('正在保存…');
  api('/teacher/knowledge-maps/'+KM.id,{method:'PUT',json:{map:m,revision:KM.revision}}).then(function(d){KM=d;kmSay('已保存');kmRender();if(done)done()})
    .catch(function(e){kmSay(e.message,true)});
}
function kmNode(m,key){for(var i=0;i<m.nodes.length;i++)if(m.nodes[i].key===key)return m.nodes[i];return null}
function kmTag(text,cls){return el('span',{class:'tag'+(cls?' '+cls:''),text:text})}
function kmCoverage(n){
  if(n.kind==='display')return kmTag('只展示，不出题');
  var c=n.coverage.counts,t=KM.levels;
  return kmTag(t.basic+' '+c.basic+' · '+t.medium+' '+c.medium+' · '+t.hard+' '+c.hard+'（共 '+n.coverage.total+'）',n.coverage.ready?'ok':'warn');
}
function kmEditForm(n,box){
  var name=el('input',{value:n.name,maxlength:'40','aria-label':'知识点名称'}),detail=el('textarea',{class:'s','aria-label':'说明'});detail.value=n.detail||'';
  var kind=el('select',{'aria-label':'类型'});Object.keys(KM.nodeKinds).forEach(function(k){var o=el('option',{value:k,text:KM.nodeKinds[k]});if(k===n.kind)o.selected=true;kind.appendChild(o)});
  var pre=el('input',{value:n.prereqs.join('、'),'aria-label':'前置知识点编号'}),bank=el('input',{value:n.bankKeys.join('；'),'aria-label':'题库知识点名'});
  box.textContent='';
  box.appendChild(el('div',{class:'card'},
    el('label',{},'名称 ',name),el('label',{},'说明 ',detail),el('label',{},'类型 ',kind),
    el('label',{},'前置知识点编号（用顿号分隔，如 2-2、2-3）',pre),
    el('label',{},'题库知识点名（题目的“知识点”字段等于其中之一就会列出，用分号分隔）',bank),
    el('div',{class:'row'},
      el('button',{class:'btn primary',text:'保存这个知识点',onclick:function(){
        kmSave(function(m){var x=kmNode(m,n.key);x.name=name.value;x.detail=detail.value;x.kind=kind.value;x.prereqs=kmKeys(pre.value);
          x.bankKeys=String(bank.value||'').split(/[;；\n]+/).map(function(s){return s.trim()}).filter(function(s){return s})})}}),
      el('button',{class:'btn',text:'取消',onclick:function(){box.textContent=''}}))));
}
function kmQuestions(n,box){
  box.textContent='';box.appendChild(el('p',{class:'muted',text:'正在读取题库…'}));
  api('/teacher/knowledge-maps/'+KM.id+'/nodes/'+encodeURIComponent(n.key)+'/questions').then(function(d){
    box.textContent='';var picks={};
    var head=el('p',{class:'muted',text:'题库中知识点名为“'+d.bankKeys.join('”或“')+'”的题目共 '+d.items.length+' 道。每题选一个难度档；选“不用”表示不进入诊断和掌握度。每个知识点至少 '+KM.minPerNode+' 题，每档至少 '+KM.minPerLevel+' 题。'});
    box.appendChild(head);
    if(!d.items.length){box.appendChild(el('p',{text:'题库里还没有匹配的题目：请先在题库中录入或导入知识点名一致的题目，或在“编辑”里补充题库知识点名。'}));return}
    var list=el('ol');
    d.items.forEach(function(q){
      var sel=el('select',{'aria-label':'难度档'});sel.appendChild(el('option',{value:'',text:'不用'}));
      Object.keys(KM.levels).forEach(function(k){var o=el('option',{value:k,text:KM.levels[k]});if(q.level===k)o.selected=true;sel.appendChild(o)});
      sel.addEventListener('change',function(){picks[q.id]=sel.value||null});
      list.appendChild(el('li',{},el('div',{text:q.text.length>160?q.text.slice(0,160)+'…':q.text}),
        el('div',{class:'row'},kmTag(q.knowledge),q.unit?kmTag(q.unit):null,sel)));
    });
    box.appendChild(list);
    box.appendChild(el('div',{class:'row'},
      el('button',{class:'btn primary',text:'保存分档',onclick:function(){
        if(!Object.keys(picks).length){kmSay('没有改动');return}
        kmSay('正在保存分档…');
        api('/teacher/knowledge-maps/'+KM.id+'/nodes/'+encodeURIComponent(n.key)+'/levels',{method:'PUT',json:{levels:picks,revision:KM.revision}})
          .then(function(r){KM=r;QPANEL={};kmSay('分档已保存');kmRender()}).catch(function(e){kmSay(e.message,true)})}}),
      el('button',{class:'btn',text:'收起',onclick:function(){box.textContent='';delete QPANEL[n.key]}})));
  }).catch(function(e){box.textContent='';box.appendChild(el('p',{class:'warn',text:e.message}))});
}
function kmNodeRow(n,unit){
  var after=KM.dependents[n.key]||[],edit=el('div'),qs=el('div');
  var tags=el('div',{class:'row'},kmTag(KM.nodeKinds[n.kind]),n.assessed?kmTag('参加诊断','ok'):kmTag(unit.learned?'不参加诊断':'未学'),kmCoverage(n),
    n.kind==='display'?null:kmTag('题库匹配 '+n.bankCount+' 题'));
  var actions=el('div',{class:'row'},
    el('button',{class:'btn',text:'编辑',onclick:function(){kmEditForm(n,edit)}}),
    n.kind==='display'?null:el('button',{class:'btn',text:'题目分档',onclick:function(){QPANEL[n.key]=1;kmQuestions(n,qs)}}),
    n.kind==='optional'?el('label',{},el('input',{type:'checkbox',checked:!!n.enabled,onchange:function(e){var on=e.target.checked;
      kmSave(function(m){kmNode(m,n.key).enabled=on})}}),' 开启这个选学内容'):null,
    el('button',{class:'btn',text:'删除',onclick:function(){
      var msgText='删除知识点 '+n.key+' '+n.name+'？'+(after.length?'它是 '+after.join('、')+' 的前置，删除后这些前置关系一并去掉。':'')+'已分档的题目不会从题库删除。';
      if(!confirm(msgText))return;
      kmSave(function(m){m.nodes=m.nodes.filter(function(x){return x.key!==n.key});m.nodes.forEach(function(x){x.prereqs=x.prereqs.filter(function(p){return p!==n.key})})})}}));
  var row=el('div',{class:'card','data-node':n.key},
    el('h4',{text:n.key+'  '+n.name}),n.detail?el('p',{class:'muted',text:n.detail}):null,tags,
    el('p',{text:'前置：'+(n.prereqs.length?n.prereqs.map(kmLabel).join('、'):'无')+'；后续：'+(after.length?after.map(kmLabel).join('、'):'无')}),
    actions,edit,qs);
  if(QPANEL[n.key])kmQuestions(n,qs);
  return row;
}
function kmLabel(key){var n=kmNode(KM.map,key);return n?key+' '+n.name:key}
function kmUnit(u){
  var nodes=KM.map.nodes.filter(function(n){return n.unit===u.key});
  var name=el('input',{value:u.name,maxlength:'40','aria-label':'单元名称'});
  var card=el('section',{class:'card','data-unit':u.key},
    el('div',{class:'row'},el('h3',{text:u.key}),name,kmTag(KM.unitKinds[u.kind]),
      el('label',{},el('input',{type:'checkbox',checked:!!u.learned,onchange:function(e){var on=e.target.checked;kmSave(function(m){m.units.forEach(function(x){if(x.key===u.key)x.learned=on})})}}),' 已学'),
      el('button',{class:'btn',text:'保存名称',onclick:function(){kmSave(function(m){m.units.forEach(function(x){if(x.key===u.key)x.name=name.value})})}}),
      el('button',{class:'btn',text:'添加知识点',onclick:function(){
        var key=prompt('新知识点编号（如 '+u.key.replace('U','')+'-'+(nodes.length+1)+'）');if(!key)return;
        var nm=prompt('知识点名称');if(!nm)return;
        kmSave(function(m){if(kmNode(m,key))return '编号 '+key+' 已存在';m.nodes.push({key:key,unit:u.key,name:nm,detail:'',kind:'core',prereqs:[],bankKeys:[nm],levels:{},enabled:true})})}})));
  nodes.forEach(function(n){card.appendChild(kmNodeRow(n,u))});
  if(!nodes.length)card.appendChild(el('p',{class:'muted',text:'这个单元还没有知识点'}));
  return card;
}
function kmRender(){
  var s=KM.summary,p=KM.published;KMBOX.textContent='';
  KMBOX.appendChild(el('div',{class:'card'},
    el('h2',{text:KM.title}),
    el('p',{text:'共 '+s.units+' 个部分、'+s.nodes+' 个知识点；已学 '+s.learnedUnits+' 个部分。现在参加诊断的知识点 '+s.assessed+' 个，其中题目已备齐 '+s.assessedReady+' 个（每个至少 '+KM.minPerNode+' 题，基础、中等、提高每档至少 '+KM.minPerLevel+' 题）。'}),
    el('p',{},p?(p.upToDate?kmTag('已发布，与草稿一致','ok'):kmTag('已发布，草稿有未发布的修改','warn')):kmTag('未发布','warn'),
      ' 学生和诊断只使用发布后的版本。'),
    el('button',{class:'btn primary',text:p&&p.upToDate?'已是最新发布':'发布知识地图',disabled:!!(p&&p.upToDate),onclick:function(){
      if(!confirm('发布后，学生端和诊断将使用这份知识地图。确定发布？'))return;
      api('/teacher/knowledge-maps/'+KM.id+'/publish',{json:{revision:KM.revision}}).then(function(d){KM=d;kmSay('已发布');kmRender()}).catch(function(e){kmSay(e.message,true)})}})));
  KM.map.units.forEach(function(u){KMBOX.appendChild(kmUnit(u))});
}
function kmOpen(id){api('/teacher/knowledge-maps/'+id).then(function(d){KM=d;QPANEL={};kmRender()}).catch(function(e){kmSay(e.message,true)})}
function kmStart(){
  root.textContent='';KMMSG=el('div',{class:'muted',role:'status'});KMBOX=el('div');root.appendChild(KMMSG);root.appendChild(KMBOX);
  api('/teacher/knowledge-maps').then(function(d){
    if(d.items.length){kmOpen(d.items[0].id);return}
    KMBOX.appendChild(el('div',{class:'card'},el('h2',{text:'还没有知识地图'}),el('p',{text:'选择教材模板创建，创建后可以逐项修改、标记已学单元，再给每个知识点的题目分档。'})));
    d.templates.forEach(function(tp){KMBOX.appendChild(el('button',{class:'btn primary',text:'用“'+tp.label+'”创建',onclick:function(){
      kmSay('正在创建…');api('/teacher/knowledge-maps',{json:{template:tp.key}}).then(function(r){KM=r;kmSay('已创建');kmRender()}).catch(function(e){kmSay(e.message,true)})}}))});
  }).catch(function(e){kmSay(e.message,true)});
}
boot(kmStart);
"""


def knowledge_map_page_html() -> str:
    return _page("知识地图", KNOWLEDGE_MAP_JS, True)


__all__ = ["KNOWLEDGE_MAP_JS", "knowledge_map_page_html"]
