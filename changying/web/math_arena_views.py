"""数学通用知识地图（自带题点亮）与强应试专项（多题型限时分级达标）学生端路由.

独立双入口、数据互通：
- 知识地图（基础模块，开箱自带题，无需教师逐题导入、不强绑定教材版本）：
  GET  /v1/math-star-map
  GET  /student/math-star-map
  POST /student/math-star-map/nodes/{key}/quiz
  POST /student/math-star-map/nodes/{key}/quiz/submit
- 强应试专项（独立入口，多题型 + 严格倒计时自动交卷 + L1-L4 分级达标）：
  GET  /v1/math-sprints
  GET  /student/math-sprints
  POST /student/math-sprints/{slug}/start
  POST /student/math-sprints/attempts/{attempt_id}/submit
"""
from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, desc, insert, select, update

from changying.services import arena_grade_profiles as agp
from changying.services import arena_review_and_custom as arc
from changying.services import exam_sprints as es
from changying.services import math_arena_points as mapts
from changying.services import math_builtin_map as mbm
from changying.web.arena_wrongbook import record_arena_outcomes
from changying.web.knowledge_map_views import NO_CACHE


class BuiltinAnswerItem(BaseModel):
    question_id: str = Field(min_length=1, max_length=120)
    selected_index: int | None = None
    text_answer: str = Field(default="", max_length=500)


class NodeQuizSubmitBody(BaseModel):
    quiz_id: int
    answers: list[BuiltinAnswerItem]


class SprintSubmitBody(BaseModel):
    answers: list[BuiltinAnswerItem] = Field(default_factory=list)
    auto_submitted: bool = False


def register_math_arena_tables(implementation: Any) -> dict[str, Table]:
    md = implementation.Base.metadata
    if "math_node_mastery" not in md.tables:
        Table(
            "math_node_mastery",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("node_key", String(24), nullable=False),
            Column("attempts", Integer, nullable=False, default=0),
            Column("correct", Integer, nullable=False, default=0),
            Column("hard_correct", Integer, nullable=False, default=0),
            Column("best_quiz_rate_pct", Integer, nullable=False, default=0),
            Column("sprint_boost_stars", Integer, nullable=False, default=0),
            Column("needs_repair", Integer, nullable=False, default=0),
            Column("updated_at", DateTime, nullable=False),
            UniqueConstraint("school_id", "student_id", "node_key", name="uq_math_node_mastery_student"),
        )
    if "math_node_quizzes" not in md.tables:
        Table(
            "math_node_quizzes",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("node_key", String(24), nullable=False),
            Column("items_json", Text, nullable=False),
            Column("status", String(16), nullable=False),  # open | submitted
            Column("correct", Integer, nullable=True),
            Column("total", Integer, nullable=True),
            Column("created_at", DateTime, nullable=False),
            Column("submitted_at", DateTime, nullable=True),
        )
    if "math_sprint_attempts" not in md.tables:
        Table(
            "math_sprint_attempts",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("slug", String(48), nullable=False, index=True),
            Column("items_json", Text, nullable=False),
            Column("time_limit_sec", Integer, nullable=False),
            Column("status", String(16), nullable=False),  # open | submitted
            Column("started_at", DateTime, nullable=False),
            Column("submitted_at", DateTime, nullable=True),
            Column("elapsed_sec", Integer, nullable=True),
            Column("earned_marks", Integer, nullable=True),
            Column("total_marks", Integer, nullable=True),
            Column("score_rate", Integer, nullable=True),
            Column("tier_code", String(8), nullable=True),
            Column("result_json", Text, nullable=True),
        )
    return {
        "mastery": md.tables["math_node_mastery"],
        "quizzes": md.tables["math_node_quizzes"],
        "sprints": md.tables["math_sprint_attempts"],
    }


