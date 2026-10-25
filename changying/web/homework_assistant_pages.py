"""Page for the after-school homework assistant (static HTML, no server data inlined).

The entry points live in the existing screens: the teacher 全部功能 list (v1_workspace_tabs) and the top of the
student 作业 page (v1_classic_unified_top)."""

from __future__ import annotations

from changying.web.classroom_window_handoff import PAGE_AUTH_JS

PAGE_CSS = r"""
:root{--bg:#f4f6fb;--card:#fff;--ink:#1c2333;--muted:#667085;--line:#d9deea;--brand:#1f6feb;--warn:#b54708;--warnbg:#fff4e5;--ok:#067647;--bad:#b42318}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 18px;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
header h1{margin:0;font-size:20px}header a{color:var(--brand);text-decoration:none;font-weight:600}
main{max-width:980px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:0 0 14px}
.card h2{margin:0 0 10px;font-size:18px}.muted{color:var(--muted);font-size:15px}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
button,.btn{font:inherit;min-height:46px;padding:8px 16px;border-radius:10px;border:1px solid var(--line);background:#fff;color:var(--ink);cursor:pointer}
button.primary{background:var(--brand);border-color:var(--brand);color:#fff;font-weight:600}
button.on{background:#e8f0ff;border-color:var(--brand);color:var(--brand);font-weight:600}
button:disabled{opacity:.55;cursor:default}
textarea,input[type=text]{width:100%;font:inherit;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:#fff}
textarea{min-height:150px;resize:vertical}
select{font:inherit;min-height:46px;padding:6px 10px;border-radius:10px;border:1px solid var(--line);background:#fff}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:8px 0}
.notice{border-radius:10px;padding:10px 14px;margin:10px 0}.notice.error{background:#fef3f2;color:var(--bad)}.notice.ok{background:#ecfdf3;color:var(--ok)}.notice.warn{background:var(--warnbg);color:var(--warn);font-weight:600}
.item{display:flex;gap:12px;align-items:flex-start;padding:12px 0;border-top:1px solid var(--line)}.item:first-child{border-top:0}
.item input[type=checkbox]{width:26px;height:26px;margin-top:3px;flex:none}
.item.done .t{text-decoration:line-through;color:var(--muted)}.t b{display:block}
.edit{display:grid;grid-template-columns:90px 1fr 100px 1fr 46px;gap:8px;margin:6px 0}
@media(max-width:720px){.edit{grid-template-columns:1fr 1fr}.edit .wide{grid-column:1/-1}}
.chips{display:flex;gap:8px;flex-wrap:wrap}.chips label{display:flex;gap:6px;align-items:center;padding:8px 12px;border:1px solid var(--line);border-radius:999px;background:#fff}
.tag{display:inline-block;padding:2px 10px;border-radius:999px;background:#eef2ff;color:#3538cd;font-size:14px}
.bar{height:10px;background:#e4e7ec;border-radius:99px;overflow:hidden;margin-top:6px}.bar i{display:block;height:100%;background:var(--brand)}
hr{border:0;border-top:1px solid var(--line);margin:14px 0}
"""

