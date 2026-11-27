"""语文知识地图（4 知识点域）与强应试专项（基础/古诗文/阅读/微写作）前端页面（宣纸暖白 + 长缨绛红，纯 ES5，无 innerHTML）."""
from __future__ import annotations

from changying.web.arena_role_hub import ARENA_ROLE_HUB_JS
from changying.web.english_arena_pages import ENGLISH_EXTRA_CSS
from changying.web.math_arena_pages import ARENA_CSS
from changying.web.v1_nezha_icons import AVATAR_PNG_B64
from changying.web.weekend_pages import _page

CHINESE_EXTRA_CSS = """<style>
.ma-domain.dom-words{border-top-color:var(--ma-brand)}
.ma-domain.dom-sentence{border-top-color:var(--ma-ok)}
.ma-domain.dom-poetry{border-top-color:var(--ma-gold)}
.ma-domain.dom-reading{border-top-color:var(--ma-blue)}
.ma-domain.dom-words .ma-domain-cnt{background:var(--ma-brand-soft);color:var(--ma-brand)}
.ma-domain.dom-sentence .ma-domain-cnt{background:var(--ma-ok-soft);color:var(--ma-ok)}
.ma-domain.dom-poetry .ma-domain-cnt{background:var(--ma-gold-soft);color:var(--ma-gold)}
.ma-domain.dom-reading .ma-domain-cnt{background:var(--ma-blue-soft);color:var(--ma-blue)}

.ca-sec{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:9px;font-size:14px;font-weight:900;color:#fff;flex-shrink:0;box-shadow:0 2px 0 rgba(0,0,0,.14)}
.ca-sec-foundation{background:#a8101c}
.ca-sec-poetry{background:#b45309}
.ca-sec-reading{background:#1e4e79}
.ca-sec-writing{background:#0b8f5a}

.ca-textarea{width:100%;min-height:112px;padding:12px 14px;border-radius:12px;border:1.5px solid var(--ma-line);background:#fff;font-size:15px;line-height:1.7;color:var(--ma-ink);font-family:inherit;box-sizing:border-box;resize:vertical}
.ca-textarea:focus{outline:none;border-color:var(--ma-brand)}
.ca-wc{margin-top:6px;font-size:12.5px;color:var(--ma-muted);display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}
.ca-ai-box{margin-top:6px;padding:8px 10px;border-radius:9px;background:#fffaf3;border:1px solid #eed9bc;color:#6c4212;font-size:13px;line-height:1.6}
</style>"""

