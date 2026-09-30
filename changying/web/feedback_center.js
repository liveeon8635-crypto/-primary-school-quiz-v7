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
    '.cy-fc-followup{padding:8px 10px;border-left:3px solid #bfd2f4;background:#f8fbff;border-radius:7px;font-size:12px}.cy-fc-actions{display:flex;gap:8px;flex-wrap:wrap}.cy-fc-actions button{border:1px solid #d7deea;background:#fff;border-radius:10px;padding:8px 11px;font-weight:700}.cy-fc-actions button.primary{background:#173a78;border-color:#173a78;color:#fff}.cy-fc-actions button.green{background:#15803d;border-color:#15803d;color:#fff}'+
    '.cy-fc-compose{display:grid;gap:8px}.cy-fc-compose textarea{width:100%;min-height:74px;border:1px solid #cfd7e5;border-radius:10px;padding:10px 11px;resize:vertical;font:inherit}.cy-fc-empty{padding:22px;text-align:center;color:#667085;background:#f5f7fb;border-radius:12px}.cy-fc-error{padding:12px;background:#fff1f1;color:#991b1b;border-radius:12px}'+
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
      const followupHtml=followups.length?'<div><b>追加反馈</b>'+followups.map(item=>
        '<div class="cy-fc-followup">'+escapeHtml(item.message||'')+'<small style="display:block;color:#667085;margin-top:3px">'+escapeHtml(item.at||'')+'</small></div>'
      ).join('')+'</div>':'';
      const ack=record.acknowledged?'<span class="cy-fc-tag granted">已查收（满意）</span>':
        '<button class="green" data-cy-fc-ack="'+id+'">查收（满意）</button>';
      return '<article class="cy-fc-record" data-cy-fc-record="'+id+'">'+
        '<div class="cy-fc-meta"><span class="cy-fc-tag '+statusClass(record)+'">取用状态：'+escapeHtml(statusLabel(record))+'</span><span class="cy-fc-tag">奖励分：'+escapeHtml(rewardText(record))+'</span></div>'+
        '<div><b>'+escapeHtml(record.category||'产品反馈')+'</b><div style="margin-top:5px;line-height:1.55">'+escapeHtml(record.message||'')+'</div><small style="color:#667085">'+escapeHtml(record.createdAt||'')+'</small></div>'+
        '<div class="cy-fc-receipt"><b>处理回执</b><div style="margin-top:4px">'+escapeHtml(receiptText(record))+'</div></div>'+
        followupHtml+
        '<div class="cy-fc-actions"><button data-cy-fc-followup-toggle="'+id+'">追加反馈</button>'+ack+'</div>'+
        '<div class="cy-fc-compose" data-cy-fc-followup-form="'+id+'" hidden><textarea maxlength="1200" data-cy-fc-followup-input="'+id+'" placeholder="补充新的现象、截图说明或后续建议"></textarea><div class="cy-fc-actions"><button class="primary" data-cy-fc-followup-submit="'+id+'">提交追加反馈</button><button data-cy-fc-followup-cancel="'+id+'">取消</button></div></div>'+
        '</article>';
    }).join('');
    body.innerHTML=summaryHtml+(items||'<div class="cy-fc-empty">还没有提交过反馈。可以点击“提交新反馈”开始。</div>');
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
      submit.disabled=true;
      try{await api('/v1/product-feedback/mine/'+id+'/follow-up',{method:'POST',body:JSON.stringify({message})});await load()}
      catch(error){submit.disabled=false;alert(error.message||'追加反馈失败')}
      return;
    }
    const acknowledge=event.target.closest('[data-cy-fc-ack]');
    if(acknowledge){
      acknowledge.disabled=true;
      try{await api('/v1/product-feedback/mine/'+acknowledge.dataset.cyFcAck+'/acknowledge',{method:'POST'});await load()}
      catch(error){acknowledge.disabled=false;alert(error.message||'查收失败')}
    }
  });

  const identityReady=()=>{
    if(!readToken())return false;
    const chip=document.getElementById('cy-v1-unified-identity')||document.getElementById('identityChip')||document.getElementById('identity');
    const label=text(chip&&chip.textContent);
    return Boolean(label&&!label.includes('正在识别')&&!label.includes('检查登录状态')&&!label.includes('尚未登录'));
  };
  const ensureEntry=()=>{
    let entry=document.getElementById('feedbackCenterButton');
    const host=document.querySelector('.top-actions')||document.querySelector('.cy-v1-unified-top-actions');
    if(!entry&&host){
      entry=document.createElement('button');
      entry.id='feedbackCenterButton';
      entry.type='button';
      entry.className='btn';
      entry.textContent='我的反馈记录';
      host.prepend(entry);
      entry.onclick=open;
    }
    if(entry)entry.hidden=!identityReady();
  };
  window.addEventListener('pageshow',ensureEntry);
  window.addEventListener('popstate',ensureEntry);
  window.addEventListener('focus',ensureEntry);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)ensureEntry()});
  let polls=0;
  const timer=setInterval(()=>{ensureEntry();polls+=1;if(polls>=24)clearInterval(timer)},500);
  ensureEntry();

  window.ChangyingFeedbackCenter=Object.freeze({open,close,load,statusLabel,statusClass,rewardText,receiptText});
})();