PAGE_JS = r"""
__PAGE_AUTH__
var el=function(tag,attrs){
  var n=document.createElement(tag);
  Object.keys(attrs||{}).forEach(function(k){
    if(k==='class')n.className=attrs[k];
    else if(k==='text')n.textContent=attrs[k];
    else if(k.slice(0,2)==='on')n.addEventListener(k.slice(2),attrs[k]);
    else if(attrs[k]===true)n.setAttribute(k,'');
    else if(attrs[k]!==false&&attrs[k]!=null)n.setAttribute(k,attrs[k]);
  });
  for(var i=2;i<arguments.length;i++){
    var c=arguments[i];if(c==null)continue;
    n.appendChild(typeof c==='string'?document.createTextNode(c):c);
  }
  return n;
};
var root=document.getElementById('app'),TOKEN='',ME=null,CONFIG={visionEnabled:false};
function api(path,opts){
  opts=opts||{};opts.headers=Object.assign({Authorization:'Bearer '+TOKEN},opts.headers||{});opts.cache='no-store';
  if(opts.json!==undefined){opts.method=opts.method||'POST';opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(opts.json);delete opts.json}
  return fetch(path,opts).then(function(r){
    return r.json().catch(function(){return {}}).then(function(d){
      if(!r.ok){var e=new Error((d&&d.detail&&typeof d.detail==='string'&&d.detail)||('请求失败（'+r.status+'）'));e.status=r.status;throw e}
      return d;
    });
  });
}
function notice(kind,text){return el('div',{class:'notice '+kind,text:text})}
function shrink(file,maxEdge){
  return new Promise(function(resolve,reject){
    var url=URL.createObjectURL(file),img=new Image();
    img.onload=function(){
      var s=Math.min(1,maxEdge/Math.max(img.width,img.height)),c=document.createElement('canvas');
      c.width=Math.max(1,Math.round(img.width*s));c.height=Math.max(1,Math.round(img.height*s));
      c.getContext('2d').drawImage(img,0,0,c.width,c.height);URL.revokeObjectURL(url);
      c.toBlob(function(b){b?resolve(b):reject(new Error('图片处理失败'))},'image/jpeg',0.88);
    };
    img.onerror=function(){URL.revokeObjectURL(url);reject(new Error('无法读取这张图片，请换一张'))};
    img.src=url;
  });
}
function frame(title,sub){
  root.textContent='';
  root.appendChild(el('div',{class:'card'},el('h2',{text:title}),sub?el('div',{class:'muted',text:sub}):null));
}

/* ---------------------------------------------------------------- student */
function studentView(){
  root.textContent='';
  var list=el('div',{id:'today'});
  root.appendChild(el('div',{class:'card'},el('h2',{text:'今日作业'}),el('div',{class:'muted',text:'做完一项，就在前面打勾。'}),list));
  __STUDENT_EXTRA__
  function paint(rows){
    list.textContent='';
    if(!rows.length){list.appendChild(el('div',{class:'muted',text:'老师还没有布置今天的作业。'}));return}
    rows.forEach(function(n){
      list.appendChild(el('div',{class:'muted',text:(n.groupLabel?n.groupLabel+' · ':'')+'发布于 '+n.publishedAt}));
      n.items.forEach(function(it){
        var box=el('input',{type:'checkbox',checked:it.done});
        var row=el('label',{class:'item'+(it.done?' done':'')},box,el('span',{class:'t'},
          el('b',{text:(it.subject?it.subject+'：':'')+it.content}),
          el('span',{class:'muted',text:[it.page,it.requirement].filter(Boolean).join(' · ')})));
        box.addEventListener('change',function(){
          api('/student/homework/items/'+n.noticeID+'/'+it.seq+'/done',{json:{done:box.checked}}).then(function(){
            it.done=box.checked;row.className='item'+(it.done?' done':'');
          }).catch(function(e){box.checked=!box.checked;alert(e.message)});
        });
        list.appendChild(row);
      });
    });
  }
  api('/student/homework/today').then(paint).catch(function(e){list.appendChild(notice('error',e.message))});
}

/* ---------------------------------------------------------------- teacher */
function teacherView(){
  root.textContent='';
  var tabs=el('div',{class:'tabs'}),body=el('div');
  root.appendChild(tabs);root.appendChild(body);
  var views={import:importView,notices:noticesView__TEACHER_VIEWS__};
  var names={import:'导入作业通知',notices:'已发布的清单'__TEACHER_NAMES__};
  function show(key){
    Object.keys(names).forEach(function(k){tabs.querySelector('[data-k="'+k+'"]').className=k===key?'on':''});
    body.textContent='';views[key](body);
  }
  Object.keys(names).forEach(function(k){tabs.appendChild(el('button',{'data-k':k,text:names[k],onclick:function(){show(k)}}))});
  window.__hwShow=show;show('import');
  if(typeof helpBadge==='function')helpBadge(tabs);
}
function importView(body){
  var text=el('textarea',{placeholder:'把家长转发的作业通知文字粘贴到这里'}),msg=el('div'),editor=el('div');
  var parseBtn=el('button',{class:'primary',text:'AI 解析'}),file=el('input',{type:'file',accept:'image/*',hidden:true});
  var shot=el('button',{text:'上传通知截图',onclick:function(){file.click()}});
  if(!CONFIG.visionEnabled)shot.style.display='none';
  body.appendChild(el('div',{class:'card'},el('h2',{text:'1. 粘贴通知'}),
    el('div',{class:'muted',text:'文字会发送给 AI 服务商用于整理成清单；手机号等会先被隐藏。'}),text,
    el('div',{class:'row'},parseBtn,shot,file,el('button',{text:'直接手动录入',onclick:function(){drawEditor({id:0,groupLabel:'',items:[{seq:1,subject:'',content:'',page:'',requirement:''}]})}})),msg));
  body.appendChild(editor);
  file.addEventListener('change',function(){
    var f=file.files&&file.files[0];if(!f)return;
    msg.textContent='';msg.appendChild(notice('ok','正在识别截图…'));shot.disabled=true;
    shrink(f,1800).then(function(blob){return api('/teacher/homework/parse-image',{method:'POST',body:blob,headers:{'Content-Type':'image/jpeg'}})})
      .then(function(d){text.value=d.text;msg.textContent='';msg.appendChild(notice('ok','已识别，请检查文字，需要的话直接修改，再点“AI 解析”。'))})
      .catch(function(e){msg.textContent='';msg.appendChild(notice('error',e.message))}).then(function(){shot.disabled=false;file.value=''});
  });
  parseBtn.addEventListener('click',function(){
    msg.textContent='';parseBtn.disabled=true;msg.appendChild(notice('ok','AI 正在整理…'));
    api('/teacher/homework/parse',{json:{text:text.value}}).then(function(n){msg.textContent='';drawEditor(n)})
      .catch(function(e){msg.textContent='';msg.appendChild(notice('error',e.message))}).then(function(){parseBtn.disabled=false});
  });
  function drawEditor(n){
    editor.textContent='';
    var label=el('input',{type:'text',value:n.groupLabel||'',placeholder:'学校 + 班级（选填，仅作标注）'}),rows=el('div'),state={id:n.id,items:n.items.slice()};
    function paintRows(){
      rows.textContent='';
      state.items.forEach(function(it,i){
        var f=function(k,ph,cls){return el('input',{type:'text',value:it[k]||'',placeholder:ph,class:cls||'',oninput:function(e){it[k]=e.target.value}})};
        rows.appendChild(el('div',{class:'edit'},f('subject','学科'),f('content','作业内容'),f('page','页码'),f('requirement','要求'),
          el('button',{text:'×','aria-label':'删除这一条',onclick:function(){state.items.splice(i,1);paintRows()}})));
      });
    }
    paintRows();
    var chips=el('div',{class:'chips'}),picked={},msg2=el('div');
    api('/teacher/homework/students').then(function(list){
      if(!list.length){chips.appendChild(el('div',{class:'muted',text:'你的班级里还没有学生。'}))}
      list.forEach(function(s){
        var cb=el('input',{type:'checkbox',onchange:function(){if(cb.checked)picked[s.id]=1;else delete picked[s.id]}});
        chips.appendChild(el('label',{},cb,(s.name||'学生')+(s.className?'（'+s.className+'）':'')));
      });
      chips.__all=function(on){chips.querySelectorAll('input').forEach(function(c){c.checked=on;c.dispatchEvent(new Event('change'))})};
    });
    var publish=el('button',{class:'primary',text:'确认并发布给选中的学生',onclick:function(){
      msg2.textContent='';
      var ids=Object.keys(picked).map(Number);
      if(!ids.length){msg2.appendChild(notice('error','请先选择学生'));return}
      publish.disabled=true;
      var save=state.id?api('/teacher/homework/notices/'+state.id,{method:'PUT',json:{groupLabel:label.value,items:state.items}})
                       :api('/teacher/homework/notices',{json:{groupLabel:label.value,items:state.items}});
      save.then(function(saved){state.id=saved.id;return api('/teacher/homework/notices/'+saved.id+'/publish',{json:{studentIDs:ids}})})
        .then(function(r){editor.textContent='';text.value='';msg.textContent='';msg.appendChild(notice('ok','已发布给 '+r.recipients+' 名学生。学生打开“晚托作业助手”就能看到。'))})
        .catch(function(e){msg2.appendChild(notice('error',e.message));publish.disabled=false});
    }});
    editor.appendChild(el('div',{class:'card'},el('h2',{text:'2. 检查并修改清单'}),el('div',{class:'muted',text:'AI 可能整理错，请逐条核对；确认前学生看不到。'}),label,rows,
      el('button',{text:'＋ 增加一条',onclick:function(){state.items.push({seq:state.items.length+1,subject:'',content:'',page:'',requirement:''});paintRows()}}),
      el('hr'),el('h2',{text:'3. 分配给学生'}),el('div',{class:'row'},el('button',{text:'全选',onclick:function(){chips.__all&&chips.__all(true)}}),el('button',{text:'全不选',onclick:function(){chips.__all&&chips.__all(false)}})),chips,
      el('div',{class:'row'},publish),msg2));
  }
}
function noticesView(body){
  var list=el('div');body.appendChild(el('div',{class:'card'},el('h2',{text:'已发布的清单'}),list));
  api('/teacher/homework/notices').then(function(rows){
    if(!rows.length){list.appendChild(el('div',{class:'muted',text:'还没有清单。'}));return}
    rows.forEach(function(n){
      var pct=n.totalCount?Math.round(100*n.doneCount/n.totalCount):0,detail=el('div');
      var card=el('div',{class:'card'},
        el('div',{class:'row'},el('b',{text:(n.groupLabel||'作业清单')+' · '+(n.publishedAt||n.createdAt)}),el('span',{class:'tag',text:n.status==='published'?'已发布':'草稿'})),
        el('div',{class:'muted',text:n.itemCount+' 条作业 · '+n.recipientCount+' 名学生 · 已完成 '+n.doneCount+'/'+n.totalCount}),
        el('div',{class:'bar'},el('i',{style:'width:'+pct+'%'})),detail);
      if(n.status==='published')card.appendChild(el('button',{text:'查看每个学生的完成情况',onclick:function(){
        detail.textContent='';
        api('/teacher/homework/notices/'+n.id).then(function(d){
          d.recipients.forEach(function(r){detail.appendChild(el('div',{class:'row'},el('b',{text:r.name||'学生'}),el('span',{class:'muted',text:'完成 '+r.done.length+'/'+d.items.length})))});
        }).catch(function(e){detail.appendChild(notice('error',e.message))});
      }}));
      list.appendChild(card);
    });
  }).catch(function(e){list.appendChild(notice('error',e.message))});
}
__EXTRA_FUNCS__

/* ---------------------------------------------------------------- start */
function start(){
  obtainToken().then(function(t){
    TOKEN=t;
    if(!TOKEN){frame('请先登录','请回到首页登录后，再点“晚托作业助手”。');root.appendChild(el('a',{class:'btn',href:'/v1',text:'去登录'}));return}
    return api('/session').then(function(s){
      ME=s;return api('/homework/config').catch(function(){return {visionEnabled:false}});
    }).then(function(c){
      CONFIG=c||CONFIG;
      if(ME.role==='teacher')teacherView();
      else if(ME.role==='student')studentView();
      else frame('这个功能只面向老师和学生','当前身份：'+(ME.role||'未知'));
    });
  }).catch(function(e){frame('打不开',e.message||'请稍后重试')});
}
start();
"""

