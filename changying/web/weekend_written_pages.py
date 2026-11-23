"""Shared classroom short-answer controls, using the existing mobile cropper."""

from changying.web.homework_assistant_pages import PHOTO_CROP_JS

WRITTEN_JS = PHOTO_CROP_JS.replace("确定，识别这一块", "确定，使用这张答案") + r"""
function writtenPhoto(box,a,auto){
  if(!a.hasPhoto)return;
  var b=el('button',{text:'查看答案照片',onclick:function(){
    b.disabled=true;
    fetch('/weekend/written/submissions/'+a.id+'/photo',{headers:{Authorization:'Bearer '+TOKEN},cache:'no-store'}).then(function(r){
      if(!r.ok)throw new Error('照片读取失败');return r.blob();
    }).then(function(blob){
      var url=URL.createObjectURL(blob),im=el('img',{src:url,alt:'学生提交的答案',style:'display:block;max-width:100%;height:auto;'+(auto?'max-height:260px;object-fit:contain;cursor:zoom-in':'')});
      if(auto)im.onclick=function(){im.style.maxHeight=im.style.maxHeight==='none'?'260px':'none'};im.onload=function(){URL.revokeObjectURL(url)};box.appendChild(im);b.remove();
    }).catch(function(e){if(auto)b.textContent='照片加载失败，点击重试';else alert(e.message);b.disabled=false});
  }});box.appendChild(b);if(auto){if(typeof IntersectionObserver!=='undefined'){var observer=new IntersectionObserver(function(entries){if(entries.some(function(e){return e.isIntersecting})){observer.disconnect();b.click()}},{rootMargin:'300px'});observer.observe(b)}else b.click()}
}
var WRITTEN_RESULT={pending:'已提交，待老师批改',correct:'正确',partial:'部分正确',revise:'需订正'};
function writtenTeacher(box){
  box.appendChild(el('h2',{text:'学生作答与批改'}));
  box.appendChild(el('p',{class:'muted',text:'上传后系统先预批，建议仅老师可见，不计入学情。请逐项核对照片、识别内容与参考答案，再确认保存；无法核对时仍可手工批改。'}));
  var lastClass=null,loadRevision=0,currentStatus='',data=null,rows={},grading=false,drafts={};
  var status=el('div',{role:'status'}),stats=el('div',{class:'notice'}),out=el('div'),filter=el('select');
  [['all','全部答案'],['pending','只看待批改'],['reviewed','只看已批改']].forEach(function(x){filter.appendChild(el('option',{value:x[0],text:x[1]}))});
  var batch=el('button',{text:'保存全部批改',class:'primary',onclick:function(){var items=[];Object.keys(rows).forEach(function(id){var r=rows[id];if(r.pick.value&&(r.pick.value!==r.answer.result||r.comment.value!==r.answer.comment))items.push(payload(r))});if(!items.length){status.textContent='请先为答案选择批改结果';return}save(items)}});
  box.appendChild(el('div',{class:'row'},filter,el('button',{text:'刷新提交与批改进度',onclick:load}),batch));box.appendChild(status);box.appendChild(stats);box.appendChild(out);
  var form=el('details',{},el('summary',{text:'临时补充一道题（仅开课前）'})),stem=el('textarea',{placeholder:'题目（开课前添加）',maxlength:4000}),ref=el('textarea',{placeholder:'参考答案／评分要点，仅老师可见',maxlength:4000}),hs=[];
  form.appendChild(stem);form.appendChild(ref);['方向提示（不含答案）','第一步提示（不含答案）','完整思路'].forEach(function(t){var h=el('input',{placeholder:t+'，选填'});hs.push(h);form.appendChild(h)});
  var add=el('button',{text:'添加简答题',onclick:function(){add.disabled=true;var levels=hs.map(function(h){return h.value.trim()});api('/teacher/weekend/sessions/'+SID+'/written/questions',{json:{stem:stem.value,reference:ref.value,hints:levels.some(Boolean)?levels:[]}}).then(function(){stem.value='';ref.value='';hs.forEach(function(h){h.value=''});load()}).catch(function(e){status.textContent=e.message}).then(function(){add.disabled=false})}});form.appendChild(add);box.appendChild(form);
  function payload(r){var b={id:r.answer.id,revision:r.answer.revision,result:r.pick.value,comment:r.comment.value};if(r.usePrecheck&&r.answer.precheck&&r.pick.value===r.answer.precheck.suggestedResult){b.precheckId=r.answer.precheck.id;b.precheckToken=r.answer.precheck.token}return b}
  var checkedPreviews={},pendingPrechecks={},precheckQueue=[],activePrechecks=0;
  function pumpPrechecks(){while(activePrechecks<2&&precheckQueue.length){var job=precheckQueue.shift();activePrechecks++;job.start(function(){delete pendingPrechecks[job.key];activePrechecks--;pumpPrechecks()})}}
  function enqueuePrecheck(key,start,priority){if(pendingPrechecks[key])return;pendingPrechecks[key]=true;var job={key:key,start:start};if(priority)precheckQueue.unshift(job);else precheckQueue.push(job);pumpPrechecks()}
  function precheckPanel(row,a,r,existingArea){
    if(a.result!=='pending')return;
    var p=a.precheck,area=existingArea||el('div',{class:'notice'});if(!existingArea)row.appendChild(area);area.textContent='';r.precheckArea=area;
    area.appendChild(el('b',{text:'系统预批 · 待老师核验'}));
    if(!p||p.status==='failed'||p.status==='disabled'||p.status==='working'||p.status==='queued'||p.status==='stale'){
      var note=el('p',{role:'status','aria-live':'polite',text:p&&p.status==='working'?'正在识别并核对，完成后会自动显示结果。':p&&p.message?p.message:'此份答案尚无预批建议，可补充生成。'});area.appendChild(note);
      var key=a.id+':'+a.revision,revision=a.revision;
      var request=function(retryRequest,watchOnly,priority){
        retry.disabled=true;retry.textContent='排队中…';note.textContent='已排队，正在等待识别；无需反复点击，完成后会自动显示结果。';
        enqueuePrecheck(key,function(done){
          var count=0,ended=false;
          function finish(view,error){if(ended)return;ended=true;done();var current=rows[a.id];if(view&&current&&current.answer.revision===revision&&current.answer.result==='pending'){current.answer.precheck=view;precheckPanel(current.node,current.answer,current,current.precheckArea)}else{note.textContent=error||'答案或批改状态已更新，请刷新核对';retry.disabled=false;retry.textContent='生成／重试预批'}}
          function poll(){
            var current=rows[a.id];if(!current||current.answer.revision!==revision||current.answer.result!=='pending'){finish(null,'答案或批改状态已更新，请刷新核对');return}
            api('/teacher/weekend/sessions/'+SID+'/written/'+a.id+'/precheck?revision='+revision).then(function(d){
              if(d.precheck&&d.precheck.status!=='working'&&d.precheck.status!=='queued'){finish(d.precheck);return}
              count++;note.textContent='正在识别并核对（已检查 '+count+' 次），完成后会自动显示结果。';
              if(count>=40){finish(null,'识别仍未完成，请稍后重试或手工批改。');return}setTimeout(poll,2000);
            }).catch(function(e){finish(null,e.message||'读取预批结果失败，请重试')});
          }
          retry.textContent='正在识别…';note.textContent='正在识别并核对，完成后会自动显示结果。';
          if(watchOnly)poll();else api('/teacher/weekend/sessions/'+SID+'/written/'+a.id+'/precheck',{json:{revision:revision,retry:retryRequest}}).then(function(d){if(!d.queued)throw Error('未收到预批安排回执，请重试');poll()}).catch(function(e){finish(null,e.message)});
        },priority);
      };
      var retry=el('button',{text:'生成／重试预批',onclick:function(){request(true,false,true)}});area.appendChild(retry);
      if(pendingPrechecks[key]){retry.disabled=true;retry.textContent='识别处理中…';note.textContent='正在处理，完成后会自动显示结果。'}
      if((!p||p.status==='working'||p.status==='queued')&&!checkedPreviews[key]){checkedPreviews[key]=true;request(false,!!p,false)}
      return;
    }
    area.appendChild(el('p',{text:p.message||'请逐项核验'}));
    var edits=[];
    (p.items||[]).forEach(function(item){
      var part=el('div',{class:'card'});part.appendChild(el('b',{text:'第 '+item.key+' 小题 · '+(item.result?WRITTEN_RESULT[item.result]:'需人工核验')}));
      part.appendChild(el('p',{text:'本题：'+item.question}));part.appendChild(el('p',{text:'照片识别题目：'+(item.observedQuestion||'未识别')}));
      part.appendChild(el('p',{text:'参考答案：'+(item.reference||[]).join('；')}));part.appendChild(el('p',{text:item.reason}));
      var observed=el('textarea',{maxlength:4000,placeholder:'核对照片中的印刷小题；识别错误时可修正'});observed.value=item.observedQuestion||'';
      part.appendChild(el('label',{text:'识别题目（老师核验后可修改）'}));part.appendChild(observed);
      var answer=el('textarea',{maxlength:4000,placeholder:'每个空的学生答案用分号分隔'});answer.value=(item.answers||[]).join('；');
      part.appendChild(el('label',{text:'学生答案识别内容（老师核验后可修改）'}));part.appendChild(answer);
      edits.push({key:item.key,question:observed,answers:answer});area.appendChild(part);
    });
    if(edits.length){var recalc=el('button',{text:'已核对／修正识别内容，重新预批',onclick:function(){
      if(!confirm('确认逐项对照原图核验了题目和学生答案？这一步只更新预批建议，不保存正式批改。'))return;
      recalc.disabled=true;api('/teacher/weekend/sessions/'+SID+'/written/'+a.id+'/precheck/transcription',{json:{revision:a.revision,token:p.token,items:edits.map(function(e){return {key:e.key,question:e.question.value,answers:e.answers.value.split(/[;；、\n]/).map(function(s){return s.trim()}),confidence:1}})}}).then(function(){load()}).catch(function(e){status.textContent=e.message;recalc.disabled=false});
    }});area.appendChild(recalc)}
    if(p.status==='ready'&&p.suggestedResult){
      area.appendChild(el('p',{text:'整题建议：'+WRITTEN_RESULT[p.suggestedResult]+'。确认前仍为待批；如不同意，可在下方手工选择结果。'}));
      area.appendChild(el('button',{text:'我已逐项核验，采用预批并保存',onclick:function(){
        if(!confirm('确认已核对本份答案的所有小题，并按“'+WRITTEN_RESULT[p.suggestedResult]+'”保存正式批改？'))return;
        r.pick.value=p.suggestedResult;r.usePrecheck=true;save([payload(r)]);
      }}));
    }
  }
  function showStatus(){if(!data)return;var pending=data.items.filter(function(a){return a.result==='pending'}).length;stats.textContent='已提交 '+data.submitted+'/'+data.total+' · 待批改 '+pending+' · 已批改 '+(data.items.length-pending);Object.keys(rows).forEach(function(id){var r=rows[id],a=r.answer;r.badge.textContent=a.name+' · '+WRITTEN_RESULT[a.result];r.node.hidden=filter.value==='pending'?a.result!=='pending':filter.value==='reviewed'?a.result==='pending':false;r.node.className='card'+(a.result==='pending'?'':' reviewed');r.heading.textContent='第 '+r.number+' 题 · 已批改 '+data.items.filter(function(x){return x.questionId===a.questionId&&x.result!=='pending'}).length+'/'+data.items.filter(function(x){return x.questionId===a.questionId}).length});}
  filter.onchange=showStatus;
  function save(items){if(grading)return;grading=true;batch.disabled=true;status.textContent='正在保存批改…';
    api('/teacher/weekend/sessions/'+SID+'/written/review-batch',{json:{items:items}}).then(function(d){if(!d.reviewed||!Array.isArray(d.items))throw Error('未收到批改保存回执，请刷新核对');d.items.forEach(function(a){var r=rows[a.id];if(!r)return;Object.assign(r.answer,a);r.pick.value=a.result;r.comment.value=a.comment;if(r.precheckArea)r.precheckArea.hidden=true;delete drafts[a.id]});showStatus();status.textContent='已保存 '+d.items.length+' 份批改，当前位置已保留。'}).catch(function(e){status.textContent=e.message}).then(function(){grading=false;batch.disabled=false});
  }
  function load(){if(grading)return;var revision=++loadRevision;
    api('/teacher/weekend/sessions/'+SID+'/written').then(function(d){if(revision!==loadRevision)return;data=d;var materials={};form.hidden=(currentStatus||d.status)!=='planned';rows={};out.textContent='';
      if(!d.questions.length)out.appendChild(el('p',{text:'本课没有文字／照片题'}));
      d.questions.forEach(function(q,i){var cut=q.stem.lastIndexOf('\n\n'),reading=cut>=0?q.stem.slice(0,cut):'',question=cut>=0?q.stem.slice(cut+2):q.stem;if(reading&&!materials[reading]){materials[reading]=true;out.appendChild(el('details',{class:'card'},el('summary',{text:'阅读材料（展开查看）'}),el('div',{style:'white-space:pre-wrap',text:reading})))}var heading=el('h3'),card=el('section',{class:'card'},heading,el('div',{style:'white-space:pre-wrap;overflow-wrap:anywhere',text:question}),el('p',{class:'muted',text:'评分要点：'+q.reference}));out.appendChild(card);
        var answers=d.items.filter(function(a){return a.questionId===q.id});heading.textContent='第 '+(i+1)+' 题 · 已批改 '+answers.filter(function(a){return a.result!=='pending'}).length+'/'+answers.length;
        (d.students||[]).filter(function(p){return !answers.some(function(a){return a.studentId===p.id})}).forEach(function(p){card.appendChild(el('p',{class:'muted',text:p.name+' · 未提交'}))});
        var waiting=answers.filter(function(a){return a.result==='pending'});
        if(waiting.length>1)card.appendChild(el('button',{text:'本题待批 '+waiting.length+' 份全部标为正确',onclick:function(){
          if(!confirm('把本题待批的 '+waiting.length+' 份答案都标为“正确”？做错的那几份请随后单独改成“部分正确”或“需订正”。'))return;
          save(waiting.map(function(a){return {id:a.id,revision:a.revision,result:'correct',comment:a.comment||''}}));
        }}));
        answers.forEach(function(a){var badge=el('b'),row=el('div',{class:'card'},badge,el('p',{style:'white-space:pre-wrap;overflow-wrap:anywhere',text:a.text})),pick=el('select'),comment=el('textarea',{placeholder:'给学生的评语',maxlength:1000,style:'min-height:60px'});
          pick.appendChild(el('option',{value:'',text:'请选择批改结果'}));['correct','partial','revise'].forEach(function(v){pick.appendChild(el('option',{value:v,text:WRITTEN_RESULT[v]}))});
          var draft=drafts[a.id];pick.value=draft&&draft.revision===a.revision?draft.result:(a.result==='pending'?'':a.result);comment.value=draft?draft.comment:a.comment;if(draft&&draft.revision!==a.revision){pick.value='';row.appendChild(el('p',{class:'notice',text:'学生已更新答案，请重新核对；原评语已保留。'}))}
          function remember(){if(rows[a.id])rows[a.id].usePrecheck=false;drafts[a.id]={revision:a.revision,result:pick.value,comment:comment.value}}pick.onchange=comment.oninput=remember;
          var r={answer:a,node:row,badge:badge,pick:pick,comment:comment,heading:heading,number:i+1};rows[a.id]=r;
          writtenPhoto(row,a,true);precheckPanel(row,a,r);row.appendChild(pick);row.appendChild(comment);
          ['correct','partial','revise'].forEach(function(v){row.appendChild(el('button',{text:WRITTEN_RESULT[v],onclick:function(){pick.value=v;remember();save([payload(r)])}}))});card.appendChild(row);
        });
      });showStatus();
    }).catch(function(e){status.textContent=e.message});
  }load();
  return function(statusValue,classId){currentStatus=statusValue;form.hidden=statusValue!=='planned';add.disabled=statusValue!=='planned';if(lastClass!==classId){lastClass=classId;load()}};
}
function writtenStudent(box){
  box.hidden=true;
  var out=el('div'),phaseNote=el('div',{role:'status'}),controls=[],closedQuestions={},submissionOpen=false,dirty=false,busy=false,drafts={},materialOpen={},lastSignature='',loadNo=0,editRevision=0,receipts={},lastSid=+(new URLSearchParams(location.search).get('s')||0);
  window.addEventListener('beforeunload',function(e){if(dirty||busy){e.preventDefault();e.returnValue=''}});
  box.appendChild(el('h2',{text:'文字／照片作答'}));box.appendChild(phaseNote);
  box.appendChild(el('button',{text:'刷新题目与老师评语',onclick:function(){if(!busy&&(!dirty||confirm('刷新会清除尚未提交的内容，继续吗？'))){drafts={};dirty=false;editRevision++;lastSignature='';load(true)}}}));box.appendChild(out);
  function load(force){
    var request=++loadNo,revision=editRevision;
    api('/student/weekend/current').then(function(c){
      if(request!==loadNo||!force&&(busy||revision!==editRevision))return;
      if(c.active){lastSid=c.sessionId;var pageUrl=new URL(location.href);pageUrl.searchParams.set('s',lastSid);history.replaceState(null,'',pageUrl)}
      if(!lastSid){box.hidden=true;out.textContent='现在没有正在上的课';return}
      c.sessionId=lastSid;
      return api('/student/weekend/sessions/'+c.sessionId+'/written').then(function(d){
        if(request!==loadNo||!force&&(busy||revision!==editRevision))return;
        var signature=lastSid+':'+JSON.stringify(d);if(signature===lastSignature)return;lastSignature=signature;
        dirty=Object.keys(drafts).length>0;submissionOpen=!!d.canSubmit;closedQuestions={};controls=[];phaseNote.textContent='';out.textContent='';
        if(d.status==='planned'||d.status==='running'&&d.stage<d.practiceStage){box.hidden=true;out.appendChild(el('p',{class:'muted',text:'老师正在讲解；进入随堂练习并逐题开放后，这里会显示文字／照片题。'}));return}
        out.appendChild(el('p',{class:'muted',text:d.canSubmit?'这是本课随堂作答：逐题输入答案或拍照提交，批改后在这里看反馈。课后针对性练习经老师审核布置后，请到学生首页“作业”完成。':'本节作答已关闭，可查看已提交答案与老师反馈。课后针对性练习请到学生首页“作业”查看。'}));
        var groups={};
        box.hidden=!d.questions.length&&!(d.status==='running'&&d.stage===d.practiceStage);
        if(!d.questions.length){
          var availability=d.questionAvailability||{},written=availability.written||{},emptyText=written.total?'老师尚未在大屏开放本课文字／照片题；开放后可在此输入答案或上传照片。':'本课目前没有已同步的文字／照片题；如老师已通过相关练习，请老师检查“同步新增练习”。课后针对性练习请到学生首页“作业”完成。';
          out.appendChild(el('div',{class:'notice',role:'status',text:emptyText}));return
        }
        d.questions.forEach(function(q){
          var stem=q.stem||'',cut=stem.lastIndexOf('\n\n'),material=cut>=0?stem.slice(0,cut):'',question=cut>=0?stem.slice(cut+2):stem,target=out;
          if(material){
            var key=material;
            if(!groups[key]){
              var section=el('div',{class:'card'}),lines=material.split('\n'),title=/^篇目|^挑战题/.test(lines[0])?lines.shift():'阅读材料';
              var reading=el('details',{open:materialOpen[key]===undefined?Object.keys(groups).length===0:materialOpen[key]},el('summary',{text:title+' · 阅读材料（展开／收起）'}),el('div',{style:'white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8',text:lines.join('\n')}));
              (function(k,n){n.addEventListener('toggle',function(){materialOpen[k]=n.open})})(key,reading);
              section.appendChild(reading);out.appendChild(section);groups[key]=section;
            }
            target=groups[key];
          }
          var receipt=receipts[c.sessionId+':'+q.id];if(receipt&&(!q.submission||q.submission.revision<receipt.revision))q.submission=receipt;var a=q.submission,card=el('div',{class:'card'},el('div',{style:'white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8;font-weight:600',text:question}));target.appendChild(card);
          if(a){card.appendChild(el('div',{class:'notice',text:(a.result==='pending'&&!q.answersPublished?'已提交，请等待老师统一在大屏公布答案。':WRITTEN_RESULT[a.result])+' · 已提交 '+(a.attempts||1)+'/3次'}));card.appendChild(el('p',{text:a.text}));writtenPhoto(card,a);if(a.comment)card.appendChild(el('p',{text:'老师评语：'+a.comment}))}
          if(!d.canSubmit||q.canSubmit===false||a&&(a.attempts||1)>=3)return;
          var ackNotice=el('div',{role:'status'});card.appendChild(ackNotice);var text=el('textarea',{placeholder:'填写答案，也可以用键盘听写或拍照提交',maxlength:4000}),photo=null,removeExisting=false,preview=el('div'),url=null;
          var draft=drafts[q.id];text.value=draft?draft.text:(a?a.text:'');photo=draft?draft.photo:null;removeExisting=!!(draft&&draft.removeExisting);
          function saveDraft(){drafts[q.id]={text:text.value,photo:photo,removeExisting:removeExisting};dirty=true;editRevision++}
          text.oninput=saveDraft;card.appendChild(text);
          var file=el('input',{type:'file',accept:'image/*',style:'display:none'}),photoBtn=el('button',{text:'拍照／选择照片',onclick:function(){if(submissionOpen&&!closedQuestions[q.id])file.click()}});
          file.onchange=function(){var f=file.files[0];file.value='';if(!f)return;busy=true;photoBtn.disabled=true;
            cropPhoto(f).then(function(blob){if(blob.size>3*1024*1024)throw new Error('照片超过3MB，请缩小取景范围');photo=blob;saveDraft();if(url)URL.revokeObjectURL(url);url=URL.createObjectURL(blob);preview.textContent='';preview.appendChild(el('img',{src:url,alt:'待提交答案预览',style:'max-width:100%;height:auto'}));preview.appendChild(el('button',{text:'移除照片',onclick:function(){photo=null;saveDraft();URL.revokeObjectURL(url);url=null;preview.textContent=''}}))}).catch(function(e){if(!e.cancelled)alert(e.message)}).then(function(){busy=false;photoBtn.disabled=false});
          };
          controls.push({questionId:q.id,button:photoBtn,blocked:function(){return busy}});
          card.appendChild(file);card.appendChild(photoBtn);card.appendChild(preview);
          if(photo){url=URL.createObjectURL(photo);preview.appendChild(el('img',{src:url,alt:'待提交答案预览',style:'max-width:100%;height:auto'}))}
          if(a&&a.hasPhoto){card.appendChild(el('div',{class:'muted',text:'未重新选择照片时保留原图；修改提交后需要老师重新批改。'}));var removeOld=el('button',{text:removeExisting?'重提时移除原照片':'移除已交照片',onclick:function(){removeExisting=!removeExisting;removeOld.textContent=removeExisting?'重提时移除原照片':'移除已交照片';saveDraft()}});card.appendChild(removeOld)}
          if(!q.hasHints&&!a)card.appendChild(el('p',{class:'muted',text:'需要帮助时请举手问老师。'}));
          if(q.hasHints&&!a){var level=q.hintUsed||0,hout=el('div');(q.hintTexts||[]).forEach(function(t){hout.appendChild(el('div',{class:'notice warn',text:t}))});var hint=el('button',{text:'要提示（'+level+'/3）',disabled:level>=3,onclick:function(){
            if(!submissionOpen||closedQuestions[q.id])return;hint.disabled=true;api('/student/weekend/sessions/'+c.sessionId+'/written/'+q.id+'/hint',{method:'POST'}).then(function(h){level=h.level;hout.appendChild(el('div',{class:'notice warn',text:h.text}));hint.textContent='要提示（'+level+'/3）';hint.disabled=level>=3}).catch(function(e){alert(e.message);hint.disabled=false});
          }});controls.push({questionId:q.id,button:hint,blocked:function(){return level>=3}});card.appendChild(hint);card.appendChild(hout)}
          var send=el('button',{class:'primary',text:a?'重新提交答案':'提交答案',onclick:function(){
            if(busy)return;if(!submissionOpen||closedQuestions[q.id]){alert('老师已关闭作答，你的草稿仍保留在页面上');return}if(!text.value.trim()&&!photo&&!(a&&a.hasPhoto&&!removeExisting)){alert('请填写答案或拍照');return}
            busy=true;send.disabled=true;var fd=new FormData();fd.append('text',text.value);fd.append('revision',a?a.revision:0);fd.append('removePhoto',removeExisting?'true':'false');if(photo)fd.append('photo',photo,'answer.jpg');
            api('/student/weekend/sessions/'+c.sessionId+'/written/'+q.id,{method:'POST',body:fd}).then(function(saved){if(!saved.submitted||!saved.submission||saved.submission.questionId!==q.id)throw Error('未收到本题保存回执，请刷新核对；草稿已保留');if(url)URL.revokeObjectURL(url);busy=false;delete drafts[q.id];dirty=Object.keys(drafts).length>0;var receipt=saved.submission;receipt.attempts=saved.attempts;receipts[c.sessionId+':'+q.id]=receipt;a=receipt;q.submission=receipt;send.textContent='已提交 '+saved.attempts+'/3次';ackNotice.textContent='已提交并保存到服务器（'+saved.attempts+'/3次）';phaseNote.textContent='本题已保存到服务器（'+saved.attempts+'/3次）';lastSignature='';load(true)}).catch(function(e){busy=false;send.disabled=false;phaseNote.textContent=e.message+'；本题草稿已保留。';if(e.status===409){lastSignature='';load(true)}});
          }});controls.push({questionId:q.id,button:send,blocked:function(){return busy}});card.appendChild(send);
        });
      });
    }).catch(function(e){alert(e.message)});
  }load();
  setInterval(function(){
    if(document.hidden||busy)return;
    if(!dirty){load();return}
    api('/student/weekend/current').then(function(c){
      submissionOpen=!!(c.active&&c.practice&&c.canSubmit!==false&&c.sessionId===lastSid);
      closedQuestions={};(c.publishedWrittenQuestionIds||[]).forEach(function(id){closedQuestions[id]=true});
      phaseNote.textContent=submissionOpen?'':'老师已关闭当前作答；未提交草稿保留在此页，请勿关闭或刷新。';
      controls.forEach(function(x){x.button.disabled=!submissionOpen||!!closedQuestions[x.questionId]||x.blocked()});
    }).catch(function(){phaseNote.textContent='课堂状态暂时读取失败，未提交草稿仍保留。'});
  },5000);
}
"""
