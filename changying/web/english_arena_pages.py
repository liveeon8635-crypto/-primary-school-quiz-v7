"""英语知识地图（按知识点域）与强应试专项（按听/说/读/写）前端页面（宣纸暖白 + 长缨绛红，纯 ES5，无 innerHTML）."""
from __future__ import annotations

from changying.web.arena_role_hub import ARENA_ROLE_HUB_JS
from changying.web.math_arena_pages import ARENA_CSS
from changying.web.v1_nezha_icons import AVATAR_PNG_B64
from changying.web.weekend_pages import _page

ENGLISH_EXTRA_CSS = """<style>
/* 学科切换胶囊与英语专属交互组件 */
.ea-subj{display:inline-flex;background:#efe6dc;border-radius:10px;padding:3px;gap:3px;box-shadow:inset 0 1px 2px rgba(56,28,24,.08)}
.ea-subj a{padding:5px 12px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:800;color:var(--ma-muted);transition:all .15s ease}
.ea-subj a.on{background:#fff;color:var(--ma-brand);box-shadow:0 1px 3px rgba(56,28,24,.12)}
.ma-domain.dom-phonics{border-top-color:var(--ma-brand)}
.ma-domain.dom-vocab{border-top-color:var(--ma-ok)}
.ma-domain.dom-grammar{border-top-color:var(--ma-gold)}
.ma-domain.dom-reading{border-top-color:var(--ma-blue)}
.ma-domain.dom-phonics .ma-domain-cnt{background:var(--ma-brand-soft);color:var(--ma-brand)}
.ma-domain.dom-vocab .ma-domain-cnt{background:var(--ma-ok-soft);color:var(--ma-ok)}
.ma-domain.dom-grammar .ma-domain-cnt{background:var(--ma-gold-soft);color:var(--ma-gold)}
.ma-domain.dom-reading .ma-domain-cnt{background:var(--ma-blue-soft);color:var(--ma-blue)}

/* 能力徽标（听/说/读/写） */
.ea-ab{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:9px;font-size:14px;font-weight:900;color:#fff;flex-shrink:0;box-shadow:0 2px 0 rgba(0,0,0,.14)}
.ea-ab-listening{background:#a8101c}
.ea-ab-speaking{background:#b45309}
.ea-ab-reading{background:#1e4e79}
.ea-ab-writing{background:#0b8f5a}

/* 静态 MP3 音频播放条 */
.ea-audio{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:10px 14px;border-radius:12px;background:#fcf8f3;border:1px solid #ead8cb;margin-bottom:14px}
.ea-play-btn{display:inline-flex;align-items:center;gap:6px;padding:7px 14px;border-radius:10px;border:1px solid var(--ma-brand);background:var(--ma-brand);color:#fff;font-size:13.5px;font-weight:700;cursor:pointer;font-family:inherit;box-shadow:0 2px 0 var(--ma-brand-dark)}
.ea-play-btn:disabled{opacity:.5;cursor:not-allowed}
.ea-rate-btn{padding:6px 10px;border-radius:8px;border:1px solid var(--ma-line);background:#fff;color:var(--ma-ink);font-size:12.5px;font-weight:700;cursor:pointer;font-family:inherit}
.ea-rate-btn.on{border-color:var(--ma-brand);background:var(--ma-brand-soft);color:var(--ma-brand)}
.ea-audio-meta{font-size:12.5px;color:var(--ma-muted);font-weight:600}

/* 短文阅读框 */
.ea-passage{background:#fcfaf7;border:1px solid #ead8cb;border-left:4px solid var(--ma-blue);border-radius:11px;padding:12px 14px;margin-bottom:14px;font-size:14.5px;line-height:1.75;color:var(--ma-ink)}

/* 字母拼块 / 词池 / 连词成句 */
.ea-slots{display:flex;align-items:center;gap:6px;flex-wrap:wrap;min-height:44px;padding:8px 12px;border-radius:11px;border:1.5px dashed #d8c6b8;background:#fffdf9;margin-bottom:10px;font-size:16px;font-weight:800;color:var(--ma-ink)}
.ea-slot-chip{display:inline-flex;align-items:center;padding:5px 11px;border-radius:8px;background:var(--ma-brand-soft);border:1px solid #efc0bc;color:var(--ma-brand-dark);font-size:15px;font-weight:800;cursor:pointer}
.ea-tiles{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.ea-tile{min-width:38px;padding:8px 12px;border-radius:10px;border:1.5px solid var(--ma-line);background:#fff;color:var(--ma-ink);font-size:15px;font-weight:800;cursor:pointer;font-family:inherit;box-shadow:0 2px 0 #e6d8ce;transition:all .12s ease}
.ea-tile:hover:not(:disabled){border-color:var(--ma-brand);background:#fffafa;transform:translateY(-1px)}
.ea-tile:disabled{opacity:.35;cursor:default;box-shadow:none}
.ea-tile.picked{border-color:var(--ma-brand);background:var(--ma-brand-soft);color:var(--ma-brand-dark)}
.ea-hint{font-size:12.5px;color:var(--ma-muted);margin:0 0 10px}

/* 跟读识别面板 */
.ea-speak-box{padding:12px 14px;border-radius:12px;background:#fcfaf7;border:1px solid #ead8cb;margin-bottom:12px}
.ea-speak-target{font-size:17px;font-weight:800;color:var(--ma-ink);margin:0 0 10px;line-height:1.6}
.ea-speak-words{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.ea-sw{padding:3px 8px;border-radius:7px;font-size:13.5px;font-weight:700;background:#efeae4;color:var(--ma-muted)}
.ea-sw.hit{background:var(--ma-ok-soft);color:var(--ma-ok)}
.ea-sw.miss{background:var(--ma-brand-soft);color:var(--ma-brand)}

/* 单题限时进度条 */
.ea-qbar-track{margin-top:8px;height:6px;background:#efe7de;border-radius:999px;overflow:hidden}
.ea-qbar-fill{height:100%;background:linear-gradient(90deg,#a8101c 0%,#e07a5f 100%);border-radius:999px;transition:width .25s linear}
</style>"""