COMMON_CHINESE_JS = r"""
var CA_AUDIO_OBJ=null;
function caStopAudio(){
  if(CA_AUDIO_OBJ){try{CA_AUDIO_OBJ.pause();CA_AUDIO_OBJ.currentTime=0}catch(_e){}CA_AUDIO_OBJ=null}
  if(window.speechSynthesis){try{window.speechSynthesis.cancel()}catch(_e2){}}
}
function caTopbar(active,pts){
  var bar=el('div',{class:'ma-topbar'});
  var left=el('div',{class:'ma-topbar-left'},
    el('a',{class:'ma-link-btn',href:'/classic?legacy=1&unified=1&page=practice',text:'‹ 返回练习'}),
    el('div',{class:'ea-subj'},
      el('a',{href:active==='sprints'?'/v1/math-sprints':'/v1/math-star-map',text:'数学'}),
      el('a',{href:active==='sprints'?'/v1/english-sprints':'/v1/english-star-map',text:'英语'}),
      el('a',{href:active==='sprints'?'/v1/chinese-sprints':'/v1/chinese-star-map',class:'on',text:'语文'})));
  var seg=el('div',{class:'ma-seg'},
    el('a',{href:'/v1/chinese-star-map',class:active==='map'?'on':'',text:'知识地图'}),
    el('a',{href:'/v1/chinese-sprints',class:active==='sprints'?'on':'',text:'应试专项'}));
  var right=el('div',{class:'ma-topbar-right'});
  if(pts)right.appendChild(el('a',{class:'ma-pts',href:'/classic?legacy=1&unified=1&page=rewards',style:'text-decoration:none',title:'查看全站积分奖励 · 语文今日学习积分 '+pts.todayEarned+'/'+pts.dailyCap,text:'积分 '+pts.balance+' ›'}));
  bar.appendChild(left);bar.appendChild(seg);bar.appendChild(right);
  return bar;
}
function caHelperTip(text,tag){
  var src=window.__CY_HELPER_AVATAR__||'';
  return el('div',{class:'ma-helper'},
    src?el('img',{class:'ma-helper-ava',src:src,alt:'长缨助手'}):null,
    el('div',{class:'ma-helper-body'},
      el('div',{class:'ma-helper-name',text:tag||'长缨助手'}),
      el('p',{class:'ma-helper-text',text:text})));
}
function caPointsGain(awarded,pts){
  if(!awarded)return null;
  if(awarded.total>0){
    return el('div',{class:'ma-pts-gain',text:'全站积分 +'+awarded.total+' 分'+(pts?'（当前总积分 '+pts.balance+'）':'')});
  }
  if(awarded.capped){
    return el('div',{class:'ma-pts-gain',text:'今日语文闯关积分已达 30 分上限，本次成绩已正常记录'});
  }
  return null;
}
function caStars(n){var s='',i;for(i=0;i<n;i++)s+='★';return s}
function caClockText(sec){var s=Math.max(0,Math.floor(sec)),m=Math.floor(s/60),r=s%60;return (m<10?'0':'')+m+':'+(r<10?'0':'')+r}
function caQuestionHint(q){
  if(!q)return '认真审题，抓准关键词再落笔！';
  var t=q.questionType;
  if(t==='dictation_spell'||t==='hanzi_tiles')return '先听清普通话读音，再想偏旁部首和词义，谨防同音别字！';
  if(t==='poem_tiles'||t==='poem_fill')return '先听一遍古诗朗诵感受韵律，默写时特别留意通假字与难写字！';
  if(t==='error_spot')return '病句先找主谓宾主干，看是否缺主语、前后矛盾、语义重复或否定不当！';
  if(t==='reading_short')return '阅读简答题记得“结合原文细节 + 提炼人物品质/说明效果”，AI 会按得分点实时批改！';
  if(t==='micro_writing')return '微片段写作尽量调动动作、神态、感官或比喻拟人细节，交卷后 AI 会给出逐条点评！';
  return '联系上下文语境仔细辨析，稳稳拿下每一分！';
}
function caRenderRoleOverview(role){
  root.textContent='';
  var isTeacher=(role==='teacher'||role==='admin');
  var backHref=isTeacher?'/v1':'/classic?legacy=1&unified=1&page=parent';
  var backText=isTeacher?'‹ 返回工作台':'‹ 返回家长端';
  var bar=el('div',{class:'ma-topbar'},
    el('div',{class:'ma-topbar-left'},
      el('a',{class:'ma-link-btn',href:backHref,text:backText}),
      el('div',{class:'ea-subj'},
        el('a',{href:'/v1/math-star-map',text:'数学'}),
        el('a',{href:'/v1/english-star-map',text:'英语'}),
        el('a',{href:'/v1/chinese-star-map',class:'on',text:'语文'}))),
    el('div',{class:'ma-topbar-right'},el('span',{class:'ma-pts',text:isTeacher?'教师语文学情':'家长语文学情'})));
  var box=el('div',{class:'ma-wrap'},bar);
  root.appendChild(box);
  var url=isTeacher?'/teacher/chinese-arena/overview':'/parent/chinese-arena/children';
  api(url).then(function(d){
    box.appendChild(el('div',{class:'ma-card'},
      el('div',{class:'ma-eyebrow',text:'小学语文 · 知识地图与四大板块专项'}),
      el('h2',{class:'ma-h1',text:isTeacher?'全班语文闯关与专项学情':'孩子语文闯关与专项学情'}),
      el('p',{class:'ma-sub',text:'覆盖 '+d.totalNodes+' 个语文核心知识点域节点与 '+d.totalSprints+' 个应试专项，积分独立计入全站账本。'})));
    box.appendChild(caHelperTip(
      isTeacher?'这里汇总了全班学生的语文知识地图点亮进度、待修补考点、四大板块专项最高段位和全站积分。'
               :'这里同步展示孩子的语文知识地图点亮情况与四大板块专项分级结果，重点关注标红待修补考点即可。',
      '长缨助手 · 学情同步'));
    if(!d.items||!d.items.length){
      box.appendChild(el('div',{class:'ma-card'},el('p',{class:'ma-sub',text:isTeacher?'当前学校还没有学生记录。':'暂未关联孩子账号。'})));
      return;
    }
    d.items.forEach(function(it){
      var pct=it.totalNodes?Math.round(it.litNodes/it.totalNodes*100):0;
      var tierTxt=it.bestTier?(it.bestTier.code+' '+it.bestTier.name):'尚未参加专项';
      box.appendChild(el('div',{class:'ma-card'},
        el('div',{class:'ma-sum-top'},
          el('div',{},
            el('h3',{style:'margin:0',text:it.name+(it.grade?'（'+it.grade+'年级）':'')}),
            el('p',{class:'ma-sub',style:'margin-top:3px',text:'已点亮 '+it.litNodes+'/'+it.totalNodes+'（'+pct+'%）· 精通 '+it.masteredNodes+' · 专项最高：'+tierTxt})),
          el('span',{class:'ma-pts',text:'全站积分 '+it.pointsBalance})),
        el('div',{class:'ma-prog-track'},el('div',{class:'ma-prog-fill',style:'width:'+pct+'%'})),
        it.repairNames&&it.repairNames.length
          ?el('p',{class:'ma-sub',style:'margin-top:8px;color:var(--ma-brand)',text:'待修补考点：'+it.repairNames.join('、')})
          :el('p',{class:'ma-sub',style:'margin-top:8px',text:'当前无待修补失分点'})));
    });
  }).catch(function(e){msg(e.message)});
}
function caBoot(run){
  obtainToken().then(function(t){
    TOKEN=t;
    if(!TOKEN){msg('请先登录后再打开');return}
    return api('/session').then(function(s){
      if(s.role==='student'){run();return}
      if(s.role==='teacher'||s.role==='admin'||s.role==='parent'){arenaRoleHub(s.role,'语文');return}
      msg('当前身份无法访问此页面');
    });
  }).catch(function(e){msg(e.message||'打不开')});
}

/* 普通话听写 / 古诗朗诵播放器 */
function caAudioBox(q,opts){
  opts=opts||{};
  var maxPlays=opts.maxPlays||0;
  var allowSlow=(opts.allowSlow!==false);
  var playState=opts.playState||{};
  var played=playState[q.id]||0;
  var rate=1.0;
  var isPoem=(q.questionType==='poem_tiles'||q.questionType==='poem_fill'||q.nodeKey.indexOf('C3')===0);
  var playLabel=isPoem?'▶ 听古诗朗诵':'▶ 听写读音';
  var box=el('div',{class:'ea-audio'});
  var btn=el('button',{type:'button',class:'ea-play-btn',text:playLabel});
  var meta=el('span',{class:'ea-audio-meta',text:maxPlays?('已播 '+played+'/'+maxPlays+' 遍'):'标准普通话配音 · 可反复收听'});
  function updateMeta(playing){
    if(playing){btn.textContent='🔊 正在播放…';btn.disabled=true;return}
    var left=maxPlays?(maxPlays-played):99;
    btn.disabled=(maxPlays>0&&left<=0);
    btn.textContent=(maxPlays>0&&left<=0)?'已播完':playLabel;
    meta.textContent=maxPlays?('已播 '+played+'/'+maxPlays+' 遍'+(left<=0?'（已达上限）':'')):(isPoem?'点击重听古诗朗诵':'点击重听词语读音');
  }
  btn.onclick=function(){
    if(maxPlays>0&&played>=maxPlays)return;
    caStopAudio();
    played+=1;
    playState[q.id]=played;
    updateMeta(true);
    var au=new Audio(q.audioUrl);
    CA_AUDIO_OBJ=au;
    try{au.playbackRate=rate}catch(_e){}
    au.onended=function(){CA_AUDIO_OBJ=null;updateMeta(false)};
    au.onerror=function(){CA_AUDIO_OBJ=null;updateMeta(false);meta.textContent='音频加载失败，请重试'};
    var p=au.play();
    if(p&&typeof p.catch==='function'){p.catch(function(){updateMeta(false);meta.textContent='请再次点击播放'})}
  };
  box.appendChild(btn);
  if(allowSlow){
    var slowBtn=el('button',{type:'button',class:'ea-rate-btn',text:'0.8x 慢速'});
    slowBtn.onclick=function(){
      rate=(rate===1.0?0.8:1.0);
      slowBtn.className='ea-rate-btn'+(rate<1.0?' on':'');
      slowBtn.textContent=(rate<1.0?'0.8x 慢速中':'0.8x 慢速');
    };
    box.appendChild(slowBtn);
  }
  box.appendChild(meta);
  updateMeta(false);
  return box;
}

/* 语文 10 类题型渲染器 */
function caRenderQuestionBody(q,ansObj,onChange,audioOpts){
  var wrap=el('div',{});
  if(q.passage){
    wrap.appendChild(el('div',{class:'ea-passage',text:q.passage}));
  }
  if(q.audioUrl){
    wrap.appendChild(caAudioBox(q,audioOpts));
  }
  wrap.appendChild(el('p',{class:'ma-q-text',text:q.text}));
  if(q.hint){
    wrap.appendChild(el('p',{class:'ea-hint',text:'提示：'+q.hint}));
  }
  var qt=q.questionType;

  if(qt==='basic_choice'||qt==='error_spot'||qt==='sentence_choice'||qt==='reading_choice'){
    var optsBox=el('div',{class:'ma-opts'});
    var keys=['A','B','C','D'];
    (q.options||[]).forEach(function(opt,idx){
      var b=el('button',{type:'button',class:'ma-opt'+(ansObj.selected_index===idx?' picked':'')},
        el('span',{class:'ma-opt-k',text:keys[idx]||String(idx+1)}),
        el('span',{text:opt}));
      b.onclick=function(){ansObj.selected_index=idx;onChange()};
      optsBox.appendChild(b);
    });
    wrap.appendChild(optsBox);
    return wrap;
  }

  if(qt==='hanzi_tiles'||qt==='poem_tiles'){
    var tiles=q.tiles||[];
    var usedIdx=ansObj._tileIndices||[];
    var slots=el('div',{class:'ea-slots'});
    if(!usedIdx.length){
      slots.appendChild(el('span',{class:'ma-muted',text:qt==='poem_tiles'?'依次点击下方字块补全古诗名句…':'依次点击下方字块拼出正确词语…'}));
    }else{
      usedIdx.forEach(function(ti,pos){
        var ch=el('span',{class:'ea-slot-chip',text:tiles[ti]});
        ch.onclick=function(){
          usedIdx.splice(pos,1);
          ansObj._tileIndices=usedIdx;
          ansObj.text_answer=usedIdx.map(function(k){return tiles[k]}).join('');
          onChange();
        };
        slots.appendChild(ch);
      });
    }
    var tileRow=el('div',{class:'ea-tiles'});
    tiles.forEach(function(ch,ti){
      var tb=el('button',{type:'button',class:'ea-tile',text:ch});
      if(usedIdx.indexOf(ti)>=0)tb.disabled=true;
      tb.onclick=function(){
        usedIdx.push(ti);
        ansObj._tileIndices=usedIdx;
        ansObj.text_answer=usedIdx.map(function(k){return tiles[k]}).join('');
        onChange();
      };
      tileRow.appendChild(tb);
    });
    var tools=el('div',{class:'ma-row'});
    var bk=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'退格'});
    bk.onclick=function(){usedIdx.pop();ansObj._tileIndices=usedIdx;ansObj.text_answer=usedIdx.map(function(k){return tiles[k]}).join('');onChange()};
    var clr=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'清空'});
    clr.onclick=function(){usedIdx.length=0;ansObj._tileIndices=usedIdx;ansObj.text_answer='';onChange()};
    tools.appendChild(bk);tools.appendChild(clr);
    wrap.appendChild(slots);wrap.appendChild(tileRow);wrap.appendChild(tools);
    return wrap;
  }

  if(qt==='reading_short'||qt==='micro_writing'){
    var ta=el('textarea',{
      class:'ca-textarea',
      placeholder:qt==='micro_writing'?'请在此写出 60～120 字的微片段描写（交卷后 AI 老师实时批改点评）…':'请结合原文细节简洁作答（交卷后 AI 老师实时批改点评）…'
    });
    ta.value=ansObj.text_answer||'';
    var wc=el('div',{class:'ca-wc'});
    function updWc(){
      var n=String(ta.value||'').replace(/\s+/g,'').length;
      wc.textContent='';
      wc.appendChild(el('span',{text:'当前已写 '+n+' 字'+(q.minChars?'（建议不少于 '+q.minChars+' 字）':'')}));
      wc.appendChild(el('span',{text:'交卷后由 AI 实时批改并给出修改建议'}));
    }
    ta.oninput=function(){ansObj.text_answer=ta.value;updWc();onChange(true)};
    updWc();
    wrap.appendChild(ta);wrap.appendChild(wc);
    return wrap;
  }

  var inp=el('input',{
    class:'ma-input',
    type:'text',
    placeholder:qt==='poem_fill'?'请输入古诗名句（不加标点也可）…':'请输入正确汉字词语…',
    value:ansObj.text_answer||''
  });
  inp.setAttribute('autocomplete','off');
  inp.oninput=function(){ansObj.text_answer=inp.value;onChange(true)};
  wrap.appendChild(inp);
  return wrap;
}
"""

