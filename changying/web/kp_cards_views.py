"""知识点讲解卡片接口 (周末课 阶段 1).

teacher  GET  /teacher/kp-cards                  list (all statuses) ?grade&subject
         POST /teacher/kp-cards                  create/update-by-key
         PUT  /teacher/kp-cards/{id}             edit
         POST /teacher/kp-cards/{id}/approve     {approved: bool}
         POST /teacher/kp-cards/seed             empty drafts for every knowledge name in the question bank
         POST /teacher/kp-cards/{id}/ai-draft    AI fills an empty/old card as a DRAFT (never auto-approved)
         POST /teacher/kp-cards/{id}/images      {data: data-URL jpeg/png} (<=600KB, <=4 per card)
         DELETE /teacher/kp-cards/images/{iid}
student  GET  /student/kp-cards?q=               approved cards of the student's own grade
         GET  /student/kp-cards/{id}
         GET  /student/kp-wrong                  own wrong-question knowledge points, with the card when one exists
any      GET  /kp-cards/images/{iid}             image bytes (teacher of the school, or student of an approved card)
"""

from __future__ import annotations

from changying.web.design_system import apply_surface

import base64
import json
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, insert, select, update

from changying.services.homework_knowledge import match_knowledge, school_knowledge
from changying.services.homework_knowledge_flags import knowledge_flags
from changying.web.kp_cards_pages import kp_page_html
from changying.services.kp_cards import (
    MAX_IMAGE_BYTES, MAX_IMAGES, SUBJECTS, card_json, clean_list, is_filled, register_kp_tables, search_text,
)

AI_FEATURE = "kp_card_draft"
DATA_URL = re.compile(r"^data:(image/(?:jpeg|png));base64,([A-Za-z0-9+/=\s]+)$")
SEARCH_LIMIT = 30


class CardBody(BaseModel):
    grade: int
    subject: str
    knowledge: str
    summary: str = ""
    steps: list[str] = []
    mistakes: list[str] = []
    examples: list[str] = []


class ApproveBody(BaseModel):
    approved: bool = True


class SeedBody(BaseModel):
    grade: int
    subject: str = ""


class ImageBody(BaseModel):
    data: str
    caption: str = ""