COMMON_ENGLISH_JS = r"""
var EA_AUDIO_OBJ=null;
function eaStopAudio(){
  if(EA_AUDIO_OBJ){try{EA_AUDIO_OBJ.pause();EA_AUDIO_OBJ.currentTime=0}catch(_e){}EA_AUDIO_OBJ=null}
  if(window.speechSynthesis){try{window.speechSynthesis.cancel()}catch(_e2){}}
}
function eaTopbar(active,pts){
  var bar=el('div',{class:'ma-topbar'});
  var left=el('div',{class:'ma-topbar-left'},
    el('a',{class:'ma-link-btn',href:'/classic?legacy=1&unified=1&page=practice',text:'‹ 返回练习'}),
    el('div',{class:'ea-subj'},
      el('a',{href:active==='sprints'?'/v1/math-sprints':'/v1/math-star-map',text:'数学'}),
      el('a',{href:active==='sprints'?'/v1/english-sprints':'/v1/english-star-map',class:'on',text:'英语'}),
      el('a',{href:active==='sprints'?'/v1/chinese-sprints':'/v1/chinese-star-map',text:'语文'})));
  var seg=el('div',{class:'ma-seg'},
    el('a',{href:'/v1/english-star-map',class:active==='map'?'on':'',text:'知识地图'}),
    el('a',{href:'/v1/english-sprints',class:active==='sprints'?'on':'',text:'应试专项'}));
  var right=el('div',{class:'ma-topbar-right'});
  var u=window.__CY_ARENA_USER__;
  if(u&&u.name)right.appendChild(el('span',{class:'ma-user-pill',text:u.name+' · 学生'}));
  if(pts)right.appendChild(el('a',{class:'ma-pts',href:'/classic?legacy=1&unified=1&page=rewards',style:'text-decoration:none',title:'查看全站积分奖励 · 英语今日学习积分 '+pts.todayEarned+'/'+pts.dailyCap,text:'积分 '+pts.balance+' ›'}));
  bar.appendChild(left);bar.appendChild(seg);bar.appendChild(right);
  return bar;
}
function eaFetchTasks(subject){
  return api('/student/arena-tasks').catch(function(){
    return api('/student/arena/tasks?subject='+encodeURIComponent(subject));
  }).then(function(r){
    var arr=(r&&r.items)?r.items:[];
    return arr.filter(function(it){
      return (!it.subject||it.subject===subject)&&it.status!=='done';
    });
  }).catch(function(){return []});
}
function eaRenderTaskBanner(tasks,onGo){
  if(!tasks||!tasks.length)return null;
  var list=el('div',{class:'ma-task-list'});
  tasks.forEach(function(t){
    var goalTxt=(t.goalLabel||t.goalCode||'完成练习')+(t.isFresh?'（需重新完成）':'');
    var metaTxt='目标：'+goalTxt+(t.dueDate?(' · 截止 '+t.dueDate):'');
    var btn=el('button',{type:'button',class:'ma-btn ma-btn-primary ma-btn-sm',text:'立即前往'});
    btn.onclick=function(){onGo(t)};
    list.appendChild(el('div',{class:'ma-task-item'},
      el('div',{class:'ma-task-info'},
        el('div',{class:'ma-task-name',text:(t.taskKind==='sprint'?'[专项] ':'[考点] ')+(t.targetTitle||t.targetKey)}),
        el('div',{class:'ma-task-meta',text:metaTxt})),
      btn));
  });
  return el('div',{class:'ma-task-banner'},
    el('div',{class:'ma-task-banner-h'},
      el('div',{class:'ma-task-banner-title',text:'📌 老师布置的今日任务（'+tasks.length+' 项待完成）'})),
    list);
}
function eaHelperTip(text,tag){
  var src=window.__CY_HELPER_AVATAR__||'';
  return el('div',{class:'ma-helper'},
    src?el('img',{class:'ma-helper-ava',src:src,alt:'长缨助手'}):null,
    el('div',{class:'ma-helper-body'},
      el('div',{class:'ma-helper-name',text:tag||'长缨助手'}),
      el('p',{class:'ma-helper-text',text:text})));
}
function eaPointsGain(awarded,pts){
  if(!awarded)return null;
  if(awarded.total>0){
    return el('div',{class:'ma-pts-gain',text:'全站积分 +'+awarded.total+' 分'+(pts?'（当前总积分 '+pts.balance+'）':'')});
  }
  if(awarded.capped){
    return el('div',{class:'ma-pts-gain',text:'今日英语闯关积分已达 30 分上限，本次成绩已正常记录'});
  }
  return null;
}
function eaStars(n){var s='',i;for(i=0;i<n;i++)s+='★';return s}
function eaClockText(sec){var s=Math.max(0,Math.floor(sec)),m=Math.floor(s/60),r=s%60;return (m<10?'0':'')+m+':'+(r<10?'0':'')+r}
function eaQuestionHint(q){
  if(!q)return '仔细听清单词重音与关键词，稳稳作答！';
  var t=q.questionType;
  if(t==='listen_choice'||t==='listen_tf')return '先快速浏览选项里的关键词，再点击播放听音抓重点！';
  if(t==='phonics_choice')return '轻轻读出每个单词，对比划线字母组合的发音规律！';
  if(t==='speak_read')return '先听一遍示范原声，注意连读和尾音，再清晰大声跟读！';
  if(t==='word_tiles')return '先听读音再按自然拼读顺序点选字母块，拼错了可以点退格！';
  if(t==='word_spell')return '键盘拼写注意单复数和星期专有名词首字母大写哦！';
  if(t==='sentence_bank')return '把选中的词放回句子默读一遍，看看主谓搭配是否通顺！';
  if(t==='sentence_fill')return '语法填空先看主语人称（是否三单）、can 后用原形、There be 看就近原则！';
  if(t==='sentence_order')return '连词成句先找首字母大写的词放开头，疑问句注意助动词或 be 动词提前！';
  return '认真读清短文或对话细节，排除干扰项再作答！';
}
function eaRenderRoleOverview(role){
  root.textContent='';
  var isTeacher=(role==='teacher'||role==='admin');
  var backHref=isTeacher?'/v1':'/classic?legacy=1&unified=1&page=parent';
  var backText=isTeacher?'‹ 返回工作台':'‹ 返回家长端';
  var bar=el('div',{class:'ma-topbar'},
    el('div',{class:'ma-topbar-left'},
      el('a',{class:'ma-link-btn',href:backHref,text:backText}),
      el('div',{class:'ea-subj'},
        el('a',{href:'/v1/math-star-map',text:'数学'}),
        el('a',{href:'/v1/english-star-map',class:'on',text:'英语'}),
        el('a',{href:'/v1/chinese-star-map',text:'语文'}))),
    el('div',{class:'ma-topbar-right'},el('span',{class:'ma-pts',text:isTeacher?'教师英语学情':'家长英语学情'})));
  var box=el('div',{class:'ma-wrap'},bar);
  root.appendChild(box);
  var url=isTeacher?'/teacher/english-arena/overview':'/parent/english-arena/children';
  api(url).then(function(d){
    box.appendChild(el('div',{class:'ma-card'},
      el('div',{class:'ma-eyebrow',text:'小学英语 · 知识地图与听说读写专项'}),
      el('h2',{class:'ma-h1',text:isTeacher?'全班英语闯关与听说读写学情':'孩子英语闯关与听说读写学情'}),
      el('p',{class:'ma-sub',text:'覆盖 '+d.totalNodes+' 个核心英语知识点域节点与 '+d.totalSprints+' 个听说读写专项，积分独立计入全站账本。'})));
    box.appendChild(eaHelperTip(
      isTeacher?'这里汇总了全班学生的英语知识地图点亮进度、待修补考点、听说读写专项最高段位和全站积分。'
               :'这里同步展示孩子的英语知识地图点亮情况与听说读写专项分级结果，重点关注标红的待修补考点即可。',
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
function eaBoot(run){
  obtainToken().then(function(t){
    TOKEN=t;
    if(!TOKEN){msg('请先登录后再打开');return}
    return api('/session').then(function(s){
      if(s.role==='student'){window.__CY_ARENA_USER__=s;run();return}
      if(s.role==='teacher'||s.role==='admin'||s.role==='parent'){arenaRoleHub(s.role,'英语',s);return}
      msg('当前身份无法访问此页面');
    });
  }).catch(function(e){msg(e.message||'打不开')});
}

/* 音频播放组件（原生 MP3 + 限次控制 + 异常 speechSynthesis 兜底） */
function eaAudioBox(q,opts){
  opts=opts||{};
  var maxPlays=opts.maxPlays||0;
  var allowSlow=(opts.allowSlow!==false);
  var playState=opts.playState||{};
  var played=playState[q.id]||0;
  var rate=1.0;
  var box=el('div',{class:'ea-audio'});
  var btn=el('button',{type:'button',class:'ea-play-btn',text:'▶ 播放录音'});
  var meta=el('span',{class:'ea-audio-meta',text:maxPlays?('已播 '+played+'/'+maxPlays+' 遍'):'可反复听清再作答'});
  function updateMeta(playing){
    if(playing){btn.textContent='🔊 正在播放…';btn.disabled=true;return}
    var left=maxPlays?(maxPlays-played):99;
    btn.disabled=(maxPlays>0&&left<=0);
    btn.textContent=(maxPlays>0&&left<=0)?'已播完':'▶ 播放录音';
    meta.textContent=maxPlays?('已播 '+played+'/'+maxPlays+' 遍'+(left<=0?'（已达上限）':'')):'点击重听 · 清晰美音';
  }
  function doPlay(){
    if(maxPlays>0&&played>=maxPlays)return;
    eaStopAudio();
    played+=1;
    playState[q.id]=played;
    updateMeta(true);
    var au=new Audio(q.audioUrl);
    EA_AUDIO_OBJ=au;
    try{au.playbackRate=rate}catch(_e){}
    au.onended=function(){EA_AUDIO_OBJ=null;updateMeta(false);if(opts.onEnded)opts.onEnded()};
    au.onerror=function(){
      EA_AUDIO_OBJ=null;
      if(window.speechSynthesis&&q.speakTarget){
        try{
          var ut=new SpeechSynthesisUtterance(q.speakTarget);
          ut.lang='en-US';ut.rate=rate;
          ut.onend=function(){updateMeta(false);if(opts.onEnded)opts.onEnded()};
          window.speechSynthesis.speak(ut);
          return;
        }catch(_e2){}
      }
      updateMeta(false);
      meta.textContent='音频加载失败，请重试';
    };
    var p=au.play();
    if(p&&typeof p.catch==='function'){
      p.catch(function(){updateMeta(false);meta.textContent='请再次点击播放录音'});
    }
  }
  btn.onclick=doPlay;
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

/* 通用 10 类英语题型作答渲染器 */
function eaRenderQuestionBody(q,ansObj,onChange,audioOpts){
  var wrap=el('div',{});
  if(q.passage){
    wrap.appendChild(el('div',{class:'ea-passage',text:q.passage}));
  }
  if(q.audioUrl){
    wrap.appendChild(eaAudioBox(q,audioOpts));
  }
  if(q.isCustom){
    wrap.appendChild(el('div',{class:'ma-custom-badge',text:'★ 老师精选'}));
  }
  wrap.appendChild(el('p',{class:'ma-q-text',text:q.text}));
  if(q.hint){
    wrap.appendChild(el('p',{class:'ea-hint',text:'提示：'+q.hint}));
  }
  var qt=q.questionType;

  // 1. 客观单选类（兼容老师私房单选/判断题）
  if(qt==='listen_choice'||qt==='listen_tf'||qt==='phonics_choice'||qt==='reading_choice'||qt==='single_choice'||qt==='true_false'){
    var optsBox=el('div',{class:'ma-opts'});
    var keys=['A','B','C','D'];
    var qOpts=(q.options&&q.options.length)?q.options:(qt==='true_false'?['正确','错误']:[]);
    qOpts.forEach(function(opt,idx){
      var b=el('button',{type:'button',class:'ma-opt'+(ansObj.selected_index===idx?' picked':'')},
        el('span',{class:'ma-opt-k',text:keys[idx]||String(idx+1)}),
        el('span',{text:opt}));
      b.onclick=function(){
        ansObj.selected_index=idx;
        onChange();
      };
      optsBox.appendChild(b);
    });
    wrap.appendChild(optsBox);
    return wrap;
  }

  // 2. 字母拼块单词填空（地图轻辅助）
  if(qt==='word_tiles'){
    var tiles=q.tiles||[];
    var usedIdx=ansObj._tileIndices||[];
    var slots=el('div',{class:'ea-slots'});
    if(!usedIdx.length){
      slots.appendChild(el('span',{class:'ma-muted',text:'请依次点击下方字母块拼出单词…'}));
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
      var isUsed=(usedIdx.indexOf(ti)>=0);
      var tb=el('button',{type:'button',class:'ea-tile',text:ch});
      if(isUsed)tb.disabled=true;
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

  // 3. 词池点选句子填空
  if(qt==='sentence_bank'){
    var bankRow=el('div',{class:'ea-tiles'});
    (q.wordBank||[]).forEach(function(w){
      var b=el('button',{type:'button',class:'ea-tile'+(ansObj.text_answer===w?' picked':''),text:w});
      b.onclick=function(){ansObj.text_answer=w;onChange()};
      bankRow.appendChild(b);
    });
    wrap.appendChild(bankRow);
    return wrap;
  }

  // 4. 连词成句（词块点击排序）
  if(qt==='sentence_order'){
    var words=q.wordBank||[];
    var pickedIdx=ansObj._orderIndices||[];
    var slotBox=el('div',{class:'ea-slots'});
    if(!pickedIdx.length){
      slotBox.appendChild(el('span',{class:'ma-muted',text:'依次点击下方词块组成完整句子…'}));
    }else{
      pickedIdx.forEach(function(wi,pos){
        var c=el('span',{class:'ea-slot-chip',text:words[wi]});
        c.onclick=function(){
          pickedIdx.splice(pos,1);
          ansObj._orderIndices=pickedIdx;
          ansObj.text_answer=pickedIdx.map(function(k){return words[k]}).join(' ');
          onChange();
        };
        slotBox.appendChild(c);
      });
    }
    var wRow=el('div',{class:'ea-tiles'});
    words.forEach(function(w,wi){
      var wb=el('button',{type:'button',class:'ea-tile',text:w});
      if(pickedIdx.indexOf(wi)>=0)wb.disabled=true;
      wb.onclick=function(){
        pickedIdx.push(wi);
        ansObj._orderIndices=pickedIdx;
        ansObj.text_answer=pickedIdx.map(function(k){return words[k]}).join(' ');
        onChange();
      };
      wRow.appendChild(wb);
    });
    var oTools=el('div',{class:'ma-row'});
    var oBk=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'撤回一词'});
    oBk.onclick=function(){pickedIdx.pop();ansObj._orderIndices=pickedIdx;ansObj.text_answer=pickedIdx.map(function(k){return words[k]}).join(' ');onChange()};
    var oClr=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'重置语序'});
    oClr.onclick=function(){pickedIdx.length=0;ansObj._orderIndices=pickedIdx;ansObj.text_answer='';onChange()};
    oTools.appendChild(oBk);oTools.appendChild(oClr);
    wrap.appendChild(slotBox);wrap.appendChild(wRow);wrap.appendChild(oTools);
    return wrap;
  }

  // 5. 跟读朗读（Web Speech API 实时比对 + 老设备平滑降级为听辨纠音）
  if(qt==='speak_read'){
    var SR=window.SpeechRecognition||window.webkitSpeechRecognition||null;
    var sBox=el('div',{class:'ea-speak-box'});
    sBox.appendChild(el('p',{class:'ea-speak-target',text:q.speakTarget||''}));
    if(SR&&!ansObj._useFallback){
      var recBtn=el('button',{type:'button',class:'ma-btn ma-btn-primary ma-btn-sm',text:'🎙️ 开始跟读录音'});
      var statusP=el('p',{class:'ma-muted',style:'margin-top:8px',text:ansObj.text_answer?('已识别：'+ansObj.text_answer):'点击按钮后清晰朗读上方英语句子'});
      var swRow=el('div',{class:'ea-speak-words'});
      function renderMatch(spoken){
        swRow.textContent='';
        if(!spoken)return;
        var sp=(spoken||'').toLowerCase().replace(/[^a-z0-9'\s]/g,' ').split(/\s+/);
        var tgt=(q.speakTarget||'').split(/\s+/);
        tgt.forEach(function(w){
          var clean=w.toLowerCase().replace(/[^a-z0-9']/g,'');
          var ok=sp.indexOf(clean)>=0;
          swRow.appendChild(el('span',{class:'ea-sw '+(ok?'hit':'miss'),text:w}));
        });
      }
      if(ansObj.text_answer&&ansObj.text_answer.indexOf('__fallback__:')!==0){renderMatch(ansObj.text_answer)}
      recBtn.onclick=function(){
        eaStopAudio();
        try{
          var rec=new SR();
          rec.lang='en-US';rec.interimResults=false;rec.maxAlternatives=1;
          recBtn.disabled=true;recBtn.textContent='🎙️ 正在聆听…';
          statusP.textContent='请大声朗读英文句子…';
          rec.onresult=function(ev){
            var txt=(ev.results&&ev.results[0]&&ev.results[0][0])?ev.results[0][0].transcript:'';
            ansObj.text_answer=txt;
            statusP.textContent='已识别：'+txt;
            renderMatch(txt);
            recBtn.disabled=false;recBtn.textContent='🎙️ 重新跟读';
            onChange(true);
          };
          rec.onerror=function(){
            recBtn.disabled=false;recBtn.textContent='🎙️ 开始跟读录音';
            statusP.textContent='未检测到麦克风或语音权限，可切换为下方听辨模式完成本题。';
          };
          rec.onend=function(){recBtn.disabled=false;if(recBtn.textContent==='🎙️ 正在聆听…')recBtn.textContent='🎙️ 开始跟读录音'};
          rec.start();
        }catch(_e){
          ansObj._useFallback=true;onChange();
        }
      };
      var swFallback=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'无麦克风？切换听辨模式'});
      swFallback.onclick=function(){ansObj._useFallback=true;ansObj.text_answer='';onChange()};
      sBox.appendChild(el('div',{class:'ma-row'},recBtn,swFallback));
      sBox.appendChild(statusP);
      sBox.appendChild(swRow);
    }else{
      sBox.appendChild(el('p',{class:'ma-muted',style:'margin-bottom:10px',text:'当前设备已切换为「原声跟读 + 听辨纠音」模式：请先跟读示范，再选出正确的发音规律：'}));
      var fbOpts=el('div',{class:'ma-opts'});
      var fKeys=['A','B','C','D'];
      (q.fallbackOptions||[]).forEach(function(opt,idx){
        var picked=(ansObj.text_answer==='__fallback__:'+idx);
        var b=el('button',{type:'button',class:'ma-opt'+(picked?' picked':'')},
          el('span',{class:'ma-opt-k',text:fKeys[idx]||String(idx+1)}),
          el('span',{text:opt}));
        b.onclick=function(){ansObj.text_answer='__fallback__:'+idx;ansObj.selected_index=idx;onChange()};
        fbOpts.appendChild(b);
      });
      sBox.appendChild(fbOpts);
    }
    wrap.appendChild(sBox);
    return wrap;
  }

  // 6. 纯键盘拼写 / 语法填空（关闭移动端自动纠错）
  var inp=el('input',{
    class:'ma-input',
    type:'text',
    placeholder:qt==='word_spell'?'请输入英文单词…':(qt==='fill_blank'?'请输入答案…':'请输入正确的词形或单词…'),
    value:ansObj.text_answer||''
  });
  inp.setAttribute('autocomplete','off');
  inp.setAttribute('autocorrect','off');
  inp.setAttribute('autocapitalize','off');
  inp.setAttribute('spellcheck','false');
  inp.oninput=function(){ansObj.text_answer=inp.value;onChange(true)};
  wrap.appendChild(inp);
  return wrap;
}
"""