CHINESE_MAP_JS = COMMON_CHINESE_JS + r"""
var CM_DATA=null,CM_SEL=null,CM_QUIZ=null,CM_ANS={},CM_IDX=0,CM_PLAY={};
var CM_BOX=el('div',{class:'ma-wrap'}),CM_TOP=el('div'),CM_SUM=el('div'),CM_DET=el('div',{class:'ma-detail-dock'}),CM_DOMS=el('div'),CM_QBOX=el('div'),CM_NOTE=el('div',{class:'ma-notice'});
root.textContent='';
root.appendChild(CM_BOX);
CM_BOX.appendChild(CM_TOP);CM_BOX.appendChild(CM_NOTE);CM_BOX.appendChild(CM_SUM);CM_BOX.appendChild(CM_DOMS);CM_BOX.appendChild(CM_DET);CM_BOX.appendChild(CM_QBOX);

function cmNotice(t,warn){
  CM_NOTE.className='ma-notice'+(t?(' show '+(warn?'warn':'info')):'');
  CM_NOTE.textContent=t||'';
}
function cmRenderMap(){
  caStopAudio();
  CM_QBOX.textContent='';
  var d=CM_DATA,s=d.summary;
  CM_TOP.textContent='';CM_TOP.appendChild(caTopbar('map',d.points));
  var pct=s.totalNodes?Math.round(s.litNodes/s.totalNodes*100):0;
  CM_SUM.textContent='';
  CM_SUM.appendChild(el('div',{class:'ma-card'},
    el('div',{class:'ma-sum-top'},
      el('div',{},
        el('div',{class:'ma-eyebrow',text:'小学五年级 · 通用语文知识地图'}),
        el('h2',{class:'ma-h1',text:'语文知识地图'}),
        el('p',{class:'ma-sub',text:'按字词语音、句子修辞、古诗文积累、阅读方法四大知识点域闯关，不限时轻微测，答对 ≥ 80% 即点亮'})),
      el('a',{class:'ma-btn ma-btn-ghost ma-btn-sm',href:'/v1/chinese-sprints',text:'去四大板块专项 ›'})),
    el('div',{class:'ma-sum-meta'},
      el('span',{},'已点亮 ',el('b',{text:s.litNodes+'/'+s.totalNodes}),'（'+pct+'%）'),
      el('span',{},'精通 ',el('b',{text:String(s.masteredNodes)})),
      el('span',{},'总星数 ',el('b',{text:s.totalStars+'/'+s.maxStars})),
      s.repairNodes?el('span',{style:'color:var(--ma-brand);font-weight:700'},'待修补 ',el('b',{text:String(s.repairNodes)})):null),
    el('div',{class:'ma-prog-track'},el('div',{class:'ma-prog-fill',style:'width:'+pct+'%'}))));
  var tipText=s.repairNodes
    ?('你有 '+s.repairNodes+' 个标红的语文薄弱点，点下方红色节点做一次 5 题轻微测就能修补并得 +2 积分！')
    :(s.litNodes===0?'欢迎来到语文知识地图！配普通话朗诵与字块默写，挑一个知识点点亮第一颗语文星吧！'
      :'已经点亮 '+s.litNodes+' 个语文节点啦！继续冲刺三星精通，再去四大板块专项实战检验！');
  CM_SUM.appendChild(caHelperTip(tipText,'长缨助手 · 语文闯关建议'));

  CM_DOMS.textContent='';
  var grid=el('div',{class:'ma-domains'});
  var domSub={
    words:'多音字、形近字、高频成语与听写词语',
    sentence:'关联词、病句诊断、句式转换与修辞标点',
    poetry:'写景爱国必背古诗、小古文实词与名言积累',
    reading:'关键句概括、说明方法、人物描写与审题立意'
  };
  d.domains.forEach(function(dom){
    var nodes=d.nodes.filter(function(n){return n.domain===dom.id});
    var litInDom=nodes.filter(function(n){return n.state==='lit'||n.state==='mastered'}).length;
    var card=el('div',{class:'ma-domain dom-'+dom.id},
      el('div',{class:'ma-domain-h'},
        el('div',{},
          el('h3',{text:dom.icon+' '+dom.name}),
          el('div',{class:'ma-domain-sub',text:domSub[dom.id]||''})),
        el('span',{class:'ma-domain-cnt',text:litInDom+'/'+nodes.length+' 已亮'})));
    var list=el('div',{class:'ma-nodes'});
    nodes.forEach(function(n){
      var cls='ma-node st-'+n.state+(n.needsRepair?' repair':'')+(CM_SEL&&CM_SEL.key===n.key?' sel':'');
      var tagCls=n.needsRepair?'repair':n.state;
      var tagTxt=n.needsRepair?'待修补':(n.stars?caStars(n.stars)+' '+n.stateLabel:n.stateLabel);
      var btn=el('button',{type:'button',class:cls},
        el('span',{class:'ma-node-left'},
          el('span',{class:'ma-node-key',text:n.key}),
          el('span',{class:'ma-node-name',text:n.name})),
        el('span',{class:'ma-tag '+tagCls,text:tagTxt}));
      btn.onclick=function(){CM_SEL=n;cmRenderDetail();cmRenderMapNodesSel()};
      list.appendChild(btn);
    });
    card.appendChild(list);
    grid.appendChild(card);
  });
  CM_DOMS.appendChild(grid);
  cmRenderDetail();
}
function cmRenderMapNodesSel(){
  var all=CM_DOMS.querySelectorAll('.ma-node');
  for(var i=0;i<all.length;i++){
    var k=all[i].querySelector('.ma-node-key');
    if(k&&CM_SEL&&k.textContent===CM_SEL.key)all[i].classList.add('sel');
    else all[i].classList.remove('sel');
  }
}
function cmRenderDetail(){
  CM_DET.textContent='';
  if(!CM_SEL)return;
  var n=CM_SEL;
  var go=el('button',{type:'button',class:'ma-btn ma-btn-primary',text:n.needsRepair?'开始修补微测（5 题）':(n.state==='unexplored'?'开始点亮微测（5 题）':'再练一次冲三星')});
  go.onclick=function(){cmStartQuiz(n)};
  CM_DET.appendChild(el('div',{class:'ma-card ma-detail'},
    el('div',{class:'ma-detail-info'},
      el('div',{class:'ma-eyebrow',text:'当前选中 · '+n.key}),
      el('h3',{text:n.icon+' '+n.name}),
      el('p',{class:'ma-muted',text:'状态：'+n.stateLabel+(n.stars?'（'+caStars(n.stars)+'）':'')+' · 最高正确率 '+n.bestQuizRate+'% · 含普通话朗诵与字块轻辅助'})),
    go));
}
function cmStartQuiz(n){
  cmNotice('正在准备 '+n.key+' 微测…');
  api('/student/chinese-star-map/nodes/'+encodeURIComponent(n.key)+'/quiz',{method:'POST'}).then(function(q){
    cmNotice('');
    CM_QUIZ=q;CM_ANS={};CM_IDX=0;CM_PLAY={};
    CM_SUM.textContent='';CM_DET.textContent='';CM_DOMS.textContent='';
    cmRenderQuiz();
  }).catch(function(e){cmNotice(e.message,true)});
}
function cmAnswered(a){return a&&((a.selected_index!==undefined&&a.selected_index!==null)||String(a.text_answer||'').trim().length>0)}
function cmRenderQuiz(){
  caStopAudio();
  CM_QBOX.textContent='';
  var qd=CM_QUIZ,qs=qd.questions,q=qs[CM_IDX];
  var ansObj=CM_ANS[q.id]||(CM_ANS[q.id]={});
  var doneCnt=0;
  qs.forEach(function(it){if(cmAnswered(CM_ANS[it.id]))doneCnt++});

  var hud=el('div',{class:'ma-hud'},
    el('div',{class:'ma-hud-top'},
      el('div',{},el('b',{text:qd.node.key+' '+qd.node.name}),el('span',{class:'ma-muted',style:'margin-left:8px',text:'5 题轻微测（不限时 · 80% 即点亮）'})),
      el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'退出返回地图',onclick:function(){CM_QUIZ=null;cmLoad()}})));
  var sheet=el('div',{class:'ma-sheet'});
  qs.forEach(function(it,i){
    var b=el('button',{type:'button',class:'ma-dot'+(i===CM_IDX?' cur':(cmAnswered(CM_ANS[it.id])?' done':'')),text:String(i+1)});
    b.onclick=function(){CM_IDX=i;cmRenderQuiz()};
    sheet.appendChild(b);
  });

  var qCard=el('div',{class:'ma-q-card'},
    el('div',{class:'ma-q-meta'},
      el('span',{text:'第 '+(CM_IDX+1)+' / '+qs.length+' 题 · '+q.typeLabel+'（'+q.levelLabel+'）'}),
      el('span',{text:'已完成 '+doneCnt+'/'+qs.length})));
  qCard.appendChild(caRenderQuestionBody(q,ansObj,function(silent){if(!silent)cmRenderQuiz()},{maxPlays:0,allowSlow:true,playState:CM_PLAY}));
  qCard.appendChild(caHelperTip(caQuestionHint(q),'长缨助手 · 解题提示'));

  var prevBtn=el('button',{type:'button',class:'ma-btn ma-btn-ghost',text:'上一题'});
  prevBtn.disabled=(CM_IDX===0);
  prevBtn.onclick=function(){CM_IDX--;cmRenderQuiz()};
  var isLast=(CM_IDX===qs.length-1);
  var nextBtn=el('button',{type:'button',class:'ma-btn '+(isLast?'ma-btn-ok':'ma-btn-primary'),text:isLast?'提交微测':'下一题'});
  nextBtn.onclick=function(){
    if(!isLast){CM_IDX++;cmRenderQuiz();return}
    cmSubmitQuiz();
  };
  qCard.appendChild(el('div',{class:'ma-foot'},prevBtn,nextBtn));

  CM_QBOX.appendChild(hud);CM_QBOX.appendChild(sheet);CM_QBOX.appendChild(qCard);
}
function cmSubmitQuiz(){
  caStopAudio();
  var qd=CM_QUIZ,arr=[];
  qd.questions.forEach(function(q){
    var a=CM_ANS[q.id]||{};
    arr.push({question_id:q.id,selected_index:(a.selected_index===undefined?null:a.selected_index),text_answer:String(a.text_answer||'')});
  });
  cmNotice('正在批改…');
  api('/student/chinese-star-map/nodes/'+encodeURIComponent(qd.node.key)+'/quiz/submit',{
    method:'POST',
    json:{quiz_id:qd.quizId,answers:arr}
  }).then(function(res){
    cmNotice('');
    CM_QUIZ=null;
    CM_QBOX.textContent='';
    CM_TOP.textContent='';CM_TOP.appendChild(caTopbar('map',res.points));
    var head=el('div',{class:'ma-card ma-res-head'},
      el('div',{class:'ma-res-tier',text:res.passed?('🎉 点亮成功 · '+res.nodeState.stateLabel+(res.nodeState.stars?' '+caStars(res.nodeState.stars):'')):'继续加油 · 差一点就点亮啦'}),
      el('h2',{class:'ma-h1',text:res.nodeKey+' '+res.nodeName+'：答对 '+res.correct+' / '+res.total+' 题（'+res.ratePct+'%）'}),
      res.repaired?el('p',{class:'ma-sub',style:'color:var(--ma-ok);font-weight:700',text:'已成功消除该节点的「待修补」红标！'}):null,
      caPointsGain(res.pointsAwarded,res.points),
      el('div',{class:'ma-row',style:'justify-content:center;margin-top:14px'},
        el('button',{type:'button',class:'ma-btn ma-btn-primary',text:'返回语文知识地图',onclick:function(){cmLoad()}}),
        el('a',{class:'ma-btn ma-btn-ghost',href:'/v1/chinese-sprints',text:'去挑战语文应试专项'})));
    CM_QBOX.appendChild(head);
    var rev=el('div',{class:'ma-card'},el('h3',{text:'逐题解析'}));
    res.details.forEach(function(d,i){
      var box=el('div',{class:'ma-rev '+(d.correct?'ok':'bad')},
        el('b',{text:(i+1)+'. ['+d.typeLabel+'] '+(d.correct?'✓ 正确':'✗ 错题')+' · 参考答案：'+d.answer}),
        el('div',{text:d.explanation}));
      if(d.aiComment){
        box.appendChild(el('div',{class:'ca-ai-box',text:(d.gradingMode==='ai'?'AI 老师点评：':'智能要点点评：')+d.aiComment}));
      }
      rev.appendChild(box);
    });
    CM_QBOX.appendChild(rev);
  }).catch(function(e){cmNotice(e.message,true)});
}
function cmLoad(){
  api('/student/chinese-star-map').then(function(d){
    CM_DATA=d;
    var hash=location.hash||'';
    if(hash.indexOf('#node=')===0){
      var want=decodeURIComponent(hash.slice(6));
      d.nodes.forEach(function(n){if(n.key===want)CM_SEL=n});
    }
    if(!CM_SEL&&d.nodes.length)CM_SEL=d.nodes[0];
    cmRenderMap();
  }).catch(function(e){cmNotice(e.message,true)});
}
caBoot(cmLoad);
"""