def install_kp_cards_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "kp_cards_installed", False):
        return app.state.kp_cards_router

    tables = register_kp_tables(implementation)
    cards, images = tables["cards"], tables["images"]
    User = implementation.User
    ClassStudent = implementation.ClassStudent
    SchoolClass = implementation.SchoolClass
    Wrong = implementation.WrongQuestionRecord
    current_user = implementation.current_user
    get_db = implementation.get_db
    need = implementation.need
    router = APIRouter()

    def check_grade_subject(grade: int, subject: str) -> None:
        if not 1 <= int(grade) <= 6:
            raise HTTPException(400, "年级需要在 1–6 之间")
        if subject not in SUBJECTS:
            raise HTTPException(400, "学科需要是：" + "、".join(SUBJECTS))

    def student_grade(db: Any, u: Any) -> int:
        if u.grade is not None:
            return int(u.grade)
        grade = db.scalar(
            select(SchoolClass.grade).join(ClassStudent, ClassStudent.class_id == SchoolClass.id)
            .where(ClassStudent.student_id == u.id, SchoolClass.school_id == u.school_id).limit(1)
        )
        if grade is None:
            raise HTTPException(404, "还没有设置你的年级，请联系老师")
        return int(grade)

    def image_map(db: Any, school_id: int, ids: list[int]) -> dict[int, list[int]]:
        out: dict[int, list[int]] = {}
        if not ids:
            return out
        for kid, iid in db.execute(
            select(images.c.card_id, images.c.id).where(images.c.school_id == school_id, images.c.card_id.in_(ids)).order_by(images.c.id)
        ).all():
            out.setdefault(int(kid), []).append(int(iid))
        return out

    def get_card(db: Any, school_id: int, kid: int) -> Any:
        row = db.execute(select(cards).where(cards.c.id == kid, cards.c.school_id == school_id)).first()
        if row is None:
            raise HTTPException(404, "没有找到这张卡片")
        return row

    def apply_body(b: CardBody) -> dict[str, Any]:
        return {
            "summary": b.summary.strip()[:1000],
            "steps_json": json.dumps(clean_list(b.steps), ensure_ascii=False),
            "mistakes_json": json.dumps(clean_list(b.mistakes), ensure_ascii=False),
            "examples_json": json.dumps(clean_list(b.examples), ensure_ascii=False),
        }

    @router.get("/v1/knowledge", include_in_schema=False)
    def kp_page():
        return HTMLResponse(apply_surface(kp_page_html(), "weekend"), headers={"Cache-Control": "no-store"})

    # ------------------------------------------------------------------ teacher
    @router.get("/teacher/kp-cards")
    def list_cards(grade: int | None = None, subject: str = "", u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        q = select(cards).where(cards.c.school_id == u.school_id)
        if grade is not None:
            q = q.where(cards.c.grade == grade)
        if subject:
            q = q.where(cards.c.subject == subject)
        rows = db.execute(q.order_by(cards.c.grade, cards.c.subject, cards.c.knowledge_key)).all()
        imgs = image_map(db, int(u.school_id), [r.id for r in rows])
        return {"items": [dict(card_json(r, imgs.get(r.id), with_status=True), filled=is_filled(r)) for r in rows]}

    @router.post("/teacher/kp-cards")
    def create_card(b: CardBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        check_grade_subject(b.grade, b.subject)
        key = b.knowledge.strip()[:160]
        if not key:
            raise HTTPException(400, "知识点名称不能为空")
        now = datetime.utcnow()
        existing = db.execute(
            select(cards).where(cards.c.school_id == u.school_id, cards.c.grade == b.grade, cards.c.subject == b.subject, cards.c.knowledge_key == key)
        ).first()
        values = apply_body(b)
        if existing is not None:
            db.execute(update(cards).where(cards.c.id == existing.id).values(**values, status="draft", approved_by=None, approved_at=None, updated_at=now))
            kid = int(existing.id)
        else:
            kid = int(db.execute(insert(cards).values(
                school_id=u.school_id, grade=b.grade, subject=b.subject, knowledge_key=key, **values,
                status="draft", created_by=u.id, created_at=now, updated_at=now)).inserted_primary_key[0])
        db.commit()
        return card_json(get_card(db, int(u.school_id), kid), image_map(db, int(u.school_id), [kid]).get(kid), with_status=True)

    @router.put("/teacher/kp-cards/{kid}")
    def edit_card(kid: int, b: CardBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = get_card(db, int(u.school_id), kid)
        # Editing takes an approved card back to draft: students never see unreviewed text.
        db.execute(update(cards).where(cards.c.id == row.id).values(**apply_body(b), status="draft", approved_by=None, approved_at=None, updated_at=datetime.utcnow()))
        db.commit()
        return card_json(get_card(db, int(u.school_id), kid), image_map(db, int(u.school_id), [kid]).get(kid), with_status=True)

    @router.post("/teacher/kp-cards/{kid}/approve")
    def approve_card(kid: int, b: ApproveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = get_card(db, int(u.school_id), kid)
        if b.approved and not is_filled(row):
            raise HTTPException(400, "卡片还是空的，先写讲解再发布")
        db.execute(update(cards).where(cards.c.id == row.id).values(
            status="approved" if b.approved else "draft", approved_by=u.id if b.approved else None,
            approved_at=datetime.utcnow() if b.approved else None))
        db.commit()
        return {"id": kid, "status": "approved" if b.approved else "draft"}

    @router.post("/teacher/kp-cards/seed")
    def seed_cards(b: SeedBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        if not 1 <= int(b.grade) <= 6:
            raise HTTPException(400, "年级需要在 1–6 之间")
        have = {(r.subject, r.knowledge_key) for r in db.execute(select(cards.c.subject, cards.c.knowledge_key).where(cards.c.school_id == u.school_id, cards.c.grade == b.grade)).all()}
        now = datetime.utcnow()
        created = 0
        for subject, knowledge in sorted(set(school_knowledge(implementation, db, int(u.school_id), b.grade))):
            if subject not in SUBJECTS or (b.subject and subject != b.subject) or (subject, knowledge) in have:
                continue
            db.execute(insert(cards).values(school_id=u.school_id, grade=b.grade, subject=subject, knowledge_key=knowledge[:160],
                                            status="draft", created_by=u.id, created_at=now, updated_at=now))
            created += 1
        db.commit()
        return {"created": created}

    @router.post("/teacher/kp-cards/{kid}/ai-draft")
    def ai_draft(kid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = get_card(db, int(u.school_id), kid)
        prompt = (
            f"你是小学{row.grade}年级{row.subject}老师。请为知识点“{row.knowledge_key}”写一张给学生看的讲解卡片。"
            "只输出 JSON：{\"summary\":\"一句话讲清是什么(40字内)\",\"steps\":[\"分步讲解，每步一句，3-6步\"],"
            "\"mistakes\":[\"常见错误及纠正，1-3条\"],\"examples\":[\"一道例题和简短解答，1-2条\"]}。"
            "语言适合该年级学生，不要出现超纲内容，不要输出 JSON 以外的文字。"
        )
        raw = implementation._ai_call(db, u, AI_FEATURE, prompt, timeout=60)
        try:
            data = implementation._ai_json(raw)
        except HTTPException:
            data = None
        if not isinstance(data, dict) or not (str(data.get("summary") or "").strip() or data.get("steps")):
            raise HTTPException(502, "AI 这次没有给出可用的草稿，请再试一次")
        db.execute(update(cards).where(cards.c.id == row.id).values(
            summary=str(data.get("summary") or "").strip()[:1000],
            steps_json=json.dumps(clean_list(data.get("steps")), ensure_ascii=False),
            mistakes_json=json.dumps(clean_list(data.get("mistakes")), ensure_ascii=False),
            examples_json=json.dumps(clean_list(data.get("examples")), ensure_ascii=False),
            status="draft", approved_by=None, approved_at=None, updated_at=datetime.utcnow()))
        db.commit()
        return card_json(get_card(db, int(u.school_id), kid), image_map(db, int(u.school_id), [kid]).get(kid), with_status=True)

    @router.post("/teacher/kp-cards/{kid}/images")
    def add_image(kid: int, b: ImageBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        get_card(db, int(u.school_id), kid)
        m = DATA_URL.match(b.data.strip())
        if not m:
            raise HTTPException(400, "只支持 JPEG 或 PNG 图片")
        try:
            raw = base64.b64decode(re.sub(r"\s+", "", m.group(2)), validate=True)
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "图片数据不完整")
        if len(raw) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "图片太大，请压缩到 600KB 以内")
        count = db.scalar(select(func.count()).select_from(images).where(images.c.card_id == kid)) or 0
        if count >= MAX_IMAGES:
            raise HTTPException(400, f"每张卡片最多 {MAX_IMAGES} 张图片")
        iid = int(db.execute(insert(images).values(school_id=u.school_id, card_id=kid, mime=m.group(1), caption=b.caption.strip()[:120],
                                                    data=raw, created_at=datetime.utcnow())).inserted_primary_key[0])
        db.execute(update(cards).where(cards.c.id == kid).values(status="draft", approved_by=None, approved_at=None, updated_at=datetime.utcnow()))
        db.commit()
        return {"id": iid}

    @router.delete("/teacher/kp-cards/images/{iid}")
    def delete_image(iid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = db.execute(select(images.c.card_id).where(images.c.id == iid, images.c.school_id == u.school_id)).first()
        if row is None:
            raise HTTPException(404, "没有找到这张图片")
        db.execute(delete(images).where(images.c.id == iid))
        db.execute(update(cards).where(cards.c.id == row.card_id).values(status="draft", approved_by=None, approved_at=None, updated_at=datetime.utcnow()))
        db.commit()
        return {"ok": True}

    @router.get("/kp-cards/images/{iid}")
    def image_bytes(iid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher", "student")
        row = db.execute(select(images).where(images.c.id == iid, images.c.school_id == u.school_id)).first()
        if row is None:
            raise HTTPException(404, "没有找到这张图片")
        if u.role == "student":
            card = db.execute(select(cards.c.status, cards.c.grade).where(cards.c.id == row.card_id)).first()
            if card is None or card.status != "approved" or int(card.grade) != student_grade(db, u):
                raise HTTPException(404, "没有找到这张图片")
        return Response(content=bytes(row.data), media_type=row.mime, headers={"Cache-Control": "private, max-age=3600"})

    # ------------------------------------------------------------------ student
    def approved_cards(db: Any, u: Any) -> list[Any]:
        return db.execute(
            select(cards).where(cards.c.school_id == u.school_id, cards.c.grade == student_grade(db, u), cards.c.status == "approved")
        ).all()

    @router.get("/student/kp-cards")
    def search_cards(q: str = "", u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        rows = approved_cards(db, u)
        words = [w for w in q.lower().split() if w][:5]
        if words:
            rows = [r for r in rows if all(w in search_text(r) for w in words)]
            rows.sort(key=lambda r: (not all(w in r.knowledge_key.lower() for w in words), r.knowledge_key))
        else:
            rows.sort(key=lambda r: (r.subject, r.knowledge_key))
        rows = rows[:SEARCH_LIMIT]
        imgs = image_map(db, int(u.school_id), [r.id for r in rows])
        return {"items": [card_json(r, imgs.get(r.id)) for r in rows]}

    @router.get("/student/kp-cards/{kid}")
    def one_card(kid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        row = get_card(db, int(u.school_id), kid)
        if row.status != "approved" or int(row.grade) != student_grade(db, u):
            raise HTTPException(404, "没有找到这张卡片")
        return card_json(row, image_map(db, int(u.school_id), [kid]).get(kid))

    @router.get("/student/kp-wrong")
    def wrong_with_cards(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        grouped = db.execute(
            select(Wrong.subject, Wrong.knowledge, func.count(Wrong.id), func.max(Wrong.created_at))
            .where(Wrong.school_id == u.school_id, Wrong.student_id == u.id, Wrong.status == "active", Wrong.knowledge != "")
            .group_by(Wrong.subject, Wrong.knowledge)
        ).all()
        rows = approved_cards(db, u)
        by_key = {(r.subject, r.knowledge_key): r for r in rows}
        candidates = [(r.subject, r.knowledge_key) for r in rows]
        open_flags = {(f["subject"], f["knowledge"]) for f in knowledge_flags(implementation, db, int(u.school_id), int(u.id))["flags"] if f["state"] == "open"} \
            if _homework_on() else set()
        items = []
        for subject, knowledge, count, last in grouped:
            card = by_key.get((subject, knowledge))
            if card is None:
                hit = match_knowledge(knowledge, candidates)
                card = by_key.get(hit) if hit else None
            items.append({
                "subject": subject, "knowledge": knowledge, "wrongCount": int(count),
                "lastAt": last.strftime("%Y-%m-%d") if last else "", "cardId": int(card.id) if card is not None else None,
                "aiAssisted": any(k == knowledge for _s, k in open_flags),
            })
        items.sort(key=lambda r: (r["cardId"] is None, -r["wrongCount"], r["knowledge"]))
        return {"items": items}

    def _homework_on() -> bool:
        try:
            from changying.web.homework_assistant import homework_enabled
            return bool(homework_enabled())
        except Exception:  # noqa: BLE001
            return False

    app.include_router(router)
    app.state.kp_cards_installed = True
    app.state.kp_cards_router = router
    return router


__all__ = ["install_kp_cards_views"]
