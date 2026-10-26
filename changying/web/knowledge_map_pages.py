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


STUDENT_MAP_JS = r"""
var SM=null,SMBOX=null,SMINFO=null,SMDIAG=null,SMMSG=null,SMSEL=null;
var SM_COLORS={weak:'#d92d20',pass:'#2e90fa',fluent:'#12b76a',insufficient:'#98a2b3',locked:'#d0d5dd',display:'#b692f6'};
function svgEl(tag,attrs){var n=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.keys(attrs||{}).forEach(function(k){if(k==='text')n.textContent=attrs[k];else n.setAttribute(k,attrs[k])});return n}
function smState(n){
  if(n.kind==='display')return 'display';
  if(!n.assessed)return 'locked';
  return n.mastery&&n.mastery.level?n.mastery.level:'insufficient';
}
function smStateText(n){
  if(n.kind==='display')return '拓展阅读，不需要做题';
  if(!n.learned)return '这个单元还没学';
  if(!n.assessed)return '选学内容，老师还没有开启';
  var m=n.mastery;
  if(!m.level)return '证据不足：已有 '+m.evidence+' 道题的第一次作答，至少 3 道才判断';
  return SM.masteryLabels[m.level]+'（加权正确率 '+Math.round(m.rate*100)+'%，'+m.evidence+' 道题的第一次作答，'+SM.confidenceLabels[m.confidence]+'）';
}
function smUnitText(n){
  var u=SM.units.filter(function(x){return x.key===n.unit})[0],m=u&&u.mastery;
  if(!m)return null;
  return el('p',{class:'muted',text:m.level?'整个单元：'+SM.masteryLabels[m.level]+'（加权正确率 '+Math.round(m.rate*100)+'%，'+m.evidence+' 道题，'+SM.confidenceLabels[m.confidence]+'）':'整个单元：证据不足（已有 '+m.evidence+' 道题的第一次作答）'});
}
function smShort(text,len){return text.length>len?text.slice(0,len)+'…':text}
function smDraw(){
  var cols=window.innerWidth>=720?3:window.innerWidth>=520?2:1,W=300,GAP=16,ROWH=50,HEAD=44,pos={},regions=[],svg;
  var units=SM.units,y=0,heights=[];
  for(var i=0;i<units.length;i+=cols){
    var h=0;for(var j=i;j<Math.min(i+cols,units.length);j++){var cnt=SM.nodes.filter(function(n){return n.unit===units[j].key}).length;h=Math.max(h,HEAD+Math.max(cnt,1)*ROWH+10)}
    for(j=i;j<Math.min(i+cols,units.length);j++)regions.push({u:units[j],x:(j-i)*(W+GAP),y:y,h:h});
    y+=h+GAP;
  }
  svg=svgEl('svg',{viewBox:'0 0 '+(cols*W+(cols-1)*GAP)+' '+Math.max(y-GAP,10),width:'100%',role:'img','aria-label':'知识地图'});
  var back=svgEl('g',{}),edges=svgEl('g',{}),body=svgEl('g',{});svg.appendChild(back);svg.appendChild(edges);svg.appendChild(body);
  regions.forEach(function(r){
    back.appendChild(svgEl('rect',{x:r.x,y:r.y,width:W,height:r.h,rx:14,fill:r.u.learned?'#f8faff':'#f9fafb',stroke:r.u.learned?'#c7d7fe':'#e4e7ec'}));
    body.appendChild(svgEl('text',{x:r.x+14,y:r.y+28,'font-size':16,'font-weight':700,fill:'#1d2939',text:smShort(r.u.name,10)+(r.u.learned?'':'（未学）')}));
    var um=r.u.mastery;
    if(um&&um.level){body.appendChild(svgEl('rect',{x:r.x+W-92,y:r.y+11,width:80,height:24,rx:12,fill:SM_COLORS[um.level]}));
      body.appendChild(svgEl('text',{x:r.x+W-52,y:r.y+28,'font-size':13,'text-anchor':'middle',fill:'#fff',text:'单元'+SM.masteryLabels[um.level]}))}
    SM.nodes.filter(function(n){return n.unit===r.u.key}).forEach(function(n,k){pos[n.key]={x:r.x+30,y:r.y+HEAD+k*ROWH+22}});
  });
  var unitOf={};SM.nodes.forEach(function(n){unitOf[n.key]=n.unit});
  SM.nodes.forEach(function(n){n.prereqs.forEach(function(p){var a=pos[p],b=pos[n.key];if(!a||!b)return;
    // Links inside a unit always show; links to other units only for the node the pupil picked.
    var hot=SMSEL===n.key||SMSEL===p;if(unitOf[p]!==n.unit&&!hot)return;
    var same=Math.abs(a.x-b.x)<1,d=same?'M'+a.x+' '+a.y+' C'+(a.x-26)+' '+a.y+','+(b.x-26)+' '+b.y+','+b.x+' '+b.y:'M'+a.x+' '+a.y+' C'+(a.x+120)+' '+a.y+','+(b.x-120)+' '+b.y+','+b.x+' '+b.y;
    edges.appendChild(svgEl('path',{d:d,fill:'none',stroke:hot?'#475467':'#98a2b3','stroke-opacity':hot?'.9':'.6','stroke-width':hot?2.5:1.5}))})});
  SM.nodes.forEach(function(n){
    var p=pos[n.key],st=smState(n),g=svgEl('g',{tabindex:'0',role:'button','aria-label':n.key+' '+n.name,'data-node':n.key,style:'cursor:pointer'});
    g.appendChild(svgEl('circle',{cx:p.x,cy:p.y,r:13,fill:st==='insufficient'||st==='locked'?'#fff':SM_COLORS[st],stroke:SM_COLORS[st],'stroke-width':2.5,
      'stroke-dasharray':st==='locked'?'4 3':'none'}));
    if(SMSEL===n.key)g.appendChild(svgEl('circle',{cx:p.x,cy:p.y,r:18,fill:'none',stroke:'#1d2939','stroke-width':1.5}));
    g.appendChild(svgEl('text',{x:p.x+22,y:p.y+5,'font-size':14,fill:st==='locked'?'#98a2b3':'#1d2939',text:n.key+' '+smShort(n.name,13)}));
    var pick=function(){SMSEL=n.key;smInfo(n);smDraw()};
    g.addEventListener('click',pick);g.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();pick()}});
    body.appendChild(g);
  });
  SMBOX.textContent='';SMBOX.appendChild(svg);
}
function smInfo(n){
  var after=SM.nodes.filter(function(x){return x.prereqs.indexOf(n.key)>=0}).map(function(x){return x.key+' '+x.name});
  var before=n.prereqs.map(function(k){var x=SM.nodes.filter(function(y){return y.key===k})[0];return x?k+' '+x.name:k});
  SMINFO.textContent='';
  SMINFO.appendChild(el('div',{class:'card'},el('h3',{text:n.key+'  '+n.name}),n.detail?el('p',{class:'muted',text:n.detail}):null,
    el('p',{text:smStateText(n)}),smUnitText(n),el('p',{class:'muted',text:'先学：'+(before.length?before.join('、'):'无')}),el('p',{class:'muted',text:'接着学：'+(after.length?after.join('、'):'无')})));
}
function smLegend(){
  var row=el('div',{class:'row'});
  [['fluent','熟练'],['pass','达标'],['weak','薄弱'],['insufficient','证据不足'],['locked','未学或未开启']].forEach(function(x){
    row.appendChild(el('span',{class:'tag',style:'border:2px solid '+SM_COLORS[x[0]]+';background:'+(x[0]==='insufficient'||x[0]==='locked'?'#fff':SM_COLORS[x[0]])+';color:'+(x[0]==='insufficient'||x[0]==='locked'?'#344054':'#fff'),text:x[1]}))});
  return row;
}
function smDiagCard(){
  var d=SM.diagnosis;SMDIAG.textContent='';
  if(d.status==='submitted'){SMDIAG.appendChild(el('div',{class:'card'},el('h3',{text:'入门诊断已完成'}),el('p',{text:'答对 '+d.correct+' / '+d.count+' 题。以后做的作业和练习也会继续更新这张地图。'})));return}
  SMDIAG.appendChild(el('div',{class:'card'},el('h3',{text:'入门诊断'}),
    el('p',{text:'做 12 道题，看看已经学过的单元掌握得怎么样。每道题只算第一次作答，认真做就好，不用紧张。'}),
    el('button',{class:'btn primary',text:d.status==='open'?'继续诊断':'开始诊断',onclick:smStartDiag})));
}
function smStartDiag(){
  smSay('正在准备题目…');
  api('/student/knowledge-map/diagnosis',{method:'POST'}).then(function(d){smSay('');smQuiz(d.questions)}).catch(function(e){smSay(e.message,true)});
}
function smQuiz(qs){
  var answers={},form=el('div');
  SMDIAG.textContent='';SMDIAG.appendChild(el('div',{class:'card'},el('h3',{text:'入门诊断（共 '+qs.length+' 题）'}),form));
  qs.forEach(function(q,i){
    var box=el('div',{class:'card','data-q':String(q.id)},el('p',{text:(i+1)+'. '+q.text}));
    if(q.figure&&q.figure.type==='uploaded_image')box.appendChild(el('img',{src:q.figure.data_url,alt:q.figure.alt||'题目图片',style:'max-width:100%;max-height:260px'}));
    if(q.questionType==='single_choice'||q.questionType==='true_false'){
      var opts=el('div',{class:'row'});
      (q.options||[]).forEach(function(o,k){var b=el('button',{class:'btn',type:'button',text:String.fromCharCode(65+k)+'. '+o,onclick:function(){
        answers[q.id]={question_id:q.id,selected_index:k};Array.prototype.forEach.call(opts.children,function(c){c.className='btn'});b.className='btn primary'}});opts.appendChild(b)});
      box.appendChild(opts);
    }else{
      box.appendChild(el('input',{'aria-label':'第'+(i+1)+'题答案',maxlength:'200',oninput:function(e){var v=e.target.value.trim();if(v)answers[q.id]={question_id:q.id,text_answer:v};else delete answers[q.id]}}));
    }
    form.appendChild(box);
  });
  var send=el('button',{class:'btn primary',text:'交卷',onclick:function(){
    var miss=qs.filter(function(q){return !answers[q.id]}).map(function(q){return qs.indexOf(q)+1});
    if(miss.length){smSay('还有第 '+miss.join('、')+' 题没有作答',true);return}
    send.disabled=true;smSay('正在判分…');
    api('/student/knowledge-map/diagnosis/submit',{json:{answers:qs.map(function(q){return answers[q.id]})}}).then(function(r){
      SM=r.map;smSay('');smDraw();smDiagCard();
      var ul=el('ul');r.nodes.forEach(function(x){ul.appendChild(el('li',{text:x.key+' '+x.name+'：答对 '+x.right+' / '+x.total}))});
      SMDIAG.appendChild(el('div',{class:'card'},el('h3',{text:'诊断结果：答对 '+r.correct+' / '+r.total+' 题'}),ul));
    }).catch(function(e){send.disabled=false;smSay(e.message,true)});
  }});
  form.appendChild(send);
}
function smSay(text,bad){SMMSG.textContent=text||'';SMMSG.className=bad?'card warn':'muted'}
function smLoad(){
  root.textContent='';SMMSG=el('div',{class:'muted',role:'status'});SMDIAG=el('div');SMBOX=el('div',{class:'card'});SMINFO=el('div');
  api('/student/knowledge-map').then(function(d){
    SM=d;root.appendChild(el('h2',{text:d.title}));root.appendChild(SMMSG);root.appendChild(SMDIAG);root.appendChild(smLegend());root.appendChild(SMBOX);root.appendChild(SMINFO);
    smDiagCard();smDraw();
    SMINFO.appendChild(el('p',{class:'muted',text:'点一个知识点，看看它的掌握情况和前后关系。'}));
    window.addEventListener('resize',function(){smDraw()});
  }).catch(function(e){msg(e.message)});
}
obtainToken().then(function(t){TOKEN=t;if(!TOKEN){msg('请先登录后再打开');return}
  return api('/session').then(function(s){if(s.role!=='student'){msg('这是学生的知识地图页面');return}smLoad()})}).catch(function(e){msg(e.message||'打不开')});
"""


def student_map_page_html() -> str:
    return _page("我的知识地图", STUDENT_MAP_JS, True)


def knowledge_map_page_html() -> str:
    return _page("知识地图", KNOWLEDGE_MAP_JS, True)


__all__ = ["KNOWLEDGE_MAP_JS", "STUDENT_MAP_JS", "knowledge_map_page_html", "student_map_page_html"]
