/* ES5-only override of lesson 11's dedicated four-method SVG.
 * Separate external script: precompiled Safari12 inline assets remain unchanged.
 * Before reveal: all four starts are genuine parallelograms, with actionable cuts.
 */
(function(){
  var previousFigureText=window.cwFigureText;
  window.cwFigureText=function(f){
    if(f&&f.type==='parallelogram_methods')return '四种操作：左侧沿高剪移、整图平移、右侧沿高剪移、换方向沿高剪移';
    return previousFigureText(f);
  };
  // Earlier imports describe a different M/N-midpoint variant. Never silently
  // display these final-paper cuts under that incompatible source question.
  var previousSteps=window.cwSteps;
  if(typeof previousSteps==='function'){
    window.cwSteps=function(box,p,view,big,teacher){
      var source=String((p&&(p.sourceProblem||p.problem))||'');
      var legacy=!!(p&&p.figure&&p.figure.type==='parallelogram_methods'&&/(?:点\s*M\s*[、,，]\s*N|M\s*[、,，]\s*N|中点)/.test(source));
      if(legacy){
        box.appendChild(el('div',{class:'notice warn',text:teacher?
          '第2题仍是旧版 M、N 中点题干，和最终审核稿的左右剪移四法不一致。请更新教案原题后再审核。':
          '第2题题干与图形版本不一致，本页互动图已暂停展示，请教师复核。'}));
        if(!teacher)return;
      }
      return previousSteps(box,p,view,big,teacher);
    };
  }
  window.cwParallelogramMethods=function(box,view,big,teacher){
    view=view||{};
    var answer=!!view.showAnswer||!!(teacher&&view.previewMode&&Number(view.step)>=5);
    var focused=teacher&&view.previewMode&&!answer?Math.max(1,Math.min(4,Number(view.step)||1)):0;
    var outer=el('div',{style:'max-width:1000px;margin:6px auto;padding:8px;border:1px solid #d0d5dd;border-radius:10px;background:#fff'});
    box.appendChild(outer);
    if(!document.createElementNS||!cwNode('svg',{}).createSVGRect){
      outer.appendChild(el('p',{text:'图示加载失败：不能仅凭文字判断四种剪拼方法，请对照原题图。'}));return;
    }
    var svg=cwNode('svg',{viewBox:'0 0 880 263',width:'100%',role:'img',
      'aria-label':'四种操作示意。学生初始只看平行四边形、剪切线和移动箭头，教师揭示后出现拼接结果。',
      style:'display:block;max-height:'+(big?'47vh':'360px')});
    outer.appendChild(svg);
    var ink='#244358',blue='#d9e9f5',piece='#f6ce91',move='#23689b',ghost='#8595a6';
    function add(g,t,attr,v){var n=cwNode(t,attr,v);g.appendChild(n);return n;}
    function path(g,d,color,dash,w){return add(g,'path',{d:d,fill:'none',stroke:color||ink,'stroke-width':w||2.3,'stroke-dasharray':dash||''});}
    function polygon(g,points,fill,color,dash){return add(g,'polygon',{points:points,fill:fill||blue,stroke:color||ink,'stroke-width':2.3,'stroke-dasharray':dash||''});}
    function text(g,x,y,value,size,color){return add(g,'text',{x:x,y:y,'font-size':size||15,fill:color||ink,'text-anchor':'middle','font-weight':'600'},value);}
    function line(g,x1,y1,x2,y2,color,dash,w){return path(g,'M '+x1+' '+y1+' L '+x2+' '+y2,color,dash,w);}
    function arrow(g,x1,y1,x2,y2){
      line(g,x1,y1,x2,y2,move,'',2.6);
      var a=Math.atan2(y2-y1,x2-x1),dx=8*Math.cos(a),dy=8*Math.sin(a);
      var nx=5*Math.sin(a),ny=-5*Math.cos(a);
      add(g,'polygon',{points:x2+','+y2+' '+(x2-dx+nx)+','+(y2-dy+ny)+' '+(x2-dx-nx)+','+(y2-dy-ny),fill:move,stroke:move});
    }
    function rectangle(g,x1,y1,x2,y2){return polygon(g,x1+','+y1+' '+x2+','+y1+' '+x2+','+y2+' '+x1+','+y2,blue);}
    function base(g){return polygon(g,'40,191 146,191 174,105 68,105',blue);}
    var names=['①','②','③','④'],descs=['左侧沿高剪移','整图向右平移','右侧沿高剪移','换方向后沿高剪移'];
    for(var i=0;i<4;i++){
      var g=add(svg,'g',{transform:'translate('+(i*220)+',0)'});
      add(g,'rect',{x:5,y:41,width:210,height:196,rx:10,fill:focused===i+1?'#fff8e9':'#fff',
        stroke:focused===i+1?'#cb7616':'#ccd7e2','stroke-width':focused===i+1?2.7:1.4});
      text(g,110,29,names[i],24,ink);
      text(g,110,255,descs[i],13,'#526577');
      if(!answer){
        if(i===0){
          base(g);polygon(g,'40,191 68,191 68,105',piece,ink);
          line(g,68,105,68,191,move,'6 4',2.2);arrow(g,61,89,164,89);
        }else if(i===1){
          base(g);arrow(g,73,88,165,88);
        }else if(i===2){
          base(g);polygon(g,'146,191 174,105 146,105',piece,ink);
          line(g,146,105,146,191,move,'6 4',2.2);arrow(g,164,89,59,89);
        }else{
          polygon(g,'75,79 168,123 168,210 75,166',blue);
          polygon(g,'75,166 168,166 168,210',piece,ink);
          line(g,75,166,168,166,move,'6 4',2.2);arrow(g,191,188,191,97);
        }
      }else if(i===0){
        rectangle(g,68,105,174,191);
        polygon(g,'146,191 174,191 174,105',piece,ink);
        line(g,146,191,174,105,ink,'',1.8);
      }else if(i===1){
        polygon(g,'40,191 146,191 174,105 68,105','none',ghost,'5 5');
        polygon(g,'56,191 162,191 190,105 84,105',blue);
      }else if(i===2){
        rectangle(g,40,105,146,191);
        polygon(g,'40,105 68,105 40,191',piece,ink);
        line(g,68,105,40,191,ink,'',1.8);
      }else{
        rectangle(g,75,79,168,166);
        polygon(g,'75,79 168,79 168,123',piece,ink);
        line(g,75,79,168,123,ink,'',1.8);
      }
    }
    outer.appendChild(el('p',{class:'muted',style:'margin:5px 0 0;font-size:12px',
      text:answer?'已揭示：①③④为等面积长方形；②整体平移后仍为平行四边形。':'学生观察态：虚线表示切割线，蓝色箭头表示移动方向；尚未显示拼接结果。'}));
  };
}());

