"""Reviewed courseware templates (ES5, DOM only: parameters are rendered with textContent/SVG attributes, never as markup)."""

COURSEWARE_JS = r"""
var CW_SVG='http://www.w3.org/2000/svg',CW_LETTERS='ABCDEF';
function cwSplit(text){return (String(text||'').match(/[^。！？；!?;\n]+[。！？；!?;]?[”」』]?/g)||[]).map(function(s){return s.trim()}).filter(Boolean)}
function cwRotate(p,c,dir,angle){var x=p[0]-c[0],y=p[1]-c[1],t=(angle/90)%4;if(dir==='ccw')t=(4-t)%4;for(var i=0;i<t;i++){var nx=y;y=-x;x=nx}return [c[0]+x,c[1]+y]}
function cwNode(tag,attrs,text){var n=document.createElementNS(CW_SVG,tag);Object.keys(attrs).forEach(function(k){n.setAttribute(k,attrs[k])});if(text!=null)n.textContent=text;return n}
function cwRotation(box,p,view,big){
  var cell=40,pad=24,W=p.width*cell+pad*2,H=p.height*cell+pad*2,on=-1;
  p.shape.forEach(function(q,k){if(q[0]===p.center[0]&&q[1]===p.center[1])on=k});
  var centerName=on>=0?CW_LETTERS[on]:'O';
  function X(x){return pad+x*cell}function Y(y){return pad+(p.height-y)*cell}
  var wrap=el('div',{style:'background:#fff;color:#111;border-radius:12px;padding:8px'});box.appendChild(wrap);
  wrap.appendChild(el('b',{style:big?'font-size:3vh':'',text:p.title+'：绕点 '+centerName+' '+(p.direction==='cw'?'顺时针':'逆时针')+'旋转 '+p.angle+'°'}));
  if(!document.createElementNS||!cwNode('svg',{}).createSVGRect){
    wrap.appendChild(el('p',{text:'原图顶点：'+p.shape.map(function(q,i){return CW_LETTERS[i]+'('+q[0]+','+q[1]+')'}).join('、')+'；旋转中心 '+centerName+'('+p.center[0]+','+p.center[1]+')'}));
    if(view.showResult)wrap.appendChild(el('p',{text:'旋转后：'+p.rotated.map(function(q,i){return CW_LETTERS[i]+'′('+q[0]+','+q[1]+')'}).join('、')}));
    return;
  }
  var svg=cwNode('svg',{viewBox:'0 0 '+W+' '+H,width:'100%',style:'display:block;max-height:'+(big?'50vh':'420px'),role:'img','aria-label':p.title});
  for(var i=0;i<=p.width;i++)svg.appendChild(cwNode('line',{x1:X(i),y1:Y(0),x2:X(i),y2:Y(p.height),stroke:'#d0d5dd','stroke-width':1}));
  for(var j=0;j<=p.height;j++)svg.appendChild(cwNode('line',{x1:X(0),y1:Y(j),x2:X(p.width),y2:Y(j),stroke:'#d0d5dd','stroke-width':1}));
  function poly(points,color,dash,suffix,transform){
    var g=cwNode('g',transform?{transform:transform}:{});
    g.appendChild(cwNode('polygon',{points:points.map(function(q){return X(q[0])+','+Y(q[1])}).join(' '),fill:color,'fill-opacity':0.18,stroke:color,'stroke-width':3,'stroke-dasharray':dash||''}));
    points.forEach(function(q,k){g.appendChild(cwNode('text',{x:X(q[0])+6,y:Y(q[1])-6,'font-size':18,'font-weight':700,fill:color},CW_LETTERS[k]+suffix))});
    svg.appendChild(g);
  }
  if(view.showOriginal!==false)poly(p.shape,'#1d4ed8','','');
  if(view.angle>0&&!(view.showResult&&view.angle>=p.angle))poly(p.shape,'#f97316','6 4','',
    'rotate('+((p.direction==='cw'?1:-1)*view.angle)+' '+X(p.center[0])+' '+Y(p.center[1])+')');
  if(view.showResult)poly(p.rotated,'#dc2626','','′');
  if(view.showCenter!==false){svg.appendChild(cwNode('circle',{cx:X(p.center[0]),cy:Y(p.center[1]),r:6,fill:'#111'}));if(on<0)svg.appendChild(cwNode('text',{x:X(p.center[0])-22,y:Y(p.center[1])+22,'font-size':18,'font-weight':700,fill:'#111'},'O'))}
  wrap.appendChild(svg);
  var steps=el('ol',{style:big?'font-size:2.6vh':''});p.steps.forEach(function(s,k){steps.appendChild(el('li',{style:k<(view.step||0)?'font-weight:700;color:#b42318':'opacity:.7',text:s}))});wrap.appendChild(steps);
  wrap.appendChild(el('div',{style:'opacity:.8',text:'当前旋转 '+(view.angle||0)+'° / '+p.angle+'°'}));
}
function cwReading(box,p,view,big,teacher,onTap){
  var wrap=el('div',{style:'background:#fff;color:#111;border-radius:12px;padding:12px;line-height:1.8;'+(big?'font-size:2.8vh':'')});box.appendChild(wrap);
  wrap.appendChild(el('b',{text:p.title}));
  var text=el('div',{style:'margin:8px 0'});
  p.sentences.forEach(function(s,i){
    var on=(view.highlight||[]).indexOf(i)>=0,ev=teacher&&(p.evidence||[]).indexOf(i)>=0;
    var n=el(onTap?'button':'span',{type:onTap?'button':null,style:'display:inline;border:0;padding:2px 1px;margin:0;font:inherit;line-height:inherit;cursor:'+(onTap?'pointer':'default')+';background:'+(on?'#fde68a':'transparent')+';border-bottom:'+(ev?'3px solid #16a34a':'0')+';color:inherit',text:s});
    if(onTap)n.addEventListener('click',function(){onTap(i)});text.appendChild(n);
  });
  wrap.appendChild(text);
  if(teacher)wrap.appendChild(el('div',{class:'muted',text:'绿色下划线＝教师认定的文本依据（仅老师可见，不上大屏）'}));
  wrap.appendChild(el('p',{style:'font-weight:700',text:'问题：'+p.question}));
  if(p.material&&(view.showMaterial||teacher))wrap.appendChild(el('p',{style:'background:#f2f4f7;padding:8px;border-radius:8px',text:'补充资料：'+p.material}));
  if(view.showPrompt||teacher)wrap.appendChild(el('p',{text:'书面解释：'+p.writingPrompt}));
}
function cwRender(box,c,view,big,teacher,onTap){box.textContent='';if(c.kind==='rotation')cwRotation(box,c.params,view||{},big);else cwReading(box,c.params,view||{},big,teacher,onTap)}
function cwControl(box,c,sid){
  var view=JSON.parse(JSON.stringify(c.view||{})),stage=el('div'),bar=el('div',{class:'row'}),msg=el('div',{role:'status'});
  box.textContent='';box.appendChild(el('h2',{text:'互动课件：'+c.kindLabel+'（大屏同步，约3秒）'}));box.appendChild(bar);box.appendChild(stage);box.appendChild(msg);
  function send(){api('/teacher/weekend/sessions/'+sid+'/courseware/view',{json:{view:view}}).then(function(r){view=r.view;draw()}).catch(function(e){msg.textContent=e.message})}
  function draw(){cwRender(stage,c,view,false,false,c.kind==='reading'?function(i){var k=view.highlight.indexOf(i);if(k>=0)view.highlight.splice(k,1);else view.highlight.push(i);draw();send()}:null)}
  function button(text,fn){bar.appendChild(el('button',{text:text,style:'min-height:44px;min-width:44px',onclick:function(){fn();draw();send()}}))}
  if(c.kind==='rotation'){
    var p=c.params,range=el('input',{type:'range',min:0,max:p.angle,step:15,value:view.angle||0,style:'width:220px;min-height:44px','aria-label':'旋转角度'});
    range.addEventListener('input',function(){view.angle=+range.value;draw()});range.addEventListener('change',function(){view.angle=+range.value;send()});
    button('−15°',function(){view.angle=Math.max(0,(view.angle||0)-15);range.value=view.angle});
    bar.appendChild(range);
    button('+15°',function(){view.angle=Math.min(p.angle,(view.angle||0)+15);range.value=view.angle});
    button('显示/隐藏结果',function(){view.showResult=!view.showResult});
    button('显示/隐藏原图',function(){view.showOriginal=view.showOriginal===false});
    button('显示/隐藏中心',function(){view.showCenter=view.showCenter===false});
    button('下一步讲解',function(){view.step=Math.min(p.steps.length,(view.step||0)+1)});
    button('重来',function(){view.angle=0;view.step=0;view.showResult=false;range.value=0});
  }else{
    bar.appendChild(el('span',{class:'muted',text:'点句子＝在大屏上高亮为同学们找到的依据'}));
    button('显示/隐藏补充资料',function(){view.showMaterial=!view.showMaterial});
    button('显示/隐藏书面解释要求',function(){view.showPrompt=!view.showPrompt});
    button('清除高亮',function(){view.highlight=[]});
  }
  draw();
}
function cwPlan(box,lessonId,refresh){
  var msg=el('div',{role:'status','aria-live':'polite'});
  function load(){box.textContent='';api('/teacher/weekend/lessons/'+lessonId+'/courseware').then(paint).catch(function(e){box.appendChild(el('div',{class:'notice error',text:e.message}))})}
  function paint(d){
    box.textContent='';msg.textContent='';
    box.appendChild(el('p',{class:'muted',text:'试点：'+d.kindLabel+'。由 AI 按固定模板填写参数，你预览、修改、审核后才会用于课堂；上课翻页和拖动不调用 AI。审核后会同时生成一道学生书面作答题（文字／拍照提交，老师批改，按逐题公布规则公布）。'}));
    var stageSel=el('select');['到课与热身','知识点介绍','例题讲解','随堂练习','练习复盘','课堂互动','布置课后'].forEach(function(x,i){stageSel.appendChild(el('option',{value:i+1,text:'放在第'+(i+1)+'环节：'+x}))});
    stageSel.value=String(d.item?d.item.stageNo:3);
    var pageSel=el('select',{'aria-label':'课件对应的页'}),pageHint=el('div',{class:'muted'});
    function fillPages(){
      var pages=(d.pages||{})[stageSel.value]||[],want=d.item&&String(d.item.stageNo)===stageSel.value&&d.item.params.page!=null?d.item.params.page:0;
      pageSel.textContent='';pages.forEach(function(x,i){pageSel.appendChild(el('option',{value:i,text:'第'+(i+1)+'页：'+x}))});
      pageSel.hidden=!pages.length;if(pages.length)pageSel.value=String(Math.min(want,pages.length-1));
      pageHint.textContent=pages.length?'课件只在大屏翻到这一页时出现，并按这一页的例题生成；其他页照常显示原内容。':'这个环节没有分页，课件在整个环节显示。';
    }
    function pageValue(){return pageSel.hidden?null:+pageSel.value}
    stageSel.addEventListener('change',fillPages);fillPages();
    var gen=el('button',{class:'primary',text:d.item?'重新生成互动课件':'生成互动课件',disabled:d.kind==='reading'&&!d.hasSource,onclick:function(){
      if(d.item&&!confirm('重新生成会替换当前草稿（已审核的版本在重新审核前仍用于课堂）。确定吗？'))return;
      gen.disabled=true;msg.textContent='AI 正在按模板生成，约半分钟…';
      api('/teacher/weekend/lessons/'+lessonId+'/courseware/generate',{json:{stageNo:+stageSel.value,page:pageValue()}}).then(paint).catch(function(e){msg.textContent=e.message;gen.disabled=false});
    }});
    box.appendChild(el('div',{class:'row'},stageSel,pageSel,gen));box.appendChild(pageHint);
    if(d.kind==='reading'&&!d.hasSource)box.appendChild(el('div',{class:'notice warn',text:'这节课没有阅读原文，请先导入教案。'}));
    box.appendChild(msg);
    var it=d.item||{kind:d.kind,stageNo:3,status:'none',params:d.kind==='rotation'?{title:'图形的旋转',width:10,height:10,shape:[[2,2],[5,2],[2,4]],center:[2,2],direction:'cw',angle:90,steps:[],question:'',reference:''}:{title:'找文本依据',passage:'',question:'',evidence:[],material:'',writingPrompt:'',reference:''}};
    if(d.item)box.appendChild(el('div',{class:'row'},el('span',{class:'tag '+(it.status==='approved'?'ok':'warn'),text:it.status==='approved'?'已审核，课堂可用':'草稿，审核前不会上课堂、不会发给学生'}),el('span',{class:'muted',text:'更新于 '+it.updatedAt+(it.hasApproved&&it.status!=='approved'?' · 课堂仍使用上次审核的版本':'')})));
    var form=el('div'),preview=el('div',{class:'card'}),p=JSON.parse(JSON.stringify(it.params)),fields={};
    function field(key,label,node){fields[key]=node;form.appendChild(el('label',{class:'field'},el('span',{text:label}),node));return node}
    function input(v){var n=el('input',{type:'text'});n.value=v==null?'':String(v);return n}
    function area(v){var n=el('textarea');n.value=v||'';return n}
    if(it.kind==='rotation'){
      field('title','标题',input(p.title));field('width','网格宽（6—12）',input(p.width));field('height','网格高（6—12）',input(p.height));
      field('shape','原图顶点（如 2,2; 5,2; 2,4）',input(p.shape.map(function(q){return q.join(',')}).join('; ')));
      field('center','旋转中心（如 2,2）',input(p.center.join(',')));
      var dir=el('select');[['cw','顺时针'],['ccw','逆时针']].forEach(function(x){dir.appendChild(el('option',{value:x[0],text:x[1]}))});dir.value=p.direction;field('direction','方向',dir);
      var ang=el('select');[90,180,270].forEach(function(x){ang.appendChild(el('option',{value:x,text:x+'°'}))});ang.value=String(p.angle);field('angle','角度',ang);
      field('steps','讲解步骤（每行一步）',area((p.steps||[]).join('\n')));field('question','学生书面作答问题',area(p.question));field('reference','评分要点（仅老师可见）',area(p.reference));
    }else{
      field('title','标题',input(p.title));field('passage','阅读材料（必须是原文中的连续段落）',area(p.passage));field('question','阅读问题',area(p.question));
      field('material','补充资料（请核实）',area(p.material));field('writingPrompt','书面解释要求',area(p.writingPrompt));field('reference','评分要点（仅老师可见）',area(p.reference));
    }
    function collect(){
      if(it.kind==='rotation'){
        function pt(s){var a=String(s).split(/[,，]/).map(function(x){return Number(x.trim())});return a}
        return {title:fields.title.value,width:+fields.width.value,height:+fields.height.value,shape:fields.shape.value.split(/[;；]/).filter(function(x){return x.trim()}).map(pt),
          center:pt(fields.center.value),direction:fields.direction.value,angle:+fields.angle.value,steps:fields.steps.value.split('\n').filter(function(x){return x.trim()}),question:fields.question.value,reference:fields.reference.value};
      }
      var s=cwSplit(fields.passage.value);p.evidence=(p.evidence||[]).filter(function(i){return i<s.length});
      return {title:fields.title.value,passage:fields.passage.value,sentences:s,question:fields.question.value,evidence:p.evidence,material:fields.material.value,writingPrompt:fields.writingPrompt.value,reference:fields.reference.value};
    }
    function show(){
      var v=collect();preview.textContent='';preview.appendChild(el('b',{text:'预览（教师视角）'}));
      if(it.kind==='rotation'){var ok=v.shape.length>=3&&v.shape.every(function(q){return q.length===2&&isFinite(q[0])&&isFinite(q[1])})&&v.center.length===2;
        if(!ok){preview.appendChild(el('div',{class:'notice warn',text:'坐标格式不完整'}));return}
        v.rotated=v.shape.map(function(q){return cwRotate(q,v.center,v.direction,v.angle)});
        cwRender(preview,{kind:'rotation',params:v},{angle:v.angle,showResult:true,showCenter:true,step:v.steps.length},false,true);
      }else cwRender(preview,{kind:'reading',params:v},{showMaterial:true,showPrompt:true},false,true,function(i){var k=p.evidence.indexOf(i);if(k>=0)p.evidence.splice(k,1);else p.evidence.push(i);show()});
      if(it.kind==='reading')preview.insertBefore(el('div',{class:'muted',text:'点句子标记／取消“文本依据”。'}),preview.children[1]||null);
    }
    Object.keys(fields).forEach(function(k){fields[k].addEventListener('input',show);fields[k].addEventListener('change',show)});
    box.appendChild(form);box.appendChild(preview);show();
    var save=el('button',{text:'保存修改（需重新审核）',onclick:function(){msg.textContent='正在保存…';api('/teacher/weekend/lessons/'+lessonId+'/courseware',{method:'PUT',json:{stageNo:+stageSel.value,page:pageValue(),params:collect()}}).then(paint).catch(function(e){msg.textContent=e.message})}});
    var ok=el('button',{class:'primary',text:'审核通过，用于课堂',disabled:!d.item||it.status==='approved',onclick:function(){
      if(!confirm('确认课件内容和答案都已核对？审核后本课新开的课堂会在所选环节显示，并为学生生成一道书面作答题。'))return;
      api('/teacher/weekend/lessons/'+lessonId+'/courseware/approve',{json:{}}).then(function(n){paint(n);if(refresh)refresh()}).catch(function(e){msg.textContent=e.message});
    }});
    box.appendChild(el('div',{class:'row'},save,ok));
    if(d.item&&d.item.writtenTask)box.appendChild(el('details',{},el('summary',{text:'审核后生成的学生书面作答题'}),el('pre',{style:'white-space:pre-wrap;font:inherit',text:d.item.writtenTask.stem}),el('pre',{style:'white-space:pre-wrap;font:inherit;color:#667085',text:'参考答案（仅老师可见）：'+d.item.writtenTask.reference})));
  }
  load();
}
"""
