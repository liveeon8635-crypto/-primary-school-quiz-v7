"""周末课 课后总结与家长反馈 pages (ES5, served through weekend_pages._page)."""

# One rendering of a report for the teacher preview and the parent page, so both show the same thing.
REPORT_VIEW_JS = r"""
var REPORT_KEYS=['content','completion','mastery','issues','consolidation','observation','homework','followup'];
function factsLine(f){var c=f.counts;return '应做 '+c.total+' 题 · 已提交 '+c.submitted+' · 未提交 '+c.unsubmitted+' · 正确 '+c.correct+' · 部分正确 '+c.partial+' · 需订正 '+c.revise+' · 待批 '+c.pending+(c.later?' · 课后题未交 '+c.later:'')}
// 一眼看懂：放在每节课最上面，家长不用读完全文也知道重点。只用已确认的考点和老师写好的课后任务。
function chipRow(label,list,color){
  var row=el('div',{class:'row'},el('b',{text:label}));
  list.forEach(function(t){row.appendChild(el('span',{class:'tag',style:'background:'+color.bg+';color:'+color.fg,text:t}))});
  return row;
}
function glanceBox(g,s){
  var box=el('div',{style:'border:2px solid #c7d7fe;border-radius:12px;padding:10px 14px;margin:10px 0;background:#f8faff'},el('b',{text:'一眼看懂'}));
  if(g.good&&g.good.length)box.appendChild(chipRow('掌握得好：',g.good,{bg:'#e7f6ec',fg:'#067647'}));
  if(g.weak&&g.weak.length)box.appendChild(chipRow('需要加强：',g.weak,{bg:'#fff4e5',fg:'#b54708'}));
  var todo=String(s.homework||'').split('\n').filter(function(x){return x.trim()})[0];
  if(todo)box.appendChild(el('div',{},el('b',{text:'回家做一件事：'}),todo));
  if(g.compare)box.appendChild(el('div',{class:'muted',text:g.compare}));
  return box;
}
function reportView(r){
  var box=el('div');
  (r.facts||[]).forEach(function(f,i){
    var s=(r.sections||[])[i]||{},card=el('div',{class:'card'});
    card.appendChild(el('h2',{text:f.subject+' · 《'+f.lessonTitle+'》'}));
    card.appendChild(el('div',{class:'muted',text:f.date+(f.unit?' · '+f.unit:'')}));
    card.appendChild(el('div',{class:'notice',text:factsLine(f)+(f.points!=null?' · 课堂积分 '+f.points+' 分（积分不是学业成绩）':'')}));
    var g=(r.glance||[])[i];if(g)card.appendChild(glanceBox(g,s));
    REPORT_KEYS.forEach(function(k){if(!s[k])return;card.appendChild(el('b',{text:r.titles[k]}));card.appendChild(el('p',{style:'white-space:pre-wrap;overflow-wrap:anywhere;margin:4px 0 10px',text:s[k]}))});
    box.appendChild(card);
  });
  if(r.comment)box.appendChild(el('div',{class:'card'},el('b',{text:'老师的话'}),el('p',{style:'white-space:pre-wrap',text:r.comment})));
  var p=r.practice;
  if(p&&p.state&&p.state!=='none'){
    var pc=el('div',{class:'card'},el('h2',{text:'针对性练习 · '+(p.label||'')}));
    if(!p.groups)pc.appendChild(el('div',{class:'muted',text:'老师正在审核根据错题出的新题，审核后会布置到孩子的“作业”里。'}));
    (p.assignments||[]).forEach(function(a){pc.appendChild(el('div',{class:'notice',text:a.subject+'：'+a.title+(a.state==='graded'?' · 已提交并批改，做对 '+a.correct+'/'+a.total+'（'+a.submittedAt+'）':' · 已布置，孩子在“作业”中完成'+(a.dueDate?'，截止 '+a.dueDate:''))}))});
    (p.groups||[]).forEach(function(g){
      pc.appendChild(el('b',{text:g.subject+' · '+g.topic}));
      g.questions.forEach(function(q,i){pc.appendChild(el('p',{style:'white-space:pre-wrap;overflow-wrap:anywhere;margin:4px 0',text:(i+1)+'. '+q.text+(q.options.length?'\n'+q.options.map(function(o,j){return String.fromCharCode(65+j)+'. '+o}).join('　'):'')}))});
    });
    box.appendChild(pc);
  }
  return box;
}
function saveDocx(path,name,status){
  status.textContent='正在生成 Word…';
  return fetch(path,{headers:{Authorization:'Bearer '+TOKEN},cache:'no-store'}).then(function(r){
    if(!r.ok)return r.json().catch(function(){return {}}).then(function(x){throw Error(x.detail||'生成失败')});return r.blob();
  }).then(function(blob){
    var url=URL.createObjectURL(blob),a=el('a',{href:url,download:name});document.body.appendChild(a);a.click();a.remove();
    setTimeout(function(){URL.revokeObjectURL(url)},1000);status.textContent='已下载：'+name;
  }).catch(function(e){status.textContent=e.message});
}
"""