(function(){
  var previousSteps=window.cwSteps;
  function isFourMethodQuestion(p){
    var s=[p&&p.title||'',p&&p.problem||'',p&&p.sourceProblem||''].join(' ');
    return /第\s*2\s*题/.test(s) && s.indexOf('平行四边形')>=0 &&
      /四种(?:操作|方法|转化)/.test(s) &&
      !/(?:点\s*M\s*[、,，]\s*N|M\s*[、,，]\s*N|中点)/.test(s);
  }
  function lesson11Figure(p){
    var s=[p&&p.title||'',p&&p.problem||'',p&&p.sourceProblem||''].join(' ');
    return isFourMethodQuestion(p) || (/第\s*5\s*题/.test(s)&&s.indexOf('方格测量')>=0)||
      (/第\s*6\s*题/.test(s)&&s.indexOf('两组对应底高')>=0)||
      (/第\s*8\s*题/.test(s)&&s.indexOf('面积累加')>=0)||
      (/第\s*10\s*题/.test(s)&&s.indexOf('等高分割')>=0)||
      (/第\s*14\s*题/.test(s)&&s.indexOf('200 m')>=0&&s.indexOf('40000')>=0)||
      (/第\s*15\s*题/.test(s)&&s.indexOf('倍拼')>=0)||
      (/第\s*16\s*题/.test(s)&&s.indexOf('面积关系')>=0)||
      (/第\s*17\s*题/.test(s)&&s.indexOf('等面积三角形')>=0)||
      (/第\s*18\s*题/.test(s)&&s.indexOf('直角三角形')>=0)||
      (/第\s*20\s*题/.test(s)&&s.indexOf('破损玻璃')>=0)||
      (/第\s*21\s*题/.test(s)&&s.indexOf('阴影面积')>=0)||
      (/第\s*22\s*题/.test(s)&&s.indexOf('割补思想')>=0)||
      (/第\s*23\s*题/.test(s)&&s.indexOf('逆向应用')>=0);
  }
  function cwLesson11Parallelogram(box,p,view,big,teacher){
  var source=[p.title||'',p.problem||'',p.sourceProblem||''].join(' ');
  if(isFourMethodQuestion(p)){cwParallelogramMethods(box,view,big,teacher);return true;}
  var q5=/第\s*5\s*题/.test(source)&&source.indexOf('方格测量')>=0;
  var q10=/第\s*10\s*题/.test(source)&&source.indexOf('等高分割')>=0;
  var q6=/第\s*6\s*题/.test(source)&&source.indexOf('两组对应底高')>=0;
  var q8=/第\s*8\s*题/.test(source)&&source.indexOf('面积累加')>=0;
  var q15=/第\s*15\s*题/.test(source)&&source.indexOf('倍拼')>=0;
  var q16=/第\s*16\s*题/.test(source)&&source.indexOf('面积关系')>=0;
  var q17=/第\s*17\s*题/.test(source)&&source.indexOf('等面积三角形')>=0;
  var q18=/第\s*18\s*题/.test(source)&&source.indexOf('直角三角形')>=0;
  var q20=/第\s*20\s*题/.test(source)&&source.indexOf('破损玻璃')>=0;
  var q21=/第\s*21\s*题/.test(source)&&source.indexOf('阴影面积')>=0;
  var q23=/第\s*23\s*题/.test(source)&&source.indexOf('逆向应用')>=0;
  var q22=/第\s*22\s*题/.test(source)&&source.indexOf('割补思想')>=0;
  var q14=/第\s*14\s*题/.test(source)&&source.indexOf('200 m')>=0&&source.indexOf('40000')>=0;
  if(!q5&&!q6&&!q8&&!q10&&!q14&&!q15&&!q16&&!q17&&!q18&&!q20&&!q21&&!q22&&!q23)return false;
  var wrap=el('div',{style:'max-width:900px;margin:10px auto;padding:10px;background:#fff;border:1px solid #d0d5dd;border-radius:10px'});
  var svg=cwNode('svg',{viewBox:q10?'0 0 700 360':q22?'0 0 1400 380':q23?'0 0 1000 390':q21?'0 0 1000 390':q20?'0 0 1000 390':q18?'0 0 1000 360':q6?'0 0 860 350':(q15?'0 0 940 340':(q16?'0 0 1040 350':(q17?'0 0 1000 350':(q5?'0 0 560 360':(q14?'0 0 560 350':'0 0 560 310'))))),width:'100%',style:'display:block;max-height:'+(big?'44vh':'360px'),role:'img','aria-label':q10?'底边三等分且中间部分高不变的平行四边形':q22?'三角形剪切、移动拼成长方形及任意三角形倍拼验证':q23?'原三角形与等面积长方形的割补前后对照':q21?'底边三等分且阴影三角形占一份的平行四边形':q20?'标出缺口的45度直角三角形玻璃残片及面积计算过程':q18?'半厘米方格三角形与标出直角的三角形':q5?'方格中的平行四边形，边长0.5厘米':q8?'单位方格中的平行四边形':q14?'底200米、面积至少3公顷的平行四边形':q15?'两张全等三角形旋转平移拼成平行四边形':q16?'等底等高面积关系与等底等面积高的关系':q17?'方格中的平行四边形和两个等面积三角形作图区':'两组对应底和高'});
  function line(x1,y1,x2,y2,color,w,dash){svg.appendChild(cwNode('line',{x1:x1,y1:y1,x2:x2,y2:y2,stroke:color||'#c7d7e5','stroke-width':w||1,'stroke-dasharray':dash||''}))}
  function text(x,y,t,color,size,anchor){svg.appendChild(cwNode('text',{x:x,y:y,fill:color||'#344054','font-size':size||17,'font-weight':700,'text-anchor':anchor||'middle'},t))}
  function panel(x,y,cell,cols,rows,base,height,caption,showHigh){
    var w=cell*cols,h=cell*rows;
    for(var i=0;i<=cols;i++)line(x+i*cell,y,x+i*cell,y+h,'#c5d8e8',1);
    for(var j=0;j<=rows;j++)line(x,y+j*cell,x+w,y+j*cell,'#c5d8e8',1);
    var shift=cell*2,top=y+cell,bottom=top+height*cell;
    svg.appendChild(cwNode('polygon',{points:(x+shift)+','+top+' '+(x+shift+base*cell)+','+top+' '+(x+base*cell)+','+bottom+' '+x+','+bottom,fill:'#3da9bd','fill-opacity':.18,stroke:'#225e7a','stroke-width':3}));
    text(x+w/2,y+h+42,caption,'#344054',16);
    if(showHigh){
      line(x+shift,top,x+shift,bottom,'#b42318',2,'6 4');
      line(x+shift,top+10,x+shift+10,top+10,'#b42318',2);
      line(x+shift+10,top+10,x+shift+10,top,'#b42318',2);
    }
    return {left:x,right:x+base*cell,top:top,bottom:bottom,center:x+base*cell/2,heightTop:top+22};
  }
  if(q5){
    var revealGrid=!!(view.showAnswer||(teacher&&(!view.previewMode||Number(view.step)>=5)));
    var g5=panel(45,35,40,10,6,8,5,'每小格0.5 cm',revealGrid);
    if(revealGrid)text(365,150,'高5格','#b42318',17,'start');
    if(revealGrid)text(g5.center,g5.bottom+17,'底8格','#1d4ed8',17);
  }else if(q8){
    var revealGrid8=!!(view.showAnswer||(teacher&&(!view.previewMode||Number(view.step)>=5)));
    var g8=panel(70,45,40,8,5,6,3,'每小格1 dm',revealGrid8);
    if(revealGrid8){text(300,145,'高3格','#b42318',17,'start');text(g8.center,g8.bottom+17,'底6格','#1d4ed8',17);}
  }else if(q10){
    var reveal=!!(view.showAnswer||(teacher&&(!view.previewMode||Number(view.step)>=5)));
    text(350,28,'底边平均分成3份，高不变','#344054',17);
    var b0=[100,260],b1=[200,260],b2=[300,260],b3=[400,260],t0=[160,100],t1=[260,100],t2=[360,100],t3=[460,100];
    svg.appendChild(cwNode('polygon',{points:b0.join(',')+' '+b1.join(',')+' '+t1.join(',')+' '+t0.join(','),fill:'#60a5fa','fill-opacity':.18,stroke:'#1d4ed8','stroke-width':3}));
    svg.appendChild(cwNode('polygon',{points:b1.join(',')+' '+b2.join(',')+' '+t2.join(',')+' '+t1.join(','),fill:'#f59e0b','fill-opacity':.6,stroke:'#b45309','stroke-width':3}));
    svg.appendChild(cwNode('polygon',{points:b2.join(',')+' '+b3.join(',')+' '+t3.join(',')+' '+t2.join(','),fill:'#60a5fa','fill-opacity':.18,stroke:'#1d4ed8','stroke-width':3}));
    text(280,80,'原图面积36 cm²','#344054',16);
    text(250,292,'底边 1份','#1d4ed8',14);text(350,292,'中间1份','#b45309',14);text(450,292,'底边 1份','#1d4ed8',14);
    if(reveal)text(350,330,'中间涂色面积=36÷3=12 cm²','#344054',16);
  }else if(q22){
    var reveal=!!(view.showAnswer||(teacher&&(!view.previewMode||Number(view.step)>=5)));
    function tri22(points,fill,stroke){svg.appendChild(cwNode('polygon',{points:points,fill:fill,'fill-opacity':.55,stroke:stroke||'#225e7a','stroke-width':3}))}
    function arrow22(x1,x2,y){line(x1,y,x2,y,'#667085',3);svg.appendChild(cwNode('polygon',{points:(x2-12)+','+(y-8)+' '+x2+','+y+' '+(x2-12)+','+(y+8),fill:'#667085'}))}
    text(160,28,'① 原三角形：沿两腰中点连线剪开','#344054',15);
    tri22('40,250 280,250 160,70','#60a5fa');
    line(100,160,220,160,'#b42318',3,'7 5');
    line(160,70,160,250,'#1d4ed8',2,'6 4');
    text(160,282,'底 a','#1d4ed8',14);text(169,120,'高 h','#1d4ed8',14,'start');
    text(160,184,'中点连线','#b42318',13);
    arrow22(300,350,170);
    text(505,28,'② 上部三角形沿高再剪成两块','#344054',15);
    tri22('365,250 525,250 485,160 405,160','#60a5fa');
    text(445,275,'下方梯形','#475467',13);
    tri22('540,160 585,160 585,100','#a78bfa');
    tri22('610,160 655,160 610,100','#a78bfa');
    text(598,190,'剪下的两块','#475467',13);
    arrow22(665,710,170);
    text(860,28,'③ 旋转180°补在两侧，拼成长方形','#344054',15);
    svg.appendChild(cwNode('rect',{x:725,y:145,width:300,height:105,fill:'#fff','fill-opacity':0,stroke:'#1d4ed8','stroke-width':3}));
    // The lower trapezoid and the two rotated top pieces tile the rectangle.
    tri22('725,250 1025,250 950,145 800,145','#60a5fa');
    tri22('725,145 800,145 725,250','#a78bfa');
    tri22('1025,145 950,145 1025,250','#a78bfa');
    line(725,145,1025,145,'#1d4ed8',3);line(725,250,1025,250,'#1d4ed8',3);
    line(725,145,725,250,'#b42318',2,'6 4');
    text(875,280,'长 a','#1d4ed8',14);
    text(734,205,'宽 h÷2','#b42318',13,'start');
    arrow22(1035,1080,170);
    text(1230,28,'④ 任意三角形：两张全等拼平行四边形','#344054',15);
    tri22('1080,250 1220,250 1320,150','#60a5fa');
    tri22('1080,250 1320,150 1180,150','#a78bfa');
    line(1080,250,1320,150,'#fff',2,'6 4');
    line(1080,250,1220,250,'#1d4ed8',2);
    line(1180,150,1180,250,'#b42318',2,'6 4');
    text(1150,280,'底 a','#1d4ed8',13);text(1188,205,'高 h','#b42318',13,'start');
    text(1220,315,'两倍面积；单个三角形为一半','#475467',13);
    if(reveal)text(700,335,'长方形面积 a×(h÷2)=ah÷2；任意三角形均可用两全等副本验证','#344054',15);
  }else if(q23){
    var showSolutions=!!(view.showAnswer||(teacher&&(!view.previewMode||Number(view.step)>=5)));
    text(250,28,'割补前：原三角形','#344054',17);
    var A=[70,265],B=[370,265],C=[150,65];
    svg.appendChild(cwNode('polygon',{points:A.join(',')+' '+B.join(',')+' '+C.join(','),fill:'#60a5fa','fill-opacity':.22,stroke:'#225e7a','stroke-width':3}));
    line(C[0],C[1],C[0],A[1],'#b42318',2,'6 4');
    line(C[0],A[1]-14,C[0]+14,A[1]-14,'#b42318',2);line(C[0]+14,A[1]-14,C[0]+14,A[1],'#b42318',2);
    text(220,294,'底 a=8 cm','#1d4ed8',16);
    text(C[0]+10,170,showSolutions?'高 h=10 cm':'高 h=?','#b42318',16,'start');
    text(515,120,'割补','#344054',16);
    line(430,165,590,165,'#667085',3);
    svg.appendChild(cwNode('polygon',{points:'590,165 574,156 574,174',fill:'#667085'}));
    text(510,205,'面积不变','#475467',14);
    text(790,28,'割补后：等面积长方形','#344054',17);
    svg.appendChild(cwNode('rect',{x:650,y:90,width:280,height:175,fill:'#a78bfa','fill-opacity':.2,stroke:'#6941c6','stroke-width':3}));
    text(790,78,'长=原三角形底=8 cm','#1d4ed8',15);
    text(790,290,'宽=原三角形高的一半=5 cm','#6941c6',15);
    if(showSolutions){
      text(500,330,'面积：8×5=40 cm²；原三角形高：5×2=10 cm','#344054',16);
    }else{
      text(500,330,'根据长方形长、宽反推三角形的底、高和面积','#475467',15);
    }
  }else if(q21){
    var showSolutions=!!(view.showAnswer||(teacher&&(!view.previewMode||Number(view.step)>=5)));
    text(300,28,'底边平均分成3份；阴影三角形占1份，且与大图等高','#344054',16);
    var A=[80,265],M=[200,265],B=[440,265],D=[152,70],C=[512,70];
    svg.appendChild(cwNode('polygon',{points:A.join(',')+' '+B.join(',')+' '+C.join(',')+' '+D.join(','),fill:'#60a5fa','fill-opacity':.12,stroke:'#1d4ed8','stroke-width':3}));
    svg.appendChild(cwNode('polygon',{points:A.join(',')+' '+M.join(',')+' '+D.join(','),fill:'#f59e0b','fill-opacity':.58,stroke:'#b45309','stroke-width':3}));
    line(D[0],D[1],D[0],A[1],'#b42318',2,'6 4');
    line(D[0],A[1]-15,D[0]+15,A[1]-15,'#b42318',2);line(D[0]+15,A[1]-15,D[0]+15,A[1],'#b42318',2);
    line(A[0],A[1],B[0],B[1],'#1d4ed8',3);
    [140,260,380].forEach(function(x){line(x,A[1]-7,x,A[1]+7,'#1d4ed8',2)});
    text(140,292,'1份','#1d4ed8',14);text(260,292,'1份','#1d4ed8',14);text(380,292,'1份','#1d4ed8',14);
    text(114,190,'阴影三角形','#92400e',15);
    text(173,166,'共同的高','#b42318',14,'start');
    text(385,58,'平行四边形','#1d4ed8',15);
    text(300,325,'阴影三角形面积12 m² → 同底同高平行四边形24 m² → 大图72 m²','#344054',15);
    if(showSolutions){
      text(790,110,'三角形底占大图底边的1/3','#344054',15);
      text(790,150,'12×2=24 m²；24×3=72 m²','#344054',15);
      text(790,190,'72×100=7200 m²','#344054',15);
      text(790,230,'7200÷10000=0.72 公顷','#344054',15);
    }
  }else if(q20){
    var showSolutions=!!(view.showAnswer||(teacher&&(!view.previewMode||Number(view.step)>=6)));
    text(250,28,'玻璃残片：保留一条直角边12 dm和一个45°锐角','#344054',15);
    var A=[65,285],B=[65,125],C=[225,285],P=[145,205],Q=[165,285];
    svg.appendChild(cwNode('polygon',{points:A.join(',')+' '+B.join(',')+' '+P.join(',')+' '+Q.join(','),fill:'#60a5fa','fill-opacity':.42,stroke:'#225e7a','stroke-width':3}));
    line(B[0],B[1],C[0],C[1],'#667085',2,'7 5');
    line(A[0],A[1],C[0],C[1],'#667085',2,'7 5');
    svg.appendChild(cwNode('polyline',{points:P.join(',')+' 152,218 162,226 153,237 '+Q.join(','),fill:'none',stroke:'#b42318','stroke-width':3}));
    line(A[0]+18,A[1],A[0]+18,A[1]-18,'#1d4ed8',2);line(A[0]+18,A[1]-18,A[0],A[1]-18,'#1d4ed8',2);
    text(82,210,'12 dm','#1d4ed8',16,'start');
    text(82,139,'45°','#344054',16,'start');
    text(150,251,'破损断口','#b42318',13);
    text(250,308,'虚线：原玻璃轮廓；红线：破损边','#475467',14);
    line(500,40,500,340,'#d0d5dd',1);
    text(750,28,'面积与价钱的推导','#344054',17);
    svg.appendChild(cwNode('polygon',{points:'585,275 585,105 755,275',fill:'#a78bfa','fill-opacity':.2,stroke:'#225e7a','stroke-width':3}));
    line(585,255,605,255,'#b42318',2);line(605,255,605,275,'#b42318',2);
    text(585,190,'1.2 m','#1d4ed8',15,'start');
    text(670,296,'1.2 m','#1d4ed8',15);
    text(655,90,'45°','#344054',15);
    if(showSolutions){
      text(820,100,'另一个锐角也是45°','#344054',15);
      text(820,135,'两直角边相等：12 dm=1.2 m','#344054',15);
      text(820,180,'面积=1.2×1.2÷2=0.72 m²','#344054',15);
      text(820,225,'价钱=0.72×80=57.6元','#344054',15);
    }else{
      text(820,140,'先由45°判断两直角边关系','#344054',15);
      text(820,185,'再求原玻璃面积和价钱','#344054',15);
    }
  }else if(q18){
    var showSolutions=!!(view.showAnswer||(teacher&&(!view.previewMode||Number(view.step)>=5)));
    text(250,25,'（1）每格0.5 cm：在三角形上画底和高并数格','#344054',15);
    function grid18(x,y,cell,cols,rows){
      for(var i=0;i<=cols;i++)line(x+i*cell,y,x+i*cell,y+rows*cell,'#c5d8e8',1);
      for(var j=0;j<=rows;j++)line(x,y+j*cell,x+cols*cell,y+j*cell,'#c5d8e8',1);
    }
    grid18(25,45,22,12,8);
    svg.appendChild(cwNode('polygon',{points:'69,199 245,199 157,89',fill:'#60a5fa','fill-opacity':.18,stroke:'#225e7a','stroke-width':3}));
    if(showSolutions){
      line(157,89,157,199,'#b42318',2,'6 4');
      line(157,185,171,185,'#b42318',2);line(171,185,171,199,'#b42318',2);
      text(157,222,'底8格=4 cm','#1d4ed8',14);
      text(165,145,'高5格=2.5 cm','#b42318',14,'start');
      text(250,260,'面积=4×2.5÷2=5 cm²','#344054',15);
    }
    line(500,40,500,320,'#d0d5dd',1);
    text(750,25,'（2）两直角边10 cm、7.5 cm','#344054',15);
    svg.appendChild(cwNode('polygon',{points:'570,250 770,250 570,100',fill:'#a78bfa','fill-opacity':.22,stroke:'#225e7a','stroke-width':3}));
    line(570,230,590,230,'#b42318',2);line(590,230,590,250,'#b42318',2);
    text(670,275,'直角边10 cm','#1d4ed8',15);
    text(585,175,'直角边7.5 cm','#1d4ed8',15,'start');
    text(700,158,'斜边12.5 cm','#344054',15);
    if(showSolutions)text(750,315,'面积=10×7.5÷2=37.5 cm²','#344054',15);
  }else if(q17){
    var showSolutions=!!(view.showAnswer||(teacher&&(!view.previewMode||Number(view.step)>=5)));
    function grid(x,y,cell,cols,rows){
      for(var i=0;i<=cols;i++)line(x+i*cell,y,x+i*cell,y+rows*cell,'#c5d8e8',1);
      for(var j=0;j<=rows;j++)line(x,y+j*cell,x+cols*cell,y+j*cell,'#c5d8e8',1);
    }
    text(130,25,'原图：底6格、高3格','#344054',15);
    grid(25,45,22,9,5);
    svg.appendChild(cwNode('polygon',{points:'47,67 179,67 157,133 25,133',fill:'#3da9bd','fill-opacity':.42,stroke:'#225e7a','stroke-width':3}));
    text(105,165,'面积 6×3=18 格²','#344054',14);
    text(435,25,'作图区A：方格上画一种三角形','#344054',15);
    grid(245,45,22,11,6);
    text(790,25,'作图区B：画形状不同的三角形','#344054',15);
    grid(735,45,20,13,6);
    if(showSolutions){
      svg.appendChild(cwNode('polygon',{points:'267,155 465,155 311,67',fill:'#60a5fa','fill-opacity':.42,stroke:'#1d4ed8','stroke-width':3}));
      line(267,155,465,155,'#1d4ed8',3);
      line(311,67,311,155,'#b42318',2,'6 4');
      text(366,176,'底9格','#1d4ed8',14);text(319,112,'高4格','#b42318',14,'start');
      svg.appendChild(cwNode('polygon',{points:'755,145 995,145 915,85',fill:'#a78bfa','fill-opacity':.45,stroke:'#6941c6','stroke-width':3}));
      line(755,145,995,145,'#6941c6',3);
      line(915,85,915,145,'#b42318',2,'6 4');
      text(875,166,'底12格','#6941c6',14);text(923,118,'高3格','#b42318',14,'start');
      text(500,225,'A：9×4÷2=18 格²；B：12×3÷2=18 格²','#344054',16);
      text(500,255,'两种三角形面积都等于原平行四边形的18格²','#344054',15);
    }else{
      text(500,225,'请在A、B网格中分别作图并标出底和高','#475467',15);
    }
  }else if(q16){
    var relationStep=Math.max(1,Math.min(5,Number(view.step)||1));
    text(245,28,'（1）平行四边形与三角形：同底、等高','#344054',16);
    svg.appendChild(cwNode('polygon',{points:'65,220 125,95 405,95 345,220',fill:'#60a5fa','fill-opacity':.3,stroke:'#225e7a','stroke-width':3}));
    line(65,220,345,220,'#1d4ed8',3);
    if(relationStep>=2){
      svg.appendChild(cwNode('polygon',{points:'65,220 345,220 185,95',fill:'#a78bfa','fill-opacity':.5,stroke:'#6941c6','stroke-width':3}));
      line(125,95,125,220,'#b42318',2,'6 4');
      line(125,206,139,206,'#b42318',2);line(139,206,139,220,'#b42318',2);
      line(185,95,185,220,'#b42318',2,'6 4');
      line(185,206,199,206,'#b42318',2);line(199,206,199,220,'#b42318',2);
      text(205,243,'相同的底','#1d4ed8',14);
      text(133,158,'共同的高','#b42318',13,'start');
    }
    if(relationStep>=3)text(230,278,'三角形面积=15 m²；平行四边形面积=30 m²','#344054',14);
    if(relationStep>=4){
      line(520,35,520,325,'#d0d5dd',1);
      text(780,28,'（2）等底、等面积','#344054',17);
      svg.appendChild(cwNode('polygon',{points:'560,230 720,230 560,100',fill:'#60a5fa','fill-opacity':.55,stroke:'#225e7a','stroke-width':3}));
      line(560,100,560,230,'#b42318',2,'6 4');
      line(560,216,574,216,'#b42318',2);line(574,216,574,230,'#b42318',2);
      text(640,258,'底 a','#1d4ed8',15);text(568,165,'高 h','#b42318',14,'start');
      svg.appendChild(cwNode('polygon',{points:'785,230 945,230 975,165 815,165',fill:'#a78bfa','fill-opacity':.55,stroke:'#225e7a','stroke-width':3}));
      line(815,165,815,230,'#b42318',2,'6 4');
      line(815,216,829,216,'#b42318',2);line(829,216,829,230,'#b42318',2);
      text(865,258,'底 a','#1d4ed8',15);
      text(823,205,relationStep>=5?'高 h/2':'高 H','#b42318',14,'start');
    }
    if(relationStep>=5)text(780,300,'a×h÷2=a×H，所以 H=h/2','#344054',16);
  }else if(q15){
    var doublingStep=Math.max(1,Math.min(5,Number(view.step)||1));
    function tri(points,fill){svg.appendChild(cwNode('polygon',{points:points,fill:fill,'fill-opacity':.7,stroke:'#225e7a','stroke-width':3}))}
    function arrow(x1,y1,x2,y2){line(x1,y1,x2,y2,'#667085',3);svg.appendChild(cwNode('polygon',{points:(x2-12)+','+(y2-8)+' '+x2+','+y2+' '+(x2-12)+','+(y2+8),fill:'#667085'}))}
    text(135,28,'① 两张完全相同的三角形纸片','#344054',16);
    tri('45,215 120,75 195,215','#60a5fa');
    tri('205,215 280,75 355,215','#a78bfa');
    text(200,250,'全等三角形','#475467',15);
    if(doublingStep>=2){
      arrow(365,150,430,150);
      text(500,28,'② 旋转或平移其中一块','#344054',16);
      tri('435,215 500,75 575,215','#60a5fa');
      tri('545,75 620,215 695,75','#a78bfa');
    }
    if(doublingStep>=3){
      arrow(700,150,735,150);
      text(815,28,'③ 拼成平行四边形','#344054',16);
      var A=[735,220],B=[865,220],C=[900,120],D=[770,120];
      tri(A.join(',')+' '+B.join(',')+' '+C.join(','),'#60a5fa');
      tri(A.join(',')+' '+C.join(',')+' '+D.join(','),'#a78bfa');
      line(A[0],A[1],C[0],C[1],'#fff',2,'6 4');
      if(doublingStep>=4){
        line(A[0],A[1]+14,B[0],B[1]+14,'#1d4ed8',2);
        text(800,255,'底 a','#1d4ed8',15);
        line(D[0],D[1],D[0],A[1],'#b42318',2,'6 4');
        line(D[0],A[1]-14,D[0]+14,A[1]-14,'#b42318',2);
        line(D[0]+14,A[1]-14,D[0]+14,A[1],'#b42318',2);
        text(D[0]+9,175,'高 h','#b42318',15,'start');
      }
      if(doublingStep>=5)text(800,300,'S平行四边形=a×h=2×S三角形','#344054',15);
    }
  }else if(q14){
    var reveal14=!!(view.showAnswer||(teacher&&(!view.previewMode||Number(view.step)>=6)));
    text(280,30,reveal14?'第（3）问：面积至少3公顷，对应高至少150 m':'第（3）问：底200 m，求对应高','#344054',17);
    var left=65,top=75,bottom=255,right=455,shift=90;
    svg.appendChild(cwNode('polygon',{points:left+','+bottom+' '+(left+shift)+','+top+' '+right+','+top+' '+(right-shift)+','+bottom,fill:'#3da9bd','fill-opacity':.16,stroke:'#225e7a','stroke-width':3}));
    line(left+shift,top,left+shift,bottom,'#b42318',3,'7 4');
    line(left+shift,bottom-14,left+shift+14,bottom-14,'#b42318',2);
    line(left+shift+14,bottom-14,left+shift+14,bottom,'#b42318',2);
    text(285,60,'底 200 m','#1d4ed8',19);
    text(left+shift+12,170,reveal14?'高 ≥150 m':'高 ? m','#b42318',18,'start');
    if(reveal14)text(280,300,'3公顷＝30,000 m²；30,000÷200＝150 m','#344054',17);
  }else{
    // Side-by-side diagrams make each altitude visibly belong to its base.
    function pair(x,label,base,height,color,slanted){
      text(x+170,28,label,'#344054',16);
      var top=90,bottom=225,left=x+35,right=left+265,shift=65;
      svg.appendChild(cwNode('polygon',{points:left+','+bottom+' '+(left+shift)+','+top+' '+right+','+top+' '+(right-shift)+','+bottom,fill:'#3da9bd','fill-opacity':.14,stroke:'#225e7a','stroke-width':3}));
      if(!slanted){
        line(left+70,top,left+70,bottom,color,3,'7 4');
        text(x+160,155,height+' m',color,18);
        text(x+170,255,base+' m 底','#1d4ed8',17);
        text(x+190,56,'高垂直于水平底','#475467',14);
      }else{
        var sideStart=[left,bottom],sideEnd=[left+shift,top],opposite=[right-shift,bottom];
        var dx=sideEnd[0]-sideStart[0],dy=sideEnd[1]-sideStart[1];
        var ratio=((opposite[0]-sideStart[0])*dx+(opposite[1]-sideStart[1])*dy)/(dx*dx+dy*dy);
        var foot=[sideStart[0]+ratio*dx,sideStart[1]+ratio*dy];
        line(sideStart[0],sideStart[1],sideEnd[0],sideEnd[1],'#1d4ed8',4);
        line(opposite[0],opposite[1],foot[0],foot[1],color,3,'7 4');
        var sideLength=Math.sqrt(dx*dx+dy*dy),ux=dx/sideLength,uy=dy/sideLength,nx=-uy,ny=ux,mark=10;
        line(foot[0],foot[1],foot[0]+ux*mark,foot[1]+uy*mark,color,2);
        line(foot[0]+ux*mark,foot[1]+uy*mark,foot[0]+(ux+nx)*mark,foot[1]+(uy+ny)*mark,color,2);
        line(foot[0]+(ux+nx)*mark,foot[1]+(uy+ny)*mark,foot[0]+nx*mark,foot[1]+ny*mark,color,2);
        text(x+80,265,base+' m 斜底','#1d4ed8',16);
        text(x+215,185,height+' m','#d97706',18);
        text(x+190,255,'虚线高与蓝色斜底垂直','#475467',14);
      }
    }
    pair(15,'8 m 底 ↔ 5.4 m 高',8,5.4,'#d97706',false);
    pair(435,'6 m 底 ↔ 7.2 m 高',6,7.2,'#7c3aed',true);
  }
  wrap.appendChild(svg);box.appendChild(wrap);return true;
}
  function lesson11CwSteps(box,p,view,big,teacher){
  var wrap=el('div',{style:'max-width:980px;margin:0 auto;background:#fff;color:#111;border-radius:12px;padding:12px;line-height:1.75;'+(big?'font-size:2.8vh':'')});box.appendChild(wrap);
  wrap.appendChild(el('b',{text:p.title}));
  if(p.sourceProblem)wrap.appendChild(el('p',{style:'white-space:pre-wrap',text:p.sourceProblem}));
  if(p.figure&&p.figure.type==='calendar_compare')view._calendarCourseware={kind:'steps',params:p};
  if(!cwLesson11Parallelogram(wrap,p,view,big,teacher)&&!cwLesson10Geometry(wrap,p,view,big,teacher)&&!cwLesson10RemainingFigure(wrap,p,view,big,teacher))cwFigure(wrap,p.figure,big,view,teacher,p.steps.length);
  if(p.sourceFigure&&p.sourceFigure.type==='uploaded_image')wrap.appendChild(el('details',{style:'margin:10px 0'},el('summary',{text:'\u67e5\u770b\u539f\u9898\u56fe\u7247\uff08\u5bf9\u7167\uff09'}),el('img',{src:p.sourceFigure.data_url,alt:p.sourceFigure.alt||'\u539f\u9898\u56fe\u7247',style:'display:block;max-width:100%;max-height:'+(big?'32vh':'260px')+';object-fit:contain;margin:8px auto;border:1px solid #e5e8f0;border-radius:8px'})));
  var shown=teacher?(view.previewMode?Math.max(1,view.step||0):p.steps.length):(view.step||0),list=el('ol',{style:'padding-left:1.6em;margin:12px 0'});
  p.steps.forEach(function(s,i){list.appendChild(el('li',{style:i<shown?(i===shown-1?'background:#fff2cc;font-weight:700;border-radius:6px;padding:0 4px':''):'color:#98a2b3',text:i<shown?s:'（第 '+(i+1)+' 步，点“下一步”显示）'}))});
  wrap.appendChild(list);
  if(view.showAnswer||teacher)wrap.appendChild(el('p',{style:'font-weight:700;color:#b42318',text:'答案：'+p.answer}));
}
  window.cwSteps=function(box,p,view,big,teacher){
    if(!lesson11Figure(p))return previousSteps(box,p,view,big,teacher);
    var wrap=el('div',{style:'max-width:980px;margin:0 auto;background:#fff;color:#111;border-radius:12px;padding:12px;line-height:1.75;'+(big?'font-size:2.8vh':'')});
    box.appendChild(wrap);wrap.appendChild(el('b',{text:p.title}));
    if(p.sourceProblem)wrap.appendChild(el('p',{style:'white-space:pre-wrap',text:p.sourceProblem}));
    cwLesson11Parallelogram(wrap,p,view,big,teacher);
    if(p.sourceFigure&&p.sourceFigure.type==='uploaded_image')wrap.appendChild(el('details',{style:'margin:10px 0'},el('summary',{text:'查看原题图片（对照）'}),el('img',{src:p.sourceFigure.data_url,alt:p.sourceFigure.alt||'原题图片',style:'display:block;max-width:100%;max-height:'+(big?'32vh':'260px')+';object-fit:contain;margin:8px auto;border:1px solid #e5e8f0;border-radius:8px'})));
    var shown=teacher?Math.max(1,Math.min(p.steps.length,Number(view.step)||1)):(view.step||0),list=el('ol',{style:'padding-left:1.6em;margin:12px 0'});
    p.steps.forEach(function(s,i){list.appendChild(el('li',{style:i<shown?(i===shown-1?'background:#fff2cc;font-weight:700;border-radius:6px;padding:0 4px':''):'color:#98a2b3',text:i<shown?s:'（第 '+(i+1)+' 步，点“下一步”显示）'}))});
    wrap.appendChild(list);
    if(view.showAnswer||(teacher&&shown>=p.steps.length))wrap.appendChild(el('p',{style:'font-weight:700;color:#b42318',text:'答案：'+p.answer}));
  };
}());

