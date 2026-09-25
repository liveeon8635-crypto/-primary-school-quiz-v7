"""Context-aware product assistant and feedback channel for Changying V1.

The assistant is available only after an authenticated account has selected an
identity. Product questions are answered with product-only context; feedback is
recorded through the existing audit log so no new schema is required.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from types import ModuleType

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from changying.web import v1 as v1_module


V1_PRODUCT_ASSISTANT_MARKER = "changying_v1_product_assistant_v1"
QUERY_PATH = "/v1/product-assistant/query"
FEEDBACK_PATH = "/v1/product-feedback"
FEEDBACK_PROOF_PREFIX = "/v1/product-feedback/proof"
FREEMAN_FEEDBACK_IMPORT_URL = "https://freeman-agent.onrender.com/api/project-feedback/import"
FEEDBACK_PROOF_TTL_MINUTES = 15


class ProductAssistantBody(BaseModel):
    question: str = Field(min_length=1, max_length=1600)
    page: str = Field(default="", max_length=240)
    identity: str = Field(default="", max_length=160)
    tutorial_step: str = Field(default="", max_length=200)


class ProductFeedbackBody(BaseModel):
    category: str = Field(default="其他反馈", max_length=60)
    message: str = Field(min_length=1, max_length=1200)
    page: str = Field(default="", max_length=240)
    identity: str = Field(default="", max_length=160)
    tutorial_step: str = Field(default="", max_length=200)


_PRODUCT_CONTEXT = """你是“长缨辅学”的产品内智能助手。只回答长缨产品怎么用、当前页面用途、不同身份功能、操作顺序和产品反馈相关问题。

