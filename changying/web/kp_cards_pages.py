"""知识点讲解卡片页面 (static HTML, no server data inlined; ES5 only so older iPads can run it)."""

from __future__ import annotations

from changying.web.classroom_window_handoff import PAGE_AUTH_JS
from changying.web.homework_assistant_pages import PAGE_CSS

EXTRA_CSS = r"""
.kp{border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:10px 0;background:#fff}
.kp h3{margin:0 0 4px;font-size:18px}.kp ol,.kp ul{margin:6px 0 6px 20px;padding:0}
.kp img{max-width:100%;border-radius:10px;margin:6px 0;display:block}
.kp .sum{font-weight:600}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:720px){.grid2{grid-template-columns:1fr}}
.tag.ok{background:#ecfdf3;color:var(--ok)}.tag.warn{background:var(--warnbg);color:var(--warn)}
textarea.s{min-height:70px}
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
  for(var i=2;i<arguments.length;i++){var c=arguments[i];if(c==null)continue;n.appendChild(typeof c==='string'?document.createTextNode(c):c)}
  return n;
};
var root=document.getElementById('app'),TOKEN='',ME=null;
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
function frame(title,sub){root.textContent='';root.appendChild(el('div',{class:'card'},el('h2',{text:title}),sub?el('div',{class:'muted',text:sub}):null))}
function lines(text){return String(text||'').split('\n').map(function(s){return s.trim()}).filter(Boolean)}
function loadImage(id,img){
  fetch('/kp-cards/images/'+id,{headers:{Authorization:'Bearer '+TOKEN},cache:'no-store'}).then(function(r){return r.ok?r.blob():null}).then(function(b){if(b)img.src=URL.createObjectURL(b)});
}
function shrink(file,maxEdge){
  return new Promise(function(resolve,reject){
    var url=URL.createObjectURL(file),img=new Image();
    img.onload=function(){
      var s=Math.min(1,maxEdge/Math.max(img.width,img.height)),c=document.createElement('canvas');
      c.width=Math.max(1,Math.round(img.width*s));c.height=Math.max(1,Math.round(img.height*s));
      c.getContext('2d').drawImage(img,0,0,c.width,c.height);URL.revokeObjectURL(url);
      resolve(c.toDataURL('image/jpeg',0.8));
    };
    img.onerror=function(){URL.revokeObjectURL(url);reject(new Error('无法读取这张图片'))};
    img.src=url;
  });
}
function renderCard(c){
  var box=el('div',{class:'kp'},el('h3',{text:c.knowledge}),el('div',{class:'muted',text:c.grade+'年级 · '+c.subject}));
  if(c.summary)box.appendChild(el('div',{class:'sum',text:c.summary}));
  if(c.steps.length){var ol=el('ol');c.steps.forEach(function(s){ol.appendChild(el('li',{text:s}))});box.appendChild(ol)}
  c.images.forEach(function(id){var img=el('img',{alt:c.knowledge+'图示'});box.appendChild(img);loadImage(id,img)});
  if(c.examples.length){box.appendChild(el('b',{text:'例题'}));var u1=el('ul');c.examples.forEach(function(s){u1.appendChild(el('li',{text:s}))});box.appendChild(u1)}
  if(c.mistakes.length){box.appendChild(el('b',{text:'容易错的地方'}));var u2=el('ul');c.mistakes.forEach(function(s){u2.appendChild(el('li',{text:s}))});box.appendChild(u2)}
  return box;
}

/* ---------------------------------------------------------------- student */
function studentView(){
  root.textContent='';
  var q=el('input',{type:'text',placeholder:'搜索知识点，例如：分数、小数乘法'}),results=el('div'),wrong=el('div');
  var go=el('button',{class:'primary',text:'搜索',onclick:function(){search()}});
  q.addEventListener('keydown',function(e){if(e.key==='Enter')search()});
  root.appendChild(el('div',{class:'card'},el('h2',{text:'我的错题知识点'}),el('div',{class:'muted',text:'点开可以看讲解。错得多的排在前面。'}),wrong));
  root.appendChild(el('div',{class:'card'},el('h2',{text:'搜索知识点'}),el('div',{class:'row'},q,go),results));
  function search(){
    results.textContent='';
    api('/student/kp-cards?q='+encodeURIComponent(q.value)).then(function(d){
      if(!d.items.length){results.appendChild(el('div',{class:'muted',text:q.value?'没有找到，换个说法试试。':'老师还没有发布讲解卡片。'}));return}
      d.items.forEach(function(c){results.appendChild(renderCard(c))});
    }).catch(function(e){results.appendChild(notice('error',e.message))});
  }
  api('/student/kp-wrong').then(function(d){
    if(!d.items.length){wrong.appendChild(el('div',{class:'muted',text:'错题本里还没有带知识点的错题。'}));return}
    d.items.forEach(function(it){
      var open=el('div');
      var row=el('div',{class:'row'},el('b',{text:it.knowledge}),el('span',{class:'tag',text:it.subject+' · 错 '+it.wrongCount+' 次'}),
        it.aiAssisted?el('span',{class:'tag warn',text:'问过 AI，还需巩固'}):null,
        it.cardId?el('button',{text:'看讲解',onclick:function(){
          open.textContent='';api('/student/kp-cards/'+it.cardId).then(function(c){open.appendChild(renderCard(c))}).catch(function(e){open.appendChild(notice('error',e.message))});
        }}):el('span',{class:'muted',text:'老师还没有发布讲解'}));
      wrong.appendChild(row);wrong.appendChild(open);
    });
  }).catch(function(e){wrong.appendChild(notice('error',e.message))});
  search();
}

/* ---------------------------------------------------------------- teacher */
function teacherView(){
  root.textContent='';
  var grade=el('select'),subject=el('select'),list=el('div'),msg=el('div');
  for(var g=1;g<=6;g++)grade.appendChild(el('option',{value:g,text:g+'年级'}));grade.value='5';
  ['数学','语文','英语'].forEach(function(s){subject.appendChild(el('option',{value:s,text:s}))});
  var seed=el('button',{text:'按题库生成空白卡片',onclick:function(){
    msg.textContent='';seed.disabled=true;
    api('/teacher/kp-cards/seed',{json:{grade:+grade.value,subject:subject.value}}).then(function(d){msg.appendChild(notice('ok','新建了 '+d.created+' 张空白卡片。'));refresh()})
      .catch(function(e){msg.appendChild(notice('error',e.message))}).then(function(){seed.disabled=false});
  }});
  var add=el('button',{text:'＋ 新建知识点',onclick:function(){
    var name=prompt('知识点名称（与题库里的知识点一致，学生错题才能自动对上）');if(!name)return;
    api('/teacher/kp-cards',{json:{grade:+grade.value,subject:subject.value,knowledge:name}}).then(refresh).catch(function(e){alert(e.message)});
  }});
  grade.addEventListener('change',refresh);subject.addEventListener('change',refresh);
  root.appendChild(el('div',{class:'card'},el('h2',{text:'知识点讲解卡片'}),
    el('div',{class:'muted',text:'卡片发布后，学生才能搜索到，也会出现在他们错题的“看讲解”里。AI 只写草稿，必须你确认发布。'}),
    el('div',{class:'row'},grade,subject,seed,add),msg));
  root.appendChild(list);
  function refresh(){
    list.textContent='';
    api('/teacher/kp-cards?grade='+grade.value+'&subject='+encodeURIComponent(subject.value)).then(function(d){
      if(!d.items.length){list.appendChild(el('div',{class:'card muted',text:'这个年级和学科还没有卡片。点“按题库生成空白卡片”。'}));return}
      d.items.forEach(function(c){list.appendChild(editor(c))});
    }).catch(function(e){list.appendChild(notice('error',e.message))});
  }
  function editor(c){
    var sum=el('textarea',{class:'s',placeholder:'一句话讲清楚是什么'}),steps=el('textarea',{placeholder:'分步讲解，每行一步'}),
        mis=el('textarea',{class:'s',placeholder:'常见错误，每行一条'}),ex=el('textarea',{class:'s',placeholder:'例题与解答，每行一条'}),
        m=el('div'),imgs=el('div'),file=el('input',{type:'file',accept:'image/*',hidden:true});
    sum.value=c.summary;steps.value=c.steps.join('\n');mis.value=c.mistakes.join('\n');ex.value=c.examples.join('\n');
    var tag=el('span',{class:'tag'+(c.status==='approved'?' ok':' warn'),text:c.status==='approved'?'已发布':(c.filled?'草稿':'空白')});
    var body=el('div',{hidden:true});
    function body_(){return {grade:c.grade,subject:c.subject,knowledge:c.knowledge,summary:sum.value,steps:lines(steps.value),mistakes:lines(mis.value),examples:lines(ex.value)}}
    function fill(d){c=Object.assign(c,d);sum.value=d.summary;steps.value=d.steps.join('\n');mis.value=d.mistakes.join('\n');ex.value=d.examples.join('\n')}
    function status(){tag.className='tag'+(c.status==='approved'?' ok':' warn');tag.textContent=c.status==='approved'?'已发布':'草稿'}
    function paintImgs(){
      imgs.textContent='';
      c.images.forEach(function(id){
        var im=el('img',{alt:'图示'});loadImage(id,im);
        imgs.appendChild(el('div',{},im,el('button',{text:'删除图片',onclick:function(){api('/teacher/kp-cards/images/'+id,{method:'DELETE'}).then(function(){c.images=c.images.filter(function(x){return x!==id});c.status='draft';status();paintImgs()}).catch(function(e){alert(e.message)})}})));
      });
    }
    paintImgs();
    var save=el('button',{text:'保存草稿',onclick:function(){
      m.textContent='';api('/teacher/kp-cards/'+c.id,{method:'PUT',json:body_()}).then(function(d){fill(d);status();m.appendChild(notice('ok','已保存（需要重新发布）'))}).catch(function(e){m.appendChild(notice('error',e.message))});
    }});
    var ai=el('button',{text:'AI 写草稿',onclick:function(){
      m.textContent='';ai.disabled=true;m.appendChild(notice('ok','AI 正在写…'));
      api('/teacher/kp-cards/'+c.id+'/ai-draft',{method:'POST'}).then(function(d){fill(d);status();m.textContent='';m.appendChild(notice('ok','草稿已生成，请核对后再发布'))})
        .catch(function(e){m.textContent='';m.appendChild(notice('error',e.message))}).then(function(){ai.disabled=false});
    }});
    var pub=el('button',{class:'primary',text:'发布给学生',onclick:function(){
      m.textContent='';
      api('/teacher/kp-cards/'+c.id,{method:'PUT',json:body_()}).then(function(){return api('/teacher/kp-cards/'+c.id+'/approve',{json:{approved:true}})})
        .then(function(){c.status='approved';status();m.appendChild(notice('ok','已发布'))}).catch(function(e){m.appendChild(notice('error',e.message))});
    }});
    var unpub=el('button',{text:'撤回',onclick:function(){api('/teacher/kp-cards/'+c.id+'/approve',{json:{approved:false}}).then(function(){c.status='draft';status()}).catch(function(e){alert(e.message)})}});
    var pic=el('button',{text:'＋ 图片',onclick:function(){file.click()}});
    file.addEventListener('change',function(){
      var f=file.files&&file.files[0];if(!f)return;m.textContent='';
      shrink(f,1000).then(function(url){return api('/teacher/kp-cards/'+c.id+'/images',{json:{data:url}})}).then(function(r){c.images.push(r.id);c.status='draft';status();paintImgs()})
        .catch(function(e){m.appendChild(notice('error',e.message))}).then(function(){file.value=''});
    });
    body.appendChild(sum);body.appendChild(steps);body.appendChild(mis);body.appendChild(ex);body.appendChild(imgs);
    body.appendChild(el('div',{class:'row'},ai,save,pic,file,pub,unpub));body.appendChild(m);
    var head=el('div',{class:'row'},el('b',{text:c.knowledge}),tag,el('button',{text:'展开/收起',onclick:function(){body.hidden=!body.hidden}}));
    return el('div',{class:'card'},head,body);
  }
  refresh();
}

function start(){
  obtainToken().then(function(t){
    TOKEN=t;
    if(!TOKEN){frame('请先登录','请回到首页登录后再打开。');root.appendChild(el('a',{class:'btn',href:'/v1',text:'去登录'}));return}
    return api('/session').then(function(s){
      ME=s;
      if(ME.role==='teacher')teacherView();else if(ME.role==='student')studentView();
      else frame('这个功能只面向老师和学生','当前身份：'+(ME.role||'未知'));
    });
  }).catch(function(e){frame('打不开',e.message||'请稍后重试')});
}
start();
"""

PAGE_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>知识点讲解</title>
<style>__CSS__</style></head>
<body><header><h1>知识点讲解</h1><a href="/v1">返回首页</a></header>
<main id="app"><div class="card muted">加载中…</div></main>
<script>__JS__</script></body></html>
"""


def kp_page_html() -> str:
    return PAGE_HTML.replace("__CSS__", PAGE_CSS + EXTRA_CSS).replace("__JS__", PAGE_JS.replace("__PAGE_AUTH__", PAGE_AUTH_JS))


__all__ = ["kp_page_html"]
