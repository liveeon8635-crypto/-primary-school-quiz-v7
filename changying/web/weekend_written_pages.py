"""Shared classroom short-answer controls, using the existing mobile cropper."""

from changying.web.homework_assistant_pages import PHOTO_CROP_JS

WRITTEN_JS = PHOTO_CROP_JS.replace("确定，识别这一块", "确定，使用这张答案") + r"""
function writtenPhoto(box,a){
  if(!a.hasPhoto)return;
  var b=el('button',{text:'查看答案照片',onclick:function(){
    b.disabled=true;
    fetch('/weekend/written/submissions/'+a.id+'/photo',{headers:{Authorization:'Bearer '+TOKEN},cache:'no-store'}).then(function(r){
      if(!r.ok)throw new Error('照片读取失败');return r.blob();
    }).then(function(blob){
      var url=URL.createObjectURL(blob),im=el('img',{src:url,alt:'学生提交的答案',style:'display:block;max-width:100%;height:auto'});
      im.onload=function(){URL.revokeObjectURL(url)};box.appendChild(im);b.remove();
    }).catch(function(e){alert(e.message);b.disabled=false});
  }});box.appendChild(b);
}
var WRITTEN_RESULT={pending:'已提交，待老师批改',correct:'正确',partial:'部分正确',revise:'需订正'};
function writtenTeacher(box){
  box.appendChild(el('h2',{text:'学生作答与批改'}));
  box.appendChild(el('p',{class:'muted',text:'学生在自己的设备上输入答案或拍照提交；这里查看本班提交并批改。教案中已审核的题目会自动带入，无需再次添加。'}));
  var lastClass=null,loadRevision=0,currentStatus="";
  var out=el('div'),form=el('details',{},el('summary',{text:'临时补充一道题（仅开课前）'})),stem=el('textarea',{placeholder:'题目（开课前添加）',maxlength:4000}),
      ref=el('textarea',{placeholder:'参考答案／评分要点，仅老师可见',maxlength:4000}),hs=[];
  form.appendChild(stem);form.appendChild(ref);
  ['方向提示（不含答案）','第一步提示（不含答案）','完整思路'].forEach(function(t){var h=el('input',{type:'text',placeholder:t+'，选填；填写则需三级完整',maxlength:300});hs.push(h);form.appendChild(h)});
  var add=el('button',{text:'添加简答题',onclick:function(){
    add.disabled=true;
    var levels=hs.map(function(h){return h.value.trim()});
    api('/teacher/weekend/sessions/'+SID+'/written/questions',{json:{stem:stem.value,reference:ref.value,hints:levels.some(Boolean)?levels:[]}}).then(function(){stem.value='';ref.value='';hs.forEach(function(h){h.value=''});load()}).catch(function(e){alert(e.message)}).then(function(){add.disabled=false});
  }});form.appendChild(add);box.appendChild(form);
  box.appendChild(el('button',{text:'刷新提交与批改进度',onclick:load}));box.appendChild(out);
  function load(){
    var revision=++loadRevision;
    api('/teacher/weekend/sessions/'+SID+'/written').then(function(d){
      if(revision!==loadRevision)return;
      form.hidden=(currentStatus||d.status)!=='planned';
      out.textContent='';
      if(!d.questions.length)out.appendChild(el('p',{class:'muted',text:'本节没有文字／拍照作答题。需要时请返回备课页审核题目，再为班级创建课堂。'}));
      out.appendChild(el('div',{class:'notice',text:'已提交 '+d.submitted+'/'+d.total+'（'+d.submissionRate+'%） · 已批改 '+d.reviewed+' · 待批改 '+d.pending+' · 正确 '+d.correct+' · 部分正确 '+d.partial}));
      d.questions.forEach(function(q){
        var card=el('details',{class:'card'},el('summary',{text:'第 '+(d.questions.indexOf(q)+1)+' 题 · 已提交 '+d.items.filter(function(a){return a.questionId===q.id}).length+' 份 · 展开批改'}),el('div',{style:'white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8',text:q.stem}),el('div',{class:'muted',text:'评分要点：'+q.reference}));out.appendChild(card);
        d.items.filter(function(a){return a.questionId===q.id}).forEach(function(a){
          var row=el('div',{class:'card'},el('b',{text:a.name+' · '+WRITTEN_RESULT[a.result]}),el('p',{text:a.text})),comment=el('textarea',{placeholder:'给学生的评语',maxlength:1000});comment.value=a.comment;
          writtenPhoto(row,a);row.appendChild(comment);
          ['correct','partial','revise'].forEach(function(result){
            var b=el('button',{text:WRITTEN_RESULT[result],onclick:function(){
              Array.prototype.forEach.call(row.querySelectorAll('button'),function(x){x.disabled=true});
              api('/teacher/weekend/sessions/'+SID+'/written/'+a.id+'/review',{json:{revision:a.revision,result:result,comment:comment.value}}).then(load).catch(function(e){alert(e.message);Array.prototype.forEach.call(row.querySelectorAll('button'),function(x){x.disabled=false})});
            }});row.appendChild(b);
          });card.appendChild(row);
        });
      });
    }).catch(function(e){alert(e.message)});
  }load();
  return function(status,classId){currentStatus=status;form.hidden=status!=='planned';add.disabled=status!=='planned';if(lastClass!==classId){lastClass=classId;load()}};
}
function writtenStudent(box){
  var out=el('div'),dirty=false,busy=false,drafts={},lastSid=+(new URLSearchParams(location.search).get('s')||0);
  window.addEventListener('beforeunload',function(e){if(dirty||busy){e.preventDefault();e.returnValue=''}});
  box.appendChild(el('h2',{text:'简答题：写答案或拍照提交'}));
  box.appendChild(el('button',{text:'刷新题目与老师评语',onclick:function(){if(!busy&&(!dirty||confirm('刷新会清除尚未提交的内容，继续吗？'))){drafts={};dirty=false;load()}}}));box.appendChild(out);
  function load(){
    api('/student/weekend/current').then(function(c){
      if(c.active){lastSid=c.sessionId;var pageUrl=new URL(location.href);pageUrl.searchParams.set('s',lastSid);history.replaceState(null,'',pageUrl)}
      if(!lastSid){out.textContent='现在没有正在上的课';return}
      c.sessionId=lastSid;
      return api('/student/weekend/sessions/'+c.sessionId+'/written').then(function(d){
        dirty=Object.keys(drafts).length>0;out.textContent='';
        if(!d.questions.length){out.appendChild(el('div',{class:'muted',text:'本节课没有简答题'}));return}
        d.questions.forEach(function(q){
          var a=q.submission,card=el('div',{class:'card'},el('div',{style:'white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8',text:q.stem}));out.appendChild(card);
          if(a){card.appendChild(el('div',{class:'notice',text:WRITTEN_RESULT[a.result]}));card.appendChild(el('p',{text:a.text}));writtenPhoto(card,a);if(a.comment)card.appendChild(el('p',{text:'老师评语：'+a.comment}))}
          if(!d.canSubmit||a&&a.result==='correct')return;
          var text=el('textarea',{placeholder:'填写答案，也可以用键盘听写或拍照提交',maxlength:4000}),photo=null,preview=el('div'),url=null;
          var draft=drafts[q.id];text.value=draft?draft.text:(a?a.text:'');photo=draft?draft.photo:null;
          function saveDraft(){drafts[q.id]={text:text.value,photo:photo};dirty=true}
          text.oninput=saveDraft;card.appendChild(text);
          var file=el('input',{type:'file',accept:'image/*',style:'display:none'}),photoBtn=el('button',{text:'拍照／选择照片',onclick:function(){file.click()}});
          file.onchange=function(){var f=file.files[0];file.value='';if(!f)return;busy=true;photoBtn.disabled=true;
            cropPhoto(f).then(function(blob){if(blob.size>3*1024*1024)throw new Error('照片超过3MB，请缩小取景范围');photo=blob;saveDraft();if(url)URL.revokeObjectURL(url);url=URL.createObjectURL(blob);preview.textContent='';preview.appendChild(el('img',{src:url,alt:'待提交答案预览',style:'max-width:100%;height:auto'}));preview.appendChild(el('button',{text:'移除照片',onclick:function(){photo=null;saveDraft();URL.revokeObjectURL(url);url=null;preview.textContent=''}}))}).catch(function(e){if(!e.cancelled)alert(e.message)}).then(function(){busy=false;photoBtn.disabled=false});
          };
          card.appendChild(file);card.appendChild(photoBtn);card.appendChild(preview);
          if(photo){url=URL.createObjectURL(photo);preview.appendChild(el('img',{src:url,alt:'待提交答案预览',style:'max-width:100%;height:auto'}))}
          if(a&&a.hasPhoto)card.appendChild(el('div',{class:'muted',text:'重新提交会替换原答案；要保留照片请重新选择。'}));
          if(q.hasHints&&!a){var level=q.hintUsed||0,hout=el('div');(q.hintTexts||[]).forEach(function(t){hout.appendChild(el('div',{class:'notice warn',text:t}))});var hint=el('button',{text:'要提示（'+level+'/3）',disabled:level>=3,onclick:function(){
            hint.disabled=true;api('/student/weekend/sessions/'+c.sessionId+'/written/'+q.id+'/hint',{method:'POST'}).then(function(h){level=h.level;hout.appendChild(el('div',{class:'notice warn',text:h.text}));hint.textContent='要提示（'+level+'/3）';hint.disabled=level>=3}).catch(function(e){alert(e.message);hint.disabled=false});
          }});card.appendChild(hint);card.appendChild(hout)}
          var send=el('button',{class:'primary',text:a?'重新提交答案':'提交答案',onclick:function(){
            if(busy)return;if(!text.value.trim()&&!photo){alert('请填写答案或拍照');return}
            busy=true;send.disabled=true;var fd=new FormData();fd.append('text',text.value);fd.append('revision',a?a.revision:0);if(photo)fd.append('photo',photo,'answer.jpg');
            api('/student/weekend/sessions/'+c.sessionId+'/written/'+q.id,{method:'POST',body:fd}).then(function(){if(url)URL.revokeObjectURL(url);busy=false;delete drafts[q.id];dirty=Object.keys(drafts).length>0;load()}).catch(function(e){alert(e.message);busy=false;send.disabled=false});
          }});card.appendChild(send);
        });
      });
    }).catch(function(e){alert(e.message)});
  }load();
}
"""