def install_math_arena_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "math_arena_installed", False):
        return app.state.math_arena_router
    tables = register_math_arena_tables(implementation)
    t_mastery, t_quizzes, t_sprints = tables["mastery"], tables["quizzes"], tables["sprints"]
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def ensure_tables(db: Any) -> None:
        arc.ensure_tables_on_session(db, t_mastery, t_quizzes, t_sprints)

    def upsert_node_mastery(
        db: Any,
        u: Any,
        *,
        node_key: str,
        add_attempts: int,
        add_correct: int,
        add_hard_correct: int,
        quiz_rate_pct: int | None = None,
        boost_stars: int = 0,
        needs_repair: bool | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        now = datetime.utcnow()
        row = db.execute(
            select(t_mastery).where(
                t_mastery.c.school_id == u.school_id,
                t_mastery.c.student_id == u.id,
                t_mastery.c.node_key == node_key,
            )
        ).first()
        if row is None:
            prev_st = mbm.compute_node_light_state(attempts=0, correct=0)
            new_attempts = max(0, add_attempts)
            new_correct = max(0, add_correct)
            new_hard = max(0, add_hard_correct)
            new_best = max(0, quiz_rate_pct or 0)
            new_boost = max(0, boost_stars)
            new_repair = 1 if needs_repair else 0
            db.execute(
                insert(t_mastery).values(
                    school_id=u.school_id,
                    student_id=u.id,
                    node_key=node_key,
                    attempts=new_attempts,
                    correct=new_correct,
                    hard_correct=new_hard,
                    best_quiz_rate_pct=new_best,
                    sprint_boost_stars=new_boost,
                    needs_repair=new_repair,
                    updated_at=now,
                )
            )
        else:
            prev_st = mbm.compute_node_light_state(
                attempts=int(row.attempts),
                correct=int(row.correct),
                best_quiz_rate=int(row.best_quiz_rate_pct) / 100.0,
                hard_correct=int(row.hard_correct),
                sprint_boost_stars=int(row.sprint_boost_stars),
                needs_repair=bool(row.needs_repair),
            )
            new_attempts = int(row.attempts) + max(0, add_attempts)
            new_correct = int(row.correct) + max(0, add_correct)
            new_hard = int(row.hard_correct) + max(0, add_hard_correct)
            new_best = max(int(row.best_quiz_rate_pct), int(quiz_rate_pct or 0))
            new_boost = max(int(row.sprint_boost_stars), int(boost_stars))
            if needs_repair is None:
                new_repair = int(row.needs_repair)
            else:
                new_repair = 1 if needs_repair else 0
            db.execute(
                update(t_mastery)
                .where(t_mastery.c.id == row.id)
                .values(
                    attempts=new_attempts,
                    correct=new_correct,
                    hard_correct=new_hard,
                    best_quiz_rate_pct=new_best,
                    sprint_boost_stars=new_boost,
                    needs_repair=new_repair,
                    updated_at=now,
                )
            )
        next_st = mbm.compute_node_light_state(
            attempts=new_attempts,
            correct=new_correct,
            best_quiz_rate=new_best / 100.0,
            hard_correct=new_hard,
            sprint_boost_stars=new_boost,
            needs_repair=bool(new_repair),
        )
        return prev_st, next_st

    def build_map_payload(db: Any, u: Any, grade: int | None = None) -> dict[str, Any]:
        ensure_tables(db)
        student_grade = agp.detect_user_grade(implementation, db, u)
        active_grade = agp.resolve_arena_grade(grade, student_grade, subject="数学")
        m = mbm.get_builtin_math_map(active_grade)
        rows = db.execute(
            select(t_mastery).where(t_mastery.c.school_id == u.school_id, t_mastery.c.student_id == u.id)
        ).all()
        by_key = {r.node_key: r for r in rows}
        now = datetime.utcnow()
        nodes_out: list[dict[str, Any]] = []
        lit_count = 0
        mastered_count = 0
        repair_count = 0
        review_due_count = 0
        total_stars = 0

        for n in m["nodes"]:
            r = by_key.get(n["key"])
            if r is None:
                st = mbm.compute_node_light_state(attempts=0, correct=0)
            else:
                st = mbm.compute_node_light_state(
                    attempts=int(r.attempts),
                    correct=int(r.correct),
                    best_quiz_rate=int(r.best_quiz_rate_pct) / 100.0,
                    hard_correct=int(r.hard_correct),
                    sprint_boost_stars=int(r.sprint_boost_stars),
                    needs_repair=bool(r.needs_repair),
                )
            rev = arc.compute_review_meta(
                r,
                now=now,
                stars=int(st["stars"]),
                needs_repair=bool(st["needsRepair"]),
            )
            st = {**st, **rev}
            if st["state"] in ("lit", "mastered"):
                lit_count += 1
            if st["state"] == "mastered":
                mastered_count += 1
            if st["needsRepair"]:
                repair_count += 1
            if rev["reviewDue"]:
                review_due_count += 1
            total_stars += int(st["stars"])
            nodes_out.append({
                "key": n["key"],
                "unit": n["unit"],
                "name": n["name"],
                "detail": n["detail"],
                "prereqs": n["prereqs"],
                "light": st,
                "reviewDue": rev["reviewDue"],
                "daysSincePractice": rev["daysSincePractice"],
                "reviewCycleDays": rev["reviewCycleDays"],
            })

        unit_summary: list[dict[str, Any]] = []
        for unit in m["units"]:
            u_nodes = [x for x in nodes_out if x["unit"] == unit["key"]]
            u_lit = sum(1 for x in u_nodes if x["light"]["state"] in ("lit", "mastered"))
            unit_summary.append({
                **unit,
                "totalNodes": len(u_nodes),
                "litNodes": u_lit,
            })

        return {
            "title": m["title"],
            "subject": m["subject"],
            "grade": active_grade,
            "studentGrade": student_grade,
            "availableGrades": agp.build_available_grades(active_grade, student_grade, subject="数学"),
            "ageProfile": agp.get_age_interaction_profile(active_grade),
            "textbookAgnostic": True,
            "summary": {
                "totalNodes": len(nodes_out),
                "litNodes": lit_count,
                "masteredNodes": mastered_count,
                "repairNodes": repair_count,
                "reviewDueCount": review_due_count,
                "totalStars": total_stars,
                "maxStars": len(nodes_out) * 3,
            },
            "units": unit_summary,
            "nodes": nodes_out,
            "lightStates": mbm.LIGHT_STATES,
            "points": mapts.student_arena_points_summary(implementation, db, u),
        }

    @router.get("/v1/math-star-map", include_in_schema=False)
    def star_map_page():
        from changying.web.math_arena_pages import math_star_map_page_html
        return HTMLResponse(math_star_map_page_html(), headers=NO_CACHE)

    @router.get("/v1/math-sprints", include_in_schema=False)
    def sprints_page():
        from changying.web.math_arena_pages import math_sprints_page_html
        return HTMLResponse(math_sprints_page_html(), headers=NO_CACHE)

    @router.get("/student/math-star-map")
    def get_star_map(grade: int | None = None, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        return build_map_payload(db, u, grade=grade)

    @router.post("/student/math-star-map/nodes/{key}/quiz")
    def start_node_quiz(key: str, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        ensure_tables(db)
        student_grade = agp.detect_user_grade(implementation, db, u)
        target_grade = agp.infer_grade_from_node_key(key, student_grade)
        m = mbm.get_builtin_math_map(target_grade)
        node = next((n for n in m["nodes"] if n["key"] == key), None) or mbm.get_all_math_nodes().get(key)
        if node is None:
            raise HTTPException(404, "没有找到这个知识点")
        past_count = len(
            db.execute(
                select(t_quizzes.c.id).where(
                    t_quizzes.c.school_id == u.school_id,
                    t_quizzes.c.student_id == u.id,
                    t_quizzes.c.node_key == key,
                )
            ).all()
        )
        seed = (int(u.id) * 17 + past_count * 7 + len(key)) % 97
        custom_qs = arc.fetch_custom_quiz_questions(
            implementation, db, school_id=int(u.school_id), subject="数学", node_key=key, limit=3, seed=seed
        )
        builtin_qs = mbm.generate_node_questions(key, count=max(0, 5 - len(custom_qs)), seed=seed)
        qs = custom_qs + builtin_qs
        res = db.execute(
            insert(t_quizzes).values(
                school_id=u.school_id,
                student_id=u.id,
                node_key=key,
                items_json=json.dumps(qs, ensure_ascii=False),
                status="open",
                created_at=datetime.utcnow(),
            )
        )
        quiz_id = int(res.inserted_primary_key[0])
        db.commit()
        public_qs = []
        for q in qs:
            pq = mbm.public_question(q)
            if q.get("isCustom"):
                pq["isCustom"] = True
                pq["typeLabel"] = q.get("typeLabel", pq.get("typeLabel", "老师加题"))
            public_qs.append(pq)
        return {
            "quizId": quiz_id,
            "nodeKey": key,
            "nodeName": node["name"],
            "detail": node["detail"],
            "grade": target_grade,
            "ageProfile": agp.get_age_interaction_profile(target_grade),
            "count": len(qs),
            "questions": public_qs,
        }

    @router.post("/student/math-star-map/nodes/{key}/quiz/submit")
    def submit_node_quiz(key: str, body: NodeQuizSubmitBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        ensure_tables(db)
        student_grade = agp.detect_user_grade(implementation, db, u)
        target_grade = agp.infer_grade_from_node_key(key, student_grade)
        qrow = db.execute(
            select(t_quizzes).where(
                t_quizzes.c.id == body.quiz_id,
                t_quizzes.c.school_id == u.school_id,
                t_quizzes.c.student_id == u.id,
                t_quizzes.c.node_key == key,
            )
        ).first()
        if qrow is None:
            raise HTTPException(404, "没有找到这次微测记录")
        if qrow.status == "submitted":
            raise HTTPException(409, "这次微测已经交卷了")
        qs = json.loads(qrow.items_json)
        ans_map = {a.question_id: a for a in body.answers}
        correct = 0
        hard_correct = 0
        details: list[dict[str, Any]] = []
        for q in qs:
            a = ans_map.get(q["id"])
            sel = a.selected_index if a else None
            txt = a.text_answer if a else ""
            if arc.is_custom_question_id(q.get("id")):
                ok, std_ans, std_exp = arc.grade_custom_question(
                    implementation, db, q, selected_index=sel, text_answer=txt
                )
            else:
                ok = mbm.grade_builtin_question(q, selected_index=sel, text_answer=txt)
                std_ans = q["answer"]
                std_exp = q.get("explanation", "")
            if ok:
                correct += 1
                if q.get("level") == "hard":
                    hard_correct += 1
            details.append({
                "id": q["id"],
                "questionType": q.get("questionType", ""),
                "typeLabel": q.get("typeLabel", mbm.TYPE_LABELS.get(q.get("questionType", ""), "")),
                "text": q["text"],
                "correct": ok,
                "answer": std_ans,
                "explanation": std_exp,
                "isCustom": bool(q.get("isCustom")),
            })
        total = len(qs)
        rate_pct = round((correct / total) * 100) if total else 0
        passed_light = rate_pct >= 80
        m = mbm.get_builtin_math_map(target_grade)
        all_nodes = mbm.get_all_math_nodes()
        node_name = next((n["name"] for n in m["nodes"] if n["key"] == key), all_nodes.get(key, {}).get("name", key))
        prev_state, light_state = upsert_node_mastery(
            db,
            u,
            node_key=key,
            add_attempts=total,
            add_correct=correct,
            add_hard_correct=hard_correct,
            quiz_rate_pct=rate_pct,
            needs_repair=False if passed_light else None,
        )
        repaired = bool(prev_state["needsRepair"] and not light_state["needsRepair"])
        points_awarded = mapts.settle_map_node_milestones(
            implementation,
            db,
            u,
            node_key=key,
            node_name=node_name,
            prev_state=prev_state["state"],
            next_state=light_state["state"],
            repaired=repaired,
            related_id=int(qrow.id),
        )
        db.execute(
            update(t_quizzes)
            .where(t_quizzes.c.id == qrow.id)
            .values(status="submitted", correct=correct, total=total, submitted_at=datetime.utcnow())
        )
        record_arena_outcomes(
            implementation, db, school_id=int(u.school_id), student_id=int(u.id),
            subject="数学", source_kind="map", details=details,
            default_node_key=key, default_node_name=node_name,
        )
        db.commit()
        map_payload = build_map_payload(db, u, grade=target_grade)
        return {
            "quizId": qrow.id,
            "nodeKey": key,
            "grade": target_grade,
            "correct": correct,
            "total": total,
            "accuracy": rate_pct,
            "litUp": passed_light,
            "repaired": repaired,
            "light": light_state,
            "pointsAwarded": points_awarded,
            "points": map_payload["points"],
            "details": details,
            "map": map_payload,
        }

    @router.get("/student/math-sprints")
    def get_math_sprints(grade: int | None = None, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        ensure_tables(db)
        student_grade = agp.detect_user_grade(implementation, db, u)
        active_grade = agp.resolve_arena_grade(grade, student_grade, subject="数学")
        rows = db.execute(
            select(t_sprints)
            .where(
                t_sprints.c.school_id == u.school_id,
                t_sprints.c.student_id == u.id,
                t_sprints.c.status == "submitted",
            )
            .order_by(desc(t_sprints.c.submitted_at), desc(t_sprints.c.id))
        ).all()
        by_slug: dict[str, list[Any]] = {}
        for r in rows:
            by_slug.setdefault(r.slug, []).append(r)

        items: list[dict[str, Any]] = []
        for sp in es.list_sprints("数学", grade=active_grade):
            hist = by_slug.get(sp["slug"], [])
            best_tier = es.TIER_BY_CODE["L0"]
            best_rate = None
            for h in hist:
                t = es.TIER_BY_CODE.get(h.tier_code or "L0", es.TIER_BY_CODE["L0"])
                if t["rank"] > best_tier["rank"]:
                    best_tier = t
                if best_rate is None or int(h.score_rate or 0) > best_rate:
                    best_rate = int(h.score_rate or 0)
            items.append({
                "slug": sp["slug"],
                "grade": int(sp.get("grade", active_grade)),
                "title": sp["title"],
                "subtitle": sp["subtitle"],
                "icon": sp["icon"],
                "timeLimitSec": sp["timeLimitSec"],
                "timeLimitMin": sp["timeLimitSec"] // 60,
                "questionCount": sp["questionCount"],
                "types": [{"type": k, "label": mbm.TYPE_LABELS.get(k, k), "count": v} for k, v in sp["typeMix"].items()],
                "attempts": len(hist),
                "bestScoreRate": best_rate,
                "bestTier": best_tier if hist else None,
            })

        recent = []
        for r in rows[:8]:
            sp = es.get_sprint(r.slug)
            recent.append({
                "attemptId": r.id,
                "slug": r.slug,
                "title": sp["title"] if sp else r.slug,
                "earnedMarks": r.earned_marks,
                "totalMarks": r.total_marks,
                "scoreRate": r.score_rate,
                "elapsedSec": r.elapsed_sec,
                "timeLimitSec": r.time_limit_sec,
                "tier": es.TIER_BY_CODE.get(r.tier_code or "L0", es.TIER_BY_CODE["L0"]),
                "submittedAt": r.submitted_at.strftime("%Y-%m-%d %H:%M") if r.submitted_at else "",
            })
        return {
            "subject": "数学",
            "grade": active_grade,
            "studentGrade": student_grade,
            "availableGrades": agp.build_available_grades(active_grade, student_grade, subject="数学"),
            "ageProfile": agp.get_age_interaction_profile(active_grade),
            "tiers": es.TIERS,
            "items": items,
            "recent": recent,
            "points": mapts.student_arena_points_summary(implementation, db, u),
        }

    @router.post("/student/math-sprints/{slug}/start")
    def start_math_sprint(slug: str, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        ensure_tables(db)
        sp = es.get_sprint(slug)
        if sp is None:
            raise HTTPException(404, "没有找到这个应试专项")
        student_grade = agp.detect_user_grade(implementation, db, u)
        target_grade = int(sp.get("grade") or agp.infer_grade_from_sprint_slug(slug, student_grade))
        past_count = len(
            db.execute(
                select(t_sprints.c.id).where(
                    t_sprints.c.school_id == u.school_id,
                    t_sprints.c.student_id == u.id,
                    t_sprints.c.slug == slug,
                )
            ).all()
        )
        seed = (int(u.id) * 23 + past_count * 11 + len(slug)) % 113
        qs = es.compose_sprint_questions(slug, seed=seed)
        now = datetime.utcnow()
        res = db.execute(
            insert(t_sprints).values(
                school_id=u.school_id,
                student_id=u.id,
                slug=slug,
                items_json=json.dumps(qs, ensure_ascii=False),
                time_limit_sec=int(sp["timeLimitSec"]),
                status="open",
                started_at=now,
            )
        )
        attempt_id = int(res.inserted_primary_key[0])
        db.commit()
        return {
            "attemptId": attempt_id,
            "slug": slug,
            "grade": target_grade,
            "ageProfile": agp.get_age_interaction_profile(target_grade),
            "title": sp["title"],
            "icon": sp["icon"],
            "timeLimitSec": int(sp["timeLimitSec"]),
            "startedAt": now.isoformat() + "Z",
            "serverNow": now.isoformat() + "Z",
            "questionCount": len(qs),
            "totalMarks": sum(int(q["marks"]) for q in qs),
            "questions": [mbm.public_question(q) for q in qs],
        }

    @router.post("/student/math-sprints/attempts/{attempt_id}/submit")
    def submit_math_sprint(attempt_id: int, body: SprintSubmitBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        ensure_tables(db)
        row = db.execute(
            select(t_sprints).where(
                t_sprints.c.id == attempt_id,
                t_sprints.c.school_id == u.school_id,
                t_sprints.c.student_id == u.id,
            )
        ).first()
        if row is None:
            raise HTTPException(404, "没有找到这次专项挑战")
        if row.status == "submitted":
            raise HTTPException(409, "这次专项挑战已经交卷了")
        now = datetime.utcnow()
        elapsed_sec = max(0, int((now - row.started_at).total_seconds()))
        qs = json.loads(row.items_json)
        answers_by_id = {
            a.question_id: {"selected_index": a.selected_index, "text_answer": a.text_answer}
            for a in body.answers
        }
        result = es.evaluate_sprint_attempt(
            questions=qs,
            answers_by_id=answers_by_id,
            elapsed_sec=elapsed_sec,
            time_limit_sec=int(row.time_limit_sec),
            auto_submitted=body.auto_submitted,
        )

        # 双向联动：反哺知识地图节点点亮状态与待修补红标，并结算全站里程碑积分
        sp_meta = es.get_sprint(row.slug)
        student_grade = agp.detect_user_grade(implementation, db, u)
        target_grade = int((sp_meta or {}).get("grade") or agp.infer_grade_from_sprint_slug(row.slug, student_grade))
        all_nodes = mbm.get_all_math_nodes()
        node_names = {k: v["name"] for k, v in all_nodes.items()}
        sp_title = sp_meta["title"] if sp_meta else row.slug

        sprint_pts = mapts.settle_sprint_tier_milestones(
            implementation,
            db,
            u,
            slug=row.slug,
            title=sp_title,
            tier_code=result["tier"]["code"],
            attempt_id=int(row.id),
        )
        awarded_entries = list(sprint_pts["entries"])
        awarded_total = int(sprint_pts["total"])
        awarded_capped = bool(sprint_pts["capped"])

        newly_lit: list[dict[str, str]] = []
        newly_repair: list[dict[str, str]] = []
        for upd in result["mapUpdates"]:
            nk = upd["nodeKey"]
            prev_st, next_st = upsert_node_mastery(
                db,
                u,
                node_key=nk,
                add_attempts=upd["attempts"],
                add_correct=upd["correct"],
                add_hard_correct=upd["hardCorrect"],
                boost_stars=upd["boostStars"],
                needs_repair=True if upd["needsRepair"] else (False if upd["boostStars"] > 0 else None),
            )
            if next_st["state"] in ("lit", "mastered") and prev_st["state"] not in ("lit", "mastered"):
                newly_lit.append({"key": nk, "name": node_names.get(nk, nk), "state": next_st["stateLabel"]})
            if next_st["needsRepair"]:
                newly_repair.append({"key": nk, "name": node_names.get(nk, nk)})
            n_pts = mapts.settle_map_node_milestones(
                implementation,
                db,
                u,
                node_key=nk,
                node_name=node_names.get(nk, nk),
                prev_state=prev_st["state"],
                next_state=next_st["state"],
                repaired=bool(prev_st["needsRepair"] and not next_st["needsRepair"]),
                related_id=int(row.id),
            )
            awarded_total += int(n_pts["total"])
            awarded_capped = awarded_capped or bool(n_pts["capped"])
            awarded_entries.extend(n_pts["entries"])

        points_awarded = {"total": awarded_total, "capped": awarded_capped, "entries": awarded_entries}
        map_changes = {"litNodes": newly_lit, "repairNodes": newly_repair}

        db.execute(
            update(t_sprints)
            .where(t_sprints.c.id == row.id)
            .values(
                status="submitted",
                submitted_at=now,
                elapsed_sec=result["elapsedSec"],
                earned_marks=result["earnedMarks"],
                total_marks=result["totalMarks"],
                score_rate=result["scoreRate"],
                tier_code=result["tier"]["code"],
                result_json=json.dumps(result, ensure_ascii=False),
            )
        )
        record_arena_outcomes(
            implementation, db, school_id=int(u.school_id), student_id=int(u.id),
            subject="数学", source_kind="sprint", details=result["details"],
        )
        db.commit()
        return {
            "attemptId": row.id,
            "slug": row.slug,
            "grade": target_grade,
            "pointsAwarded": points_awarded,
            "points": mapts.student_arena_points_summary(implementation, db, u),
            "mapChanges": map_changes,
            **result,
        }

    def _summarize_student_arena(db: Any, stu: Any) -> dict[str, Any]:
        stu_grade = agp.detect_user_grade(implementation, db, stu)
        m = mbm.get_builtin_math_map(stu_grade)
        all_nodes = mbm.get_all_math_nodes()
        node_names = {k: v["name"] for k, v in all_nodes.items()}
        m_rows = db.execute(
            select(t_mastery).where(t_mastery.c.school_id == stu.school_id, t_mastery.c.student_id == stu.id)
        ).all()
        lit_count = 0
        mastered_count = 0
        repair_names: list[str] = []
        for r in m_rows:
            st = mbm.compute_node_light_state(
                attempts=int(r.attempts),
                correct=int(r.correct),
                best_quiz_rate=int(r.best_quiz_rate_pct) / 100.0,
                hard_correct=int(r.hard_correct),
                sprint_boost_stars=int(r.sprint_boost_stars),
                needs_repair=bool(r.needs_repair),
            )
            if st["state"] in ("lit", "mastered"):
                lit_count += 1
            if st["state"] == "mastered":
                mastered_count += 1
            if st["needsRepair"]:
                repair_names.append(f"{r.node_key} {node_names.get(r.node_key, r.node_key)}")

        s_rows = db.execute(
            select(t_sprints).where(
                t_sprints.c.school_id == stu.school_id,
                t_sprints.c.student_id == stu.id,
                t_sprints.c.status == "submitted",
            )
        ).all()
        best_tier = None
        for sr in s_rows:
            t = es.TIER_BY_CODE.get(sr.tier_code or "L0", es.TIER_BY_CODE["L0"])
            if best_tier is None or t["rank"] > best_tier["rank"]:
                best_tier = t
        pts = mapts.student_arena_points_summary(implementation, db, stu)
        return {
            "studentId": int(stu.id),
            "name": stu.name or stu.username,
            "grade": getattr(stu, "grade", None),
            "litNodes": lit_count,
            "masteredNodes": mastered_count,
            "totalNodes": len(m["nodes"]),
            "repairCount": len(repair_names),
            "repairNames": repair_names[:4],
            "sprintAttempts": len(s_rows),
            "bestTier": best_tier,
            "pointsBalance": pts["balance"],
            "todayPoints": pts["todayEarned"],
        }

    @router.get("/teacher/math-arena/overview")
    def teacher_arena_overview(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher", "admin")
        ensure_tables(db)
        User = implementation.User
        students = db.scalars(
            select(User).where(User.school_id == u.school_id, User.role == "student").order_by(User.id)
        ).all()
        items = [_summarize_student_arena(db, stu) for stu in students[:100]]
        return {
            "role": u.role,
            "totalNodes": len(mbm.MATH_G5_CORE_MAP["nodes"]),
            "totalSprints": len(es.MATH_G5_SPRINTS),
            "items": items,
        }

    @router.get("/parent/math-arena/children")
    def parent_arena_children(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "parent")
        ensure_tables(db)
        User = implementation.User
        ParentStudent = getattr(implementation, "ParentStudent", None)
        children: list[Any] = []
        if ParentStudent is not None:
            sids = list(
                db.scalars(
                    select(ParentStudent.student_id).where(
                        ParentStudent.parent_id == u.id,
                    )
                ).all()
            )
            if sids:
                children = db.scalars(select(User).where(User.school_id == u.school_id, User.id.in_(sids))).all()
        items = [_summarize_student_arena(db, c) for c in children]
        return {
            "role": "parent",
            "totalNodes": len(mbm.MATH_G5_CORE_MAP["nodes"]),
            "totalSprints": len(es.MATH_G5_SPRINTS),
            "items": items,
        }

    app.include_router(router)
    app.state.math_arena_installed = True
    app.state.math_arena_router = router
    return router


__all__ = ["install_math_arena_views", "register_math_arena_tables"]