CHINESE_SPRINTS_JS = COMMON_CHINESE_JS + r"""
var CS_DATA=null,CS_ATT=null,CS_ANS={},CS_IDX=0,CS_PLAY={},CS_TIMER=null,CS_LEFT=0,CS_QLEFT=0,CS_SUBMITTING=false;
var CS_BOX=el('div',{class:'ma-wrap'}),CS_TOP=el('div'),CS_NOTE=el('div',{class:'ma-notice'}),CS_BODY=el('div');
root.textContent='';
root.appendChild(CS_BOX);
CS_BOX.appendChild(CS_TOP);CS_BOX.appendChild(CS_NOTE);CS_BOX.appendChild(CS_BODY);

function csNotice(t,warn){
  CS_NOTE.className='ma-notice'+(t?(' show '+(warn?'warn':'info')):'');
  CS_NOTE.textContent=t||'';
}
function csStopTimer(){if(CS_TIMER){clearInterval(CS_TIMER);CS_TIMER=null}}
function csAnswered(a){return a&&((a.selected_index!==undefined&&a.selected_index!==null)||String(a.text_answer||'').trim().length>0)}

function csRenderLobby(){
  csStopTimer();caStopAudio();
  var d=CS_DATA;
  CS_TOP.textContent='';CS_TOP.appendChild(caTopbar('sprints',d.points));
  CS_BODY.textContent='';
  CS_BODY.appendChild(el('div',{class:'ma-card'},
    el('div',{class:'ma-eyebrow',text:'小学五年级 · 语文四大试卷板块应试专项'}),
    el('h2',{class:'ma-h1',text:'语文应试专项'}),
    el('p',{class:'ma-sub',text:'基础字词句采用「单题限时 20 秒」快节奏听写抢答；古诗文 / 现代文阅读 / 表达与微写作采用「整体倒计时」，阅读简答与微写作支持 AI 实时批改点评！'})));
  CS_BODY.appendChild(caHelperTip('四个板块均可直接开考，无需先刷完地图！达标（L2+）自动反哺点亮语文地图，失分点会自动标红提醒修补。','长缨助手 · 备考提示'));

  var grid=el('div',{class:'ma-sprints'});
  d.sprints.forEach(function(sp){
    var tierTxt=sp.bestTier?(sp.bestTier.badge+' '+sp.bestTier.code+' '+sp.bestTier.name):'尚未挑战';
    var timeTag=sp.timingMode==='per_question'
      ?('单题限时 '+sp.perQuestionSec+' 秒/题')
      :('整体倒计时 '+Math.round(sp.timeLimitSec/60)+' 分钟');
    var go=el('button',{type:'button',class:'ma-btn ma-btn-primary',text:sp.attempts?'再次冲刺段位':'立即开考'});
    go.onclick=function(){csStart(sp.slug)};
    grid.appendChild(el('div',{class:'ma-sprint'},
      el('div',{},
        el('div',{class:'ma-row',style:'margin-bottom:6px'},
          el('span',{class:'ca-sec ca-sec-'+sp.section,text:sp.sectionLabel}),
          el('h3',{style:'margin:0',text:sp.title})),
        el('p',{class:'ma-sub',text:sp.subtitle}),
        el('div',{class:'ma-sprint-tags'},
          el('span',{class:'ma-pill',text:timeTag}),
          el('span',{class:'ma-pill',text:sp.questionCount+' 题实战'}),
          (sp.section==='reading'||sp.section==='writing')?el('span',{class:'ma-pill',text:'AI 实时点评'}):null,
          el('span',{class:'ma-pill',text:'最高：'+tierTxt}))),
      go));
  });
  CS_BODY.appendChild(grid);
}

function csStart(slug){
  csNotice('正在组卷开考…');
  api('/student/chinese-sprints/'+encodeURIComponent(slug)+'/start',{method:'POST'}).then(function(att){
    csNotice('');
    CS_ATT=att;CS_ANS={};CS_IDX=0;CS_PLAY={};CS_SUBMITTING=false;
    CS_LEFT=att.timeLimitSec;
    CS_QLEFT=att.perQuestionSec||20;
    csRenderExam();
    csStartClock();
  }).catch(function(e){csNotice(e.message,true)});
}

function csStartClock(){
  csStopTimer();
  var isPerQ=(CS_ATT&&CS_ATT.timingMode==='per_question');
  CS_TIMER=setInterval(function(){
    if(!CS_ATT||CS_SUBMITTING)return;
    CS_LEFT=Math.max(0,CS_LEFT-1);
    if(isPerQ){
      CS_QLEFT=Math.max(0,CS_QLEFT-1);
      var qClk=document.getElementById('cs-qclock');
      var qBar=document.getElementById('cs-qbar');
      if(qClk)qClk.textContent='本题剩余 '+caClockText(CS_QLEFT);
      if(qBar&&CS_ATT.perQuestionSec){
        qBar.style.width=Math.max(0,Math.round(CS_QLEFT/CS_ATT.perQuestionSec*100))+'%';
      }
      if(CS_QLEFT<=0){
        if(CS_IDX<CS_ATT.questions.length-1){
          CS_IDX++;
          CS_QLEFT=CS_ATT.perQuestionSec||20;
          csRenderExam();
        }else{
          csSubmit(true);
        }
        return;
      }
    }
    var clk=document.getElementById('cs-clock');
    var hud=document.getElementById('cs-hud');
    if(clk)clk.textContent=(isPerQ?'总剩余 ':'倒计时 ')+caClockText(CS_LEFT);
    if(hud&&(isPerQ?CS_QLEFT<=5:CS_LEFT<=60))hud.classList.add('urgent');
    if(CS_LEFT<=0){csSubmit(true)}
  },1000);
}

function csRenderExam(){
  caStopAudio();
  CS_BODY.textContent='';
  var att=CS_ATT,qs=att.questions,q=qs[CS_IDX];
  var isPerQ=(att.timingMode==='per_question');
  var ansObj=CS_ANS[q.id]||(CS_ANS[q.id]={});
  var doneCnt=0;
  qs.forEach(function(it){if(csAnswered(CS_ANS[it.id]))doneCnt++});

  var hud=el('div',{id:'cs-hud',class:'ma-hud'+((isPerQ?CS_QLEFT<=5:CS_LEFT<=60)?' urgent':'')},
    el('div',{class:'ma-hud-top'},
      el('div',{},
        el('b',{text:att.sprint.title}),
        el('span',{class:'ma-muted',style:'margin-left:8px',text:'第 '+(CS_IDX+1)+'/'+qs.length+' 题 · 已答 '+doneCnt+'/'+qs.length})),
      el('div',{class:'ma-row'},
        isPerQ?el('span',{id:'cs-qclock',class:'ma-clock',text:'本题剩余 '+caClockText(CS_QLEFT)}):null,
        el('span',{id:'cs-clock',class:isPerQ?'ma-pill':'ma-clock',text:(isPerQ?'总剩余 ':'倒计时 ')+caClockText(CS_LEFT)}))));
  if(isPerQ&&att.perQuestionSec){
    var pct=Math.max(0,Math.round(CS_QLEFT/att.perQuestionSec*100));
    hud.appendChild(el('div',{class:'ea-qbar-track'},el('div',{id:'cs-qbar',class:'ea-qbar-fill',style:'width:'+pct+'%'})));
  }
  CS_BODY.appendChild(hud);

  if(!isPerQ){
    var sheet=el('div',{class:'ma-sheet'});
    qs.forEach(function(it,i){
      var b=el('button',{type:'button',class:'ma-dot'+(i===CS_IDX?' cur':(csAnswered(CS_ANS[it.id])?' done':'')),text:String(i+1)});
      b.onclick=function(){CS_IDX=i;csRenderExam()};
      sheet.appendChild(b);
    });
    CS_BODY.appendChild(sheet);
  }

  var qCard=el('div',{class:'ma-q-card'},
    el('div',{class:'ma-q-meta'},
      el('span',{text:'第 '+(CS_IDX+1)+' 题 · '+q.typeLabel+'（'+q.marks+' 分）'}),
      el('span',{text:isPerQ?'单题限时模式（超时自动切题）':'整体限时模式（可自由回看）'})));
  qCard.appendChild(caRenderQuestionBody(q,ansObj,function(silent){if(!silent)csRenderExam()},{
    maxPlays:att.maxPlays||0,
    allowSlow:!isPerQ,
    playState:CS_PLAY
  }));
  qCard.appendChild(caHelperTip(caQuestionHint(q),'长缨助手 · 考场提示'));

  var leftBtn=isPerQ
    ?el('span',{class:'ma-muted',text:'单题限时模式不可回退上一题'})
    :el('button',{type:'button',class:'ma-btn ma-btn-ghost',text:'上一题'});
  if(!isPerQ){
    leftBtn.disabled=(CS_IDX===0);
    leftBtn.onclick=function(){CS_IDX--;csRenderExam()};
  }
  var isLast=(CS_IDX===qs.length-1);
  var nextBtn=el('button',{type:'button',class:'ma-btn '+(isLast?'ma-btn-ok':'ma-btn-primary'),text:isLast?'交卷并实时批改':'下一题'});
  nextBtn.onclick=function(){
    if(!isLast){
      CS_IDX++;
      if(isPerQ)CS_QLEFT=att.perQuestionSec||20;
      csRenderExam();
      return;
    }
    csSubmit(false);
  };
  qCard.appendChild(el('div',{class:'ma-foot'},leftBtn,nextBtn));
  CS_BODY.appendChild(qCard);
}

function csSubmit(autoSub){
  if(CS_SUBMITTING||!CS_ATT)return;
  CS_SUBMITTING=true;
  csStopTimer();caStopAudio();
  var att=CS_ATT,arr=[];
  att.questions.forEach(function(q){
    var a=CS_ANS[q.id]||{};
    arr.push({question_id:q.id,selected_index:(a.selected_index===undefined?null:a.selected_index),text_answer:String(a.text_answer||'')});
  });
  var hasSubj=(att.sprint.section==='reading'||att.sprint.section==='writing');
  csNotice(hasSubj?'正在交卷，AI 老师正在实时批改主观题与微写作…':(autoSub?'时间到，正在自动交卷评分…':'正在交卷评分…'));
  api('/student/chinese-sprints/attempts/'+att.attemptId+'/submit',{
    method:'POST',
    json:{answers:arr,auto_submitted:!!autoSub}
  }).then(function(res){
    csNotice('');
    CS_ATT=null;CS_SUBMITTING=false;
    CS_TOP.textContent='';CS_TOP.appendChild(caTopbar('sprints',res.points));
    CS_BODY.textContent='';
    var head=el('div',{class:'ma-card ma-res-head'},
      el('div',{class:'ma-res-tier',text:res.tier.badge+' '+res.tier.code+' '+res.tier.name}),
      el('h2',{class:'ma-h1',text:'得分 '+res.earnedMarks+' / '+res.totalMarks+'（'+res.scoreRate+'%）'}),
      el('p',{class:'ma-sub',text:'达标 '+res.correctCount+'/'+res.questionCount+' 题 · 用时 '+caClockText(res.elapsedSec)+(res.autoSubmitted?'（时间到自动交卷）':'')}),
      caPointsGain(res.pointsAwarded,res.points),
      el('div',{class:'ma-row',style:'justify-content:center;margin-top:14px'},
        el('button',{type:'button',class:'ma-btn ma-btn-primary',text:'返回语文应试专项',onclick:function(){csLoad()}}),
        el('a',{class:'ma-btn ma-btn-ghost',href:'/v1/chinese-star-map',text:'查看语文知识地图'})));
    CS_BODY.appendChild(head);

    var resTip=res.topLosses&&res.topLosses.length
      ?('已自动把本次失分最多的 '+res.topLosses.length+' 个语文考点标红在知识地图中，点击下方「去地图修补」即可 5 题定向消除红标！')
      :'本次表现非常出色！全对的知识点已同步反哺点亮你的语文知识地图！';
    CS_BODY.appendChild(caHelperTip(resTip,'长缨助手 · 考后复盘'));

    if(res.mapChanges&&(res.mapChanges.lit.length||res.mapChanges.flagged.length)){
      var mc=el('div',{class:'ma-card'},el('h3',{text:'知识地图双向联动更新'}));
      if(res.mapChanges.lit.length){
        mc.appendChild(el('p',{class:'ma-sub',style:'color:var(--ma-ok);font-weight:700;margin-bottom:8px',
          text:'本次专项反哺新点亮：'+res.mapChanges.lit.map(function(x){return x.key+' '+x.name}).join('、')}));
      }
      res.mapChanges.flagged.forEach(function(x){
        mc.appendChild(el('div',{class:'ma-loss-row'},
          el('span',{text:'待修补红标：'+x.key+' '+x.name}),
          el('a',{class:'ma-btn ma-btn-primary ma-btn-sm',href:'/v1/chinese-star-map#node='+encodeURIComponent(x.key),text:'去地图修补 ›'})));
      });
      CS_BODY.appendChild(mc);
    }

    var rev=el('div',{class:'ma-card'},el('h3',{text:'逐题解析与点评'}));
    res.details.forEach(function(d,i){
      var scoreTag=(d.earnedMarks!==undefined)?('（得 '+d.earnedMarks+'/'+d.marks+' 分）'):'';
      var box=el('div',{class:'ma-rev '+(d.correct?'ok':'bad')},
        el('b',{text:(i+1)+'. ['+d.typeLabel+'] '+(d.correct?'✓ 达标':'✗ 需加强')+scoreTag+' · 参考答案/范文：'+d.answer}),
        el('div',{text:d.explanation}));
      if(d.aiComment){
        box.appendChild(el('div',{class:'ca-ai-box',text:(d.gradingMode==='ai'?'AI 老师实时点评：':'智能要点点评：')+d.aiComment}));
      }
      rev.appendChild(box);
    });
    CS_BODY.appendChild(rev);
  }).catch(function(e){CS_SUBMITTING=false;csNotice(e.message,true)});
}

function csLoad(){
  api('/student/chinese-sprints').then(function(d){
    CS_DATA=d;
    csRenderLobby();
  }).catch(function(e){csNotice(e.message,true)});
}
caBoot(csLoad);
"""

HELPER_AVATAR_JS = 'window.__CY_HELPER_AVATAR__="data:image/png;base64,' + AVATAR_PNG_B64 + '";\n'


def chinese_star_map_page_html() -> str:
    return _page("语文知识地图", HELPER_AVATAR_JS + ARENA_ROLE_HUB_JS + CHINESE_MAP_JS, True).replace(
        "</head>", ARENA_CSS + ENGLISH_EXTRA_CSS + CHINESE_EXTRA_CSS + "</head>", 1
    )


def chinese_sprints_page_html() -> str:
    return _page("语文应试专项", HELPER_AVATAR_JS + ARENA_ROLE_HUB_JS + CHINESE_SPRINTS_JS, True).replace(
        "</head>", ARENA_CSS + ENGLISH_EXTRA_CSS + CHINESE_EXTRA_CSS + "</head>", 1
    )


__all__ = ["chinese_sprints_page_html", "chinese_star_map_page_html"]
