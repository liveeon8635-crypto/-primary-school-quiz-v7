"""POST /teacher/papers/compose — server-side, type-balanced paper composition.

Both assignment forms (Classic and v1) call this instead of filtering
``/questions`` in the browser; see changying/services/paper_composition.py.
The paper row and its permission/ownership rules are the same as
``POST /teacher/papers``; only the question picking moved server-side.
"""

from __future__ import annotations

import json
import random
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from changying.services.paper_composition import (
    compose_question_ids,
    distribution_text,
    online_question_type,
    type_distribution,
)

MAX_PAPER_QUESTIONS = 30


class PaperComposeBody(BaseModel):
    title: str
    grade: int
    subject: str
    textbook: str = ""
    unit: str = ""
    count: int = 10
    mix: str = "mixed"
    broaden_unit: bool = False
    required_question_ids: list[int] = []


def install_paper_composition_routes(implementation: Any, *, rng: Optional[random.Random] = None) -> None:
    app = implementation.app
    if getattr(app.state, "paper_composition_routes_installed", False):
        return
    router = APIRouter()
    Question = implementation.Question
    Paper = implementation.Paper
    current_user = implementation.current_user
    get_db = implementation.get_db

    def eligible(db: Any, u: Any, b: PaperComposeBody, *, with_unit: bool) -> dict[int, str]:
        s = select(Question).where(Question.school_id == u.school_id, Question.grade == b.grade, Question.subject == b.subject)
        if b.textbook:
            s = s.where(Question.textbook == b.textbook)
        if with_unit and b.unit:
            s = s.where(Question.unit == b.unit)
        out: dict[int, str] = {}
        for row in db.scalars(s.order_by(Question.id)).all():
            qtype = online_question_type(row, question_type_of=implementation.question_type_of, answer_meta=implementation.question_answer_meta)
            if qtype:
                out[int(row.id)] = qtype
        return out

    @router.post("/teacher/papers/compose")
    def compose_paper(b: PaperComposeBody, u: Any = Depends(current_user), db: Any = Depends(get_db)) -> dict[str, Any]:
        implementation.need(u, "teacher")
        title = (b.title or "").strip()[:160]
        if not title:
            raise HTTPException(400, "请填写作业名称")
        count = max(1, min(int(b.count or 10), MAX_PAPER_QUESTIONS))
        required = list(dict.fromkeys(int(x) for x in (b.required_question_ids or []) if int(x) > 0))[:5]
        if required:
            owned = db.scalars(select(Question.id).where(Question.school_id == u.school_id, Question.id.in_(required))).all()
            if set(owned) != set(required):
                raise HTTPException(400, "试卷包含不存在或无权限的题目")
        typed = eligible(db, u, b, with_unit=True)
        broadened = False
        if not typed and b.unit and b.broaden_unit:
            typed = eligible(db, u, b, with_unit=False)
            broadened = bool(typed)
        if not typed and not required:
            raise HTTPException(
                400,
                ("本单元暂无可在线判分的题目" if b.unit and not b.broaden_unit else "所选年级、学科和教材范围没有可在线判分的题目")
                + "；请调整教材/单元，或先用 AI 出题、导入试卷录入题目",
            )
        ids = compose_question_ids(sorted(typed.items()), count, mix=b.mix, rng=rng, required_first=required)
        if not ids:
            raise HTTPException(400, "没有符合所选题型搭配的题目；可改为“多题型”或先录入题目")
        paper = Paper(
            school_id=u.school_id, title=title, grade=b.grade, subject=b.subject[:30], textbook=(b.textbook or "")[:80],
            unit=(b.unit or "")[:100], question_ids_json=json.dumps(ids), teacher_id=u.id,
        )
        db.add(paper)
        db.flush()
        distribution = type_distribution(typed, ids)
        implementation.audit(db, u, "paper.compose", f"{paper.id}:{paper.title}:n={len(ids)}:mix={b.mix}:types={json.dumps(distribution, ensure_ascii=False)}")
        db.commit()
        db.refresh(paper)
        return {
            **implementation.pj(paper),
            "typeDistribution": distribution,
            "typeSummary": distribution_text(distribution),
            "requestedCount": count,
            "availableCount": len(typed),
            "broadenedUnit": broadened,
        }

    app.include_router(router)
    app.state.paper_composition_routes_installed = True