核心原则：
1. 学生始终是一份连续档案；换班、换教师、换学期、升年级不应重新创建学生。
2. 当前教学负责正在发生的教学；历史教学负责只读回看；升年级/升学用衔接记录表达阶段变化。
3. 教师主线：当前教学→学生连续档案→综合/模块测试或练习→教师审核布置→学生提交→分数/知识点/错题/积分回流→AI针对性练习→课堂复盘讲义→互动课堂/随堂检测→历史/升年级衔接。
4. 学生主线：课堂→作业→逐题作答→提交结果→针对性练习→学情→积分/错题/历史。
5. 家长主线：孩子课程→孩子作业→孩子学情→课堂表现/积分→连续档案与历史。
6. 管理员主线：平台总览→账号→班级与教学归属→积分规则→审计→系统设置→历史连续性。
7. 新手教学必须在账号登录并选择身份后出现；系统按当前身份顺序引导，每一步可跳过、退出保存、以后从“新手教学”继续。
8. 教师审核是重要边界；AI 可以生成建议或草稿，但不应自动替教师发布、评分确认或推进课堂。
9. 不要声称你读取了用户未提供的学生、班级、成绩或数据库数据。不要编造按钮、数据或已经发生的操作。
10. 用户问“我现在该做什么”时，根据身份、页面和新手步骤给 1-3 个明确动作；用户描述问题时，先解释当前功能，再指出应去哪个入口。
回答使用简洁中文，优先给可执行步骤。"""


def _local_answer(question: str, identity: str, page: str, tutorial_step: str) -> str:
    text = question.strip()
    context = f"当前身份：{identity or '已登录身份'}；当前页面：{page or 'V1'}"
    if tutorial_step:
        context += f"；新手步骤：{tutorial_step}"

    if any(k in text for k in ("现在该做", "下一步", "从哪里开始")):
        return (
            f"{context}。建议先按右上角“新手教学”的当前步骤继续，不要跳到其他功能。"
            "如果已经退出教学：教师从“当前教学”开始，学生从“作业/课堂”开始，家长从“孩子课程”开始，管理员从“平台总览”开始。"
        )
    if any(k in text for k in ("学生档案", "连续档案")):
        return "学生连续档案是长缨的主线：成绩、作业、错题、知识点、积分、课堂表现、家长关系和阶段变化都围绕同一个学生 ID 累积。"
    if any(k in text for k in ("针对性", "AI练习", "ai练习")):
        return "AI 针对性练习应基于最近测试、知识点正确率和具体错题生成；教师审核后再布置，学生提交后结果继续回流同一学生档案。"
    if any(k in text for k in ("课堂复盘", "讲义", "互动课堂", "随堂检测")):
        return "课堂链条是：班级练习数据汇总→教师决定生成复盘讲义→确认发布版本→选择讲解方式→需要时邀请学生→开放随堂检测→教师查看反馈并收口。系统不应自动发布或自动推进课堂。"
    if any(k in text for k in ("升年级", "升学", "历史")):
        return "升年级或换班不会重新建学生。当前教学关系发生变化，旧班级和旧学期进入历史；衔接计划继续引用同一个学生 ID。"
    return (
        f"{context}。我可以解释这个页面的用途、告诉你下一步怎么操作，或帮你定位教师/学生/家长/管理员对应功能。"
        "如果你是在反馈产品问题，也可以切到“反馈”直接提交当前页面问题。"
    )


def install_v1_product_assistant_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v1_product_assistant_routes_installed", False):
        return

    router = APIRouter()

    @router.post(QUERY_PATH, include_in_schema=False)
    def product_assistant_query(
        body: ProductAssistantBody,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        question = body.question.strip()
        prompt = (
            _PRODUCT_CONTEXT
            + "\n\n当前上下文："
            + f"账号角色={getattr(user, 'role', '')}; 身份={body.identity}; 页面={body.page}; 新手步骤={body.tutorial_step or '无'}。"
            + "\n用户问题："
            + question
        )
        try:
            reply = implementation._ai_call(
                db,
                user,
                "product_assistant",
                prompt,
                timeout=45,
            )
            return {"ok": True, "reply": reply[:5000], "source": "ai", "degraded": False}
        except HTTPException:
            return {
                "ok": True,
                "reply": _local_answer(question, body.identity, body.page, body.tutorial_step),
                "source": "local",
                "degraded": True,
            }
        except Exception:
            return {
                "ok": True,
                "reply": _local_answer(question, body.identity, body.page, body.tutorial_step),
                "source": "local",
                "degraded": True,
            }

    @router.post(FEEDBACK_PATH, include_in_schema=False)
    def product_feedback(
        body: ProductFeedbackBody,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        proof_token = secrets.token_urlsafe(24)
        payload = {
            "category": body.category.strip() or "其他反馈",
            "message": body.message.strip(),
            "page": body.page.strip(),
            "identity": body.identity.strip(),
            "tutorialStep": body.tutorial_step.strip(),
            "transferToken": proof_token,
        }
        implementation.audit(
            db,
            user,
            "product.feedback",
            json.dumps(payload, ensure_ascii=False)[:1800],
        )
        db.commit()

        synced = False
        try:
            response = requests.post(
                FREEMAN_FEEDBACK_IMPORT_URL,
                json={"projectId": "longying", "proofToken": proof_token},
                timeout=4,
            )
            synced = bool(response.ok)
        except requests.RequestException:
            synced = False
        return {"ok": True, "received": True, "freemanSynced": synced}

    @router.get(FEEDBACK_PROOF_PREFIX + "/{proof_token}", include_in_schema=False)
    def product_feedback_proof(proof_token: str, db=Depends(implementation.get_db)):
        token = str(proof_token or "").strip()
        if len(token) < 24 or len(token) > 96:
            raise HTTPException(404, "反馈凭证不存在")
        row = db.scalar(
            select(implementation.AuditLog)
            .where(
                implementation.AuditLog.action == "product.feedback",
                implementation.AuditLog.detail.contains(token),
            )
            .order_by(implementation.AuditLog.id.desc())
            .limit(1)
        )
        if not row:
            raise HTTPException(404, "反馈凭证不存在")
        created_at = row.created_at or datetime.utcnow()
        if datetime.utcnow() - created_at > timedelta(minutes=FEEDBACK_PROOF_TTL_MINUTES):
            raise HTTPException(410, "反馈凭证已过期")
        try:
            payload = json.loads(row.detail or "{}")
        except Exception:
            raise HTTPException(404, "反馈凭证无效")
        if payload.get("transferToken") != token:
            raise HTTPException(404, "反馈凭证无效")
        return {
            "ok": True,
            "projectId": "longying",
            "feedback": {
                "sourceId": row.id,
                "category": str(payload.get("category") or "其他反馈")[:60],
                "message": str(payload.get("message") or "")[:1200],
                "page": str(payload.get("page") or "")[:240],
                "identity": str(payload.get("identity") or "")[:160],
                "tutorialStep": str(payload.get("tutorialStep") or "")[:200],
                "createdAt": created_at.isoformat() + "Z",
            },
        }

    app.include_router(router)
    app.state.v1_product_assistant_routes_installed = True


_ASSISTANT_SNIPPET = r'''
<style id="changying_v1_product_assistant_v1-css">
  #cy-product-assistant-fab{position:fixed;right:16px;bottom:calc(84px + env(safe-area-inset-bottom));z-index:125;border:0;border-radius:999px;background:#173a78;color:#fff;padding:13px 16px;font-weight:850;box-shadow:0 12px 34px rgba(23,58,120,.28);display:flex;align-items:center;gap:7px}
  #cy-product-assistant-panel{position:fixed;right:14px;bottom:calc(142px + env(safe-area-inset-bottom));z-index:126;width:min(390px,calc(100vw - 28px));max-height:min(620px,70dvh);background:#fff;border:1px solid #dbe4f1;border-radius:20px;box-shadow:0 22px 70px rgba(17,34,64,.28);overflow:hidden;display:flex;flex-direction:column}
  .cy-pa-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:14px 15px;border-bottom:1px solid #e2e8f1}.cy-pa-head b{display:block}.cy-pa-head small{color:var(--muted);line-height:1.45}
  .cy-pa-tabs{display:grid;grid-template-columns:1fr 1fr;padding:9px;gap:7px;background:#f7f9fc}.cy-pa-tab{border:1px solid #dbe4f1;background:#fff;border-radius:11px;padding:9px;font-weight:750}.cy-pa-tab.active{background:#eaf1ff;border-color:#bfd2f4;color:#173a78}
  .cy-pa-body{padding:12px;overflow:auto}.cy-pa-quick{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px}.cy-pa-quick button{border:1px solid #dbe4f1;background:#fff;border-radius:999px;padding:7px 9px;font-size:12px}
  .cy-pa-chat{display:grid;gap:9px;margin-bottom:10px}.cy-pa-msg{max-width:92%;padding:10px 11px;border-radius:13px;line-height:1.55;font-size:13px;white-space:pre-wrap}.cy-pa-msg.user{justify-self:end;background:#173a78;color:#fff}.cy-pa-msg.assistant{justify-self:start;background:#f1f5fb;color:#1c2940}
  .cy-pa-compose{display:grid;grid-template-columns:1fr auto;gap:7px}.cy-pa-compose textarea{min-height:68px;resize:none}.cy-pa-compose .btn{align-self:end}
  .cy-pa-feedback{display:grid;gap:9px}.cy-pa-feedback textarea{min-height:110px}.cy-pa-note{font-size:11px;color:var(--muted);line-height:1.5}
  @media(max-width:640px){#cy-product-assistant-fab{right:12px;bottom:calc(78px + env(safe-area-inset-bottom));padding:12px 14px}#cy-product-assistant-panel{left:8px;right:8px;bottom:calc(132px + env(safe-area-inset-bottom));width:auto;max-height:68dvh}}
</style>
<button id="cy-product-assistant-fab" hidden>✦ 产品助手</button>
<section id="cy-product-assistant-panel" hidden aria-label="长缨产品助手">
  <header class="cy-pa-head"><div><b>长缨产品助手</b><small id="cy-pa-context">读取当前身份与页面…</small></div><button class="btn" id="cy-pa-close">关闭</button></header>
  <div class="cy-pa-tabs"><button class="cy-pa-tab active" data-pa-tab="ask">问产品</button><button class="cy-pa-tab" data-pa-tab="feedback">提反馈</button></div>
  <div class="cy-pa-body" id="cy-pa-ask">
    <div class="cy-pa-quick"><button data-pa-question="我现在该做什么？">我现在该做什么？</button><button data-pa-question="这个页面是干什么的？">这个页面是干什么的？</button><button data-pa-question="这一步为什么排在这里？">为什么先做这一步？</button></div>
    <div class="cy-pa-chat" id="cy-pa-chat"><div class="cy-pa-msg assistant">我会结合你当前登录身份、所在页面和新手教学步骤回答长缨怎么用。</div></div>
    <div class="cy-pa-compose"><textarea id="cy-pa-input" placeholder="例如：这个页面应该先做什么？"></textarea><button class="btn primary" id="cy-pa-send">发送</button></div>
  </div>
  <div class="cy-pa-body" id="cy-pa-feedback" hidden>
    <div class="cy-pa-feedback"><select id="cy-pa-category"><option>这里不好懂</option><option>没找到入口</option><option>流程不直观</option><option>功能与预期不符</option><option>希望增加功能</option><option>其他反馈</option></select><textarea id="cy-pa-feedback-text" placeholder="请描述你遇到的问题或建议。不要填写密码、API Key 等敏感信息。"></textarea><button class="btn primary" id="cy-pa-submit-feedback">提交反馈</button><div class="cy-pa-note">会自动附带当前页面、当前身份和正在进行的新手步骤，便于定位问题。</div></div>
  </div>
</section>
<script id="changying_v1_product_assistant_v1-script">
(()=>{
  if(window.__cyV1ProductAssistantInstalled)return;
  window.__cyV1ProductAssistantInstalled=true;
  const fab=document.getElementById('cy-product-assistant-fab'),panel=document.getElementById('cy-product-assistant-panel');
  const identityButton=document.getElementById('identityButton'),identityChip=document.getElementById('identityChip');
  const chat=document.getElementById('cy-pa-chat'),input=document.getElementById('cy-pa-input'),send=document.getElementById('cy-pa-send');
  const REMEMBER_KEY='v717Remember';
  const authRemember=()=>localStorage.getItem(REMEMBER_KEY)==='1';
  const authStore=()=>authRemember()?localStorage:sessionStorage;
  const readToken=()=>authStore().getItem('v717Token')||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||'';
  const identityReady=()=>Boolean(identityButton&&identityButton.hidden===false&&readToken());
  const tutorialStep=()=>document.querySelector('.cy-lesson-top h2')?.textContent?.trim()||'';
  const context=()=>({page:location.pathname+location.search,identity:String(identityChip?.textContent||'').trim(),tutorial_step:tutorialStep()});
  const escapeHtml=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const addMessage=(kind,text)=>{const el=document.createElement('div');el.className='cy-pa-msg '+kind;el.textContent=text;chat.appendChild(el);chat.scrollTop=chat.scrollHeight};
  const updateContext=()=>{const c=context();document.getElementById('cy-pa-context').textContent=(c.identity||'当前身份')+' · '+c.page+(c.tutorial_step?' · '+c.tutorial_step:'')};

  async function postJson(path,body){
    const token=readToken();if(!token)throw new Error('登录状态已失效，请重新登录');
    const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify(body)});
    let data={};try{data=await r.json()}catch{}
    if(!r.ok)throw new Error(data.detail||'请求失败');
    return data;
  }

  async function ask(question){
    const text=String(question||'').trim();if(!text)return;
    addMessage('user',text);input.value='';send.disabled=true;send.textContent='回答中…';
    try{
      const data=await postJson('/v1/product-assistant/query',{question:text,...context()});
      addMessage('assistant',data.reply||'暂时没有可用回答。');
    }catch(err){addMessage('assistant','产品助手暂时无法回答：'+err.message)}
    finally{send.disabled=false;send.textContent='发送'}
  }

  function setTab(name){
    document.querySelectorAll('.cy-pa-tab').forEach(x=>x.classList.toggle('active',x.dataset.paTab===name));
    document.getElementById('cy-pa-ask').hidden=name!=='ask';
    document.getElementById('cy-pa-feedback').hidden=name!=='feedback';
    updateContext();
  }

  fab.onclick=()=>{panel.hidden=false;updateContext()};
  document.getElementById('cy-pa-close').onclick=()=>panel.hidden=true;
  document.querySelectorAll('.cy-pa-tab').forEach(x=>x.onclick=()=>setTab(x.dataset.paTab));
  document.querySelectorAll('[data-pa-question]').forEach(x=>x.onclick=()=>ask(x.dataset.paQuestion));
  send.onclick=()=>ask(input.value);
  input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();ask(input.value)}});

  document.getElementById('cy-pa-submit-feedback').onclick=async()=>{
    const message=document.getElementById('cy-pa-feedback-text').value.trim();
    if(!message)return;
    const btn=document.getElementById('cy-pa-submit-feedback');btn.disabled=true;btn.textContent='提交中…';
    try{
      await postJson('/v1/product-feedback',{category:document.getElementById('cy-pa-category').value,message,...context()});
      document.getElementById('cy-pa-feedback-text').value='';
      btn.textContent='已收到，谢谢 ✓';
      setTimeout(()=>{btn.textContent='提交反馈';btn.disabled=false},1600);
    }catch(err){btn.textContent='提交失败，重试';btn.disabled=false}
  };

  const sync=()=>{const ready=identityReady();if(fab.hidden===ready)fab.hidden=!ready;if(!ready){panel.hidden=true;return}updateContext()};
  const identityObserver=new MutationObserver(()=>queueMicrotask(sync));
  if(identityButton)identityObserver.observe(identityButton,{attributes:true,attributeFilter:['hidden']});
  if(identityChip)identityObserver.observe(identityChip,{childList:true,characterData:true,subtree:true});
  window.addEventListener('pageshow',sync);window.addEventListener('popstate',sync);
  setTimeout(sync,0);setTimeout(sync,300);
})();
</script>
'''


def patch_v1_product_assistant(html: str) -> str:
    if V1_PRODUCT_ASSISTANT_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 product assistant: closing body marker not found")
    return html.replace(
        "</body>",
        _ASSISTANT_SNIPPET + f"\n<!-- {V1_PRODUCT_ASSISTANT_MARKER} -->\n</body>",
        1,
    )


def install_v1_product_assistant_patch() -> None:
    if getattr(v1_module, "_product_assistant_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_product_assistant(original())

    v1_module.v1_html = patched_v1_html
    v1_module._product_assistant_patch_installed = True


__all__ = [
    "FEEDBACK_PATH",
    "FEEDBACK_PROOF_PREFIX",
    "QUERY_PATH",
    "V1_PRODUCT_ASSISTANT_MARKER",
    "install_v1_product_assistant_patch",
    "install_v1_product_assistant_routes",
    "patch_v1_product_assistant",
]