ENGLISH_MAP_JS = COMMON_ENGLISH_JS + r"""
var EM_DATA=null,EM_SEL=null,EM_TASKS=[],EM_QUIZ=null,EM_ANS={},EM_IDX=0,EM_PLAY={};
var EM_BOX=el('div',{class:'ma-wrap'}),EM_TOP=el('div'),EM_SUM=el('div'),EM_DET=el('div',{class:'ma-detail-dock'}),EM_DOMS=el('div'),EM_QBOX=el('div'),EM_NOTE=el('div',{class:'ma-notice'});
root.textContent='';
root.appendChild(EM_BOX);
EM_BOX.appendChild(EM_TOP);EM_BOX.appendChild(EM_NOTE);EM_BOX.appendChild(EM_SUM);EM_BOX.appendChild(EM_DOMS);EM_BOX.appendChild(EM_DET);EM_BOX.appendChild(EM_QBOX);

function emHasTask(nodeKey){
  var i;
  for(i=0;i<EM_TASKS.length;i++){
    if(EM_TASKS[i].taskKind==='map_node'&&EM_TASKS[i].targetKey===nodeKey)return true;
  }
  return false;
}
function emScrollToNode(key){
  var elBtn=EM_DOMS&&EM_DOMS.querySelector('[data-node="'+key+'"]');
  if(elBtn&&elBtn.scrollIntoView)elBtn.scrollIntoView({behavior:'smooth',block:'center'});
}
function emFocusNode(key){
  if(!EM_DATA||!EM_DATA.nodes)return;
  var hit=EM_DATA.nodes.filter(function(x){return x.key===key})[0];
  if(!hit)return;
  EM_SEL=hit;
  emRenderDetail();
  emRenderMapNodesSel();
  emScrollToNode(hit.key);
}
function emNotice(t,warn){
  EM_NOTE.className='ma-notice'+(t?(' show '+(warn?'warn':'info')):'');
  EM_NOTE.textContent=t||'';
}
function emRenderMap(){
  eaStopAudio();
  EM_QBOX.textContent='';
  var d=EM_DATA,s=d.summary;
  var revCnt=s.reviewDueCount||0;
  EM_TOP.textContent='';EM_TOP.appendChild(eaTopbar('map',d.points));
  var pct=s.totalNodes?Math.round(s.litNodes/s.totalNodes*100):0;
  EM_SUM.textContent='';
  EM_SUM.appendChild(el('div',{class:'ma-card'},
    el('div',{class:'ma-sum-top'},
      el('div',{},
        el('div',{class:'ma-eyebrow',text:'小学五年级 · 通用英语知识地图'}),
        el('h2',{class:'ma-h1',text:'英语知识地图'}),
        el('p',{class:'ma-sub',text:'按语音、词汇、语法、语篇四大知识点域闯关，每节点 5 题轻微测（不限时），答对 ≥ 80% 即点亮'})),
      el('a',{class:'ma-btn ma-btn-ghost ma-btn-sm',href:'/v1/english-sprints',text:'去听说读写专项 ›'})),
    el('div',{class:'ma-sum-meta'},
      el('span',{},'已点亮 ',el('b',{text:s.litNodes+'/'+s.totalNodes}),'（'+pct+'%）'),
      el('span',{},'精通 ',el('b',{text:String(s.masteredNodes)})),
      el('span',{},'总星数 ',el('b',{text:s.totalStars+'/'+s.maxStars})),
      revCnt>0?el('span',{style:'color:#b45309;font-weight:700'},'待温习 ',el('b',{style:'color:#b45309',text:String(revCnt)}),' 个'):null,
      s.repairNodes?el('span',{style:'color:var(--ma-brand);font-weight:700'},'待修补 ',el('b',{text:String(s.repairNodes)})):null),
    el('div',{class:'ma-prog-track'},el('div',{class:'ma-prog-fill',style:'width:'+pct+'%'}))));
  var banner=eaRenderTaskBanner(EM_TASKS,function(t){
    if(t.taskKind==='map_node'){emFocusNode(t.targetKey)}
    else{location.href='/v1/english-sprints#sprint='+encodeURIComponent(t.targetKey)}
  });
  if(banner)EM_SUM.appendChild(banner);
  var tipText=revCnt>0
    ?('你有 '+revCnt+' 个已点亮的英语考点快遗忘了，先点琥珀色「需温习」节点做 5 题保鲜吧！'+(s.repairNodes?' 另外还有 '+s.repairNodes+' 个标红待修补考点也别忘了哦！':''))
    :(s.repairNodes
      ?('你有 '+s.repairNodes+' 个标红的英语薄弱点，建议先回地图做一次 5 题轻微测把它修补掉，立刻得 +2 积分！')
      :(s.litNodes===0?'欢迎来到英语知识地图！这里不限教材版本、不设压迫倒计时，选一个你喜欢的知识点点亮第一颗星吧！'
        :'已经点亮 '+s.litNodes+' 个英语节点啦！把每个节点冲到三星精通，再结合听说读写专项效果更棒！'));
  EM_SUM.appendChild(eaHelperTip(tipText,'长缨助手 · 英语闯关建议'));

  EM_DOMS.textContent='';
  var grid=el('div',{class:'ma-domains'});
  var domSub={
    phonics:'开闭音节、元音/辅音组合与自然拼读',
    vocab:'人物、饮食、星期活动与居家自然高频词',
    grammar:'be 动词、单复数、一般现在时与 There be',
    reading:'日常交际问答、特殊疑问句与短文完形'
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
      var isRev=!!n.reviewDue;
      var hasT=emHasTask(n.key);
      var cls='ma-node st-'+n.state+(n.needsRepair?' repair':'')+(isRev?' review-due':'')+(EM_SEL&&EM_SEL.key===n.key?' sel':'');
      var tagCls=n.needsRepair?'repair':n.state;
      var tagTxt=n.needsRepair?'待修补':(n.stars?eaStars(n.stars)+' '+n.stateLabel:n.stateLabel);
      var rightTags=el('span',{class:'ma-node-right'},
        hasT?el('span',{class:'ma-task-badge',text:'老师任务'}):null,
        isRev?el('span',{class:'ma-tag review-due',text:'需温习'}):null,
        el('span',{class:'ma-tag '+tagCls,text:tagTxt}));
      var btn=el('button',{type:'button',class:cls,'data-node':n.key},
        el('span',{class:'ma-node-left'},
          el('span',{class:'ma-node-key',text:n.key}),
          el('span',{class:'ma-node-name',text:n.name})),
        rightTags);
      btn.onclick=function(){EM_SEL=n;emRenderDetail();emRenderMapNodesSel()};
      list.appendChild(btn);
    });
    card.appendChild(list);
    grid.appendChild(card);
  });
  EM_DOMS.appendChild(grid);
  emRenderDetail();
}
function emRenderMapNodesSel(){
  var all=EM_DOMS.querySelectorAll('.ma-node');
  for(var i=0;i<all.length;i++){
    var k=all[i].querySelector('.ma-node-key');
    if(k&&EM_SEL&&k.textContent===EM_SEL.key)all[i].classList.add('sel');
    else all[i].classList.remove('sel');
  }
}
function emRenderDetail(){
  EM_DET.textContent='';
  if(!EM_SEL)return;
  var n=EM_SEL;
  var isRev=!!n.reviewDue;
  var closeBtn=el('button',{type:'button',class:'ma-detail-close','aria-label':'收起详情',text:'× 收起',onclick:function(){
    EM_SEL=null;EM_DET.textContent='';emRenderMapNodesSel();
  }});
  var go=el('button',{type:'button',class:'ma-btn ma-btn-primary',text:n.needsRepair?'开始修补微测（5 题）':(isRev?'温习 5 题保鲜':(n.state==='unexplored'?'开始点亮微测（5 题）':'再练一次冲三星'))});
  go.onclick=function(){emStartQuiz(n)};
  EM_DET.appendChild(el('div',{class:'ma-card ma-detail'},
    closeBtn,
    el('div',{class:'ma-detail-info'},
      el('div',{class:'ma-row',style:'margin-bottom:4px'},
        el('div',{class:'ma-eyebrow',style:'margin:0',text:'当前选中 · '+n.key}),
        emHasTask(n.key)?el('span',{class:'ma-task-badge',text:'老师任务'}):null,
        isRev?el('span',{class:'ma-tag review-due',text:'需温习'}):null),
      el('h3',{text:n.icon+' '+n.name}),
      el('p',{class:'ma-muted',text:'状态：'+n.stateLabel+(n.stars?'（'+eaStars(n.stars)+'）':'')+' · 最高正确率 '+n.bestQuizRate+'%'+(isRev?(' · 已 '+(n.daysSincePractice||0)+' 天未练习，建议温习保鲜'):' · 含听音/拼块/选词轻辅助交互')})),
    go));
}
function emStartQuiz(n){
  emNotice('正在准备 '+n.key+' 微测…');
  api('/student/english-star-map/nodes/'+encodeURIComponent(n.key)+'/quiz',{method:'POST'}).then(function(q){
    emNotice('');
    EM_QUIZ=q;EM_ANS={};EM_IDX=0;EM_PLAY={};
    EM_SUM.textContent='';EM_DET.textContent='';EM_DOMS.textContent='';
    emRenderQuiz();
  }).catch(function(e){emNotice(e.message,true)});
}
function emAnswered(a){return a&&((a.selected_index!==undefined&&a.selected_index!==null)||String(a.text_answer||'').trim().length>0)}
function emRenderQuiz(){
  eaStopAudio();
  EM_QBOX.textContent='';
  var qd=EM_QUIZ,qs=qd.questions,q=qs[EM_IDX];
  var ansObj=EM_ANS[q.id]||(EM_ANS[q.id]={});
  var doneCnt=0;
  qs.forEach(function(it){if(emAnswered(EM_ANS[it.id]))doneCnt++});

  var hud=el('div',{class:'ma-hud'},
    el('div',{class:'ma-hud-top'},
      el('div',{},el('b',{text:qd.node.key+' '+qd.node.name}),el('span',{class:'ma-muted',style:'margin-left:8px',text:'5 题轻微测（不限时 · 80% 即点亮）'})),
      el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'退出返回地图',onclick:function(){EM_QUIZ=null;emLoad()}})));
  var sheet=el('div',{class:'ma-sheet'});
  qs.forEach(function(it,i){
    var b=el('button',{type:'button',class:'ma-dot'+(i===EM_IDX?' cur':(emAnswered(EM_ANS[it.id])?' done':'')),text:String(i+1)});
    b.onclick=function(){EM_IDX=i;emRenderQuiz()};
    sheet.appendChild(b);
  });

  var qCard=el('div',{class:'ma-q-card'},
    el('div',{class:'ma-q-meta'},
      el('span',{text:'第 '+(EM_IDX+1)+' / '+qs.length+' 题 · '+q.typeLabel+'（'+q.levelLabel+'）'}),
      el('span',{text:'已完成 '+doneCnt+'/'+qs.length})));
  qCard.appendChild(eaRenderQuestionBody(q,ansObj,function(silent){if(!silent)emRenderQuiz()}, {maxPlays:0,allowSlow:true,playState:EM_PLAY}));
  qCard.appendChild(eaHelperTip(eaQuestionHint(q),'长缨助手 · 解题提示'));

  var prevBtn=el('button',{type:'button',class:'ma-btn ma-btn-ghost',text:'上一题'});
  prevBtn.disabled=(EM_IDX===0);
  prevBtn.onclick=function(){EM_IDX--;emRenderQuiz()};
  var isLast=(EM_IDX===qs.length-1);
  var nextBtn=el('button',{type:'button',class:'ma-btn '+(isLast?'ma-btn-ok':'ma-btn-primary'),text:isLast?'提交微测':'下一题'});
  nextBtn.onclick=function(){
    if(!isLast){EM_IDX++;emRenderQuiz();return}
    emSubmitQuiz();
  };
  qCard.appendChild(el('div',{class:'ma-foot'},prevBtn,nextBtn));

  EM_QBOX.appendChild(hud);EM_QBOX.appendChild(sheet);EM_QBOX.appendChild(qCard);
}
function emSubmitQuiz(){
  eaStopAudio();
  var qd=EM_QUIZ,arr=[];
  qd.questions.forEach(function(q){
    var a=EM_ANS[q.id]||{};
    arr.push({question_id:q.id,selected_index:(a.selected_index===undefined?null:a.selected_index),text_answer:String(a.text_answer||'')});
  });
  emNotice('正在批改…');
  api('/student/english-star-map/nodes/'+encodeURIComponent(qd.node.key)+'/quiz/submit',{
    method:'POST',
    json:{quiz_id:qd.quizId,answers:arr}
  }).then(function(res){
    emNotice('');
    EM_QUIZ=null;
    EM_QBOX.textContent='';
    EM_TOP.textContent='';EM_TOP.appendChild(eaTopbar('map',res.points));
    var head=el('div',{class:'ma-card ma-res-head'},
      el('div',{class:'ma-res-tier',text:res.passed?('🎉 点亮成功 · '+res.nodeState.stateLabel+(res.nodeState.stars?' '+eaStars(res.nodeState.stars):'')):'继续加油 · 差一点就点亮啦'}),
      el('h2',{class:'ma-h1',text:res.nodeKey+' '+res.nodeName+'：答对 '+res.correct+' / '+res.total+' 题（'+res.ratePct+'%）'}),
      res.repaired?el('p',{class:'ma-sub',style:'color:var(--ma-ok);font-weight:700',text:'已成功消除该节点的「待修补」红标！'}):null,
      eaPointsGain(res.pointsAwarded,res.points),
      el('div',{class:'ma-row',style:'justify-content:center;margin-top:14px'},
        el('button',{type:'button',class:'ma-btn ma-btn-primary',text:'返回英语知识地图',onclick:function(){emLoad()}}),
        el('a',{class:'ma-btn ma-btn-ghost',href:'/v1/english-sprints',text:'去挑战听说读写专项'})));
    EM_QBOX.appendChild(head);
    var rev=el('div',{class:'ma-card'},el('h3',{text:'逐题解析'}));
    res.details.forEach(function(d,i){
      rev.appendChild(el('div',{class:'ma-rev '+(d.correct?'ok':'bad')},
        el('b',{text:(i+1)+'. ['+d.typeLabel+'] '+(d.correct?'✓ 正确':'✗ 错题')+' · 参考答案：'+d.answer}),
        el('div',{text:d.explanation})));
    });
    EM_QBOX.appendChild(rev);
  }).catch(function(e){emNotice(e.message,true)});
}
function emLoad(){
  Promise.all([api('/student/english-star-map'),eaFetchTasks('英语')]).then(function(res){
    var d=res[0];
    EM_DATA=d;EM_TASKS=res[1]||[];
    var hit=null;
    var want=/[#&]node=([^&]+)/.exec(location.hash||'');
    if(want){
      var key=decodeURIComponent(want[1]);
      d.nodes.forEach(function(n){if(n.key===key){EM_SEL=n;hit=n}});
    }
    if(!EM_SEL&&d.nodes.length)EM_SEL=d.nodes[0];
    emRenderMap();
    if(hit)emScrollToNode(hit.key);
  }).catch(function(e){emNotice(e.message,true)});
}
eaBoot(emLoad);
"""