MARK_JS = r"""
// 考点 / 课后题 of one written question: stored once on the lesson's template, used by every class of the lesson.
function markBox(lid,m,goals,done){
  var box=el('div',{class:'row'}),inp=el('input',{maxlength:40,placeholder:'考点，如：省略乘号','aria-label':'考点'});
  inp.value=m.knowledge||m.suggestedKnowledge||'';
  var pick=null;
  if(goals&&goals.length){pick=el('select',{'aria-label':'从训练目标选考点'});pick.appendChild(el('option',{value:'',text:'从训练目标选'}));
    goals.forEach(function(g){pick.appendChild(el('option',{value:g,text:g}))});pick.onchange=function(){if(pick.value)inp.value=pick.value}}
  var after=el('input',{type:'checkbox'});after.checked=!!m.afterClass;
  var note=el('span',{class:'muted',text:m.knowledge?'已标注':(m.suggestedKnowledge?'系统按题目小标题建议，保存后生效':'未标注')});
  var save=el('button',{text:'保存考点',onclick:function(){
    save.disabled=true;
    api('/teacher/weekend/lessons/'+lid+'/written/questions/'+m.templateId+'/marks',{method:'PUT',json:{knowledge:inp.value.trim(),afterClass:after.checked}})
      .then(function(r){m.knowledge=r.knowledge;m.afterClass=r.afterClass;note.textContent=r.knowledge?'已标注（所有班级通用）':'未标注';if(done)done(r)})
      .catch(function(e){note.textContent=e.message}).then(function(){save.disabled=false});
  }});
  box.appendChild(el('b',{text:'考点'}));box.appendChild(inp);if(pick)box.appendChild(pick);
  box.appendChild(el('label',{},after,' 课后题（没交不算课堂未提交）'));box.appendChild(save);box.appendChild(note);
  return box;
}
"""

