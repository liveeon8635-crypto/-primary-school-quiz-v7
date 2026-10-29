"""知识地图教师页 (static HTML, ES5)：单元、知识点、前置关系与题目分档."""

from __future__ import annotations

from changying.web.cube_figures_js import CUBES_JS
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
    if(KM.visualNodes&&KM.visualNodes[n.key]){var vis=el('div');box.appendChild(vis);kmVisual(n,vis)}
    var gen=el('div');box.appendChild(gen);kmAIGen(n,gen);
    var pick=el('div');box.appendChild(pick);kmBankPick(n,pick);
    if(!d.items.length){box.appendChild(el('p',{text:'这个知识点还没有题目：可以用上面的“从题库挑题”按单元挑选已导入的题，或用“AI 出题”。'}));return}
    box.appendChild(el('h4',{text:'已归到这个知识点的题'}));
    var list=el('ol');
    d.items.forEach(function(q){
      var sel=el('select',{'aria-label':'难度档'});sel.appendChild(el('option',{value:'',text:'不用'}));
      Object.keys(KM.levels).forEach(function(k){var o=el('option',{value:k,text:KM.levels[k]});if(q.level===k)o.selected=true;sel.appendChild(o)});
      sel.addEventListener('change',function(){picks[q.id]=sel.value||null});
      list.appendChild(el('li',{},el('div',{text:q.text.length>160?q.text.slice(0,160)+'…':q.text}),
        el('div',{class:'row'},kmTag(q.knowledge),q.unit?kmTag(q.unit):null,q.note?kmTag(q.note,'warn'):null,sel)));
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
// 图形题：系统按数据画出小正方体组合体、算出视图和答案；老师只改题干和解析，图、选项、答案不可改。
function kmVisual(n,holder){
  var level=el('select',{'aria-label':'难度档'}),count=el('select',{'aria-label':'题数'}),out=el('div'),note=el('p',{class:'muted'});
  Object.keys(KM.levels).forEach(function(k){level.appendChild(el('option',{value:k,text:KM.levels[k]}))});
  [2,4,6].forEach(function(c){var o=el('option',{value:String(c),text:c+' 题'});if(c===4)o.selected=true;count.appendChild(o)});
  var make=function(){
    note.textContent='正在画图出题…';out.textContent='';
    api('/teacher/knowledge-maps/'+KM.id+'/nodes/'+encodeURIComponent(n.key)+'/visual',{json:{level:level.value,count:+count.value}})
      .then(function(d){note.textContent='题型：'+d.kind+'。图和答案由系统计算，保证一致；题干和解析可以改。';kmVisualDrafts(n,d,out)})
      .catch(function(e){note.textContent=e.message});
  };
  holder.appendChild(el('div',{class:'card'},el('h4',{text:'图形题（系统画图，答案由系统计算）'}),
    el('div',{class:'row'},el('label',{},'难度 ',level),el('label',{},'数量 ',count),el('button',{class:'btn',text:'生成图形题',onclick:make})),note,out));
}
function kmVisualDrafts(n,d,out){
  out.textContent='';var rows=[];
  d.items.forEach(function(q,i){
    var keep=el('input',{type:'checkbox',checked:true}),text=el('textarea',{class:'s','aria-label':'题干'}),exp=el('textarea',{class:'s','aria-label':'解析'});
    text.value=q.text;exp.value=q.explanation||'';
    out.appendChild(el('div',{class:'card','data-visual':String(i)},el('label',{},keep,' 保留这道题'),el('label',{},'题干 ',text),cyCubeSvgNode(q.figure),
      el('p',{text:q.question_type==='fill_blank'?'填空题，答案：'+q.answer:'选项：'+q.options.join('　')+'　　正确答案：'+q.options[q.correct_index]}),el('label',{},'解析 ',exp)));
    rows.push(function(){return keep.checked?{text:text.value.trim(),question_type:q.question_type,options:q.options,correct_index:q.correct_index,answer:q.answer||'',explanation:exp.value,figure:q.figure}:null});
  });
  var msgBox=el('p',{class:'muted'});
  out.appendChild(el('div',{class:'row'},
    el('button',{class:'btn primary',text:'存入题库并分为“'+KM.levels[d.level]+'”',onclick:function(e){
      var qs=rows.map(function(f){return f()}).filter(function(x){return x});
      if(!qs.length){msgBox.textContent='没有勾选要保留的题';return}
      e.target.disabled=true;msgBox.textContent='正在保存…';
      api('/teacher/knowledge-maps/'+KM.id+'/nodes/'+encodeURIComponent(n.key)+'/visual/save',{json:{level:d.level,revision:KM.revision,questions:qs}})
        .then(function(r){KM=r;QPANEL[n.key]=1;kmSay('已存入 '+r.saved.length+' 道图形题并分档');kmRender()})
        .catch(function(err){e.target.disabled=false;msgBox.textContent=err.message});
    }})),msgBox);
}
// 从题库挑题：按单元或关键词搜索本校题库，不要求题目的知识点名与地图一致；分档按题目编号保存。
function kmBankPick(n,holder){
  var unit=el('select',{'aria-label':'单元'}),kw=el('input',{placeholder:'关键词（题干或知识点）','aria-label':'关键词',maxlength:'60'}),out=el('div');
  unit.appendChild(el('option',{value:'',text:'全部单元'}));
  var run=function(){
    if(!unit.value&&!kw.value.trim()){out.textContent='请先选单元或输入关键词';return}
    out.textContent='正在搜索…';
    api('/teacher/knowledge-maps/'+KM.id+'/bank?unit='+encodeURIComponent(unit.value)+'&q='+encodeURIComponent(kw.value.trim())).then(function(d){kmBankList(n,d,out)})
      .catch(function(e){out.textContent=e.message});
  };
  holder.appendChild(el('div',{class:'card'},el('h4',{text:'从题库挑题（按单元或关键词，不要求知识点名一致）'}),
    el('div',{class:'row'},unit,kw,el('button',{class:'btn',text:'搜索',onclick:run})),out));
  api('/teacher/knowledge-maps/'+KM.id+'/bank').then(function(d){d.units.forEach(function(x){unit.appendChild(el('option',{value:x,text:x}))})}).catch(function(){});
}
function kmBankList(n,d,out){
  out.textContent='';var picks={};
  out.appendChild(el('p',{class:'muted',text:'找到 '+d.total+' 道'+(d.total>d.items.length?'，先显示前 '+d.items.length+' 道，可加关键词缩小范围':'')+'。给要放进“'+n.name+'”的题选难度档，再点“把选中的题归到这个知识点”。'}));
  if(!d.items.length)return;
  var list=el('ol');
  d.items.forEach(function(q){
    var sel=el('select',{'aria-label':'难度档'});sel.appendChild(el('option',{value:'',text:'不选'}));
    Object.keys(KM.levels).forEach(function(k){sel.appendChild(el('option',{value:k,text:KM.levels[k]}))});
    sel.addEventListener('change',function(){if(sel.value)picks[q.id]=sel.value;else delete picks[q.id]});
    var where=q.placed?(q.placed[0]===n.key?'已在本知识点（'+KM.levels[q.placed[1]]+'）':'已归到 '+q.placed[0]+'（'+KM.levels[q.placed[1]]+'）'):null;
    list.appendChild(el('li',{'data-bank':String(q.id)},el('div',{text:q.text.length>160?q.text.slice(0,160)+'…':q.text}),
      el('div',{class:'row'},kmTag(q.knowledge),q.unit?kmTag(q.unit):null,q.note?kmTag(q.note,'warn'):null,where?kmTag(where):null,sel)));
  });
  out.appendChild(list);
  out.appendChild(el('button',{class:'btn primary',text:'把选中的题归到这个知识点',onclick:function(e){
    if(!Object.keys(picks).length){kmSay('还没有给题目选难度档');return}
    e.target.disabled=true;
    api('/teacher/knowledge-maps/'+KM.id+'/nodes/'+encodeURIComponent(n.key)+'/levels',{method:'PUT',json:{levels:picks,revision:KM.revision}})
      .then(function(r){KM=r;QPANEL[n.key]=1;kmSay('已把 '+Object.keys(picks).length+' 道题归到 '+n.key+' 并分档');kmRender()})
      .catch(function(err){e.target.disabled=false;kmSay(err.message,true)});
  }}));
}
// AI 出题：复用现有的 /ai/questions/generate 和 /ai/questions/save（教师审核后才入库），保存后按所选难度档分档。
// 教材名沿用题库核定的“人教版”（出题接口只接受核定教材）。
function kmAIGen(n,holder){
  var level=el('select',{'aria-label':'难度档'}),count=el('select',{'aria-label':'题数'});
  Object.keys(KM.levels).forEach(function(k){level.appendChild(el('option',{value:k,text:KM.levels[k]}))});
  [4,6,8,10].forEach(function(c){var o=el('option',{value:String(c),text:c+' 题'});if(c===6)o.selected=true;count.appendChild(o)});
  var drafts=el('div'),note=el('p',{class:'muted'});
  var refIds=[],refBox=el('div',{class:'muted',text:'正在读取本校教学资源…'});
  // 参考资料是可选项：读不到资源也不影响出题。
  api('/teaching/resources?grade='+encodeURIComponent(KM.grade)+'&subject='+encodeURIComponent(KM.subject))
    .then(function(d){
      refBox.textContent='';
      var list=(d.items||[]).slice(0,40);
      if(!list.length){refBox.textContent='本校还没有教学资源。可先在“教学资源”里上传课件、教案或真题，出题时会作为参考。';return}
      list.forEach(function(r){
        var cb=el('input',{type:'checkbox','aria-label':'参考资料'});
        cb.onchange=function(){
          var i=refIds.indexOf(r.id);
          if(cb.checked&&i<0)refIds.push(r.id);
          if(!cb.checked&&i>=0)refIds.splice(i,1);
        };
        refBox.appendChild(el('label',{},cb,' '+(r.title||r.fileName||r.file_name||('资料 '+r.id))));
      });
    })
    .catch(function(){refBox.textContent='参考资料读取失败，不影响出题。'});
  var qtype=el('select',{'aria-label':'题型'});
  [['mixed','混合题型（推荐）'],['single_choice','选择'],['true_false','判断'],['fill_blank','填空']].concat(KM.subject==='数学'?[['calculation','计算'],['short_answer','解决问题']]:[])
    .forEach(function(t){qtype.appendChild(el('option',{value:t[0],text:t[1]}))});
  holder.appendChild(el('div',{class:'card'},el('h4',{text:'AI 出题（多题型，需老师审核）'}),
    el('p',{class:'muted',text:'系统会检查：中等至少 2 步、提高至少 3 步；数学答案按 AI 给的算式重新计算，算错的题直接丢掉。'}),
    el('div',{class:'row'},el('label',{},'难度 ',level),el('label',{},'题型 ',qtype),el('label',{},'数量 ',count),
      el('button',{class:'btn',text:'生成草稿',onclick:function(e){
        var btn=e.target;
        btn.disabled=true;note.textContent='AI 正在出题并逐题检查，大约需要一分钟…';drafts.textContent='';
        api('/teacher/knowledge-maps/'+KM.id+'/nodes/'+encodeURIComponent(n.key)+'/ai',{json:{level:level.value,count:+count.value,questionType:qtype.value,resourceIds:refIds}})
          .then(function(r){btn.disabled=false;
            var drop=Object.keys(r.dropped||{}).map(function(k){return k+' '+r.dropped[k]+' 道'});
            note.textContent='出了 '+r.items.length+' 道'+(r.verified?'，其中 '+r.verified+' 道数学答案已由系统验算':'')+'。'+(r.short?'还差 '+r.short+' 道，可以再点一次。':'')+(drop.length?'没通过检查已丢弃：'+drop.join('、')+'。':'');
            kmDrafts(n,level.value,r.items||[],drafts)})
          .catch(function(err){btn.disabled=false;note.textContent=err.message})}})),
    el('details',{},el('summary',{text:'参考资料（可选）'}),refBox),note,drafts));
}
var KM_TYPE_NAMES={single_choice:'选择',true_false:'判断',fill_blank:'填空',calculation:'计算',short_answer:'解决问题'};
function kmDrafts(n,lv,items,box){
  box.textContent='';var rows=[];
  items.forEach(function(q,i){
    var text=el('textarea',{class:'s','aria-label':'题干'});text.value=q.text;
    var choice=q.question_type==='single_choice'||q.question_type==='true_false';
    var opts=choice?(q.options||[]).map(function(o,k){return el('input',{value:o,'aria-label':'选项 '+String.fromCharCode(65+k),readonly:q.question_type==='true_false'})}):[];
    var right=el('select',{'aria-label':'正确答案'});opts.forEach(function(_,k){var o=el('option',{value:String(k),text:String.fromCharCode(65+k)});if(k===q.correct_index)o.selected=true;right.appendChild(o)});
    var answer=el('input',{value:q.answer||'','aria-label':'答案'});
    var exp=el('textarea',{class:'s','aria-label':'解析'});
    exp.value=(q.verified&&q.expression?'列式：'+q.expression+'（系统已验算）\n':'')+(q.explanation||(q.steps||[]).map(function(t){return String(t).replace(/[。；;，,\s]+$/,'')}).join('；'));
    var keep=el('input',{type:'checkbox',checked:true});
    var tags=el('div',{class:'row'},kmTag(KM_TYPE_NAMES[q.question_type]||q.question_type),q.angle?kmTag('考法：'+q.angle):null,
      q.verified?kmTag('已验算','ok'):(KM.subject==='数学'&&q.question_type!=='true_false'?kmTag('答案待核对','warn'):null));
    var card=el('div',{class:'card km-draft','data-draft':String(i)},tags,el('label',{},keep,' 保留这道题'),el('label',{},'题干 ',text));
    if(choice){opts.forEach(function(o,k){card.appendChild(el('label',{},String.fromCharCode(65+k)+' ',o))});card.appendChild(el('label',{},'正确答案 ',right))}
    else card.appendChild(el('label',{},'答案 ',answer));
    card.appendChild(el('label',{},'解析 ',exp));
    box.appendChild(card);
    rows.push(function(){if(!keep.checked)return null;var unit=KM.map.units.filter(function(u){return u.key===n.unit})[0];
      var base={grade:KM.grade,subject:KM.subject,textbook:'人教版',semester:KM.term,unit:unit?unit.name:'',knowledge:n.bankKeys[0]||n.name,
        text:text.value.trim(),explanation:exp.value,question_type:q.question_type};
      if(choice){base.options=opts.map(function(o){return o.value.trim()});base.correct_index=+right.value}
      else{base.options=[];base.correct_index=-1;base.answer=answer.value.trim();base.accepted_answers=q.accepted_answers||[]}
      return base});
  });
  if(!items.length)return;
  var msgBox=el('p',{class:'muted'});
  box.appendChild(el('button',{class:'btn primary',text:'审核无误，存入题库并分为“'+KM.levels[lv]+'”',onclick:function(e){
    var qs=rows.map(function(f){return f()}).filter(function(x){return x});
    if(!qs.length){msgBox.textContent='没有勾选要保留的题';return}
    if(qs.some(function(x){return !x.options.length&&!x.answer})){msgBox.textContent='有题没填答案';return}
    e.target.disabled=true;msgBox.textContent='正在保存…';
    api('/ai/questions/save',{json:{questions:qs}}).then(function(r){
      var levels={};r.items.forEach(function(q){levels[q.id]=lv});
      return api('/teacher/knowledge-maps/'+KM.id+'/nodes/'+encodeURIComponent(n.key)+'/levels',{method:'PUT',json:{levels:levels,revision:KM.revision}})
        .then(function(d){KM=d;QPANEL[n.key]=1;kmSay('已存入 '+r.items.length+' 道题并分档');kmRender()});
    }).catch(function(err){e.target.disabled=false;msgBox.textContent=err.message});
  }}));
  box.appendChild(msgBox);
}
function kmNodeRow(n,unit){
  var after=KM.dependents[n.key]||[],edit=el('div'),qs=el('div');
  var tags=el('div',{class:'row'},kmTag(KM.nodeKinds[n.kind]),n.assessed?kmTag('参加诊断','ok'):kmTag(unit.learned?'不参加诊断':'未学'),
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
  // 默认只占一行：编号 + 名称 + 题目覆盖；点开才看说明、前后置和操作按钮。
  var caret=el('span',{class:'km-caret',text:'▸'});
  var body=el('div',{class:'km-node-b'},n.detail?el('p',{class:'muted',text:n.detail}):null,tags,
    el('p',{class:'muted',text:'前置：'+(n.prereqs.length?n.prereqs.map(kmLabel).join('、'):'无')+'；后续：'+(after.length?after.map(kmLabel).join('、'):'无')}),
    actions,edit,qs);
  body.hidden=true;
  var head=el('button',{class:'km-node-h',type:'button','aria-expanded':'false',
    onclick:function(){
      var open=body.hidden;body.hidden=!open;caret.textContent=open?'▾':'▸';
      head.setAttribute('aria-expanded',open?'true':'false');
    }},
    el('span',{class:'km-node-t',text:n.key+'  '+n.name}),kmCoverage(n),caret);
  var row=el('div',{class:'card km-node','data-node':n.key},head,body);
  if(QPANEL[n.key]){body.hidden=false;caret.textContent='▾';head.setAttribute('aria-expanded','true');kmQuestions(n,qs)}
  return row;
}
function kmLabel(key){var n=kmNode(KM.map,key);return n?key+' '+n.name:key}
function kmUnit(u){
  var nodes=KM.map.nodes.filter(function(n){return n.unit===u.key});
  var name=el('input',{value:u.name,maxlength:'40','aria-label':'单元名称'});
  var card=el('section',{class:'card','data-unit':u.key,id:'unit-'+u.key},
    el('div',{class:'row'},el('h3',{text:u.key}),name,kmTag(KM.unitKinds[u.kind]),
      el('label',{},el('input',{type:'checkbox',checked:!!u.learned,onchange:function(e){var on=e.target.checked;kmSave(function(m){m.units.forEach(function(x){if(x.key===u.key)x.learned=on})})}}),' 已学'),
      el('button',{class:'btn',text:'保存名称',onclick:function(){kmSave(function(m){m.units.forEach(function(x){if(x.key===u.key)x.name=name.value})})}}),
      el('button',{class:'btn',text:'添加知识点',onclick:function(){kmAddForm(u,nodes,add)}}),
      el('button',{class:'btn',text:'按模板恢复本单元知识点',onclick:function(){
        if(!confirm('把模板里这个单元缺少的知识点补回来（连同前置关系）。已有的知识点、修改和分档都不会动。继续？'))return;
        api('/teacher/knowledge-maps/'+KM.id+'/units/'+encodeURIComponent(u.key)+'/restore',{json:{revision:KM.revision}})
          .then(function(d){KM=d;kmSay('已恢复：'+d.restored.join('、'));kmRender()}).catch(function(e){kmSay(e.message,true)})}})));
  var add=el('div');card.appendChild(add);
  nodes.forEach(function(n){card.appendChild(kmNodeRow(n,u))});
  if(!nodes.length)card.appendChild(el('p',{class:'muted',text:'这个单元还没有知识点：可以点“按模板恢复本单元知识点”，或“添加知识点”。'}));
  return card;
}
// 页面内的添加表单：编号和名称分开填，当场检查格式和重复。
function kmAddForm(u,nodes,box){
  var prefix=u.key.replace(/^U/,''),key=el('input',{value:prefix+'-'+(nodes.length+1),maxlength:'12','aria-label':'新知识点编号'}),
      name=el('input',{maxlength:'40','aria-label':'新知识点名称',placeholder:'例如：从不同位置观察同一组合体'}),err=el('p',{class:'warn'});
  var go=function(){
    var k=key.value.trim(),nm=name.value.trim();err.textContent='';
    if(!/^[0-9A-Za-z\u4e00-\u9fff-]{1,12}$/.test(k)){err.textContent='编号只能用 1—12 个字母、数字、汉字或短横线，例如 '+prefix+'-1';return}
    if(kmNode(KM.map,k)){err.textContent='编号 '+k+' 已经有了（'+kmNode(KM.map,k).name+'），请换一个';return}
    if(!nm){err.textContent='请填写知识点名称';return}
    kmSave(function(m){m.nodes.push({key:k,unit:u.key,name:nm,detail:'',kind:'core',prereqs:[],bankKeys:[nm],levels:{},enabled:true})});
  };
  box.textContent='';
  box.appendChild(el('div',{class:'card'},el('h4',{text:'在“'+u.name+'”里添加知识点'}),
    el('label',{},'编号 ',key),el('label',{},'名称 ',name),err,
    el('div',{class:'row'},el('button',{class:'btn primary',text:'添加',onclick:go}),el('button',{class:'btn',text:'取消',onclick:function(){box.textContent=''}}))));
  name.focus();
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
  var cv=el('div');
  KMBOX.appendChild(el('div',{class:'card'},el('h3',{text:'全班掌握情况'}),
    p?el('button',{class:'btn',text:'查看全班掌握情况',onclick:function(){kmClassView(cv)}}):el('p',{class:'muted',text:'发布知识地图后可以查看。'}),cv));
  var grid=el('div',{class:'km-grid'});
  KM.map.units.forEach(function(u){grid.appendChild(kmUnit(u))});
  // 左侧单元导航：点击跳到该单元（原生锚点，不依赖 JS 滚动）。
  var nav=el('nav',{class:'km-nav','aria-label':'单元导航'},el('div',{class:'km-nav-t',text:'单元'}));
  KM.map.units.forEach(function(u){
    var count=KM.map.nodes.filter(function(n){return n.unit===u.key}).length;
    nav.appendChild(el('a',{href:'#unit-'+u.key,title:u.name,text:u.key+' · '+u.name+'（'+count+'）'}));
  });
  KMBOX.appendChild(el('div',{class:'km-layout'},nav,grid));
}
var KM_LEVEL_TAG={weak:'warn',pass:'',fluent:'ok'};
function kmMasteryTag(x,labels){
  if(!x)return kmTag('—');
  if(!x.level)return kmTag('证据不足（'+x.evidence+' 题）');
  return kmTag(labels[x.level]+' '+Math.round(x.rate*100)+'%'+(x.confidence==='preliminary'?'（初步）':''),KM_LEVEL_TAG[x.level]);
}
function kmClassView(box){
  box.textContent='';box.appendChild(el('p',{class:'muted',text:'正在读取班级…'}));
  api('/teacher/knowledge-maps/'+KM.id+'/classes').then(function(d){
    box.textContent='';
    if(!d.items.length){box.appendChild(el('p',{text:'你还没有自己任教的班级。'}));return}
    var out=el('div'),sel=el('select',{'aria-label':'选择班级'});sel.appendChild(el('option',{value:'',text:'选择班级'}));
    d.items.forEach(function(c){sel.appendChild(el('option',{value:String(c.id),text:c.name+'（'+c.studentCount+' 人'+(c.sameGrade?'':'，年级与地图不同')+'）'}))});
    sel.addEventListener('change',function(){if(sel.value)kmClassLoad(+sel.value,out)});
    box.appendChild(el('div',{class:'row'},el('label',{},'班级 ',sel)));box.appendChild(out);
    if(d.items.length===1){sel.value=String(d.items[0].id);kmClassLoad(d.items[0].id,out)}
  }).catch(function(e){box.textContent='';box.appendChild(el('p',{class:'warn',text:e.message}))});
}
function kmClassLoad(cid,out){
  out.textContent='';out.appendChild(el('p',{class:'muted',text:'正在计算…'}));
  api('/teacher/knowledge-maps/'+KM.id+'/classes/'+cid).then(function(d){
    out.textContent='';var L=d.masteryLabels;
    out.appendChild(el('p',{class:'muted',text:'按已发布的知识地图计算：只看每道已分档题目的第一次作答，基础 1、中等 1.5、提高 2 加权；不足 3 题为证据不足，3—4 题为初步，5 题及以上可信。单元一栏把该单元所有题目合并计算。'}));
    if(!d.students.length){out.appendChild(el('p',{text:'这个班还没有学生。'}));return}
    var head=el('tr',{},el('th',{text:'学生'}),el('th',{text:'入门诊断'}));
    d.units.forEach(function(u){head.appendChild(el('th',{text:u.name}))});
    var tb=el('tbody'),changes={};
    d.students.forEach(function(st){
      var g=st.diagnosis,tr=el('tr',{},el('td',{text:st.name}),
        el('td',{text:g.status==='submitted'?'已完成 '+g.correct+'/'+g.count:g.status==='open'?'做了一半':'未开始'}));
      d.units.forEach(function(u){
        // 老师自己的判断：与系统判断对照，算一致率（验收用）。
        var pick=el('select',{'aria-label':st.name+' '+u.name+' 老师判断','data-rate':st.id+':'+u.key});
        [['','我的判断'],['weak',L.weak],['pass',L.pass],['fluent',L.fluent]].forEach(function(x){var o=el('option',{value:x[0],text:x[1]});if((st.ratings||{})[u.key]===x[0])o.selected=true;pick.appendChild(o)});
        pick.addEventListener('change',function(){changes[st.id+':'+u.key]={studentId:st.id,unitKey:u.key,level:pick.value||null}});
        tr.appendChild(el('td',{},kmMasteryTag(st.units[u.key],L),el('div',{},pick)));
      });
      tb.appendChild(tr);
    });
    var ag=d.agreement,agText=ag.compared?'老师判断与系统判断一致 '+ag.agreed+' / '+ag.compared+' 项，一致率 '+Math.round(ag.rate*100)+'%（验收要求不低于 '+Math.round(ag.threshold*100)+'%）'+(ag.passed?'，已达到':'，未达到'):
      '还没有可比对的判断：在下表每格选“我的判断”后保存。系统为“证据不足”的格不计入一致率。';
    var save=el('button',{class:'btn',text:'保存我的判断',onclick:function(){
      var list=Object.keys(changes).map(function(k){return changes[k]});if(!list.length){kmSay('没有改动');return}
      save.disabled=true;
      api('/teacher/knowledge-maps/'+KM.id+'/classes/'+d.classId+'/ratings',{method:'PUT',json:{ratings:list}}).then(function(){kmSay('判断已保存');kmClassLoad(d.classId,out)})
        .catch(function(e){save.disabled=false;kmSay(e.message,true)});
    }});
    out.appendChild(el('h3',{text:d.className+' · 各单元'}));
    out.appendChild(el('p',{},ag.compared?kmTag(agText,ag.passed?'ok':'warn'):el('span',{class:'muted',text:agText}),
      ag.rated>ag.compared?el('span',{class:'muted',text:'（另有 '+(ag.rated-ag.compared)+' 项系统证据不足，未计入）'}):null));
    out.appendChild(el('div',{style:'overflow-x:auto'},el('table',{},el('thead',{},head),tb)));
    out.appendChild(save);
    var detail=el('div'),nb=el('tbody');
    d.nodes.forEach(function(n){
      var c=d.tally[n.key],tr=el('tr',{style:'cursor:pointer',tabindex:'0','data-tally':n.key},el('td',{text:n.key+' '+n.name}),
        el('td',{text:String(c.weak)}),el('td',{text:String(c.pass)}),el('td',{text:String(c.fluent)}),el('td',{text:String(c.insufficient)}));
      var show=function(){kmNodeStudents(d,n,detail)};
      tr.addEventListener('click',show);tr.addEventListener('keydown',function(e){if(e.key==='Enter')show()});
      nb.appendChild(tr);
    });
    out.appendChild(el('h3',{text:'各知识点（点一行看学生名单）'}));
    out.appendChild(el('div',{style:'overflow-x:auto'},el('table',{},el('thead',{},el('tr',{},el('th',{text:'知识点'}),el('th',{text:L.weak}),el('th',{text:L.pass}),el('th',{text:L.fluent}),el('th',{text:'证据不足'}))),nb)));
    out.appendChild(detail);
  }).catch(function(e){out.textContent='';out.appendChild(el('p',{class:'warn',text:e.message}))});
}
function kmNodeStudents(d,n,box){
  var order={weak:0,pass:1,fluent:2},rows=d.students.map(function(st){return {id:st.id,name:st.name,m:st.nodes[n.key]}});
  rows.sort(function(a,b){var x=a.m.level?order[a.m.level]:3,y=b.m.level?order[b.m.level]:3;return x-y||b.m.evidence-a.m.evidence});
  var ul=el('ul'),picked={};
  rows.forEach(function(r){var on=r.m.level==='weak';if(on)picked[r.id]=1;
    var cb=el('input',{type:'checkbox',checked:on,'aria-label':'选择 '+r.name,onchange:function(e){if(e.target.checked)picked[r.id]=1;else delete picked[r.id]}});
    ul.appendChild(el('li',{},cb,' '+r.name+'：',kmMasteryTag(r.m,d.masteryLabels),' 第一次作答 '+r.m.evidence+' 题'))});
  var count=el('select',{'aria-label':'每人题数'});[3,4,5,6].forEach(function(c){var o=el('option',{value:String(c),text:'每人 '+c+' 题'});if(c===4)o.selected=true;count.appendChild(o)});
  var res=el('div');
  var go=el('button',{class:'btn primary',text:'给勾选的学生布置巩固练习',onclick:function(){
    var ids=Object.keys(picked).map(Number);if(!ids.length){res.textContent='请先勾选学生';return}
    go.disabled=true;res.textContent='正在布置…';
    api('/teacher/knowledge-maps/'+KM.id+'/classes/'+d.classId+'/reinforce',{json:{nodeKey:n.key,studentIds:ids,count:+count.value}}).then(function(r){
      go.disabled=false;res.textContent='';var out=el('ul');
      r.results.forEach(function(x){out.appendChild(el('li',{text:x.name+'：'+(x.ok?'已布置 '+x.questionCount+' 题':x.reason)}))});
      res.appendChild(out);
    }).catch(function(e){go.disabled=false;res.textContent=e.message});
  }});
  box.textContent='';box.appendChild(el('div',{class:'card'},el('h4',{text:n.key+' '+n.name}),
    el('p',{class:'muted',text:'薄弱的学生已默认勾选。巩固题从这个知识点已分档的题里选学生没做过的，先基础后中等；学生按普通作业完成，做完后掌握情况自动更新。'}),
    ul,el('div',{class:'row'},count,go),res));
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
    if(cyIsDrawnFigure(q.figure))box.appendChild(cyCubeSvgNode(q.figure));
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
    return _page("我的知识地图", CUBES_JS + STUDENT_MAP_JS, True).replace("</head>", KM_WIDE_CSS + "</head>", 1)


# 知识地图页在宽屏上放宽容器：共用样式是 980px，在 1440/1920 的桌面上会挤成一条窄栏。
# 这里只注入 <style>，不改内联 JS，所以 Safari 12 清单无需重建。
KM_WIDE_CSS = """<style>
@media (min-width:1100px){main{max-width:1440px;padding:20px 28px}}
@media (min-width:1600px){main{max-width:1600px;padding:22px 32px}}
.km-grid{display:block}
/* 知识点：去掉「卡片套卡片」，改成单元内的一条条分隔行，页面立刻轻一半。 */
section.card[data-unit] .card{border:0;border-top:1px solid #e3e8f2;border-radius:0;box-shadow:none;margin:0;padding:14px 0 12px}
section.card[data-unit] .card:first-of-type{border-top:0;padding-top:6px}
section.card[data-unit] .card h4{margin:0 0 4px;font-size:16px}
/* 知识点默认只占一行，点开才展开详情与操作。 */
section.card[data-unit] .km-node{padding:0}
.km-node-h{display:flex;align-items:center;gap:10px;width:100%;background:none;border:0;padding:12px 2px;font:inherit;text-align:left;cursor:pointer}
.km-node-h:hover .km-node-t{color:#1f6feb}
.km-node-t{flex:1 1 auto;min-width:0;font-weight:700;font-size:16px;color:#1c2333;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.km-caret{color:#667085;font-size:13px;width:1em;text-align:center;flex:0 0 auto}
.km-node-b{padding:0 2px 14px}
.km-node-b[hidden]{display:none}
/* AI 草稿卡片：每个选项、答案、解析各占一行，不和下一个选项字母挤在一起。 */
.km-draft>label{display:block;margin:8px 0}.km-draft>label>input:not([type=checkbox]){width:calc(100% - 2.5em);max-width:420px}
/* 平板横屏（≥900）起两列，同行等高；不做三列——出题面板带图形，三列会被压到 ~250px。 */
@media (min-width:900px){.km-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.km-grid>.card{margin-bottom:0}}
/* 栅格子项默认 min-width:auto，长题干或图片会把整页撑出横向滚动条。 */
.km-grid>.card{min-width:0}
.km-grid img{max-width:100%;height:auto}
.km-grid>.card{scroll-margin-top:84px}
/* 宽屏：左侧单元导航 + 右侧内容。 */
.km-nav{display:none}
@media (min-width:1100px){
  .km-layout{display:grid;grid-template-columns:220px minmax(0,1fr);gap:18px;align-items:start}
  .km-nav{display:block;position:sticky;top:76px;max-height:calc(100vh - 100px);overflow:auto;background:#fff;border:1px solid #d9deea;border-radius:14px;padding:8px}
  .km-nav-t{font-size:12.5px;font-weight:700;color:#667085;letter-spacing:.08em;padding:6px 10px}
  .km-nav a{display:block;padding:7px 10px;border-radius:8px;color:#1c2333;text-decoration:none;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .km-nav a:hover{background:#eef2fa}
}
</style>"""


def knowledge_map_page_html() -> str:
    return _page("知识地图", CUBES_JS + KNOWLEDGE_MAP_JS, True).replace("</head>", KM_WIDE_CSS + "</head>", 1)


__all__ = ["KNOWLEDGE_MAP_JS", "STUDENT_MAP_JS", "knowledge_map_page_html", "student_map_page_html"]
