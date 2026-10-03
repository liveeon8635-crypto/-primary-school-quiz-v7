(()=>{
  if(window.__cyFeedbackCenterInstalled)return;
  window.__cyFeedbackCenterInstalled=true;

  const REMEMBER_KEY='v717Remember';
  const readToken=()=>{
    const remembered=localStorage.getItem(REMEMBER_KEY)==='1';
    const primary=remembered?localStorage:sessionStorage;
    return primary.getItem('v717Token')||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||
      sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||'';
  };
  const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const text=value=>String(value??'').trim();
  const statusLabel=record=>{
    const explicit=text(record&&record.statusLabel);
    if(explicit)return explicit;
    const status=text(record&&record.rewardStatus);
    if(status==='granted')return '已取用';
    if(status==='pending')return '待处理';
    return '已收到';
  };
  const statusClass=record=>text(record&&record.rewardStatus)==='granted'?'granted':'pending';
  const rewardText=record=>{
    const points=Number(record&&record.rewardPoints||0);
    return text(record&&record.rewardStatus)==='granted'?'已获得 +'+points+' 分':'待发放 '+points+' 分';
  };
  const receiptText=record=>text(record&&record.receipt)||((record&&record.acknowledged)?'已查收（满意）':'已收到，等待处理回执');
  const catalogGapText=record=>{
    const gap=record&&record.catalogGap;
    if(!gap)return '';
    const students=Array.isArray(gap.students)?gap.students:[];
    if(!students.length)return '';
    return '教材/知识模块练习缺失：'+students.map(name=>text(name)).filter(Boolean).join('、');
  };
  const reviewHref=record=>{
    const raw=text(record&&record.acceptanceUrl)||text(record&&record.page)||'/v1';
    let url;try{url=new URL(raw,location.origin)}catch{return '/v1'}
    if(url.origin!==location.origin)return '/v1';
    url.searchParams.set('cy_feedback_review',String(record&&record.id||''));
    url.searchParams.set('cy_feedback_return','/v1/workspace?tab=feedback-records&reviewed='+encodeURIComponent(String(record&&record.id||''))+'&focus='+encodeURIComponent(String(record&&record.id||'')));
    return url.pathname+url.search+url.hash;
  };

  const style=document.createElement('style');
  style.id='changying-feedback-center-style';
  style.textContent=
    '#cy-feedback-center-backdrop[hidden]{display:none!important}'+
    '#cy-feedback-center-backdrop{position:fixed;inset:0;z-index:180;background:rgba(15,23,42,.42);display:grid;place-items:center;padding:18px}'+
    '#cy-feedback-center-modal{width:min(760px,100%);max-height:min(760px,88dvh);overflow:auto;background:#fff;border-radius:20px;box-shadow:0 28px 90px rgba(15,23,42,.32);border:1px solid #dbe4f1}'+
    '.cy-fc-head{position:sticky;top:0;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 18px;background:#fff;border-bottom:1px solid #e4e9f2}'+
    '.cy-fc-head h2{margin:0;font-size:20px}.cy-fc-body{padding:16px;display:grid;gap:14px}.cy-fc-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}'+
    '.cy-fc-kpi,.cy-fc-record{border:1px solid #e4e9f2;border-radius:14px;background:#fff;padding:13px}.cy-fc-kpi strong{display:block;font-size:24px;margin-top:5px}.cy-fc-kpi small{color:#667085}'+
    '.cy-fc-record{display:grid;gap:10px}.cy-fc-meta{display:flex;gap:7px;flex-wrap:wrap}.cy-fc-tag{display:inline-flex;padding:5px 8px;border:1px solid #dbe4f1;border-radius:999px;font-size:11px;background:#f8fbff}'+
    '.cy-fc-tag.granted{color:#166534;background:#eefbf2;border-color:#cdebd7}.cy-fc-tag.pending{color:#8a4b00;background:#fff8e8;border-color:#f5d79a}.cy-fc-receipt{padding:10px 11px;border-radius:10px;background:#f5f8fd;border:1px solid #e0e7f2}'+
    '.cy-fc-followup{padding:8px 10px;border-left:3px solid #bfd2f4;background:#f8fbff;border-radius:7px;font-size:12px}.cy-fc-actions{display:flex;gap:8px;flex-wrap:wrap}.cy-fc-actions button{border:1px solid #d7deea;background:#fff;border-radius:10px;padding:8px 11px;font-weight:700}.cy-fc-actions button.primary{background:#173a78;border-color:#173a78;color:#fff}.cy-fc-actions button.green{background:#15803d;border-color:#15803d;color:#fff}.cy-fc-review{display:inline-flex;align-items:center;text-decoration:none;background:#173a78;color:#fff;border-radius:10px;padding:8px 11px;font-weight:800}'+
    '.cy-fc-compose{display:grid;gap:8px}.cy-fc-compose textarea{width:100%;min-height:74px;border:1px solid #cfd7e5;border-radius:10px;padding:10px 11px;resize:vertical;font:inherit}.cy-fc-photo{display:flex;align-items:center;gap:8px;font-size:12px;color:#475467}.cy-fc-photo input{max-width:220px}.cy-fc-empty{padding:22px;text-align:center;color:#667085;background:#f5f7fb;border-radius:12px}.cy-fc-error{padding:12px;background:#fff1f1;color:#991b1b;border-radius:12px}'+
    '@media(max-width:640px){#cy-feedback-center-backdrop{padding:8px;align-items:end}#cy-feedback-center-modal{max-height:84dvh;border-radius:18px 18px 0 0}.cy-fc-summary{grid-template-columns:1fr}.cy-fc-head{padding:13px 14px}.cy-fc-body{padding:12px}}';
  document.head.appendChild(style);

  const backdrop=document.createElement('div');
  backdrop.id='cy-feedback-center-backdrop';
  backdrop.hidden=true;
  backdrop.innerHTML='<section id="cy-feedback-center-modal" role="dialog" aria-modal="true" aria-label="我的反馈记录">'+
    '<header class="cy-fc-head"><div><h2>我的反馈记录</h2><small>查看取用状态、处理回执与反馈奖励分</small></div><div class="cy-fc-actions"><button id="cy-fc-new" class="primary">提交新反馈</button><button id="cy-fc-close">关闭</button></div></header>'+
    '<div class="cy-fc-body" id="cy-fc-body"><div class="cy-fc-empty">正在读取反馈记录…</div></div></section>';
  document.body.appendChild(backdrop);

  const body=backdrop.querySelector('#cy-fc-body');
  const api=async(path,options)=>{
    const token=readToken();
    if(!token)throw new Error('登录状态已失效，请重新登录');
    const opts=options||{};
    const headers={Authorization:'Bearer '+token,...(opts.headers||{})};
    if(opts.body!==undefined)headers['Content-Type']='application/json';
    const response=await fetch(path,{...opts,headers});
    let data={};try{data=await response.json()}catch{}
    if(!response.ok)throw new Error(data.detail||'请求失败');
    return data;
  };

  const filePayload=async file=>{
    if(!file)return {};
    if(!['image/jpeg','image/png','image/webp'].includes(file.type))throw new Error('追加反馈照片仅支持 JPG、PNG 或 WebP');
    if(file.size<1||file.size>1000000)throw new Error('照片大小需在 1 MB 以内');
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||'').split(',')[1]||'');reader.onerror=()=>reject(new Error('照片读取失败'));reader.readAsDataURL(file)});
    return {attachment_name:file.name,attachment_type:file.type,attachment_size:file.size,attachment_data:data};
  };

  const renderRecords=data=>{
    const records=Array.isArray(data&&data.records)?data.records:[];
    const summary=data&&data.rewardSummary||{};
    const summaryHtml='<div class="cy-fc-summary">'+
      '<div class="cy-fc-kpi"><small>已提交</small><strong>'+Number(summary.receivedFeedbackCount||records.length)+'</strong></div>'+
      '<div class="cy-fc-kpi"><small>已取用</small><strong>'+Number(summary.adoptedFeedbackCount||0)+'</strong></div>'+
      '<div class="cy-fc-kpi"><small>已获得奖励分</small><strong>'+Number(summary.earnedPoints||0)+'</strong><small>待发放 '+Number(summary.pendingPoints||0)+' 分</small></div>'+
      '</div>';
    const items=records.map(record=>{
      const id=Number(record.id);
      const followups=Array.isArray(record.followUps)?record.followUps:[];
      const followupHtml='<div class="cy-fc-followups" data-cy-fc-followups="'+id+'"><b>追加反馈（'+followups.length+'）</b>'+
        (followups.length?followups.map(item=>
          '<div class="cy-fc-followup">'+escapeHtml(item.message||'')+'<small style="display:block;color:#667085;margin-top:3px">'+escapeHtml(item.at||'')+'</small></div>'
        ).join(''):'<div class="cy-fc-followup">暂无追加反馈</div>')+'</div>';
      const own=record.canFollowUp!==false;
      const canConfirm=record.canConfirm===true,accepted=record.terminalAccepted===true;
      const reviewed=new URLSearchParams(location.search).get('reviewed')===String(id);
      const ack=record.acknowledged?'<span class="cy-fc-tag granted">用户已确认</span>':
        (reviewed&&canConfirm&&own?'<button class="green" data-cy-fc-ack="'+id+'">确认通过</button>':'');
      const review=canConfirm?'<a class="cy-fc-review" href="'+escapeHtml(reviewHref(record))+'">'+(reviewed?'重新去验收':'已处理 · 点击去验收')+'</a>':'';
      const ownerMeta=record.submittedBy?'<span class="cy-fc-tag">提交人：'+escapeHtml(record.submittedBy)+'</span>':'';
      return '<article class="cy-fc-record" data-cy-fc-record="'+id+'">'+
        '<div class="cy-fc-meta"><span class="cy-fc-tag '+statusClass(record)+'">取用状态：'+escapeHtml(statusLabel(record))+'</span><span class="cy-fc-tag" data-cy-fc-reward="'+id+'">奖励分：'+escapeHtml(rewardText(record))+'</span>'+ownerMeta+'</div>'+
        '<div><b>'+escapeHtml(record.category||'产品反馈')+'</b><div style="margin-top:5px;line-height:1.55">'+escapeHtml(record.message||'')+'</div><small style="color:#667085">'+escapeHtml(record.createdAt||'')+'</small></div>'+
        '<div class="cy-fc-receipt"><b>处理回执</b><div style="margin-top:4px">'+escapeHtml(receiptText(record))+'</div>'+(review?'<div class="cy-fc-actions" style="margin-top:8px">'+review+'</div>':'')+'</div>'+
        followupHtml+
        '<div class="cy-fc-actions">'+ack+(reviewed&&!accepted&&own?'<button data-cy-fc-followup-toggle="'+id+'">追加反馈</button>':'')+'</div>'+
        '<div class="cy-fc-compose" data-cy-fc-followup-form="'+id+'" hidden><textarea maxlength="1200" data-cy-fc-followup-input="'+id+'" placeholder="补充新的现象、截图说明或后续建议"></textarea><label class="cy-fc-photo">📷 添加照片 <input type="file" accept="image/jpeg,image/png,image/webp" data-cy-fc-followup-photo="'+id+'"></label><div class="cy-fc-actions"><button class="primary" data-cy-fc-followup-submit="'+id+'">提交追加反馈</button><button data-cy-fc-followup-cancel="'+id+'">取消</button></div></div>'+
        '</article>';
    }).join('');
    body.innerHTML=summaryHtml+(items||'<div class="cy-fc-empty">还没有提交过反馈。可以点击“提交新反馈”开始。</div>');
    const focusId=new URLSearchParams(location.search).get('focus');
    if(focusId){
      const target=body.querySelector('[data-cy-fc-record="'+CSS.escape(String(focusId))+'"]');
      if(target){
        target.style.outline='3px solid #7aa2f7';
        target.style.outlineOffset='2px';
        target.scrollIntoView({behavior:'smooth',block:'center'});
        setTimeout(()=>{target.style.outline='';target.style.outlineOffset=''},2600);
      }
    }
  };

  const load=async()=>{
    body.innerHTML='<div class="cy-fc-empty">正在读取反馈记录…</div>';
    try{renderRecords(await api('/v1/product-feedback/mine'))}
    catch(error){body.innerHTML='<div class="cy-fc-error">反馈记录读取失败：'+escapeHtml(error.message||'请稍后重试')+'</div>'}
  };
  const open=()=>{backdrop.hidden=false;load()};
  const close=()=>{backdrop.hidden=true};

  backdrop.querySelector('#cy-fc-close').onclick=close;
  backdrop.addEventListener('click',event=>{if(event.target===backdrop)close()});
  backdrop.querySelector('#cy-fc-new').onclick=()=>{
    close();
    const fab=document.getElementById('cy-product-assistant-fab');
    if(fab&&fab.hidden===false)fab.click();
    const tab=document.querySelector('[data-pa-tab="feedback"]');
    if(tab)tab.click();
  };
  body.addEventListener('click',async event=>{
    const toggle=event.target.closest('[data-cy-fc-followup-toggle]');
    if(toggle){
      const form=body.querySelector('[data-cy-fc-followup-form="'+toggle.dataset.cyFcFollowupToggle+'"]');
      if(form)form.hidden=!form.hidden;
      return;
    }
    const cancel=event.target.closest('[data-cy-fc-followup-cancel]');
    if(cancel){
      const form=body.querySelector('[data-cy-fc-followup-form="'+cancel.dataset.cyFcFollowupCancel+'"]');
      if(form)form.hidden=true;
      return;
    }
    const submit=event.target.closest('[data-cy-fc-followup-submit]');
    if(submit){
      const id=submit.dataset.cyFcFollowupSubmit;
      const input=body.querySelector('[data-cy-fc-followup-input="'+id+'"]');
      const message=text(input&&input.value);
      if(!message){if(input)input.focus();return}
      const photo=body.querySelector('[data-cy-fc-followup-photo="'+id+'"]');
      submit.disabled=true;
      try{
        const attachment=await filePayload(photo&&photo.files&&photo.files[0]);
        await api('/v1/product-feedback/mine/'+id+'/follow-up',{method:'POST',body:JSON.stringify({message,...attachment})});
        await load();
      }catch(error){submit.disabled=false;alert(error.message||'追加反馈失败')}
      return;
    }
    const reject=event.target.closest('[data-cy-fc-reject]');
    if(reject){
      const id=reject.dataset.cyFcReject;
      const reason=prompt('请输入驳回原因或需要继续修改的内容：');
      if(!text(reason))return;
      reject.disabled=true;
      try{await api('/v1/product-feedback/mine/'+id+'/reject',{method:'POST',body:JSON.stringify({message:text(reason)})});await load()}
      catch(error){reject.disabled=false;alert(error.message||'驳回失败')}
      return;
    }
    const acknowledge=event.target.closest('[data-cy-fc-ack]');
    if(acknowledge){
      acknowledge.disabled=true;
      try{await api('/v1/product-feedback/mine/'+acknowledge.dataset.cyFcAck+'/acknowledge',{method:'POST'});await load()}
      catch(error){acknowledge.disabled=false;alert(error.message||'查收失败')}
    }
  });

  // Feedback records are intentionally exposed only through the product assistant
  // dropdown. Do not create a second standalone top-navigation entry.
  window.ChangyingFeedbackCenter=Object.freeze({open,close,load,statusLabel,statusClass,rewardText,receiptText});
})();