PAGE_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>晚托作业助手</title>
<style>__CSS__</style></head>
<body><header><h1>晚托作业助手</h1><a href="/v1">返回首页</a></header>
<main id="app"><div class="card muted">加载中…</div></main>
<script>__JS__</script></body></html>
"""

# Follow-up pull requests extend the page by filling these slots.
PHOTO_CROP_JS = r"""

/* Let the student frame just the one question before it is sent: drag the corners, or drag inside to move. */
function cropPhoto(file){
  return new Promise(function(resolve,reject){
    var url=URL.createObjectURL(file),img=new Image();
    img.onerror=function(){URL.revokeObjectURL(url);reject(new Error('无法读取这张图片，请换一张'))};
    img.onload=function(){
      var NW=img.naturalWidth,NH=img.naturalHeight,MIN=64,sc=1,ox=0,oy=0,dw=0,dh=0,r={x:0,y:0,w:0,h:0};
      var overlay=el('div',{style:'position:fixed;inset:0;z-index:10000;background:#111;display:flex;flex-direction:column'});
      var tip=el('div',{style:'color:#fff;padding:10px 14px;font-size:15px;line-height:1.4',text:'拖动白框的四个角，只框住这一道题（拖框里面可以移动）'});
      var stage=el('div',{style:'position:relative;flex:1;min-height:0;overflow:hidden;touch-action:none;user-select:none;-webkit-user-select:none'});
      var pic=el('img',{src:url,draggable:'false',style:'position:absolute;pointer-events:none;max-width:none'});
      var box=el('div',{style:'position:absolute;border:2px solid #fff;box-sizing:border-box;box-shadow:0 0 0 9999px rgba(0,0,0,.6);cursor:move;touch-action:none'});
      ['nw','ne','sw','se'].forEach(function(k){
        var dot=el('div',{style:'width:18px;height:18px;border-radius:50%;background:#fff;box-shadow:0 0 0 2px #1f6feb'});
        box.appendChild(el('div',{'data-h':k,style:'position:absolute;width:48px;height:48px;display:flex;align-items:center;justify-content:center;touch-action:none;'+
          (k.charAt(0)==='n'?'top:-24px;':'bottom:-24px;')+(k.charAt(1)==='w'?'left:-24px;':'right:-24px;')},dot));
      });
      var bar=el('div',{style:'display:flex;gap:10px;padding:10px 14px calc(10px + env(safe-area-inset-bottom));background:#111'});
      function done(){overlay.remove();URL.revokeObjectURL(url);window.removeEventListener('resize',layout);window.removeEventListener('mousemove',move);window.removeEventListener('mouseup',end)}
      var cancel=el('button',{text:'取消',onclick:function(){done();var e=new Error('已取消');e.cancelled=true;reject(e)}});
      function out(sx,sy,sw,sh){
        var k=Math.min(1,1600/Math.max(sw,sh)),c=document.createElement('canvas');
        c.width=Math.max(1,Math.round(sw*k));c.height=Math.max(1,Math.round(sh*k));
        c.getContext('2d').drawImage(img,sx,sy,sw,sh,0,0,c.width,c.height);
        c.toBlob(function(b){done();b?resolve(b):reject(new Error('图片处理失败'))},'image/jpeg',0.88);
      }
      var whole=el('button',{text:'不裁剪，用整张',onclick:function(){out(0,0,NW,NH)}});
      var ok=el('button',{class:'primary',style:'flex:1',text:'确定，识别这一块',onclick:function(){out((r.x-ox)/sc,(r.y-oy)/sc,r.w/sc,r.h/sc)}});
      bar.appendChild(cancel);bar.appendChild(whole);bar.appendChild(ok);
      stage.appendChild(pic);stage.appendChild(box);
      overlay.appendChild(tip);overlay.appendChild(stage);overlay.appendChild(bar);document.body.appendChild(overlay);
      function paint(){
        box.style.left=r.x+'px';box.style.top=r.y+'px';box.style.width=r.w+'px';box.style.height=r.h+'px';
      }
      function layout(){
        var sw=stage.clientWidth,sh=stage.clientHeight;
        sc=Math.min(sw/NW,sh/NH);dw=NW*sc;dh=NH*sc;ox=(sw-dw)/2;oy=(sh-dh)/2;
        pic.style.width=dw+'px';pic.style.height=dh+'px';pic.style.left=ox+'px';pic.style.top=oy+'px';
        r={x:ox+dw*0.06,y:oy+dh*0.14,w:dw*0.88,h:dh*0.72};paint();
      }
      layout();
      var drag=null;
      function clampRect(x1,y1,x2,y2){
        x1=Math.max(ox,Math.min(x1,ox+dw-MIN));y1=Math.max(oy,Math.min(y1,oy+dh-MIN));
        x2=Math.max(x1+MIN,Math.min(x2,ox+dw));y2=Math.max(y1+MIN,Math.min(y2,oy+dh));
        r={x:x1,y:y1,w:x2-x1,h:y2-y1};
      }
      function startDrag(e){
        var h=e.target.closest&&e.target.closest('[data-h]'),inBox=e.target===box;
        if(!h&&!inBox)return;
        drag={mode:h?h.getAttribute('data-h'):'move',px:e.clientX,py:e.clientY,r:{x:r.x,y:r.y,w:r.w,h:r.h}};
        try{stage.setPointerCapture(e.pointerId)}catch(_e){}e.preventDefault();
      }
      function move(e){
        if(!drag)return;
        var dx=e.clientX-drag.px,dy=e.clientY-drag.py,o=drag.r,m=drag.mode;
        if(m==='move'){
          var nx=Math.max(ox,Math.min(o.x+dx,ox+dw-o.w)),ny=Math.max(oy,Math.min(o.y+dy,oy+dh-o.h));
          r={x:nx,y:ny,w:o.w,h:o.h};
        }else{
          var x1=o.x,y1=o.y,x2=o.x+o.w,y2=o.y+o.h;
          if(m.charAt(1)==='w')x1=o.x+dx;else x2=o.x+o.w+dx;
          if(m.charAt(0)==='n')y1=o.y+dy;else y2=o.y+o.h+dy;
          if(x2-x1<MIN){if(m.charAt(1)==='w')x1=x2-MIN;else x2=x1+MIN}
          if(y2-y1<MIN){if(m.charAt(0)==='n')y1=y2-MIN;else y2=y1+MIN}
          clampRect(x1,y1,x2,y2);
        }
        paint();e.preventDefault();
      }
      function end(){drag=null}
      if(window.PointerEvent){
        stage.addEventListener('pointerdown',startDrag);stage.addEventListener('pointermove',move);
        stage.addEventListener('pointerup',end);stage.addEventListener('pointercancel',end);
      }else{
        function touch(e,handler){
          if(e.touches.length!==1){end();return}
          var t=e.touches[0];handler({target:t.target,clientX:t.clientX,clientY:t.clientY,pointerId:t.identifier,preventDefault:function(){e.preventDefault()}});
        }
        stage.addEventListener('touchstart',function(e){touch(e,startDrag)},{passive:false});
        stage.addEventListener('touchmove',function(e){touch(e,move)},{passive:false});
        stage.addEventListener('touchend',end);stage.addEventListener('touchcancel',end);
        stage.addEventListener('mousedown',startDrag);window.addEventListener('mousemove',move);window.addEventListener('mouseup',end);
      }
      window.addEventListener('resize',layout);
    };
    img.src=url;
  });
}
"""

STUDENT_HELP_JS = PHOTO_CROP_JS + r"""
var HELP_TIP='只拍这一道题，让题目占满画面；避开人脸、姓名、学号；光线要亮，别有阴影。';
function afterConfirm(box,help){
  box.textContent='';box.appendChild(notice('ok','AI 正在想，请稍等…'));
  return api('/student/homework/help/'+help.id+'/solve',{method:'POST'}).then(function(h){showSolution(box,h)}).catch(function(e){
    box.textContent='';box.appendChild(notice('error',e.message));
    if(e.status!==429)box.appendChild(el('button',{text:'再试一次',onclick:function(){afterConfirm(box,help)}}));
    escalateBox(box,help);
  });
}
function escalateBox(box,h){
  if(h.state==='escalated'){box.appendChild(notice('ok','已请老师帮忙，请先做别的题，老师会来找你。'));return}
  var note=el('input',{type:'text',placeholder:'想对老师说的话（选填）',maxlength:300});
  var btn=el('button',{text:'求助老师',onclick:function(){
    btn.disabled=true;
    api('/student/homework/help/'+h.id+'/escalate',{json:{note:note.value}}).then(function(){
      box.appendChild(notice('ok','已通知老师，请先做别的题，老师会来找你。'));wrap.remove();
    }).catch(function(e){btn.disabled=false;box.appendChild(notice('error',e.message))});
  }});
  var wrap=el('div',{class:'row'},note,btn);box.appendChild(wrap);
}
function showSolution(box,h){
  box.textContent='';
  var warn=h.warning||'AI 可能出错，请自己判断';
  box.appendChild(notice('warn',warn));
  if(!h.solution){box.appendChild(notice('error',h.message||'这道题没有得到解答'));escalateBox(box,h);return}
  var s=h.solution,list=el('div'),shown=0,next=el('button',{text:'看下一步'});
  var head=[s.method?'解法：'+s.method:'',s.knowledgePoint?'知识点：'+s.knowledgePoint:''].filter(Boolean).join(' · ');
  if(head)box.appendChild(el('div',{class:'muted',text:head}));
  box.appendChild(list);
  function more(){
    if(shown<s.steps.length){list.appendChild(el('div',{class:'item'},el('b',{text:'第'+s.steps[shown].n+'步'}),el('span',{text:s.steps[shown].text})));shown++}
    if(shown>=s.steps.length){next.remove();list.appendChild(notice('ok','答案：'+s.answer))}
  }
  next.addEventListener('click',more);box.appendChild(next);more();
  box.appendChild(notice('warn',warn+'。看不懂，或者觉得不对，就请老师帮忙。'));
  escalateBox(box,h);
}
function helpCard(){
  var text=el('textarea',{placeholder:'题目文字：可以拍照识别，也可以自己输入',maxlength:1000}),msg=el('div'),out=el('div');
  var last=null,grade=el('select',{}),file=el('input',{type:'file',accept:'image/*',capture:'environment',hidden:true});
  for(var g=1;g<=6;g++)grade.appendChild(el('option',{value:String(g),text:['一','二','三','四','五','六'][g-1]+'年级'}));
  if(ME&&ME.grade>=1&&ME.grade<=6)grade.value=String(ME.grade);
  var snap=el('button',{text:'拍题',onclick:function(){file.click()}});
  if(!CONFIG.visionEnabled)snap.style.display='none';
  var confirmBtn=el('button',{class:'primary',text:'确认题目，请 AI 讲解'});
  root.appendChild(el('div',{class:'card'},el('h2',{text:'这道题我不会'}),el('div',{class:'muted',text:HELP_TIP}),
    el('div',{class:'row'},snap,file,grade),text,msg,el('div',{class:'row'},confirmBtn),out));
  file.addEventListener('change',function(){
    var f=file.files&&file.files[0];if(!f)return;
    msg.textContent='';snap.disabled=true;
    cropPhoto(f).then(function(blob){msg.appendChild(notice('ok','正在识别…'));return api('/student/homework/recognize',{method:'POST',body:blob,headers:{'Content-Type':'image/jpeg'}})})
      .then(function(d){
        text.value=d.text;msg.textContent='';
        msg.appendChild(notice('ok','请检查识别出的文字，不对就直接修改，然后点“确认题目”。'));
        if(d.hasFigure)msg.appendChild(notice('warn','题目里有图形，AI 看不到图。请用文字补充说明，或者直接请老师帮忙。'));
      })
      .catch(function(e){msg.textContent='';if(!e.cancelled)msg.appendChild(notice('error',e.message))})
      .then(function(){snap.disabled=false;file.value=''});
  });
  confirmBtn.addEventListener('click',function(){
    msg.textContent='';out.textContent='';
    if(!text.value.trim()){msg.appendChild(notice('error','请先拍下或写下题目'));return}
    confirmBtn.disabled=true;
    var same=last&&last.text===text.value&&last.grade===Number(grade.value);
    // Same question again (e.g. after an error): reuse its request instead of opening a second one.
    (same?Promise.resolve(last.help):api('/student/homework/help',{json:{questionText:text.value,grade:Number(grade.value)}}))
      .then(function(h){last={text:text.value,grade:Number(grade.value),help:h};return afterConfirm(out,h)})
      .catch(function(e){msg.appendChild(notice('error',e.message))})
      .then(function(){confirmBtn.disabled=false});
  });
}
"""

TEACHER_HELP_JS = r"""
var helpTimer=null,helpSeen=-1;
function helpBadge(tabs){
  function paint(){
    if(document.hidden)return;
    api('/teacher/homework/help?status=open').then(function(d){
      var tab=tabs.querySelector('[data-k="help"]');if(tab)tab.textContent='求助列表'+(d.open?'（'+d.open+'）':'');
      if(helpSeen>=0&&d.open>helpSeen&&document.title.indexOf('●')<0)document.title='● '+document.title;
      helpSeen=d.open;
    }).catch(function(){});
  }
  paint();setInterval(paint,10000);
}
function helpView(body){
  var filter='open',list=el('div'),bar=el('div',{class:'tabs'});
  var openBtn=el('button',{text:'待处理',onclick:function(){filter='open';load()}}),doneBtn=el('button',{text:'已处理',onclick:function(){filter='resolved';load()}});
  bar.appendChild(openBtn);bar.appendChild(doneBtn);
  body.appendChild(el('div',{class:'card'},el('h2',{text:'学生求助'}),el('div',{class:'muted',text:'列表每 10 秒自动刷新。这里只有你班里的学生。'}),bar,list));
  function load(){
    openBtn.className=filter==='open'?'on':'';doneBtn.className=filter==='resolved'?'on':'';
    api('/teacher/homework/help?status='+filter).then(function(d){
      list.textContent='';
      if(!d.items.length){list.appendChild(el('div',{class:'muted',text:filter==='open'?'现在没有人求助。':'还没有处理过的求助。'}));return}
      d.items.forEach(function(it){list.appendChild(helpCard(it))});
    }).catch(function(e){list.textContent='';list.appendChild(notice('error',e.message))});
  }
  function helpCard(it){
    var detail=el('div'),note=el('textarea',{placeholder:'给学生的说明（选填）',style:'min-height:70px'});
    var card=el('div',{class:'card'},
      el('div',{class:'row'},el('b',{text:(it.studentName||'学生')+' · '+(it.grade?it.grade+'年级':'')}),el('span',{class:'tag',text:it.reasonLabel}),
        el('span',{class:'muted',text:it.state==='resolved'?'已处理 '+it.resolvedAt:'已等 '+it.waitMinutes+' 分钟'})),
      el('div',{text:it.questionText}),
      it.studentNote?el('div',{class:'muted',text:'学生说：'+it.studentNote}):null,detail);
    card.appendChild(el('button',{text:'看 AI 对话',onclick:function(){
      detail.textContent='';
      api('/teacher/homework/help/'+it.id).then(function(d){
        d.conversation.forEach(function(m){
          detail.appendChild(el('div',{class:'notice '+(m.role==='ai'?'warn':'ok')},el('b',{text:{student:'学生',ai:'AI',teacher:'老师'}[m.role]+'：'}),
            el('span',{style:'white-space:pre-wrap',text:m.text})));
        });
      }).catch(function(e){detail.appendChild(notice('error',e.message))});
    }}));
    if(it.state==='escalated'){
      card.appendChild(note);
      card.appendChild(el('button',{class:'primary',text:'标记为已处理',onclick:function(){
        api('/teacher/homework/help/'+it.id+'/resolve',{json:{note:note.value}}).then(load).catch(function(e){alert(e.message)});
      }}));
    }
    return card;
  }
  load();clearInterval(helpTimer);helpTimer=setInterval(function(){if(!document.hidden&&body.isConnected)load()},10000);
}
"""


STUDENT_KNOWLEDGE_JS = r"""
function flagLine(f){
  return f.knowledge+(f.subject?'（'+f.subject+'）':'')+' · 问过 '+f.count+' 次 · 最近 '+f.lastAt+' · '+
    (f.state==='open'?'待巩固':'已巩固 '+f.clearedAt);
}
function ruleText(r){return '之后的作业或测试里，这个知识点至少 '+r.minQuestions+' 道题、正确率 '+r.passPercent+'% 以上，标记才会取消。'}
function knowledgeCard(){
  var flagsBox=el('div'),histBox=el('div');
  root.appendChild(el('div',{class:'card'},el('h2',{text:'我的 AI 辅助记录'}),
    el('div',{class:'muted',text:'你让 AI 讲解过的知识点会一直标记，帮助你和老师知道哪里还要巩固。'}),flagsBox,
    el('h3',{text:'我问过的题（保留 90 天）'}),histBox));
  api('/student/homework/knowledge').then(function(d){
    if(!d.flags.length){flagsBox.appendChild(el('div',{class:'muted',text:'还没有记录。'}));return}
    d.flags.forEach(function(f){flagsBox.appendChild(el('div',{class:'item'+(f.state==='open'?'':' done')},el('span',{class:'t',text:flagLine(f)})))});
    flagsBox.appendChild(el('div',{class:'muted',text:ruleText(d.rule)}));
  }).catch(function(e){flagsBox.appendChild(notice('error',e.message))});
  api('/student/homework/history').then(function(d){
    if(!d.items.length){histBox.appendChild(el('div',{class:'muted',text:'还没有问过的题。'}));return}
    d.items.forEach(function(it){histBox.appendChild(el('div',{class:'item'},el('span',{class:'t',text:it.createdAt+' · '+(it.knowledge||'未归类')+' · '+it.stateLabel+'：'+it.questionText})))});
  }).catch(function(e){histBox.appendChild(notice('error',e.message))});
}
"""

TEACHER_KNOWLEDGE_JS = r"""
function newRequestId(){return 'r'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,10)}
var PQ_TYPES={single_choice:'单选',true_false:'判断',fill_blank:'填空',calculation:'计算',short_answer:'简答'};
function practicePanel(box,sid){
  box.textContent='';var msg=el('div',{role:'status','aria-live':'polite'}),card=el('div',{class:'card'});box.appendChild(card);
  card.appendChild(el('h3',{text:'晚托提问 → 巩固练习'}));
  card.appendChild(el('div',{class:'muted',text:'勾选这名学生近 30 天由 AI 讲解过的题，按知识点出新题（不重发原题）。生成后由你审核、修改，确认后才通过“针对性练习”只布置给这名学生；已匹配知识点的题默认出够 3 道，做得好会自动消除“待巩固”。'}));
  api('/teacher/homework/students/'+sid+'/practice-sources').then(function(d){
    (d.practice||[]).forEach(function(p){card.appendChild(notice(p.state==='graded'?'ok':'',p.title+' · '+p.assignedAt+' · '+(p.state==='graded'?'已完成，做对 '+p.correct+'/'+p.total:'已布置，等待学生完成')))});
    if(!d.items.length){card.appendChild(el('div',{class:'muted',text:'近 30 天没有 AI 讲解过的题。'}));return}
    var checks=[],subjectSel=el('select');['数学','语文','英语'].forEach(function(x){subjectSel.appendChild(el('option',{value:x,text:x}))});
    d.items.forEach(function(it){
      var cb=el('input',{type:'checkbox'});cb.checked=!it.practised;checks.push({cb:cb,it:it});
      var tag=it.matched?(it.flag==='open'?'待巩固':it.flag==='cleared'?'已巩固':'已归类'):'未归类';
      card.appendChild(el('label',{class:'item'},cb,el('span',{class:'t'},el('b',{text:(it.knowledge||'未写知识点')+' · '+tag+(it.practised?' · 已出过练习':'')+(it.verify==='mismatch'?' · AI 答案未通过核对':'')}),el('div',{class:'muted',text:it.createdAt+' · '+it.question}))));
    });
    card.appendChild(el('div',{class:'row'},el('span',{class:'muted',text:'未归类题目的科目'}),subjectSel));
    var out=el('div'),go=el('button',{class:'primary',text:'生成巩固题（不会布置）',onclick:function(){
      var picked=checks.filter(function(x){return x.cb.checked});if(!picked.length){msg.textContent='请至少勾选一道题';return}
      var subjects={};picked.forEach(function(x){if(!x.it.matched)subjects[x.it.groupKey]=subjectSel.value});
      go.disabled=true;msg.textContent='AI 正在出题，约半分钟…';
      api('/teacher/homework/students/'+sid+'/practice/generate',{json:{helpIds:picked.map(function(x){return x.it.helpId}),subjects:subjects}}).then(function(r){msg.textContent=r.problems.length?'部分题目没有生成：'+r.problems.join('；'):'';review(out,r)}).catch(function(e){msg.textContent=e.message}).then(function(){go.disabled=false});
    }});
    card.appendChild(go);card.appendChild(msg);card.appendChild(out);
  }).catch(function(e){card.appendChild(notice('error',e.message))});
  function review(out,r){
    out.textContent='';var editors=[],requestId=newRequestId(),status=el('div',{role:'status'});
    r.groups.forEach(function(g){
      var gb=el('div',{class:'card'},el('b',{text:g.subject+' · '+g.topic+(g.matched?'':'（未归类）')}),el('div',{class:'muted',text:'依据（学生问过的题）：'+g.basis.join('；')}));
      if(g.matched&&g.questions.length<r.minQuestions)gb.appendChild(notice('warn','少于 '+r.minQuestions+' 道题时，完成后不足以消除“待巩固”标记。'));
      var list=[];
      g.questions.forEach(function(q){
        var item=el('div',{class:'item'}),t=el('span',{class:'t'}),text=el('textarea');text.value=q.text;
        var answer=el('input',{type:'text',value:q.answer||'',placeholder:'标准答案'}),exp=el('textarea',{placeholder:'解析（仅老师可见）'});exp.value=q.explanation||'';
        var opts=(q.options||[]).map(function(o){return el('input',{type:'text',value:o})}),ci=el('select');
        if(q.question_type==='single_choice')opts.forEach(function(_,i){ci.appendChild(el('option',{value:i,text:'正确答案：'+String.fromCharCode(65+i)}))});
        if(q.question_type==='true_false')['正确','错误'].forEach(function(x,i){ci.appendChild(el('option',{value:i,text:'答案：'+x}))});
        ci.value=String(q.correct_index);
        t.appendChild(el('b',{text:(PQ_TYPES[q.question_type]||q.question_type)+' · 难度 '+q.level}));t.appendChild(text);
        if(q.question_type==='single_choice')opts.forEach(function(n,i){t.appendChild(el('div',{class:'row'},el('span',{text:String.fromCharCode(65+i)+'.'}),n))});
        if(q.question_type==='single_choice'||q.question_type==='true_false')t.appendChild(ci);else t.appendChild(answer);
        t.appendChild(exp);item.appendChild(t);
        var rec={value:function(){return {question_type:q.question_type,level:q.level,text:text.value,options:q.question_type==='single_choice'?opts.map(function(n){return n.value}):q.options,
          correct_index:+ci.value,answer:answer.value,accepted_answers:q.accepted_answers||[],figure:q.figure||{},explanation:exp.value,knowledge:q.knowledge}}};
        item.appendChild(el('button',{text:'删除这题',onclick:function(){item.remove();list.splice(list.indexOf(rec),1)}}));
        list.push(rec);gb.appendChild(item);
      });
      editors.push({g:g,list:list});out.appendChild(gb);
    });
    var due=el('input',{type:'text',placeholder:'截止日期（可空，默认3天）'}),assign=el('button',{class:'primary',text:'审核确认并布置',onclick:function(){
      if(!confirm('确认题目、答案和解析都已审核？将只布置给这名学生，不会重复布置。'))return;
      assign.disabled=true;status.textContent='正在布置…';
      api('/teacher/homework/students/'+sid+'/practice/assign',{json:{requestId:requestId,dueDate:due.value,groups:editors.map(function(x){return {key:x.g.key,subject:x.g.subject,helpIds:x.g.helpIds,questions:x.list.map(function(q){return q.value()})}})}})
        .then(function(res){out.textContent='';out.appendChild(notice('ok','已布置：'+res.assigned.map(function(a){return a.title+'（'+a.questionCount+' 题）'}).join('、')+'。学生在“作业”中完成后，这里会显示结果。'))})
        .catch(function(e){status.textContent=e.message;if(e.status!==409){requestId=newRequestId();assign.disabled=false}});
    }});
    out.appendChild(el('div',{class:'row'},due,assign));out.appendChild(status);
  }
}
function knowledgeView(body){
  var sumBox=el('div'),listBox=el('div');
  body.appendChild(el('div',{class:'card'},el('h2',{text:'学生的 AI 辅助记录'}),
    el('div',{class:'muted',text:'这里是你班里学生让 AI 讲解过的知识点。标记会一直保留，直到之后的作业或测试里这个知识点做得好。'}),sumBox));
  body.appendChild(el('div',{class:'card'},el('h2',{text:'最近的提问'}),listBox));
  api('/teacher/homework/knowledge-summary').then(function(d){
    if(!d.students.length){sumBox.appendChild(el('div',{class:'muted',text:'还没有学生用过 AI 辅助。'}));return}
    d.students.forEach(function(s){
      var panel=el('div'),box=el('div',{class:'item'},el('span',{class:'t'},el('b',{text:s.studentName}),' · 问过 '+s.assists+' 次 · 待巩固 '+s.open+' 个知识点'),
        el('button',{text:'生成巩固练习',onclick:function(){practicePanel(panel,s.studentId)}}));
      sumBox.appendChild(box);sumBox.appendChild(panel);
      s.flags.forEach(function(f){sumBox.appendChild(el('div',{class:'muted',text:'　'+flagLine(f)}))});
    });
    sumBox.appendChild(el('div',{class:'muted',text:ruleText(d.rule)}));
  }).catch(function(e){sumBox.appendChild(notice('error',e.message))});
  api('/teacher/homework/ai-assists').then(function(d){
    if(!d.items.length){listBox.appendChild(el('div',{class:'muted',text:'还没有记录。'}));return}
    d.items.forEach(function(it){
      listBox.appendChild(el('div',{class:'item'},el('span',{class:'t'},el('b',{text:it.studentName}),' · '+it.createdAt+' · '+(it.knowledge||'未归类')+(it.matched?'':'（未归类）')+' · '+it.stateLabel+(it.verify==='mismatch'?' · 答案未通过核对':''),
        el('div',{text:it.questionText}))));
    });
  }).catch(function(e){listBox.appendChild(notice('error',e.message))});
}
"""

SLOTS: dict[str, str] = {
    "__STUDENT_EXTRA__": "helpCard();knowledgeCard();",
    "__TEACHER_VIEWS__": ",help:helpView,knowledge:knowledgeView",
    "__TEACHER_NAMES__": ",help:'求助列表',knowledge:'AI 辅助记录'",
    "__EXTRA_FUNCS__": STUDENT_HELP_JS + TEACHER_HELP_JS + STUDENT_KNOWLEDGE_JS + TEACHER_KNOWLEDGE_JS,
}


def homework_page_html() -> str:
    js = PAGE_JS.replace("__PAGE_AUTH__", PAGE_AUTH_JS)
    for key, value in SLOTS.items():
        js = js.replace(key, value)
    return PAGE_HTML.replace("__CSS__", PAGE_CSS).replace("__JS__", js)


__all__ = ["homework_page_html"]

