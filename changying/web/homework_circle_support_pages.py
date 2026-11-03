"""Fixed, non-scoring geometry support. No model-generated markup or extra AI requests."""

CIRCLE_SUPPORT_JS = r"""
function hwCircleEligible(text,grade){return +grade===6&&/圆/.test(text||'')&&/面积/.test(text||'')&&!/圆柱|圆锥|球体/.test(text||'')}
function hwCircleSymbolic(text){return /[πΠ]|\bpi\b/i.test(String(text||''))}
function hwCircleFigure(kind,parts){
  var box=el('div',{class:'circle-figure'}),body='',title='',n=parts===16?16:8;
  if(kind==='square'){
    title='边长4厘米的正方形，四行四列共16个单位方格';
    for(var y=0;y<4;y++)for(var x=0;x<4;x++)body+='<rect x="'+(45+x*30)+'" y="'+(25+y*30)+'" width="30" height="30" fill="#e8f0ff" stroke="#1f6feb"/>';
    body+='<text x="80" y="172">4厘米</text><text x="183" y="94">4厘米</text><text x="183" y="124" font-size="14">每格1平方厘米</text>';
  }else if(kind==='rearrange'){
    title='等分圆后交错拼合，有限份数时仍不是长方形';
    var r=44,a=Math.PI/n,s=r*Math.sin(a),h=r*Math.cos(a),start=95,top=55;
    for(var j=0;j<n;j++){
      var t0=2*Math.PI*j/n-Math.PI/2,t1=2*Math.PI*(j+1)/n-Math.PI/2;
      body+='<path d="M45 82 L'+(45+31*Math.cos(t0))+' '+(82+31*Math.sin(t0))+' A31 31 0 0 1 '+(45+31*Math.cos(t1))+' '+(82+31*Math.sin(t1))+' Z" fill="'+(j%2?'#dbeafe':'#ffedd5')+'" stroke="#667085" stroke-width="0.7"/>';
    }
    for(var i=0;i<n/2;i++){
      var up=start+s+2*s*i,down=start+2*s+2*s*i;
      body+='<path d="M'+up+' '+(top+h)+' L'+(up-s)+' '+top+' A'+r+' '+r+' 0 0 1 '+(up+s)+' '+top+' Z" fill="#ffedd5" stroke="#b45309"/>';
      body+='<path d="M'+down+' '+top+' L'+(down+s)+' '+(top+h)+' A'+r+' '+r+' 0 0 1 '+(down-s)+' '+(top+h)+' Z" fill="#dbeafe" stroke="#1f6feb"/>';
    }
    body+='<path d="M'+start+' 30 H'+(start+n*s)+'" stroke="#1f6feb"/><text x="128" y="24">长约为πr</text><text x="260" y="85" fill="#b42318">宽约为r</text><text x="30" y="140">面积没变，边缘仍有弧线</text><text x="30" y="170">切得越细，越接近长方形</text>';
  }else{
    title=kind==='circumference'?'同一个圆的半径和圆周边界':'同一张圆图中的红色半径r、蓝色直径d';
    body='<circle cx="105" cy="87" r="61" fill="#f2f6ff" stroke="'+(kind==='circumference'?'#067647':'#1f6feb')+'" stroke-width="4"/><path d="M105 26 V148" stroke="#1f6feb" stroke-width="4"/><path d="M105 87 H166" stroke="#b42318" stroke-width="5"/><circle cx="105" cy="87" r="4" fill="#1c2333"/><text x="83" y="104">O</text><text x="122" y="76" fill="#b42318">r</text><text x="76" y="55" fill="#1f6feb">d</text><text x="190" y="70" fill="#b42318">红线：r</text><text x="190" y="102" fill="#1f6feb">蓝线：d</text>';
    if(kind==='circumference')body+='<text x="190" y="134" fill="#067647">绿边：圆的一圈</text>';
    body+='<text x="30" y="177">'+(kind==='circumference'?'周长表示圆的一圈长度':'半径到圆边，直径穿过圆心')+'</text>';
  }
  // The entire SVG is fixed content or bounded mathematical coordinates, never model/user HTML.
  var source='<svg xmlns="http://www.w3.org/2000/svg" width="360" height="195" viewBox="0 0 360 195" role="img" aria-label="'+title+'" style="display:block;width:100%;max-width:480px;height:auto;font:17px sans-serif"><title>'+title+'</title>'+body+'</svg>';
  try{var svg=new DOMParser().parseFromString(source,'image/svg+xml').documentElement;if(svg.nodeName!=='svg')throw Error('invalid fixed figure');box.appendChild(svg)}catch(e){box.appendChild(el('p',{text:'图示暂未显示，请按下方文字继续，或请老师一起看。'}))}
  return box;
}
function hwCircleSupport(box,opts){
  var mount=el('div',{class:'circle-support'});box.textContent='';box.appendChild(mount);box=mount;
  var old=opts.record||{},state={entry:opts.before?'before':'after',focus:old.focus||'concept',gaps:(old.gaps||[]).slice(),rounds:Object.assign({radius:0,square:0,circumference:0,unit:0,application:0},old.rounds||{}),outcome:'in_progress',unitChecked:!!old.unitChecked,level:old.level||0,totalMisses:old.totalMisses||0,seenAnswer:!!old.seenAnswer,nodeKey:old.nodeKey||'',visits:Object.assign({},old.visits||{}),steps:old.steps||0};
  var index=0,busy=false,status=null,serial=0;
  var names={radius:'半径与直径',square:'平方与面积',circumference:'圆周长',unit:'面积单位',application:'套用面积公式'};
  function gap(key){if(state.gaps.indexOf(key)<0)state.gaps.push(key)}
  function finish(outcome,teacher){
    if(busy)return;busy=true;state.outcome=outcome;status.textContent='正在保存本次辅导过程…';
    Promise.resolve().then(function(){return opts.onFinish(JSON.parse(JSON.stringify(state)),!!teacher)}).catch(function(e){busy=false;status.textContent=e.message||'保存失败，请重试';status.appendChild(el('button',{text:'重试保存',onclick:function(){finish(outcome,teacher)}}))});
  }
  function frame(title,figure){
    serial++;box.textContent='';box.appendChild(el('h3',{text:title}));
    box.appendChild(el('p',{class:'muted',text:'这是辅导练习，不计分、不改变知识地图掌握度。'}));
    if(figure)box.appendChild(hwCircleFigure(figure));
    status=el('div',{role:'status','aria-live':'polite'});box.appendChild(status);
    box.appendChild(el('button',{text:opts.before?'跳过补救，直接请AI讲原题':'返回原题讲解',onclick:function(){finish(state.outcome==='practice_passed'||state.outcome==='needs_teacher'?state.outcome:'stopped',false)}}));
    box.appendChild(el('button',{text:'请老师一起看',onclick:function(){finish('teacher_requested',true)}}));
  }
  function choice(ask,options,correct,done){
    box.appendChild(el('p',{text:ask}));var row=el('div',{class:'row'}),ended=false,token=serial;
    options.forEach(function(label,k){row.appendChild(el('button',{text:label,onclick:function(){if(ended||busy||token!==serial)return;ended=true;done(k===correct)}}))});
    row.appendChild(el('button',{text:'这一步不会',onclick:function(){if(ended||busy||token!==serial)return;ended=true;done(false)}}));box.appendChild(row);
  }
  function numeric(ask,target,done){
    box.appendChild(el('p',{text:ask}));var input=el('input',{type:'text',maxlength:40,'aria-label':ask,placeholder:'只填写数值'}),tip=el('div',{role:'status'}),ended=false,token=serial;
    box.appendChild(input);box.appendChild(tip);
    box.appendChild(el('button',{text:'确定',class:'primary',onclick:function(){
      if(ended||busy||token!==serial)return;var v=input.value.trim();if(!v)return;
      if(hwCircleSymbolic(v)){tip.textContent='写成含π的式子不算答错。这个示例明确要求π取3.14，请按该要求写出数值。';return}
      if(!/^(?:\d+(?:\.\d+)?|\.\d+)$/.test(v)){tip.textContent='这里只填数字，单位会单独练习；不把暂时无法读取的写法判错。';return}
      ended=true;done(Math.abs(+v-target)<0.000001);
    }}));
    box.appendChild(el('button',{text:'这一步不会',onclick:function(){if(ended||busy||token!==serial)return;ended=true;done(false)}}));
  }
  function needTeacher(){
    state.outcome='needs_teacher';
    frame('这一步请老师一起看');box.appendChild(el('p',{text:'两轮图示补救后仍有疑问，老师会从卡住的位置接着讲。'}));
    box.appendChild(el('button',{text:'带上本次辅导过程，求助老师',class:'primary',onclick:function(){finish('needs_teacher',true)}}));
  }
  function remedy(key,round,next){
    state.rounds[key]=round;frame('先回忆：'+names[key],key==='unit'?'square':key);
    var explanation={radius:'红色r从圆心到圆边；蓝色d穿过圆心，两端在圆上。d=2r。',
      square:'正方形面积是边长乘边长。图里每边4厘米，四行四列共16个单位方格；4²表示4×4，不是4×2。',
      circumference:'先离开面积推导，看看圆的一圈：圆周长=2×π×r，也可以是π×d。这里的单位是厘米等长度单位。',
      unit:'面积表示铺满图形内部，用平方厘米等平方单位；沿边的一圈才用厘米。'};
    box.appendChild(el('p',{text:explanation[key]}));
    function checked(ok){
      if(ok){if(key==='unit')state.unitChecked=true;frame('这次确认通过');box.appendChild(el('p',{text:'这只是本次补救确认，不等于已经独立掌握。'}));box.appendChild(el('button',{text:'继续',onclick:next}));}
      else if(round<2){frame('再换个例子试一次');box.appendChild(el('p',{text:'刚才的图示还没说明白，我们再用一次图示和一道新确认题。'}));box.appendChild(el('button',{text:'开始第二轮补救',onclick:function(){remedy(key,2,next)}}));}
      else needTeacher();
    }
    if(key==='radius')choice(round===1?'同一个圆的直径是6厘米，半径是多少？':'直径是10厘米，半径是多少？',round===1?['6厘米','3厘米','12厘米']:['20厘米','10厘米','5厘米'],round===1?1:2,checked);
    if(key==='square')choice(round===1?'另一个正方形边长5厘米，面积是多少？':'另一个正方形边长6厘米，面积是多少？',round===1?['10平方厘米','25平方厘米','20平方厘米']:['36平方厘米','12平方厘米','24平方厘米'],round===1?1:0,checked);
    if(key==='circumference')choice(round===1?'半径3厘米，π取3.14，求周长应列哪一个式子？':'直径8厘米，π取3.14，求周长应列哪一个式子？',round===1?['3.14×3×3','2×3.14×3','3.14×3']:['3.14×8','3.14×8×8','2×3.14×8'],round===1?1:0,checked);
    if(key==='unit')choice(round===1?'铺满一个圆形纸片，面积的单位应该是哪一个？':'题目长度用米，求出的面积用哪一个单位？',round===1?['厘米','平方厘米']:['平方米','米'],round===1?1:0,checked);
  }
  function startRemedy(key,next){if(state.rounds[key]>=2)needTeacher();else remedy(key,state.rounds[key]+1,next)}
  // ---- 退阶阶梯：从最简单一级开始，答对升一级、答错退一级、错够两次进兜底 ----
  var LADDER=[{rank:1,ask:'边长 4 厘米的正方形，面积是多少？',options:['8 平方厘米','12 平方厘米','16 平方厘米'],correct:2},
    {rank:2,ask:'r = 4 厘米，r × r 是多少？',value:16},
    {rank:3,ask:'3.14 × 16 是多少？',value:50.24},
    {rank:4,ask:'r = 4 厘米的圆，面积是多少平方厘米？（π 取 3.14）',value:50.24}];
  var MISS_LIMIT_TEACHER=4;
  function ladderItem(rank){for(var i=0;i<LADDER.length;i++){if(LADDER[i].rank===rank)return LADDER[i]}return null}
  function alertTeacher(){
    if(state.teacherAlert)return;state.teacherAlert=true;
    box.appendChild(el('p',{class:'muted',text:'这一次你错得比较多，已经记下来给老师看了；也可以现在就点「请老师一起看」。'}));
  }
  var MAX_VISITS_PER_RANK=3;
  function ladderFrame(rank){
    state.visits=state.visits||{};
    state.visits[rank]=(state.visits[rank]||0)+1;
    state.steps=(state.steps||0)+1;
    if(state.steps>12){state.teacherAlert=true;needTeacher();return}
    if(state.visits[rank]>MAX_VISITS_PER_RANK){ladderFallback(rank);return}
    var item=ladderItem(rank);
    frame('第 '+rank+' 步'+(item?'':'：回到原题'));
    if(rank>=5){box.appendChild(el('p',{text:'前四步都通过了。现在回到原题，用题目自己的条件重新做一遍。'}));
      box.appendChild(el('button',{class:'primary',text:'回原题',onclick:function(){example(0)}}));return}
    box.appendChild(el('p',{class:'muted',text:'一次只加一个条件；答错会退一步，不是扣分。'}));
    function answered(ok){
      if(ok){state.missCount=0;state.level=Math.min(5,rank+1);state.rounds.application=0;
        if(state.level>=5){ladderFrame(5)}else{ladderFrame(state.level)}return}
      state.totalMisses+=1;state.missCount=(state.missCount||0)+1;
      if(state.totalMisses>=MISS_LIMIT_TEACHER)alertTeacher();
      if(state.missCount>=2){state.missCount=0;ladderFallback(rank);return}
      var next=rank>1?rank-1:1;state.level=next;
      frame('退一步：第 '+next+' 步');box.appendChild(el('p',{text:'这一步没过去，我们退一级再看一次同样的意思，不算错。'}));
      box.appendChild(el('button',{class:'primary',text:'继续',onclick:function(){ladderFrame(next)}}));
    }
    if(item.options)choice(item.ask,item.options,item.correct,answered);
    else numeric(item.ask,item.value,answered);
  }
  function ladderFallback(rank){
    frame('换一种方式看懂它');
    box.appendChild(el('p',{text:'连着两次没过去，我们不再往下退，换两个更有用的办法：'}));
    box.appendChild(el('button',{text:'看 15 秒微课：圆怎么拼成近似长方形',onclick:function(){
      frame('微课：拼成接近长方形');
      box.appendChild(el('p',{text:'圆被分成很多小扇形、交错拼起来。切得越多，越接近长方形；它不是长方形本身。'}));
      box.appendChild(hwCircleFigure('rearrange',8));
      box.appendChild(el('button',{class:'primary',text:'看完了，再试一次',onclick:function(){state.missCount=0;state.visits[rank]=0;ladderFrame(rank)}}));
    }}));
    box.appendChild(el('button',{text:'看答案拆解',onclick:function(){
      state.seenAnswer=true;state.missCount=0;
      frame('看答案拆解');
      box.appendChild(el('p',{text:'这道题是：先算 4×4=16，再算 3.14×16=50.24，面积是 50.24 平方厘米。'}));
      box.appendChild(el('p',{class:'muted',text:'这次是看答案学会的，不算你已经掌握；下次自己再做对才算。'}));
      box.appendChild(el('button',{class:'primary',text:'我明白了，回去试试',onclick:function(){state.visits[rank]=0;ladderFrame(rank)}}));
    }}));
    box.appendChild(el('button',{text:'请老师一起看',onclick:function(){finish('teacher_requested',true)}}));
  }
  function diagnose(){
    var keys=['radius','square','circumference'];if(index>=keys.length){formula();return}var key=keys[index++];
    frame('先看看：'+names[key],key);
    function answer(ok){if(ok)diagnose();else{gap(key);startRemedy(key,diagnose)}}
    if(key==='radius')choice('同一张圆图里，哪一条线段是半径？',['蓝色d','红色r'],1,answer);
    if(key==='square')choice('图中正方形边长4厘米，面积是多少？',['8平方厘米','12平方厘米','16平方厘米'],2,answer);
    if(key==='circumference')choice('半径是r，圆一周的长度可以写成哪一个？',['πr²','2πr','πr'],1,answer);
  }
  function formula(){
    frame('公式从哪里来？');box.appendChild(el('p',{text:'圆被分割、交错拼合，面积没有改变。切得越多，拼出来的图形越接近长方形；我们用它来推出公式，它不是长方形本身。'}));
    var picture=el('div');picture.appendChild(hwCircleFigure('rearrange',8));box.appendChild(picture);
    [8,16].forEach(function(n){box.appendChild(el('button',{text:'分成'+n+'份看看',onclick:function(){if(busy)return;picture.textContent='';picture.appendChild(hwCircleFigure('rearrange',n))}}))});
    box.appendChild(el('p',{text:'长约为半个圆周长πr，宽约为半径r；长×宽连接到πr×r=πr²。面积单位也要跟着走。'}));
    box.appendChild(el('button',{text:'用一个有明确π取值的例子试试',class:'primary',onclick:function(){example(0)}}));
  }
  function example(stage){
    frame('示例：半径2厘米，π取3.14');
    box.appendChild(el('p',{text:'这是固定示例，不替换原题的条件或π取值。'}));
    if(stage===0)numeric('先算2×2，结果是多少？',4,function(ok){if(!ok){gap('square');startRemedy('square',function(){example(1)})}else example(1)});
    else numeric('再算3.14×4，面积的数值是多少？',12.56,function(ok){
      if(!ok)gap('application');frame('把数值和面积单位放在一起');
      box.appendChild(el('p',{text:'示例中3.14×4=12.56，面积是12.56平方厘米，不是12.56厘米。接下来换一个半径，自己确认一次。'}));
      choice('这个示例应写哪一个面积单位？',['厘米','平方厘米'],1,function(right){if(right){state.unitChecked=true;practice(1)}else{gap('unit');startRemedy('unit',function(){practice(1)})}});
    });
  }
  function practice(round){
    if(round<=state.rounds.application)round=state.rounds.application+1;
    if(round>2){needTeacher();return}
    state.rounds.application=round;var radius=round===1?3:4;frame('补救确认：换一个半径');
    box.appendChild(el('p',{text:'回忆刚才的面积图示：先算半径乘半径，再乘题目给定的π近似值。这道固定确认题仍不计分。'}));
    numeric('半径'+radius+'厘米，π取3.14，面积的数值是多少？',round===1?28.26:50.24,function(ok){
      if(ok){state.outcome='practice_passed';frame('本次辅导练习完成');box.appendChild(el('p',{text:'补救确认通过，尚未完成独立小测。现在回原题按原条件作答；真正的掌握情况要由老师审核的新题验证。'}));box.appendChild(el('button',{class:'primary',text:opts.before?'保存反馈，请AI讲原题':'保存反馈，回到原题',onclick:function(){finish('practice_passed',false)}}));}
      else if(round===1){gap('application');frame('再看一次面积图示','rearrange');box.appendChild(el('p',{text:'刚才半径3厘米，应先算3×3，再算3.14×9。我们换成半径4厘米，进行第二轮确认。'}));box.appendChild(el('button',{text:'开始第二轮确认',onclick:function(){practice(2)}}));}
      else{gap('application');needTeacher()}
    });
  }
  if(old.outcome==='needs_teacher')needTeacher();
  else if(old.outcome==='practice_passed'){
    state.outcome='practice_passed';
    frame('本次补救确认已完成','rearrange');box.appendChild(el('p',{text:'这份求助的补救确认已经完成，但不代表独立掌握。仍然不理解时，请老师接着讲；不要重复刷确认题。'}));
  }else{
    frame('圆的面积，想先回忆哪一块？');
    [['公式还没懂，先检查基础','concept'],['基础我会，想看公式来历','formula'],['公式知道，练一下计算','calculation'],['从最简单的开始，一步一步来','ladder']].forEach(function(item){box.appendChild(el('button',{text:item[0],onclick:function(){if(busy)return;state.focus=item[1];if(item[1]==='calculation')example(0);else if(item[1]==='ladder'){state.level=state.level||1;state.missCount=0;ladderFrame(state.level)}else{index=item[1]==='formula'?2:0;diagnose()}}}))});
  }
}
"""
