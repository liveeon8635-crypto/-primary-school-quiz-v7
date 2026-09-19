"""Final V1 acceptance patch for mixed-type reinforcement review cards.

This patch is deliberately installed after the other V1 HTML patches so the
teacher review surface cannot fall back to the older choice-only renderer.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_REINFORCEMENT_FIX_MARKER = "changying_v1_reinforcement_acceptance_fix_v1"


def _patch_html() -> str:
    return r'''
<style id="changying_v1_reinforcement_acceptance_fix_v1-style">
.cy-ai-question .cy-rf-meta{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:8px}
.cy-ai-question .cy-rf-tag{display:inline-flex;padding:4px 8px;border:1px solid #d9e3f2;border-radius:999px;background:#f8fbff;color:#526178;font-size:11px;font-weight:800}
.cy-ai-question .cy-rf-options{margin-top:8px;color:#667085;line-height:1.7}
.cy-ai-question .cy-rf-answer{margin-top:9px;color:#667085;line-height:1.65}
.cy-ai-question .cy-rf-figure{margin:10px 0;padding:9px;border:1px solid #dce5f0;border-radius:12px;background:#fff}
.cy-ai-question .cy-rf-figure svg{width:100%;max-width:420px;display:block;margin:auto}
</style>
<script id="changying_v1_reinforcement_acceptance_fix_v1-script">
(()=>{
 if(window.__cyReinforcementAcceptanceFix)return;window.__cyReinforcementAcceptanceFix=true;
 const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
 const typeLabel=q=>({single_choice:'单选题',choice:'单选题',true_false:'判断题',fill_blank:'填空题',calculation:'计算题',short_answer:'应用简答题'})[String(q?.question_type||q?.questionType||'').toLowerCase()]||'练习题';
 const choiceLike=q=>{const t=String(q?.question_type||q?.questionType||'').toLowerCase();return ['single_choice','choice','true_false'].includes(t)||(((q?.options||[]).length>0)&&!['fill_blank','calculation','short_answer'].includes(t))};
 function figureHtml(fig){
   if(!fig||!fig.type)return '';
   const type=String(fig.type||'').toLowerCase(),w=320,h=210,m=28,num=(v,d=0)=>Number.isFinite(+v)?+v:d;let body='';
   if(type==='coordinate_grid'){
     const xm=Math.max(1,Math.min(12,num(fig.xMax,8))),ym=Math.max(1,Math.min(12,num(fig.yMax,8))),sx=(w-2*m)/xm,sy=(h-2*m)/ym;
     for(let x=0;x<=xm;x++){const px=m+x*sx;body+='<line x1="'+px+'" y1="'+m+'" x2="'+px+'" y2="'+(h-m)+'" stroke="#d8dee9"/><text x="'+px+'" y="'+(h-m+17)+'" text-anchor="middle" font-size="10">'+x+'</text>'}
     for(let y=0;y<=ym;y++){const py=h-m-y*sy;body+='<line x1="'+m+'" y1="'+py+'" x2="'+(w-m)+'" y2="'+py+'" stroke="#d8dee9"/><text x="'+(m-9)+'" y="'+(py+3)+'" text-anchor="middle" font-size="10">'+y+'</text>'}
     (fig.points||[]).forEach(p=>{const px=m+num(p.x)*sx,py=h-m-num(p.y)*sy;body+='<circle cx="'+px+'" cy="'+py+'" r="4" fill="#111827"/><text x="'+(px+7)+'" y="'+(py-7)+'" font-size="12">'+esc(p.label||p.name||'')+'</text>'});
   }else if(type==='geometry'){
     const shape=String(fig.shape||'rectangle').toLowerCase();
     if(shape==='triangle')body='<polygon points="65,170 255,170 160,45" fill="none" stroke="#374151" stroke-width="3"/>';
     else if(shape==='trapezoid')body='<polygon points="85,55 225,55 270,170 45,170" fill="none" stroke="#374151" stroke-width="3"/>';
     else if(shape==='parallelogram')body='<polygon points="90,55 260,55 225,170 55,170" fill="none" stroke="#374151" stroke-width="3"/>';
     else if(shape==='composite_rect')body='<path d="M55 45 H265 V170 H145 V110 H55 Z" fill="none" stroke="#374151" stroke-width="3"/>';
     else body='<rect x="55" y="50" width="210" height="120" fill="none" stroke="#374151" stroke-width="3"/>';
     const labels=fig.labels||{};let y=202;Object.keys(labels).slice(0,4).forEach(k=>{body+='<text x="'+m+'" y="'+y+'" font-size="11">'+esc(k)+'：'+esc(labels[k])+'</text>';y-=15});
   }else if(type==='line_segment'){
     const segs=(fig.segments||[]).length?fig.segments:[{label:'间隔',ratio:1}],total=segs.reduce((sum,x)=>sum+Math.max(.1,num(x.ratio,1)),0);let x=m;
     segs.forEach((seg,idx)=>{const ww=(w-2*m)*Math.max(.1,num(seg.ratio,1))/total;body+='<line x1="'+x+'" y1="105" x2="'+(x+ww)+'" y2="105" stroke="#374151" stroke-width="4"/><line x1="'+x+'" y1="96" x2="'+x+'" y2="114" stroke="#374151" stroke-width="2"/><text x="'+(x+ww/2)+'" y="88" text-anchor="middle" font-size="11">'+esc(seg.label||('第'+(idx+1)+'段'))+'</text>';x+=ww});body+='<line x1="'+x+'" y1="96" x2="'+x+'" y2="114" stroke="#374151" stroke-width="2"/>';
   }else if(type==='bar_chart'){
     const bars=(fig.bars||[]).slice(0,8),max=Math.max(1,...bars.map(x=>num(x.value,0))),bw=Math.max(18,(w-2*m)/Math.max(1,bars.length)-10);
     body+='<line x1="'+m+'" y1="'+(h-m)+'" x2="'+(w-m)+'" y2="'+(h-m)+'" stroke="#374151"/>';
     bars.forEach((bar,idx)=>{const bh=(h-2*m)*num(bar.value,0)/max,x=m+idx*((w-2*m)/Math.max(1,bars.length))+5,y=h-m-bh;body+='<rect x="'+x+'" y="'+y+'" width="'+bw+'" height="'+bh+'" fill="#9ca3af"/><text x="'+(x+bw/2)+'" y="'+(h-m+15)+'" text-anchor="middle" font-size="10">'+esc(bar.name||bar.label||'')+'</text>'});
   }else if(type==='object_group'){
     const groups=(fig.groups||[]).slice(0,6);let y=48;groups.forEach(g=>{const count=Math.max(0,Math.min(12,Math.round(num(g.count,0)))),symbol=esc(g.symbol||'●');body+='<text x="25" y="'+y+'" font-size="13">'+esc(g.label||g.name||'')+'：</text><text x="105" y="'+y+'" font-size="18">'+Array(count).fill(symbol).join(' ')+'</text>';y+=28});
   }else return '';
   const title=fig.title?'<div style="text-align:center;color:#667085;font-size:12px;margin-bottom:4px">'+esc(fig.title)+'</div>':'';
   return '<div class="cy-rf-figure">'+title+'<svg viewBox="0 0 '+w+' '+h+'" role="img" aria-label="题目图示">'+body+'</svg></div>';
 }
 function renderLatest(){
   const draft=window.__cyLatestReinforcementDraft,cards=[...document.querySelectorAll('.cy-ai-question')];
   if(!draft||!Array.isArray(draft.items)||!cards.length||cards.length!==draft.items.length)return;
   cards.forEach((card,i)=>{
     const q=draft.items[i]||{},options=q.options||[],choice=choiceLike(q),ci=Number(q.correct_index),figure=figureHtml(q.figure||{});
     const optionHtml=choice&&options.length?'<div class="cy-rf-options">'+options.map((x,j)=>String.fromCharCode(65+j)+'. '+esc(x)).join('<br>')+'</div>':'';
     const answer=choice?(Number.isInteger(ci)&&ci>=0?String.fromCharCode(65+ci)+' · '+esc(options[ci]||''):''):esc(q.answer||'');
     const accepted=(q.accepted_answers||[]).length?' <span>可接受：'+esc(q.accepted_answers.join(' / '))+'</span>':'';
     card.innerHTML='<div class="cy-rf-meta"><span class="cy-rf-tag">'+esc(typeLabel(q))+'</span><span class="cy-rf-tag">'+esc(q.knowledge||'知识点')+'</span></div><b>'+(i+1)+'. '+esc(q.text||'')+'</b>'+figure+optionHtml+'<div class="cy-rf-answer">'+esc(q.textbook||'')+(q.textbook&&q.knowledge?' · ':'')+esc(q.knowledge||'')+'<br><b>参考答案：</b>'+answer+accepted+(q.explanation?' · '+esc(q.explanation):'')+'</div>';
   });
 }
 const originalFetch=window.fetch.bind(window);
 window.fetch=async(...args)=>{
   const response=await originalFetch(...args);
   try{
     const input=args[0],url=typeof input==='string'?input:(input?.url||'');
     if(url.includes('/teacher/students/')&&url.includes('/reinforcement/generate')&&response.ok){
       response.clone().json().then(data=>{window.__cyLatestReinforcementDraft=data;setTimeout(renderLatest,0);setTimeout(renderLatest,80)}).catch(()=>{});
     }
   }catch(_){}
   return response;
 };
 const observer=new MutationObserver(()=>renderLatest());observer.observe(document.documentElement,{subtree:true,childList:true});
})();
</script>
'''


def patch_v1_reinforcement_acceptance_html(html: str) -> str:
    if V1_REINFORCEMENT_FIX_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 reinforcement acceptance patch: closing body marker not found")
    return html.replace("</body>", _patch_html() + "\n</body>", 1)


def install_v1_reinforcement_acceptance_fix() -> None:
    if getattr(v1_module, "_reinforcement_acceptance_fix_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_reinforcement_acceptance_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._reinforcement_acceptance_fix_installed = True


__all__ = [
    "V1_REINFORCEMENT_FIX_MARKER",
    "install_v1_reinforcement_acceptance_fix",
    "patch_v1_reinforcement_acceptance_html",
]
