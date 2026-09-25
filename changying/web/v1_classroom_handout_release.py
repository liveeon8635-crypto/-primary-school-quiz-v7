"""Teacher-confirmed classroom handout publishing with immutable version snapshots."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, func, select

from changying.utils.datetime_tools import school_local_iso
from changying.web import v1 as v1_module


V1_CLASSROOM_HANDOUT_RELEASE_MARKER = "changying_v1_classroom_handout_release_v1"


class HandoutReleaseBody(BaseModel):
    confirm: bool = False


def register_classroom_handout_release_table(implementation: Any) -> Table:
    metadata = implementation.Base.metadata
    table = metadata.tables.get("classroom_handout_releases")
    if table is not None:
        return table
    return Table(
        "classroom_handout_releases",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("school_id", Integer, nullable=False, index=True),
        Column("assignment_id", Integer, nullable=False, index=True),
        Column("class_id", Integer, nullable=False, index=True),
        Column("teacher_id", Integer, nullable=False, index=True),
        Column("handout_id", Integer, nullable=False, index=True),
        Column("version_no", Integer, nullable=False),
        Column("status", String(30), nullable=False, default="published", index=True),
        Column("title", String(220), nullable=False, default=""),
        Column("content_text", Text, nullable=False, default=""),
        Column("selected_knowledge_json", Text, nullable=False, default="[]"),
        Column("selected_question_ids_json", Text, nullable=False, default="[]"),
        Column("teacher_notes", Text, nullable=False, default=""),
        Column("source_draft_updated_at", DateTime, nullable=True),
        Column("published_at", DateTime, nullable=False, default=datetime.utcnow, index=True),
        Column("superseded_at", DateTime, nullable=True),
        Column("revoked_at", DateTime, nullable=True),
        Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
        UniqueConstraint(
            "school_id",
            "assignment_id",
            "version_no",
            name="uq_classroom_handout_release_version",
        ),
    )


def _mapping(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def _iso(value: Any) -> str:
    return school_local_iso(value) if value else ""


def _release_payload(row: Any, *, include_content: bool = False) -> dict[str, Any] | None:
    if row is None:
        return None
    data = _mapping(row)
    payload = {
        "id": int(data["id"]),
        "assignmentID": int(data["assignment_id"]),
        "classID": int(data["class_id"]),
        "version": int(data["version_no"]),
        "status": str(data["status"] or ""),
        "title": str(data["title"] or ""),
        "publishedAt": _iso(data["published_at"]),
        "supersededAt": _iso(data["superseded_at"]),
        "revokedAt": _iso(data["revoked_at"]),
        "sourceDraftUpdatedAt": _iso(data["source_draft_updated_at"]),
    }
    if include_content:
        payload["content"] = str(data["content_text"] or "")
    return payload


def _json_list(raw: Any) -> list[Any]:
    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _teacher_release_payload(row: Any) -> dict[str, Any] | None:
    payload = _release_payload(row, include_content=True)
    if payload is None:
        return None
    data = _mapping(row)
    payload.update(
        {
            "selectedKnowledge": [
                str(x) for x in _json_list(data.get("selected_knowledge_json"))
            ],
            "selectedQuestionIDs": [
                int(x)
                for x in _json_list(data.get("selected_question_ids_json"))
                if str(x).strip().lstrip("-").isdigit()
            ],
            "teacherNotes": str(data.get("teacher_notes") or ""),
            "snapshot": {
                "handoutID": int(data.get("handout_id") or 0),
                "sourceDraftUpdatedAt": _iso(data.get("source_draft_updated_at")),
                "publishedAt": _iso(data.get("published_at")),
                "supersededAt": _iso(data.get("superseded_at")),
                "revokedAt": _iso(data.get("revoked_at")),
            },
        }
    )
    return payload


def patch_v1_classroom_handout_release_html(html: str) -> str:
    if V1_CLASSROOM_HANDOUT_RELEASE_MARKER in html:
        return html

    title_anchor = "const title=isSchool?'学校教学工作台':'培训机构教学工作台';"
    if title_anchor not in html:
        raise RuntimeError("handout release workspace title anchor not found")
    html = html.replace(
        title_anchor,
        "if(session.role==='student'&&!tasks.includes('课堂讲义'))tasks.unshift('课堂讲义');" + title_anchor,
        1,
    )

    handler = (
        "document.querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>{"
        "if(b.dataset.feature==='课堂复盘')navigate('/v1/classroom-review');"
        "else if(b.dataset.feature==='课堂互动')navigate('/v1/classroom-invitations');"
        "else if(b.dataset.feature==='随堂检测')navigate('/v1/classroom-quick-checks');"
        "else toast(b.dataset.feature+'：V1 入口已预留')});"
    )
    if handler not in html:
        raise RuntimeError("handout release workspace handler anchor not found")
    html = html.replace(
        handler,
        (
            "document.querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>{"
            "if(b.dataset.feature==='课堂复盘')navigate('/v1/classroom-review');"
            "else if(b.dataset.feature==='课堂互动')navigate('/v1/classroom-invitations');"
            "else if(b.dataset.feature==='随堂检测')navigate('/v1/classroom-quick-checks');"
            "else if(b.dataset.feature==='课堂讲义')navigate('/v1/classroom-handouts');"
            "else toast(b.dataset.feature+'：V1 入口已预留')});"
        ),
        1,
    )

    load_anchor = (
        "const load=async(aid)=>{current=Number(aid);summary=await api('/teacher/assignments/'+current+'/class-review');renderReview()};"
    )
    if load_anchor not in html:
        raise RuntimeError("handout release classroom review load anchor not found")
    html = html.replace(
        load_anchor,
        (
            "const load=async(aid)=>{current=Number(aid);const pair=await Promise.all(["
            "api('/teacher/assignments/'+current+'/class-review'),"
            "api('/teacher/assignments/'+current+'/class-review/handout-releases')]);"
            "summary=pair[0];window.__cyClassroomClosureSummary=summary;window.__cyHandoutReleaseAssignment=current;"
            "window.__cyHandoutReleaseState=pair[1];renderReview()};"
        ),
        1,
    )

    page_anchor = "    function v1QuestionTypeLabel(q){"
    if page_anchor not in html:
        raise RuntimeError("handout release page anchor not found")
    page = r'''
    async function classroomHandoutsPage(){
      if(session.role!=='student'){toast('课堂讲义仅学生本人可查看');navigate('/v1/workspace');return}
      const query=new URLSearchParams(location.search),rid=Number(query.get('release')||0);
      if(rid){
        try{
          const x=await api('/student/classroom-handouts/'+rid);
          const content=heading('课堂讲义','教师确认发布的冻结版本。','<button class="btn" id="cy-handout-list-back">返回讲义列表</button>')+
            '<section class="card"><div class="section-head"><div><h2>'+esc(x.title||'课堂讲义')+'</h2><p>'+esc([x.assignmentTitle,x.className,'V'+x.version,x.publishedAt].filter(Boolean).join(' · '))+'</p></div><span class="tag">已发布</span></div><div style="white-space:pre-wrap;line-height:1.8;margin-top:14px">'+esc(x.content||'')+'</div></section>'+
            '<div class="notice">这是教师发布时冻结的版本；教师后续修改草稿不会改变本版本内容。</div>';
          screen.innerHTML=shell(content,'workspace');bindNav();document.getElementById('cy-handout-list-back').onclick=()=>navigate('/v1/classroom-handouts');
        }catch(err){screen.innerHTML=shell(heading('课堂讲义','无法读取讲义')+'<div class="notice error">'+esc(err.message)+'</div>','workspace');bindNav()}
        return;
      }
      try{
        const rows=await api('/student/classroom-handouts');
        const cards=(rows||[]).map(x=>'<section class="card"><div class="section-head"><div><h3>'+esc(x.title||'课堂讲义')+'</h3><p>'+esc([x.assignmentTitle,x.className,'V'+x.version,x.publishedAt].filter(Boolean).join(' · '))+'</p></div><span class="tag">已发布</span></div><button class="btn primary cy-open-handout" data-release="'+x.id+'">查看讲义</button></section>').join('')||'<div class="empty">当前没有教师已发布的课堂讲义。</div>';
        screen.innerHTML=shell(heading('课堂讲义','只显示教师明确发布、且你原本就是对应作业接收人的讲义。')+'<section class="section" style="display:grid;gap:12px">'+cards+'</section>','workspace');bindNav();
        document.querySelectorAll('.cy-open-handout').forEach(b=>b.onclick=()=>navigate('/v1/classroom-handouts?release='+b.dataset.release));
      }catch(err){screen.innerHTML=shell(heading('课堂讲义','读取失败')+'<div class="notice error">'+esc(err.message)+'</div>','workspace');bindNav()}
    }

    function mountClassroomHandoutReleaseControls(){
      if(location.pathname!='/v1/classroom-review'||session?.role!=='teacher')return;
      const state=window.__cyHandoutReleaseState,aid=Number(window.__cyHandoutReleaseAssignment||0);
      if(!state||!aid)return;
      const existing=document.getElementById('cy-handout-release-card');if(existing)existing.remove();
      const existingClosure=document.getElementById('cy-classroom-closure-overview');if(existingClosure)existingClosure.remove();
      const draftSection=[...document.querySelectorAll('section.card')].find(x=>x.querySelector('h2')?.textContent.trim()==='课堂练习情况讲义草稿');
      if(!draftSection)return;
      const history=(state.history||[]).map(x=>'<div class="row"><span class="row-main"><b>V'+x.version+' · '+esc(x.title||'课堂讲义')+'</b><small>'+esc([x.publishedAt,x.status==='published'?'当前发布':x.status==='superseded'?'历史版本':'已撤回'].filter(Boolean).join(' · '))+'</small></span><span style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><span class="tag">'+esc(x.status==='published'?'已发布':x.status==='superseded'?'历史':'已撤回')+'</span><button class="btn cy-handout-history-open" data-release="'+x.id+'">查看版本</button></span></div>').join('')||'<div class="empty">还没有发布版本。</div>';
      const current=state.current;
      const interaction=window.__cyClassroomClosureSummary||null;
      const closure=(interaction&&interaction.classroomInteraction)||null;
      const completed=Number(interaction?.completedCount||0),recipients=Number(interaction?.recipientCount||0);
      const closureRows=[
        ['课堂练习',recipients?(completed+'/'+recipients+' 人完成'):'暂无接收学生'],
        ['知识点讲解',closure?((closure.segments||[]).length+' 个环节'):'暂无互动课堂记录'],
        ['随堂检测',closure?((closure.quickCheckRoundCount||0)+' 轮'):'0 轮'],
        ['补讲决策',closure?((closure.reteachCount||0)+' 次'):'0 次'],
        ['学生讲解',closure?((closure.presentationCount||0)+' 次'):'0 次'],
        ['教师加分',closure?((closure.teacherGrantedPoints||0)+' 分'):'0 分'],
        ['课堂讲义',current?('V'+current.version+' 当前发布'):(state.history||[]).length?('无当前发布 · 历史 '+state.history.length+' 版'):'尚未发布']
      ].map(x=>'<div class="row"><span class="row-main"><b>'+esc(x[0])+'</b></span><span class="tag">'+esc(x[1])+'</span></div>').join('');
      const closureCard=document.createElement('section');closureCard.id='cy-classroom-closure-overview';closureCard.className='section card';
      const classInfo=interaction?.class||{},paperInfo=interaction?.paper||{},assignmentInfo=interaction?.assignment||{},sessionInfo=closure?.session||{};
      const recordTitle=[classInfo.grade?(classInfo.grade+'年级'):'',paperInfo.subject||'',assignmentInfo.title||''].filter(Boolean).join(' · ');
      const recordMeta=[paperInfo.textbook||'',paperInfo.unit||'',sessionInfo.completedAt?('完成于 '+sessionInfo.completedAt):''].filter(Boolean).join(' · ');
      closureCard.innerHTML='<h2>本堂课完整课堂记录</h2><p class="muted">'+esc(recordTitle||'课堂记录')+(recordMeta?'<br>'+esc(recordMeta):'')+'</p><div class="notice">这是一份按课堂事实自动汇总的只读记录：练习结果、互动过程、教师决策、明确加分与讲义版本共同归属于本堂课；不自动改变学生长期掌握状态。</div><div class="list">'+closureRows+'</div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px"><button class="btn" id="cy-record-open-interaction" '+(sessionInfo.id?'':'disabled')+'>查看互动课堂</button><button class="btn" id="cy-record-open-handout" '+(current?'':'disabled')+'>查看当前讲义版本</button></div>';
      draftSection.insertAdjacentElement('beforebegin',closureCard);
      const interactionButton=document.getElementById('cy-record-open-interaction');if(interactionButton&&sessionInfo.id)interactionButton.onclick=()=>navigate('/v1/classroom-execution?session='+sessionInfo.id);
      const handoutButton=document.getElementById('cy-record-open-handout');if(handoutButton&&current)handoutButton.onclick=()=>renderHistoryPreview(Number(current.id));
      const publishLabel=current?'发布新版本 V'+state.nextVersion:'确认发布 V'+state.nextVersion;
      const actions=(state.canPublish?'<button class="btn primary" id="cy-handout-publish">'+publishLabel+'</button>':'')+(current?' <button class="btn" id="cy-handout-revoke">撤回当前发布</button>':'');
      const section=document.createElement('section');section.id='cy-handout-release-card';section.className='section card';
      section.innerHTML='<h2>讲义发布</h2><div class="notice"><b>必须由教师明确确认。</b><br>发布会把当前草稿复制为冻结版本；之后继续修改草稿不会改变学生已经看到的版本。撤回只取消学生可见性，不删除历史快照。</div><div style="display:flex;gap:8px;flex-wrap:wrap;margin:12px 0">'+actions+'</div><div class="list">'+history+'</div><div id="cy-handout-history-preview"></div>';
      draftSection.insertAdjacentElement('afterend',section);
      const renderHistoryPreview=async(releaseID)=>{const preview=document.getElementById('cy-handout-history-preview');if(!preview)return;preview.innerHTML='<div class="notice">正在读取冻结版本…</div>';try{const ordered=[...(state.history||[])].sort((a,b)=>Number(a.version)-Number(b.version)),targetIndex=ordered.findIndex(x=>Number(x.id)===Number(releaseID)),targetMeta=targetIndex>=0?ordered[targetIndex]:null,peerMeta=targetIndex>0?ordered[targetIndex-1]:(targetIndex>=0&&targetIndex<ordered.length-1?ordered[targetIndex+1]:null);const pair=await Promise.all([api('/teacher/assignments/'+aid+'/class-review/handout-releases/'+releaseID),peerMeta?api('/teacher/assignments/'+aid+'/class-review/handout-releases/'+peerMeta.id):Promise.resolve(null)]);const target=pair[0],peer=pair[1],changes=[];if(peer){if(target.title!==peer.title)changes.push('标题');if(target.content!==peer.content)changes.push('正文');if(JSON.stringify(target.selectedKnowledge)!==JSON.stringify(peer.selectedKnowledge))changes.push('知识点选择');if(JSON.stringify(target.selectedQuestionIDs)!==JSON.stringify(peer.selectedQuestionIDs))changes.push('题目选择');if(target.teacherNotes!==peer.teacherNotes)changes.push('教师备注')}const diff=peer?'<div class="notice"><b>版本差异：V'+target.version+' ↔ V'+peer.version+'</b><br>'+(changes.length?'发生变化：'+esc(changes.join('、')):'冻结内容完全一致')+'</div>':'';const snapshot=(x)=>{const s=x.snapshot||{};return '<p class="muted">发布：'+esc(s.publishedAt||x.publishedAt||'—')+'<br>来源草稿更新时间：'+esc(s.sourceDraftUpdatedAt||x.sourceDraftUpdatedAt||'—')+(s.supersededAt?'<br>被新版本替代：'+esc(s.supersededAt):'')+(s.revokedAt?'<br>撤回：'+esc(s.revokedAt):'')+'</p>'};const peerBlock=peer?'<div class="card"><h3>对比版本 V'+peer.version+'</h3><p class="muted">'+esc(peer.title||'')+'</p>'+snapshot(peer)+'<div style="white-space:pre-wrap;line-height:1.7;max-height:420px;overflow:auto">'+esc(peer.content||'')+'</div></div>':'';preview.innerHTML='<section class="section card"><div class="section-head"><div><h3>历史版本只读预览 · V'+target.version+'</h3><p>'+esc([target.status,target.publishedAt].filter(Boolean).join(' · '))+'</p></div><button class="btn" id="cy-handout-history-close">关闭预览</button></div>'+diff+'<div class="grid cols-2"><div class="card"><h3>查看版本 V'+target.version+'</h3><p class="muted">'+esc(target.title||'')+'</p>'+snapshot(target)+'<div style="white-space:pre-wrap;line-height:1.7;max-height:420px;overflow:auto">'+esc(target.content||'')+'</div><p class="muted">知识点：'+esc((target.selectedKnowledge||[]).join('、')||'—')+'<br>教师备注：'+esc(target.teacherNotes||'—')+'</p></div>'+peerBlock+'</div></section>';document.getElementById('cy-handout-history-close').onclick=()=>{preview.innerHTML=''}}catch(err){preview.innerHTML='<div class="notice error">'+esc(err.message)+'</div>'}};
      document.querySelectorAll('.cy-handout-history-open').forEach(b=>b.onclick=()=>renderHistoryPreview(Number(b.dataset.release)));
      const publish=document.getElementById('cy-handout-publish');
      if(publish)publish.onclick=async()=>{if(!confirm('确认将当前教师草稿发布给本作业接收学生？发布后会冻结为 V'+state.nextVersion+'，后续修改不会覆盖这一版本。'))return;publish.disabled=true;try{const r=await api('/teacher/assignments/'+aid+'/class-review/handout-publish',{method:'POST',body:JSON.stringify({confirm:true})});window.__cyHandoutReleaseState=r.releaseState;toast('讲义 V'+r.release.version+' 已发布');mountClassroomHandoutReleaseControls()}catch(err){toast(err.message);publish.disabled=false}};
      const revoke=document.getElementById('cy-handout-revoke');
      if(revoke)revoke.onclick=async()=>{if(!confirm('确认撤回当前已发布讲义？学生将立即不能再打开当前版本，但历史快照不会删除。'))return;revoke.disabled=true;try{const r=await api('/teacher/assignments/'+aid+'/class-review/handout-revoke',{method:'POST',body:JSON.stringify({confirm:true})});window.__cyHandoutReleaseState=r.releaseState;toast('当前发布已撤回');mountClassroomHandoutReleaseControls()}catch(err){toast(err.message);revoke.disabled=false}};
    }
    let cyHandoutReleaseTimer=null;
    new MutationObserver(()=>{clearTimeout(cyHandoutReleaseTimer);cyHandoutReleaseTimer=setTimeout(mountClassroomHandoutReleaseControls,60)}).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});

'''
    html = html.replace(page_anchor, page + page_anchor, 1)

    dispatch = (
        "if(path.includes('/classroom-execution'))await classroomExecutionPage();"
        "else if(path.includes('/classroom-quick-checks'))await classroomQuickChecksPage();"
        "else if(path.includes('/classroom-invitations'))await classroomInvitationsPage();"
        "else if(path.includes('/classroom-review'))await classroomReviewPage();"
        "else if(path.includes('/student'))await studentPage();"
    )
    if dispatch not in html:
        raise RuntimeError("handout release route dispatch anchor not found")
    html = html.replace(
        dispatch,
        (
            "if(path.includes('/classroom-execution'))await classroomExecutionPage();"
            "else if(path.includes('/classroom-quick-checks'))await classroomQuickChecksPage();"
            "else if(path.includes('/classroom-invitations'))await classroomInvitationsPage();"
            "else if(path.includes('/classroom-review'))await classroomReviewPage();"
            "else if(path.includes('/classroom-handouts'))await classroomHandoutsPage();"
            "else if(path.includes('/student'))await studentPage();"
        ),
        1,
    )

    return html.replace(
        "</head>",
        '<meta name="' + V1_CLASSROOM_HANDOUT_RELEASE_MARKER + '" content="1"></head>',
        1,
    )


def install_v1_classroom_handout_release_patch() -> None:
    if getattr(v1_module, "_classroom_handout_release_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_classroom_handout_release_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._classroom_handout_release_patch_installed = True


def install_v1_classroom_handout_release_routes(implementation: Any) -> None:
    app = implementation.app
    if getattr(app.state, "v1_classroom_handout_release_routes_installed", False):
        return

    router = APIRouter()

    releases = register_classroom_handout_release_table(implementation)
    metadata = implementation.Base.metadata
    drafts = metadata.tables.get("classroom_review_handouts")
    sessions = metadata.tables.get("classroom_sessions")
    if drafts is None or sessions is None:
        raise RuntimeError("classroom review and execution tables must be registered before handout releases")

    Assignment = implementation.Assignment
    AssignmentRecipient = implementation.AssignmentRecipient
    Paper = implementation.Paper
    SchoolClass = implementation.SchoolClass
    current_user = implementation.current_user
    get_db = implementation.get_db

    def teacher_assignment(db: Any, user: Any, aid: int) -> Any:
        implementation.need(user, "teacher")
        row = implementation.teacher_assignment_for(db, user.school_id, user.id, aid)
        if not row:
            raise HTTPException(404, "课堂练习不存在或无权限")
        return row

    def release_state(db: Any, user: Any, aid: int) -> dict[str, Any]:
        assignment = teacher_assignment(db, user, aid)
        draft = db.execute(
            select(drafts).where(
                drafts.c.school_id == user.school_id,
                drafts.c.assignment_id == aid,
                drafts.c.teacher_id == user.id,
            )
        ).first()
        completed_session = db.execute(
            select(sessions.c.id).where(
                sessions.c.school_id == user.school_id,
                sessions.c.teacher_id == user.id,
                sessions.c.source_assignment_id == aid,
                sessions.c.status == "completed",
            ).limit(1)
        ).first()
        rows = db.execute(
            select(releases).where(
                releases.c.school_id == user.school_id,
                releases.c.assignment_id == aid,
                releases.c.teacher_id == user.id,
            ).order_by(releases.c.version_no.desc())
        ).all()
        current = next((row for row in rows if _mapping(row)["status"] == "published"), None)
        max_version = max([int(_mapping(row)["version_no"]) for row in rows] or [0])
        return {
            "assignmentID": int(assignment.id),
            "draftPresent": draft is not None,
            "completedClassroomPresent": completed_session is not None,
            "canPublish": bool(draft is not None and completed_session is not None),
            "nextVersion": max_version + 1,
            "current": _release_payload(current),
            "history": [_release_payload(row) for row in rows],
        }

    @router.get("/teacher/assignments/{aid}/class-review/handout-releases")
    def teacher_handout_releases(
        aid: int,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        return release_state(db, u, aid)

    @router.get("/teacher/assignments/{aid}/class-review/handout-releases/{release_id}")
    def teacher_handout_release_detail(
        aid: int,
        release_id: int,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        teacher_assignment(db, u, aid)
        row = db.execute(
            select(releases).where(
                releases.c.id == release_id,
                releases.c.school_id == u.school_id,
                releases.c.assignment_id == aid,
                releases.c.teacher_id == u.id,
            )
        ).first()
        if not row:
            raise HTTPException(404, "讲义历史版本不存在或无权限")
        return _teacher_release_payload(row)

    @router.post("/teacher/assignments/{aid}/class-review/handout-publish")
    def publish_handout(
        aid: int,
        body: HandoutReleaseBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        if not body.confirm:
            raise HTTPException(400, "必须由教师明确确认后才能发布")
        assignment = teacher_assignment(db, u, aid)
        draft = db.execute(
            select(drafts).where(
                drafts.c.school_id == u.school_id,
                drafts.c.assignment_id == aid,
                drafts.c.teacher_id == u.id,
            )
        ).first()
        if not draft:
            raise HTTPException(400, "请先生成并审核课堂讲义草稿")
        completed_session = db.execute(
            select(sessions.c.id).where(
                sessions.c.school_id == u.school_id,
                sessions.c.teacher_id == u.id,
                sessions.c.source_assignment_id == aid,
                sessions.c.status == "completed",
            ).limit(1)
        ).first()
        if not completed_session:
            raise HTTPException(400, "课堂尚未完成，不能发布课后讲义")

        data = _mapping(draft)
        content = str(data["content_text"] or "").strip()
        if not content:
            raise HTTPException(400, "讲义正文不能为空")
        now = datetime.utcnow()
        next_version = int(
            db.scalar(
                select(func.coalesce(func.max(releases.c.version_no), 0)).where(
                    releases.c.school_id == u.school_id,
                    releases.c.assignment_id == aid,
                )
            )
            or 0
        ) + 1
        db.execute(
            releases.update().where(
                releases.c.school_id == u.school_id,
                releases.c.assignment_id == aid,
                releases.c.status == "published",
            ).values(status="superseded", superseded_at=now)
        )
        result = db.execute(
            releases.insert().values(
                school_id=u.school_id,
                assignment_id=aid,
                class_id=int(assignment.class_id),
                teacher_id=u.id,
                handout_id=int(data["id"]),
                version_no=next_version,
                status="published",
                title=str(data["title"] or "")[:220],
                content_text=content[:50000],
                selected_knowledge_json=str(data["selected_knowledge_json"] or "[]"),
                selected_question_ids_json=str(data["selected_question_ids_json"] or "[]"),
                teacher_notes=str(data["teacher_notes"] or "")[:3000],
                source_draft_updated_at=data["updated_at"],
                published_at=now,
                created_at=now,
            )
        )
        release_id = int(result.inserted_primary_key[0])
        implementation.audit(
            db,
            u,
            "class.review.handout.publish",
            f"assignment={aid}:release={release_id}:version={next_version}",
        )
        db.commit()
        row = db.execute(select(releases).where(releases.c.id == release_id)).first()
        return {
            "ok": True,
            "release": _release_payload(row),
            "releaseState": release_state(db, u, aid),
            "notice": "已发布冻结版本；后续修改教师草稿不会改变这一版本。",
        }

    @router.post("/teacher/assignments/{aid}/class-review/handout-revoke")
    def revoke_handout(
        aid: int,
        body: HandoutReleaseBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        if not body.confirm:
            raise HTTPException(400, "必须由教师明确确认后才能撤回")
        teacher_assignment(db, u, aid)
        current = db.execute(
            select(releases).where(
                releases.c.school_id == u.school_id,
                releases.c.assignment_id == aid,
                releases.c.teacher_id == u.id,
                releases.c.status == "published",
            ).order_by(releases.c.version_no.desc()).limit(1)
        ).first()
        if not current:
            raise HTTPException(409, "当前没有可撤回的已发布讲义")
        data = _mapping(current)
        now = datetime.utcnow()
        db.execute(
            releases.update()
            .where(releases.c.id == int(data["id"]))
            .values(status="revoked", revoked_at=now)
        )
        implementation.audit(
            db,
            u,
            "class.review.handout.revoke",
            f"assignment={aid}:release={data['id']}:version={data['version_no']}",
        )
        db.commit()
        return {
            "ok": True,
            "releaseState": release_state(db, u, aid),
            "notice": "当前发布已撤回；历史快照仍保留，学生不再可见。",
        }

    def student_release_rows(db: Any, user: Any) -> list[dict[str, Any]]:
        implementation.need(user, "student")
        recipient_rows = db.scalars(
            select(AssignmentRecipient).where(
                AssignmentRecipient.school_id == user.school_id,
                AssignmentRecipient.student_id == user.id,
            )
        ).all()
        assignment_ids = [int(row.assignment_id) for row in recipient_rows]
        if not assignment_ids:
            return []
        rows = db.execute(
            select(releases).where(
                releases.c.school_id == user.school_id,
                releases.c.assignment_id.in_(assignment_ids),
                releases.c.status == "published",
            ).order_by(releases.c.published_at.desc(), releases.c.id.desc())
        ).all()
        out = []
        for raw in rows:
            data = _mapping(raw)
            assignment = db.get(Assignment, int(data["assignment_id"]))
            class_row = db.get(SchoolClass, int(data["class_id"]))
            paper = db.get(Paper, assignment.paper_id) if assignment is not None else None
            payload = _release_payload(raw) or {}
            payload.update(
                {
                    "assignmentTitle": str(getattr(assignment, "title", "") or ""),
                    "className": str(getattr(class_row, "name", "") or ""),
                    "subject": str(getattr(paper, "subject", "") or ""),
                    "textbook": str(getattr(paper, "textbook", "") or ""),
                }
            )
            out.append(payload)
        return out

    @router.get("/student/classroom-handouts")
    def student_handouts(
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        return student_release_rows(db, u)

    @router.get("/student/classroom-handouts/{release_id}")
    def student_handout(
        release_id: int,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        implementation.need(u, "student")
        row = db.execute(
            select(releases).where(
                releases.c.id == release_id,
                releases.c.school_id == u.school_id,
                releases.c.status == "published",
            )
        ).first()
        if not row:
            raise HTTPException(404, "课堂讲义不存在、已撤回或无权限")
        data = _mapping(row)
        recipient = db.scalar(
            select(AssignmentRecipient).where(
                AssignmentRecipient.school_id == u.school_id,
                AssignmentRecipient.assignment_id == int(data["assignment_id"]),
                AssignmentRecipient.student_id == u.id,
            )
        )
        if not recipient:
            raise HTTPException(403, "你不是这份课堂讲义对应作业的接收学生")
        assignment = db.get(Assignment, int(data["assignment_id"]))
        class_row = db.get(SchoolClass, int(data["class_id"]))
        payload = _release_payload(row, include_content=True) or {}
        payload.update(
            {
                "assignmentTitle": str(getattr(assignment, "title", "") or ""),
                "className": str(getattr(class_row, "name", "") or ""),
            }
        )
        return payload

    @router.get("/v1/classroom-handouts", include_in_schema=False)
    def classroom_handouts_page():
        return HTMLResponse(
            v1_module.v1_html(),
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "X-Changying-V1": V1_CLASSROOM_HANDOUT_RELEASE_MARKER,
            },
        )

    app.include_router(router)
    app.state.v1_classroom_handout_release_routes_installed = True


__all__ = [
    "HandoutReleaseBody",
    "V1_CLASSROOM_HANDOUT_RELEASE_MARKER",
    "_teacher_release_payload",
    "install_v1_classroom_handout_release_patch",
    "install_v1_classroom_handout_release_routes",
    "patch_v1_classroom_handout_release_html",
    "register_classroom_handout_release_table",
]
