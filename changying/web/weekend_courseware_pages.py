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
var CW_SHAPES={rectangle:'长方形',square:'正方形',triangle:'三角形',parallelogram:'平行四边形',trapezoid:'梯形'};
function cwFigureText(f){
  if(f.type==='segment')return '线段上的点：'+f.points.map(function(q){return q.name}).join(' — ')+(f.marks.length?'；'+f.marks.map(function(m){return m.from+m.to+'＝'+m.label}).join('，'):'');
  if(f.type==='flow')return '程序：'+f.boxes.join(' → ')+(f.branches.length?'；'+f.branches.map(function(b){return b.when+'：'+b.boxes.join(' → ')}).join('；'):'');
  if(f.type==='shape')return CW_SHAPES[f.shape]+'：'+Object.keys(f.labels).map(function(k){return f.labels[k]}).join('，');
  if(f.type==='calendar_cross')return '\u6708\u5386\u5341\u5b57\u6846\uff1a\u4e2d\u5fc3 '+f.center+'\uff0c\u4e94\u6570\u548c '+f.total;
  if(f.type==='seating_pattern')return '\u65b9\u684c\u4eba\u6570\u89c4\u5f8b\uff1a'+f.sampleCounts.join('\u3001');
  if(f.type==='alternating_triangle')return '\u9ed1\u767d\u68cb\u5b50\u4e09\u89d2\u5f62\uff1a'+f.rows+'\u5c42\uff0c\u5dee\u503c '+f.differenceSymbol;
  if(f.type==='running_track')return '\u540c\u5411\u73af\u5f62\u8dd1\u9053\uff1a'+f.fastSpeed+'\u7c73/\u5206\u949f\u548c '+f.slowSpeed+'\u7c73/\u5206\u949f\uff0c\u8dd1\u9053\u5468\u957f '+f.distanceSymbol;
  return f.rows.map(function(r){return r.join(' | ')}).join('\n');
}
function cwFigureOk(f){
  if(f.type==='uploaded_image')return /^data:image\/jpeg;base64,/.test(String(f.data_url||''));
  if(f.type==='segment'){var at=(f.points||[]).map(function(q){return q.at});return at.length>=2&&at.every(function(a){return isFinite(a)})&&Math.max.apply(null,at)>Math.min.apply(null,at)}
  if(f.type==='flow')return (f.boxes||[]).length>0||(f.branches||[]).length>0;
  if(f.type==='shape')return !!CW_SHAPES[f.shape];
  if(f.type==='calendar_cross')return isFinite(f.center)&&isFinite(f.daysInMonth)&&isFinite(f.firstWeekday)&&isFinite(f.total)&&f.center===f.total/5;
  if(f.type==='seating_pattern')return (f.sampleCounts||[]).length>=2&&f.sampleCounts.length<=4&&f.sampleCounts[0]===8&&f.sampleCounts.every(function(n,i){return isFinite(n)&&n===8+i*4});
  if(f.type==='alternating_triangle')return f.rows>=4&&f.rows<=8&&f.rows%2===0&&/^[A-Za-z]$/.test(f.differenceSymbol||'');
  if(f.type==='running_track')return f.fastSpeed>f.slowSpeed&&f.slowSpeed>0&&/^[A-Za-z]$/.test(f.distanceSymbol||'');
  return (f.rows||[]).length>0;
}
function cwCalendarCross(box,f,view,big,teacher){
  var step=teacher&&!view.previewMode?4:(view.step||0),wrap=el('div',{style:'max-width:560px;margin:8px auto;padding:12px;border:1px solid #d0d5dd;border-radius:12px;background:#fff'});
  box.appendChild(wrap);wrap.appendChild(el('div',{style:'text-align:center;font-weight:700;margin-bottom:8px',text:'\u6708\u5386\u793a\u610f\uff1a\u5de6\u53f3\u76f8\u5dee 1\uff0c\u4e0a\u4e0b\u76f8\u5dee 7'}));
  var grid=el('div',{style:'display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:4px'}),names=['\u65e5','\u4e00','\u4e8c','\u4e09','\u56db','\u4e94','\u516d'];
  names.forEach(function(n){grid.appendChild(el('div',{style:'text-align:center;color:#667085;font-size:12px;padding:4px 0',text:n}))});
  var count=f.firstWeekday+f.daysInMonth;for(var i=0;i<Math.ceil(count/7)*7;i++){
    var day=i-f.firstWeekday+1;if(day<1||day>f.daysInMonth){grid.appendChild(el('div',{style:'aspect-ratio:1'}));continue}
    var diff=day-f.center,active=day===f.center||(step>=1&&Math.abs(diff)===1)||(step>=2&&Math.abs(diff)===7),center=day===f.center;
    var label='';if(step>=3&&active)label=center?'a':diff===-7?'a-7':diff===-1?'a-1':diff===1?'a+1':'a+7';
    var style='aspect-ratio:1;min-height:32px;display:flex;flex-direction:column;align-items:center;justify-content:center;border-radius:8px;font-weight:700;font-size:'+(big?'2.5vh':'14px')+';background:'+(active?(center?'#f5b942':'#2364e8'):'#f2f4f7')+';color:'+(active?(center?'#412b00':'#fff'):'#475467')+';border:'+(active?'2px solid '+(center?'#d49413':'#2364e8'):'2px solid transparent');
    grid.appendChild(el('div',{style:style},el('span',{text:String(day)}),label?el('small',{style:'font-size:10px;line-height:1.1',text:label}):null));
  }
  wrap.appendChild(grid);
  if(step>=3)wrap.appendChild(el('div',{style:'margin-top:12px;text-align:center;font-weight:700;color:#17449b;font-size:'+(big?'2.4vh':'16px'),text:'\u4e94\u6570\u548c = (a-7)+(a-1)+a+(a+1)+(a+7) = 5a'}));
  if(view.showAnswer||teacher){var a=f.total/5;wrap.appendChild(el('div',{style:'margin-top:8px;text-align:center;color:#b42318;font-weight:700',text:'5a='+f.total+'\uff0ca='+a+'\uff1b\u6700\u5c0f\u6570 '+(a-7)+'\uff0c\u6700\u5927\u6570 '+(a+7)}))}
}
function cwSeatingPattern(box,f,view,big,teacher,stepCount){
  var step=teacher&&!view.previewMode?(stepCount||99):(view.step||0),shown=Math.max(1,Math.min(f.sampleCounts.length,Math.ceil(Math.max(1,step)*f.sampleCounts.length/Math.max(1,(stepCount||f.sampleCounts.length+1)-1))));
  var wrap=el('div',{style:'max-width:760px;margin:10px auto;padding:12px;border:1px solid #d0d5dd;border-radius:12px;background:#fff'});
  box.appendChild(wrap);
  var svg=cwNode('svg',{viewBox:'0 0 720 210',width:'100%',style:'display:block;max-height:'+(big?'38vh':'300px'),role:'img','aria-label':cwFigureText(f)});
  for(var i=0;i<shown;i++){
    var n=i+1,panel=180,x0=i*180,unit=22,w=n*unit,x=x0+(180-w)/2,y=76,h=42,color=i===shown-1?'#2563eb':'#667085';
    svg.appendChild(cwNode('rect',{x:x0+5,y:12,width:170,height:188,rx:10,fill:i===shown-1?'#eff6ff':'#fff',stroke:i===shown-1?'#2563eb':'#d0d5dd','stroke-width':i===shown-1?2:1}));
    svg.appendChild(cwNode('text',{x:x0+90,y:36,'text-anchor':'middle','font-size':17,'font-weight':700,fill:'#111'},n+' \u5f20\u684c'));
    for(var j=0;j<n;j++){
      svg.appendChild(cwNode('rect',{x:x+j*unit,y:y,width:unit,height:h,fill:'#fef3c7',stroke:'#344054','stroke-width':2}));
      for(var k=0;k<2;k++){
        var sx=x+j*unit+unit*(k+1)/3;
        svg.appendChild(cwNode('circle',{cx:sx,cy:y-10,r:4,fill:color,stroke:'#fff','stroke-width':1}));
        svg.appendChild(cwNode('circle',{cx:sx,cy:y+h+10,r:4,fill:color,stroke:'#fff','stroke-width':1}));
      }
    }
    for(var q=0;q<2;q++){
      svg.appendChild(cwNode('circle',{cx:x-10,cy:y+12+q*18,r:4,fill:color,stroke:'#fff','stroke-width':1}));
      svg.appendChild(cwNode('circle',{cx:x+w+10,cy:y+12+q*18,r:4,fill:color,stroke:'#fff','stroke-width':1}));
    }
    svg.appendChild(cwNode('text',{x:x0+90,y:157,'text-anchor':'middle','font-size':18,'font-weight':700,fill:color},f.sampleCounts[i]+' \u4eba'));
  }
  wrap.appendChild(svg);
  if(step>=stepCount)wrap.appendChild(el('div',{style:'text-align:center;font-weight:700;color:#17449b;font-size:'+(big?'2.4vh':'16px'),text:'1\u5f20\u684c8\u4eba\uff0c\u6bcf\u52a0\u4e00\u5f20\u591a4\u4eba\uff1a8+4(m-1)=4m+4'}));
}
function cwAlternatingTriangle(box,f,view,big,teacher,stepCount){
  var step=teacher&&!view.previewMode?(stepCount||99):(view.step||0),shown=Math.max(1,Math.min(f.rows,Math.ceil(Math.max(1,step)*f.rows/Math.max(1,stepCount||f.rows))));
  var wrap=el('div',{style:'max-width:620px;margin:10px auto;padding:12px;border:1px solid #d0d5dd;border-radius:12px;background:#fff;text-align:center'});
  box.appendChild(wrap);
  var size=31,svg=cwNode('svg',{viewBox:'0 0 420 310',width:'100%',style:'display:block;max-height:'+(big?'42vh':'320px'),role:'img','aria-label':cwFigureText(f)});
  for(var row=0;row<shown;row++){
    var count=row+1,y=32+row*size,start=210-(count*size)/2,black=row%2===1;
    for(var col=0;col<count;col++){
      var cx=start+col*size+size/2,cy=y+size/2;
      svg.appendChild(cwNode('circle',{cx:cx,cy:cy,r:10,fill:black?'#111827':'#fff',stroke:black?'#111827':'#667085','stroke-width':2}));
    }
    svg.appendChild(cwNode('text',{x:start+count*size+12,y:y+size/2+5,'font-size':14,fill:black?'#111827':'#475467'},black?'\u9ed1 '+count:'\u767d '+count));
  }
  wrap.appendChild(svg);
  wrap.appendChild(el('div',{style:'font-size:14px;color:#475467',text:'\u6bcf\u5c42\u9ed1\u767d\u4ea4\u66ff\uff1b\u4ece\u9876\u5c42\u767d\u68cb\u5f00\u59cb'}));
  if(step>=stepCount)wrap.appendChild(el('div',{style:'margin-top:10px;font-weight:700;color:#17449b;font-size:'+(big?'2.3vh':'16px'),text:'\u767d\uff1a1+3+\u22ef+(2k-1)=k\u00b2\uff1b\u9ed1\uff1a2+4+\u22ef+2k=k(k+1)\uff1b\u9ed1\u6bd4\u767d\u591a k='+f.differenceSymbol+'\uff0c\u6240\u4ee5\u603b\u5c42\u6570=2'+f.differenceSymbol}));
}
function cwRunningTrack(box,f,view,big,teacher,stepCount){
  var step=teacher&&!view.previewMode?(stepCount||99):Math.max(1,view.step||0),max=Math.max(4,stepCount||4),shown=Math.min(max,step),gap=(f.fastSpeed-f.slowSpeed)*shown;
  var wrap=el('div',{style:'max-width:720px;margin:10px auto;padding:12px;border:1px solid #d0d5dd;border-radius:12px;background:#fff;text-align:center'});
  var svg=cwNode('svg',{viewBox:'0 0 680 300',width:'100%',style:'display:block;max-height:'+(big?'40vh':'320px'),role:'img','aria-label':cwFigureText(f)});
  svg.appendChild(cwNode('ellipse',{cx:340,cy:145,rx:245,ry:92,fill:'none',stroke:'#98a2b3','stroke-width':24}));
  svg.appendChild(cwNode('ellipse',{cx:340,cy:145,rx:245,ry:92,fill:'none',stroke:'#fff','stroke-width':2,'stroke-dasharray':'8 8'}));
  svg.appendChild(cwNode('path',{d:'M520 83 L548 90 L527 108',fill:'none',stroke:'#2563eb','stroke-width':5,'stroke-linecap':'round','stroke-linejoin':'round'}));
  svg.appendChild(cwNode('text',{x:340,y:137,'text-anchor':'middle','font-size':23,'font-weight':700,fill:'#344054'},'\u591a\u8dd1\u4e00\u5708 = '+f.distanceSymbol+' \u7c73'));
  svg.appendChild(cwNode('text',{x:340,y:169,'text-anchor':'middle','font-size':17,fill:'#475467'},'\u540c\u4e00\u5730\u70b9\u51fa\u53d1\uff0c\u540c\u65b9\u5411\u8ffd\u53ca\uff08\u56fe\u793a\u975e\u6309\u6bd4\u4f8b\uff09'));
  var angleFast=(-90+shown*19)*Math.PI/180,angleSlow=(-90+shown*19*(f.slowSpeed/f.fastSpeed))*Math.PI/180;
  function runner(a,color,label,speed){var x=340+245*Math.cos(a),y=145+92*Math.sin(a);svg.appendChild(cwNode('circle',{cx:x,cy:y,r:16,fill:color,stroke:'#fff','stroke-width':3}));svg.appendChild(cwNode('text',{x:x,y:y+5,'text-anchor':'middle','font-size':14,'font-weight':700,fill:'#fff'},label));svg.appendChild(cwNode('text',{x:x,y:y+34,'text-anchor':'middle','font-size':15,'font-weight':700,fill:color},speed+'\u7c73/\u5206'))}
  runner(angleFast,'#dc2626','\u5feb',f.fastSpeed);runner(angleSlow,'#2563eb','\u6162',f.slowSpeed);
  wrap.appendChild(svg);
  wrap.appendChild(el('div',{style:'font-weight:700;color:#17449b;font-size:'+(big?'2.3vh':'16px'),text:'\u7b2c '+shown+' \u5206\u949f\uff1a\u5feb\u8005\u591a\u8dd1 '+gap+' \u7c73\uff1b\u6bcf\u5206\u949f\u8def\u7a0b\u5dee '+f.fastSpeed+' - '+f.slowSpeed+' = '+(f.fastSpeed-f.slowSpeed)+' \u7c73'}));
  if(step>=stepCount)wrap.appendChild(el('div',{style:'margin-top:8px;color:#b42318;font-weight:700',text:'\u8def\u7a0b\u5dee\u8fbe\u5230\u4e00\u5708 '+f.distanceSymbol+' \u7c73\u65f6\u8ffd\u4e0a\uff1a'+f.distanceSymbol+' \u00f7 ('+f.fastSpeed+' - '+f.slowSpeed+') = '+f.distanceSymbol+' / '+(f.fastSpeed-f.slowSpeed)+' \u5206\u949f'}));
}
function cwFigure(wrap,f,big,view,teacher,stepCount){
  view=view||{};
  if(!f||!f.type)return;
  var box=el('div',{style:'margin:8px 0'});wrap.appendChild(box);
  if(!cwFigureOk(f)){box.appendChild(el('div',{class:'notice warn',text:'图示还没填完整'}));return}
  if(f.type==='uploaded_image'){
    box.appendChild(el('img',{src:f.data_url,alt:f.alt||'原卷插图',style:'display:block;max-width:100%;max-height:'+(big?'40vh':'300px')+';object-fit:contain;margin:0 auto;border:1px solid #e5e8f0;border-radius:8px'}));
    return;
  }
  if(f.type==='calendar_cross'){cwCalendarCross(box,f,view,big,teacher);return}
  if(f.type==='seating_pattern'){cwSeatingPattern(box,f,view,big,teacher,stepCount);return}
  if(f.type==='alternating_triangle'){cwAlternatingTriangle(box,f,view,big,teacher,stepCount);return}
  if(f.type==='running_track'){cwRunningTrack(box,f,view,big,teacher,stepCount);return}
  f={type:f.type,points:(f.points||[]).slice().sort(function(a,b){return a.at-b.at}),marks:(f.marks||[]).filter(function(m){return m.from&&m.to}),
    boxes:f.boxes||[],branches:f.branches||[],shape:f.shape,labels:f.labels||{},rows:f.rows||[]};
  var visualStep=teacher&&!view.previewMode?(stepCount||1):(view.step||0),visualSteps=Math.max(1,stepCount||1);
  if(f.type==='table'){
    var t=el('table',{style:'border-collapse:collapse;margin:0 auto;'+(big?'font-size:3vh':'')});
    var step=teacher&&!view.previewMode?Math.max(1,stepCount||f.rows[0].length-1):(view.step||0);
    var columns=Math.max(1,Math.min(f.rows[0].length-1,Math.ceil((step/Math.max(1,stepCount||f.rows[0].length-1))*(f.rows[0].length-1))));
    f.rows.forEach(function(r,i){var tr=el('tr');r.forEach(function(c,j){var shown=i===0||j===0||j<=columns;tr.appendChild(el(i?'td':'th',{style:'border:1px solid #98a2b3;padding:4px 12px;text-align:center;background:'+(j===columns&&i>0?'#dbeafe':'#fff')+';color:'+(shown?'#111':'#98a2b3'),text:shown?c:'·'}))});t.appendChild(tr)});
    box.appendChild(t);return;
  }
  if(!document.createElementNS||!cwNode('svg',{}).createSVGRect){box.appendChild(el('p',{style:'white-space:pre-wrap',text:cwFigureText(f)}));return}
  var W=600,H=f.type==='flow'?(f.branches.length?260:120):f.type==='shape'?300:120+f.marks.length*34,svg=cwNode('svg',{viewBox:'0 0 '+W+' '+H,width:'100%',style:'display:block;max-height:'+(big?'40vh':'300px'),role:'img','aria-label':cwFigureText(f)});
  function txt(x,y,t,size,anchor,color){svg.appendChild(cwNode('text',{x:x,y:y,'font-size':size||22,'text-anchor':anchor||'middle','font-weight':700,fill:color||'#111'},t))}
  if(f.type==='segment'){
    var lo=f.points[0].at,hi=f.points[f.points.length-1].at,X=function(a){return 40+(a-lo)/(hi-lo)*(W-80)},at={};
    f.points.forEach(function(q){at[q.name]=X(q.at)});
    svg.appendChild(cwNode('line',{x1:X(lo),y1:90,x2:X(hi),y2:90,stroke:'#1d2939','stroke-width':4}));
    f.points.forEach(function(q){svg.appendChild(cwNode('line',{x1:at[q.name],y1:80,x2:at[q.name],y2:100,stroke:'#1d2939','stroke-width':3}));txt(at[q.name],70,q.name,24)});
    f.marks.filter(function(m){return at[m.from]!=null&&at[m.to]!=null}).forEach(function(m,k){if(k>=Math.ceil(visualStep/visualSteps*f.marks.length))return;var a=Math.min(at[m.from],at[m.to]),b=Math.max(at[m.from],at[m.to]),y=115+k*34;
      svg.appendChild(cwNode('path',{d:'M'+a+' '+(y-6)+' L'+a+' '+y+' L'+b+' '+y+' L'+b+' '+(y-6),fill:'none',stroke:'#2563eb','stroke-width':2}));
      txt((a+b)/2,y+16,m.label,18,'middle','#2563eb')});
  }else if(f.type==='flow'){
    function row(items,y,x0){var n=items.length,w=Math.min(120,(W-x0-20)/n-24),x=x0,active=Math.min(n-1,Math.max(0,Math.floor(Math.max(0,visualStep-1)*n/visualSteps)));
      items.forEach(function(t,i){var fill=i===active?'#fef3c7':i<active?'#dcfce7':'#eff6ff';svg.appendChild(cwNode('rect',{x:x,y:y-24,width:w,height:48,rx:8,fill:fill,stroke:i===active?'#d97706':'#1d4ed8','stroke-width':i===active?3:2}));txt(x+w/2,y+7,t,w<90?15:18);
        if(i<n-1){svg.appendChild(cwNode('line',{x1:x+w+2,y1:y,x2:x+w+20,y2:y,stroke:'#1d2939','stroke-width':2}));svg.appendChild(cwNode('path',{d:'M'+(x+w+20)+' '+(y-5)+' L'+(x+w+26)+' '+y+' L'+(x+w+20)+' '+(y+5)+'Z',fill:'#1d2939'}))}
        x+=w+28});return x}
    if(!f.branches.length)row(f.boxes,60,20);
    else{var end=row(f.boxes,130,20);f.branches.forEach(function(b,k){var y=k?200:60;
      svg.appendChild(cwNode('path',{d:'M'+(end-8)+' 130 L'+(end+10)+' '+y,fill:'none',stroke:'#1d2939','stroke-width':2}));
      txt(end+14,y-30,b.when,16,'start','#b42318');row(b.boxes,y,end+14)})}
  }else{
    var L=f.labels,pts={rectangle:[[150,60],[450,60],[450,240],[150,240]],square:[[200,50],[400,50],[400,250],[200,250]],
      triangle:[[300,50],[480,250],[120,250]],parallelogram:[[200,60],[480,60],[400,240],[120,240]],trapezoid:[[220,60],[380,60],[480,240],[120,240]]}[f.shape];
    svg.appendChild(cwNode('polygon',{points:pts.map(function(q){return q.join(',')}).join(' '),fill:'#eff6ff',stroke:'#1d4ed8','stroke-width':3}));
    var top=pts[0][1],bot=pts[pts.length-1][1];
    var labelOrder=['top','bottom','left','right','height'],visibleLabels=Math.ceil(visualStep/visualSteps*labelOrder.length);
    if(L.top&&visibleLabels>=1)txt(f.shape==='triangle'?300:(pts[0][0]+pts[1][0])/2,top-14,L.top,20);
    if(L.bottom&&visibleLabels>=2)txt(300,bot+30,L.bottom,20);
    if(L.left&&visibleLabels>=3)txt(Math.min(pts[0][0],pts[pts.length-1][0])-12,(top+bot)/2+7,L.left,20,'end');
    if(L.right&&visibleLabels>=4)txt(Math.max.apply(null,pts.map(function(q){return q[0]}))+12,(top+bot)/2+7,L.right,20,'start');
    if(L.height&&visibleLabels>=5){svg.appendChild(cwNode('line',{x1:pts[0][0],y1:top,x2:pts[0][0],y2:bot,stroke:'#b42318','stroke-width':2,'stroke-dasharray':'6 4'}));txt(pts[0][0]+8,(top+bot)/2,L.height,18,'start','#b42318')}
  }
  box.appendChild(svg);
}
function cwSteps(box,p,view,big,teacher){
  var wrap=el('div',{style:'background:#fff;color:#111;border-radius:12px;padding:12px;line-height:1.8;'+(big?'font-size:2.8vh':'')});box.appendChild(wrap);
  wrap.appendChild(el('b',{text:p.title}));
  if(p.sourceProblem)wrap.appendChild(el('p',{style:'white-space:pre-wrap',text:p.sourceProblem}));
  cwFigure(wrap,p.figure,big,view,teacher,p.steps.length);
  if(p.sourceFigure&&p.sourceFigure.type==='uploaded_image')wrap.appendChild(el('details',{style:'margin:10px 0'},el('summary',{text:'\u67e5\u770b\u539f\u9898\u56fe\u7247\uff08\u5bf9\u7167\uff09'}),el('img',{src:p.sourceFigure.data_url,alt:p.sourceFigure.alt||'\u539f\u9898\u56fe\u7247',style:'display:block;max-width:100%;max-height:'+(big?'32vh':'260px')+';object-fit:contain;margin:8px auto;border:1px solid #e5e8f0;border-radius:8px'})));
  var shown=teacher?(view.previewMode?(view.step||0):p.steps.length):(view.step||0),list=el('ol');
  p.steps.forEach(function(s,i){list.appendChild(el('li',{style:i<shown?(i===shown-1?'background:#fff2cc;font-weight:700;border-radius:6px;padding:0 4px':''):'color:#98a2b3',text:i<shown?s:'（第 '+(i+1)+' 步，点“下一步”显示）'}))});
  wrap.appendChild(list);
  if(view.showAnswer||teacher)wrap.appendChild(el('p',{style:'font-weight:700;color:#b42318',text:'答案：'+p.answer}));
}
function cwClock(box,p,view,big){
  var wrap=el('div',{style:'background:#fff;color:#111;border-radius:12px;padding:8px'});box.appendChild(wrap);
  var way=p.direction==='cw'?'顺时针':'逆时针';
  wrap.appendChild(el('b',{style:big?'font-size:3vh':'',text:p.title+'：从 '+p.start+' 出发，'+way+'旋转 '+p.angle+'°'}));
  if(!document.createElementNS||!cwNode('svg',{}).createSVGRect){wrap.appendChild(el('p',{text:view.showResult?'指向数字 '+p.end:'请想一想指针会指向几'}));return}
  var svg=cwNode('svg',{viewBox:'0 0 300 300',width:'100%',style:'display:block;max-height:'+(big?'50vh':'360px'),role:'img','aria-label':p.title});
  svg.appendChild(cwNode('circle',{cx:150,cy:150,r:130,fill:'#fff',stroke:'#344054','stroke-width':4}));
  for(var n=1;n<=12;n++){var a=(n*30-90)*Math.PI/180;svg.appendChild(cwNode('text',{x:150+108*Math.cos(a),y:150+108*Math.sin(a)+8,'text-anchor':'middle','font-size':22,'font-weight':700,fill:'#111'},String(n)))}
  function hand(deg,color,dash){var a=(deg-90)*Math.PI/180;svg.appendChild(cwNode('line',{x1:150,y1:150,x2:150+88*Math.cos(a),y2:150+88*Math.sin(a),stroke:color,'stroke-width':6,'stroke-linecap':'round','stroke-dasharray':dash||''}))}
  var from=p.start*30,sign=p.direction==='cw'?1:-1;
  hand(from,'#1d4ed8');
  if(view.angle>0&&!(view.showResult&&view.angle>=p.angle))hand(from+sign*view.angle,'#f97316','8 6');
  if(view.showResult)hand(p.end*30,'#dc2626');
  svg.appendChild(cwNode('circle',{cx:150,cy:150,r:7,fill:'#111'}));
  wrap.appendChild(svg);
  var steps=el('ol',{style:big?'font-size:2.6vh':''});p.steps.forEach(function(s,k){steps.appendChild(el('li',{style:k<(view.step||0)?'font-weight:700;color:#b42318':'opacity:.7',text:s}))});wrap.appendChild(steps);
  wrap.appendChild(el('div',{style:'opacity:.8',text:'当前转过 '+(view.angle||0)+'° / '+p.angle+'°'+(view.showResult?' · 指向数字 '+p.end:'')}));
}
function cwRender(box,c,view,big,teacher,onTap){box.textContent='';view=view||{};
  if(c.kind==='rotation')cwRotation(box,c.params,view,big);else if(c.kind==='clock')cwClock(box,c.params,view,big);
  else if(c.kind==='steps')cwSteps(box,c.params,view,big,teacher);else cwReading(box,c.params,view,big,teacher,onTap)}
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
  }else if(c.kind==='clock'){
    var q=c.params,dial=el('input',{type:'range',min:0,max:q.angle,step:30,value:view.angle||0,style:'width:220px;min-height:44px','aria-label':'旋转角度'});
    dial.addEventListener('input',function(){view.angle=+dial.value;draw()});dial.addEventListener('change',function(){view.angle=+dial.value;send()});
    button('−30°',function(){view.angle=Math.max(0,(view.angle||0)-30);dial.value=view.angle});
    bar.appendChild(dial);
    button('+30°',function(){view.angle=Math.min(q.angle,(view.angle||0)+30);dial.value=view.angle});
    button('显示/隐藏结果',function(){view.showResult=!view.showResult});
    button('下一步讲解',function(){view.step=Math.min(q.steps.length,(view.step||0)+1)});
    button('重来',function(){view.angle=0;view.step=0;view.showResult=false;dial.value=0});
  }else if(c.kind==='steps'){
    button('上一步',function(){view.step=Math.max(0,(view.step||0)-1)});
    button('下一步',function(){view.step=Math.min(c.params.steps.length,(view.step||0)+1)});
    button('显示/隐藏答案',function(){view.showAnswer=!view.showAnswer});
    button('重来',function(){view.step=0;view.showAnswer=false});
  }else{
    bar.appendChild(el('span',{class:'muted',text:'点句子＝在大屏上高亮为同学们找到的依据'}));
    button('显示/隐藏补充资料',function(){view.showMaterial=!view.showMaterial});
    button('显示/隐藏书面解释要求',function(){view.showPrompt=!view.showPrompt});
    button('清除高亮',function(){view.highlight=[]});
  }
  draw();
}
"""

# Preparation editor: only the lesson-plan page needs it.
COURSEWARE_PLAN_JS = r"""
var CW_STAGES=['到课与热身','知识点介绍','例题讲解','随堂练习','练习复盘','课堂互动','布置课后'];
function cwPlan(box,lessonId,refresh){
  var stageNo='3',msg=el('div',{role:'status','aria-live':'polite'}),data=null,busy=false,editorBox=null,notes={};
  function load(){api('/teacher/weekend/lessons/'+lessonId+'/courseware').then(paint).catch(function(e){box.textContent='';box.appendChild(el('div',{class:'notice error',text:e.message}))})}
  function itemAt(page){return (data.items||[]).filter(function(i){return String(i.stage)===stageNo&&i.page===page})[0]}
  function paint(d){
    data=d;box.textContent='';
    box.appendChild(el('p',{class:'muted',text:'每一页讲解／例题可配一个互动课件。AI 从审核过的模板（'+d.templates.map(function(k){return d.kindLabels[k]}).join('、')+'）中为每页选一个并填写参数；你逐页预览、修改、审核后才会在大屏那一页出现。上课翻页和操作不调用 AI。'}));
    var stageSel=el('select',{'aria-label':'环节'});CW_STAGES.forEach(function(x,i){stageSel.appendChild(el('option',{value:i+1,text:'第'+(i+1)+'环节：'+x+((d.pages[String(i+1)]||[]).length?'（'+d.pages[String(i+1)].length+' 页）':'')}))});
    stageSel.value=stageNo;stageSel.onchange=function(){stageNo=stageSel.value;paint(data)};
    var pages=d.pages[stageNo]||[],list=pages.length?pages.map(function(x,i){return {page:i,text:x}}):[{page:null,text:'整个环节'}];
    var redo=el('input',{type:'checkbox'});
    var all=el('button',{class:'primary',text:'为本环节全部 '+list.length+' 页生成',onclick:function(){
      var todo=list.filter(function(x){var it=itemAt(x.page);return redo.checked||!it});
      if(!todo.length){msg.textContent='本环节每页都已有课件；如需重新生成请勾选“包括已有课件的页”。';return}
      if(!confirm('将逐页调用 AI 生成 '+todo.length+' 页课件草稿（每页约十几秒），生成后需逐页审核才会上课堂。确定吗？'))return;
      run(todo,function(x){return api('/teacher/weekend/lessons/'+lessonId+'/courseware/generate',{json:{stageNo:+stageNo,page:x.page}})},'生成');
    }});
    var approveAll=el('button',{text:'全部草稿审核通过',onclick:function(){
      var todo=list.filter(function(x){var it=itemAt(x.page);return it&&it.status==='draft'});
      if(!todo.length){msg.textContent='没有待审核的草稿';return}
      if(!confirm('确认已逐页预览这 '+todo.length+' 页课件的内容和答案？审核后会在大屏对应页显示。'))return;
      run(todo,function(x){return api('/teacher/weekend/lessons/'+lessonId+'/courseware/approve',{json:{stageNo:+stageNo,page:x.page}})},'审核');
    }});
    box.appendChild(el('div',{class:'row'},stageSel,all,el('label',{class:'row'},redo,el('span',{text:'包括已有课件的页'})),approveAll));
    box.appendChild(msg);
    var rows=el('div'),editor=el('div');box.appendChild(rows);box.appendChild(editor);editorBox=editor;notes={};
    list.forEach(function(x){
      var it=itemAt(x.page),tag=!it?['','未生成']:it.status==='approved'?['ok','已审核']:it.approved?['warn','已审核·有新草稿']:['warn','草稿'];
      var line=el('div',{class:'item'},el('span',{class:'t'},el('b',{text:(x.page==null?'':'第'+(x.page+1)+'页：')+x.text}),
        el('div',{class:'row'},el('span',{class:'tag '+tag[0],text:tag[1]}),it?el('span',{class:'muted',text:d.kindLabels[it.kind]+(it.writtenTask?' · 含学生作答题':'')}):null)));
      var note=el('div',{role:'status','aria-live':'polite',style:'flex-basis:100%'});notes[String(x.page)]=note;
      line.appendChild(el('button',{text:it?'重新生成':'生成',onclick:function(e){
        if(busy){note.textContent='正在处理另一页，请等它完成后再点。';return}
        var b=e.target,label=b.textContent;busy=true;b.disabled=true;b.textContent='生成中…';
        note.className='notice';note.textContent='AI 正在为这一页生成课件，约十几秒，请稍候…';
        api('/teacher/weekend/lessons/'+lessonId+'/courseware/generate',{json:{stageNo:+stageNo,page:x.page}}).then(function(d){
          busy=false;paint(d);if(refresh)refresh();
          // Say it on this page's row (the list can be long), then open the new draft's preview.
          var n=notes[String(x.page)];if(n){n.className='notice ok';n.textContent='已生成新草稿'+(d.notice?'（'+d.notice+'）':'')+'，预览在下方，核对后点“审核通过”。'}
          edit(editorBox,x,itemAt(x.page));
        }).catch(function(err){busy=false;b.disabled=false;b.textContent=label;note.className='notice error';note.textContent=err.message});
      }}));
      line.appendChild(el('button',{text:it?'预览／修改':'手动填写',onclick:function(){edit(editor,x,itemAt(x.page))}}));
      if(it&&it.previousDraft)line.appendChild(el('button',{text:'恢复上一版',onclick:function(){
        if(!confirm('恢复这一页上一次的课件草稿？恢复后请重新核对。'))return;
        api('/teacher/weekend/lessons/'+lessonId+'/courseware/restore-previous',{json:{stageNo:+stageNo,page:x.page}})
          .then(function(d2){paint(d2);msg.textContent='已恢复上一版草稿，请预览核对。'})
          .catch(function(e){note.className='notice error';note.textContent=e.message});
      }}));
      if(it)line.appendChild(el('button',{text:'存为模板',onclick:function(){
        var name=prompt('给这个模板起个名字，以后可以套用到其它课：',(data.subject||'')+'课件模板');
        if(name===null)return;
        api('/teacher/weekend/lessons/'+lessonId+'/courseware/save-as-template',{json:{stageNo:+stageNo,page:x.page,name:name}})
          .then(function(r){msg.textContent='已存为模板：'+r.name}).catch(function(e){msg.textContent=e.message});
      }}));
      line.appendChild(el('button',{text:'套用模板',onclick:function(){pickTemplate(x)}}));
      if(it&&it.status==='draft')line.appendChild(el('button',{class:'primary',text:'审核通过',onclick:function(){run([x],function(y){return api('/teacher/weekend/lessons/'+lessonId+'/courseware/approve',{json:{stageNo:+stageNo,page:y.page}})},'审核')}}));
      if(it)line.appendChild(el('button',{text:'删除',onclick:function(){if(confirm('删除这一页的课件？'))api('/teacher/weekend/lessons/'+lessonId+'/courseware/remove',{json:{stageNo:+stageNo,page:x.page}}).then(paint).catch(function(e){msg.textContent=e.message})}}));
      rows.appendChild(line);line.appendChild(note);
    });
  }
  function pickTemplate(x){
    editorBox.textContent='';
    var card=el('div',{class:'card'}),listBox=el('div');
    card.appendChild(el('h2',{text:'套用本校模板（'+(x.page==null?'整个环节':'第'+(x.page+1)+'页')+'）'}));
    card.appendChild(listBox);
    card.appendChild(el('button',{text:'关闭',onclick:function(){editorBox.textContent=''}}));
    editorBox.appendChild(card);
    api('/teacher/weekend/courseware/templates?subject='+encodeURIComponent(data.subject||'')).then(function(d){
      if(!d.items.length){listBox.appendChild(el('div',{class:'notice warn',text:'本校还没有模板。先在某个课件上点“存为模板”。'}));return}
      d.items.forEach(function(t){
        listBox.appendChild(el('div',{class:'row'},el('b',{text:t.name}),
          el('span',{class:'muted',text:t.kindLabel+' · 第'+t.stageNo+'环节'}),
          el('button',{class:'primary',text:'套用',onclick:function(){
            if(!confirm('把“'+t.name+'”套用到这一页？套用后是新的草稿，需要你重新审核。'))return;
            api('/teacher/weekend/lessons/'+lessonId+'/courseware/from-template',{json:{stageNo:+stageNo,page:x.page,templateId:t.id}})
              .then(function(d2){msg.textContent='已套用模板，请预览后点“审核通过”。';paint(d2)})
              .catch(function(e){msg.textContent=e.message});
          }})));
      });
    }).catch(function(e){listBox.appendChild(el('div',{class:'notice error',text:e.message}))});
  }
  function run(todo,call,label){
    if(busy)return;busy=true;var failed=[],i=0,last=null;
    function next(){
      if(i>=todo.length){busy=false;if(last)paint(last);else load();msg.textContent=label+'完成 '+(todo.length-failed.length)+'/'+todo.length+' 页'+(failed.length?'。未完成：\n'+failed.join('\n'):'');if(refresh)refresh();
        return}
      var x=todo[i++];msg.textContent='正在'+label+'第 '+i+'/'+todo.length+' 页…';
      call(x).then(function(d){last=d}).catch(function(e){failed.push(e.message)}).then(next);
    }
    next();
  }
  function edit(box2,x,it){
    box2.textContent='';var card=el('div',{class:'card'}),fields={},kinds=data.templates,kind=it?it.kind:kinds[kinds.length-1],p=JSON.parse(JSON.stringify(it?it.params:{})),previewState={step:1,previewMode:true},preview=el('div',{class:'card',style:'position:sticky;top:76px;z-index:4;max-height:76vh;overflow:auto;box-shadow:0 8px 24px #10182822'});
    card.appendChild(el('h3',{text:(x.page==null?'整个环节':'第'+(x.page+1)+'页')+' 的课件'}));
    card.appendChild(el('p',{class:'muted',style:'white-space:pre-wrap',text:'这一页的内容：'+x.text}));
    var kindSel=el('select');kinds.forEach(function(k){kindSel.appendChild(el('option',{value:k,text:data.kindLabels[k]}))});kindSel.value=kind;
    var task=el('input',{type:'checkbox'});task.checked=!!(it&&it.writtenTask);
    card.appendChild(el('div',{class:'row'},el('span',{text:'模板'}),kindSel,el('label',{class:'row'},task,el('span',{text:'审核后同时生成学生书面作答题'}))));
    var form=el('div');card.appendChild(form);card.appendChild(preview);
    function input(v){var n=el('input',{type:'text'});n.value=v==null?'':String(v);return n}
    function area(v){var n=el('textarea');n.value=v||'';return n}
    function field(key,label,node){fields[key]=node;form.appendChild(el('label',{class:'field'},el('span',{text:label}),node));node.addEventListener('input',show);node.addEventListener('change',show)}
    function sel(opts,v){var n=el('select');opts.forEach(function(o){n.appendChild(el('option',{value:o[0],text:o[1]}))});n.value=String(v);return n}
    function build(){
      form.textContent='';fields={};kind=kindSel.value;
      field('title','标题',input(p.title));
      if(kind==='rotation'){
        field('width','网格宽（6—12）',input(p.width||10));field('height','网格高（6—12）',input(p.height||10));
        field('shape','原图顶点（如 2,2; 5,2; 2,4）',input((p.shape||[[2,2],[5,2],[2,4]]).map(function(q){return q.join(',')}).join('; ')));
        field('center','旋转中心（如 2,2）',input((p.center||[2,2]).join(',')));
        field('direction','方向',sel([['cw','顺时针'],['ccw','逆时针']],p.direction||'cw'));field('angle','角度',sel([[90,'90°'],[180,'180°'],[270,'270°']],p.angle||90));
        field('steps','讲解步骤（每行一步）',area((p.steps||[]).join('\n')));
      }else if(kind==='clock'){
        field('start','起始数字（1—12）',input(p.start||12));field('direction','方向',sel([['cw','顺时针'],['ccw','逆时针']],p.direction||'cw'));
        field('angle','角度（30° 的倍数）',input(p.angle||90));field('steps','讲解步骤（每行一步）',area((p.steps||[]).join('\n')));
      }else if(kind==='steps'){
        field('problem','题目原文（不含答案，生成学生作答题时使用）',area(p.problem));
        field('steps','讲解步骤（每行一步，2—6 步）',area((p.steps||[]).join('\n')));field('answer','答案',input(p.answer));
        var f=p.figure||{},choices=[['','不画图'],['segment','线段和点'],['flow','计算程序图'],['shape','图形'],['table','数表'],['calendar_cross','\u6708\u5386\u5341\u5b57\u6846'],['seating_pattern','方桌人数规律'],['alternating_triangle','黑白棋子三角形'],['running_track','环形跑道追及']];if(f.type==='uploaded_image')choices.unshift(['uploaded_image','原卷图片']);var ft=sel(choices,f.type||'');
        field('figType','图示（大屏上画出题目条件）',ft);ft.onchange=function(){var keep=collect();keep.figure=ft.value==='calendar_cross'?{type:ft.value,center:18,daysInMonth:31,firstWeekday:0,total:90}:ft.value==='seating_pattern'?{type:ft.value,sampleCounts:[8,12,16]}:ft.value==='alternating_triangle'?{type:ft.value,rows:6,differenceSymbol:'m'}:ft.value==='running_track'?{type:ft.value,fastSpeed:180,slowSpeed:140,distanceSymbol:'s'}:{type:ft.value,points:[],marks:[],boxes:[],branches:[],labels:{},rows:[],shape:'rectangle'};p=keep;build()};
        if(f.type==='segment'){
          field('figA','线段上的点（名称:位置，分号隔开，如 A:0; C:3; B:6; D:10）',input((f.points||[]).map(function(q){return q.name+':'+q.at}).join('; ')));
          field('figB','标注（如 A-D:L; A-B:x，可留空）',input((f.marks||[]).map(function(m){return m.from+'-'+m.to+':'+m.label}).join('; ')));
        }else if(f.type==='flow'){
          field('figA','程序框（用 → 隔开，如 输入 a → ÷0.5 → +b → 输出）',input((f.boxes||[]).join(' → ')));
          field('figB','分两种情况时每行一种（如 n 是单数：2n+4），不分情况留空',area((f.branches||[]).map(function(b){return b.when+'：'+b.boxes.join(' → ')}).join('\n')));
        }else if(f.type==='shape'){
          field('figShape','图形',sel([['rectangle','长方形'],['square','正方形'],['triangle','三角形'],['parallelogram','平行四边形'],['trapezoid','梯形']],f.shape||'rectangle'));
          var names={top:'上',bottom:'下',left:'左',right:'右',height:'高'};
          field('figA','边上的标注（如 上:a cm; 左:b cm; 高:h，可用 上 下 左 右 高）',input(Object.keys(f.labels||{}).map(function(k){return names[k]+':'+f.labels[k]}).join('; ')));
        }else if(f.type==='calendar_cross'){
          field('figCenter','\u5341\u5b57\u6846\u4e2d\u5fc3\u65e5\u671f',input(f.center||18));field('figDays','\u672c\u6708\u5929\u6570\uff0828\u201431\uff09',input(f.daysInMonth||31));
          field('figWeekday','\u672c\u67081\u65e5\u661f\u671f\u51e0\uff080\u5468\u65e5\u20146\u5468\u516d\uff09',input(f.firstWeekday==null?0:f.firstWeekday));field('figTotal','\u4e94\u4e2a\u6570\u7684\u603b\u548c',input(f.total||90));
        }else if(f.type==='seating_pattern'){
          field('figCounts','\u6bcf\u79cd\u684c\u6570\u7684\u4eba\u6570\uff08\u9017\u53f7\u9694\u5f00\uff0c\u4ece1\u5f20\u684c8\u4eba\u5f00\u59cb\uff09',input((f.sampleCounts||[8,12,16]).join(', ')));
        }else if(f.type==='alternating_triangle'){
          field('figRows','\u663e\u793a\u5c42\u6570\uff084/6/8\uff0c\u9996\u5c42\u767d\uff0c\u5076\u6570\u5c42\u9ed1\uff09',input(f.rows||6));field('figDiff','\u9ed1\u591a\u767d\u7684\u9897\u6570\u5b57\u6bcd',input(f.differenceSymbol||'m'));
        }else if(f.type==='running_track'){
          field('figFast','\u5feb\u8005\u901f\u5ea6\uff08\u7c73/\u5206\uff09',input(f.fastSpeed||180));field('figSlow','\u6162\u8005\u901f\u5ea6\uff08\u7c73/\u5206\uff09',input(f.slowSpeed||140));field('figDistanceSymbol','\u8dd1\u9053\u5468\u957f\u5b57\u6bcd',input(f.distanceSymbol||'s'));
        }else if(f.type==='table'){
          field('figA','数表（每行一行，格子用 | 隔开）',area((f.rows||[]).map(function(r){return r.join(' | ')}).join('\n')));
        }
      }else{
        field('passage','阅读材料（必须是原文中的连续段落）',area(p.passage));field('question','阅读问题',area(p.question));
        field('material','补充资料（请核实）',area(p.material));field('writingPrompt','书面解释要求',area(p.writingPrompt));p.evidence=p.evidence||[];
      }
      if(kind!=='reading')field('question','学生书面作答问题',area(p.question));
      field('reference','评分要点（仅老师可见）',area(p.reference));
      show();
    }
    function lines(n){return n.value.split('\n').map(function(v){return v.trim()}).filter(Boolean)}
    function parts(v,sep){return String(v||'').split(sep).map(function(x){return x.trim()}).filter(Boolean)}
    function figure(){
      var t=fields.figType?fields.figType.value:'';if(!t)return {};if(t==='uploaded_image')return p.figure||{};
      if(t==='calendar_cross')return {type:t,center:Number(fields.figCenter.value),daysInMonth:Number(fields.figDays.value),firstWeekday:Number(fields.figWeekday.value),total:Number(fields.figTotal.value)};
      if(t==='seating_pattern')return {type:t,sampleCounts:parts(fields.figCounts.value,/,/).map(function(x){return Number(x)})};
      if(t==='alternating_triangle')return {type:t,rows:Number(fields.figRows.value),differenceSymbol:fields.figDiff.value};
      if(t==='running_track')return {type:t,fastSpeed:Number(fields.figFast.value),slowSpeed:Number(fields.figSlow.value),distanceSymbol:fields.figDistanceSymbol.value};
      if(!fields.figA)return {type:t,points:[],marks:[],boxes:[],branches:[],labels:{},rows:[],shape:'rectangle'};
      if(t==='segment')return {type:t,points:parts(fields.figA.value,/[;；]/).map(function(x){var k=x.split(/[:：]/);return {name:(k[0]||'').trim(),at:Number((k[1]||'').trim())}}),
        marks:parts(fields.figB.value,/[;；]/).map(function(x){var k=x.split(/[:：]/),ab=(k[0]||'').split(/[-－—]/);return {from:(ab[0]||'').trim(),to:(ab[1]||'').trim(),label:(k.slice(1).join(':')||'').trim()}})};
      if(t==='flow')return {type:t,boxes:parts(fields.figA.value,/→|->|>/),branches:lines(fields.figB).map(function(x){var k=x.split(/[:：]/);return {when:(k[0]||'').trim(),boxes:parts(k.slice(1).join(':'),/→|->|>/)}})};
      if(t==='shape'){var keys={'上':'top','下':'bottom','左':'left','右':'right','高':'height'},labels={};
        parts(fields.figA.value,/[;；]/).forEach(function(x){var k=x.split(/[:：]/);if(keys[(k[0]||'').trim()])labels[keys[k[0].trim()]]=k.slice(1).join(':').trim()});
        return {type:t,shape:fields.figShape.value,labels:labels}}
      return {type:t,rows:lines(fields.figA).map(function(r){return parts(r,'|')})};
    }
    function pt(v){return String(v).split(/[,，]/).map(function(x){return Number(x.trim())})}
    function collect(){
      var v={title:fields.title.value,question:fields.question.value,reference:fields.reference.value};
      if(kind==='rotation'){v.width=+fields.width.value;v.height=+fields.height.value;v.shape=fields.shape.value.split(/[;；]/).filter(function(x){return x.trim()}).map(pt);v.center=pt(fields.center.value);v.direction=fields.direction.value;v.angle=+fields.angle.value;v.steps=lines(fields.steps)}
      else if(kind==='clock'){v.start=+fields.start.value;v.direction=fields.direction.value;v.angle=+fields.angle.value;v.steps=lines(fields.steps)}
      else if(kind==='steps'){v.problem=fields.problem.value;v.sourceProblem=p.sourceProblem||'';v.steps=lines(fields.steps);v.answer=fields.answer.value;v.figure=figure();v.sourceFigure=p.sourceFigure||{}}
      else{v.passage=fields.passage.value;v.sentences=cwSplit(v.passage);v.material=fields.material.value;v.writingPrompt=fields.writingPrompt.value;p.evidence=(p.evidence||[]).filter(function(i){return i<v.sentences.length});v.evidence=p.evidence}
      return v;
    }
    function show(){
      var v=collect(),title=el('b',{text:'预览（教师视角，含答案）'}),view=el('div'),fig=v.figure||{};preview.textContent='';preview.appendChild(el('div',{class:'row',style:'justify-content:space-between'},title,el('span',{class:'tag',text:kind!=='steps'?'模板图示':fig.type==='uploaded_image'?'原卷图片':fig.type?'课件图示':'无图'})));preview.appendChild(view);
      if(kind==='rotation'){if(!(v.shape.length>=3&&v.center.length===2&&v.shape.every(function(q){return q.length===2&&isFinite(q[0])&&isFinite(q[1])}))){view.appendChild(el('div',{class:'notice warn',text:'坐标格式不完整'}));return}
        v.rotated=v.shape.map(function(q){return cwRotate(q,v.center,v.direction,v.angle)});cwRender(view,{kind:kind,params:v},{angle:v.angle,showResult:true,showCenter:true,step:v.steps.length},false,true)}
      else if(kind==='clock'){var t=v.angle/30*(v.direction==='cw'?1:-1);v.end=((v.start-1+t)%12+12)%12+1;cwRender(view,{kind:kind,params:v},{angle:v.angle,showResult:true,step:v.steps.length},false,true)}
      else if(kind==='steps'){
        previewState.step=Math.max(1,Math.min(previewState.step,v.steps.length));
        var nav=el('div',{class:'row',style:'margin:8px 0'});
        nav.appendChild(el('button',{text:'\u4e0a\u4e00\u6b65',disabled:previewState.step<=1,onclick:function(){previewState.step=Math.max(1,previewState.step-1);show()}}));
        nav.appendChild(el('button',{text:'\u4e0b\u4e00\u6b65',disabled:previewState.step>=v.steps.length,onclick:function(){previewState.step=Math.min(v.steps.length,previewState.step+1);show()}}));
        nav.appendChild(el('span',{class:'muted',text:'\u5df2\u663e\u793a '+previewState.step+' / '+v.steps.length+' \u6b65'}));preview.appendChild(nav);
        cwRender(view,{kind:kind,params:v},previewState,false,true);
      }
      else cwRender(view,{kind:kind,params:v},{showMaterial:true,showPrompt:true},false,true,function(i){var k=p.evidence.indexOf(i);if(k>=0)p.evidence.splice(k,1);else p.evidence.push(i);show()});
    }
    kindSel.onchange=build;build();
    var m2=el('div',{role:'status'});
    var save=el('button',{text:'保存修改（需重新审核）',onclick:function(){api('/teacher/weekend/lessons/'+lessonId+'/courseware',{method:'PUT',json:{stageNo:+stageNo,page:x.page,kind:kind,params:collect(),writtenTask:task.checked}}).then(function(d){paint(d);m2.textContent='已保存为草稿'}).catch(function(e){m2.textContent=e.message})}});
    card.appendChild(el('div',{class:'row'},save));card.appendChild(m2);
    if(it&&it.writtenTaskPreview)card.appendChild(el('details',{},el('summary',{text:'学生书面作答题（勾选后审核时生成）'}),el('pre',{style:'white-space:pre-wrap;font:inherit',text:it.writtenTaskPreview.stem}),el('pre',{style:'white-space:pre-wrap;font:inherit;color:#667085',text:'参考答案（仅老师可见）：'+it.writtenTaskPreview.reference})));
    box2.appendChild(card);card.scrollIntoView&&card.scrollIntoView();
  }
  load();
}
"""



