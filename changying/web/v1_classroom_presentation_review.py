"""Interactive classroom Phase D: teacher review + explicit custom points."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text, UniqueConstraint, select

from changying.services.classroom_presentation_review import (
    normalize_review_ratings,
    presentation_point_note,
)
from changying.services.classroom_quick_check import quick_check_summary
from changying.utils.datetime_tools import school_local_iso
from changying.web import v1 as v1_module


V1_CLASSROOM_PRESENTATION_REVIEW_MARKER = "changying_v1_classroom_presentation_review_d_v1"


class PresentationReviewBody(BaseModel):
    accuracy_rating: int | None = None
    clarity_rating: int | None = None
    interaction_rating: int | None = None
    teacher_note: str = ""


class PresentationPointGrantBody(BaseModel):
    points: int
    reason: str = ""


def register_classroom_presentation_review_table(implementation: Any) -> Table:
    metadata = implementation.Base.metadata
    table = metadata.tables.get("classroom_presentation_reviews")
    if table is not None:
        return table
    return Table(
        "classroom_presentation_reviews",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("school_id", Integer, nullable=False, index=True),
        Column("session_id", Integer, nullable=False, index=True),
        Column("segment_id", Integer, nullable=False, index=True),
        Column("turn_id", Integer, nullable=False, index=True),
        Column("student_id", Integer, nullable=False, index=True),
        Column("teacher_id", Integer, nullable=False, index=True),
        Column("accuracy_rating", Integer, nullable=True),
        Column("clarity_rating", Integer, nullable=True),
        Column("interaction_rating", Integer, nullable=True),
        Column("teacher_note", Text, nullable=False, default=""),
        Column("quick_check_id", Integer, nullable=True, index=True),
        Column("quick_check_accuracy", Integer, nullable=True),
        Column("presenter_check_correct", Boolean, nullable=True),
        Column("point_ledger_id", Integer, nullable=True, index=True),
        Column("granted_points", Integer, nullable=True),
        Column("point_reason", String(180), nullable=False, default=""),
        Column("reviewed_at", DateTime, nullable=False, default=datetime.utcnow),
        Column("points_granted_at", DateTime, nullable=True),
        Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
        Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
        UniqueConstraint("turn_id", name="uq_classroom_presentation_review_turn"),
    )


def _mapping(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def _iso(value: Any) -> str:
    return school_local_iso(value) if value else ""


def patch_v1_classroom_presentation_review_html(html: str) -> str:
    if V1_CLASSROOM_PRESENTATION_REVIEW_MARKER in html:
        return html

    reload_anchor = (
        "const reload=async()=>{const pair=await Promise.all([api('/teacher/classroom-sessions/'+sid),"
        "api('/teacher/classroom-sessions/'+sid+'/quick-checks')]);data=pair[0];"
        "data.quickChecks=pair[1]||[];renderExec()};"
    )
    if reload_anchor not in html:
        raise RuntimeError("presentation review reload anchor not found")
    html = html.replace(
        reload_anchor,
        "const reload=async()=>{const pair=await Promise.all([api('/teacher/classroom-sessions/'+sid),api('/teacher/classroom-sessions/'+sid+'/quick-checks'),api('/teacher/classroom-sessions/'+sid+'/presentation-reviews')]);data=pair[0];data.quickChecks=pair[1]||[];data.presentationReviews=pair[2]||[];renderExec()};",
        1,
    )

    helper_anchor = "      const quickCheckBlock=(seg,s)=>{"
    if helper_anchor not in html:
        raise RuntimeError("presentation review helper anchor not found")
    helper = r'''
      const presentationReviewBlock=(seg)=>{
        const rows=(data.presentationReviews||[]).filter(x=>Number(x.segmentID)===Number(seg.id));
        if(!rows.length)return '';
        return rows.map(x=>{
          const r=x.review||{},f=x.feedback||{},point=x.point||null,locked=!!point;
          const rating=(key,label)=>'<div class="field"><label>'+label+'</label><select class="cy-pr-rating" data-turn="'+x.turnID+'" data-key="'+key+'" '+(locked?'disabled':'')+'><option value="">不打分</option>'+[1,2,3,4,5].map(v=>'<option value="'+v+'" '+(Number(r[key])===v?'selected':'')+'>'+v+' / 5</option>').join('')+'</select></div>';
          const feedback=f.quickCheckID?('<div class="notice"><b>讲解后的随堂检测反馈</b><br>班级：'+f.responseCount+'人提交 · 正确率 '+(f.classAccuracy===null?'—':f.classAccuracy+'%')+'<br>讲解学生：'+(f.presenterResponded?(f.presenterCorrect?'已答对':'未答对'):'未提交')+(f.decision?'<br>教师课堂决策：'+(f.decision==='reteach'?'继续讲解':'确认完成'):'')+'</div>'):'<div class="notice"><b>讲解后的随堂检测反馈</b><br><span class="muted">尚无该次讲解之后已结束的随堂检测。评价可以先保存，后续反馈会自动显示，但不会自动改分。</span></div>';
          const pointBox=point?('<div class="notice"><b>互动积分</b><br>已由教师确认加 '+point.points+' 分 · '+esc(point.reason||'课堂讲解表现')+(point.reversed?' · 原记录已撤销':'')+'<br><span class="muted">积分来自教师明确确认，不由评价或检测结果自动生成。</span></div>'):(r.id?'<div class="notice"><b>教师自定义加分（可选）</b><div style="display:flex;gap:8px;flex-wrap:wrap;align-items:end"><div class="field" style="min-width:100px"><label>加分</label><input type="number" min="1" max="100" class="cy-pr-points" data-review="'+r.id+'" value="1"></div><div class="field" style="min-width:220px;flex:1"><label>原因</label><input class="cy-pr-reason" data-review="'+r.id+'" value="课堂讲解表现"></div><button class="btn primary cy-pr-grant" data-review="'+r.id+'">确认加分</button></div><span class="muted">点击确认前不会写入积分动态；随堂检测正确率不会自动折算积分。</span></div>':'<div class="notice"><span class="muted">先保存教师评价后，才能由教师再次确认是否加分。</span></div>');
          return '<div class="card" style="margin-top:10px"><div class="section-head"><div><h3>学生讲解评价 · '+esc(x.studentName)+'</h3><p>'+esc(x.knowledgeKey)+' · 讲解完成 '+esc(x.completedAt||'')+'</p></div><span class="tag">'+(r.id?'已保存评价':'待评价')+'</span></div>'+feedback+'<div class="grid cols-3">'+rating('accuracyRating','内容准确性')+rating('clarityRating','表达清晰度')+rating('interactionRating','互动效果')+'</div><div class="field"><label>教师评价备注</label><textarea class="cy-pr-note" data-turn="'+x.turnID+'" rows="2" '+(locked?'disabled':'')+'>'+esc(r.teacherNote||'')+'</textarea></div>'+(locked?'':'<button class="btn cy-pr-save" data-turn="'+x.turnID+'">'+(r.id?'更新评价':'保存评价')+'</button>')+pointBox+'</div>';
        }).join('');
      };
'''
    html = html.replace(helper_anchor, helper + helper_anchor, 1)

    card_anchor = "<div id=\"cy-candidates-'+seg.id+'\"></div>'+reveal+quickCheckBlock(seg,s)+'</section>';"
    if card_anchor not in html:
        raise RuntimeError("presentation review card anchor not found")
    html = html.replace(
        card_anchor,
        "<div id=\"cy-candidates-'+seg.id+'\"></div>'+reveal+quickCheckBlock(seg,s)+presentationReviewBlock(seg)+'</section>';",
        1,
    )

    binding_anchor = "      };\n      await reload();\n    }\n\n    async function classroomInvitationsPage(){"
    if binding_anchor not in html:
        raise RuntimeError("presentation review binding anchor not found")
    bindings = r'''
        document.querySelectorAll('.cy-pr-save').forEach(b=>b.onclick=async()=>{const tid=b.dataset.turn;const get=k=>{const el=document.querySelector('.cy-pr-rating[data-turn="'+tid+'"][data-key="'+k+'"]');return el&&el.value?Number(el.value):null};const note=document.querySelector('.cy-pr-note[data-turn="'+tid+'"]')?.value||'';b.disabled=true;try{await api('/teacher/classroom-sessions/'+sid+'/presenter-turns/'+tid+'/review',{method:'PUT',body:JSON.stringify({accuracy_rating:get('accuracyRating'),clarity_rating:get('clarityRating'),interaction_rating:get('interactionRating'),teacher_note:note})});toast('讲解评价已保存；未自动加分');await reload()}catch(e){toast(e.message);b.disabled=false}});
        document.querySelectorAll('.cy-pr-grant').forEach(b=>b.onclick=async()=>{const rid=b.dataset.review,points=Number(document.querySelector('.cy-pr-points[data-review="'+rid+'"]')?.value||0),reason=document.querySelector('.cy-pr-reason[data-review="'+rid+'"]')?.value||'';if(!confirm('确认由教师为本次学生讲解加 '+points+' 分？该操作会写入学生积分动态。'))return;b.disabled=true;try{await api('/teacher/classroom-sessions/'+sid+'/presentation-reviews/'+rid+'/grant-points',{method:'POST',body:JSON.stringify({points,reason})});toast('互动积分已由教师确认发放');await reload()}catch(e){toast(e.message);b.disabled=false}});
'''
    html = html.replace(
        binding_anchor,
        bindings + "\n      };\n      await reload();\n    }\n\n    async function classroomInvitationsPage(){",
        1,
    )

    return html.replace(
        "</head>",
        '<meta name="' + V1_CLASSROOM_PRESENTATION_REVIEW_MARKER + '" content="1"></head>',
        1,
    )


def install_v1_classroom_presentation_review_patch() -> None:
    if getattr(v1_module, "_classroom_presentation_review_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_classroom_presentation_review_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._classroom_presentation_review_patch_installed = True


def install_v1_classroom_presentation_review_routes(implementation: Any) -> None:
    app = implementation.app
    if getattr(app.state, "v1_classroom_presentation_review_routes_installed", False):
        return

    router = APIRouter()

    reviews = register_classroom_presentation_review_table(implementation)
    metadata = implementation.Base.metadata
    sessions = metadata.tables.get("classroom_sessions")
    segments = metadata.tables.get("classroom_segments")
    turns = metadata.tables.get("classroom_presenter_turns")
    events = metadata.tables.get("classroom_events")
    checks = metadata.tables.get("classroom_quick_checks")
    responses = metadata.tables.get("classroom_quick_check_responses")
    if any(x is None for x in (sessions, segments, turns, events, checks, responses)):
        raise RuntimeError("classroom execution and quick-check tables must be registered before presentation reviews")

    User = implementation.User
    PointLedger = implementation.PointLedger
    current_user = implementation.current_user
    get_db = implementation.get_db

    def append_event(
        db: Any,
        user: Any,
        session_id: int,
        event_type: str,
        *,
        segment_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        import json
        db.execute(
            events.insert().values(
                school_id=user.school_id,
                session_id=session_id,
                segment_id=segment_id,
                actor_id=user.id,
                actor_role=str(getattr(user, "role", "") or ""),
                event_type=event_type[:80],
                payload_json=json.dumps(payload or {}, ensure_ascii=False),
                created_at=datetime.utcnow(),
            )
        )

    def teacher_session(db: Any, user: Any, sid: int) -> dict[str, Any]:
        implementation.need(user, "teacher")
        raw = db.execute(
            select(sessions).where(
                sessions.c.id == sid,
                sessions.c.school_id == user.school_id,
                sessions.c.teacher_id == user.id,
            )
        ).first()
        if not raw:
            raise HTTPException(404, "课堂执行记录不存在或无权限")
        return _mapping(raw)

    def completed_turn(db: Any, user: Any, sid: int, tid: int) -> dict[str, Any]:
        teacher_session(db, user, sid)
        raw = db.execute(
            select(turns).where(
                turns.c.id == tid,
                turns.c.session_id == sid,
                turns.c.school_id == user.school_id,
            )
        ).first()
        if not raw:
            raise HTTPException(404, "学生讲解记录不存在")
        row = _mapping(raw)
        if str(row["status"]) != "completed":
            raise HTTPException(400, "只有已经完成的学生讲解才能评价")
        return row

    def segment_row(db: Any, school_id: int, sid: int, segid: int) -> dict[str, Any]:
        raw = db.execute(
            select(segments).where(
                segments.c.id == segid,
                segments.c.session_id == sid,
                segments.c.school_id == school_id,
            )
        ).first()
        return _mapping(raw) if raw else {}

    def student_name(db: Any, school_id: int, student_id: int) -> str:
        row = db.scalar(
            select(User).where(
                User.id == student_id,
                User.school_id == school_id,
                User.role == "student",
            )
        )
        return str(getattr(row, "name", "") or "") if row else ""

    def latest_followup_feedback(
        db: Any,
        *,
        school_id: int,
        sid: int,
        segid: int,
        student_id: int,
        completed_at: Any,
    ) -> dict[str, Any]:
        statement = select(checks).where(
            checks.c.school_id == school_id,
            checks.c.session_id == sid,
            checks.c.segment_id == segid,
            checks.c.status == "closed",
        )
        if completed_at is not None:
            statement = statement.where(checks.c.closed_at >= completed_at)
        raw = db.execute(
            statement.order_by(checks.c.closed_at.desc(), checks.c.id.desc()).limit(1)
        ).first()
        if not raw:
            return {
                "quickCheckID": None,
                "responseCount": 0,
                "classAccuracy": None,
                "presenterResponded": False,
                "presenterCorrect": None,
                "decision": "",
            }
        check = _mapping(raw)
        response_rows = [
            _mapping(x)
            for x in db.execute(
                select(responses).where(
                    responses.c.school_id == school_id,
                    responses.c.check_id == check["id"],
                )
            ).all()
        ]
        options = []
        try:
            import json
            value = json.loads(check.get("options_json") or "[]")
            options = value if isinstance(value, list) else []
        except Exception:
            options = []
        stats = quick_check_summary(response_rows, option_count=len(options))
        mine = next(
            (x for x in response_rows if int(x["student_id"]) == int(student_id)),
            None,
        )
        return {
            "quickCheckID": int(check["id"]),
            "responseCount": int(stats["responseCount"]),
            "classAccuracy": stats["accuracy"],
            "presenterResponded": mine is not None,
            "presenterCorrect": bool(mine["is_correct"]) if mine is not None else None,
            "decision": str(check.get("decision") or ""),
        }

    def review_row_for_turn(db: Any, school_id: int, tid: int) -> dict[str, Any] | None:
        raw = db.execute(
            select(reviews).where(
                reviews.c.school_id == school_id,
                reviews.c.turn_id == tid,
            )
        ).first()
        return _mapping(raw) if raw else None

    def point_payload(db: Any, review: dict[str, Any]) -> dict[str, Any] | None:
        lid = review.get("point_ledger_id")
        if not lid:
            return None
        row = db.scalar(
            select(PointLedger).where(
                PointLedger.id == int(lid),
                PointLedger.school_id == review["school_id"],
            )
        )
        if row is None:
            return None
        return {
            "ledgerID": int(row.id),
            "points": int(row.points or 0),
            "reason": str(row.reason or ""),
            "reversed": bool(row.reversed),
            "createdAt": implementation.school_local_iso(row.created_at),
        }

    def review_payload(
        db: Any,
        *,
        session: dict[str, Any],
        turn: dict[str, Any],
    ) -> dict[str, Any]:
        seg = segment_row(
            db,
            int(session["school_id"]),
            int(session["id"]),
            int(turn["segment_id"]),
        )
        review = review_row_for_turn(db, int(session["school_id"]), int(turn["id"]))
        feedback = latest_followup_feedback(
            db,
            school_id=int(session["school_id"]),
            sid=int(session["id"]),
            segid=int(turn["segment_id"]),
            student_id=int(turn["student_id"]),
            completed_at=turn.get("completed_at"),
        )
        review_data = None
        if review:
            review_data = {
                "id": int(review["id"]),
                "accuracyRating": review.get("accuracy_rating"),
                "clarityRating": review.get("clarity_rating"),
                "interactionRating": review.get("interaction_rating"),
                "teacherNote": str(review.get("teacher_note") or ""),
                "reviewedAt": _iso(review.get("reviewed_at")),
                "pointsGrantedAt": _iso(review.get("points_granted_at")),
            }
        return {
            "turnID": int(turn["id"]),
            "segmentID": int(turn["segment_id"]),
            "studentID": int(turn["student_id"]),
            "studentName": student_name(
                db,
                int(session["school_id"]),
                int(turn["student_id"]),
            ),
            "knowledgeKey": str(seg.get("knowledge_key") or ""),
            "completedAt": _iso(turn.get("completed_at")),
            "review": review_data,
            "feedback": feedback,
            "point": point_payload(db, review) if review else None,
        }

    @router.get("/teacher/classroom-sessions/{sid}/presentation-reviews")
    def list_presentation_reviews(
        sid: int,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        session = teacher_session(db, u, sid)
        rows = [
            _mapping(x)
            for x in db.execute(
                select(turns)
                .where(
                    turns.c.school_id == u.school_id,
                    turns.c.session_id == sid,
                    turns.c.status == "completed",
                )
                .order_by(turns.c.completed_at, turns.c.id)
            ).all()
        ]
        return [review_payload(db, session=session, turn=row) for row in rows]

    @router.put("/teacher/classroom-sessions/{sid}/presenter-turns/{tid}/review")
    def save_presentation_review(
        sid: int,
        tid: int,
        body: PresentationReviewBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        session = teacher_session(db, u, sid)
        turn = completed_turn(db, u, sid, tid)
        try:
            ratings = normalize_review_ratings(
                accuracy_rating=body.accuracy_rating,
                clarity_rating=body.clarity_rating,
                interaction_rating=body.interaction_rating,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        existing = review_row_for_turn(db, u.school_id, tid)
        if existing and existing.get("point_ledger_id"):
            raise HTTPException(400, "本次讲解已经确认发放积分；为保持审计一致性，评价已锁定")
        feedback = latest_followup_feedback(
            db,
            school_id=u.school_id,
            sid=sid,
            segid=int(turn["segment_id"]),
            student_id=int(turn["student_id"]),
            completed_at=turn.get("completed_at"),
        )
        now = datetime.utcnow()
        values = {
            "school_id": u.school_id,
            "session_id": sid,
            "segment_id": int(turn["segment_id"]),
            "turn_id": tid,
            "student_id": int(turn["student_id"]),
            "teacher_id": u.id,
            **ratings,
            "teacher_note": body.teacher_note.strip()[:3000],
            "quick_check_id": feedback["quickCheckID"],
            "quick_check_accuracy": feedback["classAccuracy"],
            "presenter_check_correct": feedback["presenterCorrect"],
            "reviewed_at": now,
            "updated_at": now,
        }
        if existing:
            db.execute(
                reviews.update()
                .where(reviews.c.id == int(existing["id"]))
                .values(**values)
            )
            rid = int(existing["id"])
        else:
            rid = int(
                db.execute(
                    reviews.insert()
                    .values(**values, created_at=now)
                    .returning(reviews.c.id)
                ).scalar_one()
            )
        append_event(
            db,
            u,
            sid,
            "presenter.review_saved",
            segment_id=int(turn["segment_id"]),
            payload={
                "reviewID": rid,
                "turnID": tid,
                "studentID": int(turn["student_id"]),
                "quickCheckID": feedback["quickCheckID"],
            },
        )
        implementation.audit(
            db,
            u,
            "classroom.presenter.review",
            f"session={sid};turn={tid};review={rid};student={turn['student_id']}",
        )
        db.commit()
        saved = review_row_for_turn(db, u.school_id, tid)
        return {
            "ok": True,
            "reviewID": rid,
            "notice": "教师评价已保存；系统没有自动加分，也没有写入知识掌握证据。",
            "review": {
                "id": rid,
                "accuracyRating": saved.get("accuracy_rating"),
                "clarityRating": saved.get("clarity_rating"),
                "interactionRating": saved.get("interaction_rating"),
                "teacherNote": str(saved.get("teacher_note") or ""),
            },
            "feedback": feedback,
        }

    @router.post("/teacher/classroom-sessions/{sid}/presentation-reviews/{rid}/grant-points")
    def grant_presentation_points(
        sid: int,
        rid: int,
        body: PresentationPointGrantBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        session = teacher_session(db, u, sid)
        raw = db.execute(
            select(reviews).where(
                reviews.c.id == rid,
                reviews.c.school_id == u.school_id,
                reviews.c.session_id == sid,
                reviews.c.teacher_id == u.id,
            )
        ).first()
        if not raw:
            raise HTTPException(404, "讲解评价不存在或无权限")
        review = _mapping(raw)
        if review.get("point_ledger_id"):
            raise HTTPException(400, "本次讲解已经发放过积分，不能重复加分")
        points = int(body.points or 0)
        if points < 1 or points > 100:
            raise HTTPException(400, "讲解互动加分须为1-100分")
        turn = completed_turn(db, u, sid, int(review["turn_id"]))
        implementation.can_manage_student_points(
            db,
            u,
            int(review["student_id"]),
            int(session["class_id"]),
        )
        seg = segment_row(
            db,
            u.school_id,
            sid,
            int(review["segment_id"]),
        )
        feedback = latest_followup_feedback(
            db,
            school_id=u.school_id,
            sid=sid,
            segid=int(review["segment_id"]),
            student_id=int(review["student_id"]),
            completed_at=turn.get("completed_at"),
        )
        reason = body.reason.strip()[:180] or (
            "课堂讲解表现：" + str(seg.get("knowledge_key") or "知识点讲解")[:140]
        )
        note = presentation_point_note(
            knowledge_key=str(seg.get("knowledge_key") or ""),
            accuracy_rating=review.get("accuracy_rating"),
            clarity_rating=review.get("clarity_rating"),
            interaction_rating=review.get("interaction_rating"),
            quick_check_accuracy=feedback["classAccuracy"],
            presenter_check_correct=feedback["presenterCorrect"],
            teacher_note=str(review.get("teacher_note") or ""),
        )
        ledger = PointLedger(
            school_id=u.school_id,
            student_id=int(review["student_id"]),
            class_id=int(session["class_id"]),
            actor_id=u.id,
            rule_id=None,
            category="activity",
            points=points,
            reason=reason,
            note=note,
            source="classroom",
            related_id=rid,
            idempotency_key=f"classroom_presentation:{rid}",
        )
        db.add(ledger)
        db.flush()
        now = datetime.utcnow()
        db.execute(
            reviews.update()
            .where(reviews.c.id == rid)
            .values(
                quick_check_id=feedback["quickCheckID"],
                quick_check_accuracy=feedback["classAccuracy"],
                presenter_check_correct=feedback["presenterCorrect"],
                point_ledger_id=int(ledger.id),
                granted_points=points,
                point_reason=reason,
                points_granted_at=now,
                updated_at=now,
            )
        )
        auto_changed = implementation.reconcile_auto_rewards(
            db,
            u.school_id,
            [int(review["student_id"])],
            u.id,
        )
        append_event(
            db,
            u,
            sid,
            "presenter.points_granted",
            segment_id=int(review["segment_id"]),
            payload={
                "reviewID": rid,
                "turnID": int(review["turn_id"]),
                "studentID": int(review["student_id"]),
                "ledgerID": int(ledger.id),
                "points": points,
            },
        )
        implementation.audit(
            db,
            u,
            "classroom.presenter.points",
            f"session={sid};review={rid};student={review['student_id']};points={points};ledger={ledger.id}",
        )
        db.commit()
        return {
            "ok": True,
            "points": points,
            "record": implementation.point_ledger_json(db, ledger),
            "autoRewards": [
                implementation.auto_grant_json(db, x)
                for x in auto_changed
                if getattr(x, "status", "") == "pending"
            ],
            "notice": "积分由教师本次明确确认后写入；评价和随堂检测均不会自动生成积分。",
        }

    app.include_router(router)
    app.state.v1_classroom_presentation_review_routes_installed = True


__all__ = [
    "PresentationPointGrantBody",
    "PresentationReviewBody",
    "V1_CLASSROOM_PRESENTATION_REVIEW_MARKER",
    "install_v1_classroom_presentation_review_patch",
    "install_v1_classroom_presentation_review_routes",
    "patch_v1_classroom_presentation_review_html",
    "register_classroom_presentation_review_table",
]
