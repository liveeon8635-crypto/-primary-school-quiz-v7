"""Teacher writing review and frozen classroom, using the shared authenticated shell."""


def writing_page():
    from changying.web.weekend_pages import _page
    html = _page('作文课', r'''
var query=new URLSearchParams(location.search),lid=query.get('lesson'),sid=query.get('session'),data,editor,noteBox,activeStage=2;
var roles={pending:'待确认',review:'点名与回顾',model:'范文段落',model_image:'范文配图',picture:'看图写话图片',method:'写作方法与例句',task:'写作主题',feedback:'课后反馈要求'};
var roleStage={review:1,model:2,model_image:2,picture:3,method:4,task:5,feedback:6};
function message(e){noteBox.textContent=e.message||e;if(noteBox.scrollIntoView)noteBox.scrollIntoView({block:'nearest'})}
function button(label,fn){return el('button',{text:label,onclick:function(){Promise.resolve().then(fn).catch(message)}})}
function prepare(){return api('/teacher/weekend/lessons/'+lid+'/writing').then(function(d){data=d;
 var remembered=sessionStorage.getItem('writing-stage-'+lid);
 var first=(d.package&&d.package.nodes||[]).filter(function(n){return n.status==='pending'&&roleStage[n.role]}).map(function(n){return roleStage[n.role]}).sort()[0];
 activeStage=remembered==='pending'?'pending':Number(remembered)>=1&&Number(remembered)<=6?Number(remembered):first||1;
 paintEditor();
 if(query.get('imported')==='1'){message('已导入备课草稿');query.delete('imported');history.replaceState(null,'',location.pathname+'?'+query.toString())}
 })}
function selectStage(stage){
 activeStage=stage;
 sessionStorage.setItem('writing-stage-'+lid,String(stage));
 paintEditor();
 var panel=root.querySelector('.wr-stage-panel');
 panel.focus();
 panel.scrollIntoView({block:'start'});
}
function paintEditor(){
 root.className='writing-review';root.textContent='';noteBox=el('p',{role:'status'});root.appendChild(el('h1',{text:'作文素材与审核'}));root.appendChild(noteBox);
 var back='/v1/weekend-plan?subject='+encodeURIComponent('语文')+'&lesson='+encodeURIComponent(lid);
 root.appendChild(el('a',{href:back,text:'返回本课课次行'}));
 if(data.package)root.appendChild(el('a',{href:back+'&view=courseware',style:'margin-left:16px',text:'审核本课六环节课件'}));
 if(!data.package){message('请从备课工作栏导入作文教案。');return}
 var title=el('input',{'aria-label':'课程标题',value:data.package.title||''});title.oninput=function(){data.package.title=title.value};root.appendChild(el('label',{text:'课题名称'}));root.appendChild(title);
 root.appendChild(el('p',{class:'wr-intro',text:'按作文六环节整理材料。先选环节，再核对该环节的文字、图片与来源；改动后需重新审核，已创建课堂仍使用原冻结版本。'}));
 var counts={pending:0,confirmed:0,ignored:0};data.package.nodes.forEach(function(n){counts[n.status]=(counts[n.status]||0)+1});
 var summary=el('div',{class:'wr-summary','aria-label':'素材审核概况'});
 [['待确认',counts.pending],['已确认',counts.confirmed],['已忽略',counts.ignored]].forEach(function(x){summary.appendChild(el('div',{class:'wr-stat'},el('strong',{text:String(x[1])}),x[0]+'项素材'))});root.appendChild(summary);
 var readiness=data.readiness.stageReadiness||[],nav=el('nav',{class:'wr-stages','aria-label':'作文六环节'});
 readiness.forEach(function(s,index){var stage=index+1,items=data.package.nodes.filter(function(n){return Number(roleStage[n.role])===stage}),pending=items.filter(function(n){return n.status==='pending'}).length;
  var b=button(stage+'. '+s.name,function(){selectStage(stage)});b.className='wr-stage';b.setAttribute('aria-pressed',String(Number(activeStage)===stage));b.appendChild(el('small',{text:(pending?'待审核':s.status)+(pending?' · '+pending+'项待确认':'')+(s.missing&&s.missing.length?' · '+s.missing.join('、'):'')}));nav.appendChild(b);
 });
 var pendingUnassigned=data.package.nodes.filter(function(n){return !roleStage[n.role]&&n.status==='pending'}).length;var ub=button('待分类',function(){selectStage('pending')});ub.className='wr-stage';ub.setAttribute('aria-pressed',String(activeStage==='pending'));ub.appendChild(el('small',{text:pendingUnassigned+'项待分类素材'}));nav.appendChild(ub);root.appendChild(nav);
 root.appendChild(el('p',{class:'wr-intro',text:'图片是否适合作文场景、段落是否完整，需要老师核对原件。图片截图和思维导图不会自动当作配图。'}));
 var actions=el('div',{class:'wr-review-actions'});actions.appendChild(button('保存草稿',function(){return save(false)}));actions.appendChild(button('审核通过',function(){return save(true)}));root.insertBefore(actions,nav);
 var assigned=data.package.nodes.filter(function(n){return n.status==='pending'&&n.role&&n.role!=='pending'}).length;
 var tools=el('details',{class:'wr-tools'});tools.appendChild(el('summary',{text:'补充或批量处理素材'}));tools.appendChild(el('p',{text:'批量操作会记入修订历史；确认素材归属不等于整课审核通过。'}));var toolrow=el('div',{class:'row'});
 toolrow.appendChild(button('确认已分类（'+assigned+'项）',function(){if(!assigned)throw Error('没有待确认的已分类素材');if(!confirm('确认你已检查并同意这 '+assigned+' 项素材的归属及内容吗？审核通过仍需另行操作。'))return;return api('/teacher/weekend/lessons/'+lid+'/writing/bulk-review',{method:'POST',json:{expectedRevision:data.revision,action:'confirm_assigned'}}).then(function(d){data=d;paintEditor();message('已确认 '+d.updated+' 项；课程仍未审核通过')})}));
 toolrow.appendChild(button('忽略待分类（'+pendingUnassigned+'项）',function(){if(!pendingUnassigned)throw Error('没有待处理的未分类素材');if(!confirm('确认这 '+pendingUnassigned+' 项不纳入本次作文课？素材会保留在原始记录和修订历史中。'))return;return api('/teacher/weekend/lessons/'+lid+'/writing/bulk-review',{method:'POST',json:{expectedRevision:data.revision,action:'ignore_unassigned'}}).then(function(d){data=d;paintEditor();message('已将 '+d.updated+' 项标为忽略；可以在素材列表中恢复审核')})}));
 toolrow.appendChild(button('导入已确认配图',function(){return api('/teacher/weekend/lessons/'+lid+'/writing/imported-images',{method:'POST',json:{}}).then(function(d){data=d;paintEditor();message(d.created?'已将 '+d.created+' 张图片加入作文包；请逐张确认并绑定范文段落':'没有新的已确认配图可导入')})}));
 toolrow.appendChild(button('新增文字素材',function(){data.package.nodes.push({id:'manual-'+Date.now(),kind:'text',text:'',role:activeStage==='pending'?'pending':activeStage===1?'review':activeStage===2?'model':activeStage===3?'picture':activeStage===4?'method':activeStage===5?'task':'feedback',status:'pending',targets:[]});paintEditor()}));
 var file=el('input',{type:'file',accept:'image/*','aria-label':'补充图片'});toolrow.appendChild(file);toolrow.appendChild(button('上传图片',function(){if(!file.files[0])throw Error('请先选择图片');return save(false).then(function(){var fd=new FormData();fd.append('file',file.files[0]);fd.append('expectedRevision',data.revision);return api('/teacher/weekend/lessons/'+lid+'/writing/images',{method:'POST',body:fd})}).then(function(d){data=d;paintEditor()})}));tools.appendChild(toolrow);root.insertBefore(tools,nav);
 if(data.readiness.startReasons&&data.readiness.startReasons.length)root.appendChild(el('details',{},el('summary',{text:'查看开课前待办（'+data.readiness.startReasons.length+'）'}),el('ul',{},...data.readiness.startReasons.map(function(reason){return el('li',{text:reason})}))));else root.appendChild(el('p',{class:'notice ok',text:'六环节素材已满足开课检查。'}));
 if(data.readiness.canStart)root.appendChild(button('选择班级并保存待开课堂',function(){if(!data.readiness.canStart)throw Error('请先完成审核');chooseWeekendClass(function(classId){return api('/teacher/weekend/sessions',{json:{lessonId:Number(lid),classId:classId}}).then(function(s){location.href='/v1/weekend-writing?session='+s.id})})}));
 root.appendChild(el('p',{class:'wr-intro',text:'预约日期在备课工作栏填写；保存待开课堂后，教师可在课堂页点击“立即开始”。修订 '+data.revision+' · 历史修改 '+(data.package.history||[]).length+' 次。'}));
 var section=el('section',{class:'wr-stage-panel',tabindex:'-1'},el('h2',{text:activeStage==='pending'?'待分类素材':(readiness[Number(activeStage)-1]||{}).name||''}));
 var stageNodes=data.package.nodes.map(function(n,i){return {node:n,index:i}}).filter(function(x){return activeStage==='pending'?!roleStage[x.node.role]:Number(roleStage[x.node.role])===Number(activeStage)});
 if(!stageNodes.length)section.appendChild(el('p',{text:'本环节还没有素材。可从“补充或批量处理素材”添加文字或图片。'}));
 stageNodes.forEach(function(entry){var n=entry.node,i=entry.index;
  var card=el('section',{class:'wr-item'}),head=el('div',{class:'wr-item-head'}),role=el('select',{'aria-label':'素材归属'}),status=el('select',{'aria-label':'审核状态'}),text=el('textarea',{'aria-label':'素材正文'});
  Object.keys(roles).forEach(function(k){role.appendChild(el('option',{value:k,text:roles[k],selected:n.role===k}))});role.onchange=function(){n.role=role.value};
  ['pending','confirmed','ignored'].forEach(function(k){status.appendChild(el('option',{value:k,text:{pending:'待确认',confirmed:'确认',ignored:'忽略'}[k],selected:n.status===k}))});status.onchange=function(){n.status=status.value};
  text.value=n.text||'';text.oninput=function(){n.text=text.value};head.appendChild(el('strong',{text:(i+1)+' · '+(n.kind==='image'?'图片素材':'文字素材')}));head.appendChild(el('span',{class:'tag '+(n.status==='confirmed'?'ok':'warn'),text:{pending:'待确认',confirmed:'已确认',ignored:'已忽略'}[n.status]||'待确认'}));card.appendChild(head);
  if(n.dataUrl)card.appendChild(el('img',{src:n.dataUrl,alt:'素材原图'}));
  if(n.text||n.kind!=='image')card.appendChild(text);
  var fields=el('div',{class:'wr-bindings'});fields.appendChild(el('label',{},'用途 ',role));fields.appendChild(el('label',{},'状态 ',status));card.appendChild(fields);
  var source=el('details');source.appendChild(el('summary',{text:'查看原件来源与识别依据'}));source.appendChild(el('p',{class:'wr-source',text:'来源：'+JSON.stringify(n.source||{})+(n.declaredSource?'；素材声明：'+JSON.stringify(n.declaredSource):'')+'；识别依据：'+(n.reason||'教师配置')}));card.appendChild(source);
  if(n.kind==='image'){
    card.appendChild(el('p',{text:'这张图对应哪段范文？（可多选）'}));var bindings=el('div',{class:'wr-bindings'});
    data.package.nodes.filter(function(p){return p.role==='model'&&p.status!=='ignored'}).forEach(function(p){var check=el('input',{type:'checkbox',checked:(n.targets||[]).indexOf(p.id)>=0});check.onchange=function(){n.targets=(n.targets||[]).filter(function(x){return x!==p.id});if(check.checked)n.targets.push(p.id)};bindings.appendChild(el('label',{},check,(p.text||'未填写段落').slice(0,100))) });card.appendChild(bindings);
  }
  var edit=el('details');edit.appendChild(el('summary',{text:'整理文字与顺序'}));edit.appendChild(button('上移',function(){if(i){data.package.nodes.splice(i,1);data.package.nodes.splice(i-1,0,n);paintEditor()}}));
  edit.appendChild(button('按换行拆分',function(){var pieces=(n.text||'').split(/\n+/).filter(Boolean);if(pieces.length<2)throw Error('请先用换行分段');n.status='ignored';pieces.forEach(function(t,j){data.package.nodes.splice(i+1+j,0,{id:'split-'+Date.now()+'-'+j,derivedFrom:n.id,kind:'text',text:t,role:n.role,status:'pending',targets:[]})});paintEditor()}));
  edit.appendChild(button('与下一段合并',function(){var next=data.package.nodes[i+1];if(!next||next.kind==='image')throw Error('下一项不能合并');n.text+='\n'+next.text;next.status='ignored';n.status='pending';paintEditor()}));card.appendChild(edit);section.appendChild(card);
 });root.insertBefore(section,nav.nextSibling);
}
function save(approve){return api('/teacher/weekend/lessons/'+lid+'/writing',{method:'PUT',json:{expectedRevision:data.revision,nodes:data.package.nodes,title:data.package.title||'',approve:approve}}).then(function(d){data=d;paintEditor();message(approve?'审核通过，后续课堂将冻结此版本':'草稿已保存')})}
function loadClass(){return api('/weekend/writing/sessions/'+sid).then(function(d){data=d;paintClass()})}
function paintClass(){
 root.className='';root.textContent='';noteBox=el('p',{role:'status'});root.appendChild(el('h1',{text:data.title||'作文课'}));root.appendChild(noteBox);
 if(data.teacher){
  root.appendChild(el('a',{href:'/v1/weekend?s='+sid,text:'点名、课堂计时与班级控制'}));
  if(data.status==='planned')root.appendChild(button('立即开始',function(){return api('/teacher/weekend/sessions/'+sid+'/start',{json:{}}).then(loadClass)}));
  (data.stages||[]).forEach(function(stage){root.appendChild(button(stage.name,function(){return api('/teacher/weekend/sessions/'+sid+'/goto',{json:{stage:stage.no}}).then(loadClass)}))});
 }
 root.appendChild(el('p',{text:'当前第 '+data.stage+' 环节。'+(data.teacher?'勾选后开放；学生接口只返回开放内容。':'只显示老师开放的内容。')}));
 var selected=data.open.slice();
 var roleStage={review:1,model:2,model_image:2,picture:3,method:4,task:5,feedback:6};
 var choose=el('select',{'aria-label':'查看环节'}),cards=el('div');
 (data.stages||[]).forEach(function(stage){choose.appendChild(el('option',{value:stage.no,text:stage.name,selected:stage.no===data.stage}))});
 root.appendChild(choose);root.appendChild(cards);
 function drawStage(){
  cards.textContent='';var no=Number(choose.value),items=data.nodes.filter(function(n){return roleStage[n.role]===no});
  if(no===2){var images=items.filter(function(n){return n.role==='model_image'}),ordered=[];
   items.filter(function(n){return n.role==='model'}).forEach(function(n){ordered.push(n);images.forEach(function(pic){if((pic.targets||[]).indexOf(n.id)>=0&&ordered.indexOf(pic)<0)ordered.push(pic)})});
   images.forEach(function(pic){if(ordered.indexOf(pic)<0)ordered.push(pic)});items=ordered}
  if(!items.length)cards.appendChild(el('p',{text:'本环节还没有开放内容。'}));
  items.forEach(function(n){var card=el('section',{class:'card'});
   if(data.teacher){var check=el('input',{type:'checkbox',checked:selected.indexOf(n.id)>=0});check.onchange=function(){selected=selected.filter(function(x){return x!==n.id});if(check.checked)selected.push(n.id)};card.appendChild(el('label',{},check,'开放 '+roles[n.role]))}
   if(n.text)card.appendChild(el('p',{text:n.text,style:'white-space:pre-wrap'}));
   if(n.dataUrl)card.appendChild(el('img',{src:n.dataUrl,alt:roles[n.role],style:'max-width:100%;max-height:500px'}));cards.appendChild(card)});
 }
 choose.onchange=drawStage;drawStage();
 if(data.teacher){root.appendChild(button('保存开放范围',function(){return api('/teacher/weekend/writing/sessions/'+sid+'/release',{json:{expectedRevision:data.revision,nodeIds:selected}}).then(function(d){data=d;paintClass()})}));teacherWork()}else{studentWork()}
}
function studentWork(){
 var area=el('section',{class:'card'});root.appendChild(area);
 api('/student/weekend/sessions/'+sid+'/written').then(function(d){d.questions.forEach(function(q){var text=el('textarea',{'aria-label':'作文文字'}),camera=el('input',{type:'file',accept:'image/*',capture:'environment','aria-label':'拍照或重拍'}),files=el('input',{type:'file',accept:'image/*',multiple:true,'aria-label':'选择多张照片'}),preview=el('div');text.value=q.submission?q.submission.text:'';
 area.appendChild(el('h2',{text:q.stem}));area.appendChild(text);
 area.appendChild(el('label',{},'拍照或重拍',camera));area.appendChild(el('label',{},'从相册选择多张',files));area.appendChild(preview);
 function photos(){return Array.prototype.slice.call(camera.files||[]).concat(Array.prototype.slice.call(files.files||[]))}
 function showPhotoPreview(){preview.textContent='';photos().forEach(function(f){var url=URL.createObjectURL(f);preview.appendChild(el('img',{src:url,alt:'待提交照片',style:'max-width:180px',onload:function(){URL.revokeObjectURL(url)}}))})}
 camera.onchange=showPhotoPreview;files.onchange=showPhotoPreview;
 area.appendChild(button('提交／重拍后再次提交',function(){var selected=photos();if(selected.length>6)throw Error('一次最多6张照片');var fd=new FormData();fd.append('text',text.value);fd.append('revision',q.submission?q.submission.revision:0);selected.forEach(function(f){fd.append('photos',f)});return api('/student/weekend/sessions/'+sid+'/written/'+q.id,{method:'POST',body:fd}).then(function(r){q.submission=r.submission;message('已提交第 '+r.versionNo+' 版；照片不会因课堂翻页丢失')})}));
 area.appendChild(button('查看我的提交与批注',function(){return api('/student/weekend/sessions/'+sid+'/written/'+q.id+'/versions').then(function(r){showVersions(area,r,q.id,null)})}));
 })}).catch(message);
 if(data.feedback)area.appendChild(el('p',{text:'已发布反馈：'+data.feedback.comment+'；下一步：'+data.feedback.nextStep}));
}
function teacherWork(){
 var area=el('section',{class:'card'});root.appendChild(area);area.appendChild(el('h2',{text:'学生提交、批注与反馈'}));
 api('/teacher/weekend/sessions/'+sid+'/written').then(function(d){
 (data.students||[]).forEach(function(s){var card=el('section',{class:'card'});card.appendChild(el('strong',{text:s.name}));
 var facts=data.completion[String(s.id)]||{};card.appendChild(el('p',{text:'到课：'+(facts.attendance===true?'已到':facts.attendance===false?'缺席':'未点名')+'；范文/看图/技法到达：'+[facts.model,facts.picture,facts.methods].map(function(v){return v?'是':'否'}).join('/')+'；写作提交：'+(facts.submitted?'已提交':'未提交')}));
 [true,false].forEach(function(present){card.appendChild(button(present?'到课':'缺席',function(){return api('/teacher/weekend/writing/sessions/'+sid+'/attendance',{json:{expectedRevision:data.revision,studentId:s.id,present:present}}).then(function(r){data=r;message('点名已保存')})}))});
 (d.questions||[]).forEach(function(q){card.appendChild(button('查看写作照片与版本',function(){return api('/teacher/weekend/sessions/'+sid+'/written/'+q.id+'/students/'+s.id+'/versions').then(function(r){showVersions(card,r,q.id,s.id)})}))});
 var draft=(data.feedback[String(s.id)]||{}).draft||{},comment=el('textarea',{'aria-label':'教师评语'}),next=el('textarea',{'aria-label':'下一步建议'});comment.value=draft.comment||('课堂记录：'+(facts.submitted?'已提交写作任务。':'尚未提交写作任务。'));next.value=draft.nextStep||'';card.appendChild(comment);card.appendChild(next);
 [false,true].forEach(function(publish){card.appendChild(button(publish?'确认发布反馈':'保存反馈草稿',function(){return api('/teacher/weekend/writing/sessions/'+sid+'/feedback',{json:{studentId:s.id,expectedRevision:data.revision,comment:comment.value,nextStep:next.value,publish:publish}}).then(function(r){data=r;message(publish?'反馈已发布':'草稿已保存，学生不可见')})}))});area.appendChild(card)
 })}).catch(message);
}
function drawMarks(canvas,p,shapes){
 var image=new Image();image.onload=function(){var width=Math.min(720,image.width),height=image.height*width/image.width;canvas.width=width;canvas.height=height;var ctx=canvas.getContext('2d');ctx.drawImage(image,0,0,width,height);ctx.strokeStyle='#d62828';ctx.fillStyle='#d62828';ctx.lineWidth=3;ctx.font='18px sans-serif';
 shapes.forEach(function(s){ctx.beginPath();if(s.kind==='circle'){ctx.ellipse(s.x,s.y,Math.max(Math.abs(s.w),5),Math.max(Math.abs(s.h),5),0,0,Math.PI*2)}else if(s.kind==='text'){ctx.fillText(s.text||'',s.x,s.y)}else{ctx.moveTo(s.x,s.y);ctx.lineTo(s.x+s.w,s.y+s.h);var a=Math.atan2(s.h,s.w),x=s.x+s.w,y=s.y+s.h;ctx.moveTo(x-12*Math.cos(a-.5),y-12*Math.sin(a-.5));ctx.lineTo(x,y);ctx.lineTo(x-12*Math.cos(a+.5),y-12*Math.sin(a+.5))}ctx.stroke()})};image.src=p.dataUrl;
}
function showVersions(area,result,qid,student){
 (result.items||result.versions||[]).forEach(function(v){var box=el('section',{class:'card'});box.appendChild(el('p',{text:'第 '+v.versionNo+' 版 '+(v.text||v.answerText||'')}));
 var shapes=[],mode=el('select');[['circle','圈画'],['arrow','箭头'],['text','文字']].forEach(function(x){mode.appendChild(el('option',{value:x[0],text:x[1]}))});var label=el('input',{'aria-label':'图上文字',placeholder:'文字批注'});if(student){box.appendChild(mode);box.appendChild(label)}
 (v.photos||[]).forEach(function(p,index){var canvas=el('canvas',{'aria-label':'照片批注画布',style:'max-width:100%;touch-action:none'}),start=null;box.appendChild(canvas);var prior=[];(v.annotations||[]).forEach(function(a){(a.shapes||[]).forEach(function(s){if((s.photoIndex||0)===index)prior.push(s)})});function draw(){drawMarks(canvas,p,prior.concat(shapes.filter(function(s){return s.photoIndex===index})))}draw();
 if(student){function point(e){var t=e.touches?e.touches[0]:e.changedTouches?e.changedTouches[0]:e,r=canvas.getBoundingClientRect();return {x:(t.clientX-r.left)*canvas.width/r.width,y:(t.clientY-r.top)*canvas.height/r.height}}function down(e){e.preventDefault();start=point(e)}function up(e){if(!start)return;e.preventDefault();var end=point(e);shapes.push({kind:mode.value,photoIndex:index,x:start.x,y:start.y,w:end.x-start.x,h:end.y-start.y,text:label.value});start=null;draw()}canvas.addEventListener('mousedown',down);canvas.addEventListener('mouseup',up);canvas.addEventListener('touchstart',down);canvas.addEventListener('touchend',up)}
 });
 (v.annotations||[]).forEach(function(a){box.appendChild(el('p',{text:a.verdict+'：'+a.comment}))});
 if(student){var comment=el('textarea',{'aria-label':'批注文字'}),verdict=el('select');[['passed','通过'],['needs_revision','需修改'],['retake','需重拍']].forEach(function(x){verdict.appendChild(el('option',{value:x[0],text:x[1]}))});box.appendChild(comment);box.appendChild(verdict);box.appendChild(button('保存批注',function(){return api('/teacher/weekend/sessions/'+sid+'/written/'+qid+'/students/'+student+'/annotate',{json:{submissionVersionId:v.id,verdict:verdict.value,comment:comment.value,shapes:shapes}}).then(function(){message('批注已保存')})}))}area.appendChild(box)
 });
}
obtainToken().then(function(t){
 TOKEN=t;
 if(query.get('student')){
  root.textContent='';
  return api('/parent/weekend/writing/students/'+query.get('student')).then(function(d){
   root.appendChild(el('h1',{text:'作文课已发布反馈'}));
   d.items.forEach(function(i){
    var v=i.versions[i.versions.length-1];
    root.appendChild(el('section',{class:'card'},el('h2',{text:i.title}),el('p',{text:v.comment}),el('p',{text:'下一步：'+v.nextStep})));
   });
  });
 }
 if(!sid&&!lid){
  root.textContent='';
  return api('/parent/weekend/writing').then(function(d){
   root.appendChild(el('h1',{text:'作文课已发布反馈'}));
   d.students.forEach(function(s){root.appendChild(el('a',{href:'/v1/weekend-writing?student='+s.id,text:s.name+' 的作文反馈'}))});
  });
 }
 return sid?loadClass():prepare();
}).catch(function(e){root.textContent=e.message});
''', True, ('/v1/weekend-plan','返回备课'))
    css = """<style id="writing-review-workbench">
#app.writing-review{max-width:1180px;margin:0 auto;padding:20px 18px 48px;color:#172b4d}
#app.writing-review h1{font-size:26px;margin:4px 0 14px}
#app.writing-review .wr-intro{color:#526581;margin:0 0 14px;line-height:1.65}
#app.writing-review .wr-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0}
#app.writing-review .wr-stat,#app.writing-review .wr-stage{border:1px solid #dbe3ed;border-radius:12px;background:#fff;padding:12px 14px}
#app.writing-review .wr-stat strong{display:block;font-size:20px;margin-bottom:3px}
#app.writing-review .wr-stages{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin:12px 0 18px}
#app.writing-review .wr-stage{cursor:pointer;text-align:left;color:#17345f;min-height:72px}
#app.writing-review .wr-stage[aria-pressed="true"]{border-color:#a80d20;box-shadow:inset 0 0 0 1px #a80d20;background:#fff8f7}
#app.writing-review .wr-stage small{display:block;color:#66758b;margin-top:5px}
#app.writing-review .wr-tools{border:1px solid #dbe3ed;border-radius:12px;background:#f7f9fc;padding:12px;margin:14px 0}
#app.writing-review .wr-tools summary{cursor:pointer;font-weight:700}
#app.writing-review .wr-tools .row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
#app.writing-review .wr-item{margin:10px 0;padding:16px;border:1px solid #dbe3ed;border-radius:14px;background:white}
#app.writing-review .wr-item-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}
#app.writing-review .wr-item img{display:block;max-width:min(100%,760px);max-height:420px;object-fit:contain;margin:12px auto;border-radius:10px;background:#f7f8fa}
#app.writing-review .wr-item textarea{display:block;width:100%;min-height:100px;box-sizing:border-box;margin:10px 0;padding:10px;border:1px solid #cbd5e1;border-radius:9px;font:inherit}
#app.writing-review select,#app.writing-review input:not([type=checkbox]):not([type=file]){max-width:100%;padding:9px 10px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;font:inherit}
#app.writing-review button{margin:4px;padding:9px 13px;border:1px solid #d5dce6;border-radius:9px;background:#fff;color:#17345f;font:inherit;cursor:pointer}
#app.writing-review button.primary{background:#a80d20;color:white;border-color:#a80d20}
#app.writing-review .wr-source{color:#65748b;font-size:13px;overflow-wrap:anywhere}
#app.writing-review .wr-bindings{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}
#app.writing-review .wr-bindings label{padding:8px 10px;border:1px solid #e0e6ed;border-radius:8px;max-width:100%}
#app.writing-review .wr-bindings input{margin-right:7px}
@media(max-width:680px){#app.writing-review{padding:14px 12px 32px}#app.writing-review .wr-summary{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}#app.writing-review .wr-stat{padding:9px 7px;font-size:13px}#app.writing-review .wr-stat strong{font-size:17px}#app.writing-review .wr-stages{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}#app.writing-review .wr-stage{padding:10px;min-height:65px}}
</style>"""
    return html.replace('</head>', css + '</head>', 1)