ENGLISH_SPRINTS_JS = COMMON_ENGLISH_JS + r"""
var ES_DATA=null,ES_TASKS=[],ES_ATT=null,ES_ANS={},ES_IDX=0,ES_PLAY={},ES_TIMER=null,ES_LEFT=0,ES_QLEFT=0,ES_SUBMITTING=false;
var ES_BOX=el('div',{class:'ma-wrap'}),ES_TOP=el('div'),ES_NOTE=el('div',{class:'ma-notice'}),ES_BODY=el('div');
root.textContent='';
root.appendChild(ES_BOX);
ES_BOX.appendChild(ES_TOP);ES_BOX.appendChild(ES_NOTE);ES_BOX.appendChild(ES_BODY);

function esNotice(t,warn){
  ES_NOTE.className='ma-notice'+(t?(' show '+(warn?'warn':'info')):'');
  ES_NOTE.textContent=t||'';
}
function esStopTimer(){if(ES_TIMER){clearInterval(ES_TIMER);ES_TIMER=null}}
function esAnswered(a){return a&&((a.selected_index!==undefined&&a.selected_index!==null)||String(a.text_answer||'').trim().length>0)}

function esRenderLobby(){
  esStopTimer();eaStopAudio();
  var d=ES_DATA;
  ES_TOP.textContent='';ES_TOP.appendChild(eaTopbar('sprints',d.points));
  ES_BODY.textContent='';
  ES_BODY.appendChild(el('div',{class:'ma-card'},
    el('div',{class:'ma-eyebrow',text:'小学五年级 · 听说读写四大能力应试专项'}),
    el('h2',{class:'ma-h1',text:'英语应试专项'}),
    el('p',{class:'ma-sub',text:'听 / 说专项采用「单题限时」还原考场节奏；读 / 写专项采用「整体倒计时」支持回看检查。达标（L2+）自动反哺点亮知识地图！'})));
  var banner=eaRenderTaskBanner(ES_TASKS,function(t){
    if(t.taskKind==='sprint'){esStart(t.targetKey)}
    else{location.href='/v1/english-star-map#node='+encodeURIComponent(t.targetKey)}
  });
  if(banner)ES_BODY.appendChild(banner);
  ES_BODY.appendChild(eaHelperTip('四个专项按「听、说、读、写」独立开考，无需先刷完地图！考完会自动把薄弱考点标红到地图，方便精准修补。','长缨助手 · 备考提示'));

  var grid=el('div',{class:'ma-sprints'});
  d.sprints.forEach(function(sp){
    var hasSpTask=ES_TASKS.some(function(t){return t.taskKind==='sprint'&&t.targetKey===sp.slug});
    var tierTxt=sp.bestTier?(sp.bestTier.badge+' '+sp.bestTier.code+' '+sp.bestTier.name):'尚未挑战';
    var timeTag=sp.timingMode==='per_question'
      ?('单题限时 '+sp.perQuestionSec+' 秒/题')
      :('整体倒计时 '+Math.round(sp.timeLimitSec/60)+' 分钟');
    var go=el('button',{type:'button',class:'ma-btn ma-btn-primary',text:sp.attempts?'再次冲刺段位':'立即开考'});
    go.onclick=function(){esStart(sp.slug)};
    grid.appendChild(el('div',{class:'ma-sprint'},
      el('div',{},
        el('div',{class:'ma-row',style:'margin-bottom:6px'},
          el('span',{class:'ea-ab ea-ab-'+sp.ability,text:sp.abilityLabel}),
          el('h3',{style:'margin:0',text:sp.title})),
        el('p',{class:'ma-sub',text:sp.subtitle}),
        el('div',{class:'ma-sprint-tags'},
          hasSpTask?el('span',{class:'ma-task-badge',text:'老师任务'}):null,
          el('span',{class:'ma-pill',text:timeTag}),
          el('span',{class:'ma-pill',text:sp.questionCount+' 题多题型'}),
          sp.maxPlays?el('span',{class:'ma-pill',text:'每题限播 '+sp.maxPlays+' 遍'}):null,
          el('span',{class:'ma-pill',text:'最高：'+tierTxt}))),
      go));
  });
  ES_BODY.appendChild(grid);
}

function esStart(slug){
  esNotice('正在组卷开考…');
  api('/student/english-sprints/'+encodeURIComponent(slug)+'/start',{method:'POST'}).then(function(att){
    esNotice('');
    ES_ATT=att;ES_ANS={};ES_IDX=0;ES_PLAY={};ES_SUBMITTING=false;
    ES_LEFT=att.timeLimitSec;
    ES_QLEFT=att.perQuestionSec||20;
    esRenderExam();
    esStartClock();
  }).catch(function(e){esNotice(e.message,true)});
}

function esStartClock(){
  esStopTimer();
  var isPerQ=(ES_ATT&&ES_ATT.timingMode==='per_question');
  ES_TIMER=setInterval(function(){
    if(!ES_ATT||ES_SUBMITTING)return;
    ES_LEFT=Math.max(0,ES_LEFT-1);
    if(isPerQ){
      ES_QLEFT=Math.max(0,ES_QLEFT-1);
      var qClk=document.getElementById('es-qclock');
      var qBar=document.getElementById('es-qbar');
      if(qClk)qClk.textContent='本题剩余 '+eaClockText(ES_QLEFT);
      if(qBar&&ES_ATT.perQuestionSec){
        qBar.style.width=Math.max(0,Math.round(ES_QLEFT/ES_ATT.perQuestionSec*100))+'%';
      }
      if(ES_QLEFT<=0){
        if(ES_IDX<ES_ATT.questions.length-1){
          ES_IDX++;
          ES_QLEFT=ES_ATT.perQuestionSec||20;
          esRenderExam();
        }else{
          esSubmit(true);
        }
        return;
      }
    }
    var clk=document.getElementById('es-clock');
    var hud=document.getElementById('es-hud');
    if(clk)clk.textContent=(isPerQ?'总剩余 ':'倒计时 ')+eaClockText(ES_LEFT);
    if(hud&&(isPerQ?ES_QLEFT<=5:ES_LEFT<=60))hud.classList.add('urgent');
    if(ES_LEFT<=0){esSubmit(true)}
  },1000);
}

function esRenderExam(){
  eaStopAudio();
  ES_BODY.textContent='';
  var att=ES_ATT,qs=att.questions,q=qs[ES_IDX];
  var isPerQ=(att.timingMode==='per_question');
  var ansObj=ES_ANS[q.id]||(ES_ANS[q.id]={});
  var doneCnt=0;
  qs.forEach(function(it){if(esAnswered(ES_ANS[it.id]))doneCnt++});

  var hud=el('div',{id:'es-hud',class:'ma-hud'+((isPerQ?ES_QLEFT<=5:ES_LEFT<=60)?' urgent':'')},
    el('div',{class:'ma-hud-top'},
      el('div',{},
        el('b',{text:att.sprint.title}),
        el('span',{class:'ma-muted',style:'margin-left:8px',text:'第 '+(ES_IDX+1)+'/'+qs.length+' 题 · 已答 '+doneCnt+'/'+qs.length})),
      el('div',{class:'ma-row'},
        isPerQ?el('span',{id:'es-qclock',class:'ma-clock',text:'本题剩余 '+eaClockText(ES_QLEFT)}):null,
        el('span',{id:'es-clock',class:isPerQ?'ma-pill':'ma-clock',text:(isPerQ?'总剩余 ':'倒计时 ')+eaClockText(ES_LEFT)}))));
  if(isPerQ&&att.perQuestionSec){
    var pct=Math.max(0,Math.round(ES_QLEFT/att.perQuestionSec*100));
    hud.appendChild(el('div',{class:'ea-qbar-track'},el('div',{id:'es-qbar',class:'ea-qbar-fill',style:'width:'+pct+'%'})));
  }
  ES_BODY.appendChild(hud);

  if(!isPerQ){
    var sheet=el('div',{class:'ma-sheet'});
    qs.forEach(function(it,i){
      var b=el('button',{type:'button',class:'ma-dot'+(i===ES_IDX?' cur':(esAnswered(ES_ANS[it.id])?' done':'')),text:String(i+1)});
      b.onclick=function(){ES_IDX=i;esRenderExam()};
      sheet.appendChild(b);
    });
    ES_BODY.appendChild(sheet);
  }

  var qCard=el('div',{class:'ma-q-card'},
    el('div',{class:'ma-q-meta'},
      el('span',{text:'第 '+(ES_IDX+1)+' 题 · '+q.typeLabel+'（'+q.marks+' 分）'}),
      el('span',{text:isPerQ?'单题限时模式（超时自动切题）':'整体限时模式（可自由回看）'})));
  qCard.appendChild(eaRenderQuestionBody(q,ansObj,function(silent){if(!silent)esRenderExam()}, {
    maxPlays:att.maxPlays||0,
    allowSlow:false,
    playState:ES_PLAY
  }));
  qCard.appendChild(eaHelperTip(eaQuestionHint(q),'长缨助手 · 考场提示'));

  var leftBtn=isPerQ
    ?el('span',{class:'ma-muted',text:'单题限时模式不可回退上一题'})
    :el('button',{type:'button',class:'ma-btn ma-btn-ghost',text:'上一题'});
  if(!isPerQ){
    leftBtn.disabled=(ES_IDX===0);
    leftBtn.onclick=function(){ES_IDX--;esRenderExam()};
  }
  var isLast=(ES_IDX===qs.length-1);
  var nextBtn=el('button',{type:'button',class:'ma-btn '+(isLast?'ma-btn-ok':'ma-btn-primary'),text:isLast?'交卷评分':'下一题'});
  nextBtn.onclick=function(){
    if(!isLast){
      ES_IDX++;
      if(isPerQ)ES_QLEFT=att.perQuestionSec||20;
      esRenderExam();
      return;
    }
    esSubmit(false);
  };
  qCard.appendChild(el('div',{class:'ma-foot'},leftBtn,nextBtn));
  ES_BODY.appendChild(qCard);
}

function esSubmit(autoSub){
  if(ES_SUBMITTING||!ES_ATT)return;
  ES_SUBMITTING=true;
  esStopTimer();eaStopAudio();
  var att=ES_ATT,arr=[];
  att.questions.forEach(function(q){
    var a=ES_ANS[q.id]||{};
    arr.push({question_id:q.id,selected_index:(a.selected_index===undefined?null:a.selected_index),text_answer:String(a.text_answer||'')});
  });
  esNotice(autoSub?'时间到，正在自动交卷评分…':'正在交卷评分…');
  api('/student/english-sprints/attempts/'+att.attemptId+'/submit',{
    method:'POST',
    json:{answers:arr,auto_submitted:!!autoSub}
  }).then(function(res){
    esNotice('');
    ES_ATT=null;ES_SUBMITTING=false;
    ES_TOP.textContent='';ES_TOP.appendChild(eaTopbar('sprints',res.points));
    ES_BODY.textContent='';
    var head=el('div',{class:'ma-card ma-res-head'},
      el('div',{class:'ma-res-tier',text:res.tier.badge+' '+res.tier.code+' '+res.tier.name}),
      el('h2',{class:'ma-h1',text:'得分 '+res.earnedMarks+' / '+res.totalMarks+'（'+res.scoreRate+'%）'}),
      el('p',{class:'ma-sub',text:'答对 '+res.correctCount+'/'+res.questionCount+' 题 · 用时 '+eaClockText(res.elapsedSec)+(res.autoSubmitted?'（时间到自动交卷）':'')}),
      eaPointsGain(res.pointsAwarded,res.points),
      el('div',{class:'ma-row',style:'justify-content:center;margin-top:14px'},
        el('button',{type:'button',class:'ma-btn ma-btn-primary',text:'返回听说读写专项',onclick:function(){esLoad()}}),
        el('a',{class:'ma-btn ma-btn-ghost',href:'/v1/english-star-map',text:'查看英语知识地图'})));
    ES_BODY.appendChild(head);

    var resTip=res.topLosses&&res.topLosses.length
      ?('已自动把本次失分最多的 '+res.topLosses.length+' 个英语考点标红在知识地图中，点击下方「去地图修补」即可 5 题定向消除红标！')
      :'本次表现非常稳健！全对的知识点已经同步反哺点亮你的英语知识地图啦！';
    ES_BODY.appendChild(eaHelperTip(resTip,'长缨助手 · 考后复盘'));

    if(res.mapChanges&&(res.mapChanges.lit.length||res.mapChanges.flagged.length)){
      var mc=el('div',{class:'ma-card'},el('h3',{text:'知识地图双向联动更新'}));
      if(res.mapChanges.lit.length){
        mc.appendChild(el('p',{class:'ma-sub',style:'color:var(--ma-ok);font-weight:700;margin-bottom:8px',
          text:'本次专项反哺新点亮：'+res.mapChanges.lit.map(function(x){return x.key+' '+x.name}).join('、')}));
      }
      res.mapChanges.flagged.forEach(function(x){
        mc.appendChild(el('div',{class:'ma-loss-row'},
          el('span',{text:'待修补红标：'+x.key+' '+x.name}),
          el('a',{class:'ma-btn ma-btn-primary ma-btn-sm',href:'/v1/english-star-map#node='+encodeURIComponent(x.key),text:'去地图修补 ›'})));
      });
      ES_BODY.appendChild(mc);
    }

    var rev=el('div',{class:'ma-card'},el('h3',{text:'逐题解析'}));
    res.details.forEach(function(d,i){
      rev.appendChild(el('div',{class:'ma-rev '+(d.correct?'ok':'bad')},
        el('b',{text:(i+1)+'. ['+d.typeLabel+'] '+(d.correct?'✓ 正确':'✗ 错题')+' · 参考答案：'+d.answer}),
        el('div',{text:d.explanation})));
    });
    ES_BODY.appendChild(rev);
  }).catch(function(e){ES_SUBMITTING=false;esNotice(e.message,true)});
}

function esLoad(){
  Promise.all([api('/student/english-sprints'),eaFetchTasks('英语')]).then(function(res){
    ES_DATA=res[0];ES_TASKS=res[1]||[];
    esRenderLobby();
  }).catch(function(e){esNotice(e.message,true)});
}
eaBoot(esLoad);
"""

HELPER_AVATAR_JS = 'window.__CY_HELPER_AVATAR__="data:image/png;base64,' + AVATAR_PNG_B64 + '";\n'


def english_star_map_page_html() -> str:
    return _page("英语知识地图", HELPER_AVATAR_JS + ARENA_ROLE_HUB_JS + ENGLISH_MAP_JS, True).replace(
        "</head>", ARENA_CSS + ENGLISH_EXTRA_CSS + "</head>", 1
    )


def english_sprints_page_html() -> str:
    return _page("英语应试专项", HELPER_AVATAR_JS + ARENA_ROLE_HUB_JS + ENGLISH_SPRINTS_JS, True).replace(
        "</head>", ARENA_CSS + ENGLISH_EXTRA_CSS + "</head>", 1
    )


__all__ = ["english_sprints_page_html", "english_star_map_page_html"]
