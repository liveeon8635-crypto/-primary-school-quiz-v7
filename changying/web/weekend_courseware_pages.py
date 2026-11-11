"""Reviewed courseware templates (ES5, DOM only: parameters are rendered with textContent/SVG attributes, never as markup)."""

COURSEWARE_JS = r"""
var CW_SVG='http://www.w3.org/2000/svg',CW_LETTERS='ABCDEF';
function cwSplit(text){return (String(text||'').match(/[^。！？；!?;\n]+[。！？；!?;]?[”」』]?/g)||[]).map(function(s){return s.trim()}).filter(Boolean)}
function cwRotate(p,c,dir,angle){var x=p[0]-c[0],y=p[1]-c[1],t=(angle/90)%4;if(dir==='ccw')t=(4-t)%4;for(var i=0;i<t;i++){var nx=y;y=-x;x=nx}return [c[0]+x,c[1]+y]}
function cwNode(tag,attrs,text){var n=document.createElementNS(CW_SVG,tag);Object.keys(attrs||{}).forEach(function(k){n.setAttribute(k,attrs[k])});if(text!=null)n.textContent=text;return n}
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
  if(f.type==='calendar_compare')return '月历四种框形：A一行四格、B两行两列、C一列三格、D三行三列';
  if(f.type==='calendar_cross')return '\u6708\u5386\u5341\u5b57\u6846\uff1a\u4e2d\u5fc3 '+f.center+'\uff0c\u4e94\u6570\u548c '+f.total;
  if(f.type==='seating_pattern')return '\u65b9\u684c\u4eba\u6570\u89c4\u5f8b\uff1a'+f.sampleCounts.join('\u3001');
  if(f.type==='alternating_triangle')return '\u9ed1\u767d\u68cb\u5b50\u4e09\u89d2\u5f62\uff1a'+f.rows+'\u5c42\uff0c\u5dee\u503c '+f.differenceSymbol;
  if(f.type==='running_track')return '\u540c\u5411\u73af\u5f62\u8dd1\u9053\uff1a'+f.fastSpeed+'\u7c73/\u5206\u949f\u548c '+f.slowSpeed+'\u7c73/\u5206\u949f\uff0c\u8dd1\u9053\u5468\u957f '+f.distanceSymbol;
  if(f.type==='triangular_numbers')return '\u4e09\u89d2\u5f62\u6570\uff1a'+f.terms.join('\u3001')+'\uff0c\u6c42\u7b2c '+f.targetTerm+' \u9879';
  if(f.type==='tile_pattern')return '\u5730\u7816\u6392\u5217\u89c4\u5f8b\uff1a\u767d\u7816 '+f.whiteCounts.join('\u3001')+'\uff0c\u84dd\u7816 '+f.blueCounts.join('\u3001');
  if(f.type==='square_sticks_pattern')return '\u8fde\u7eed\u6b63\u65b9\u5f62\u4e0e\u5c0f\u68d2\uff1a'+f.sampleCounts.join('\u3001')+'\u6839\uff1b\u5171\u7528\u8fb9\u53ea\u7b97\u4e00\u6839';
  if(f.type==='hundred_chart_square')return '\u767e\u6570\u8868\u7530\u5b57\u683c\uff1a'+f.topLeftNumber+'\uff1b\u6a2a\u5411\u76f8\u5dee1\uff0c\u7eb5\u5411\u76f8\u5dee10';
  return f.rows.map(function(r){return r.join(' | ')}).join('\n');
}
function cwFigureOk(f){
  if(f.type==='uploaded_image')return /^data:image\/jpeg;base64,/.test(String(f.data_url||''));
  if(f.type==='segment'){var at=(f.points||[]).map(function(q){return q.at});return at.length>=2&&at.every(function(a){return isFinite(a)})&&Math.max.apply(null,at)>Math.min.apply(null,at)}
  if(f.type==='flow')return (f.boxes||[]).length>0||(f.branches||[]).length>0;
  if(f.type==='shape')return !!CW_SHAPES[f.shape];
  if(f.type==='calendar_compare')return true;
  if(f.type==='calendar_cross')return isFinite(f.center)&&isFinite(f.daysInMonth)&&isFinite(f.firstWeekday)&&isFinite(f.total)&&f.center===f.total/5;
  if(f.type==='seating_pattern')return (f.sampleCounts||[]).length>=2&&f.sampleCounts.length<=4&&f.sampleCounts[0]===8&&f.sampleCounts.every(function(n,i){return isFinite(n)&&n===8+i*4});
  if(f.type==='alternating_triangle')return f.rows>=4&&f.rows<=8&&f.rows%2===0&&/^[A-Za-z]$/.test(f.differenceSymbol||'');
  if(f.type==='running_track')return f.fastSpeed>f.slowSpeed&&f.slowSpeed>0&&/^[A-Za-z]$/.test(f.distanceSymbol||'');
  if(f.type==='triangular_numbers')return (f.terms||[]).length>=3&&f.terms.every(function(n,i){return n===(i+1)*(i+2)/2})&&f.targetTerm>=2&&f.targetTerm<=100;
  if(f.type==='tile_pattern')return (f.whiteCounts||[]).length===2&&(f.blueCounts||[]).length===2&&f.whiteCounts[1]>f.whiteCounts[0]&&f.blueCounts[1]>f.blueCounts[0]&&f.targetTerm>=1&&f.targetTerm<=100&&f.targetBlue>=1;
  if(f.type==='square_sticks_pattern')return (f.sampleCounts||[]).join(',')==='4,7,10'&&(f.targetSquares||[]).length===2&&f.targetSquares.every(function(n){return n>=1&&n<=1000})&&f.targetSticks>=4&&f.targetSticks<=10000;
  if(f.type==='hundred_chart_square')return f.topLeftNumber>=1&&f.topLeftNumber<=89&&f.topLeftNumber%10!==0;
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
  var step=teacher&&!view.previewMode?(stepCount||99):(view.step||0),counts=f.sampleCounts||[8,12,16],shown=Math.max(1,Math.min(counts.length,Math.ceil(Math.max(1,step)*counts.length/Math.max(1,(stepCount||counts.length+1)-1))));
  var wrap=el('div',{style:'max-width:920px;margin:10px auto;padding:12px;border:1px solid #d0d5dd;border-radius:12px;background:#fff'});box.appendChild(wrap);
  var svg=cwNode('svg',{viewBox:'0 0 900 300',width:'100%',style:'display:block;max-height:'+(big?'42vh':'340px'),role:'img','aria-label':cwFigureText(f)});
  function chair(cx,cy,dir,color){
    var g=cwNode('g',{transform:'translate('+cx+' '+cy+') rotate('+dir+')'});
    g.appendChild(cwNode('rect',{x:-8,y:-7,width:16,height:12,rx:2,fill:'#fff',stroke:color,'stroke-width':2}));
    g.appendChild(cwNode('line',{x1:-9,y1:7,x2:9,y2:7,stroke:color,'stroke-width':2}));
    g.appendChild(cwNode('line',{x1:-7,y1:5,x2:-7,y2:11,stroke:color,'stroke-width':2}));g.appendChild(cwNode('line',{x1:7,y1:5,x2:7,y2:11,stroke:color,'stroke-width':2}));svg.appendChild(g);
  }
  for(var i=0;i<shown;i++){
    var n=i+1,x0=i*300,side=42,w=n*side,x=x0+(300-w)/2,y=112,color=i===shown-1?'#2563eb':'#667085';
    svg.appendChild(cwNode('rect',{x:x0+5,y:8,width:290,height:278,rx:10,fill:i===shown-1?'#eff6ff':'#fff',stroke:i===shown-1?'#2563eb':'#d0d5dd','stroke-width':i===shown-1?2:1}));
    svg.appendChild(cwNode('text',{x:x0+150,y:34,'text-anchor':'middle','font-size':18,'font-weight':700,fill:'#111'},n+' 张单位正方桌'));
    for(var j=0;j<n;j++){
      svg.appendChild(cwNode('rect',{x:x+j*side,y:y,width:side,height:side,fill:'#fef3c7',stroke:'#344054','stroke-width':2}));
      if(j>0)svg.appendChild(cwNode('line',{x1:x+j*side,y1:y+3,x2:x+j*side,y2:y+side-3,stroke:'#98a2b3','stroke-width':1,'stroke-dasharray':'3 3'}));
      chair(x+j*side+side/4,y-13,0,color);chair(x+j*side+side*3/4,y-13,0,color);
      chair(x+j*side+side/4,y+side+13,180,color);chair(x+j*side+side*3/4,y+side+13,180,color);
    }
    chair(x-13,y+side/3,-90,color);chair(x-13,y+side*2/3,-90,color);chair(x+w+13,y+side/3,90,color);chair(x+w+13,y+side*2/3,90,color);
    svg.appendChild(cwNode('rect',{x:x-4,y:y-4,width:w+8,height:side+8,fill:'none',stroke:'#dc2626','stroke-width':3,'stroke-dasharray':'7 4',rx:3}));
    svg.appendChild(cwNode('text',{x:x0+150,y:222,'text-anchor':'middle','font-size':18,'font-weight':700,fill:color},counts[i]+' 人'));
    svg.appendChild(cwNode('text',{x:x0+150,y:250,'text-anchor':'middle','font-size':13,fill:'#b42318'},'红虚线：拼接后外周'));
  }
  wrap.appendChild(svg);
  wrap.appendChild(el('div',{style:'text-align:center;color:#475467;font-size:14px',text:'每张桌面是单位正方形；相邻边拼在内部，座位只沿外周排列。'}));
  if(step>=stepCount){
    wrap.appendChild(el('div',{style:'margin-top:8px;padding:10px 12px;border-radius:8px;background:#fff7ed;color:#9a3412;font-weight:700;text-align:center',text:'外周单位边数 = 4m − 2(m−1) = 2m+2；每条外周边坐2人，所以人数 = 2(2m+2) = 4m+4。'}));
  }
}
function cwAlternatingTriangle(box,f,view,big,teacher,stepCount){
  var step=teacher&&!view.previewMode?(stepCount||99):(view.step||0),shown=Math.max(1,Math.min(f.rows,Math.ceil(Math.max(1,step)*f.rows/Math.max(1,stepCount||f.rows))));
  var wrap=el('div',{style:'max-width:620px;margin:10px auto;padding:12px;border:1px solid #d0d5dd;border-radius:12px;background:#fff;text-align:center'});
  box.appendChild(wrap);
  var size=31,svg=cwNode('svg',{viewBox:'0 0 420 '+(55+shown*size),width:'100%',style:'display:block;max-height:'+(big?'38vh':'280px'),role:'img','aria-label':cwFigureText(f)});
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
  if(step>=stepCount){
    var formulas=el('div',{style:'display:grid;grid-template-columns:1fr;gap:6px;margin-top:10px;text-align:left'});
    function formulaCard(title,equation,color){var card=el('div',{style:'padding:7px 10px;border-radius:8px;background:#f8fafc;color:'+color});card.appendChild(el('div',{style:'font-size:13px;font-weight:600;color:#475467',text:title}));card.appendChild(el('div',{style:'font-size:15px;font-weight:700;text-align:center;white-space:nowrap;margin-top:3px',text:equation}));return card}
    formulas.appendChild(formulaCard('\u767d\u68cb\u5b50\uff08\u5947\u6570\u5c42\uff09','1 + 3 + \u22ef + (2k\u22121) = k\u00b2','#17449b'));
    formulas.appendChild(formulaCard('\u9ed1\u68cb\u5b50\uff08\u5076\u6570\u5c42\uff09','2 + 4 + \u22ef + 2k = k(k+1)','#344054'));
    formulas.appendChild(formulaCard('\u4e24\u8272\u5c42\u6570\u5173\u7cfb','\u9ed1\u6bd4\u767d\u591a '+f.differenceSymbol+'\uff0c\u603b\u5c42\u6570 = 2'+f.differenceSymbol,'#17449b'));
    wrap.appendChild(formulas);
  }
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
function cwTilePattern(box,f,view,big,teacher,stepCount){
  var finalStep=Math.max(4,stepCount||4),step=teacher&&!view.previewMode?finalStep:Math.max(1,view.step||0),wrap=el('div',{style:'max-width:840px;margin:10px auto;padding:12px;border:1px solid #d0d5dd;border-radius:12px;background:#fff'});
  var svg=cwNode('svg',{viewBox:'0 0 820 300',width:'100%',style:'display:block;max-height:'+(big?'38vh':'300px'),role:'img','aria-label':cwFigureText(f)});
  function label(x,y,t,size,color,weight,anchor){svg.appendChild(cwNode('text',{x:x,y:y,'font-size':size||16,'font-weight':weight||600,'text-anchor':anchor||'start',fill:color||'#344054'},t))}
  function arrangement(x,white,blue,name){
    var size=18,gap=2,unit=size+gap,base=207;
    label(x+175,35,name,17,'#344054',700,'middle');
    // A white horizontal side and a blue vertical side meet at a right angle.
    for(var i=0;i<white;i++)svg.appendChild(cwNode('rect',{x:x+i*unit,y:base,width:size,height:size,rx:2,fill:'#fff',stroke:'#667085','stroke-width':2}));
    for(var j=0;j<blue;j++)svg.appendChild(cwNode('rect',{x:x+white*unit,y:base-(j+1)*unit,width:size,height:size,rx:2,fill:'#93c5fd',stroke:'#2563eb','stroke-width':2}));
    svg.appendChild(cwNode('path',{d:'M '+(x-3)+' '+(base-3)+' L '+(x+white*unit+size+3)+' '+(base-3)+' L '+(x+white*unit+size+3)+' '+(base-blue*unit-3),fill:'none',stroke:'#dc2626','stroke-width':2,'stroke-dasharray':'5 4'}));
    label(x+white*unit/2,base+37,'白砖边 '+white+' 块',14,'#475467',600,'middle');
    label(x+white*unit+size+7,base-blue*unit+size/2,'蓝砖边 '+blue+' 块',13,'#17449b',600,'start');
    svg.appendChild(cwNode('path',{d:'M '+(x+white*unit-2)+' '+(base-4)+' l 0 -12 l 12 0',fill:'none',stroke:'#b42318','stroke-width':2}));
  }
  arrangement(30,f.whiteCounts[0],f.blueCounts[0],'第 1 幅：两条直角边');
  if(step>=2){arrangement(430,f.whiteCounts[1],f.blueCounts[1],'第 2 幅：边长递增');label(410,150,'→',22,'#2563eb',700,'middle');label(410,173,'白、蓝边各增加 '+(f.whiteCounts[1]-f.whiteCounts[0])+' 块',13,'#475467',600,'middle')}
  else label(410,280,'白砖边与蓝砖边在拐角相接，构成直角',15,'#98a2b3',500,'middle');
  wrap.appendChild(svg);
  if(step>=Math.max(3,finalStep-1)){
    var wi=f.whiteCounts[1]-f.whiteCounts[0],bi=f.blueCounts[1]-f.blueCounts[0],wc=f.whiteCounts[0]-wi,bc=f.blueCounts[0]-bi;
    function expr(a,b){return a+'n'+(b>0?' + '+b:b<0?' − '+Math.abs(b):'')}
    var formulas=el('div',{style:'display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px;margin-top:6px'});
    formulas.appendChild(el('div',{style:'padding:9px 12px;border-radius:8px;background:#f8fafc;color:#17449b;font-weight:700;text-align:center',text:'白砖边长：'+f.whiteCounts[0]+' + '+wi+'(n−1) = '+expr(wi,wc)}));
    formulas.appendChild(el('div',{style:'padding:9px 12px;border-radius:8px;background:#eff6ff;color:#17449b;font-weight:700;text-align:center',text:'蓝砖边长：'+f.blueCounts[0]+' + '+bi+'(n−1) = '+expr(bi,bc)}));wrap.appendChild(formulas);
  }
  if(step>=finalStep){
    var blueInc=f.blueCounts[1]-f.blueCounts[0],blueConst=f.blueCounts[0]-blueInc,whiteInc=f.whiteCounts[1]-f.whiteCounts[0],whiteConst=f.whiteCounts[0]-whiteInc;
    var whiteAt=whiteInc*f.targetTerm+whiteConst,blueAt=blueInc*f.targetTerm+blueConst,sol=(f.targetBlue-blueConst)/blueInc;
    wrap.appendChild(el('div',{style:'margin-top:8px;padding:9px 12px;border-radius:8px;background:#fff7ed;color:#9a3412;font-weight:700;text-align:center',text:'第 '+f.targetTerm+' 幅：白砖边长 '+whiteAt+' 块，蓝砖边长 '+blueAt+' 块；蓝砖边长为 '+f.targetBlue+' 块时，n = '+(Number.isInteger(sol)?sol:'不是整数')}));
  }
  box.appendChild(wrap);
}

function cwSquareSticksPattern(box,f,view,big,teacher,stepCount){
  var finalStep=Math.max(5,stepCount||5),step=teacher&&!view.previewMode?finalStep:Math.max(1,view.step||0);
  var counts=f.sampleCounts||[4,7,10],wrap=el('div',{style:'max-width:900px;margin:10px auto;padding:12px;border:1px solid #d0d5dd;border-radius:12px;background:#fff'});
  var svg=cwNode('svg',{viewBox:'0 0 900 230',width:'100%',style:'display:block;max-height:'+(big?'38vh':'300px'),role:'img','aria-label':cwFigureText(f)});
  function text(x,y,t,size,color,weight,anchor){svg.appendChild(cwNode('text',{x:x,y:y,'font-size':size||16,'font-weight':weight||600,'text-anchor':anchor||'middle',fill:color||'#344054'},t))}
  var xs=[145,450,755],unit=38,y=88;
  for(var n=1;n<=3;n++){
    if(step<n)continue;
    var x0=xs[n-1]-n*unit/2;
    text(xs[n-1],28,n+'个正方形',17,'#344054',700,'middle');
    text(xs[n-1],185,counts[n-1]+'根小棒',16,n===1?'#475467':'#17449b',700,'middle');
    // Draw each unique stick once: n top and bottom segments, plus n+1 vertical segments.
    for(var j=0;j<n;j++){
      var c=j===0?'#667085':'#2563eb',sw=j===0?4:5,x=x0+j*unit;
      svg.appendChild(cwNode('line',{x1:x,y1:y,x2:x+unit,y2:y,stroke:c,'stroke-width':sw,'stroke-linecap':'round'}));
      svg.appendChild(cwNode('line',{x1:x,y1:y+unit,x2:x+unit,y2:y+unit,stroke:c,'stroke-width':sw,'stroke-linecap':'round'}));
    }
    for(var k=0;k<=n;k++){
      var vc=(k===0||n===1)?'#667085':'#2563eb';
      svg.appendChild(cwNode('line',{x1:x0+k*unit,y1:y,x2:x0+k*unit,y2:y+unit,stroke:vc,'stroke-width':k===0?4:5,'stroke-linecap':'round'}));
    }
  }
  if(step<3)text(450,215,'每增加1个正方形，与前一个共用一条边，只新增3根',14,'#98a2b3',500,'middle');
  else text(450,215,'新增的3根：上边1根 + 下边1根 + 右侧边1根；中间共用边只画一次',14,'#475467',600,'middle');
  wrap.appendChild(svg);
  if(step>=4)wrap.appendChild(el('div',{style:'margin-top:8px;padding:10px;border-radius:8px;background:#eff6ff;color:#17449b;font-weight:700;text-align:center',text:'1个先用4根；之后每个与前一个共用1条边，只增加3根。n = 4 + 3(m−1) = 3m + 1'}));
  if(step>=finalStep){
    var targets=f.targetSquares||[8,60];
    wrap.appendChild(el('div',{style:'margin-top:8px;padding:10px;border-radius:8px;background:#fff7ed;color:#9a3412;font-weight:700;text-align:center',text:'代入验证：m='+targets[0]+' 时 n='+ (3*targets[0]+1)+'；m='+targets[1]+' 时 n='+(3*targets[1]+1)+'；n='+f.targetSticks+' 时，m='+(f.targetSticks-1)/3+'。'}));
  }
  box.appendChild(wrap);
}

function cwHundredChartSquare(box,f,view,big,teacher,stepCount){
  var finalStep=5,step=teacher&&!view.previewMode?finalStep:Math.max(1,view.step||0),n=f.topLeftNumber||45;
  var wrap=el('div',{style:'max-width:780px;margin:10px auto;padding:12px;border:1px solid #d0d5dd;border-radius:12px;background:#fff'});
  var svg=cwNode('svg',{viewBox:'0 0 760 525',width:'100%',style:'display:block;max-height:'+(big?'45vh':'380px'),role:'img','aria-label':cwFigureText(f)});
  function label(x,y,t,size,color,weight,anchor){svg.appendChild(cwNode('text',{x:x,y:y,'font-size':size||15,'font-weight':weight||600,'text-anchor':anchor||'middle',fill:color||'#344054'},t))}
  label(380,24,'百数表：同行向右 +1，同列向下 +10',17,'#344054',700,'middle');
  var highlightRow=Math.floor((n-1)/10),highlightCol=(n-1)%10;
  for(var r=0;r<10;r++)for(var c=0;c<10;c++){
    var value=r*10+c+1,x=55+c*33,y=48+r*28,hot=(r===highlightRow||r===highlightRow+1)&&(c===highlightCol||c===highlightCol+1);
    svg.appendChild(cwNode('rect',{x:x,y:y,width:31,height:26,rx:2,fill:hot?'#dbeafe':'#fff',stroke:hot?'#2563eb':'#cbd5e1','stroke-width':hot?2:1}));
    label(x+15.5,y+18,String(value),12,hot?'#17449b':'#475467',hot?700:400,'middle');
  }
  var gx=170,gy=365,cell=74,labels=step===1?[String(n),String(n+1),String(n+10),String(n+11)]:step<4?['n','n+1','n+10','n+11']:['m−11','m−10','m−1','m'];
  var defs=cwNode('defs',{}),marker=cwNode('marker',{id:'cw-hundred-arrow',viewBox:'0 0 10 10',refX:8,refY:5,markerWidth:5,markerHeight:5,orient:'auto'});
  marker.appendChild(cwNode('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#2563eb'}));defs.appendChild(marker);svg.appendChild(defs);
  for(var rr=0;rr<2;rr++)for(var cc=0;cc<2;cc++){
    var idx=rr*2+cc;
    svg.appendChild(cwNode('rect',{x:gx+cc*cell,y:gy+rr*cell,width:cell,height:cell,fill:step>=2?'#eff6ff':'#f8fafc',stroke:'#2563eb','stroke-width':2}));
    label(gx+cc*cell+cell/2,gy+rr*cell+cell/2+7,labels[idx],18,'#17449b',700,'middle');
  }
  label(gx+cell,gy-14,'向右 +1',14,'#2563eb',700,'middle');
  label(gx-18,gy+cell,'向下 +10',13,'#2563eb',700,'end');
  svg.appendChild(cwNode('path',{d:'M '+(gx+5)+' '+(gy-4)+' L '+(gx+cell*2-5)+' '+(gy-4),stroke:'#2563eb','stroke-width':2,'marker-end':'url(#cw-hundred-arrow)'}));
  svg.appendChild(cwNode('path',{d:'M '+(gx-7)+' '+(gy+5)+' L '+(gx-7)+' '+(gy+cell*2-5),stroke:'#2563eb','stroke-width':2,'marker-end':'url(#cw-hundred-arrow)'}));
  wrap.appendChild(svg);
  if(step>=3)wrap.appendChild(el('div',{style:'margin-top:8px;padding:10px;border-radius:8px;background:#eff6ff;color:#17449b;font-weight:700;text-align:center',text:'左上角 n：n + (n+1) + (n+10) + (n+11) = 4n + 22'}));
  if(step>=4)wrap.appendChild(el('div',{style:'margin-top:8px;padding:10px;border-radius:8px;background:#f8fafc;color:#344054;font-weight:700;text-align:center',text:'改以右下角 m 表示：左上 m−11，右上 m−10，左下 m−1，右下 m'}));
  if(step>=5)wrap.appendChild(el('div',{style:'margin-top:8px;padding:10px;border-radius:8px;background:#fff7ed;color:#9a3412;font-weight:700;text-align:center',text:'四数和：(m−11)+(m−10)+(m−1)+m = 4m − 22'}));
  box.appendChild(wrap);
}

function cwTriangularNumbers(box,f,view,big,teacher,stepCount){
  var step=teacher&&!view.previewMode?(stepCount||99):Math.max(1,view.step||0),maxRows=f.terms.length;
  var shown=Math.max(1,Math.min(maxRows,Math.ceil(maxRows*Math.min(step,Math.max(1,stepCount||maxRows))/Math.max(1,stepCount||maxRows))));
  var wrap=el('div',{style:'max-width:760px;margin:10px auto;padding:12px;border:1px solid #d0d5dd;border-radius:12px;background:#fff'});
  var svg=cwNode('svg',{viewBox:'0 0 720 300',width:'100%',style:'display:block;max-height:'+(big?'38vh':'300px'),role:'img','aria-label':cwFigureText(f)});
  svg.appendChild(cwNode('text',{x:180,y:26,'text-anchor':'middle','font-size':17,'font-weight':700,fill:'#344054'},'\u4e09\u89d2\u70b9\u9635\uff1a\u6309\u5c42\u6570\u4e00\u6b65\u6b65\u52a0\u70b9'));
  var dotSize=24,baseX=180;
  for(var row=0;row<shown;row++){
    var count=row+1,y=54+row*dotSize,start=baseX-count*dotSize/2;
    for(var col=0;col<count;col++)svg.appendChild(cwNode('circle',{cx:start+col*dotSize+dotSize/2,cy:y+dotSize/2,r:7,fill:'#2563eb',stroke:'#17449b','stroke-width':1}));
    svg.appendChild(cwNode('text',{x:baseX+100,y:y+17,'font-size':14,fill:'#475467'},'\u7b2c '+count+' \u9879\uff1a'+f.terms[row]));
  }
  svg.appendChild(cwNode('line',{x1:360,y1:25,x2:360,y2:270,stroke:'#e4e7ec','stroke-width':2}));
  if(step>=stepCount){
    var n=maxRows,cell=24,x0=420,y0=63;
    svg.appendChild(cwNode('text',{x:535,y:27,'text-anchor':'middle','font-size':17,'font-weight':700,fill:'#344054'},'\u4e24\u4e2a\u4e09\u89d2\u5f62\u62fc\u6210\u957f\u65b9\u5f62'));
    for(var rr=0;rr<n;rr++)for(var cc=0;cc<n+1;cc++){
      var inTriangle=cc<=rr;
      svg.appendChild(cwNode('circle',{cx:x0+cc*cell,cy:y0+rr*cell,r:7,fill:inTriangle?'#2563eb':'#f59e0b',stroke:inTriangle?'#17449b':'#b45309','stroke-width':1}));
    }
    svg.appendChild(cwNode('text',{x:535,y:y0+n*cell+14,'text-anchor':'middle','font-size':14,'font-weight':700,fill:'#475467'},n+' × '+(n+1)+' = '+(n*(n+1))+' \u4e2a\u70b9\uff08\u4e24\u4efd\uff09'));
  }else{
    svg.appendChild(cwNode('text',{x:535,y:150,'text-anchor':'middle','font-size':16,fill:'#667085'},'\u6bcf\u4e00\u6b65\u65b0\u589e\u4e00\u5c42\u70b9'));
  }
  wrap.appendChild(svg);
  var sequence=f.terms.slice(0,shown).join(' \u2192 ')+(shown<maxRows?' \u2192 \u2026':'');
  wrap.appendChild(el('div',{style:'text-align:center;color:#344054;font-weight:700;margin:6px 0',text:sequence}));
  if(step>=stepCount){
    var formula=el('div',{style:'display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;margin-top:8px'});
    formula.appendChild(el('div',{style:'padding:8px 10px;border-radius:8px;background:#eff6ff;color:#17449b;font-weight:700;text-align:center',text:'\u7b2cn\u9879 = n(n+1) \u00f7 2'}));
    formula.appendChild(el('div',{style:'padding:8px 10px;border-radius:8px;background:#fff7ed;color:#9a3412;font-weight:700;text-align:center',text:'\u7b2c '+f.targetTerm+' \u9879 = '+f.targetTerm+' \u00d7 '+(f.targetTerm+1)+' \u00f7 2 = '+(f.targetTerm*(f.targetTerm+1)/2)}));
    wrap.appendChild(formula);
  }
}
function cwNineGrid(box,f,view,big,teacher,stepCount){
  var finalStep=Math.max(4,stepCount||4),step=teacher&&!view.previewMode?finalStep:Math.max(1,view.step||0),rows=f.rows||[];
  var pairs=[[[0,0],[2,2]],[[0,1],[2,1]],[[0,2],[2,0]],[[1,0],[1,2]]],
      colors=[['#e0f2fe','#0284c7'],['#dcfce7','#15803d'],['#fef3c7','#b45309'],['#fae8ff','#a21caf']],pairAt={};
  pairs.forEach(function(p,k){p.forEach(function(q){pairAt[q[0]+','+q[1]]=k})});
  var wrap=el('div',{style:'max-width:640px;margin:10px auto;padding:14px 16px 12px;border:1px solid #d0d5dd;border-radius:16px;background:linear-gradient(180deg,#fff,#f8fafc);box-shadow:0 8px 22px #10182810'});
  wrap.appendChild(el('div',{style:'text-align:center;color:#667085;font-size:'+(big?'1.4vh':'12px')+';font-weight:600;letter-spacing:.02em',text:'百数表九宫格：同行向右 +1，同列向下 +10'}));
  var grid=el('div',{style:'display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;max-width:'+(big?'480px':'360px')+';margin:8px auto'});
  rows.forEach(function(r,i){r.forEach(function(cell,j){
    var pair=step>=2&&pairAt[i+','+j]!=null?colors[pairAt[i+','+j]]:null,center=i===1&&j===1,active=center&&step>=3;
    var bg=active?'#1f6feb':pair?pair[0]:'#fff',bd=active?'#1f6feb':pair?pair[1]:'#d0d5dd',
        fg=active?'#fff':center?'#1f6feb':'#1c2333',
        label=center&&step>=4&&f.center!=null?String(f.center):cell;
    grid.appendChild(el('div',{style:'min-height:'+(big?'94px':'78px')+';display:flex;align-items:center;justify-content:center;border:2px solid '+bd+';border-radius:12px;background:'+bg+';color:'+fg+';font-weight:800;font-size:'+(big?'3vh':'22px')+';box-shadow:'+(active?'0 8px 18px #1f6feb55':'0 1px 3px #1018280f')+';transition:background .18s,border-color .18s,color .18s',text:label}));
  })});
  wrap.appendChild(grid);
  var caption=step>=4&&f.center!=null?'九数和 '+f.targetSum+' ÷ 9 = '+f.center+'（中心数）':step>=3?'九个数相加 = 9a':step>=2?'四组对称数，每组相加都等于 2a':'九个数的位置关系';
  wrap.appendChild(el('div',{style:'margin-top:10px;text-align:center;font-weight:700;color:'+(step>=3?'#17449b':'#475467')+';font-size:'+(big?'2.1vh':'15px'),text:caption}));
  box.appendChild(wrap);
}
function cwCalendarCompare(box,f,view,big,teacher){
  var wrap=el('div',{style:'max-width:920px;margin:10px auto;padding:14px;border:1px solid #d5dfef;border-radius:14px;background:#f8fbff'});
  wrap.appendChild(el('p',{style:'font-weight:700;margin:0 0 8px',text:'月历观察实验：先比较日期，再判断题目中的表达是否正确。'}));
  var options=[['A',4,1],['B',2,2],['C',1,3],['D',3,3]];
  var selected=view.calendarChoice||'A';
  var nav=el('div',{style:'display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px'});
  options.forEach(function(opt){
    var btn=el('button',{type:'button',style:'padding:8px 18px;border-radius:9px;border:2px solid '+(selected===opt[0]?'#2563eb':'#b7c8df')+';background:'+(selected===opt[0]?'#dbeafe':'#fff')+';font-weight:700',text:opt[0]+' · '+opt[1]+'×'+opt[2]});
    btn.onclick=function(){view.calendarChoice=opt[0];view.calendarFeedback=false;if(view._calendarOnChange)view._calendarOnChange();else cwRender(box.parentNode.parentNode,view._calendarCourseware,view,big,teacher)};
    nav.appendChild(btn);
  });
  wrap.appendChild(nav);
  var shape=options.filter(function(o){return o[0]===selected})[0]||options[0];
  var calendar=el('div',{style:'display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:3px;max-width:620px;margin:0 auto'});
  ['一','二','三','四','五','六','日'].forEach(function(d){calendar.appendChild(el('div',{style:'text-align:center;font-weight:700;color:#475569;padding:6px',text:d}))});
  for(var day=1;day<=35;day++){
    var row=Math.floor((day-1)/7),col=(day-1)%7,active=row>=1&&row<1+shape[2]&&col>=1&&col<1+shape[1];
    calendar.appendChild(el('div',{style:'text-align:center;padding:8px 0;min-height:24px;border:1px solid '+(active?'#2563eb':'#e2e8f0')+';border-radius:6px;background:'+(active?'#bfdbfe':'#fff')+';font-weight:'+(active?'700':'400'),text:day<=31?String(day):''}));
  }
  wrap.appendChild(calendar);
  wrap.appendChild(el('p',{style:'margin:10px 0 4px;color:#334155',text:'蓝色区域是 '+selected+' 的示意框形。想一想：横向与纵向每移动一格，日期分别怎样变化？'}));
  var question=selected==='C'?'如果最下方是 x，向上一格、两格分别应是什么？':selected==='D'?'中心对称的两格，与中心格有什么数量关系？':'这些蓝色日期能否支持题目对 '+selected+' 的描述？';
  wrap.appendChild(el('p',{style:'font-weight:600',text:question}));
  if(!teacher){
    var check=el('button',{type:'button',style:'padding:8px 14px;border:1px solid #2563eb;border-radius:8px;background:#fff;color:#1d4ed8',text:'我已思考，查看提示'});
    check.onclick=function(){view.calendarFeedback=true;if(view._calendarOnChange)view._calendarOnChange();else cwRender(box.parentNode.parentNode,view._calendarCourseware,view,big,teacher)};
    wrap.appendChild(check);
  }
  if(view.calendarFeedback||teacher&&!view.previewMode){
    wrap.appendChild(el('p',{style:'margin-top:10px;padding:10px;border-radius:8px;background:#eff6ff',text:'提示：同一行每向右一格加1，同一列每向下一格加7。请用这个规则自行核对题目表达。'}));
  }
  box.appendChild(wrap);
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
  if(f.type==='calendar_compare'){cwCalendarCompare(box,f,view,big,teacher);return}
  if(f.type==='calendar_cross'){cwCalendarCross(box,f,view,big,teacher);return}
  if(f.type==='seating_pattern'){cwSeatingPattern(box,f,view,big,teacher,stepCount);return}
  if(f.type==='alternating_triangle'){cwAlternatingTriangle(box,f,view,big,teacher,stepCount);return}
  if(f.type==='running_track'){cwRunningTrack(box,f,view,big,teacher,stepCount);return}
  if(f.type==='triangular_numbers'){cwTriangularNumbers(box,f,view,big,teacher,stepCount);return}
  if(f.type==='tile_pattern'){cwTilePattern(box,f,view,big,teacher,stepCount);return}
  if(f.type==='square_sticks_pattern'){cwSquareSticksPattern(box,f,view,big,teacher,stepCount);return}
  if(f.type==='hundred_chart_square'){cwHundredChartSquare(box,f,view,big,teacher,stepCount);return}
  f={type:f.type,reveal:f.reveal,nineGrid:f.nineGrid,targetSum:f.targetSum,center:f.center,points:(f.points||[]).slice().sort(function(a,b){return a.at-b.at}),marks:(f.marks||[]).filter(function(m){return m.from&&m.to}),
    boxes:f.boxes||[],branches:f.branches||[],shape:f.shape,labels:f.labels||{},rows:f.rows||[]};
  var visualStep=teacher&&!view.previewMode?(stepCount||1):(view.step||0),visualSteps=Math.max(1,stepCount||1);
  if(f.type==='table'){
    if(f.nineGrid){cwNineGrid(box,f,view,big,teacher,stepCount);return}
    var t=el('table',{style:'border-collapse:collapse;margin:0 auto;'+(big?'font-size:3vh':'')});
    var revealAll=f.reveal===false,maxCols=f.rows[0].length-1;
    var step=teacher&&!view.previewMode?Math.max(1,stepCount||maxCols):(view.step||0);
    var columns=revealAll?maxCols:Math.max(1,Math.min(maxCols,Math.ceil((step/Math.max(1,stepCount||maxCols))*maxCols)));
    f.rows.forEach(function(r,i){var tr=el('tr');r.forEach(function(c,j){var shown=i===0||j===0||j<=columns,current=!revealAll&&j===columns&&i>0;tr.appendChild(el(i?'td':'th',{style:'border:1px solid #98a2b3;padding:4px 12px;text-align:center;background:'+(current?'#dbeafe':'#fff')+';color:'+(shown?'#111':'#98a2b3'),text:shown?c:'·'}))});t.appendChild(tr)});
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
    function splitLabel(value){
      var source=String(value||''),parts=[],match=source.match(/^([^:：]{1,8})[:：]\s*(.*)$/);
      if(match&&match[2])parts=[match[1]+'：',match[2]];else parts=[source];
      var lines=[];
      parts.forEach(function(part){while(part.length>13){lines.push(part.slice(0,13));part=part.slice(13)}if(part)lines.push(part)});
      return lines.length?lines:[''];
    }
    function flowLabel(cx,cy,lines,size){
      var gap=size*1.3,firstY=cy-((lines.length-1)*gap)/2+size*0.35,node=cwNode('text',{x:cx,y:firstY,'font-size':size,'font-weight':700,'text-anchor':'middle',fill:'#111'});
      lines.forEach(function(line,index){node.appendChild(cwNode('tspan',{x:cx,dy:index===0?0:gap},line))});svg.appendChild(node);
    }
    function row(items,y,x0){
      var n=items.length,gap=34,w=Math.max(76,Math.min(178,(W-x0-20-Math.max(0,n-1)*gap)/Math.max(1,n))),x=x0;
      var active=Math.min(n-1,Math.max(0,Math.floor(Math.max(0,visualStep-1)*n/visualSteps)));
      items.forEach(function(t,i){
        var lines=splitLabel(t),size=lines.some(function(line){return line.length>10})?13:15;
        var boxH=Math.max(56,lines.length*size*1.3+18),fill=i===active?'#fef3c7':i<active?'#dcfce7':'#eff6ff';
        svg.appendChild(cwNode('rect',{x:x,y:y-boxH/2,width:w,height:boxH,rx:8,fill:fill,stroke:i===active?'#d97706':'#1d4ed8','stroke-width':i===active?3:2}));
        flowLabel(x+w/2,y,lines,size);
        if(i<n-1){svg.appendChild(cwNode('line',{x1:x+w+3,y1:y,x2:x+w+21,y2:y,stroke:'#1d2939','stroke-width':2}));svg.appendChild(cwNode('path',{d:'M'+(x+w+21)+' '+(y-5)+' L'+(x+w+27)+' '+y+' L'+(x+w+21)+' '+(y+5)+'Z',fill:'#1d2939'}))}
        x+=w+gap
      });
      return x
    }
    if(!f.branches.length)row(f.boxes,60,20);
    else{var endRow=row(f.boxes,130,20);f.branches.forEach(function(b,k){var y=k?200:60;
      svg.appendChild(cwNode('path',{d:'M'+(endRow-8)+' 130 L'+(endRow+10)+' '+y,fill:'none',stroke:'#1d2939','stroke-width':2}));
      txt(endRow+14,y-30,b.when,16,'start','#b42318');row(b.boxes,y,endRow+14)})}
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
  var wrap=el('div',{style:'max-width:980px;margin:0 auto;background:#fff;color:#111;border-radius:12px;padding:12px;line-height:1.75;'+(big?'font-size:2.8vh':'')});box.appendChild(wrap);
  wrap.appendChild(el('b',{text:p.title}));
  if(p.sourceProblem)wrap.appendChild(el('p',{style:'white-space:pre-wrap',text:p.sourceProblem}));
  if(p.figure&&p.figure.type==='calendar_compare')view._calendarCourseware={kind:'steps',params:p};
  cwFigure(wrap,p.figure,big,view,teacher,p.steps.length);
  if(p.sourceFigure&&p.sourceFigure.type==='uploaded_image')wrap.appendChild(el('details',{style:'margin:10px 0'},el('summary',{text:'\u67e5\u770b\u539f\u9898\u56fe\u7247\uff08\u5bf9\u7167\uff09'}),el('img',{src:p.sourceFigure.data_url,alt:p.sourceFigure.alt||'\u539f\u9898\u56fe\u7247',style:'display:block;max-width:100%;max-height:'+(big?'32vh':'260px')+';object-fit:contain;margin:8px auto;border:1px solid #e5e8f0;border-radius:8px'})));
  var shown=teacher?(view.previewMode?Math.max(1,view.step||0):p.steps.length):(view.step||0),list=el('ol',{style:'padding-left:1.6em;margin:12px 0'});
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
  function draw(){if(c.kind==='steps'&&c.params.figure&&c.params.figure.type==='calendar_compare')view._calendarOnChange=send;cwRender(stage,c,view,false,false,c.kind==='reading'?function(i){var k=view.highlight.indexOf(i);if(k>=0)view.highlight.splice(k,1);else view.highlight.push(i);draw();send()}:null)}
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
  var stageNo='3',msg=el('div',{role:'status','aria-live':'polite'}),data=null,busy=false,editorBox=null,notes={},rowEls={};
  function load(){api('/teacher/weekend/lessons/'+lessonId+'/courseware').then(paint).catch(function(e){box.textContent='';box.appendChild(el('div',{class:'notice error',text:e.message}))})}
  function itemAt(page){return (data.items||[]).filter(function(i){return String(i.stage)===stageNo&&i.page===page})[0]}
  function paint(d){
    data=d;rowEls={};box.textContent='';
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
    if(stageNo==='3'&&d.qualityAudit){
      var audit=d.qualityAudit;
      box.appendChild(el('div',{class:'notice warn',style:'margin:10px 0;white-space:normal',
        text:'课件逐页体检：共 '+audit.totalPages+' 页，已配置 '+audit.configured+' 页，发现明确问题 '+audit.flagged+' 页。全部仍须与原题逐页人工核对；机器未报警不等于验收通过。'}));
    }
    var rows=el('div'),editor=el('div');box.appendChild(rows);box.appendChild(editor);editorBox=editor;notes={};rowEls={};
    list.forEach(function(x){
      var it=itemAt(x.page),tag=!it?['','未生成']:it.status==='approved'?['ok','已审核']:it.approved?['warn','已审核·有新草稿']:['warn','草稿'];
      var line=el('div',{class:'item'},el('span',{class:'t'},el('b',{text:(x.page==null?'':'第'+(x.page+1)+'页：')+x.text}),
        el('div',{class:'row'},el('span',{class:'tag '+tag[0],text:tag[1]}),it?el('span',{class:'muted',text:d.kindLabels[it.kind]+(it.writtenTask?' · 含学生作答题':'')}):null)));
      if(stageNo==='3'&&d.qualityAudit&&x.page!=null){
        var auditRow=(d.qualityAudit.pages||[])[x.page];
        if(auditRow){
          var findings=(auditRow.issues||[]).concat(auditRow.warnings||[]);
          line.appendChild(el('div',{style:'flex-basis:100%;font-size:13px;color:'+(auditRow.issues.length?'#b42318':'#475467'),
            text:findings.length?'课件体检：'+findings.join('；'):'课件体检：暂无机器识别问题，仍须对照原题和课堂效果人工核对'}));
        }
      }
      var note=el('div',{role:'status','aria-live':'polite',style:'flex-basis:100%'});notes[String(x.page)]=note;
      line.appendChild(el('button',{text:it?'重新生成':'生成',onclick:function(e){
        if(busy){note.textContent='正在处理另一页，请等它完成后再点。';return}
        var b=e.target,label=b.textContent;busy=true;b.disabled=true;b.textContent='生成中…';
        note.className='notice';note.textContent='AI 正在为这一页生成课件，约十几秒，请稍候…';
        api('/teacher/weekend/lessons/'+lessonId+'/courseware/generate',{json:{stageNo:+stageNo,page:x.page}}).then(function(d){
          busy=false;paint(d);if(refresh)refresh();
          // Say it on this page's row (the list can be long), then open the new draft's preview.
          var n=notes[String(x.page)];if(n){n.className='notice ok';n.textContent='已生成新草稿'+(d.notice?'（'+d.notice+'）':'')+'，预览在下方，核对后点“审核通过”。'}
          openEditor(x,itemAt(x.page));
        }).catch(function(err){busy=false;b.disabled=false;b.textContent=label;note.className='notice error';note.textContent=err.message});
      }}));
      line.appendChild(el('button',{type:'button',text:it?'预览／修改':'手动填写',onclick:function(){openEditor(x,itemAt(x.page))}}));
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
      rows.appendChild(line);line.appendChild(note);rowEls[String(x.page)]=line;
    });
  }
  function openEditor(x,it){
    try{
      edit(editorBox,x,it);
      var target=rowEls[String(x.page)];
      if(target&&target.parentNode)target.parentNode.insertBefore(editorBox,target.nextSibling);
      if(editorBox&&editorBox.scrollIntoView)editorBox.scrollIntoView({block:'start',behavior:'smooth'});
    }catch(err){
      var note=notes[String(x.page)];
      if(note){note.className='notice error';note.textContent='预览打开失败：'+(err&&err.message?err.message:'页面脚本异常')}
    }
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
    box2.textContent='';var card=el('div',{class:'card'}),fields={},kinds=data.templates,kind=it&&it.kind?it.kind:kinds[kinds.length-1],p=JSON.parse(JSON.stringify(it&&it.params?it.params:{})),previewState={step:1,previewMode:true},preview=el('div',{class:'card',style:'max-height:76vh;overflow:auto;box-shadow:0 8px 24px #10182822'});
    if(kind==='steps'){
      if(!p || typeof p!=='object')p={};
      if(!Array.isArray(p.steps))p.steps=[];
      if(!p.figure || typeof p.figure!=='object')p.figure={type:''};
      // The legacy example-16 table is an answer key, not a useful calendar diagram.
      // Upgrade only this recognisable legacy rendering; preserve teacher-authored steps.
      var calendarSource=String(x.text||'')+' '+String(p.problem||'')+' '+String(p.title||'');
      if(calendarSource.indexOf('月历')>=0 &&
         (calendarSource.indexOf('框形辨析')>=0||calendarSource.indexOf('哪一种错误')>=0||calendarSource.indexOf('哪种错误')>=0)){
        var oldCalendarTable=p.figure.type==='table' && (p.figure.rows||[]).some(function(r){
          return (r||[]).some(function(c){return String(c).indexOf('月历关系')>=0||String(c).indexOf('竖列差10')>=0});
        });
        if(oldCalendarTable||!p.figure.type){
          p.figure={type:'calendar_compare'};
          if((p.steps||[]).some(function(line){return /选项C写成|因此C错误|竖列三格应相差7/.test(String(line))})){
            p.steps=['观察月历：同一行、同一列的相邻日期分别怎样变化？',
                     '切换A与B的框形，检查横向与纵向关系是否符合题意。',
                     '检查C：若最下格为x，从下往上另外两格该怎样表达？',
                     '比较D中中心对称的日期，再逐项判断并说出理由。'];
          }
        }
      }
      var sourceText=String(x.text||'')+' '+String(p.problem||'')+' '+String(p.sourceProblem||''),normalizedSource=sourceText.replace(/[\s"'“”‘’「」『』]/g,''),required=null;
      if(normalizedSource.indexOf('田字形')>=0&&normalizedSource.indexOf('百数表')>=0){required={type:'hundred_chart_square',topLeftNumber:45};}
      else if(sourceText.indexOf('地砖')>=0&&(sourceText.indexOf('排列')>=0||sourceText.indexOf('白地砖')>=0)){
        function values(re){var out=[],m;re.lastIndex=0;while((m=re.exec(sourceText))!==null)out.push(Number(m[1]));return out}
        var white=values(/(\d+)\s*块白地砖/g),blue=values(/(\d+)\s*块蓝地砖/g),term=sourceText.match(/当\s*n\s*[=＝]\s*(\d+)/),target=sourceText.match(/(?:用了|用)\s*(\d+)\s*块蓝(?:色)?砖/);
        required={type:'tile_pattern',whiteCounts:white.length>=2?white.slice(0,2):[5,8],blueCounts:blue.length>=2?blue.slice(0,2):[4,7],targetTerm:term?Number(term[1]):10,targetBlue:target?Number(target[1]):100};
      }else if(sourceText.indexOf('正方形')>=0&&sourceText.indexOf('小棒')>=0&&/4\s*根/.test(sourceText)&&/7\s*根/.test(sourceText)&&/10\s*根/.test(sourceText)){
        var mts=[],mm,mRe=/m\s*[=＝]\s*(\d+)/g;while((mm=mRe.exec(sourceText))!==null)mts.push(Number(mm[1]));var nt=sourceText.match(/n\s*[=＝]\s*(\d+)/);
        required={type:'square_sticks_pattern',sampleCounts:[4,7,10],targetSquares:mts.length>=2?mts.slice(0,2):[8,60],targetSticks:nt?Number(nt[1]):100};
      }else if(sourceText.indexOf('方桌')>=0&&(sourceText.indexOf('可坐')>=0||sourceText.indexOf('拼')>=0))required={type:'seating_pattern',sampleCounts:[8,12,16]};
      if(required){
        // Legacy saved slides may contain the wrong figure parameters; infer the pictured counts from the actual problem text.
        p.figure=required;
        if(required.type==='hundred_chart_square'&&(!(p.steps||[]).some(function(q){return /4n\s*[+＋]\s*22/.test(String(q))})||(p.steps||[]).some(function(q){return String(q).indexOf('点下一步显示')>=0})))p.steps=['百数表中，同一行向右相邻数相差1，同一列向下相邻数相差10。','设田字格左上角为n，则右上是n+1，左下是n+10，右下是n+11。','四数相加：n+(n+1)+(n+10)+(n+11)=4n+22。','若右下角为m，则左上m−11，右上m−10，左下m−1。','四数和：(m−11)+(m−10)+(m−1)+m=4m−22。'];
        if(required.type==='square_sticks_pattern'&&!(p.steps||[]).some(function(q){return /共用边|新增3根|3m\s*[+＋]\s*1/.test(String(q))}))p.steps=['观察：摆1个正方形用4根；摆2个共用一条边，只需新增3根，共7根；摆3个再新增3根，共10根。','发现：每增加1个正方形，都会和前一个共用一条边，所以只增加3根小棒。','列式：摆m个，先用4根，后面m−1个各增加3根，n=4+3(m−1)=3m+1。','代入：m=8时n=25；m=60时n=181。','反求：n=100时，3m+1=100，所以m=33。'];
        if(required.type==='seating_pattern'&&!(p.steps||[]).some(function(q){return /周长|外周/.test(String(q))}))p.steps=['1张方桌是一块单位正方形，外周有4条单位边，每条边坐2人，共8人。','拼接时相邻方桌共用一条边；共用边在内部，不算外周。','m张连成一排：外周单位边数 = 4m − 2(m−1) = 2m+2。','每条外周单位边坐2人：人数 = 2(2m+2) = 4m+4。'];
      }
    }
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
        var f=p.figure||{},choices=[['','不画图'],['segment','线段和点'],['flow','计算程序图'],['shape','图形'],['table','数表'],['calendar_compare','月历框形辨析'],['calendar_cross','\u6708\u5386\u5341\u5b57\u6846'],['seating_pattern','方桌人数规律'],['alternating_triangle','黑白棋子三角形'],['running_track','环形跑道追及'],['triangular_numbers','三角形数规律'],['tile_pattern','地砖排列规律'],['square_sticks_pattern','连续正方形小棒规律'],['hundred_chart_square','百数表田字形四数规律']];if(f.type==='uploaded_image')choices.unshift(['uploaded_image','原卷图片']);var ft=sel(choices,f.type||'');
        field('figType','图示（大屏上画出题目条件）',ft);ft.onchange=function(){var keep=collect();keep.figure=ft.value==='calendar_compare'?{type:ft.value}:ft.value==='calendar_cross'?{type:ft.value,center:18,daysInMonth:31,firstWeekday:0,total:90}:ft.value==='seating_pattern'?{type:ft.value,sampleCounts:[8,12,16]}:ft.value==='alternating_triangle'?{type:ft.value,rows:6,differenceSymbol:'m'}:ft.value==='running_track'?{type:ft.value,fastSpeed:180,slowSpeed:140,distanceSymbol:'s'}:ft.value==='triangular_numbers'?{type:ft.value,terms:[1,3,6,10,15],targetTerm:10}:ft.value==='tile_pattern'?{type:ft.value,whiteCounts:[5,8],blueCounts:[4,7],targetTerm:10,targetBlue:100}:ft.value==='square_sticks_pattern'?{type:ft.value,sampleCounts:[4,7,10],targetSquares:[8,60],targetSticks:100}:ft.value==='hundred_chart_square'?{type:ft.value,topLeftNumber:45}:{type:ft.value,points:[],marks:[],boxes:[],branches:[],labels:{},rows:[],shape:'rectangle'};p=keep;build()};
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
        }else if(f.type==='triangular_numbers'){
          field('figTerms','\u4e09\u89d2\u5f62\u6570\u6837\u4f8b\uff08\u9017\u53f7\u5206\u9694\uff09',input((f.terms||[1,3,6,10,15]).join(', ')));field('figTarget','\u9898\u76ee\u95ee\u7b2c\u51e0\u9879',input(f.targetTerm||10));
        }else if(f.type==='tile_pattern'){
          field('figWhiteCounts','\u524d\u4e24\u5e45\u767d\u5730\u7816\u6570\uff08\u9017\u53f7\u5206\u9694\uff09',input((f.whiteCounts||[5,8]).join(', ')));
          field('figBlueCounts','\u524d\u4e24\u5e45\u84dd\u5730\u7816\u6570\uff08\u9017\u53f7\u5206\u9694\uff09',input((f.blueCounts||[4,7]).join(', ')));
          field('figTarget','\u9898\u76ee\u95ee\u7684\u5e45\u6570 n',input(f.targetTerm||10));field('figBlueTarget','\u9898\u76ee\u7ed9\u51fa\u7684\u84dd\u7816\u6570',input(f.targetBlue||100));
        }else if(f.type==='square_sticks_pattern'){
          field('figSquareCounts','小棒样例数量（4、7、10）',input((f.sampleCounts||[4,7,10]).join(', ')));
          field('figTargets','题目给出的m值（两个，逗号分隔）',input((f.targetSquares||[8,60]).join(', ')));
          field('figTargetSticks','题目给出的n值',input(f.targetSticks||100));
        }else if(f.type==='hundred_chart_square'){
          field('figHundredTop','百数表田字格左上角示意数（1—89，不能在整十列）',input(f.topLeftNumber||45));
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
      if(t==='calendar_compare')return {type:t};
      if(t==='calendar_cross')return {type:t,center:Number(fields.figCenter.value),daysInMonth:Number(fields.figDays.value),firstWeekday:Number(fields.figWeekday.value),total:Number(fields.figTotal.value)};
      if(t==='seating_pattern')return {type:t,sampleCounts:parts(fields.figCounts.value,/,/).map(function(x){return Number(x)})};
      if(t==='alternating_triangle')return {type:t,rows:Number(fields.figRows.value),differenceSymbol:fields.figDiff.value};
      if(t==='running_track')return {type:t,fastSpeed:Number(fields.figFast.value),slowSpeed:Number(fields.figSlow.value),distanceSymbol:fields.figDistanceSymbol.value};
      if(t==='triangular_numbers')return {type:t,terms:parts(fields.figTerms.value,/,/).map(function(x){return Number(x)}),targetTerm:Number(fields.figTarget.value)};
      if(t==='tile_pattern')return {type:t,whiteCounts:parts(fields.figWhiteCounts.value,/,/).map(function(x){return Number(x)}),blueCounts:parts(fields.figBlueCounts.value,/,/).map(function(x){return Number(x)}),targetTerm:Number(fields.figTarget.value),targetBlue:Number(fields.figBlueTarget.value)};
      if(t==='square_sticks_pattern')return {type:t,sampleCounts:parts(fields.figSquareCounts.value,/,/).map(function(x){return Number(x)}),targetSquares:parts(fields.figTargets.value,/,/).map(function(x){return Number(x)}),targetSticks:Number(fields.figTargetSticks.value)};
      if(t==='hundred_chart_square')return {type:t,topLeftNumber:Number(fields.figHundredTop.value)};
      if(!fields.figA)return {type:t,points:[],marks:[],boxes:[],branches:[],labels:{},rows:[],shape:'rectangle'};
      if(t==='segment')return {type:t,points:parts(fields.figA.value,/[;；]/).map(function(x){var k=x.split(/[:：]/);return {name:(k[0]||'').trim(),at:Number((k[1]||'').trim())}}),
        marks:parts(fields.figB.value,/[;；]/).map(function(x){var k=x.split(/[:：]/),ab=(k[0]||'').split(/[-－—]/);return {from:(ab[0]||'').trim(),to:(ab[1]||'').trim(),label:(k.slice(1).join(':')||'').trim()}})};
      if(t==='flow')return {type:t,boxes:parts(fields.figA.value,/→|->|>/),branches:lines(fields.figB).map(function(x){var k=x.split(/[:：]/);return {when:(k[0]||'').trim(),boxes:parts(k.slice(1).join(':'),/→|->|>/)}})};
      if(t==='shape'){var keys={'上':'top','下':'bottom','左':'left','右':'right','高':'height'},labels={};
        parts(fields.figA.value,/[;；]/).forEach(function(x){var k=x.split(/[:：]/);if(keys[(k[0]||'').trim()])labels[keys[k[0].trim()]]=k.slice(1).join(':').trim()});
        return {type:t,shape:fields.figShape.value,labels:labels}}
      var table={type:t,rows:lines(fields.figA).map(function(r){return parts(r,'|')})};
      if(p.figure&&p.figure.reveal===false)table.reveal=false;
      if(p.figure&&p.figure.nineGrid){table.nineGrid=true;table.targetSum=p.figure.targetSum;table.center=p.figure.center}
      return table;
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
        if(v.figure&&v.figure.type==='calendar_compare')previewState._calendarOnChange=show;
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