REPORT_JS = REPORT_VIEW_JS + MARK_JS + r"""
var SID=+(new URLSearchParams(location.search).get('s')||0),FILTER='all',SUMMARY=null,EDITOR=null;
var STATE_CLASS={none:'',draft:'warn',published:'ok',stale:'warn'};
function reportPage(){
  root.textContent='';
  if(!SID){msg('请从周末课课堂页打开课后总结');return}
  var back=document.querySelector('header a');if(back){back.href='/v1/weekend?s='+SID;back.textContent='返回课堂'}
  var head=el('div',{class:'card'}),editorBox=el('div'),classBox=el('div',{class:'card'}),listBox=el('div',{class:'card'}),note=el('div');
  root.appendChild(head);root.appendChild(note);root.appendChild(editorBox);root.appendChild(classBox);root.appendChild(listBox);
  window.addEventListener('beforeunload',function(e){if(EDITOR&&EDITOR.dirty){e.preventDefault();e.returnValue=''}});
  function load(){
    note.textContent='';
    return api('/teacher/weekend/sessions/'+SID+'/summary').then(function(d){SUMMARY=d;paintHead(d);paintClass(d);paintList(d)})
      .catch(function(e){note.appendChild(el('div',{class:'notice error',text:e.message}))});
  }
  function paintHead(d){
    head.textContent='';
    head.appendChild(el('h2',{text:'课后总结与家长反馈 · '+d.title}));
    head.appendChild(el('div',{class:'muted',text:[d.subject,'《'+d.lessonTitle+'》',d.unit,d.className?'班级：'+d.className:'未绑定班级（按老师名下班级）','上课日期 '+(d.date||'未开课'),d.status==='finished'?'已结束':d.status==='running'?'进行中':'未开始'].filter(Boolean).join(' · ')}));
    if(d.coreTarget)head.appendChild(el('div',{class:'muted',text:'训练目标：'+d.coreTarget}));
    head.appendChild(el('div',{class:'muted',text:'数据截止 '+d.cutoff+'。查看、生成和保存不会结算积分、公布答案或发给家长。'}));
    if(d.summary.pendingReview)head.appendChild(el('div',{class:'notice warn',text:'还有 '+d.summary.pendingReview+' 道文字／照片答案待批改，待批不计为错误。可回到课堂“学生作答与批改”补批，再点“刷新数据”。'}));
    head.appendChild(el('div',{class:'notice '+(d.settled?'ok':'warn'),text:d.settled?'本节积分已结算（积分不是学业成绩）。':'本节积分未结算；本页不会结算积分。'}));
    head.appendChild(el('div',{class:'row'},el('button',{text:'刷新数据',onclick:function(){load()}}),el('a',{class:'btn',href:'/v1/weekend?s='+SID,text:'回到课堂批改'})));
  }
  function tags(c){
    return [el('span',{class:'tag',text:'已提交 '+c.submitted+'/应做 '+c.total}),el('span',{class:'tag ok',text:'正确 '+c.correct}),el('span',{class:'tag',text:'部分正确 '+c.partial}),
      el('span',{class:'tag '+(c.revise?'warn':''),text:'需订正 '+c.revise}),el('span',{class:'tag '+(c.pending?'warn':''),text:'待批 '+c.pending}),el('span',{class:'tag',text:'未提交 '+c.unsubmitted}),c.later?el('span',{class:'tag',text:'课后题未交 '+c.later}):null].filter(Boolean);
  }
  function paintClass(d){
    var s=d.summary,c=s.counts;classBox.textContent='';
    classBox.appendChild(el('h2',{text:'全班汇总（'+s.participated+' / '+s.pupils+' 人有作答记录）'}));
    var row=el('div',{class:'row'});tags(c).forEach(function(t){row.appendChild(t)});classBox.appendChild(row);
    classBox.appendChild(el('div',{class:'muted',text:'分母：本节 '+d.summary.questions.length+' 题 × 名单 '+s.pupils+' 人'+(c.later?'，减去课后题未交 '+c.later+' 题次':'')+' = '+c.total+' 题次；完成与正确分开统计，部分正确不折算分数；同一题多次提交只算一题。'}));
    classBox.appendChild(el('div',{class:'muted',text:'提示使用 '+s.hintUses+' 题次 · 学生讲解 '+s.explained+' 次 · 巩固题 已完成 '+s.followups.done+'（做对 '+s.followups.correct+'），未完成 '+s.followups.open}));
    var kd=el('details',{},el('summary',{text:'考点表现与对应题目'}));
    s.knowledge.forEach(function(k){kd.appendChild(el('div',{class:'row'},el('b',{text:k.knowledge}),el('span',{class:'muted',text:'第'+k.questions.join('、')+'题 · 正确 '+k.correct+' · 部分正确 '+k.partial+' · 需订正 '+k.revise+' · 待批 '+k.pending+' · 未提交 '+k.unsubmitted})))});
    classBox.appendChild(kd);
    var qd=el('details',{},el('summary',{text:'逐题统计（文字题可在这里标考点）'})),marks={},unmarked=0;
    (d.marks||[]).forEach(function(m){marks[m.no]=m;if(!m.knowledge)unmarked++});
    if(unmarked)classBox.appendChild(el('div',{class:'notice warn',text:'有 '+unmarked+' 道文字题还没标考点。展开“逐题统计”，确认系统建议或从训练目标里选，标一次所有班级通用；标完点“刷新数据”。'}));
    s.questions.forEach(function(q){qd.appendChild(el('div',{class:'row'},el('b',{text:'第'+q.no+'题（'+(q.kind==='choice'?'选择':'文字／照片')+'）'}),el('span',{text:q.stem}),el('span',{class:'muted',text:q.knowledge+' · 正确 '+q.correct+' · 部分正确 '+q.partial+' · 需订正 '+q.revise+' · 待批 '+q.pending+' · 未提交 '+q.unsubmitted+(q.later?' · 课后题未交 '+q.later:'')})));
      if(marks[q.no])qd.appendChild(markBox(d.lessonId,marks[q.no],d.goals));});
    if(unmarked)qd.open=true;
    classBox.appendChild(qd);
  }
  function paintList(d){
    listBox.textContent='';listBox.appendChild(el('h2',{text:'每位学生'}));
    var filters=el('div',{class:'tabs'});
    [['all','全部'],['pending','有待批'],['unsubmitted','有未提交'],['revise','需订正']].forEach(function(f){filters.appendChild(el('button',{class:FILTER===f[0]?'on':'',text:f[1],onclick:function(){FILTER=f[0];paintList(d)}}))});
    listBox.appendChild(filters);
    listBox.appendChild(classActions(d));
    var shown=d.students.filter(function(p){return FILTER==='all'||p.counts[FILTER]>0});
    if(!shown.length)listBox.appendChild(el('div',{class:'muted',text:'没有符合条件的学生。'}));
    shown.forEach(function(p){listBox.appendChild(studentCard(d,p))});
  }
  // 全班：一次为还没有反馈的学生生成草稿（只用事实模板，不发布）；草稿逐个检查后，可一次发布全部草稿。
  function classActions(d){
    var box=el('div',{class:'card'}),msg=el('div',{class:'muted',role:'status'});
    var fresh=d.students.filter(function(p){return p.participated&&p.report.state==='none'});
    var drafts=d.students.filter(function(p){return p.participated&&p.report.state==='draft'});
    var done=d.students.filter(function(p){return p.report.state==='published'}).length;
    box.appendChild(el('b',{text:'全班反馈进度：已发布 '+done+' · 草稿 '+drafts.length+' · 未生成 '+fresh.length}));
    function run(list,step,label){
      var chain=Promise.resolve(),n=0;
      list.forEach(function(p){chain=chain.then(function(){msg.textContent=label+'（'+(++n)+'/'+list.length+'）'+p.name+'…';return step(p)})});
      return chain.then(function(){msg.textContent=label+'完成 '+list.length+' 份。';load()}).catch(function(e){msg.textContent=e.message;load()});
    }
    if(fresh.length)box.appendChild(el('button',{class:'primary',text:'为全班生成草稿（'+fresh.length+' 人，不会发布）',onclick:function(e){
      e.target.disabled=true;
      run(fresh,function(p){return api('/teacher/weekend/reports',{json:{studentId:p.studentId,sessionIds:[SID],useAi:false}})},'正在生成草稿');
    }}));
    if(drafts.length)box.appendChild(el('button',{text:'发布全部草稿（'+drafts.length+' 人）',onclick:function(e){
      if(!confirm('以下 '+drafts.length+' 位学生的草稿会发给家长：'+drafts.map(function(p){return p.name}).join('、')+'。\n请确认每份都已检查过。'))return;
      e.target.disabled=true;
      run(drafts,function(p){return api('/teacher/weekend/reports/'+p.report.reportId).then(function(r){
        return api('/teacher/weekend/reports/'+r.id+'/publish',{json:{revision:r.draft.revision}})})},'正在发布');
    }}));
    box.appendChild(msg);
    return box;
  }
  function studentCard(d,p){
    var card=el('div',{class:'card'}),row=el('div',{class:'row'},el('b',{text:p.name}));
    if(!p.participated){card.appendChild(row);card.appendChild(el('div',{class:'muted',text:'本节没有作答记录（'+p.counts.total+' 题均未提交）。系统无法区分缺课或到课未提交，不生成本节反馈。'}));return card}
    tags(p.counts).forEach(function(t){row.appendChild(t)});
    row.appendChild(el('span',{class:'tag '+STATE_CLASS[p.report.state],text:'学情反馈：'+p.report.stateLabel}));
    card.appendChild(row);
    var extra=[];if(p.explained.length)extra.push('讲解第'+p.explained.join('、')+'题');p.followups.forEach(function(f){extra.push('第'+f.no+'题巩固题'+(f.correct?'做对':f.correct===false?'未做对':'未完成'))});
    if(p.points.settled)extra.push('已结算积分 '+p.points.total+' 分');
    if(extra.length)card.appendChild(el('div',{class:'muted',text:extra.join(' · ')}));
    var detail=el('details',{},el('summary',{text:'逐题答案、照片与批改'}));
    detail.addEventListener('toggle',function(){if(!detail.open||detail.filled)return;detail.filled=true;p.items.forEach(function(i){detail.appendChild(itemView(i))})});
    card.appendChild(detail);
    var gen=el('div'),actions=el('div',{class:'row'});
    if(p.report.reportId)actions.appendChild(el('button',{class:'primary',text:'打开学情报告',onclick:function(){openReport(p.report.reportId)}}));
    else actions.appendChild(el('button',{class:'primary',text:'生成学情草稿',onclick:function(){chooseLessons(d,p,gen)}}));
    card.appendChild(actions);card.appendChild(gen);
    return card;
  }
  function itemView(i){
    var box=el('div',{class:'item'}),t=el('span',{class:'t'});
    t.appendChild(el('b',{text:'第'+i.no+'题（'+(i.kind==='choice'?'选择':'文字／照片')+'）'+i.stem}));
    t.appendChild(el('div',{class:'muted',text:[(i.knowledge||'未标注考点'),i.statusLabel,i.attempts?'提交 '+i.attempts+' 次（只保留最后一次答案）':'',i.hint?'用过 '+i.hint+' 级提示':'',i.submittedAt?'最后提交 '+i.submittedAt:''].filter(Boolean).join(' · ')}));
    if(i.answer)t.appendChild(el('div',{style:'white-space:pre-wrap;overflow-wrap:anywhere',text:'学生答案：'+i.answer}));
    if(i.reference)t.appendChild(el('div',{class:'muted',text:'参考答案（仅老师可见）：'+i.reference}));
    if(i.comment)t.appendChild(el('div',{class:'muted',text:'批改评语：'+i.comment}));
    if(i.hasPhoto)writtenPhoto(t,{id:i.submissionId,hasPhoto:true});
    box.appendChild(t);return box;
  }
  function chooseLessons(d,p,box){
    box.textContent='';box.appendChild(el('div',{class:'muted',text:'正在查找同一天的课堂…'}));
    api('/teacher/weekend/report-sessions?date='+encodeURIComponent(d.date)).then(function(day){
      box.textContent='';box.appendChild(el('b',{text:'选择本报告包含的课（同一天，每科一节；只列出 '+p.name+' 有作答记录的课）'}));
      var picks=[];
      day.items.filter(function(s){return s.participants.some(function(x){return x.studentId===p.studentId})}).forEach(function(s){
        var cb=el('input',{type:'checkbox',checked:s.sessionId===SID,disabled:s.sessionId===SID});cb.value=s.sessionId;picks.push(cb);
        box.appendChild(el('label',{class:'row'},cb,el('span',{text:s.subject+' · '+s.title+(s.className?' · '+s.className:'')})));
      });
      var ai=el('input',{type:'checkbox'}),status=el('div',{role:'status'});
      box.appendChild(el('label',{class:'row'},ai,el('span',{text:'用 AI 整理文字（只改写掌握点、问题、课后任务和跟进计划；不计算成绩，失败时使用事实模板）'})));
      var go=el('button',{class:'primary',text:'生成草稿（不会发布）',onclick:function(){
        go.disabled=true;status.textContent='正在生成…';
        var ids=picks.filter(function(c){return c.checked}).map(function(c){return +c.value});
        api('/teacher/weekend/reports',{json:{studentId:p.studentId,sessionIds:ids,useAi:ai.checked}}).then(function(r){
          box.textContent='';showReport(r.report,{ai:r.source,existing:r.source==='existing'});load();
        }).catch(function(e){status.textContent=e.message;go.disabled=false});
      }});
      box.appendChild(go);box.appendChild(status);
    }).catch(function(e){box.textContent=e.message});
  }
  function openReport(rid){
    if(EDITOR&&EDITOR.dirty&&!confirm('当前报告有未保存的修改，切换后会丢失。确定吗？'))return;
    api('/teacher/weekend/reports/'+rid).then(function(r){showReport(r,{})}).catch(function(e){note.textContent='';note.appendChild(el('div',{class:'notice error',text:e.message}))});
  }
  var AI_NOTE={ai:'已用 AI 整理文字，请逐句核对。',ai_failed:'AI 暂时不可用，已使用事实模板。',ai_not_allowed:'学校未开启或未允许发送学生学习数据给 AI，已使用事实模板。',existing:'这份报告已有草稿，已打开保存的内容，没有覆盖你的修改。'};
  function showReport(r,info){
    var ed={report:r,dirty:false,fields:[],comment:null};EDITOR=ed;
    editorBox.textContent='';
    var card=el('div',{class:'card'}),status=el('div',{role:'status','aria-live':'polite'});editorBox.appendChild(card);
    card.appendChild(el('h2',{text:r.studentName+' · '+r.date+' 学情反馈'}));
    card.appendChild(el('div',{class:'row'},el('span',{class:'tag '+STATE_CLASS[r.state],text:r.stateLabel}),el('span',{class:'muted',text:'草稿保存于 '+r.draft.savedAt+(r.published?' · 已发布第 '+r.published.version+' 版（'+r.published.at+'）':' · 家长尚未看到')})));
    var why=info.ai||(info.existing?'existing':'');if(AI_NOTE[why])card.appendChild(el('div',{class:'notice',text:AI_NOTE[why]}));
    if(r.state==='stale')card.appendChild(el('div',{class:'notice warn',text:'发布后有新的提交、批改或积分记录；家长仍看到第 '+r.published.version+' 版。请核对后重新发布。'}));
    if(r.draft.factsChanged)card.appendChild(el('div',{class:'notice warn',text:'草稿生成后数据有变化（下方统计已是最新）。可手动修改，或点“按最新数据重新生成”（保留教师观察和老师的话）。'}));
    if(r.published&&r.draft.unpublishedEdits)card.appendChild(el('div',{class:'notice warn',text:'草稿有尚未发布的修改。'}));
    r.facts.forEach(function(f,i){
      var s=r.draft.sections[i]||{},sec=el('div',{class:'card'});
      sec.appendChild(el('h2',{text:f.subject+' · 《'+f.lessonTitle+'》'}));
      sec.appendChild(el('div',{class:'notice',text:factsLine(f)+(f.points.settled?' · 已结算积分 '+f.points.total+' 分':' · 积分未结算')}));
      var fields={};
      r.sectionKeys.forEach(function(k){
        var t=el('textarea',{maxlength:1500,placeholder:k==='observation'?'填写有依据的课堂观察（可留空；没有观察就不写行为评价）':k==='consolidation'?'没有订正或巩固记录时留空':''});
        t.value=s[k]||'';t.addEventListener('input',function(){ed.dirty=true;status.textContent='有未保存的修改'});
        fields[k]=t;sec.appendChild(el('label',{class:'field'},el('span',{text:r.titles[k]}),t));
      });
      ed.fields.push(fields);card.appendChild(sec);
    });
    ed.comment=el('textarea',{maxlength:1500,placeholder:'老师的话（可留空）'});ed.comment.value=r.draft.comment||'';ed.comment.addEventListener('input',function(){ed.dirty=true;status.textContent='有未保存的修改'});
    card.appendChild(el('label',{class:'field'},el('span',{text:'老师的话'}),ed.comment));
    ed.evidence=evidencePanel(card,r,function(){ed.dirty=true;status.textContent='有未保存的修改'});
    function values(){return {sections:ed.fields.map(function(f,i){var o={sessionId:r.facts[i].sessionId};Object.keys(f).forEach(function(k){o[k]=f[k].value});return o}),comment:ed.comment.value}}
    function save(){var v=values();return api('/teacher/weekend/reports/'+r.id,{method:'PUT',json:{revision:r.draft.revision,sections:v.sections,comment:v.comment,evidence:ed.evidence()}}).then(function(n){ed.dirty=false;return n})}
    practicePanel(card,r,ed,function(n){showReport(n,{});load()});
    var preview=el('div');
    var buttons=el('div',{class:'row'});
    buttons.appendChild(el('button',{class:'primary',text:'保存草稿',onclick:function(){status.textContent='正在保存…';save().then(function(n){showReport(n,{});load()}).catch(function(e){status.textContent=e.message})}}));
    buttons.appendChild(el('button',{text:'预览家长看到的内容',onclick:function(){var v=values();preview.textContent='';preview.appendChild(el('div',{class:'notice',text:'预览（与家长页面相同的排版；不含答案、参考答案、照片和其他学生信息）'}));preview.appendChild(reportView({facts:r.parentFacts,sections:v.sections,comment:v.comment,titles:r.titles,practice:r.parentPractice,glance:r.glance}))}}));
    buttons.appendChild(el('button',{text:r.published?'发布更新给家长':'发布给家长',onclick:function(){
      if(!confirm('发布后，'+r.studentName+' 已关联的家长可以看到这份反馈'+(r.published?'（替换第 '+r.published.version+' 版）':'')+'。确定发布吗？'))return;
      status.textContent='正在发布…';
      (ed.dirty?save():Promise.resolve(r)).then(function(n){return api('/teacher/weekend/reports/'+r.id+'/publish',{json:{revision:n.draft.revision}})}).then(function(n){showReport(n,{});load();status.textContent='已发布'}).catch(function(e){status.textContent=e.message});
    }}));
    var fname=r.studentName+'-'+r.date+'-周末课学情反馈';
    buttons.appendChild(el('button',{text:'下载 Word（草稿）',onclick:function(){if(ed.dirty){status.textContent='请先保存草稿，再下载 Word';return}saveDocx('/teacher/weekend/reports/'+r.id+'/report.docx?version=draft',fname+'-草稿.docx',status)}}));
    if(r.published)buttons.appendChild(el('button',{text:'下载 Word（已发布版）',onclick:function(){saveDocx('/teacher/weekend/reports/'+r.id+'/report.docx?version=published',fname+'-第'+r.published.version+'版.docx',status)}}));
    buttons.appendChild(el('button',{text:'按最新数据重新生成',onclick:function(){
      if(!confirm('将用最新数据重写系统生成的部分（学习内容、完成情况、掌握点、问题、巩固、课后任务、跟进计划）；保留“教师课堂观察”和“老师的话”。已发布版本不受影响。'+(ed.dirty?'\n当前未保存的修改会丢失。':'')+'\n确定吗？'))return;
      api('/teacher/weekend/reports',{json:{studentId:r.studentId,sessionIds:r.sessionIds,replace:true,revision:r.draft.revision}}).then(function(n){showReport(n.report,{ai:n.source==='template'?'':n.source});load()}).catch(function(e){status.textContent=e.message});
    }}));
    buttons.appendChild(el('button',{text:'关闭',onclick:function(){if(ed.dirty&&!confirm('有未保存的修改，确定关闭吗？'))return;EDITOR=null;editorBox.textContent=''}}));
    card.appendChild(buttons);card.appendChild(status);card.appendChild(preview);
    card.scrollIntoView&&card.scrollIntoView();
  }
  var EV_STATUS={correct:'正确',partial:'部分正确',revise:'需订正'};
  function evidencePanel(card,r,changed){
    var box=el('details',{class:'card'},el('summary',{text:'考点与表现依据（家长报告里的“已掌握”“需要改进”由此生成）'})),rows=[];
    box.appendChild(el('div',{class:'muted',text:'没有标注考点的题，可填写具体考点（如“旋转后对应点的位置判断”）；错因只在有依据时填写。勾选“已核实”后才会写进家长报告，再点“按最新数据重新生成”更新文字。AI 建议需核实后使用。'}));
    var pending=0;
    (r.draft.evidence||[]).forEach(function(e){
      var k=el('input',{type:'text',maxlength:80,placeholder:'具体考点（需教师补充）',disabled:e.knowledgeSource==='question'}),c=el('input',{type:'text',maxlength:200,placeholder:'错因（有依据再填）',hidden:e.status==='correct'}),ok=el('input',{type:'checkbox'});
      k.value=e.knowledge||'';c.value=e.cause||'';ok.checked=e.knowledgeSource==='teacher'||e.causeSource==='teacher';
      if(e.knowledgeSource==='ai'||e.causeSource==='ai')pending++;
      [k,c,ok].forEach(function(n){n.addEventListener('input',changed);n.addEventListener('change',changed)});
      var tag=e.knowledgeSource==='question'?'题目考点':e.knowledgeSource==='teacher'?'教师已核实':e.knowledgeSource==='ai'?'AI 建议，待核实':'考点待补充';
      box.appendChild(el('div',{class:'item'},el('span',{class:'t'},
        el('b',{text:e.subject+' 第'+e.no+'题 · '+EV_STATUS[e.status]+' · '+tag}),
        el('div',{class:'muted',text:'题目任务：'+e.task+(e.material?' · 材料《'+e.material+'》':'')+(e.answer?' · 学生答案：'+e.answer:'')+(e.comment?' · 批注：'+e.comment:'')}),
        el('div',{class:'row'},k,c,el('label',{class:'row'},ok,el('span',{text:'已核实'}))))));
      rows.push({key:e.key,k:k,c:c,ok:ok});
    });
    if(pending)box.insertBefore(el('div',{class:'notice warn',text:'有 '+pending+' 条 AI 建议待核实，未核实前不会出现在家长报告中。'}),box.children[2]||null);
    if(!rows.length)box.appendChild(el('div',{class:'muted',text:'暂无已批改的题目。'}));
    card.appendChild(box);
    return function(){return rows.map(function(x){return {key:x.key,knowledge:x.k.value,cause:x.c.value,confirmed:x.ok.checked}})};
  }
  var QT={single_choice:'单选',true_false:'判断',fill_blank:'填空',calculation:'计算',short_answer:'简答'};
  function questionEditor(q,onchange){
    var box=el('div',{class:'item'}),t=el('span',{class:'t'}),text=el('textarea',{maxlength:4000}),answer=el('input',{type:'text',maxlength:300,placeholder:'标准答案'}),exp=el('textarea',{maxlength:1000,placeholder:'解析（仅老师可见）'}),know=el('input',{type:'text',maxlength:120,placeholder:'考点'});
    text.value=q.text;answer.value=q.answer||'';exp.value=q.explanation||'';know.value=q.knowledge||'';
    var opts=(q.options||[]).map(function(o){var n=el('input',{type:'text',value:o});return n}),ci=el('select');
    opts.forEach(function(_,i){ci.appendChild(el('option',{value:i,text:'正确答案：'+String.fromCharCode(65+i)}))});ci.value=String(q.correct_index);
    t.appendChild(el('b',{text:(QT[q.question_type]||q.question_type)+' · 难度 '+q.level}));t.appendChild(text);
    if(q.question_type==='single_choice'){opts.forEach(function(n,i){t.appendChild(el('label',{class:'row'},el('span',{text:String.fromCharCode(65+i)+'.'}),n))});t.appendChild(ci)}
    else if(q.question_type==='true_false'){ci.textContent='';['正确','错误'].forEach(function(x,i){ci.appendChild(el('option',{value:i,text:'答案：'+x}))});ci.value=String(q.correct_index);t.appendChild(ci)}
    else t.appendChild(answer);
    if(q.figure&&q.figure.type)t.appendChild(el('div',{class:'muted',text:'含图示（'+q.figure.type+'），布置后学生页面显示。'}));
    t.appendChild(know);t.appendChild(exp);box.appendChild(t);
    [text,answer,exp,know,ci].concat(opts).forEach(function(n){n.addEventListener('input',onchange);n.addEventListener('change',onchange)});
    return {box:box,value:function(){return {question_type:q.question_type,level:q.level,text:text.value,options:q.question_type==='single_choice'?opts.map(function(n){return n.value}):q.options,
      correct_index:+ci.value,answer:answer.value,accepted_answers:q.accepted_answers||[],figure:q.figure||{},explanation:exp.value,knowledge:know.value}}};
  }
  function practicePanel(card,r,ed,refresh){
    var p=r.draft.practice||{},box=el('div',{class:'card'}),msg=el('div',{role:'status','aria-live':'polite'}),dirty=false;
    var stored={};(p.groups||[]).forEach(function(g){stored[g.key]=g});
    box.appendChild(el('h2',{text:'针对性练习 · '+(r.practiceLabels[p.state||'none']||'未生成')}));
    box.appendChild(el('div',{class:'muted',text:'按本报告中需订正、部分正确的题，为'+r.studentName+'单独出新题（不重发原题）。生成和发布报告都不会布置；审核后点“确认并布置”，才会通过现有针对性练习发到该生的“作业”。'}));
    if(!r.practiceGroups.length&&!(p.groups||[]).length){box.appendChild(el('div',{class:'muted',text:'本报告没有需订正或部分正确的题，不需要针对性练习。'}));card.appendChild(box);return}
    var locked=['assigning','assigned','graded','partial'].indexOf(p.state)>=0,counts={},editors=[];
    function changed(){dirty=true;msg.textContent='练习有未保存的修改'}
    r.practiceGroups.forEach(function(g){
      var sg=stored[g.key]||{},gb=el('div',{class:'card'});
      gb.appendChild(el('b',{text:g.subject+' · 薄弱点：'+g.topic}));
      gb.appendChild(el('div',{class:'muted',text:'错题依据：'+g.basis}));
      if(!locked){
        var n=el('input',{type:'number',min:1,max:5,value:sg.count||g.count,style:'width:70px'});counts[g.key]=n;
        gb.appendChild(el('div',{class:'row'},el('span',{class:'muted',text:'题数'}),n,el('button',{text:(sg.questions||[]).length?'重新生成本薄弱点':'生成本薄弱点',onclick:function(){generate([g.key])}})));
      }
      var list=[];
      (sg.questions||[]).forEach(function(q,i){
        if(locked){gb.appendChild(el('p',{style:'white-space:pre-wrap',text:(i+1)+'. ['+(QT[q.question_type]||'')+'] '+q.text+(q.options.length?'\n'+q.options.map(function(o,j){return String.fromCharCode(65+j)+'. '+o}).join('　'):'')+'\n答案：'+(q.question_type==='single_choice'||q.question_type==='true_false'?String.fromCharCode(65+q.correct_index):q.answer)+(q.explanation?'　解析：'+q.explanation:'')}));return}
        var qe=questionEditor(q,changed),holder=el('div');holder.appendChild(qe.box);
        holder.appendChild(el('button',{text:'删除这题',onclick:function(){holder.remove();list.splice(list.indexOf(qe),1);changed()}}));
        list.push(qe);gb.appendChild(holder);
      });
      editors.push({key:g.key,list:list});
      box.appendChild(gb);
    });
    function generate(keys){
      if(dirty&&!confirm('练习有未保存的修改，重新生成会替换所选薄弱点的题目。确定吗？'))return;
      if(ed.dirty){msg.textContent='请先保存报告草稿，再生成练习';return}
      var c={};Object.keys(counts).forEach(function(k){c[k]=+counts[k].value||2});
      msg.textContent='正在出题，约半分钟…';
      api('/teacher/weekend/reports/'+r.id+'/practice/generate',{json:{revision:r.draft.revision,groupKeys:keys||[],counts:c}}).then(function(d){refresh(d.report);if(d.problems.length)alert('部分题目没有生成：\n'+d.problems.join('\n'))}).catch(function(e){msg.textContent=e.message});
    }
    var actions=el('div',{class:'row'});
    if(!locked){
      actions.appendChild(el('button',{text:(p.groups||[]).length?'全部重新生成':'生成针对性练习（不会布置）',onclick:function(){generate([])}}));
      if((p.groups||[]).length){
        actions.appendChild(el('button',{text:'保存练习修改',onclick:function(){
          if(ed.dirty){msg.textContent='请先保存报告草稿';return}
          api('/teacher/weekend/reports/'+r.id+'/practice',{method:'PUT',json:{revision:r.draft.revision,groups:editors.map(function(x){return {key:x.key,questions:x.list.map(function(q){return q.value()})}})}}).then(refresh).catch(function(e){msg.textContent=e.message});
        }}));
        var due=el('input',{type:'text',placeholder:'截止日期（可空，默认3天）',style:'width:190px'}),go=el('button',{class:'primary',text:'审核确认并布置给'+r.studentName,onclick:function(){
          if(dirty||ed.dirty){msg.textContent='请先保存修改，再布置';return}
          if(!confirm('确认题目、答案和解析都已审核？将只布置给'+r.studentName+'，布置后不能再修改，也不会重复布置。'))return;
          go.disabled=true;msg.textContent='正在布置…';
          api('/teacher/weekend/reports/'+r.id+'/practice/assign',{json:{revision:r.draft.revision,dueDate:due.value}}).then(refresh).catch(function(e){msg.textContent=e.message;go.disabled=false});
        }});
        actions.appendChild(due);actions.appendChild(go);
      }
    }else{
      (p.assignments||[]).forEach(function(a){
        var out=el('div');
        box.appendChild(el('div',{class:'notice '+(a.state==='graded'?'ok':''),text:a.subject+'：'+a.title+(a.state==='graded'?' · 已提交并自动批改，做对 '+a.correct+'/'+a.total+'（'+a.submittedAt+'）':' · 已布置，等待学生提交')}));
        var expanded=false,detailButton=el('button',{text:'查看作答与批改',onclick:function(){
          if(expanded){out.textContent='';expanded=false;detailButton.textContent='查看作答与批改';return}
          detailButton.disabled=true;out.textContent='正在读取逐题作答…';
          api('/teacher/weekend/reports/'+r.id+'/practice/'+a.assignmentId+'/answers').then(function(d){
            out.textContent='';expanded=true;detailButton.textContent='收起作答，返回报告';
            out.appendChild(el('div',{class:'notice',text:d.state==='submitted'?'作业汇总：做对 '+d.correct+'/'+d.total:'尚未提交；以下为当前练习题目'}));
            out.appendChild(el('div',{class:'muted',text:d.questionNotice}));
            if(!d.items.length)out.appendChild(el('div',{class:'muted',text:'没有可读取的逐题记录，请在原作业中核对。'}));
            d.items.forEach(function(q,i){
              var item=el('div',{class:'card'});
              item.appendChild(el('b',{text:(i+1)+'. '+(q.knowledge||'未标注考点')}));
              item.appendChild(el('p',{style:'white-space:pre-wrap;overflow-wrap:anywhere',text:q.text}));
              if(q.options.length)item.appendChild(el('p',{style:'white-space:pre-wrap',text:q.options.map(function(o,j){return String.fromCharCode(65+j)+'. '+o}).join('\n')}));
              item.appendChild(el('div',{text:'记录的回答：'+(q.studentAnswer||'未记录')}));
              item.appendChild(el('div',{class:'muted',text:'提交时判定：'+(q.correct===true?'正确':q.correct===false?'需订正':'无逐题判定记录')}));
              out.appendChild(item);
            });
          }).catch(function(e){out.textContent=e.message}).then(function(){detailButton.disabled=false});
        }});
        box.appendChild(detailButton);
        box.appendChild(out);
      });
      if(p.state==='partial')actions.appendChild(el('button',{class:'primary',text:'继续布置未完成的科目',onclick:function(){api('/teacher/weekend/reports/'+r.id+'/practice/assign',{json:{revision:r.draft.revision}}).then(refresh).catch(function(e){msg.textContent=e.message})}}));
    }
    box.appendChild(actions);box.appendChild(msg);card.appendChild(box);
  }
  load();
}
boot(reportPage);
"""

