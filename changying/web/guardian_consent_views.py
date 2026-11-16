"""Guardian AI consent endpoints, personal AI settings UI patch, and egress guard (P0-1 + P0-2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from changying.services.guardian_consent import (
    DEFAULT_VALID_DAYS,
    TOKEN_TTL_HOURS,
    compliance_student_ai_enabled,
    confirm_consent_token,
    create_consent_token,
    install_ai_egress_guard,
    record_proof_consent,
    register_guardian_consent_tables,
    revoke_student_consent,
    verify_proof_consent,
)
from changying.web.design_system import apply_surface


class TokenCreateBody(BaseModel):
    scope: str = Field(default="student_ai_all", max_length=64)
    policyVersion: str = Field(default="v1.0", max_length=32)
    validDays: int = Field(default=DEFAULT_VALID_DAYS, ge=1, le=365)
    ttlHours: int = Field(default=TOKEN_TTL_HOURS, ge=1, le=720)


class ProofConsentBody(BaseModel):
    verificationMethod: str = Field(default="written_proof", max_length=32)
    proofDigest: str = Field(min_length=6, max_length=128)
    scope: str = Field(default="student_ai_all", max_length=64)
    policyVersion: str = Field(default="v1.0", max_length=32)
    validDays: int = Field(default=DEFAULT_VALID_DAYS, ge=1, le=365)


class ProofVerifyBody(BaseModel):
    approved: bool = True


class TokenConfirmBody(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    studentId: int | None = None


class RevokeBody(BaseModel):
    scope: str | None = Field(default=None, max_length=64)
    reason: str = Field(default="", max_length=200)


PERSONAL_AI_HTML_V2 = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>我的 AI 设置 · 长缨辅学</title>
<style>
:root{--ink:#1f2738;--muted:#778095;--line:#e5e8f0;--brand:#a8101c;--ok:#0b8f5a}
*{box-sizing:border-box}body{margin:0;background:#f4f6fb;color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
main{max-width:660px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:22px;margin:0 0 4px}p.sub{color:var(--muted);margin:0 0 18px;font-size:14px}
.card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:14px}
label{display:block;font-size:13.5px;font-weight:700;margin:14px 0 6px}
input,select{width:100%;border:1px solid #cfd7e5;border-radius:10px;padding:11px 12px;font:inherit;background:#fff}
.hint{color:var(--muted);font-size:12.5px;margin-top:6px;line-height:1.5}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}
button{border:0;border-radius:10px;padding:10px 16px;font:inherit;font-weight:700;cursor:pointer}
button.primary{background:var(--brand);color:#fff}
button.plain{background:#eef2fa;color:var(--brand)}
button:disabled{opacity:.6;cursor:wait}
.status{margin-top:14px;font-size:13.5px;line-height:1.6;color:var(--muted)}
.status.ok{color:var(--ok)}.status.err{color:#b91c1c}
a.back{display:inline-block;margin-top:6px;color:var(--brand);text-decoration:none;font-weight:700}
</style></head><body><main>
<h1>我的 AI 设置</h1>
<p class="sub">个人免费版：模型由你自己提供，Key 只保存在这间工作室，费用也由你自己承担。</p>
<div class="card">
<div id="cy-status" class="status">正在读取当前设置…</div>
<label for="cy-provider">接口协议</label>
<select id="cy-provider">
<option value="openai_responses">OpenAI Responses API（/responses）</option>
<option value="openai_compatible">OpenAI 兼容接口（/chat/completions）</option>
</select>
<div class="hint">DeepSeek、通义千问等中转或兼容服务请选择「OpenAI 兼容接口」。</div>
<label for="cy-base">模型地址</label>
<input id="cy-base" autocomplete="off" placeholder="https://api.openai.com/v1">
<div class="hint">一般保持默认；用中转或自建服务时才改。</div>
<label for="cy-model">模型名</label>
<input id="cy-model" autocomplete="off" placeholder="例如 gpt-4o-mini">
<label for="cy-key">API Key</label>
<input id="cy-key" type="password" autocomplete="off" placeholder="粘贴你的 Key">
<div class="hint">保存后不再显示完整 Key，只显示末四位；留空表示不修改已保存的 Key。</div>
<label style="display:flex;align-items:center;gap:8px;font-weight:600;margin-top:14px">
<input id="cy-allow-student" type="checkbox" style="width:auto"> 允许将经监护人授权的学生内容发送给外部 AI
</label>
<div class="hint">默认关闭。开启后仍须学生监护人单独确认授权且平台合规开关开放，方可外发真实学生数据。</div>
<div class="actions">
<button class="primary" id="cy-save">保存</button>
<button class="plain" id="cy-test">测试连接</button>
</div>
<div id="cy-msg" class="status"></div>
</div>
<a class="back" href="/start">← 返回我的工作室</a>
</main>
<script>
(function(){
  function token(){try{return localStorage.getItem('v717Token')||sessionStorage.getItem('v717Token')||''}catch(e){return ''}}
  var t=token();
  function el(id){return document.getElementById(id)}
  function setStatus(text,cls){var s=el('cy-status');if(!s)return;s.textContent=text;s.className='status'+(cls?' '+cls:'')}
  function msg(text,cls){var m=el('cy-msg');if(!m)return;m.textContent=text;m.className='status'+(cls?' '+cls:'')}
  if(!t){setStatus('请先用你的账号登录，再从工作台打开这个页面。','err');if(el('cy-save'))el('cy-save').disabled=true;if(el('cy-test'))el('cy-test').disabled=true;return}
  function send(method,url,body,cb){
    var x=new XMLHttpRequest();
    x.open(method,url,true);
    x.setRequestHeader('Authorization','Bearer '+t);
    if(body)x.setRequestHeader('Content-Type','application/json');
    x.onload=function(){var d=null;try{d=JSON.parse(x.responseText)}catch(e){}cb(x.status,d)};
    x.onerror=function(){cb(0,null)};
    x.send(body?JSON.stringify(body):null);
  }
  var hasKey=false;
  var currentProvider='openai_responses';
  function apply(d){
    if(!d)return;
    currentProvider=d.provider||'openai_responses';
    if(el('cy-provider'))el('cy-provider').value=currentProvider;
    el('cy-base').value=d.baseURL||'';
    el('cy-model').value=d.configuredModel||d.model||'';
    if(el('cy-allow-student'))el('cy-allow-student').checked=!!d.allowStudentData;
    hasKey=!!d.hasKey;
    if(d.configured&&d.enabled){
      el('cy-key').placeholder='已保存，留空表示不修改';
      setStatus('已配置并启用（协议：'+currentProvider+'，Key 末四位 '+(d.keyLast4||'****')+'），可点「测试连接」。','ok');
    }else if(hasKey){
      el('cy-key').placeholder='已保存，留空表示不修改';
      setStatus('已保存 Key（末四位 '+(d.keyLast4||'****')+'），但尚未启用或缺少模型名。','');
    }else{
      setStatus('未配置：请填写模型地址、模型名和 API Key。','');
    }
  }
  send('GET','/teacher/ai-config',null,function(s,d){
    if(s===200)apply(d);else setStatus((d&&d.detail)||'读取失败，请刷新重试','err');
  });
  el('cy-save').onclick=function(){
    var prov=(el('cy-provider')?el('cy-provider').value:currentProvider)||currentProvider||'openai_responses';
    var allowStudent=!!(el('cy-allow-student')&&el('cy-allow-student').checked);
    var body={provider:prov,base_url:el('cy-base').value.trim(),model:el('cy-model').value.trim(),api_key:el('cy-key').value.trim(),enabled:true,allow_student_data:allowStudent,clear_api_key:false};
    if(!body.model){msg('请先填写模型名','err');return}
    if(!body.api_key&&!hasKey){msg('请填写 API Key','err');return}
    el('cy-save').disabled=true;msg('正在保存…','');
    send('PUT','/teacher/ai-config',body,function(s,d){
      el('cy-save').disabled=false;
      if(s===200){el('cy-key').value='';msg('已保存，可以点「测试连接」确认能不能用。','ok');if(d&&d.config)apply(d.config)}
      else{msg((d&&d.detail)||'保存失败，请重试','err')}
    });
  };
  el('cy-test').onclick=function(){
    el('cy-test').disabled=true;msg('正在连接…','');
    send('POST','/teacher/ai-test',{},function(s,d){
      el('cy-test').disabled=false;
      if(s===200){msg('连接成功：'+((d&&d.reply)||'模型已响应'),'ok')}
      else{msg((d&&d.detail)||'连接失败，请检查地址、模型名和 Key','err')}
    });
  };
})();
</script></body></html>"""


