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
