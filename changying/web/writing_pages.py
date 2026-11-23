"""Teacher writing review and frozen classroom, using the shared authenticated shell."""


def writing_page():
    from changying.web.weekend_pages import _page
    return _page('作文课', r'''
var query=new URLSearchParams(location.search),lid=query.get('lesson'),sid=query.get('session'),data,editor,noteBox;
var roles={pending:'待确认',review:'点名与回顾',model:'范文段落',model_image:'范文配图',picture:'看图写话图片',method:'写作方法与例句',task:'写作主题',feedback:'课后反馈要求'};
function message(e){noteBox.textContent=e.message||e}
function button(label,fn){return el('button',{text:label,onclick:function(){Promise.resolve().then(fn).catch(message)}})}
function prepare(){return api('/teacher/weekend/lessons/'+lid+'/writing').then(function(d){data=d;paintEditor()})}
function paintEditor(){
 root.textContent='';noteBox=el('p',{role:'status'});root.appendChild(el('h1',{text:'作文素材与审核'}));root.appendChild(noteBox);
 if(!data.package){message('请从备课工作栏导入作文教案。');return}
 var title=el('input',{'aria-label':'课程标题',value:data.package.title||''});title.oninput=function(){data.package.title=title.value};root.appendChild(title);
 root.appendChild(el('p',{text:'原件只读保留。图片截图不等于场景配图，请核对用途。修改后审核自动失效；已创建课堂使用冻结版本。'}));
 data.readiness.stageReadiness.forEach(function(s){root.appendChild(el('p',{text:s.name+'：'+s.status+(s.missing.length?'（'+s.missing.join('、')+'）':'')}))});
 root.appendChild(el('p',{text:data.readiness.startReasons.join('；')}));
 root.appendChild(button('保存草稿',function(){return save(false)}));root.appendChild(button('审核通过',function(){return save(true)}));
 var assigned=data.package.nodes.filter(function(n){return n.status==='pending'&&n.role&&n.role!=='pending'}).length;
 var unassigned=data.package.nodes.filter(function(n){return n.status==='pending'&&(!n.role||n.role==='pending')}).length;
 root.appendChild(el('p',{text:'批量处理只作用于待审核项；已分类素材由老师逐项检查后确认，未分类内容由老师决定忽略。每次操作都会记录在修订历史中。'}));
 root.appendChild(button('确认已分类素材（'+assigned+'项）',function(){if(!assigned)throw Error('没有待确认的已分类素材');if(!confirm('确认你已检查并同意这 '+assigned+' 项素材的归属及内容吗？审核通过仍需另行操作。'))return;return api('/teacher/weekend/lessons/'+lid+'/writing/bulk-review',{method:'POST',json:{expectedRevision:data.revision,action:'confirm_assigned'}}).then(function(d){data=d;paintEditor();message('已确认 '+d.updated+' 项；课程仍未审核通过')})}));
 root.appendChild(button('忽略未分类素材（'+unassigned+'项）',function(){if(!unassigned)throw Error('没有待处理的未分类素材');if(!confirm('确认这 '+unassigned+' 项不纳入本次作文课？素材会保留在原始记录和修订历史中。'))return;return api('/teacher/weekend/lessons/'+lid+'/writing/bulk-review',{method:'POST',json:{expectedRevision:data.revision,action:'ignore_unassigned'}}).then(function(d){data=d;paintEditor();message('已将 '+d.updated+' 项标为忽略；可以在素材列表中恢复审核')})}));
 root.appendChild(button('导入已确认的配图',function(){return api('/teacher/weekend/lessons/'+lid+'/writing/imported-images',{method:'POST',json:{}}).then(function(d){data=d;paintEditor();message(d.created?'已将 '+d.created+' 张图片加入作文包；请逐张确认并绑定范文段落':'没有新的已确认配图可导入')})}));
 root.appendChild(button('新增素材',function(){data.package.nodes.push({id:'manual-'+Date.now(),kind:'text',text:'',role:'pending',status:'pending',targets:[]});paintEditor()}));
 var file=el('input',{type:'file',accept:'image/*','aria-label':'补充图片'});root.appendChild(file);
 root.appendChild(button('上传图片',function(){if(!file.files[0])throw Error('请先选择图片');return save(false).then(function(){var fd=new FormData();fd.append('file',file.files[0]);fd.append('expectedRevision',data.revision);return api('/teacher/weekend/lessons/'+lid+'/writing/images',{method:'POST',body:fd})}).then(function(d){data=d;paintEditor()})}));
 root.appendChild(button('选择班级并保存待开课堂',function(){if(!data.readiness.canStart)throw Error('请先完成审核');chooseWeekendClass(function(classId){return api('/teacher/weekend/sessions',{json:{lessonId:Number(lid),classId:classId}}).then(function(s){location.href='/v1/weekend-writing?session='+s.id})})}));
 root.appendChild(el('p',{},'预约日期在备课工作栏填写；保存待开课堂后，教师可在课堂页点击“立即开始”。'));
 root.appendChild(el('p',{text:'修订 '+data.revision+'；历史修改 '+(data.package.history||[]).length+' 次。排序后保存；拆分/合并保留来源条目。'}));
 data.package.nodes.forEach(function(n,i){
  var card=el('section',{class:'card'}),role=el('select',{'aria-label':'素材归属'}),status=el('select',{'aria-label':'审核状态'}),text=el('textarea',{'aria-label':'素材正文'});
  Object.keys(roles).forEach(function(k){role.appendChild(el('option',{value:k,text:roles[k],selected:n.role===k}))});role.onchange=function(){n.role=role.value};
  ['pending','confirmed','ignored'].forEach(function(k){status.appendChild(el('option',{value:k,text:{pending:'待确认',confirmed:'确认',ignored:'忽略'}[k],selected:n.status===k}))});status.onchange=function(){n.status=status.value};
  text.value=n.text||'';text.oninput=function(){n.text=text.value};card.appendChild(el('strong',{text:(i+1)+' · '+n.id}));
  card.appendChild(el('p',{text:'导入来源：'+JSON.stringify(n.source||{})+(n.declaredSource?'；素材声明来源：'+JSON.stringify(n.declaredSource):'')+'；依据：'+(n.reason||'教师配置')}));
  if(n.dataUrl)card.appendChild(el('img',{src:n.dataUrl,alt:'素材原图',style:'max-width:100%;max-height:400px'}));
  card.appendChild(role);card.appendChild(status);card.appendChild(text);
  if(n.kind==='image'){
   card.appendChild(el('p',{text:'关联范文段落（可多选）'}));
   data.package.nodes.filter(function(p){return p.role==='model'&&p.status!=='ignored'}).forEach(function(p){var check=el('input',{type:'checkbox',checked:(n.targets||[]).indexOf(p.id)>=0});check.onchange=function(){n.targets=(n.targets||[]).filter(function(x){return x!==p.id});if(check.checked)n.targets.push(p.id)};card.appendChild(el('label',{},check,p.text.slice(0,60)))})
  }
  card.appendChild(button('上移',function(){if(i){data.package.nodes.splice(i,1);data.package.nodes.splice(i-1,0,n);paintEditor()}}));
  card.appendChild(button('按换行拆分',function(){var pieces=n.text.split(/\n+/).filter(Boolean);if(pieces.length<2)throw Error('请先用换行分段');n.status='ignored';pieces.forEach(function(t,j){data.package.nodes.splice(i+1+j,0,{id:'split-'+Date.now()+'-'+j,derivedFrom:n.id,kind:'text',text:t,role:n.role,status:'pending',targets:[]})});paintEditor()}));
  card.appendChild(button('与下一段合并',function(){var next=data.package.nodes[i+1];if(!next||next.kind==='image')throw Error('下一项不能合并');n.text+='\n'+next.text;next.status='ignored';n.status='pending';paintEditor()}));root.appendChild(card);
 });
}
function save(approve){return api('/teacher/weekend/lessons/'+lid+'/writing',{method:'PUT',json:{expectedRevision:data.revision,nodes:data.package.nodes,title:data.package.title||'',approve:approve}}).then(function(d){data=d;paintEditor();message(approve?'审核通过，后续课堂将冻结此版本':'草稿已保存')})}
function loadClass(){return api('/weekend/writing/sessions/'+sid).then(function(d){data=d;paintClass()})}
function paintClass(){
 root.textContent='';noteBox=el('p',{role:'status'});root.appendChild(el('h1',{text:data.title||'作文课'}));root.appendChild(noteBox);
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

