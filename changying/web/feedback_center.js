(()=>{
  if(window.ChangyingFeedbackCenter)return;
  const text=value=>String(value??'').trim();
  const statusLabel=record=>{
    const explicit=text(record?.statusLabel);
    if(explicit)return explicit;
    const status=text(record?.rewardStatus);
    if(status==='granted')return '已取用';
    if(status==='pending')return '待处理';
    return '已收到';
  };
  const statusClass=record=>text(record?.rewardStatus)==='granted'?'granted':'pending';
  const rewardText=record=>{
    const points=Number(record?.rewardPoints||0);
    return text(record?.rewardStatus)==='granted'?'已获得 +'+points+' 分':'待发放 '+points+' 分';
  };
  const receiptText=record=>text(record?.receipt)||(record?.acknowledged?'已查收（满意）':'已收到，等待处理回执');
  window.ChangyingFeedbackCenter=Object.freeze({statusLabel,statusClass,rewardText,receiptText});
})();