PARENT_CONSENT_PAGE_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>监护人 AI 授权确认 · 长缨辅学</title>
<style>
:root{--ink:#1f2738;--muted:#778095;--line:#e5e8f0;--brand:#a8101c;--ok:#0b8f5a}
*{box-sizing:border-box}body{margin:0;background:#f4f6fb;color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
main{max-width:600px;margin:0 auto;padding:24px 16px 60px}
.card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:14px}
h1{font-size:21px;margin:0 0 6px}p.sub{color:var(--muted);font-size:14px;margin:0 0 14px}
label{display:block;font-size:13.5px;font-weight:700;margin:12px 0 6px}
input{width:100%;border:1px solid #cfd7e5;border-radius:10px;padding:10px 12px;font:inherit}
.actions{display:flex;gap:8px;margin-top:16px;flex-wrap:wrap}
button{border:0;border-radius:10px;padding:10px 16px;font:inherit;font-weight:700;cursor:pointer}
button.primary{background:var(--brand);color:#fff}
button.plain{background:#eef2fa;color:var(--brand)}
.status{margin-top:12px;font-size:13.5px;color:var(--muted)}.status.ok{color:var(--ok)}.status.err{color:#b91c1c}
</style></head><body><main>
<h1>监护人 AI 授权确认</h1>
<p class="sub">仅已登录并绑定对应学生的家长账号可确认或撤回 AI 授权。</p>
<div class="card">
<label for="gc-token">授权确认令牌</label>
<input id="gc-token" placeholder="粘贴授权令牌">
<label for="gc-student">学生编号（选填）</label>
<input id="gc-student" placeholder="学生 ID">
<div class="actions">
<button class="primary" id="gc-confirm">确认授权</button>
<button class="plain" id="gc-revoke">撤回授权</button>
</div>
<div id="gc-msg" class="status"></div>
</div></main>
<script>
(function(){
  function tok(){try{return localStorage.getItem('v717Token')||sessionStorage.getItem('v717Token')||''}catch(e){return ''}}
  function el(id){return document.getElementById(id)}
  var q=new URLSearchParams(location.search);
  if(q.get('token'))el('gc-token').value=q.get('token');
  if(q.get('studentId'))el('gc-student').value=q.get('studentId');
  function show(t,c){var m=el('gc-msg');m.textContent=t;m.className='status'+(c?' '+c:'')}
  function req(url,body,cb){
    var x=new XMLHttpRequest();x.open('POST',url,true);
    x.setRequestHeader('Authorization','Bearer '+tok());
    x.setRequestHeader('Content-Type','application/json');
    x.onload=function(){var d=null;try{d=JSON.parse(x.responseText)}catch(e){}cb(x.status,d)};
    x.send(JSON.stringify(body));
  }
  el('gc-confirm').onclick=function(){
    var sid=Number(el('gc-student').value.trim())||null;
    req('/parent/ai-consent/confirm',{token:el('gc-token').value.trim(),studentId:sid},function(s,d){
      if(s===200)show('授权已确认（'+d.status+'）','ok');
      else show((d&&d.detail)||'确认失败','err');
    });
  };
  el('gc-revoke').onclick=function(){
    var sid=Number(el('gc-student').value.trim());
    if(!sid){show('请填写学生编号后再撤回','err');return}
    req('/parent/children/'+sid+'/ai-consent/revoke',{reason:'parent_ui_revoke'},function(s,d){
      if(s===200)show('授权已撤回','ok');
      else show((d&&d.detail)||'撤回失败','err');
    });
  };
})();
</script></body></html>"""


def install_guardian_consent_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "guardian_consent_installed", False):
        return app.state.guardian_consent_router

    tables = register_guardian_consent_tables(implementation)
    consents_t, audits_t = tables["consents"], tables["audits"]
    # Upgrade PERSONAL_AI_HTML on the legacy module and install unified AI egress guard
    if hasattr(implementation, "PERSONAL_AI_HTML"):
        implementation.PERSONAL_AI_HTML = PERSONAL_AI_HTML_V2
    install_ai_egress_guard(implementation)

    if not getattr(app.state, "guardian_consent_sid_middleware_installed", False):
        import re as _re
        from changying.services.guardian_consent import _REQUEST_STUDENT_ID

        _reinforce_re = _re.compile(r"^/teacher/students/(\d+)/reinforcement/generate$")

        @app.middleware("http")
        async def _bind_student_id_for_reinforcement(request: Any, call_next: Any):
            m = _reinforce_re.match(request.url.path)
            if not m:
                return await call_next(request)
            token = _REQUEST_STUDENT_ID.set(int(m.group(1)))
            try:
                return await call_next(request)
            finally:
                _REQUEST_STUDENT_ID.reset(token)

        app.state.guardian_consent_sid_middleware_installed = True

    User = implementation.User
    ParentStudent = implementation.ParentStudent
    SchoolClass = implementation.SchoolClass
    ClassStudent = implementation.ClassStudent
    current_user = implementation.current_user
    get_db = implementation.get_db
    need = implementation.need

    router = APIRouter()

    def _teacher_owns_student(db: Any, teacher: Any, student_id: int) -> Any:
        stu = db.scalar(
            select(User).where(
                User.id == int(student_id),
                User.school_id == int(teacher.school_id),
                User.role == "student",
            )
        )
        if not stu:
            raise HTTPException(404, "未找到该学生")
        if teacher.role != "admin":
            in_my_class = db.scalar(
                select(ClassStudent.id)
                .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
                .where(
                    ClassStudent.student_id == stu.id,
                    SchoolClass.school_id == teacher.school_id,
                    SchoolClass.teacher_id == teacher.id,
                )
            )
            if not in_my_class:
                raise HTTPException(403, "无权管理其他教师名下学生的授权")
        return stu

    def _parent_linked_student(db: Any, parent: Any, student_id: int) -> None:
        link = db.scalar(
            select(ParentStudent.id).where(
                ParentStudent.parent_id == int(parent.id),
                ParentStudent.student_id == int(student_id),
            )
        )
        if not link:
            raise HTTPException(403, "无权访问未关联学生的授权记录")

    def _serialize_consents(db: Any, school_id: int, student_id: int) -> list[dict[str, Any]]:
        rows = db.execute(
            select(consents_t)
            .where(
                consents_t.c.school_id == int(school_id),
                consents_t.c.student_id == int(student_id),
            )
            .order_by(desc(consents_t.c.id))
            .limit(20)
        ).all()
        return [
            {
                "id": int(r.id),
                "studentId": int(r.student_id),
                "status": str(r.status),
                "scope": str(r.scope),
                "policyVersion": str(r.policy_version),
                "verificationMethod": str(r.verification_method),
                "verifiedAt": r.verified_at.isoformat(timespec="seconds") if r.verified_at else None,
                "validUntil": r.valid_until.isoformat(timespec="seconds") if r.valid_until else None,
                "retentionUntil": r.retention_until.isoformat(timespec="seconds") if r.retention_until else None,
                "revokedAt": r.revoked_at.isoformat(timespec="seconds") if r.revoked_at else None,
            }
            for r in rows
        ]

    @router.get("/parent/ai-consent-confirm", include_in_schema=False)
    def parent_consent_confirm_page():
        return HTMLResponse(
            apply_surface(PARENT_CONSENT_PAGE_HTML, "personal"),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    @router.get("/teacher/students/{student_id}/ai-consent")
    def teacher_get_consent(student_id: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher", "admin")
        _teacher_owns_student(db, u, student_id)
        audits = db.execute(
            select(audits_t)
            .where(
                audits_t.c.school_id == int(u.school_id),
                audits_t.c.student_id == int(student_id),
            )
            .order_by(desc(audits_t.c.id))
            .limit(20)
        ).all()
        return {
            "complianceApproved": compliance_student_ai_enabled(),
            "consents": _serialize_consents(db, int(u.school_id), int(student_id)),
            "audits": [
                {
                    "action": str(a.action),
                    "scope": str(a.scope),
                    "detail": str(a.detail),
                    "createdAt": a.created_at.isoformat(timespec="seconds") if a.created_at else None,
                }
                for a in audits
            ],
        }

    @router.post("/teacher/students/{student_id}/ai-consent/token")
    def teacher_create_consent_token(
        student_id: int,
        b: TokenCreateBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        _teacher_owns_student(db, u, student_id)
        return create_consent_token(
            db,
            implementation,
            teacher=u,
            student_id=student_id,
            scope=b.scope,
            policy_version=b.policyVersion,
            valid_days=b.validDays,
            ttl_hours=b.ttlHours,
        )

    @router.post("/teacher/students/{student_id}/ai-consent/proof")
    def teacher_record_proof_consent(
        student_id: int,
        b: ProofConsentBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        _teacher_owns_student(db, u, student_id)
        return record_proof_consent(
            db,
            implementation,
            teacher=u,
            student_id=student_id,
            verification_method=b.verificationMethod,
            proof_digest=b.proofDigest,
            scope=b.scope,
            policy_version=b.policyVersion,
            valid_days=b.validDays,
        )

    @router.post("/guardian-consents/{consent_id}/verify")
    def verify_pending_consent(
        consent_id: int,
        b: ProofVerifyBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "parent", "admin", "teacher")
        return verify_proof_consent(
            db,
            implementation,
            consent_id=consent_id,
            actor_user=u,
            approved=b.approved,
        )

    @router.post("/teacher/students/{student_id}/ai-consent/revoke")
    def teacher_revoke_consent(
        student_id: int,
        b: RevokeBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        _teacher_owns_student(db, u, student_id)
        return revoke_student_consent(
            db,
            implementation,
            school_id=int(u.school_id),
            student_id=int(student_id),
            actor_user_id=int(u.id),
            scope=b.scope,
            reason=b.reason,
        )

    @router.post("/parent/ai-consent/confirm")
    def parent_confirm_consent(
        b: TokenConfirmBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "parent")
        return confirm_consent_token(
            db,
            implementation,
            raw_token=b.token,
            parent_user=u,
            expected_student_id=b.studentId,
        )

    @router.get("/parent/children/{student_id}/ai-consent")
    def parent_get_consent(student_id: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "parent")
        _parent_linked_student(db, u, student_id)
        return {
            "complianceApproved": compliance_student_ai_enabled(),
            "consents": _serialize_consents(db, int(u.school_id), int(student_id)),
        }

    @router.post("/parent/children/{student_id}/ai-consent/revoke")
    def parent_revoke_consent(
        student_id: int,
        b: RevokeBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "parent")
        _parent_linked_student(db, u, student_id)
        return revoke_student_consent(
            db,
            implementation,
            school_id=int(u.school_id),
            student_id=int(student_id),
            actor_user_id=int(u.id),
            scope=b.scope,
            reason=b.reason or "parent_revoked",
        )

    app.include_router(router)
    app.state.guardian_consent_installed = True
    app.state.guardian_consent_router = router
    return router


__all__ = ["install_guardian_consent_views"]