(function(){
  function cleanText(value){return String(value||'').trim();}
  function classHas(node,name){return !!(node&&(' '+String(node.className||'')+' ').indexOf(' '+name+' ')>=0);}
  function activity(scope){
    if(!scope||!scope.querySelectorAll)return '';
    var nodes=scope.querySelectorAll('div');
    for(var i=0;i<nodes.length;i++){
      var n=nodes[i],t=cleanText(n.textContent||'');
      if(n.children&&n.children.length===0&&(t.indexOf('正在审核第')===0||t.indexOf('审核完成 ')===0))return t;
    }
    return '';
  }
  function rowStatus(scope,label,message,error){
    if(!scope||!scope.querySelectorAll)return;
    var rows=scope.querySelectorAll('.item');
    for(var i=0;i<rows.length;i++){
      var b=rows[i].querySelector('b');
      if(!b||cleanText(b.textContent)!==label)continue;
      var note=rows[i].querySelector('[role="status"]');
      if(note){note.className='notice '+(error?'error':'ok');note.textContent=message}
      return;
    }
  }
  if(document&&document.addEventListener)document.addEventListener('click',function(event){
    var button=event.target;
    while(button&&button.tagName!=='BUTTON')button=button.parentNode;
    if(!button||cleanText(button.textContent)!=='审核通过')return;
    var row=button;
    while(row&&!classHas(row,'item'))row=row.parentNode;
    if(!row)return;
    var title=row.querySelector('b');
    var label=title?cleanText(title.textContent):'';
    var scope=row;
    while(scope&&!classHas(scope,'card'))scope=scope.parentNode;
    if(!scope)return;
    var current=activity(scope);
    if(/^正在审核第/.test(current)){
      rowStatus(scope,label,'上一项课件仍在审核处理中，请等待页面提示后再试。',true);
      return;
    }
    rowStatus(scope,label,'正在提交审核…',false);
    var tries=0;
    var timer=setInterval(function(){
      tries++;
      var state=activity(scope);
      if(/^审核完成 /.test(state)){
        rowStatus(scope,label,state,state.indexOf('未完成：')>=0);
        clearInterval(timer);
      }else if(tries>=80){
        rowStatus(scope,label,'审核请求仍未返回，请检查连接后重试。',true);
        clearInterval(timer);
      }
    },250);
  },true);
}());