PARENT_JS = REPORT_VIEW_JS + r"""
var CHILD=+(new URLSearchParams(location.search).get('child')||0);
function parentBoot(){
  obtainToken().then(function(t){TOKEN=t;if(!TOKEN){msg('请先登录后再打开');return}
    return api('/session').then(function(s){if(s.role!=='parent'){msg('这个页面给家长使用');return}return api('/parent/children').then(paintChildren)})}).catch(function(e){msg(e.message||'打不开')});
}
function paintChildren(list){
  root.textContent='';
  var items=Array.isArray(list)?list:(list.items||list.children||[]);
  if(CHILD)items=items.filter(function(c){return +(c.id||c.studentID||c.studentId)===CHILD});
  if(!items.length){root.appendChild(el('div',{class:'card'},el('h2',{text:'还没有关联孩子'})));return}
  items.forEach(function(c){
    var id=c.id||c.studentID||c.studentId,box=el('div',{class:'card'},el('h2',{text:(c.name||'孩子')+' 的周末课学情反馈'}));
    root.appendChild(box);
    api('/parent/children/'+id+'/weekend-briefs').then(function(d){
      var reports=d.reports||[];
      if(!reports.length&&!d.items.length){box.appendChild(el('div',{class:'muted',text:'老师发布后会显示在这里。还没有反馈不代表孩子没有交作业。'}));return}
      var subject=el('select',{'aria-label':'科目'}),date=el('select',{'aria-label':'日期'}),out=el('div');
      [['','全部科目'],['语文','语文'],['数学','数学']].forEach(function(x){subject.appendChild(el('option',{value:x[0],text:x[1]}))});
      date.appendChild(el('option',{value:'',text:'全部日期'}));
      reports.map(function(r){return r.date}).filter(function(x,i,a){return a.indexOf(x)===i}).forEach(function(x){date.appendChild(el('option',{value:x,text:x}))});
      function paint(){
        out.textContent='';var shown=0;
        reports.forEach(function(r){
          if(date.value&&r.date!==date.value)return;
          var keep=r.facts.map(function(f,i){return i}).filter(function(i){return !subject.value||r.facts[i].subject===subject.value});
          if(!keep.length)return;shown++;
          out.appendChild(el('div',{class:'row'},el('b',{text:r.date+' · '+keep.map(function(i){return r.facts[i].subject}).join('、')}),el('span',{class:'muted',text:'发布于 '+r.publishedAt+(r.version>1?' · 已更新为第 '+r.version+' 版（最新）':'')})));
          var pr=r.practice&&Object.assign({},r.practice);
          if(pr&&subject.value){if(pr.groups)pr.groups=pr.groups.filter(function(g){return g.subject===subject.value});if(pr.assignments)pr.assignments=pr.assignments.filter(function(a){return a.subject===subject.value})}
          out.appendChild(reportView({facts:keep.map(function(i){return r.facts[i]}),sections:keep.map(function(i){return r.sections[i]}),glance:keep.map(function(i){return (r.glance||[])[i]}),comment:r.comment,titles:r.titles,practice:pr}));
        });
        if(!shown&&reports.length)out.appendChild(el('div',{class:'muted',text:'所选日期或科目还没有已发布的反馈。'}));
      }
      if(reports.length){box.appendChild(el('div',{class:'row'},el('label',{},el('span',{text:'科目 '}),subject),el('label',{},el('span',{text:'日期 '}),date)));subject.onchange=date.onchange=paint;box.appendChild(out);paint()}
      if(d.items.length){
        var old=el('details',{open:!reports.length},el('summary',{text:'此前的课堂简报'}));
        d.items.forEach(function(b){old.appendChild(el('div',{class:'item'},el('span',{class:'t'},el('b',{text:b.title+' · '+b.at}),el('div',{text:b.text}))))});
        box.appendChild(old);
      }
    }).catch(function(e){box.appendChild(el('div',{class:'notice error',text:e.message}))});
  });
}
parentBoot();
"""

