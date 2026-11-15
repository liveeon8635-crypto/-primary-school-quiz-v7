"""知识地图（教师端）：维护单元、知识点、前置关系，并给每个知识点的题目分档.

teacher  GET  /v1/knowledge-map                                  page
         GET  /knowledge-map/config                              {enabled} (404 when the flag is off)
         GET  /teacher/knowledge-maps                            the school's maps and the templates not used yet
         POST /teacher/knowledge-maps                            {template} create a draft from a reviewed template
         GET  /teacher/knowledge-maps/{mid}                      draft + coverage per node + published state
         PUT  /teacher/knowledge-maps/{mid}                      {map, revision} save the draft (validated)
         GET  /teacher/knowledge-maps/{mid}/nodes/{key}/questions  questions of the bank matching the node
         POST /teacher/knowledge-maps/{mid}/nodes/{key}/visual        {level, count} picture questions drawn and solved
                                                                by the system (cube solids, grid moves), not saved
         POST /teacher/knowledge-maps/{mid}/nodes/{key}/visual/save   {level, revision, questions} save reviewed ones, level
         GET  /teacher/knowledge-maps/{mid}/bank?unit=&q=          search the school's bank by unit / keyword to pick
                                                                questions for a node whatever their knowledge name
         PUT  /teacher/knowledge-maps/{mid}/nodes/{key}/levels   {levels, revision} question levels of one node
         POST /teacher/knowledge-maps/{mid}/publish              {revision} the draft becomes the published map
         POST /teacher/knowledge-maps/{mid}/units/{ukey}/restore {revision} add back the template's missing points of a unit
         GET  /teacher/knowledge-maps/{mid}/classes              the teacher's classes
         GET  /teacher/knowledge-maps/{mid}/classes/{cid}        mastery of every pupil of the class (published map)
         POST /teacher/knowledge-maps/{mid}/classes/{cid}/reinforce  {nodeKey, studentIds, count} one consolidation
                                                                    homework per pupil from the node's levelled questions
         PUT  /teacher/knowledge-maps/{mid}/classes/{cid}/ratings    {ratings} the teacher's own judgement per pupil and
                                                                    unit; the class view reports agreement with the map

Everything sits behind the ``KNOWLEDGE_MAP`` environment flag (default off; 404 when off). One map per school,
grade, subject and term; teachers of the school share it. Students and diagnosis (later PRs) only read the
published copy, so editing the draft never changes what pupils see until the teacher publishes again.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, delete, func, insert, select, update

from changying.services import visual_questions as vq
from changying.services import g3_question_drafts
from changying.services import g6_question_drafts
from changying.services import knowledge_maps as km

KNOWLEDGE_MAP_FLAG = "KNOWLEDGE_MAP"
NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}


def knowledge_map_enabled() -> bool:
    return os.getenv(KNOWLEDGE_MAP_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


class CreateBody(BaseModel):
    template: str = Field(max_length=40)


class SaveBody(BaseModel):
    map: dict[str, Any]
    revision: int = Field(ge=0)


class LevelsBody(BaseModel):
    levels: dict[str, str | None]
    revision: int = Field(ge=0)


class PublishBody(BaseModel):
    revision: int = Field(ge=0)


class Rating(BaseModel):
    studentId: int
    unitKey: str = Field(max_length=12)
    level: str | None = None


class RatingsBody(BaseModel):
    ratings: list[Rating] = Field(max_length=600)


class VisualBody(BaseModel):
    level: str = Field(max_length=10)
    count: int = Field(default=4, ge=1, le=8)


class VisualSaveBody(BaseModel):
    level: str = Field(max_length=10)
    revision: int = Field(ge=0)
    questions: list[dict[str, Any]] = Field(min_length=1, max_length=8)


class AIDraftBody(BaseModel):
    level: str = Field(max_length=10)
    count: int = Field(default=6, ge=2, le=10)
    questionType: str = Field(default="mixed", max_length=20)
    resourceIds: list[int] = Field(default_factory=list, max_length=20)


AI_REQUEST_TYPES = ("mixed", "single_choice", "true_false", "fill_blank", "calculation", "short_answer")


class ReinforceBody(BaseModel):
    nodeKey: str = Field(max_length=12)
    studentIds: list[int] = Field(max_length=60)
    count: int = Field(default=4, ge=1, le=10)
    dueDate: str | None = Field(default=None, max_length=20)


def register_knowledge_map_table(implementation: Any) -> Table:
    md = implementation.Base.metadata
    if "knowledge_maps" not in md.tables:
        Table("knowledge_maps", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("grade", Integer, nullable=False),
              Column("subject", String(30), nullable=False),
              Column("term", String(20), nullable=False),
              Column("textbook", String(80), nullable=False),
              Column("title", String(120), nullable=False),
              Column("template_key", String(40), nullable=False),
              Column("map_json", Text, nullable=False),                # the teacher's draft
              Column("revision", Integer, nullable=False),             # bumps on every save; stale saves get 409
              Column("published_json", Text, nullable=True),           # what diagnosis and students read
              Column("published_revision", Integer, nullable=True),
              Column("published_at", DateTime, nullable=True),
              Column("updated_by", Integer, nullable=False),
              Column("updated_at", DateTime, nullable=False),
              UniqueConstraint("school_id", "grade", "subject", "term", name="uq_knowledge_maps_school_term"))
    return md.tables["knowledge_maps"]


def register_knowledge_map_rating_table(implementation: Any) -> Table:
    md = implementation.Base.metadata
    if "knowledge_map_ratings" not in md.tables:
        Table("knowledge_map_ratings", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("map_id", Integer, nullable=False, index=True),
              Column("student_id", Integer, nullable=False, index=True),
              Column("unit_key", String(12), nullable=False),
              Column("level", String(10), nullable=False),              # weak | pass | fluent
              Column("teacher_id", Integer, nullable=False),
              Column("updated_at", DateTime, nullable=False),
              UniqueConstraint("map_id", "student_id", "unit_key", name="uq_knowledge_map_ratings_unit"))
    return md.tables["knowledge_map_ratings"]


def _drafts_for_grade(grade: int) -> set[str]:
    """该年级有预置草稿的知识点名；没有草稿的年级返回空集。"""
    from changying.services import g3_question_drafts, g6_question_drafts

    table = {3: g3_question_drafts.build_drafts(), 6: g6_question_drafts.build_drafts()}.get(grade)
    return set(table or {})


def install_knowledge_map_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "knowledge_map_installed", False):
        return app.state.knowledge_map_router
    t = register_knowledge_map_table(implementation)
    ratings = register_knowledge_map_rating_table(implementation)
    Question = implementation.Question
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def require_enabled() -> None:
        if not knowledge_map_enabled():
            raise HTTPException(404, "Not Found")

    def teacher(u: Any) -> None:
        require_enabled()
        need(u, "teacher")

    def my_map(db: Any, u: Any, mid: int, lock: bool = False) -> Any:
        q = select(t).where(t.c.id == mid, t.c.school_id == u.school_id)
        row = db.execute(q.with_for_update() if lock else q).first()
        if row is None:
            raise HTTPException(404, "没有找到这份知识地图")
        return row

    def fresh(row: Any, revision: int) -> None:
        if int(row.revision) != int(revision):
            raise HTTPException(409, "知识地图已被其他老师修改，请刷新后再改")

    def cleaned(raw: Any) -> dict[str, Any]:
        try:
            return km.clean_map(raw)
        except ValueError as e:
            raise HTTPException(400, str(e))

    def bank(db: Any, row: Any, names: list[str]) -> list[Any]:
        if not names:
            return []
        return list(db.scalars(select(Question).where(Question.school_id == row.school_id, Question.grade == row.grade,
                                                      Question.subject == row.subject, Question.knowledge.in_(names))
                               .order_by(Question.id).limit(300)))

    def existing_ids(db: Any, row: Any, m: dict[str, Any]) -> set[int]:
        ids = {int(q) for n in m["nodes"] for q in n["levels"]}
        if not ids:
            return set()
        return set(db.scalars(select(Question.id).where(Question.school_id == row.school_id, Question.id.in_(ids))))

    def detail(db: Any, row: Any) -> dict[str, Any]:
        m = json.loads(row.map_json)
        alive = existing_ids(db, row, m)
        names = sorted({b for n in m["nodes"] for b in n["bankKeys"]})
        per_name = dict(db.execute(select(Question.knowledge, func.count(Question.id)).where(
            Question.school_id == row.school_id, Question.grade == row.grade, Question.subject == row.subject,
            Question.knowledge.in_(names)).group_by(Question.knowledge)).all()) if names else {}
        nodes = []
        for n in m["nodes"]:
            nodes.append({**n, "assessed": km.assessed(m, n), "coverage": km.coverage(n, alive),
                          "bankCount": sum(int(per_name.get(b, 0)) for b in n["bankKeys"]) if n["kind"] != "display" else 0})
        ready = {n["key"]: n["coverage"]["ready"] for n in nodes}
        return {"id": row.id, "title": row.title, "grade": row.grade, "subject": row.subject, "term": row.term, "textbook": row.textbook,
                "revision": int(row.revision), "map": {**m, "nodes": nodes}, "dependents": km.dependents(m),
                "summary": km.summary(m, ready), "unitKinds": km.UNIT_KINDS, "nodeKinds": km.NODE_KINDS, "levels": km.LEVELS,
                "minPerLevel": km.MIN_PER_LEVEL, "minPerNode": km.MIN_PER_NODE,
                "visualNodes": vq.NODE_LABELS,
                # 哪些知识点有预置题目草稿：页面据此决定显不显示「导入预置题目草稿」按钮
                "draftNodes": sorted(set(_drafts_for_grade(row.grade)) & {n["name"] for n in m["nodes"]}),
                "published": None if row.published_revision is None else {
                    "revision": int(row.published_revision), "upToDate": int(row.published_revision) == int(row.revision),
                    "at": row.published_at.replace(tzinfo=None).isoformat(timespec="minutes") if row.published_at else None},
                "updatedAt": row.updated_at.isoformat(timespec="minutes")}

    def save(db: Any, u: Any, row: Any, m: dict[str, Any]) -> None:
        db.execute(update(t).where(t.c.id == row.id).values(map_json=json.dumps(m, ensure_ascii=False), revision=int(row.revision) + 1,
                                                            updated_by=u.id, updated_at=datetime.utcnow()))
        db.commit()

    @router.get("/knowledge-map/config")
    def config():
        require_enabled()
        return {"enabled": True}

    @router.get("/v1/knowledge-map", include_in_schema=False)
    def page():
        require_enabled()
        from changying.web.knowledge_map_pages import knowledge_map_page_html
        return HTMLResponse(knowledge_map_page_html(), headers=NO_CACHE)

    @router.get("/teacher/knowledge-maps")
    def list_maps(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        rows = db.execute(select(t).where(t.c.school_id == u.school_id).order_by(t.c.grade, t.c.subject, t.c.term)).all()
        used = {(r.grade, r.subject, r.term) for r in rows}
        return {"items": [{"id": r.id, "title": r.title, "revision": int(r.revision), "published": r.published_revision is not None,
                           "upToDate": r.published_revision is not None and int(r.published_revision) == int(r.revision)} for r in rows],
                "templates": [{"key": k, "label": v["label"]} for k, v in km.TEMPLATES.items()
                              if (v["grade"], v["subject"], v["term"]) not in used]}

    @router.post("/teacher/knowledge-maps")
    def create(b: CreateBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        if b.template not in km.TEMPLATES:
            raise HTTPException(400, "没有这个知识地图模板")
        meta = km.TEMPLATES[b.template]
        if db.execute(select(t.c.id).where(t.c.school_id == u.school_id, t.c.grade == meta["grade"], t.c.subject == meta["subject"],
                                           t.c.term == meta["term"])).first():
            raise HTTPException(409, "本校这个年级学期已经有知识地图了")
        m = km.clean_map(km.template(b.template))
        db.execute(insert(t).values(school_id=u.school_id, grade=meta["grade"], subject=meta["subject"], term=meta["term"],
                                    textbook=meta["textbook"], title=meta["label"], template_key=b.template,
                                    map_json=json.dumps(m, ensure_ascii=False), revision=0, updated_by=u.id, updated_at=datetime.utcnow()))
        db.commit()
        row = db.execute(select(t).where(t.c.school_id == u.school_id, t.c.grade == meta["grade"], t.c.subject == meta["subject"],
                                         t.c.term == meta["term"])).first()
        return detail(db, row)

    @router.get("/teacher/knowledge-maps/{mid}")
    def get_map(mid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        return detail(db, my_map(db, u, mid))

    @router.put("/teacher/knowledge-maps/{mid}")
    def put_map(mid: int, b: SaveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid, lock=True)
        fresh(row, b.revision)
        m = cleaned(b.map)
        # Question levels are only changed through the levels endpoint; a structure edit keeps them for kept nodes.
        old = {n["key"]: n["levels"] for n in json.loads(row.map_json)["nodes"]}
        for n in m["nodes"]:
            n["levels"] = old.get(n["key"], {}) if n["kind"] != "display" else {}
        save(db, u, row, m)
        return detail(db, my_map(db, u, mid))

    @router.get("/teacher/knowledge-maps/{mid}/nodes/{key}/questions")
    def node_questions(mid: int, key: str, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid)
        m = json.loads(row.map_json)
        node = next((n for n in m["nodes"] if n["key"] == key), None)
        if node is None or node["kind"] == "display":
            raise HTTPException(404, "没有找到这个知识点")
        found = {q.id: q for q in bank(db, row, node["bankKeys"])}
        # Questions already levelled stay listed even if their knowledge name was changed later.
        extra = [int(q) for q in node["levels"] if int(q) not in found]
        if extra:
            found.update({q.id: q for q in db.scalars(select(Question).where(Question.school_id == row.school_id, Question.id.in_(extra)))})
        items = [{"id": q.id, "text": q.text, "type": q.question_type or "single_choice", "knowledge": q.knowledge, "unit": q.unit,
                  "level": node["levels"].get(str(q.id)), "note": diagnosis_note(q)} for q in sorted(found.values(), key=lambda q: q.id)]
        return {"key": key, "name": node["name"], "bankKeys": node["bankKeys"], "items": items, "revision": int(row.revision)}

    def diagnosis_note(q: Any) -> str:
        """Why a question can be levelled but will not be picked for the diagnosis (empty when it can)."""
        if implementation.question_type_of(q) not in implementation.AUTO_GRADED_QUESTION_TYPES:
            return "需老师批改，诊断不会选"
        figure = implementation.question_figure(q)
        if figure and figure.get("type") not in km.SHOWN_FIGURES:
            return "含绘制图示，诊断暂不选"
        return ""

    def visual_node(db: Any, u: Any, mid: int, key: str, lock: bool = False) -> tuple[Any, dict[str, Any]]:
        row = my_map(db, u, mid, lock=lock)
        node = next((n for n in json.loads(row.map_json)["nodes"] if n["key"] == key), None)
        if node is None or not vq.supports(getattr(row, "template_key", None), key):
            raise HTTPException(404, "这个知识点暂时没有系统画图题")
        return row, node

    @router.post("/teacher/knowledge-maps/{mid}/nodes/{key}/ai")
    def ai_drafts(mid: int, key: str, b: AIDraftBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """AI drafts for one point: mixed types by default, then checked here (steps for the level, maths answers
        recomputed) so that only drafts as hard as their level, with answers that add up, reach the teacher."""
        teacher(u)
        row = my_map(db, u, mid)
        m = json.loads(row.map_json)
        node = next((n for n in m["nodes"] if n["key"] == key), None)
        if node is None or node["kind"] == "display":
            raise HTTPException(404, "这个知识点不出题")
        if b.level not in km.LEVELS:
            raise HTTPException(400, "难度档只能是基础、中等或提高")
        if b.questionType not in AI_REQUEST_TYPES or (b.questionType in ("calculation", "short_answer") and "数学" not in row.subject):
            raise HTTPException(400, "题型不对")
        unit = next((x for x in m["units"] if x["key"] == node["unit"]), {"name": ""})
        maths = "数学" in row.subject
        ids = [int(q) for q in node["levels"]][:12]
        seen = db.scalars(select(Question.text).where(Question.school_id == row.school_id, Question.id.in_(ids))).all() if ids else []
        avoid = ("已有题目（不要重复这些题，也不要只换数字）：" + "；".join(t.strip()[:40] for t in seen) + "。") if seen else ""
        body = implementation.AIQuestionGenerateBody(
            # The map says e.g. "人教版 2026"; the textbook registry knows the publisher line ("人教版").
            grade=row.grade, subject=row.subject, textbook="人教版" if "人教" in row.textbook else row.textbook, semester=row.term, unit=unit["name"],
            knowledge=(node["bankKeys"] or [node["name"]])[0], difficulty=km.LEVELS[b.level],
            count=min(b.count + (4 if maths else 3), 20),                 # some will not pass the checks below
            question_type=b.questionType, resource_ids=b.resourceIds,
            notes=f"知识点：{node['name']}。说明：{node.get('detail') or node['name']}。题目只考这一个知识点；题干不能依赖图片，"
                  "涉及图形、方向、方格位置时用文字说清楚。" + ("题型要多样，不要全是选择题。" if b.questionType == "mixed" else "") + avoid
                  + ("\n" + km.angle_brief(b.level, b.count, unit["name"]) if maths else ""))
        route = next(r for r in implementation.app.routes if getattr(r, "path", "") == "/ai/questions/generate" and "POST" in getattr(r, "methods", ()))
        got = route.dependant.call(b=body, u=u, db=db)
        kept, dropped = [], {}
        for item in got.get("items") or []:
            ok, why = km.check_ai_question(item, b.level, row.subject, unit["name"])
            if ok is None:
                dropped[why] = dropped.get(why, 0) + 1
            else:
                kept.append(ok)
        items = km.pick_ai_drafts(kept, b.count, b.level if maths else "", list(seen), unit["name"])
        if not items:
            raise HTTPException(502, "AI 这次出的题都没通过检查（" + "、".join(f"{k} {v} 道" for k, v in dropped.items()) + "），请再试一次")
        return {"items": items, "dropped": dropped, "short": b.count - len(items), "level": b.level,
                "notice": got.get("notice", ""), "verified": sum(1 for x in items if x["verified"])}

    @router.post("/teacher/knowledge-maps/{mid}/nodes/{key}/visual")
    def visual_drafts(mid: int, key: str, b: VisualBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        visual_node(db, u, mid, key)
        if b.level not in km.LEVELS:
            raise HTTPException(400, "难度档只能是基础、中等或提高")
        items = vq.generate(key, b.level, b.count, secrets.randbelow(10 ** 9), getattr(my_map(db, u, mid), "template_key", None))
        if not items:
            raise HTTPException(502, "这次没有生成合适的题，请再点一次")
        return {"kind": vq.NODE_LABELS[key], "level": b.level, "items": items}

    @router.post("/teacher/knowledge-maps/{mid}/nodes/{key}/visual/save")
    def visual_save(mid: int, key: str, b: VisualSaveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row, node = visual_node(db, u, mid, key, lock=True)
        fresh(row, b.revision)
        if b.level not in km.LEVELS:
            raise HTTPException(400, "难度档只能是基础、中等或提高")
        I = implementation
        unit = next((x["name"] for x in json.loads(row.map_json)["units"] if x["key"] == node["unit"]), "")
        ids = []
        for raw in b.questions:
            try:
                qt = raw.get("question_type") if raw.get("question_type") in ("single_choice", "fill_blank") else "single_choice"
                q = I.QuestionCreate(**{**raw, "grade": row.grade, "subject": row.subject, "textbook": "人教版", "semester": row.term,
                                        "unit": unit, "knowledge": node["bankKeys"][0], "question_type": qt})
            except ValueError:
                raise HTTPException(400, "图形题格式不对，请重新生成")
            if not vq.sanitize(q.figure) or not q.text.strip():
                raise HTTPException(400, "图形题的图或题干不完整，请重新生成")
            qt, opts, ci, exp, answer_json, figure_json = I._ai_question_storage_parts(q)
            r = Question(school_id=u.school_id, grade=q.grade, subject=q.subject, textbook=q.textbook, semester=q.semester, unit=q.unit[:100],
                         knowledge=q.knowledge[:120], text=q.text, options_json=json.dumps(opts, ensure_ascii=False), correct_index=ci,
                         explanation=exp, question_type=qt, answer_json=answer_json, figure_json=figure_json, creator_id=u.id)
            db.add(r)
            db.flush()
            ids.append(r.id)
        m = json.loads(row.map_json)
        target = next(n for n in m["nodes"] if n["key"] == key)
        target["levels"].update({str(i): b.level for i in ids})
        I.audit(db, u, "knowledge_map.visual.save", f"map={row.id}:node={key}:level={b.level}:questions={len(ids)}")
        save(db, u, row, cleaned(m))
        return {**detail(db, my_map(db, u, mid)), "saved": ids}

    @router.get("/teacher/knowledge-maps/{mid}/bank")
    def bank_search(mid: int, unit: str = "", q: str = "", u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid)
        base = select(Question).where(Question.school_id == row.school_id, Question.grade == row.grade, Question.subject == row.subject)
        units = [x for x in db.scalars(select(Question.unit).where(Question.school_id == row.school_id, Question.grade == row.grade,
                                                                     Question.subject == row.subject).distinct().order_by(Question.unit)) if x]
        unit, q = unit.strip()[:100], " ".join(q.split())[:60]
        if not unit and not q:
            return {"units": units, "items": [], "total": 0}
        if unit:
            base = base.where(Question.unit == unit)
        if q:
            like = "%" + q.replace("%", "").replace("_", "") + "%"
            base = base.where((Question.text.like(like)) | (Question.knowledge.like(like)))
        total = db.scalar(select(func.count()).select_from(base.subquery()))
        m = json.loads(row.map_json)
        placed = {int(qid): (n["key"], lv) for n in m["nodes"] for qid, lv in n["levels"].items()}
        items = [{"id": x.id, "text": x.text, "type": x.question_type or "single_choice", "knowledge": x.knowledge, "unit": x.unit,
                  "note": diagnosis_note(x), "placed": placed.get(x.id)} for x in db.scalars(base.order_by(Question.id).limit(80))]
        return {"units": units, "items": items, "total": int(total or 0)}

    @router.post("/teacher/knowledge-maps/{mid}/nodes/{key}/drafts")
    def import_drafts(mid: int, key: str, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """把这个知识点的预置题目草稿导入本校题库，并按草稿标注的分档挂到节点上。

        只导入本校没有的（同年级、同知识点、同题干视为同一题）；题目仍是普通题库题，
        老师可以逐题审核、改题干或换档，确认后再发布地图。
        """
        teacher(u)
        row = my_map(db, u, mid, lock=True)
        m = json.loads(row.map_json)
        node = next((n for n in m["nodes"] if n["key"] == key), None)
        if node is None or node["kind"] == "display":
            raise HTTPException(404, "没有找到这个知识点")
        drafts_by_grade = {3: g3_question_drafts.build_drafts(), 6: g6_question_drafts.build_drafts()}
        drafts = drafts_by_grade.get(row.grade, {}).get(node["name"])
        if not drafts:
            raise HTTPException(400, "这个知识点没有预置的题目草稿")
        unit_name = next((x["name"] for x in m["units"] if x["key"] == node["unit"]), "")

        existing = {t: i for t, i in db.execute(
            select(Question.text, Question.id).where(
                Question.school_id == row.school_id,
                Question.grade == row.grade,
                Question.subject == row.subject,
                Question.knowledge == node["name"],
            )
        ).all()}
        added, reused = [], 0
        for draft in drafts:
            qid = existing.get(draft["text"])
            if qid:
                reused += 1
            else:
                q = Question(
                    school_id=row.school_id, grade=row.grade, subject=row.subject,
                    textbook=row.textbook, semester=row.term, unit=unit_name,
                    knowledge=node["name"], text=draft["text"], options_json="[]",
                    correct_index=0, explanation="", question_type="fill_blank",
                    answer_json=json.dumps({"answer": draft["answer"]}, ensure_ascii=False),
                    creator_id=u.id,
                )
                db.add(q)
                db.flush()
                qid = q.id
                added.append(qid)
            node["levels"][str(qid)] = draft["level"]

        save(db, u, row, cleaned(m))
        implementation.audit(db, u, "km.drafts.import", f"map={mid};node={key};added={len(added)};reused={reused}")
        db.commit()
        out = detail(db, my_map(db, u, mid))
        out["imported"] = {"added": len(added), "reused": reused, "node": node["name"]}
        return out

    @router.put("/teacher/knowledge-maps/{mid}/nodes/{key}/levels")
    def put_levels(mid: int, key: str, b: LevelsBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid, lock=True)
        fresh(row, b.revision)
        m = json.loads(row.map_json)
        node = next((n for n in m["nodes"] if n["key"] == key), None)
        if node is None or node["kind"] == "display":
            raise HTTPException(404, "没有找到这个知识点")
        ids = {int(q) for q in b.levels if str(q).isdigit()}
        if len(ids) != len(b.levels):
            raise HTTPException(400, "题目编号不对")
        owned = set(db.scalars(select(Question.id).where(Question.school_id == row.school_id, Question.id.in_(ids)))) if ids else set()
        if owned != ids:
            raise HTTPException(400, "只能给本校题库里的题目分档")
        for qid, level in b.levels.items():
            if level is None:
                node["levels"].pop(str(int(qid)), None)
            elif level in km.LEVELS:
                node["levels"][str(int(qid))] = level
            else:
                raise HTTPException(400, "难度档只能是基础、中等或提高")
        save(db, u, row, cleaned(m))
        return detail(db, my_map(db, u, mid))

    @router.post("/teacher/knowledge-maps/{mid}/units/{ukey}/restore")
    def restore_unit(mid: int, ukey: str, b: PublishBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid, lock=True)
        fresh(row, b.revision)
        if row.template_key not in km.TEMPLATES:
            raise HTTPException(400, "这份知识地图没有对应的模板")
        tmpl = km.template(row.template_key)
        m = json.loads(row.map_json)
        if not any(x["key"] == ukey for x in m["units"]) or not any(x["key"] == ukey for x in tmpl["units"]):
            raise HTTPException(404, "模板里没有这个单元")
        restored_map, restored = km.restore_unit(m, tmpl, ukey)
        if not restored:
            raise HTTPException(409, "这个单元模板里的知识点都还在，不需要恢复")
        save(db, u, row, cleaned(restored_map))
        return {**detail(db, my_map(db, u, mid)), "restored": restored}

    @router.post("/teacher/knowledge-maps/{mid}/publish")
    def publish(mid: int, b: PublishBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid, lock=True)
        fresh(row, b.revision)
        m = cleaned(json.loads(row.map_json))
        if not any(km.assessed(m, n) for n in m["nodes"]):
            raise HTTPException(400, "还没有标记为已学的单元，发布后无法诊断")
        db.execute(update(t).where(t.c.id == row.id).values(published_json=json.dumps(m, ensure_ascii=False), published_revision=int(row.revision),
                                                            published_at=datetime.utcnow()))
        db.commit()
        return detail(db, my_map(db, u, mid))

    @router.get("/teacher/knowledge-maps/{mid}/classes")
    def classes(mid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid)
        SC = implementation.SchoolClass
        rows = db.scalars(select(SC).where(SC.school_id == u.school_id, SC.teacher_id == u.id).order_by(SC.name, SC.id)).all()
        return {"items": [{"id": c.id, "name": c.name, "grade": c.grade, "sameGrade": int(c.grade or 0) == int(row.grade),
                           "studentCount": len(pupils(db, u, c.id))} for c in rows]}

    def pupils(db: Any, u: Any, cid: int) -> list[Any]:
        User, CS = implementation.User, implementation.ClassStudent
        return list(db.scalars(select(User).join(CS, CS.student_id == User.id).where(
            CS.class_id == cid, User.school_id == u.school_id, User.role == "student", User.active == True)  # noqa: E712
            .order_by(User.name, User.id)))

    def answers_of(db: Any, u: Any, ids: list[int]) -> dict[int, list[Any]]:
        """Every pupil's submissions in order (oldest first), read in one query."""
        Submission = implementation.Submission
        answers: dict[int, list[Any]] = {i: [] for i in ids}
        if ids:
            for sid, raw in db.execute(select(Submission.student_id, Submission.answers_json).where(
                    Submission.school_id == u.school_id, Submission.student_id.in_(ids)).order_by(Submission.submitted_at, Submission.id)):
                try:
                    answers[sid].append(json.loads(raw or "[]"))
                except ValueError:
                    continue
        return answers

    def own_class(db: Any, u: Any, cid: int) -> Any:
        SC = implementation.SchoolClass
        cls = db.scalar(select(SC).where(SC.id == cid, SC.school_id == u.school_id, SC.teacher_id == u.id))
        if cls is None:
            raise HTTPException(404, "没有找到这个班级")
        return cls

    @router.get("/teacher/knowledge-maps/{mid}/classes/{cid}")
    def class_mastery(mid: int, cid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid)
        cls = own_class(db, u, cid)
        if row.published_json is None:
            raise HTTPException(409, "知识地图还没有发布，发布后才能查看全班掌握情况")
        from changying.web.knowledge_map_student import register_knowledge_map_run_table
        from changying.services.knowledge_map_evidence import collect_cross_scene_evidence
        runs = register_knowledge_map_run_table(implementation)
        m = json.loads(row.published_json)
        kids = pupils(db, u, cls.id)
        ids = [k.id for k in kids]
        answers = answers_of(db, u, ids)
        evidence_by_student = collect_cross_scene_evidence(db, implementation, row, m, ids)
        diag = {r.student_id: r for r in db.execute(select(runs).where(runs.c.map_id == row.id, runs.c.school_id == u.school_id,
                                                                         runs.c.student_id.in_(ids)))} if ids else {}
        students = []
        for k in kids:
            node_m, unit_m = km.mastery_view(m, km.first_attempts(answers[k.id]))
            r = diag.get(k.id)
            students.append({"id": k.id, "name": k.name, "nodes": node_m, "units": unit_m,
                             "evidence": evidence_by_student.get(k.id, []),
                             "diagnosis": {"status": "new"} if r is None else {"status": r.status, "count": len(json.loads(r.items_json)),
                                                                                 "correct": r.correct}})
        nodes = [{"key": n["key"], "unit": n["unit"], "name": n["name"]} for n in m["nodes"] if km.assessed(m, n)]
        tally = {}
        for n in nodes:
            c = {"weak": 0, "pass": 0, "fluent": 0, "insufficient": 0}
            for st in students:
                c[st["nodes"][n["key"]]["level"] or "insufficient"] += 1
            tally[n["key"]] = c
        rated: dict[int, dict[str, str]] = {}
        if ids:
            for r in db.execute(select(ratings).where(ratings.c.map_id == row.id, ratings.c.school_id == u.school_id,
                                                      ratings.c.student_id.in_(ids))):
                rated.setdefault(r.student_id, {})[r.unit_key] = r.level
        units_shown = [x["key"] for x in m["units"] if any(n["unit"] == x["key"] for n in nodes)]
        pairs = [(st["units"][k]["level"], rated.get(st["id"], {}).get(k)) for st in students for k in units_shown
                 if st["units"].get(k) and rated.get(st["id"], {}).get(k)]
        compared = [(a, b) for a, b in pairs if a]
        agreed = sum(1 for a, b in compared if a == b)
        agreement = {"rated": len(pairs), "compared": len(compared), "agreed": agreed, "threshold": km.AGREEMENT_TARGET,
                     "rate": round(agreed / len(compared), 2) if compared else None,
                     "passed": bool(compared) and agreed / len(compared) >= km.AGREEMENT_TARGET}
        for st in students:
            st["ratings"] = rated.get(st["id"], {})
        return {"agreement": agreement, "classId": cls.id, "className": cls.name, "title": row.title, "publishedRevision": int(row.published_revision),
                "units": [x for x in m["units"] if any(n["unit"] == x["key"] for n in nodes)], "nodes": nodes, "tally": tally,
                "students": students, "masteryLabels": km.MASTERY_LABELS, "confidenceLabels": km.CONFIDENCE_LABELS,
                "evidenceDisclaimer": "跨场景学习证据按原始来源分别展示（含时间、数量、批改状态与受助/提示状态），不直接合并或修改掌握度结论；无法区分是否受助的记录标注为“未知”。"}

    @router.post("/teacher/knowledge-maps/{mid}/classes/{cid}/reinforce")
    def reinforce(mid: int, cid: int, b: ReinforceBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid)
        cls = own_class(db, u, cid)
        if row.published_json is None:
            raise HTTPException(409, "知识地图还没有发布")
        m = json.loads(row.published_json)
        node = next((n for n in m["nodes"] if n["key"] == b.nodeKey and km.assessed(m, n)), None)
        if node is None:
            raise HTTPException(404, "这个知识点现在不参加诊断，不能布置巩固")
        kids = {k.id: k for k in pupils(db, u, cls.id)}
        wanted = list(dict.fromkeys(b.studentIds))
        if not wanted or any(s not in kids for s in wanted):
            raise HTTPException(400, "只能给本班学生布置")
        I = implementation
        levelled = {int(q): lv for q, lv in node["levels"].items()}
        bank = {q.id: q for q in db.scalars(select(Question).where(Question.school_id == u.school_id, Question.id.in_(list(levelled))))} if levelled else {}
        usable = [q for q in bank.values() if I.question_type_of(q) in I.AUTO_GRADED_QUESTION_TYPES
                  and (not I.question_figure(q) or I.question_figure(q).get("type") in km.SHOWN_FIGURES)]
        title = f"知识地图巩固 · {node['name']}"[:160]
        answers = answers_of(db, u, wanted)
        order = {"basic": 0, "medium": 1, "hard": 2}
        results = []
        for sid in wanted:
            kid = kids[sid]
            open_one = db.scalar(select(I.Assignment.id).join(I.AssignmentRecipient, I.AssignmentRecipient.assignment_id == I.Assignment.id).where(
                I.Assignment.school_id == u.school_id, I.Assignment.title == title, I.AssignmentRecipient.student_id == sid,
                ~select(I.Submission.id).where(I.Submission.assignment_id == I.Assignment.id, I.Submission.student_id == sid).exists()).limit(1))
            if open_one:
                results.append({"studentId": sid, "name": kid.name, "ok": False, "reason": "已有未完成的这项巩固练习"})
                continue
            seen = set(km.first_attempts(answers[sid])) | I.protected_question_ids_for_student(db, kid)
            # Questions the pupil has never answered, easiest first: their answers count as first attempts.
            picks = sorted((q for q in usable if q.id not in seen), key=lambda q: (order[levelled[q.id]], q.id))[: b.count]
            if not picks:
                results.append({"studentId": sid, "name": kid.name, "ok": False, "reason": "没有这名学生没做过的题，请先给这个知识点补题"})
                continue
            p = I.Paper(school_id=u.school_id, title=title, grade=row.grade, subject=row.subject, textbook=picks[0].textbook or "",
                        unit=picks[0].unit or "", question_ids_json=json.dumps([q.id for q in picks]), teacher_id=u.id)
            db.add(p); db.flush()
            due = (b.dueDate or (datetime.now(I.SCHOOL_TZ).date() + timedelta(days=3)).isoformat())[:20]
            a = I.Assignment(school_id=u.school_id, title=title, class_id=cls.id, paper_id=p.id, due_date=due)
            db.add(a); db.flush()
            db.add(I.AssignmentSubmissionSetting(school_id=u.school_id, assignment_id=a.id, mode="quiz",
                                                 instructions=f"知识地图巩固：{node['name']}。认真完成，每道题都按第一次作答记入掌握情况。"))
            I.ensure_recipient(db, a, sid, "knowledge_map")
            I.audit(db, u, "knowledge_map.reinforce", f"map={row.id}:node={node['key']}:student={sid}:assignment={a.id}:questions={len(picks)}")
            results.append({"studentId": sid, "name": kid.name, "ok": True, "assignmentId": a.id, "questionCount": len(picks)})
        db.commit()
        return {"node": {"key": node["key"], "name": node["name"]}, "results": results}

    @router.put("/teacher/knowledge-maps/{mid}/classes/{cid}/ratings")
    def put_ratings(mid: int, cid: int, b: RatingsBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid)
        cls = own_class(db, u, cid)
        if row.published_json is None:
            raise HTTPException(409, "知识地图还没有发布")
        m = json.loads(row.published_json)
        units = {x["key"] for x in m["units"] if any(km.assessed(m, n) and n["unit"] == x["key"] for n in m["nodes"])}
        kids = {k.id for k in pupils(db, u, cls.id)}
        for r in b.ratings:
            if r.studentId not in kids or r.unitKey not in units:
                raise HTTPException(400, "只能给本班学生、已学单元填写判断")
            if r.level is not None and r.level not in km.MASTERY_LABELS:
                raise HTTPException(400, "判断只能是薄弱、达标或熟练")
        now = datetime.utcnow()
        for r in b.ratings:
            where = (ratings.c.map_id == row.id, ratings.c.student_id == r.studentId, ratings.c.unit_key == r.unitKey,
                     ratings.c.school_id == u.school_id)
            old = db.execute(select(ratings.c.id).where(*where)).first()
            if r.level is None:
                if old:
                    db.execute(delete(ratings).where(ratings.c.id == old.id))
            elif old:
                db.execute(update(ratings).where(ratings.c.id == old.id).values(level=r.level, teacher_id=u.id, updated_at=now))
            else:
                db.execute(insert(ratings).values(school_id=u.school_id, map_id=row.id, student_id=r.studentId, unit_key=r.unitKey,
                                                  level=r.level, teacher_id=u.id, updated_at=now))
        db.commit()
        return class_mastery(mid, cid, u, db)

    app.include_router(router)
    app.state.knowledge_map_installed = True
    app.state.knowledge_map_router = router
    return router


__all__ = ["install_knowledge_map_views", "knowledge_map_enabled", "register_knowledge_map_rating_table", "register_knowledge_map_table"]
