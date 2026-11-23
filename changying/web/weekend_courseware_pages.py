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
// 图示的文字描述：任何字段缺失时都只给一句读得懂的话，绝不抛异常（老师看到的不能是白屏）。
function cwFigureText(f){
  f=f||{};
  var points=f.points||[],marks=f.marks||[],boxes=f.boxes||[],branches=f.branches||[],sampleCounts=f.sampleCounts||[],
      whiteCounts=f.whiteCounts||[],blueCounts=f.blueCounts||[],terms=f.terms||[],rows=f.rows||[],labels=f.labels||{},
      unit=f.unit||'',missing='（数据不全）';
  if(f.type==='segment')return '线段上的点：'+(points.length?points.map(function(q){return q.name}).join(' — '):'还没有标点')+(marks.length?'；'+marks.map(function(m){return m.from+m.to+'＝'+m.label}).join('，'):'');
  if(f.type==='flow')return '程序：'+(boxes.length?boxes.join(' → '):'还没有方框')+(branches.length?'；'+branches.map(function(b){return b.when+'：'+((b.boxes||[]).join(' → '))}).join('；'):'');
  if(f.type==='shape')return (CW_SHAPES[f.shape]||'图形')+'：'+Object.keys(labels).map(function(k){return labels[k]}).join('，');
  if(f.type==='equal_base_height')return '三个平行四边形：底均为 '+f.base+' cm，高均为 '+f.height+' cm';
  if(f.type==='parallelogram_thirds')return '平行四边形底边三等分，中间部分涂色，高不变，总面积 '+f.totalArea+' cm²';
  if(f.type==='parallelogram_methods')return '平行四边形面积公式：①②③④四种剪拼、平移或旋转方法（示意图，含中点M、N和垂足）';
  if(f.type==='calendar_compare')return '月历四种框形：A一行四格、B两行两列、C一列三格、D三行三列';
  if(f.type==='calendar_cross')return '\u6708\u5386\u5341\u5b57\u6846\uff1a\u4e2d\u5fc3 '+f.center+'\uff0c\u4e94\u6570\u548c '+f.total;
  if(f.type==='seating_pattern')return '\u65b9\u684c\u4eba\u6570\u89c4\u5f8b\uff1a'+(sampleCounts.length?sampleCounts.join('\u3001'):missing);
  if(f.type==='alternating_triangle')return '\u9ed1\u767d\u68cb\u5b50\u4e09\u89d2\u5f62\uff1a'+f.rows+'\u5c42\uff0c\u5dee\u503c '+f.differenceSymbol;
  if(f.type==='running_track')return '\u540c\u5411\u73af\u5f62\u8dd1\u9053\uff1a'+f.fastSpeed+'\u7c73/\u5206\u949f\u548c '+f.slowSpeed+'\u7c73/\u5206\u949f\uff0c\u8dd1\u9053\u5468\u957f '+f.distanceSymbol;
  if(f.type==='triangular_numbers')return '\u4e09\u89d2\u5f62\u6570\uff1a'+(terms.length?terms.join('\u3001'):missing)+'\uff0c\u6c42\u7b2c '+f.targetTerm+' \u9879';
  if(f.type==='tile_pattern')return '\u5730\u7816\u6392\u5217\u89c4\u5f8b\uff1a\u767d\u7816 '+(whiteCounts.length?whiteCounts.join('\u3001'):missing)+'\uff0c\u84dd\u7816 '+(blueCounts.length?blueCounts.join('\u3001'):missing);
  if(f.type==='square_sticks_pattern')return '\u8fde\u7eed\u6b63\u65b9\u5f62\u4e0e\u5c0f\u68d2\uff1a'+(sampleCounts.length?sampleCounts.join('\u3001'):missing)+'\u6839\uff1b\u5171\u7528\u8fb9\u53ea\u7b97\u4e00\u6839';
  if(f.type==='hundred_chart_square')return '\u767e\u6570\u8868\u7530\u5b57\u683c\uff1a'+f.topLeftNumber+'\uff1b\u6a2a\u5411\u76f8\u5dee1\uff0c\u7eb5\u5411\u76f8\u5dee10';
  if(f.type==='obtuse_triangle_height')return '\u949d\u89d2\u4e09\u89d2\u5f62\uff1a\u5e95 BC='+(f.base==null?missing:f.base+unit)+'\uff0c\u659c\u8fb9 AC='+(f.side==null?missing:f.side+unit)+'\uff0c\u5e95\u8fb9\u5ef6\u957f\u7ebf\u4e0a\u7684\u9ad8='+(f.height==null?missing:f.height+unit);
  if(rows.length)return rows.map(function(r){return (r||[]).join(' | ')}).join('\n');
  return '\u56fe\u793a\uff1a'+((f.type&&CW_SHAPES[f.type])||f.type||'\u672a\u77e5\u7c7b\u578b')+missing;
}
function cwFigureOk(f){
  if(f.type==='uploaded_image')return /^data:image\/(jpeg|png);base64,/.test(String(f.data_url||''));
  if(f.type==='segment'){var at=(f.points||[]).map(function(q){return q.at});return at.length>=2&&at.every(function(a){return isFinite(a)})&&Math.max.apply(null,at)>Math.min.apply(null,at)}
  if(f.type==='flow')return (f.boxes||[]).length>0||(f.branches||[]).length>0;
  if(f.type==='shape')return !!CW_SHAPES[f.shape];
  if(f.type==='equal_base_height')return isFinite(f.base)&&f.base>0&&isFinite(f.height)&&f.height>0;
  if(f.type==='parallelogram_thirds')return f.parts===3&&isFinite(f.totalArea)&&f.totalArea>0;
  if(f.type==='parallelogram_methods')return true;
  if(f.type==='calendar_compare')return true;
  if(f.type==='calendar_cross')return isFinite(f.center)&&isFinite(f.daysInMonth)&&isFinite(f.firstWeekday)&&isFinite(f.total)&&f.center===f.total/5;
  if(f.type==='seating_pattern')return (f.sampleCounts||[]).length>=2&&f.sampleCounts.length<=4&&f.sampleCounts[0]===8&&f.sampleCounts.every(function(n,i){return isFinite(n)&&n===8+i*4});
  if(f.type==='alternating_triangle')return f.rows>=4&&f.rows<=8&&f.rows%2===0&&/^[A-Za-z]$/.test(f.differenceSymbol||'');
  if(f.type==='running_track')return f.fastSpeed>f.slowSpeed&&f.slowSpeed>0&&/^[A-Za-z]$/.test(f.distanceSymbol||'');
  if(f.type==='triangular_numbers')return (f.terms||[]).length>=3&&f.terms.every(function(n,i){return n===(i+1)*(i+2)/2})&&f.targetTerm>=2&&f.targetTerm<=100;
  if(f.type==='tile_pattern')return (f.whiteCounts||[]).length===2&&(f.blueCounts||[]).length===2&&f.whiteCounts[1]>f.whiteCounts[0]&&f.blueCounts[1]>f.blueCounts[0]&&f.targetTerm>=1&&f.targetTerm<=100&&f.targetBlue>=1;
  if(f.type==='square_sticks_pattern')return (f.sampleCounts||[]).join(',')==='4,7,10'&&(f.targetSquares||[]).length===2&&f.targetSquares.every(function(n){return n>=1&&n<=1000})&&f.targetSticks>=4&&f.targetSticks<=10000;
  if(f.type==='hundred_chart_square')return f.topLeftNumber>=1&&f.topLeftNumber<=89&&f.topLeftNumber%10!==0;
  // 钝角三角形的高：底、斜边、高都必须是正数，否则不画（走“图示还没填完整”）。
  if(f.type==='obtuse_triangle_height')return isFinite(f.base)&&f.base>0&&isFinite(f.side)&&f.side>0&&isFinite(f.height)&&f.height>0&&f.side>=f.base;
  return (f.rows||[]).length>0;
}
function cwCalendarCross(box,f,view,big,teacher){
  var step=teacher&&!view.previewMode?4:(view.step||0),wrap=el('div',{style:'max-width:560px;margin:8px auto;padding:12px;border:1px solid #d0d5dd;border-radius:12px;background:#fff'});
  box.appendChild(wrap);wrap.appendChild(el('div',{style:'text-align:center;font-weight:700;margin-bottom:8px',text:step<2?'观察月历：相邻日期分别怎样变化？':'月历规律：左右相差1，上下相差7'}));
  var grid=el('div',{style:'display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:4px'}),names=['\u65e5','\u4e00','\u4e8c','\u4e09','\u56db','\u4e94','\u516d'];
  names.forEach(function(n){grid.appendChild(el('div',{style:'text-align:center;color:#667085;font-size:12px;padding:4px 0',text:n}))});
  var count=f.firstWeekday+f.daysInMonth;for(var i=0;i<Math.ceil(count/7)*7;i++){
    var day=i-f.firstWeekday+1;if(day<1||day>f.daysInMonth){grid.appendChild(el('div',{style:'aspect-ratio:1'}));continue}
    var diff=day-f.center,active=day===f.center||(step>=1&&Math.abs(diff)===1)||(step>=2&&Math.abs(diff)===7),center=day===f.center;
    var label='';if(step>=3&&active)label=center?'a':diff===-7?'a-7':diff===-1?'a-1':diff===1?'a+1':'a+7';
    var style='aspect-ratio:1;min-height:32px;display:flex;flex-direction:column;align-items:center;justify-content:center;border-radius:8px;font-weight:700;font-size:'+(big?'2.5vh':'14px')+';background:'+(active?(center?'#f5b942':'#2364e8'):'#f2f4f7')+';color:'+(active?(center?'#412b00':'#fff'):'#475467')+';border:'+(active?'2px solid '+(center?'#d49413':'#2364e8'):'2px solid transparent');
    var visibleDay=active&&!teacher&&!view.showAnswer?(center?'a':step>=3?label:'？'):String(day);
    grid.appendChild(el('div',{style:style},el('span',{text:visibleDay}),label&&(!active||teacher||view.showAnswer)?el('small',{style:'font-size:10px;line-height:1.1',text:label}):null));
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
  // A、B 两点：A 是同一起点，B 是快者多跑一整圈的位置，方便学生指着图说理。
  function point(x,y,name){svg.appendChild(cwNode('rect',{x:x-9,y:y-9,width:18,height:18,rx:4,fill:'#fff',stroke:'#1d2939','stroke-width':3}));svg.appendChild(cwNode('text',{x:x,y:y+6,'text-anchor':'middle','font-size':14,'font-weight':700,fill:'#111'},name))}
  point(95,145,'A');point(585,145,'B');
  function runner(a,color,label,speed){var x=340+245*Math.cos(a),y=145+92*Math.sin(a);svg.appendChild(cwNode('circle',{cx:x,cy:y,r:16,fill:color,stroke:'#fff','stroke-width':3}));svg.appendChild(cwNode('text',{x:x,y:y+5,'text-anchor':'middle','font-size':14,'font-weight':700,fill:'#fff'},label));svg.appendChild(cwNode('text',{x:x,y:y+34,'text-anchor':'middle','font-size':15,'font-weight':700,fill:color},speed+'\u7c73/\u5206'))}
  runner(angleFast,'#dc2626','\u5feb',f.fastSpeed);runner(angleSlow,'#2563eb','\u6162',f.slowSpeed);
  wrap.appendChild(svg);
  wrap.appendChild(el('div',{style:'font-weight:700;color:#17449b;font-size:'+(big?'2.3vh':'16px'),text:'\u7b2c '+shown+' \u5206\u949f\uff1a\u5feb\u8005\u591a\u8dd1 '+gap+' \u7c73\uff1b\u6bcf\u5206\u949f\u8def\u7a0b\u5dee '+f.fastSpeed+' - '+f.slowSpeed+' = '+(f.fastSpeed-f.slowSpeed)+' \u7c73\uff08\u6bcf\u5206\u949f\u591a\u8dd1 '+(f.fastSpeed-f.slowSpeed)+' \u7c73\uff09'}));
  if(step>=stepCount)wrap.appendChild(el('div',{style:'margin-top:8px;color:#b42318;font-weight:700',text:'\u8def\u7a0b\u5dee\u8fbe\u5230\u4e00\u5708 '+f.distanceSymbol+' \u7c73\u65f6\u8ffd\u4e0a\uff1a'+f.distanceSymbol+' \u00f7 ('+f.fastSpeed+' - '+f.slowSpeed+') = '+f.distanceSymbol+' / '+(f.fastSpeed-f.slowSpeed)+' \u5206\u949f'}));
  box.appendChild(wrap);
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
  box.appendChild(wrap);
}
function cwNineGrid(box,f,view,big,teacher,stepCount){
  var finalStep=Math.max(4,stepCount||4),step=teacher&&!view.previewMode?finalStep:Math.max(1,view.step||0),rows=f.rows||[];
  // Example 15: keep the existing 3×3 visual style, but synchronize
  // all nine labels with its six classroom steps. Other grids are unchanged.
  var lesson15=f.nineGrid===true && Number(f.targetSum)===2016
      && Number(f.center)===224 && stepCount===6;
  if(lesson15){
    var step15=teacher&&!view.previewMode?6:Math.max(0,Math.min(6,view.step||0));
    var answer15=!!view.showAnswer||(teacher&&(!view.previewMode||step15>=6));
    var cells15=[['a−11','a−10','a−9'],['a−1','a','a+1'],['a+9','a+10','a+11']];
    var appearAt=[[4,3,4],[2,1,2],[4,3,4]];
    var wrap15=el('div',{style:'max-width:640px;margin:10px auto;padding:14px 16px 12px;border:1px solid #d0d5dd;border-radius:16px;background:linear-gradient(180deg,#fff,#f8fafc);box-shadow:0 8px 22px #10182810'});
    wrap15.appendChild(el('div',{style:'text-align:center;color:#667085;font-size:'+(big?'1.4vh':'12px')+';font-weight:600',text:step15>=3?'每行10个数：横向相邻差1，纵向相邻差10':'观察每行10个数的数表，逐步填写九宫格'}));
    var grid15=el('div',{style:'display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;max-width:'+(big?'480px':'360px')+';margin:8px auto'});
    cells15.forEach(function(row,i){row.forEach(function(val,j){
      var rank=appearAt[i][j],visible=step15>=rank,center=i===1&&j===1,
          newCell=visible&&step15===rank,finalCenter=center&&step15>=6&&answer15,
          bg=finalCenter?'#1f6feb':newCell?'#dbeafe':visible?'#eff6ff':'#fff',
          bd=finalCenter?'#1f6feb':newCell?'#2563eb':'#d0d5dd',
          fg=finalCenter?'#fff':visible?'#173b70':'#98a2b3',
          label=visible?(finalCenter?'224':val):'？';
      grid15.appendChild(el('div',{style:'min-height:'+(big?'94px':'78px')+';display:flex;align-items:center;justify-content:center;border:2px solid '+bd+';border-radius:12px;background:'+bg+';color:'+fg+';font-weight:800;font-size:'+(big?'3vh':'22px')+';transition:background .18s,border-color .18s,color .18s',text:label}));
    })});
    wrap15.appendChild(grid15);
    var tip15=step15>=6&&answer15?'九数和为 2016：9a = 2016，a = 224':
              step15>=6?'九数和为 2016：9a = 2016':
              step15>=5?'九个数相加，对称数相互抵消：九数和 = 9a':
              step15>=4?'四个角已补齐：上下移动10，左右移动1':
              step15>=3?'上面是 a−10，下面是 a+10':
              step15>=2?'左边是 a−1，右边是 a+1':
              step15>=1?'先把九宫格中心数设为 a':'先观察题目，再逐步揭示数量关系';
    wrap15.appendChild(el('div',{style:'margin-top:10px;text-align:center;font-weight:700;color:'+(step15>=5?'#17449b':'#475467')+';font-size:'+(big?'2.1vh':'15px'),text:tip15}));
    box.appendChild(wrap15);
    return;
  }
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

function cwParallelogramMethods(box,view,big,teacher){
  // Four distinct panels redrawn from the supplied lesson 11 exercise (not
  // a fabricated solution key). One highlighted method per teacher step.
  var wrap=el('div',{style:'max-width:980px;margin:6px auto;padding:8px;border:1px solid #d0d5dd;border-radius:10px;background:#fff'});
  box.appendChild(wrap);
  if(!document.createElementNS||!cwNode('svg',{}).createSVGRect){
    wrap.appendChild(el('p',{text:'原题图示：① 剪下的三角形平移补成长方形；② 平移后仍需判断目标图形；③ 经过两边中点M、N的剪拼和旋转；④ 利用高进行旋转割补。'}));
    return;
  }
  var svg=cwNode('svg',{viewBox:'0 0 760 210',width:'100%',style:'display:block;max-height:'+(big?'43vh':'330px'),role:'img','aria-label':cwFigureText({type:'parallelogram_methods'})});
  var focused=(view&&view.step>0)?Math.max(1,Math.min(4,view.step)):(teacher&&view&&view.previewMode?1:0);
  function node(g,t,attrs,value){var n=cwNode(t,attrs,value);g.appendChild(n);return n}
  function path(g,d,stroke,dash,width){return node(g,'path',{d:d,fill:'none',stroke:stroke||'#283949','stroke-width':width||2.3,'stroke-dasharray':dash||''})}
  function poly(g,points,fill,dash){return node(g,'polygon',{points:points,fill:fill||'#e5f2fc',stroke:'#263647','stroke-width':2.2,'stroke-dasharray':dash||''})}
  function label(g,x,y,value,size){return node(g,'text',{x:x,y:y,'font-size':size||16,fill:'#253647','text-anchor':'middle','font-weight':600},value)}
  function arrow(g,d,x,y,orientation){
    path(g,d,'#235e97','',2.5);
    if(orientation==='up')poly(g,(x-5)+','+(y+8)+' '+x+','+y+' '+(x+5)+','+(y+8),'#235e97');
    else if(orientation==='left')poly(g,(x+8)+','+(y-5)+' '+x+','+y+' '+(x+8)+','+(y+5),'#235e97');
    else poly(g,(x-8)+','+(y-5)+' '+x+','+y+' '+(x-8)+','+(y+5),'#235e97');
  }
  var labels=['①','②','③','④'];
  for(var i=0;i<4;i++){
    var g=node(svg,'g',{transform:'translate('+(i*190)+',0)'});
    node(g,'rect',{x:4,y:36,width:181,height:145,rx:9,fill:focused===i+1?'#fff7df':'#fff',stroke:focused===i+1?'#d97706':'#cbd5e1','stroke-width':focused===i+1?3:1.5});
    label(g,94,25,labels[i],25);
    if(i===0){
      // Option ①: a left triangle relocates to the opposite side.
      poly(g,'55,64 151,64 151,160 55,160');
      path(g,'M 23 160 L 55 64 L 23 64','#87919d','5 4');
      path(g,'M 55 64 L 55 160','#283949','',2.3);
      path(g,'M 120 64 L 90 160','#283949','',2.3);
      path(g,'M 55 149 L 66 149 L 66 160','#283949','',1.7);
      arrow(g,'M 43 111 L 140 111',140,111,'right');
    }else if(i===1){
      // Option ②: the illustrated transfer does not by itself make a rectangle.
      poly(g,'60,64 141,64 169,160 88,160');
      path(g,'M 28 160 L 60 64','#87919d','5 4');
      path(g,'M 141 64 L 113 160','#283949','',2.3);
      arrow(g,'M 35 112 L 158 112',158,112,'right');
    }else if(i===2){
      // Option ③: both side midpoints M,N and two rotating end parts.
      poly(g,'48,66 151,66 151,159 48,159','#f4f9fd');
      path(g,'M 28 159 L 53 66 L 172 66 L 151 159','#8d99a8','5 4',1.8);
      path(g,'M 48 112 L 151 112','#235e97','5 3',1.8);
      label(g,50,104,'N',16);label(g,149,104,'M',16);
      path(g,'M 49 148 L 61 148 L 61 159','#283949','',1.5);
      arrow(g,'M 38 77 Q 18 108 42 135',42,135,'right');
      arrow(g,'M 159 76 Q 183 113 154 142',154,142,'left');
    }else{
      // Option ④: triangle pivots about an edge; base and altitude marked.
      path(g,'M 21 68 L 151 68 L 151 159 L 21 159 Z','#8995a5','5 4',2);
      poly(g,'21,159 79,102 180,102 151,159');
      path(g,'M 79 102 L 79 159','#263647','',2.2);
      path(g,'M 79 149 L 89 149 L 89 159','#263647','',1.6);
      label(g,93,133,'高',15);
      arrow(g,'M 152 45 Q 180 35 177 75',177,75,'right');
    }
  }
  wrap.appendChild(svg);
  var methodHints=[
    '第 1 步看图①：沿高剪下左边的直角三角形，向右平移拼成长方形。',
    '第 2 步看图②：沿斜边剪下并平移后，拼出的图形还是平行四边形还是长方形？',
    '第 3 步看图③：经过两边中点 M、N 剪下两个小三角形并旋转，拼成什么图形？',
    '第 4 步看图④：以高为界旋转割补，观察面积有没有变化。'
  ];
  wrap.appendChild(el('p',{class:'muted',style:'margin:4px 0;font-size:12px',text:focused?methodHints[focused-1]:'依据原练习①②③④重绘的操作示意图；观察剪拼与旋转方向，先讨论，再判断。'}));
}

function cwEqualBaseHeight(box,f,view,big,teacher,stepCount){
  view=view||{};
  var steps=Math.max(4,stepCount||4),step=teacher&&!view.previewMode?steps:(view.step||0);
  var wrap=el('div',{style:'max-width:900px;margin:8px auto;padding:10px;border:1px solid #d0d5dd;border-radius:10px;background:#fff'});
  box.appendChild(wrap);
  if(!document.createElementNS||!cwNode('svg',{}).createSVGRect){
    wrap.appendChild(el('p',{text:cwFigureText(f)+(step>=4?'；等底等高，面积相等 = '+(Number(f.base)*Number(f.height))+' cm²':'')}));
    return;
  }
  var svg=cwNode('svg',{viewBox:'0 0 780 260',width:'100%',style:'display:block;max-height:'+(big?'34vh':'280px'),role:'img','aria-label':cwFigureText(f)});
  var shifts=[20,45,0],starts=[25,280,535];
  function line(x1,y1,x2,y2,color,width,dash){svg.appendChild(cwNode('line',{x1:x1,y1:y1,x2:x2,y2:y2,stroke:color,'stroke-width':width,'stroke-dasharray':dash||''}))}
  function txt(x,y,s,size,color,weight,anchor){svg.appendChild(cwNode('text',{x:x,y:y,'font-size':size,fill:color,'font-weight':weight||400,'text-anchor':anchor||'middle'},s))}
  for(var i=0;i<3;i++){
    var x=starts[i],shift=shifts[i],left=x+35,bottomY=205,topY=45,width=68;
    svg.appendChild(cwNode('text',{x:x+100,y:28,'text-anchor':'middle','font-size':20,'font-weight':700,fill:'#17449b'},['①','②','③'][i]));
    svg.appendChild(cwNode('polygon',{points:(left+shift)+','+topY+' '+(left+shift+width)+','+topY+' '+(left+width)+','+bottomY+' '+left+','+bottomY,fill:'#eaf3ff',stroke:'#2563eb','stroke-width':3}));
    line(x+12,topY,x+195,topY,'#98a2b3',1.3,'4 4');
    line(x+12,bottomY,x+195,bottomY,'#98a2b3',1.3,'4 4');
    if(step>=2){
      line(left,bottomY+18,left+width,bottomY+18,'#c2410c',2);
      line(left,bottomY+13,left,bottomY+23,'#c2410c',2);
      line(left+width,bottomY+13,left+width,bottomY+23,'#c2410c',2);
      txt(left+width/2,bottomY+43,'底 = '+f.base+' cm',16,'#344054',600);
    }
    if(step>=3){
      var hx=x+170;
      line(hx,bottomY,hx,topY,'#c2410c',2);
      line(hx,bottomY,hx-5,bottomY-8,'#c2410c',2);line(hx,bottomY,hx+5,bottomY-8,'#c2410c',2);
      line(hx,topY,hx-5,topY+8,'#c2410c',2);line(hx,topY,hx+5,topY+8,'#c2410c',2);
      txt(hx+28,130,'高 = '+f.height+' cm',15,'#344054',600,'start');
    }
  }
  wrap.appendChild(svg);
  var msgText=step>=4?'等底等高，三个平行四边形面积相等 = '+f.base+' × '+f.height+' = '+(Number(f.base)*Number(f.height))+' cm²':'先观察三条平行线之间的三个平行四边形，再逐步比较底和高';
  wrap.appendChild(el('div',{style:'text-align:center;color:'+(step>=4?'#17449b':'#475467')+';font-weight:'+(step>=4?700:400)+';font-size:13px',text:msgText}));
}
function cwParallelogramThirds(box,f,view,big,teacher,stepCount){
  view=view||{};
  var steps=Math.max(3,stepCount||3),step=teacher&&!view.previewMode?steps:(view.step||0);
  var wrap=el('div',{style:'max-width:760px;margin:8px auto;padding:10px;border:1px solid #d0d5dd;border-radius:10px;background:#fff'});
  box.appendChild(wrap);
  if(!document.createElementNS||!cwNode('svg',{}).createSVGRect){
    wrap.appendChild(el('p',{text:cwFigureText(f)+(step>=3?'；中间涂色部分面积 = '+(Math.round(Number(f.totalArea)*100/3)/100)+' cm²':'')}));
    return;
  }
  var svg=cwNode('svg',{viewBox:'0 0 720 300',width:'100%',style:'display:block;max-height:'+(big?'38vh':'320px'),role:'img','aria-label':cwFigureText(f)});
  function line(x1,y1,x2,y2,color,width,dash){svg.appendChild(cwNode('line',{x1:x1,y1:y1,x2:x2,y2:y2,stroke:color,'stroke-width':width,'stroke-dasharray':dash||''}))}
  function txt(x,y,s,size,color,weight,anchor){svg.appendChild(cwNode('text',{x:x,y:y,'font-size':size,fill:color,'font-weight':weight||400,'text-anchor':anchor||'middle'},s))}
  var yTop=65,yBottom=220,baseLeft=90,baseWidth=390,slant=65,part=baseWidth/3;
  txt(285,34,'底边平均分成 3 份，原总面积 '+f.totalArea+' cm²',20,'#17449b',700);
  svg.appendChild(cwNode('polygon',{points:(baseLeft+slant)+','+yTop+' '+(baseLeft+slant+baseWidth)+','+yTop+' '+(baseLeft+baseWidth)+','+yBottom+' '+baseLeft+','+yBottom,fill:'#eaf3ff',stroke:'#2563eb','stroke-width':3}));
  svg.appendChild(cwNode('polygon',{points:(baseLeft+slant+part)+','+yTop+' '+(baseLeft+slant+2*part)+','+yTop+' '+(baseLeft+2*part)+','+yBottom+' '+(baseLeft+part)+','+yBottom,fill:step>=3?'#ffdf87':'#dbeafe',stroke:'none'}));
  line(baseLeft+part,yBottom,baseLeft+slant+part,yTop,'#2563eb',3);
  line(baseLeft+2*part,yBottom,baseLeft+slant+2*part,yTop,'#2563eb',3);
  line(baseLeft+slant,yTop,baseLeft+slant+baseWidth,yTop,'#2563eb',3);
  line(baseLeft,yBottom,baseLeft+baseWidth,yBottom,'#2563eb',3);
  if(step>=2){
    var hx=baseLeft+slant+part+8;
    line(hx,yTop,hx,yBottom,'#c2410c',2,'5 4');
    line(hx,yTop,hx-5,yTop+8,'#c2410c',2);line(hx,yTop,hx+5,yTop+8,'#c2410c',2);
    line(hx,yBottom,hx-5,yBottom-8,'#c2410c',2);line(hx,yBottom,hx+5,yBottom-8,'#c2410c',2);
    txt(hx+16,150,'高不变',15,'#9a3412',700,'start');
  }
  for(var i=0;i<3;i++){
    var cx=baseLeft+part*(i+.5);
    txt(cx,yBottom+25,'1 份',15,'#475467',600);
    if(i===1&&step>=3)txt(cx,yBottom+52,'中间涂色部分占 1/3',15,'#9a3412',700);
  }
  wrap.appendChild(svg);
  if(step>=3){
    wrap.appendChild(el('div',{style:'text-align:center;color:#9a3412;font-weight:700;font-size:13px',text:'等底等高的 3 份各占总面积的 1/3：'+f.totalArea+' ÷ 3 = '+(Math.round(Number(f.totalArea)*100/3)/100)+' cm²'}));
  }
}
// 钝角三角形在底边延长线上的高：底边水平，顶点在底边左上方，所以高落在延长线上。
function cwObtuseTriangleHeight(box,f,view,big,teacher,stepCount){
  var unit=f.unit||'',base=Number(f.base),side=Number(f.side),height=Number(f.height);
  var steps=Math.max(5,stepCount||5);
  // 课堂大屏（老师、非预览）一次看全；预览和学生端跟着 step 走，第 0 步只画三角形本身。
  var step=teacher&&!view.previewMode?steps:(view.step||0);
  var wrap=el('div',{style:'max-width:760px;margin:10px auto;padding:10px;background:#fff;border:1px solid #d0d5dd;border-radius:12px'});box.appendChild(wrap);
  if(!document.createElementNS||!cwNode('svg',{}).createSVGRect){wrap.appendChild(el('p',{style:'white-space:pre-wrap',text:cwFigureText(f)}));return}
  var svg=cwNode('svg',{viewBox:'0 0 720 360',width:'100%',style:'display:block;max-height:'+(big?'46vh':'360px'),role:'img','aria-label':cwFigureText(f)});
  wrap.appendChild(svg);
  // 顶点：底边 BC 水平，A 在 B 的左上方，这样高就落在底边的延长线上，一眼能看出是钝角。
  var A={x:150,y:110},B={x:330,y:270},C={x:570,y:270},F={x:150,y:270};
  function line(o){svg.appendChild(cwNode('line',o))}
  function txt(x,y,t,size,anchor,color){svg.appendChild(cwNode('text',{x:x,y:y,'font-size':size||20,'text-anchor':anchor||'middle','font-weight':700,fill:color||'#111'},t))}
  svg.appendChild(cwNode('polygon',{points:[A,B,C].map(function(q){return q.x+','+q.y}).join(' '),fill:'#eff6ff',stroke:'#1d4ed8','stroke-width':3}));
  // 第 1 步只有三角形；第 2 步才画底边向左的虚线延长线。
  if(step>=2){
    line({x1:110,y1:B.y,x2:B.x,y2:B.y,stroke:'#667085','stroke-width':2,'stroke-dasharray':'8 6'});
    txt(112,B.y+24,'底边延长线',15,'start','#475467');
  }
  if(step>=3){
    line({x1:A.x,y1:A.y,x2:F.x,y2:F.y,stroke:'#b42318','stroke-width':2,'stroke-dasharray':'7 5'});
    // 垂足处的直角小方块，让学生看清“高和底边垂直”。
    svg.appendChild(cwNode('path',{d:'M'+(F.x+14)+' '+F.y+' L'+(F.x+14)+' '+(F.y-14)+' L'+F.x+' '+(F.y-14),fill:'none',stroke:'#b42318','stroke-width':2}));
    svg.appendChild(cwNode('circle',{cx:F.x,cy:F.y,r:4,fill:'#b42318'}));
    txt(F.x-8,F.y+24,'垂足',15,'end','#b42318');
  }
  if(step>=4){
    txt(A.x,A.y-14,'A',22);txt(B.x-4,B.y+34,'B',22);txt(C.x+16,C.y+34,'C',22);
    txt((B.x+C.x)/2,B.y+30,'底 BC = '+base+unit,20);
    txt((A.x+C.x)/2+26,(A.y+C.y)/2-6,'边 AC = '+side+unit,20,'start','#1d4ed8');
    txt(A.x-14,(A.y+F.y)/2,'高 = '+height+unit,20,'end','#b42318');
  }
  if(step>=5){
    var area=base*height/2;
    wrap.appendChild(el('div',{style:'margin-top:8px;text-align:center;font-weight:700;color:#17449b;font-size:'+(big?'2.4vh':'16px'),text:'面积 = 底 × 高 ÷ 2 = '+base+' × '+height+' ÷ 2 = '+area+' '+unit+'²'}));
  }else{
    wrap.appendChild(el('div',{style:'margin-top:6px;color:#475467',text:'提示：高在底边的延长线上，所以要把底边用虚线接着画出去。'}));
  }
}

function cwFigure(wrap,f,big,view,teacher,stepCount){
  view=view||{};
  if(!f||!f.type)return;
  var box=el('div',{style:big?'margin:0;width:100%;height:100%;display:flex;align-items:center;justify-content:center':'margin:8px 0'});wrap.appendChild(box);
  if(!cwFigureOk(f)){box.appendChild(el('div',{class:'notice warn',text:'图示还没填完整'}));return}
  if(f.type==='uploaded_image'){
    box.appendChild(el('img',{src:f.data_url,alt:f.alt||'原卷插图',style:'display:block;max-width:100%;max-height:'+(big?'75vh':'300px')+';'+(big?'width:100%;height:100%;':'')+'object-fit:contain;margin:0 auto;border:1px solid #e5e8f0;border-radius:10px;background:#fff'}));
    return;
  }
  if(f.type==='equal_base_height'){cwEqualBaseHeight(box,f,view,big,teacher,stepCount);return}
  if(f.type==='parallelogram_thirds'){cwParallelogramThirds(box,f,view,big,teacher,stepCount);return}
  if(f.type==='parallelogram_methods'){cwParallelogramMethods(box,view,big,teacher);return}
  if(f.type==='calendar_compare'){cwCalendarCompare(box,f,view,big,teacher);return}
  if(f.type==='calendar_cross'){cwCalendarCross(box,f,view,big,teacher);return}
  if(f.type==='seating_pattern'){cwSeatingPattern(box,f,view,big,teacher,stepCount);return}
  if(f.type==='alternating_triangle'){cwAlternatingTriangle(box,f,view,big,teacher,stepCount);return}
  if(f.type==='running_track'){cwRunningTrack(box,f,view,big,teacher,stepCount);return}
  if(f.type==='triangular_numbers'){cwTriangularNumbers(box,f,view,big,teacher,stepCount);return}
  if(f.type==='tile_pattern'){cwTilePattern(box,f,view,big,teacher,stepCount);return}
  if(f.type==='square_sticks_pattern'){cwSquareSticksPattern(box,f,view,big,teacher,stepCount);return}
  if(f.type==='hundred_chart_square'){cwHundredChartSquare(box,f,view,big,teacher,stepCount);return}
  if(f.type==='obtuse_triangle_height'){cwObtuseTriangleHeight(box,f,view,big,teacher,stepCount);return}
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
// Lesson 10 examples 17 and 20: display-time correction for the two
// legacy *single rectangle* diagrams only. Teacher-authored data is unchanged.
function cwLesson10Geometry(box,p,view,big,teacher){
  if(!p.figure||p.figure.type!=='shape'||p.figure.shape!=='rectangle')return false;
  var source=[p.title||'',p.problem||'',p.sourceProblem||''].join(' ');
  var ex17=/(第\s*17\s*题|单元知识回顾)/.test(source)&&source.indexOf('正方形')>=0&&source.indexOf('长方形')>=0;
  var ex20=/(第\s*20\s*题|大、小正方形拼图)/.test(source)&&
    source.indexOf('大正方形')>=0&&source.indexOf('小正方形')>=0&&source.indexOf('拼')>=0;
  if(!ex17&&!ex20)return false;
  var last=Math.max(1,(p.steps||[]).length),step=teacher&&!view.previewMode?last:Math.max(0,Math.min(last,view.step||0));
  var wrap=el('div',{style:'max-width:880px;margin:12px auto;padding:14px;background:#f8fbff;border:1px solid #d5dfef;border-radius:14px'});
  wrap.appendChild(el('div',{style:'font-weight:700;text-align:center;color:#284b83;margin-bottom:6px',text:ex17?'分别观察：正方形与长方形':'观察拼图：上排2个大正方形，下排3个小正方形'}));
  var canvas=cwNode('svg',{viewBox:ex17?'0 0 760 325':'0 0 760 465',width:'100%',role:'img',
    'aria-label':ex17?'正方形边长a，与长方形长a宽b的对照图':'上排两个边长m的大正方形，下排三个边长n的小正方形，共同拼成一个长方形',
    style:'display:block;max-height:'+(big?'54vh':'390px')+';margin:auto'});
  function rect(x,y,w,h,fill,stroke){canvas.appendChild(cwNode('rect',{x:x,y:y,width:w,height:h,rx:2,fill:fill,stroke:stroke||'#2563eb','stroke-width':3}))}
  function label(x,y,t,size,color){canvas.appendChild(cwNode('text',{x:x,y:y,'text-anchor':'middle','font-size':size||21,'font-weight':700,fill:color||'#1c3970'},t))}
  if(ex17){
    // The square really has four equal sides; do not infer b for this shape.
    rect(68,71,210,210,'#e0edff');
    rect(424,96,270,160,'#fef3c7','#b7791f');
    label(173,54,'a');label(52,181,'a');
    label(559,79,'a');label(404,182,'b');
    label(173,311,'正方形');label(559,298,'长方形');
  }else{
    // m:n=3:2 follows from two m-squares and three n-squares sharing
    // precisely the same total width: 2*210 = 3*140 = 420.
    for(var a=0;a<2;a++){rect(170+a*210,42,210,210,'#dbeafe');label(275+a*210,157,'m',24)}
    for(var b=0;b<3;b++){rect(170+b*140,252,140,140,'#fef3c7','#b7791f');label(240+b*140,326,'n',23)}
    if(step>=2){label(380,27,'上排总宽 2m',19);label(380,419,'下排总宽 3n',19)}
    if(step>=3)label(380,453,'两排等宽：2m = 3n',19);
  }
  wrap.appendChild(canvas);
  if(ex17&&step>=2)wrap.appendChild(el('div',{style:'text-align:center;font-weight:600;color:#184b82',text:'正方形：周长 4a，面积 a²'}));
  if(ex17&&step>=3)wrap.appendChild(el('div',{style:'text-align:center;font-weight:600;color:#184b82',text:'长方形：周长 2(a+b)，面积 ab'}));
  if(ex17&&step>=4)wrap.appendChild(el('div',{style:'text-align:center;font-weight:600;color:#a15c12',text:'m = n + 20，m = 37：n = 17'}));
  if(ex20&&step>=last)wrap.appendChild(el('div',{style:'text-align:center;font-weight:700;color:#184b82',text:'长 = 2m = 3n，宽 = m+n；C = 2(3n+m+n) = 11n'}));
  box.appendChild(wrap);return true;
}
// Restore the existing, reviewed visual components for the two remaining
// lesson-10 examples shown with a blank diagram / stock numeric table.
// This is presentation-only: do not edit saved teacher figures or steps.
function cwLesson10RemainingFigure(wrap,p,view,big,teacher){
  var f=p.figure||{},kind=f.type||'';
  if(kind&&kind!=='table')return false;
  var text=[p.title||'',p.problem||'',p.sourceProblem||''].join(' ');
  var is21=/(?:第\s*21\s*题|跑道追及)/.test(text)
    &&text.indexOf('跑道')>=0
    &&/180\s*米/.test(text)&&/140\s*米/.test(text)
    &&/(?:同向|同一方向)/.test(text);
  if(is21&&(!kind||kind==='table')){
    // Keep the original question and the teacher's five steps unchanged.
    cwFigure(wrap,{type:'running_track',fastSpeed:180,slowSpeed:140,distanceSymbol:'s'},
      big,view,teacher,p.steps.length);
    return true;
  }
  var is22=/(?:第\s*22\s*题|三角形数规律)/.test(text)
    &&text.indexOf('三角形数')>=0
    &&/(?:第\s*10\s*个|第\s*10\s*项)/.test(text);
  if(is22&&(!kind||kind==='table')){
    // Replace only the generic n/三角形数 enumeration seen in the legacy
    // editor, not an unrelated hand-crafted table or any specialized figure.
    if(kind==='table'){
      var rows=f.rows||[];
      var header=rows.length?rows[0].join(''):'';
      var values=rows.length>1?rows[1].join(''):'';
      if(header.indexOf('n')<0||values.indexOf('三角形数')<0)return false;
    }
    cwFigure(wrap,{type:'triangular_numbers',terms:[1,3,6,10,15],targetTerm:10},
      big,view,teacher,p.steps.length);
    return true;
  }
  return false;
}
function cwPreviewFigureTag(kind,v){
  v=v||{};
  if(kind==='steps'&&Array.isArray(v.stepFigures)&&v.stepFigures.length)return '分步图示';
  var fig=v.figure||{};
  return kind!=='steps'?'模板图示':fig.type==='uploaded_image'?'原卷图片':fig.type?'课件图示':'无图';
}
function cwSteps(box,p,view,big,teacher){
  p=p||{};view=view||{};
  var steps=Array.isArray(p.steps)?p.steps:[];
  var hasStepFigs=Array.isArray(p.stepFigures)&&p.stepFigures.length===steps.length+1;
  var card=el('div',{style:(big?'flex:1;min-height:0;width:100%;max-width:none;margin:0;padding:1vh 1.4vw;display:flex;flex-direction:column;gap:0.8vh;font-size:2.3vh;line-height:1.5;':'max-width:980px;margin:0 auto;padding:12px;line-height:1.75;')+'background:#fff;color:#111;border-radius:14px;box-sizing:border-box'});box.appendChild(card);
  // 预览和课堂用同一套展开规则：新题从 0 步开始，点一下“下一步”只多展开 1 步。
  var shown=teacher?(view.previewMode?(view.step||0):steps.length):(view.step||0);
  shown=Math.max(0,Math.min(steps.length,shown));
  if(big){
    if(!hasStepFigs){
      var hdr=el('div',{style:'display:flex;justify-content:space-between;align-items:center;gap:1vw;padding-bottom:0.5vh;border-bottom:1px solid #e5e7eb;flex:none'});
      hdr.appendChild(el('b',{style:'font-size:2.3vh;color:#0f172a',text:p.title||'分步讲解'}));
      hdr.appendChild(el('span',{style:'font-size:1.8vh;font-weight:700;color:#1d4ed8;background:#eff6ff;border:1px solid #bfdbfe;padding:0.2vh 0.8vw;border-radius:999px;white-space:nowrap',text:'已展开 '+shown+' / '+steps.length+' 步'}));
      card.appendChild(hdr);
    }
  }else{
    card.appendChild(el('b',{text:p.title||'分步讲解'}));
  }
  var sourceProblem=String(p.sourceProblem||'');
  if(p.figure&&p.figure.type==='table'&&sourceProblem.indexOf('对应面积')>=0&&sourceProblem.indexOf('平方千米')>=0&&sourceProblem.indexOf('公顷')>=0){
    var tableHeader=sourceProblem.lastIndexOf('正方形边长',sourceProblem.indexOf('对应面积'));
    if(tableHeader>0)sourceProblem=sourceProblem.slice(0,tableHeader).trim();
  }
  if(sourceProblem)card.appendChild(el('p',{style:'white-space:pre-wrap;margin:0;flex:none',text:sourceProblem}));
  var wrap=big?el('div',{class:'cw-big-stage',style:'flex:1;min-height:0;width:100%;display:flex;flex-direction:column;justify-content:center;align-items:center'}):card;
  if(big)card.appendChild(wrap);
  if(p.figure&&p.figure.type==='calendar_compare')view._calendarCourseware={kind:'steps',params:p};
  if(p.figureUnverified){
    // 图示和题干数据对不上时不能当正确图展示，改成黄底提示让老师先核对。
    wrap.appendChild(el('div',{style:'margin:10px 0 0;padding:10px 12px;border-radius:10px;background:#fff7ed;border:1px solid #f59e0b;color:#92400e;font-weight:700',text:'本题需要老师确认配图'}));
    wrap.appendChild(el('div',{style:'margin:6px 0 10px;padding:12px;border-radius:10px;background:#fef3c7;border:1px solid #f59e0b;color:#78350f',text:p.figureNotice||'图示待确认：题干与图示不一致，请老师核对'}));
  }else if(hasStepFigs){
    var frameStep=teacher&&!view.previewMode?steps.length:(view.step||0);
    cwFigure(wrap,p.stepFigures[Math.max(0,Math.min(steps.length,frameStep))],big,view,teacher,p.steps.length);
  }else if(!cwLesson10Geometry(wrap,p,view,big,teacher)&&!cwLesson10RemainingFigure(wrap,p,view,big,teacher))cwFigure(wrap,p.figure,big,view,teacher,p.steps.length);
  if(p.figureNotice&&!p.figureUnverified)wrap.appendChild(el('div',{class:'muted',style:'margin-top:6px',text:p.figureNotice}));
  if(p.sourceFigure&&p.sourceFigure.type==='uploaded_image')wrap.appendChild(el('details',{style:'margin:10px 0'},el('summary',{text:'\u67e5\u770b\u539f\u9898\u56fe\u7247\uff08\u5bf9\u7167\uff09'}),el('img',{src:p.sourceFigure.data_url,alt:p.sourceFigure.alt||'\u539f\u9898\u56fe\u7247',style:'display:block;max-width:100%;max-height:'+(big?'32vh':'260px')+';object-fit:contain;margin:8px auto;border:1px solid #e5e8f0;border-radius:8px'})));
  // 答案和步骤分开：只有点了“显示答案”（或老师整题全展开）才出现，不跟 step 联动。
  var answerVisible=!!view.showAnswer||(teacher&&!view.previewMode);
  if(big){
    var bar=el('div',{class:'cw-big-focusbar',style:'flex:none;display:flex;align-items:center;gap:1.1vw;padding:0.9vh 1.2vw;border-radius:12px;background:#f8fafc;border:1px solid #dbe4f0'});
    var pills=el('div',{style:'display:flex;align-items:center;gap:0.45vw;flex:none;flex-wrap:wrap'});
    pills.appendChild(el('span',{style:'font-size:1.75vh;font-weight:700;color:#1e40af;background:#eff6ff;border:1px solid #bfdbfe;padding:0.25vh 0.7vw;border-radius:999px;white-space:nowrap',text:'已展开 '+shown+'/'+steps.length}));
    steps.forEach(function(_,i){
      var isCur=i===shown-1,isDone=i<shown-1;
      pills.appendChild(el('span',{style:'min-width:2.1em;text-align:center;font-size:1.7vh;font-weight:'+(isCur?'800':'600')+';padding:0.2vh 0.55vw;border-radius:999px;white-space:nowrap;'+(isCur?'background:#1d4ed8;color:#fff':isDone?'background:#dbeafe;color:#1e40af':'background:#e2e8f0;color:#64748b'),text:'第'+(i+1)+'步'}));
    });
    bar.appendChild(pills);
    var focusText=shown>0?('第 '+shown+' 步：'+steps[shown-1]):'请先观察图示，思考解题思路…';
    bar.appendChild(el('div',{style:'flex:1;min-width:0;font-size:2.25vh;line-height:1.4;font-weight:'+(shown>0?'700':'500')+';color:'+(shown>0?'#0f172a':'#64748b')+';padding-left:0.9vw;border-left:4px solid '+(shown>0?'#f59e0b':'#cbd5e1'),text:focusText}));
    if(answerVisible&&p.answer)bar.appendChild(el('div',{style:'flex:none;max-width:34%;font-size:2.15vh;font-weight:800;color:#b42318;background:#fef2f2;border:2px solid #fca5a5;border-radius:10px;padding:0.55vh 0.95vw;line-height:1.35',text:'答案：'+p.answer}));
    card.appendChild(bar);
    return;
  }
  card.appendChild(el('div',{style:'margin:12px 0 2px;color:#475467;font-weight:600',text:'已展开 '+shown+' / '+steps.length+' 步'}));
  card.appendChild(el('div',{class:'muted',text:'点“下一步”只多展开 1 步'}));
  var list=el('ol',{style:'padding-left:1.5em;margin:8px 0'});
  steps.forEach(function(s,i){
    if(i<shown)list.appendChild(el('li',{style:i===shown-1?'background:#fff2cc;font-weight:700;border-radius:6px;padding:2px 6px':'',text:s}));
    else list.appendChild(el('li',{style:'color:#98a2b3',text:'第 '+(i+1)+' 步'}));
  });
  card.appendChild(list);
  if(answerVisible&&p.answer)card.appendChild(el('p',{style:'font-weight:700;color:#b42318',text:'答案：'+p.answer}));
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
function cwAppendRichText(node,text){
  var parts=String(text||'').split(/(==[^=]+==)/g);
  parts.forEach(function(seg){
    if(!seg)return;
    if(seg.length>4&&seg.slice(0,2)==='=='&&seg.slice(-2)==='=='){
      node.appendChild(el('mark',{style:'background:#fde68a;color:#7c2d12;padding:1px 4px;border-radius:4px;font-weight:700',text:seg.slice(2,-2)}));
    }else{
      node.appendChild(document.createTextNode(seg));
    }
  });
}
var CW_AUDIO_BLOB_CACHE={};
function cwResolveAudioSrc(raw){
  var s=String(raw||'');
  if(!s)return '';
  var m=/^data:(audio\/[A-Za-z0-9.+-]+);base64,([\s\S]+)$/.exec(s);
  if(m&&typeof Blob==='function'&&typeof Uint8Array==='function'&&typeof atob==='function'&&typeof URL!=='undefined'&&URL.createObjectURL){
    if(CW_AUDIO_BLOB_CACHE[s])return CW_AUDIO_BLOB_CACHE[s];
    try{
      var bin=atob(m[2].replace(/\s+/g,''));
      var bytes=new Uint8Array(bin.length);
      for(var i=0;i<bin.length;i++)bytes[i]=bin.charCodeAt(i);
      var blobUrl=URL.createObjectURL(new Blob([bytes],{type:m[1]}));
      CW_AUDIO_BLOB_CACHE[s]=blobUrl;
      return blobUrl;
    }catch(_e){}
  }
  return s;
}
function cwBindSingleAudio(au){
  if(!au||!au.addEventListener)return;
  au.addEventListener('play',function(){
    if(typeof document==='undefined'||!document.querySelectorAll)return;
    var allAudios=document.querySelectorAll('audio');
    for(var i=0;i<allAudios.length;i++){
      if(allAudios[i]!==au&&allAudios[i].pause){try{allAudios[i].pause()}catch(_e){}}
    }
  });
}
function cwCreateAudio(raw,styleStr,errBox){
  var au=el('audio',{controls:true,preload:'metadata',src:cwResolveAudioSrc(raw),style:styleStr});
  cwBindSingleAudio(au);
  if(errBox&&au&&au.addEventListener){
    au.addEventListener('error',function(){
      errBox.hidden=false;
      errBox.textContent='音频加载失败，请检查格式或点击“替换 .mp3”重试';
    });
    au.addEventListener('loadedmetadata',function(){errBox.hidden=true});
  }
  return au;
}
function cwRenderOneSlide(p,cur,idx,total,big,view,teacher){
  var isCover=cur.layout==='cover';
  var isReading=cur.layout==='reading';
  var hasUploadedImg=!!(cur.figure&&cur.figure.type==='uploaded_image'&&cwFigureOk(cur.figure));
  var hasOtherFig=!!(cur.figure&&cur.figure.type&&cur.figure.type!=='uploaded_image');
  var cardStyle='background:linear-gradient(135deg,#fffdf9 0%,#fbf4e6 100%);color:#1f2937;border:1px solid #e6d8be;border-top:5px solid #8b1e24;border-radius:14px;padding:'+(big?'26px 32px':'18px 22px')+';box-shadow:0 6px 20px rgba(120,53,15,0.09);min-height:'+(big?'64vh':'320px')+';display:flex;flex-direction:column;justify-content:space-between;gap:12px;margin-bottom:16px;flex:none;box-sizing:border-box;width:100%';
  var slideEl=el('div',{style:cardStyle});
  var topBar=el('div',{style:'display:flex;justify-content:space-between;align-items:center;gap:8px;border-bottom:1px solid #efe3cc;padding-bottom:8px'});
  var leftMeta=el('div',{style:'display:flex;align-items:center;gap:8px;flex-wrap:wrap'});
  leftMeta.appendChild(el('span',{style:'font-weight:700;color:#8b1e24;'+(big?'font-size:2.2vh':'font-size:13px'),text:p.title||'课件幻灯片'}));
  if(cur.badge)leftMeta.appendChild(el('span',{style:'background:#8b1e24;color:#fff;padding:2px 9px;border-radius:999px;font-weight:700;'+(big?'font-size:1.8vh':'font-size:12px'),text:cur.badge}));
  topBar.appendChild(leftMeta);
  topBar.appendChild(el('span',{class:'tag',style:'background:#f3e8d2;color:#78350f;font-weight:700',text:'第 '+(idx+1)+' / '+total+' 页'}));
  slideEl.appendChild(topBar);
  var main=el('div',{style:'flex:1;display:flex;flex-direction:column;gap:12px;'+(isCover?'justify-content:center;text-align:center;padding:8px 0':'')});
  if(isCover&&hasUploadedImg){
    var heroWrap=el('div',{style:'display:flex;flex-direction:column;gap:5px'});
    heroWrap.appendChild(el('img',{src:cur.figure.data_url,alt:cur.figure.alt||cur.heading||'课文插图',style:'display:block;width:100%;max-height:'+(big?'34vh':'230px')+';object-fit:cover;border-radius:12px;border:1px solid #e6d8be;box-shadow:0 4px 12px rgba(120,53,15,0.1)'}));
    if(cur.caption)heroWrap.appendChild(el('div',{class:'muted',style:'font-size:12px;text-align:center',text:cur.caption}));
    main.appendChild(heroWrap);
  }
  if(cur.heading){
    main.appendChild(el('h3',{style:'margin:2px 0 0;color:#7f1d1d;line-height:1.35;'+(isCover?(big?'font-size:4.2vh':'font-size:24px'):(big?'font-size:3.1vh':'font-size:19px')),text:cur.heading}));
  }
  if(cur.subtitle){
    main.appendChild(el('div',{style:'color:#6b4f3a;font-weight:600;'+(big?'font-size:2.2vh':'font-size:14px'),text:cur.subtitle}));
  }
  var au=null;
  var audioScenes=Array.isArray(cur.audioScenes)?cur.audioScenes.filter(function(sc){return sc&&sc.data_url}):[];
  if(cur.audioUrl){
    var audioBar=el('div',{style:'background:#fff5f5;border:1px solid #fecaca;border-radius:10px;padding:8px 12px;display:flex;flex-wrap:wrap;align-items:center;gap:10px;text-align:left'});
    audioBar.appendChild(el('span',{style:'font-weight:700;color:#991b1b;white-space:nowrap;'+(big?'font-size:2.1vh':'font-size:13px'),text:'🎧 '+(cur.audioLabel||'课文／讲解配音朗读')}));
    var audioErr=el('span',{hidden:true,style:'flex-basis:100%;color:#b42318;font-size:12px;font-weight:600'});
    au=cwCreateAudio(cur.audioUrl,'flex:1;min-width:210px;height:36px',audioErr);
    var audioNote=el('span',{hidden:true,style:'color:#b45309;font-size:12px',text:'若大屏未自动出声，请轻点页面后点播放'});
    audioBar.appendChild(au);
    audioBar.appendChild(audioNote);
    var scriptBox=null;
    if(teacher&&cur.audioText){
      scriptBox=el('div',{hidden:true,style:'background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:8px 12px;color:#451a03;font-size:13px;line-height:1.7;white-space:pre-wrap;text-align:left',text:cur.audioText});
      var scriptToggle=el('button',{type:'button',style:'font-size:12px;padding:4px 10px',text:'对照朗读原稿',onclick:function(){
        scriptBox.hidden=!scriptBox.hidden;
        scriptToggle.textContent=scriptBox.hidden?'对照朗读原稿':'收起朗读原稿';
      }});
      audioBar.appendChild(scriptToggle);
    }
    audioBar.appendChild(audioErr);
    main.appendChild(audioBar);
    if(scriptBox)main.appendChild(scriptBox);
    if(big&&view){
      if(view.audioPlaying){
        try{
          var pr=au.play();
          if(pr&&pr.catch)pr.catch(function(){audioNote.hidden=false});
        }catch(_e){audioNote.hidden=false}
      }else{
        try{au.pause()}catch(_e2){}
      }
    }
  }
  if(Array.isArray(cur.gallery)&&cur.gallery.length){
    var galGrid=el('div',{style:'display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;text-align:left'});
    cur.gallery.forEach(function(g){
      if(!g||!g.data_url)return;
      var gcard=el('div',{style:'background:#fff;border:1px solid #eadcc4;border-radius:10px;padding:8px;display:flex;flex-direction:column;gap:6px;box-shadow:0 2px 8px rgba(120,53,15,0.06)'});
      gcard.appendChild(el('img',{src:g.data_url,alt:g.alt||g.caption||'分镜插图',style:'display:block;width:100%;max-height:'+(big?'30vh':'195px')+';object-fit:contain;background:#fff;border-radius:6px'}));
      if(g.caption)gcard.appendChild(el('div',{style:'font-size:12px;color:#6b4f3a;text-align:center;line-height:1.45',text:g.caption}));
      galGrid.appendChild(gcard);
    });
    main.appendChild(galGrid);
  }
  var hasSplitMedia=(audioScenes.length>0||hasUploadedImg)&&!isCover;
  var hasBody=!!(cur.body&&cur.body.length);
  var hasChars=!!(Array.isArray(cur.characters)&&cur.characters.length);
  var hasPlot=!!(Array.isArray(cur.plot)&&cur.plot.length);
  var hasCards=!!(Array.isArray(cur.cards)&&cur.cards.length);
  var hasSteps=!!(Array.isArray(cur.steps)&&cur.steps.length);
  var hasQa=!!(Array.isArray(cur.qa)&&cur.qa.length);
  var hasPrimarySide=hasBody||hasChars||hasPlot;
  var stepsInSide=hasSplitMedia&&!hasPrimarySide&&hasSteps;
  var cardsInSide=hasSplitMedia&&!hasPrimarySide&&!stepsInSide&&hasCards;
  var qaInSide=hasSplitMedia&&!hasPrimarySide&&!stepsInSide&&!cardsInSide&&hasQa;
  var hasAnySide=hasPrimarySide||stepsInSide||cardsInSide||qaInSide;
  var contentHost=main,bodyParas=[],bodyWrap=null,sceneCtrl=null;
  if(hasSplitMedia){
    var figCol=el('div',{style:'min-width:0;background:#fff;border:1px solid #eadcc4;border-radius:12px;padding:8px;box-shadow:0 3px 10px rgba(120,53,15,0.06)'});
    if(audioScenes.length){
      sceneCtrl=(function(){
        var activeSceneIdx=-1;
        var headerBar=el('div',{style:'display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap'});
        var sceneBadge=el('span',{style:'background:#8b1e24;color:#fff;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700',text:'画面 1 / '+audioScenes.length});
        var sceneHint=el('span',{class:'muted',style:'font-size:12px',text:audioScenes.length>1?'随配音进度自动切换 · 点击分镜可跳转':''});
        headerBar.appendChild(sceneBadge);
        if(audioScenes.length>1)headerBar.appendChild(sceneHint);
        figCol.appendChild(headerBar);
        var sceneImg=el('img',{src:audioScenes[0].data_url,alt:audioScenes[0].alt||audioScenes[0].caption||cur.heading||'课文插图',style:'display:block;width:100%;max-height:'+(big?'48vh':'320px')+';object-fit:contain;background:#fdfaf3;border-radius:8px'});
        figCol.appendChild(sceneImg);
        var sceneCap=el('div',{style:'margin-top:6px;font-size:12px;color:#6b4f3a;text-align:center;line-height:1.5',text:audioScenes[0].caption||''});
        figCol.appendChild(sceneCap);
        var sceneBtns=[];
        function fmtAt(sec){
          var t=Math.max(0,Math.floor(Number(sec||0)));
          var m=Math.floor(t/60),s=t%60;
          return m+':'+(s<10?'0':'')+s;
        }
        if(audioScenes.length>1){
          var strip=el('div',{style:'display:grid;grid-template-columns:repeat('+Math.min(audioScenes.length,3)+',minmax(0,1fr));gap:6px;margin-top:8px'});
          audioScenes.forEach(function(sc,si){
            var btn=el('button',{type:'button','aria-pressed':si===0?'true':'false',style:'display:flex;flex-direction:column;align-items:center;gap:4px;padding:4px;border-radius:8px;border:1px solid #eadcc4;background:#fff;color:#4b5563;cursor:pointer;text-align:center;min-width:0',onclick:function(){
              applyScene(si,true);
            }});
            btn.appendChild(el('img',{src:sc.data_url,alt:sc.alt||sc.label||sc.caption||('画面'+(si+1)),style:'display:block;width:100%;height:'+(big?'64px':'48px')+';object-fit:cover;border-radius:5px'}));
            btn.appendChild(el('span',{style:'font-size:11px;font-weight:700;line-height:1.3;word-break:break-word',text:(sc.label||('第'+(si+1)+'幕'))+' '+fmtAt(sc.at)}));
            sceneBtns.push(btn);
            strip.appendChild(btn);
          });
          figCol.appendChild(strip);
        }
        function applyScene(nextIdx,shouldSeek){
          if(nextIdx<0||nextIdx>=audioScenes.length)return;
          var sc=audioScenes[nextIdx];
          if(nextIdx!==activeSceneIdx){
            activeSceneIdx=nextIdx;
            sceneImg.src=sc.data_url;
            sceneImg.alt=sc.alt||sc.caption||cur.heading||'课文插图';
            sceneBadge.textContent='画面 '+(nextIdx+1)+' / '+audioScenes.length+(sc.label?' · '+sc.label:'');
            sceneCap.textContent=sc.caption||'';
            sceneCap.hidden=!sceneCap.textContent;
            sceneBtns.forEach(function(b,bi){
              var active=bi===nextIdx;
              if(b.setAttribute)b.setAttribute('aria-pressed',active?'true':'false');
              if(b.style){
                b.style.border=active?'2px solid #8b1e24':'1px solid #eadcc4';
                b.style.background=active?'#fff5f5':'#fff';
                b.style.color=active?'#8b1e24':'#4b5563';
              }
            });
            if(bodyParas.length&&typeof sc.paraIndex==='number'){
              var startP=sc.paraIndex,endP=bodyParas.length;
              for(var ni=nextIdx+1;ni<audioScenes.length;ni++){
                if(typeof audioScenes[ni].paraIndex==='number'){endP=audioScenes[ni].paraIndex;break}
              }
              bodyParas.forEach(function(pNode,pi){
                var hl=pi>=startP&&pi<endP;
                if(pNode.style){
                  pNode.style.borderLeft=hl?'3px solid #8b1e24':'none';
                  pNode.style.background=hl?'#fffbeb':'transparent';
                  pNode.style.paddingLeft=hl?'8px':'0px';
                  pNode.style.borderRadius=hl?'4px':'0px';
                }
              });
              if(bodyWrap&&bodyParas[startP]&&typeof bodyWrap.scrollTop==='number'){
                var pEl=bodyParas[startP];
                var relTop=(pEl.offsetParent===bodyWrap)?(pEl.offsetTop||0):((pEl.offsetTop||0)-(bodyWrap.offsetTop||0));
                var targetTop=Math.max(0,relTop-10);
                if(nextIdx>0||shouldSeek||bodyWrap.scrollTop>0){
                  if(bodyWrap.scrollTo){try{bodyWrap.scrollTo({top:targetTop,behavior:'smooth'})}catch(_eScr){bodyWrap.scrollTop=targetTop}}
                  else{bodyWrap.scrollTop=targetTop}
                }
              }
            }
          }
          if(shouldSeek&&au){
            try{au.currentTime=Number(sc.at||0)}catch(_eSeek){}
          }
        }
        return {applyScene:applyScene};
      })();
    }else{
      figCol.appendChild(el('img',{src:cur.figure.data_url,alt:cur.figure.alt||cur.heading||'课文插图',style:'display:block;width:100%;max-height:'+(big?'45vh':'290px')+';object-fit:cover;border-radius:8px'}));
      if(cur.caption)figCol.appendChild(el('div',{style:'margin-top:6px;font-size:12px;color:#6b4f3a;text-align:center;line-height:1.5',text:cur.caption}));
    }
    if(hasAnySide){
      var splitGrid=el('div',{style:'display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;align-items:start;text-align:left'});
      var textCol=el('div',{style:'min-width:0;display:flex;flex-direction:column;gap:10px'});
      splitGrid.appendChild(figCol);
      splitGrid.appendChild(textCol);
      main.appendChild(splitGrid);
      contentHost=textCol;
    }else{
      main.appendChild(figCol);
    }
  }
  if((cur.body||[]).length){
    var readingScrollCss=(isReading&&hasSplitMedia)?('max-height:'+(big?'60vh':'430px')+';overflow-y:auto;position:relative;scroll-behavior:smooth;'):'';
    bodyWrap=el('div',{style:isReading?(readingScrollCss+'background:#fff;border:1px solid #eadcc4;border-radius:10px;padding:12px 16px;box-shadow:inset 0 1px 3px rgba(0,0,0,0.03)'):''});
    (cur.body||[]).forEach(function(line){
      var para=el('p',{style:'margin:6px 0;line-height:1.85;white-space:pre-wrap;'+(isReading?'text-indent:2em;':'')+(big?'font-size:2.3vh':'font-size:15px')});
      cwAppendRichText(para,line);
      bodyParas.push(para);
      bodyWrap.appendChild(para);
    });
    contentHost.appendChild(bodyWrap);
  }
  if(sceneCtrl){
    sceneCtrl.applyScene(0,false);
    if(audioScenes.length>1&&au&&au.addEventListener){
      var syncFromAudio=function(){
        var t=Number(au.currentTime||0),pick=0;
        for(var si=0;si<audioScenes.length;si++){
          if(t>=Number(audioScenes[si].at||0)-0.15)pick=si;
        }
        sceneCtrl.applyScene(pick,false);
      };
      au.addEventListener('timeupdate',syncFromAudio);
      au.addEventListener('seeked',syncFromAudio);
      au.addEventListener('play',syncFromAudio);
    }
  }
  if(Array.isArray(cur.characters)&&cur.characters.length){
    var chGrid=el('div',{style:'display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;text-align:left'});
    cur.characters.forEach(function(ch){
      var chCard=el('div',{style:'background:#fff;border:1px solid #e7decb;border-left:4px solid #8b1e24;border-radius:12px;padding:12px 14px;display:flex;flex-direction:column;gap:8px'});
      var chHead=el('div',{style:'display:flex;align-items:center;gap:10px'});
      chHead.appendChild(el('span',{style:'flex:none;width:36px;height:36px;border-radius:999px;background:#8b1e24;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-weight:800;font-size:16px',text:(ch.name||'人').slice(0,1)}));
      var chMeta=el('div',{style:'display:flex;flex-direction:column;gap:2px'});
      chMeta.appendChild(el('b',{style:'color:#1f2937;'+(big?'font-size:2.3vh':'font-size:15px'),text:ch.name||'人物'}));
      if(ch.role)chMeta.appendChild(el('span',{style:'font-size:12px;color:#6b4f3a',text:ch.role}));
      chHead.appendChild(chMeta);
      chCard.appendChild(chHead);
      if(Array.isArray(ch.traits)&&ch.traits.length){
        var trRow=el('div',{style:'display:flex;flex-wrap:wrap;gap:6px'});
        ch.traits.forEach(function(tr){
          trRow.appendChild(el('span',{style:'background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700',text:tr}));
        });
        chCard.appendChild(trRow);
      }
      if(ch.details){
        var det=el('div',{style:'color:#374151;line-height:1.7;white-space:pre-wrap;'+(big?'font-size:2vh':'font-size:13.5px')});
        cwAppendRichText(det,'细节描写：'+ch.details);
        chCard.appendChild(det);
      }
      if(ch.emotion){
        var emo=el('div',{style:'padding:6px 10px;border-radius:8px;background:#fdf2f2;color:#7f1d1d;font-weight:600;line-height:1.6;'+(big?'font-size:1.9vh':'font-size:13px')});
        cwAppendRichText(emo,'情感品质：'+ch.emotion);
        chCard.appendChild(emo);
      }
      chGrid.appendChild(chCard);
    });
    (hasBody?main:contentHost).appendChild(chGrid);
  }
  if(Array.isArray(cur.plot)&&cur.plot.length){
    var plGrid=el('div',{style:'display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:10px;text-align:left'});
    cur.plot.forEach(function(pl,pi){
      var plCard=el('div',{style:'background:#fff;border:1px solid #e7decb;border-top:3px solid #b45309;border-radius:10px;padding:10px 12px;display:flex;flex-direction:column;gap:6px'});
      var plTop=el('div',{style:'display:flex;align-items:center;gap:6px'});
      plTop.appendChild(el('span',{style:'flex:none;width:22px;height:22px;border-radius:999px;background:#b45309;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:12px',text:String(pi+1)}));
      if(pl.stage)plTop.appendChild(el('b',{style:'color:#92400e;font-size:13px',text:pl.stage}));
      plCard.appendChild(plTop);
      if(pl.scene)plCard.appendChild(el('b',{style:'color:#1f2937;'+(big?'font-size:2.1vh':'font-size:14px'),text:pl.scene}));
      if(pl.event){
        var evBox=el('div',{style:'color:#374151;line-height:1.65;white-space:pre-wrap;'+(big?'font-size:1.95vh':'font-size:13px')});
        cwAppendRichText(evBox,pl.event);
        plCard.appendChild(evBox);
      }
      if(pl.feeling)plCard.appendChild(el('div',{style:'margin-top:auto;padding:4px 8px;border-radius:6px;background:#fffbeb;color:#92400e;font-size:12px;font-weight:700',text:'情感：'+pl.feeling}));
      plGrid.appendChild(plCard);
    });
    (hasBody?main:contentHost).appendChild(plGrid);
  }
  if(Array.isArray(cur.cards)&&cur.cards.length){
    var grid=el('div',{style:'display:grid;grid-template-columns:'+(cardsInSide?'1fr':'repeat(auto-fit,minmax(210px,1fr))')+';gap:12px;text-align:left'});
    var accents=['#8b1e24','#b45309','#1d4ed8','#15803d'];
    cur.cards.forEach(function(cd,ci){
      var accent=accents[ci%accents.length];
      var card=el('div',{style:'background:#fff;border:1px solid #e7decb;border-top:3px solid '+accent+';border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:6px'});
      if(cd.tag)card.appendChild(el('span',{style:'align-self:flex-start;background:#fef3c7;color:#92400e;padding:2px 7px;border-radius:6px;font-size:12px;font-weight:700',text:cd.tag}));
      if(cd.title)card.appendChild(el('b',{style:'color:#1f2937;'+(big?'font-size:2.3vh':'font-size:15px'),text:cd.title}));
      if(cd.text){
        var ct=el('div',{style:'color:#374151;line-height:1.7;white-space:pre-wrap;'+(big?'font-size:2.1vh':'font-size:14px')});
        cwAppendRichText(ct,cd.text);
        card.appendChild(ct);
      }
      grid.appendChild(card);
    });
    (cardsInSide?contentHost:main).appendChild(grid);
  }
  if(Array.isArray(cur.steps)&&cur.steps.length){
    var srow=el('div',{style:'display:grid;grid-template-columns:'+(stepsInSide?'1fr':'repeat(auto-fit,minmax(170px,1fr))')+';gap:10px;text-align:left'});
    cur.steps.forEach(function(st,si){
      var sc=el('div',{style:'background:#fff;border:1px solid #e7decb;border-radius:10px;padding:10px 12px;display:flex;align-items:flex-start;gap:9px'});
      sc.appendChild(el('span',{style:'flex:none;width:24px;height:24px;border-radius:999px;background:#8b1e24;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:13px',text:String(si+1)}));
      var sb=el('div',{style:'display:flex;flex-direction:column;gap:3px'});
      if(st.label)sb.appendChild(el('b',{style:'color:#7f1d1d;'+(big?'font-size:2.2vh':'font-size:14px'),text:st.label}));
      if(st.desc)sb.appendChild(el('span',{style:'color:#374151;line-height:1.6;'+(big?'font-size:2vh':'font-size:13px'),text:st.desc}));
      sc.appendChild(sb);
      srow.appendChild(sc);
    });
    (stepsInSide?contentHost:main).appendChild(srow);
  }
  if(hasOtherFig)cwFigure(main,cur.figure,big,view,teacher,1);
  if(Array.isArray(cur.qa)&&cur.qa.length){
    var qaWrap=el('div',{style:'display:flex;flex-direction:column;gap:8px;text-align:left'});
    cur.qa.forEach(function(item,qi){
      var qbox=el('div',{style:'background:#fff;border:1px solid #e5d5bc;border-left:4px solid #8b1e24;border-radius:10px;padding:10px 14px'});
      var qrow=el('div',{style:'display:flex;justify-content:space-between;align-items:flex-start;gap:10px'});
      var qtxt=el('div',{style:'font-weight:700;color:#1f2937;line-height:1.65;'+(big?'font-size:2.2vh':'font-size:14px'),text:'思考 '+(qi+1)+'：'+item.q});
      qrow.appendChild(qtxt);
      var ansBox=item.a?el('div',{hidden:true,style:'margin-top:8px;padding:8px 10px;border-radius:8px;background:#f0fdf4;border:1px solid #bbf7d0;color:#14532d;line-height:1.7;white-space:pre-wrap;'+(big?'font-size:2.1vh':'font-size:14px')}):null;
      if(ansBox){
        cwAppendRichText(ansBox,'参考点拨：'+item.a);
        var toggle=el('button',{type:'button',style:'flex:none;font-size:12px;padding:4px 10px',text:'查看点拨',onclick:function(){
          ansBox.hidden=!ansBox.hidden;
          toggle.textContent=ansBox.hidden?'查看点拨':'收起点拨';
        }});
        qrow.appendChild(toggle);
      }
      qbox.appendChild(qrow);
      if(ansBox)qbox.appendChild(ansBox);
      qaWrap.appendChild(qbox);
    });
    (qaInSide?contentHost:main).appendChild(qaWrap);
  }
  slideEl.appendChild(main);
  if(cur.highlight){
    var hl=el('div',{style:'padding:10px 14px;border-radius:10px;background:#fef3c7;border-left:4px solid #b45309;color:#78350f;font-weight:700;white-space:pre-wrap;line-height:1.65;'+(big?'font-size:2.2vh':'font-size:14px')});
    cwAppendRichText(hl,cur.highlight);
    slideEl.appendChild(hl);
  }
  return slideEl;
}
function cwSlide(box,p,view,big,teacher){
  var slides=Array.isArray(p.slides)&&p.slides.length?p.slides:[{heading:p.title||'幻灯片',body:[]}];
  if(view&&view.showAllSlides){
    slides.forEach(function(cur,i){
      box.appendChild(cwRenderOneSlide(p,cur,i,slides.length,big,view,teacher));
    });
    return;
  }
  var idx=Math.max(0,Math.min(slides.length-1,Number(view.slideIndex||0)));
  var cur=slides[idx]||{};
  box.appendChild(cwRenderOneSlide(p,cur,idx,slides.length,big,view,teacher));
  if(teacher&&slides.length>1){
    var nav=el('div',{class:'row',style:'margin-top:6px;justify-content:center;align-items:center'});
    nav.appendChild(el('button',{type:'button',text:'‹ 上一页',disabled:idx<=0,onclick:function(){view.slideIndex=Math.max(0,idx-1);box.textContent='';cwSlide(box,p,view,big,teacher)}}));
    nav.appendChild(el('span',{class:'muted',text:'第 '+(idx+1)+' / '+slides.length+' 页'}));
    nav.appendChild(el('button',{type:'button',text:'下一页 ›',disabled:idx>=slides.length-1,onclick:function(){view.slideIndex=Math.min(slides.length-1,idx+1);box.textContent='';cwSlide(box,p,view,big,teacher)}}));
    box.appendChild(nav);
  }
}
function cwRender(box,c,view,big,teacher,onTap){
  box.textContent='';view=view||{};c=c||{};
  try{
    if(c.kind==='rotation')cwRotation(box,c.params,view,big);else if(c.kind==='clock')cwClock(box,c.params,view,big);
    else if(c.kind==='steps')cwSteps(box,c.params,view,big,teacher);else if(c.kind==='slide')cwSlide(box,c.params,view,big,teacher);else cwReading(box,c.params,view,big,teacher,onTap);
  }catch(err){
    // 单个图示画坏了也不能整页白屏：清空后给一句老师看得懂的话，再给“重试”按钮。
    var reason=err&&err.message?err.message:String(err||'未知原因');
    if(typeof console!=='undefined'&&console.error)console.error('图示渲染失败',err);
    box.textContent='';
    box.appendChild(el('div',{class:'notice error',text:'图示渲染失败：'+reason}));
    box.appendChild(el('button',{type:'button',text:'重试',style:'min-height:44px',onclick:function(){cwRender(box,c,view,big,teacher,onTap)}}));
  }
}
var CW_PENDING=0,CW_VERSION=0;
function cwControl(box,c,sid,opts){
  opts=opts||{};
  var view=JSON.parse(JSON.stringify(c.view||{})),stage=el('div'),bar=el('div',{class:'row'}),msg=el('div',{role:'status'});
  box.textContent='';box.appendChild(el('h2',{text:'互动课件：'+c.kindLabel+'（大屏同步，约3秒）'}));box.appendChild(bar);box.appendChild(stage);box.appendChild(msg);
  var pending=Promise.resolve(),revision=0,syncSteps=null,syncSlide=null;
  function publicView(v){var out={};Object.keys(v||{}).sort().forEach(function(k){if(k.charAt(0)!=='_')out[k]=v[k]});return out}
  function send(){var publicState={};Object.keys(view||{}).sort().forEach(function(k){if(k.charAt(0)!=='_')publicState[k]=view[k]});publicState=JSON.parse(JSON.stringify(publicState));var sentJson=JSON.stringify(publicState);var seq=++revision;CW_PENDING++;CW_VERSION++;
    pending=pending.then(function(){return api('/teacher/weekend/sessions/'+sid+'/courseware/view',{json:{view:publicState,stageNo:c.stageNo,page:c.page}})}).then(function(r){if(seq===revision){var nextClean=publicView(r.view),same=JSON.stringify(nextClean)===sentJson;view=r.view;msg.textContent='';if(!same)draw()}}).catch(function(e){msg.textContent=e.message}).then(function(){CW_PENDING--});}
  function draw(){if(syncSteps)syncSteps();if(syncSlide)syncSlide();if(c.kind==='steps'&&c.params.figure&&c.params.figure.type==='calendar_compare')view._calendarOnChange=send;cwRender(stage,c,view,false,false,c.kind==='reading'?function(i){var k=view.highlight.indexOf(i);if(k>=0)view.highlight.splice(k,1);else view.highlight.push(i);draw();send()}:null)}
  box._cwSyncView=function(nextView){
    if(!nextView||CW_PENDING)return;
    var curJson=JSON.stringify(publicView(view));
    var nextClean=publicView(nextView);
    var nextJson=JSON.stringify(nextClean);
    if(nextJson===curJson)return;
    var sameSlide=c.kind==='slide'&&Number(nextClean.slideIndex||0)===Number(view.slideIndex||0);
    view=JSON.parse(nextJson);
    if(!sameSlide)draw();
  };
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
    var sp=c.params||{},slen=(sp.steps||[]).length;
    // 四个按钮各管一件事：上一步/下一步只动 step，答案只动 showAnswer，重来把两样都归零。
    function stepNow(){return Math.max(0,Math.min(slen,view.step||0))}
    function stepBtn(text,fn){var b=el('button',{text:text,style:'min-height:44px;min-width:44px',onclick:function(){fn();draw();send()}});bar.appendChild(b);return b}
    var prevBtn=stepBtn('上一步',function(){view.step=Math.max(0,stepNow()-1)});
    var nextBtn=stepBtn('下一步',function(){view.step=Math.min(slen,stepNow()+1)});
    var answerBtn=stepBtn('显示/隐藏答案',function(){view.showAnswer=!view.showAnswer});
    var resetBtn=stepBtn('重来',function(){view.step=0;view.showAnswer=false});
    syncSteps=function(){
      var s=stepNow();
      prevBtn.textContent='上一步（'+(s>0?s-1:0)+'）';prevBtn.disabled=s<=0;
      nextBtn.textContent='下一步（'+Math.min(slen,s+1)+'/'+slen+'）';nextBtn.disabled=s>=slen;
      answerBtn.textContent=view.showAnswer?'隐藏答案':'显示答案';answerBtn.disabled=false;
      resetBtn.textContent='重来';resetBtn.disabled=(s===0&&!view.showAnswer);
    };
  }else if(c.kind==='slide'){
    var sl=((c.params&&c.params.slides)||[]),scount=sl.length||1;
    function slideNow(){return Math.max(0,Math.min(scount-1,Number(view.slideIndex||0)))}
    function slideNavBtn(text,fn){var b=el('button',{text:text,style:'min-height:44px;min-width:44px',onclick:function(){if(!fn())return;draw();send()}});bar.appendChild(b);return b}
    var prevSlideBtn=slideNavBtn('‹ 上一页',function(){var cur=slideNow();if(cur<=0)return false;view.slideIndex=cur-1;view.audioPlaying=false;return true});
    var slidePosBadge=el('span',{style:'display:inline-flex;align-items:center;padding:6px 10px;border-radius:999px;background:#f3f4f6;color:#374151;font-size:13px;font-weight:700',text:''});
    bar.appendChild(slidePosBadge);
    var nextSlideBtn=slideNavBtn('下一页 ›',function(){var cur=slideNow();if(cur>=scount-1)return false;view.slideIndex=cur+1;view.audioPlaying=false;return true});
    var nextStageBtn=(opts.canNextStage&&opts.onNextStage)?el('button',{class:'primary',text:'进入下一环节 ›',style:'min-height:44px;min-width:44px',onclick:function(){opts.onNextStage()}}):null;
    if(nextStageBtn)bar.appendChild(nextStageBtn);
    bar.appendChild(el('button',{text:'🔊 大屏播放/暂停朗读',style:'min-height:44px;min-width:44px',onclick:function(){
      view.slideIndex=slideNow();
      view.audioPlaying=!view.audioPlaying;
      send();
      msg.textContent=view.audioPlaying?'已通知大屏播放本页朗读（约3秒同步）':'已通知大屏暂停本页朗读（约3秒同步）';
    }}));
    syncSlide=function(){
      var curIdx=slideNow();
      prevSlideBtn.disabled=curIdx<=0;
      nextSlideBtn.disabled=curIdx>=scount-1;
      slidePosBadge.textContent='本环节 第 '+(curIdx+1)+' / '+scount+' 页';
      if(nextStageBtn)nextStageBtn.hidden=curIdx<scount-1;
    };
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
var CW_STAGES=[];
function cwPlan(box,lessonId,refresh){
  var stageNo='',practiceNo='4',msg=el('div',{role:'status','aria-live':'polite'}),data=null,busy=false,editorBox=null,notes={},rowEls={},audioAuditOpen=false;
  function load(){api('/teacher/weekend/lessons/'+lessonId+'/courseware').then(paint).catch(function(e){box.textContent='';box.appendChild(el('div',{class:'notice error',text:e.message}))})}
  function itemAt(page){return (data.items||[]).filter(function(i){return String(i.stage)===stageNo&&i.page===page})[0]}
  function paint(d){
    d=d||{};
    // AI 或网络偶尔会回一个空对象：先把缺的字段补齐再画，避免 Cannot convert undefined or null to object。
    d.templates=d.templates||[];d.kindLabels=d.kindLabels||{};d.pages=d.pages||{};d.items=d.items||[];d.stageOptions=d.stageOptions||[];d.writingImages=d.writingImages||[];
    CW_STAGES=d.stageOptions;
    practiceNo=String(d.practiceStage||4);
    if(!CW_STAGES.length){box.appendChild(el('div',{class:'notice warn',text:'语文课型尚未选择，暂不能配置课件。请先在备课工作栏选择阅读课或作文课。'}));return}
    if(!stageNo||!CW_STAGES.some(function(x){return String(x.no)===stageNo})){stageNo=d.courseType&&d.courseType!=='math'?'2':'3';if(!CW_STAGES.some(function(x){return String(x.no)===stageNo}))stageNo=String(CW_STAGES[0].no);}
    data=d;rowEls={};box.textContent='';
    box.appendChild(el('p',{class:'muted',text:d.subject==='语文'?'课件生成结果是待确认草稿。按六环节核对原文、题目与素材，再逐页审核；缺项不会用其他环节内容填充。':'讲解、例题和已通过的随堂练习可逐题配置互动课件。你需逐页预览、修改、审核；随堂练习在课堂公布该题答案后才显示对应讲解。上课翻页和操作不调用 AI。'}));
    function writingImageGallery(stage){var images=d.writingImages.filter(function(x){return Number(x.stage)===Number(stage)});if(!images.length)return null;var g=el('section',{class:'card','aria-label':stage==2?'范文配图核对':'看图写话图片核对',style:'margin:12px 0'});g.appendChild(el('h3',{text:stage==2?'范文配图核对（'+images.length+' 张）':'看图写话图片核对（'+images.length+' 张）'}));var pending=images.filter(function(x){return x.status!=='confirmed'}).length;if(pending){g.appendChild(el('p',{class:'notice warn',text:'有 '+pending+' 张图片尚未确认。图片只读展示，需进入“作文素材与审核”完成用途、环节、状态及范文段落绑定后，才能通过开课检查。'}));g.appendChild(el('a',{href:'/v1/weekend-writing?lesson='+encodeURIComponent(String(d.lessonId||'')),text:'去作文素材与审核',style:'display:inline-block;margin:4px 0 10px;color:#8b1e24;font-weight:700'}));}var grid=el('div',{style:'display:flex;flex-wrap:wrap;gap:12px'});images.forEach(function(x){var c=el('div',{style:'flex:1 1 240px;max-width:420px;border:1px solid #e5e7eb;border-radius:10px;padding:10px'});c.appendChild(el('img',{src:x.dataUrl,alt:stage==2?'范文配图':'看图写话图片',style:'display:block;width:100%;max-height:280px;object-fit:contain'}));c.appendChild(el('p',{text:'状态：'+(x.status==='confirmed'?'已确认':'待确认')+'；来源：'+((x.source||{}).file||'未标明')}));if(x.targets&&x.targets.length)c.appendChild(el('p',{text:'对应段落：'+x.targets.join('；').slice(0,240)}));grid.appendChild(c)});g.appendChild(grid);return g;}
    var wholePreviewWrap=el('div',{hidden:true});
    function renderWholePreview(){
      wholePreviewWrap.textContent='';
      CW_STAGES.forEach(function(st){
        var stageItems=d.items.filter(function(it){return Number(it.stage)===Number(st.no)});

        var sec=el('div',{class:'card'});
        var stageImages=writingImageGallery(st.no);if(stageImages)sec.appendChild(stageImages);
        sec.appendChild(el('h3',{text:'第'+st.no+'环节：'+st.name}));
        if(!stageItems.length)sec.appendChild(el('p',{class:'notice warn',text:'缺少素材：请配置本环节内容并审核。'}));
        stageItems.forEach(function(it){
          sec.appendChild(el('p',{class:'muted',text:it.approved?'已审核版本（教师预览）':'已导入 · 待确认草稿（教师预览）'}));
          var previewHost=el('div');sec.appendChild(previewHost);
          var previewParams=(it.status==='approved'||!it.approved||(it.kind==='slide'&&!(it.approved.slides&&it.approved.slides.length)))?(it.params||it.approved):it.approved;
          cwRender(previewHost,{kind:it.kind,params:previewParams,kindLabel:it.kindLabel||d.kindLabels[it.kind]||it.kind},{showAllSlides:true},false,true);
        });
        wholePreviewWrap.appendChild(sec);
      });
    }
    var genAllBtn=el('button',{class:'primary',text:'补充课件草稿',onclick:function(){
      if(busy)return;busy=true;msg.className='';msg.textContent='正在补充课件草稿…';
      api('/teacher/weekend/lessons/'+lessonId+'/courseware/generate-all',{json:{}}).then(function(res){busy=false;paint(res);msg.textContent=res.notice||'已生成整套课件';if(refresh)refresh()}).catch(function(e){busy=false;msg.textContent=e.message});
    }});
    var totalSlides=0,audioCount=0;
    d.items.forEach(function(it){
      if(it.kind!=='slide')return;
      var prm=it.params||it.approved||{};
      var sls=Array.isArray(prm.slides)?prm.slides:[];
      totalSlides+=sls.length;
      sls.forEach(function(sl){if(sl&&sl.audioUrl)audioCount++});
    });
    var audioAuditWrap=el('div',{hidden:!audioAuditOpen});
    function renderAudioAudit(){
      audioAuditWrap.textContent='';
      var panel=el('div',{class:'card',style:'border:1px solid #fecaca;background:#fffaf8'});
      panel.appendChild(el('h3',{text:'🎧 音频配套核对总表（已配音 '+audioCount+' / '+totalSlides+' 页）'}));
      panel.appendChild(el('p',{class:'muted',text:'按六环节列出整套 PPT 的朗读音频与逐字原稿；点播一条时会自动暂停其余音频，方便核对或逐页上传替换 .mp3。'}));
      if(!totalSlides){panel.appendChild(el('div',{class:'notice warn',text:'当前还没有幻灯片课件，请先导入整包或添加幻灯片。'}));audioAuditWrap.appendChild(panel);return}
      CW_STAGES.forEach(function(st){
        var entries=d.items.filter(function(it){return Number(it.stage)===Number(st.no)&&it.kind==='slide'});
        entries.forEach(function(it){
          var prm=it.params||it.approved||{};
          var sls=Array.isArray(prm.slides)?prm.slides:[];
          sls.forEach(function(sl,sIdx){
            var row=el('div',{class:'card',style:'margin:8px 0;padding:10px 12px;background:#fff'});
            var top=el('div',{class:'row',style:'justify-content:space-between;align-items:center'});
            top.appendChild(el('b',{text:'第'+st.no+'环节（'+st.name+'）· 第 '+(sIdx+1)+'/'+sls.length+' 页：'+(sl.heading||'幻灯片')}));
            top.appendChild(el('span',{class:'tag '+(sl.audioUrl?'ok':'warn'),text:sl.audioUrl?'已配音':'未配音'}));
            row.appendChild(top);
            if(sl.audioLabel)row.appendChild(el('div',{class:'muted',style:'margin:4px 0',text:'配音标题：'+sl.audioLabel}));
            var ctrlRow=el('div',{class:'row',style:'margin-top:6px;align-items:center'});
            var audErr=el('div',{hidden:true,style:'margin-top:4px;color:#b42318;font-size:12px;font-weight:600'});
            if(sl.audioUrl){
              var au=cwCreateAudio(sl.audioUrl,'flex:1;min-width:220px;height:34px',audErr);
              ctrlRow.appendChild(au);
            }
            var trBox=el('div',{hidden:true,style:'margin-top:8px;padding:8px 10px;border-radius:8px;background:#fffbeb;border:1px solid #fde68a;font-size:13px;line-height:1.7;white-space:pre-wrap',text:sl.audioText||'（未填写逐字朗读原稿）'});
            var trBtn=el('button',{type:'button',text:'对照朗读原稿',onclick:function(){
              trBox.hidden=!trBox.hidden;
              trBtn.textContent=trBox.hidden?'对照朗读原稿':'收起朗读原稿';
            }});
            var repIn=el('input',{type:'file',accept:'audio/mpeg,audio/mp3,audio/*',hidden:true});
            var repStatus=el('span',{class:'muted',style:'font-size:12px'});
            var repBtn=el('button',{type:'button',text:'替换 .mp3',onclick:function(){repIn.click()}});
            repIn.addEventListener('change',function(){
              var f=repIn.files&&repIn.files[0];if(!f)return;
              if(f.size>1350000){repStatus.textContent='音频文件不能超过 1.3 MB';repIn.value='';return}
              repBtn.disabled=true;repStatus.textContent='正在读取并保存…';
              var reader=new FileReader();
              reader.onload=function(){
                var copy=JSON.parse(JSON.stringify(prm));
                if(Array.isArray(copy.slides)&&copy.slides[sIdx]){
                  copy.slides[sIdx].audioUrl=String(reader.result||'');
                  api('/teacher/weekend/lessons/'+lessonId+'/courseware',{method:'PUT',json:{stageNo:it.stage,page:it.page,kind:it.kind,params:copy,writtenTask:!!it.writtenTask}})
                    .then(function(updated){audioAuditOpen=true;msg.textContent='已替换第'+st.no+'环节第'+(sIdx+1)+'页音频（保存为草稿，需重新审核）';paint(updated);if(refresh)refresh()})
                    .catch(function(e){repStatus.textContent=e.message;repBtn.disabled=false});
                }
              };
              reader.readAsDataURL(f);
            });
            ctrlRow.appendChild(trBtn);ctrlRow.appendChild(repBtn);ctrlRow.appendChild(repIn);ctrlRow.appendChild(repStatus);
            row.appendChild(ctrlRow);row.appendChild(audErr);row.appendChild(trBox);
            panel.appendChild(row);
          });
        });
      });
      audioAuditWrap.appendChild(panel);
    }
    if(audioAuditOpen)renderAudioAudit();
    var audioAuditBtn=el('button',{text:(audioAuditOpen?'收起音频核对总表':'🎧 核对音频配套（'+audioCount+'/'+totalSlides+'）'),onclick:function(){
      audioAuditOpen=!audioAuditOpen;
      audioAuditWrap.hidden=!audioAuditOpen;
      audioAuditBtn.textContent=audioAuditOpen?'收起音频核对总表':'🎧 核对音频配套（'+audioCount+'/'+totalSlides+'）';
      if(audioAuditOpen)renderAudioAudit();
    }});
    var previewAllBtn=el('button',{text:'整体预览整套课件',onclick:function(){
      wholePreviewWrap.hidden=!wholePreviewWrap.hidden;
      previewAllBtn.textContent=wholePreviewWrap.hidden?'整体预览整套课件':'收起整体预览';
      if(!wholePreviewWrap.hidden)renderWholePreview();
    }});
    var allDrafts=d.items.filter(function(it){return it.status==='draft'});
    var approveAllStagesBtn=el('button',{class:allDrafts.length?'primary':'',disabled:!allDrafts.length,text:allDrafts.length?('一键审核全部待确认课件（'+allDrafts.length+'页）'):'全部课件已审核',onclick:function(){
      var drafts=d.items.filter(function(it){return it.status==='draft'});
      if(!drafts.length){msg.textContent='当前没有待确认的课件草稿';return}
      if(!confirm('确认已核对这 '+drafts.length+' 页待审核课件的内容和答案？通过后即可在课堂大屏显示。'))return;
      run(drafts,function(it){return api('/teacher/weekend/lessons/'+lessonId+'/courseware/approve',{json:{stageNo:it.stage,page:it.page}})},'审核');
    }});
    var preparedFile=el('input',{type:'file',accept:'.json,application/json','aria-label':'选择预制课件包',style:'display:none'});
    var fileLabel=el('span',{class:'muted',style:'font-size:13px',text:'未选择文件'});
    preparedFile.onchange=function(){
      var f=preparedFile.files&&preparedFile.files[0];
      fileLabel.textContent=f?('已选：'+f.name):'未选择文件';
    };
    var pickFileBtn=el('button',{type:'button',text:'选择课件包 (.json)',onclick:function(){preparedFile.click()}});
    var replacePrepared=el('input',{type:'checkbox'});
    replacePrepared.checked=true;
    var preparedImport=el('button',{class:'primary',text:'预检并导入课件包',onclick:function(){
      var file=preparedFile.files&&preparedFile.files[0];
      if(!file){msg.className='notice warn';msg.textContent='请先点“选择课件包 (.json)”选中文件';return}
      var reader=new FileReader();reader.onerror=function(){msg.textContent='无法读取课件包'};
      reader.onload=function(){
        var parsed,bundle;try{parsed=JSON.parse(String(reader.result||''))}catch(e){msg.textContent='课件包不是有效 JSON';return}
        if(parsed&&Array.isArray(parsed.items)&&parsed.courseware){
          msg.className='notice warn';
          msg.textContent='检测到“教案+习题+课件”完整整包。请回到本次课列表，点“导入教案/整包”；这里只用于补传课件，不会导入教案和习题。';
          return;
        }
        bundle=parsed;
        if(bundle&&bundle.courseware)bundle=bundle.courseware;
        if(!bundle||!Array.isArray(bundle.pages)){msg.textContent='课件包缺少 pages 列表';return}
        if(JSON.stringify(bundle.pages).length>18000000){msg.textContent='课件内容不能超过 18 MB，请压缩图片或分批导入';return}
        var url='/teacher/weekend/lessons/'+lessonId+'/courseware/prepared-import';
        api(url,{json:{dryRun:true,replaceExisting:replacePrepared.checked,pages:bundle.pages}}).then(function(preview){
          var warnings=(preview.pages||[]).filter(function(p){return !!p.notice}).length;
          if(!confirm('预检通过：'+preview.ready+' 页，其中 '+preview.replacing+' 页替换已有草稿，'+warnings+' 页有图示待核对提示。替换前版本可恢复，导入后需逐页审核。确定导入吗？'))return;
          return api(url,{json:{dryRun:false,replaceExisting:replacePrepared.checked,expectedRevision:preview.revision,pages:bundle.pages}}).then(function(result){paint(result.courseware);msg.className='notice ok';msg.textContent='已导入 '+result.imported+' 页草稿，可直接点“一键审核全部待确认课件”或逐页核对'})
        }).catch(function(e){msg.className='notice error';msg.textContent=e.message})
      };reader.readAsText(file,'UTF-8');
    }});
    var moreTools=el('details',{style:'display:inline-block'},
      el('summary',{style:'cursor:pointer;list-style:none;padding:7px 12px;border:1px solid #d0d5dd;border-radius:10px;background:#fff;font-size:14px;color:#344054',text:'更多工具 ▾'}),
      el('div',{class:'row',style:'margin-top:8px;padding:10px 12px;border:1px solid #e4e7ec;border-radius:10px;background:#f8fafc'},
        genAllBtn));
    var topCard=el('div',{class:'card',style:'margin:10px 0 12px;padding:14px 16px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px'},
      el('div',{class:'row',style:'align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap'},
        el('div',{class:'row',style:'align-items:center;gap:8px;flex-wrap:wrap'},
          el('b',{style:'font-size:15px;color:#0f172a',text:'导入 / 更新课件包'}),
          pickFileBtn,preparedFile,fileLabel,
          el('label',{class:'row',style:'font-size:13px;color:#475467;gap:4px;cursor:pointer'},replacePrepared,el('span',{text:'替换对应页并保留上一版'})),
          preparedImport),
        el('div',{class:'row',style:'align-items:center;gap:8px;flex-wrap:wrap'},
          approveAllStagesBtn,previewAllBtn,
          (d.subject==='语文'||totalSlides>0)?audioAuditBtn:null,
          moreTools)),
      el('div',{class:'muted',style:'margin-top:6px;font-size:12px',text:'提示：这里只用于补传课件包（不动教案与课堂记录）；若需导入含教案和习题的整包，请回到课次列表点“导入教案/整包”。'}));
    box.appendChild(topCard);
    box.appendChild(audioAuditWrap);
    box.appendChild(wholePreviewWrap);
    var stageTabs=el('div',{class:'row','aria-label':d.subject==='语文'?'六环节课件状态':'各环节课件状态',style:'margin:8px 0 10px;gap:8px;flex-wrap:wrap'});
    CW_STAGES.forEach(function(st){
      var server=(d.stageReadiness||[]).filter(function(x){return String(x.no)===String(st.no)})[0];
      var entries=d.items.filter(function(it){return Number(it.stage)===Number(st.no)});
      var draftCnt=entries.filter(function(it){return it.status==='draft'}).length;
      var approved=entries.filter(function(it){return !!it.approved}).length;
      var local=!entries.length?'未配置':draftCnt?('待审 '+draftCnt):(approved===entries.length?'已审核':'待确认');
      var label=server?server.status:local;
      var active=String(st.no)===String(stageNo);
      stageTabs.appendChild(el('button',{
        type:'button',
        class:active?'primary':'',
        style:'padding:7px 13px;border-radius:999px;font-size:13px;'+(active?'':'background:#fff;border:1px solid '+(draftCnt?'#f59e0b':'#d0d5dd')+';color:'+(draftCnt?'#b45309':'#344054')),
        text:st.no+'. '+st.name+' · '+label,
        onclick:function(){stageNo=String(st.no);paint(data)}
      }));
    });
    box.appendChild(stageTabs);
    var stageSel=el('select',{'aria-label':'环节',style:'display:none'});CW_STAGES.forEach(function(x){stageSel.appendChild(el('option',{value:x.no,text:'第'+x.no+'环节：'+x.name+((d.pages[String(x.no)]||[]).length?'（'+(d.pages[String(x.no)]||[]).length+' 项）':'')}))});
    stageSel.value=stageNo;stageSel.onchange=function(){stageNo=stageSel.value;paint(data)};
    var currentImages=writingImageGallery(stageNo);if(currentImages)box.appendChild(currentImages);
    var pages=d.pages[stageNo]||[],list=pages.length?pages.map(function(x,i){return {page:i,text:x}}):(stageNo===practiceNo?[]:[{page:null,text:'整个环节'}]);
    if(stageNo===practiceNo&&itemAt(null))list.unshift({page:null,text:'整个环节（原有课件）'});
    var seenPages={};list.forEach(function(x){seenPages[x.page===null?'null':String(x.page)]=true});
    d.items.forEach(function(it){
      if(String(it.stage)!==String(stageNo))return;
      var pk=(it.page===null||it.page===undefined)?'null':String(it.page);
      if(!seenPages[pk]){
        seenPages[pk]=true;
        list.push({page:(it.page===undefined?null:it.page),text:(it.pageText||'历史残留课件（可删除）'),orphan:true});
      }
    });
    if(stageNo===practiceNo&&!pages.length&&d.subject!=='语文')box.appendChild(el('div',{class:'notice warn',text:'暂无通过审核的课堂任务；请先导入任务并完成审核。'}));
    var redo=el('input',{type:'checkbox'});
    var all=el('button',{text:'为本环节全部 '+list.length+' 页生成',onclick:function(){
      var todo=list.filter(function(x){var it=itemAt(x.page);return redo.checked||!it});
      if(!todo.length){msg.textContent='本环节每页都已有课件；如需重新生成请勾选“包括已有课件的页”。';return}
      if(!confirm('将逐页调用 AI 生成 '+todo.length+' 页课件草稿（每页约十几秒），生成后需逐页审核才会上课堂。确定吗？'))return;
      run(todo,function(x){return api('/teacher/weekend/lessons/'+lessonId+'/courseware/generate',{json:{stageNo:+stageNo,page:x.page}})},'生成');
    }});
    var stageDrafts=list.filter(function(x){var it=itemAt(x.page);return it&&it.status==='draft'});
    var approveAll=el('button',{class:stageDrafts.length?'primary':'',disabled:!stageDrafts.length,text:stageDrafts.length?('全部草稿审核通过（本环节 '+stageDrafts.length+' 页）'):'全部草稿审核通过',onclick:function(){
      var todo=list.filter(function(x){var it=itemAt(x.page);return it&&it.status==='draft'});
      if(!todo.length){msg.textContent='没有待审核的草稿';return}
      if(!confirm('确认已逐页预览这 '+todo.length+' 页课件的内容和答案？审核后会在大屏对应页显示。'))return;
      run(todo,function(x){return api('/teacher/weekend/lessons/'+lessonId+'/courseware/approve',{json:{stageNo:+stageNo,page:x.page}})},'审核');
    }});
    var actionRow=el('div',{class:'row',style:'align-items:center;justify-content:space-between;margin:4px 0 8px'},
      el('div',{class:'row',style:'align-items:center;gap:8px'},stageSel,approveAll),
      (stageNo!==practiceNo&&d.subject!=='语文')?el('details',{},
        el('summary',{style:'cursor:pointer;list-style:none;padding:6px 10px;border:1px solid #d0d5dd;border-radius:8px;background:#fff;font-size:13px;color:#475467',text:'AI 批量生成 ▾'}),
        el('div',{class:'row',style:'margin-top:6px;padding:8px 10px;border:1px solid #e4e7ec;border-radius:8px;background:#f8fafc;gap:8px'},
          all,el('label',{class:'row',style:'font-size:13px'},redo,el('span',{text:'包括已有课件的页'})))
      ):(stageNo===practiceNo?el('span',{class:'muted',style:'font-size:13px',text:'随堂练习不调用 AI，请通过上方导入课件包或手动填写。'}):null));
    var host=d.subject==='语文'?el('section',{'aria-label':'本环节课件审核',style:'margin-top:10px'}):box;
    if(d.subject==='语文')box.appendChild(host);
    host.appendChild(actionRow);
    box.appendChild(msg);
    if(stageNo==='3'&&d.qualityAudit){
      var audit=d.qualityAudit;
      box.appendChild(el('div',{class:'notice warn',style:'margin:10px 0;white-space:normal',
        text:'课件逐页体检：共 '+audit.totalPages+' 页，已配置 '+audit.configured+' 页，发现明确问题 '+audit.flagged+' 页。全部仍须与原题逐页人工核对；机器未报警不等于验收通过。'}));
    }
    var rows=el('div'),editor=el('div');host.appendChild(rows);box.appendChild(editor);editorBox=editor;notes={};rowEls={};
    list.forEach(function(x){
      var it=itemAt(x.page),tag=!it?['','未生成']:x.orphan?['warn','历史残留 · 建议删除']:it.status==='approved'?['ok','已审核']:it.approved?['warn','已审核·有新草稿']:['warn','待审核草稿'];
      var line=el('div',{class:'item',style:'align-items:center;gap:8px'},el('span',{class:'t'},el('b',{text:(x.page==null?'':'第'+(x.page+1)+'页：')+x.text}),
        el('div',{class:'row'},el('span',{class:'tag '+tag[0],text:tag[1]}),it?el('span',{class:'muted',text:(d.kindLabels[it.kind]||'课件')+(it.writtenTask?' · 含学生作答题':'')}):null)));
       if(data.courseType==='math'&&stageNo==='3'&&d.qualityAudit&&x.page!=null){
        var auditRow=(d.qualityAudit.pages||[])[x.page];
        if(auditRow){
          var findings=(auditRow.issues||[]).concat(auditRow.warnings||[]);
          line.appendChild(el('div',{style:'flex-basis:100%;font-size:13px;color:'+(auditRow.issues.length?'#b42318':'#475467'),
            text:findings.length?'课件体检：'+findings.join('；'):'课件体检：暂无机器识别问题，仍须对照原题和课堂效果人工核对'}));
        }
      }
      var note=el('div',{role:'status','aria-live':'polite',style:'flex-basis:100%'});notes[String(x.page)]=note;
      line.appendChild(el('button',{type:'button',text:it?'预览／修改':'手动填写',onclick:function(){openEditor(x,itemAt(x.page))}}));
      if(it&&it.status==='draft')line.appendChild(el('button',{class:'primary',text:'审核通过',onclick:function(e){
        if(busy){note.className='notice warn';note.textContent='正在处理另一页，请等它完成后再点。';return}
        var btn=e&&e.target;if(btn){btn.disabled=true;btn.textContent='审核中…'}
        note.className='notice';note.textContent='正在审核这一页，请稍候…';
        run([x],function(y){return api('/teacher/weekend/lessons/'+lessonId+'/courseware/approve',{json:{stageNo:+stageNo,page:y.page}})},'审核',function(ok){
          if(!ok&&btn){btn.disabled=false;btn.textContent='审核通过'}
        });
      }}));
      var moreBtns=[];
      if(stageNo!==practiceNo)moreBtns.push(el('button',{text:it?'重新生成':'生成',onclick:function(e){
        if(busy){note.textContent='正在处理另一页，请等它完成后再点。';return}
        var b=e.target,label=b.textContent;busy=true;b.disabled=true;b.textContent='生成中…';
        note.className='notice';note.textContent='AI 正在为这一页生成课件，约十几秒，请稍候…';
        api('/teacher/weekend/lessons/'+lessonId+'/courseware/generate',{json:{stageNo:+stageNo,page:x.page}}).then(function(d){
          busy=false;paint(d);if(refresh)refresh();
          var n=notes[String(x.page)];if(n){n.className='notice ok';n.textContent='已生成新草稿'+(d.notice?'（'+d.notice+'）':'')+'，预览在下方，核对后点“审核通过”。'}
          openEditor(x,itemAt(x.page));
        }).catch(function(err){busy=false;b.disabled=false;b.textContent=label;note.className='notice error';note.textContent=err.message});
      }}));
      if(it&&it.previousDraft)moreBtns.push(el('button',{text:'恢复上一版',onclick:function(){
        if(!confirm('恢复这一页上一次的课件草稿？恢复后请重新核对。'))return;
        api('/teacher/weekend/lessons/'+lessonId+'/courseware/restore-previous',{json:{stageNo:+stageNo,page:x.page}})
          .then(function(d2){paint(d2);msg.textContent='已恢复上一版草稿，请预览核对。'})
          .catch(function(e){note.className='notice error';note.textContent=e.message});
      }}));
      if(it)moreBtns.push(el('button',{text:'存为模板',onclick:function(){
        var name=prompt('给这个模板起个名字，以后可以套用到其它课：',(data.subject||'')+'课件模板');
        if(name===null)return;
        api('/teacher/weekend/lessons/'+lessonId+'/courseware/save-as-template',{json:{stageNo:+stageNo,page:x.page,name:name}})
          .then(function(r){msg.textContent='已存为模板：'+r.name}).catch(function(e){msg.textContent=e.message});
      }}));
      moreBtns.push(el('button',{text:'套用模板',onclick:function(){pickTemplate(x)}}));
      if(it)moreBtns.push(el('button',{text:'删除',onclick:function(){if(confirm('删除这一页的课件？'))api('/teacher/weekend/lessons/'+lessonId+'/courseware/remove',{json:{stageNo:+stageNo,page:x.page}}).then(function(d2){paint(d2);if(refresh)refresh()}).catch(function(e){msg.textContent=e.message})}}));
      var moreBox=el('div',{class:'row',style:'margin-top:6px;gap:6px;flex-wrap:wrap'});
      moreBtns.forEach(function(b){moreBox.appendChild(b)});
      var moreMenu=el('details',{style:'display:inline-block'},
        el('summary',{style:'cursor:pointer;list-style:none;padding:6px 10px;border:1px solid #d0d5dd;border-radius:8px;background:#fff;font-size:13px;color:#475467',text:'更多 ▾'}),
        moreBox);
      line.appendChild(moreMenu);
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
      // 预览失败时不能只在行里写一句英文报错：给原因，也给一个能再试一次的按钮。
      var note=notes[String(x.page)],why=err&&err.message?err.message:'页面脚本异常';
      if(typeof console!=='undefined'&&console.error)console.error('课件预览打开失败',err);
      if(editorBox){
        editorBox.textContent='';
        var failCard=el('div',{class:'card'});
        failCard.appendChild(el('div',{class:'notice error',text:'预览失败：'+why}));
        failCard.appendChild(el('button',{type:'button',text:'重试',onclick:function(){openEditor(x,it)}}));
        editorBox.appendChild(failCard);
      }
      if(note){note.className='notice error';note.textContent='预览失败：'+why}
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
  function run(todo,call,label,done){
    if(busy)return;busy=true;var failed=[],i=0,last=null;
    function next(){
      if(i>=todo.length){busy=false;if(last)paint(last);msg.textContent=label+'完成 '+(todo.length-failed.length)+'/'+todo.length+' 页'+(failed.length?'。未完成：\n'+failed.join('\n'):'');if(done)done(failed.length===0);if(refresh)refresh();
        return}
      var x=todo[i++];msg.textContent='正在'+label+'第 '+i+'/'+todo.length+' 页…';
      call(x).then(function(d){last=d}).catch(function(e){failed.push(e.message)}).then(next);
    }
    next();
  }
  function edit(box2,x,it){
    data=data||{};data.templates=data.templates||[];data.kindLabels=data.kindLabels||{};
    var kinds=data.templates;
    if(!kinds.length){
      // 模板列表也可能是空的（比如页面数据没加载完），先给一句人话，不要让预览直接抛异常。
      box2.textContent='';
      box2.appendChild(el('div',{class:'notice error',text:'预览失败：这一课还没有可用的课件模板，请刷新页面后再试。'}));
      return;
    }
    box2.textContent='';var card=el('div',{class:'card'}),fields={},kind=it&&it.kind?it.kind:kinds[kinds.length-1],p=JSON.parse(JSON.stringify(it&&it.params?it.params:{})),previewState={step:0,previewMode:true},preview=el('div',{class:'card',style:'max-height:76vh;overflow:auto;box-shadow:0 8px 24px #10182822'});
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
      // Repair the known equal-base/equal-height visuals from visible source text, including legacy drafts.
      if(sourceText.indexOf('平行四边形')>=0&&sourceText.indexOf('三个图形')>=0&&sourceText.indexOf('底均为')>=0&&sourceText.indexOf('平行线间距')>=0){
        var baseMatch=sourceText.match(/底(?:均)?\\s*(?:为|是)?\\s*(\\d+(?:\\.\\d+)?)\\s*(?:cm|厘米)/i);
        var heightMatch=sourceText.match(/平行线间距(?:离)?(?:为|是)?\\s*(\\d+(?:\\.\\d+)?)\\s*(?:cm|厘米)/i);
        p.figure={type:'equal_base_height',base:baseMatch?Number(baseMatch[1]):3,height:heightMatch?Number(heightMatch[1]):7};
      }else if(sourceText.indexOf('平行四边形')>=0&&sourceText.indexOf('底被平均分成')>=0&&sourceText.indexOf('中间涂色')>=0&&sourceText.indexOf('高不变')>=0){
        var totalMatch=sourceText.match(/(?:原图面积|面积)\\s*(?:为|是)?\\s*(\\d+(?:\\.\\d+)?)\\s*(?:平方厘米|cm²|cm2)/i);
        p.figure={type:'parallelogram_thirds',parts:3,totalArea:totalMatch?Number(totalMatch[1]):36};
      }
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
    var templateRow=el('div',{class:'row'},el('span',{text:'模板'}),kindSel);
     if(stageNo!==practiceNo)templateRow.appendChild(el('label',{class:'row'},task,el('span',{text:'审核后同时生成学生书面作答任务'})));
    card.appendChild(templateRow);
    var form=el('div');card.appendChild(form);card.appendChild(preview);
    function input(v){var n=el('input',{type:'text'});n.value=v==null?'':String(v);return n}
    function area(v){var n=el('textarea');n.value=v||'';return n}
    function fieldTo(host,key,label,node){fields[key]=node;host.appendChild(el('label',{class:'field'},el('span',{text:label}),node));node.addEventListener('input',show);node.addEventListener('change',show)}
    function field(key,label,node){fieldTo(form,key,label,node)}
    function sel(opts,v){var n=el('select');opts.forEach(function(o){n.appendChild(el('option',{value:o[0],text:o[1]}))});n.value=String(v);return n}
    function build(){
      form.textContent='';fields={};kind=kindSel.value;
      if(kind==='slide'){card.insertBefore(preview,form)}else{card.insertBefore(form,preview)}
      if(kind!=='slide')field('title','标题',input(p.title));
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
        var f=p.figure||{},choices=[['','不画图'],['segment','线段和点'],['flow','计算程序图'],['shape','图形'],['table','数表'],['equal_base_height','等底等高平行四边形'],['parallelogram_thirds','平行四边形底三等分'],['parallelogram_methods','平行四边形四种转化方法'],['calendar_compare','月历框形辨析'],['calendar_cross','\u6708\u5386\u5341\u5b57\u6846'],['seating_pattern','方桌人数规律'],['alternating_triangle','黑白棋子三角形'],['running_track','环形跑道追及'],['triangular_numbers','三角形数规律'],['tile_pattern','地砖排列规律'],['square_sticks_pattern','连续正方形小棒规律'],['hundred_chart_square','百数表田字形四数规律'],['obtuse_triangle_height','钝角三角形与底边延长线']];if(f.type==='uploaded_image')choices.unshift(['uploaded_image','原卷图片']);var ft=sel(choices,f.type||'');
        field('figType','图示（大屏上画出题目条件）',ft);ft.onchange=function(){var keep=collect();keep.figure=ft.value==='equal_base_height'?{type:ft.value,base:3,height:7}:ft.value==='parallelogram_thirds'?{type:ft.value,parts:3,totalArea:36}:ft.value==='parallelogram_methods'?{type:ft.value}:ft.value==='calendar_compare'?{type:ft.value}:ft.value==='calendar_cross'?{type:ft.value,center:18,daysInMonth:31,firstWeekday:0,total:90}:ft.value==='seating_pattern'?{type:ft.value,sampleCounts:[8,12,16]}:ft.value==='alternating_triangle'?{type:ft.value,rows:6,differenceSymbol:'m'}:ft.value==='running_track'?{type:ft.value,fastSpeed:180,slowSpeed:140,distanceSymbol:'s'}:ft.value==='triangular_numbers'?{type:ft.value,terms:[1,3,6,10,15],targetTerm:10}:ft.value==='tile_pattern'?{type:ft.value,whiteCounts:[5,8],blueCounts:[4,7],targetTerm:10,targetBlue:100}:ft.value==='square_sticks_pattern'?{type:ft.value,sampleCounts:[4,7,10],targetSquares:[8,60],targetSticks:100}:ft.value==='hundred_chart_square'?{type:ft.value,topLeftNumber:45}:ft.value==='obtuse_triangle_height'?{type:ft.value,base:7,side:15,height:7.5,unit:'cm'}:{type:ft.value,points:[],marks:[],boxes:[],branches:[],labels:{},rows:[],shape:'rectangle'};p=keep;build()};
        if(f.type==='equal_base_height'){
          field('figBase','三个图形的底（cm）',input(f.base||3));field('figHeight','平行线间距／高（cm）',input(f.height||7));
        }else if(f.type==='parallelogram_thirds'){
          field('figTotalArea','原平行四边形面积（平方厘米）',input(f.totalArea||36));
        }else if(f.type==='segment'){
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
        }else if(f.type==='obtuse_triangle_height'){
          field('figBase','底 BC（正数）',input(f.base==null?7:f.base));field('figSide','斜边 AC（正数，最长边）',input(f.side==null?15:f.side));
          field('figHeight','底边延长线上的高（正数）',input(f.height==null?7.5:f.height));field('figUnit','单位（如 cm）',input(f.unit||'cm'));
        }else if(f.type==='table'){
          field('figA','数表（每行一行，格子用 | 隔开）',area((f.rows||[]).map(function(r){return r.join(' | ')}).join('\n')));
        }
      }else if(kind==='slide'){
        if(!Array.isArray(p.slides)||!p.slides.length)p.slides=[{layout:'standard',heading:p.title||'幻灯片',body:[x.text||''],highlight:'',audioLabel:'',audioText:'',audioUrl:''}];
        var slideEditorDetails=el('details',{style:'margin:8px 0'},el('summary',{style:'cursor:pointer;font-weight:700;color:#8b1e24',text:'展开编辑本组幻灯片文字、配音与页数（共 '+p.slides.length+' 页）'}));
        var slidesBox=el('div');
        fieldTo(slideEditorDetails,'title','幻灯片组标题',input(p.title));
        slideEditorDetails.appendChild(slidesBox);form.appendChild(slideEditorDetails);
        function renderSlideFields(){
          slidesBox.textContent='';
          p.slides.forEach(function(sl,sIdx){
            var scard=el('div',{class:'card',style:'margin:8px 0;padding:10px'});
            var hdr=el('div',{class:'row',style:'justify-content:space-between'});
            var badges=[];
            if(sl.figure&&sl.figure.type)badges.push('配图');
            if(Array.isArray(sl.gallery)&&sl.gallery.length)badges.push('多图分镜');
            if(sl.audioUrl)badges.push('真人配音');
            if(Array.isArray(sl.characters)&&sl.characters.length)badges.push('人物档案');
            if(Array.isArray(sl.plot)&&sl.plot.length)badges.push('情节脉络');
            if(Array.isArray(sl.cards)&&sl.cards.length)badges.push('考点卡片');
            if(Array.isArray(sl.qa)&&sl.qa.length)badges.push('互动点拨');
            hdr.appendChild(el('b',{text:'第 '+(sIdx+1)+' 页幻灯片'+(badges.length?'（含：'+badges.join(' / ')+'）':'')}));
            if(p.slides.length>1)hdr.appendChild(el('button',{type:'button',text:'删除本页',onclick:function(){p.slides.splice(sIdx,1);renderSlideFields();show()}}));
            scard.appendChild(hdr);
            var hIn=input(sl.heading||''),subIn=input(sl.subtitle||''),bIn=area((sl.body||[]).join('\n')),hlIn=input(sl.highlight||''),alIn=input(sl.audioLabel||''),atIn=area(sl.audioText||''),auIn=input(sl.audioUrl||'');
            [['页标题',hIn,function(){sl.heading=hIn.value}],['副标题',subIn,function(){sl.subtitle=subIn.value}],['正文段落（每行一段，可用 ==重点== 高亮）',bIn,function(){sl.body=lines(bIn)}],['重点／答题模板（高亮框）',hlIn,function(){sl.highlight=hlIn.value}],['配音标题',alIn,function(){sl.audioLabel=alIn.value}],['逐字朗读原稿（核对音频用）',atIn,function(){sl.audioText=atIn.value}],['真人音频链接或 data:audio URL',auIn,function(){sl.audioUrl=auIn.value}]].forEach(function(row){
              var fn=function(){row[2]();show()};row[1].addEventListener('input',fn);row[1].addEventListener('change',fn);
              scard.appendChild(el('label',{class:'field'},el('span',{text:row[0]}),row[1]));
            });
            var mp3In=el('input',{type:'file',accept:'audio/mpeg,audio/mp3,audio/*',hidden:true});
            var mp3Btn=el('button',{type:'button',text:'上传本地 .mp3',onclick:function(){mp3In.click()}});
            mp3In.addEventListener('change',function(){
              var f=mp3In.files&&mp3In.files[0];if(!f)return;
              if(f.size>1350000){mp3In.value='';return}
              var reader=new FileReader();
              reader.onload=function(){sl.audioUrl=String(reader.result||'');auIn.value=sl.audioUrl;renderSlideFields();show()};
              reader.readAsDataURL(f);
            });
            scard.appendChild(el('div',{class:'row',style:'margin-top:4px'},mp3Btn,mp3In));
            slidesBox.appendChild(scard);
          });
          if(p.slides.length<12)slidesBox.appendChild(el('button',{type:'button',text:'+ 添加一页幻灯片',onclick:function(){p.slides.push({layout:'standard',heading:'新页面',body:[],highlight:'',audioLabel:'',audioUrl:''});renderSlideFields();show()}}));
        }
        renderSlideFields();
        fieldTo(slideEditorDetails,'teacherNotes','教师备课提示（仅老师可见）',area(p.teacherNotes||''));
      }else{
        field('passage','阅读材料（必须是原文中的连续段落）',area(p.passage));field('question','阅读问题',area(p.question));
        field('material','补充资料（请核实）',area(p.material));field('writingPrompt','书面解释要求',area(p.writingPrompt));p.evidence=p.evidence||[];
      }
      if(kind!=='reading'&&kind!=='slide')field('question','学生书面作答问题',area(p.question));
      if(kind!=='slide')field('reference','评分要点（仅老师可见）',area(p.reference));
      show();
    }
    function lines(n){return n.value.split('\n').map(function(v){return v.trim()}).filter(Boolean)}
    function parts(v,sep){return String(v||'').split(sep).map(function(x){return x.trim()}).filter(Boolean)}
    function figure(){
      var t=fields.figType?fields.figType.value:'';if(!t)return {};if(t==='uploaded_image')return p.figure||{};
      if(t==='equal_base_height')return {type:t,base:Number(fields.figBase.value),height:Number(fields.figHeight.value)};
      if(t==='parallelogram_thirds')return {type:t,parts:3,totalArea:Number(fields.figTotalArea.value)};
      if(t==='parallelogram_methods')return {type:t};
      if(t==='calendar_compare')return {type:t};
      if(t==='calendar_cross')return {type:t,center:Number(fields.figCenter.value),daysInMonth:Number(fields.figDays.value),firstWeekday:Number(fields.figWeekday.value),total:Number(fields.figTotal.value)};
      if(t==='seating_pattern')return {type:t,sampleCounts:parts(fields.figCounts.value,/,/).map(function(x){return Number(x)})};
      if(t==='alternating_triangle')return {type:t,rows:Number(fields.figRows.value),differenceSymbol:fields.figDiff.value};
      if(t==='running_track')return {type:t,fastSpeed:Number(fields.figFast.value),slowSpeed:Number(fields.figSlow.value),distanceSymbol:fields.figDistanceSymbol.value};
      if(t==='triangular_numbers')return {type:t,terms:parts(fields.figTerms.value,/,/).map(function(x){return Number(x)}),targetTerm:Number(fields.figTarget.value)};
      if(t==='tile_pattern')return {type:t,whiteCounts:parts(fields.figWhiteCounts.value,/,/).map(function(x){return Number(x)}),blueCounts:parts(fields.figBlueCounts.value,/,/).map(function(x){return Number(x)}),targetTerm:Number(fields.figTarget.value),targetBlue:Number(fields.figBlueTarget.value)};
      if(t==='square_sticks_pattern')return {type:t,sampleCounts:parts(fields.figSquareCounts.value,/,/).map(function(x){return Number(x)}),targetSquares:parts(fields.figTargets.value,/,/).map(function(x){return Number(x)}),targetSticks:Number(fields.figTargetSticks.value)};
      if(t==='hundred_chart_square')return {type:t,topLeftNumber:Number(fields.figHundredTop.value)};
      if(t==='obtuse_triangle_height')return {type:t,base:Number(fields.figBase.value),side:Number(fields.figSide.value),height:Number(fields.figHeight.value),unit:fields.figUnit.value||'cm'};
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
      if(kind==='slide'){
        return {
          title:fields.title.value,
          slides:(p.slides||[]).map(function(sl){
            return {
              layout:sl.layout||'standard',
              badge:sl.badge||'',
              heading:sl.heading||'',
              subtitle:sl.subtitle||'',
              caption:sl.caption||'',
              body:Array.isArray(sl.body)?sl.body:[],
              characters:Array.isArray(sl.characters)?sl.characters:[],
              plot:Array.isArray(sl.plot)?sl.plot:[],
              cards:Array.isArray(sl.cards)?sl.cards:[],
              steps:Array.isArray(sl.steps)?sl.steps:[],
              qa:Array.isArray(sl.qa)?sl.qa:[],
              highlight:sl.highlight||'',
              audioLabel:sl.audioLabel||'',
              audioText:sl.audioText||'',
              audioUrl:sl.audioUrl||'',
              figure:sl.figure||{},
              gallery:Array.isArray(sl.gallery)?sl.gallery:[],
              audioScenes:Array.isArray(sl.audioScenes)?sl.audioScenes:[]
            };
          }),
          teacherNotes:fields.teacherNotes?fields.teacherNotes.value:''
        };
      }
      var v={title:fields.title.value,question:fields.question?fields.question.value:'',reference:fields.reference?fields.reference.value:''};
      if(kind==='rotation'){v.width=+fields.width.value;v.height=+fields.height.value;v.shape=fields.shape.value.split(/[;；]/).filter(function(x){return x.trim()}).map(pt);v.center=pt(fields.center.value);v.direction=fields.direction.value;v.angle=+fields.angle.value;v.steps=lines(fields.steps)}
      else if(kind==='clock'){v.start=+fields.start.value;v.direction=fields.direction.value;v.angle=+fields.angle.value;v.steps=lines(fields.steps)}
      else if(kind==='steps'){v.problem=fields.problem.value;v.sourceProblem=p.sourceProblem||'';v.steps=lines(fields.steps);v.answer=fields.answer.value;v.figure=figure();v.sourceFigure=p.sourceFigure||{};v.stepFigures=(p.stepFigures||[]).length===v.steps.length+1?p.stepFigures:[]}
      else{v.passage=fields.passage.value;v.sentences=cwSplit(v.passage);v.material=fields.material.value;v.writingPrompt=fields.writingPrompt.value;p.evidence=(p.evidence||[]).filter(function(i){return i<v.sentences.length});v.evidence=p.evidence}
      return v;
    }
    function show(){
      var v=collect(),title=el('b',{text:'预览（教师视角，含答案）'}),view=el('div');preview.textContent='';preview.appendChild(el('div',{class:'row',style:'justify-content:space-between'},title,el('span',{class:'tag',text:cwPreviewFigureTag(kind,v)})));preview.appendChild(view);
      if(kind==='slide'){
        previewState.slideIndex=Math.max(0,Math.min((v.slides||[]).length-1,Number(previewState.slideIndex||0)));
        cwRender(view,{kind:'slide',params:v},previewState,false,true);
      }else if(kind==='rotation'){if(!(v.shape.length>=3&&v.center.length===2&&v.shape.every(function(q){return q.length===2&&isFinite(q[0])&&isFinite(q[1])}))){view.appendChild(el('div',{class:'notice warn',text:'坐标格式不完整'}));return}
        v.rotated=v.shape.map(function(q){return cwRotate(q,v.center,v.direction,v.angle)});cwRender(view,{kind:kind,params:v},{angle:v.angle,showResult:true,showCenter:true,step:v.steps.length},false,true)}
      else if(kind==='clock'){var t=v.angle/30*(v.direction==='cw'?1:-1);v.end=((v.start-1+t)%12+12)%12+1;cwRender(view,{kind:kind,params:v},{angle:v.angle,showResult:true,step:v.steps.length},false,true)}
      else if(kind==='steps'){
        previewState.step=Math.max(0,Math.min(previewState.step,v.steps.length));
        var nav=el('div',{class:'row',style:'margin:8px 0'});
        nav.appendChild(el('button',{text:'上一步',disabled:previewState.step<=0,onclick:function(){previewState.step=Math.max(0,previewState.step-1);show()}}));
        nav.appendChild(el('button',{text:'下一步（'+Math.min(v.steps.length,previewState.step+1)+'/'+v.steps.length+'）',disabled:previewState.step>=v.steps.length,onclick:function(){previewState.step=Math.min(v.steps.length,previewState.step+1);show()}}));
        nav.appendChild(el('button',{text:previewState.showAnswer?'隐藏答案':'显示答案',onclick:function(){previewState.showAnswer=!previewState.showAnswer;show()}}));
        nav.appendChild(el('span',{class:'muted',text:'已展开 '+previewState.step+' / '+v.steps.length+' 步'}));preview.appendChild(nav);
        if(v.figure&&v.figure.type==='calendar_compare')previewState._calendarOnChange=show;
        cwRender(view,{kind:kind,params:v},previewState,false,true);
      }
      else cwRender(view,{kind:kind,params:v},{showMaterial:true,showPrompt:true},false,true,function(i){var k=p.evidence.indexOf(i);if(k>=0)p.evidence.splice(k,1);else p.evidence.push(i);show()});
    }
    kindSel.onchange=build;build();
    var m2=el('div',{role:'status'});
    var save=el('button',{text:'保存修改（需重新审核）',onclick:function(){
      if(busy)return;
      var params;try{params=collect()}catch(e){m2.textContent='无法保存：'+(e.message||'请检查课件内容');return}
      busy=true;save.disabled=true;save.textContent='正在保存…';m2.textContent='正在保存，请稍候，完成后仍需审核。';
      api('/teacher/weekend/lessons/'+lessonId+'/courseware',{method:'PUT',json:{stageNo:+stageNo,page:x.page,kind:kind,params:params,writtenTask:task.checked}}).then(function(d){busy=false;paint(d);msg.textContent='第'+(x.page==null?'整个环节':(x.page+1)+'页')+'课件已保存为草稿，请核对后点击审核通过。'}).catch(function(e){busy=false;save.disabled=false;save.textContent='保存修改（需重新审核）';m2.textContent='保存未确认：'+e.message+'。请检查后重试。'})
    }});
    card.appendChild(el('div',{class:'row'},save));card.appendChild(m2);
    if(it&&it.writtenTaskPreview)card.appendChild(el('details',{},el('summary',{text:'学生书面作答题（勾选后审核时生成）'}),el('pre',{style:'white-space:pre-wrap;font:inherit',text:it.writtenTaskPreview.stem}),el('pre',{style:'white-space:pre-wrap;font:inherit;color:#667085',text:'参考答案（仅老师可见）：'+it.writtenTaskPreview.reference})));
    box2.appendChild(card);card.scrollIntoView&&card.scrollIntoView();
  }
  load();
}
"""


