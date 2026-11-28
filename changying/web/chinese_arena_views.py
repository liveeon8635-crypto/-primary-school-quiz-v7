"""语文通用知识地图（按知识点域自带题点亮）与强应试专项（按试卷四大板块混合计时+AI批改）路由.

独立双入口、底层双向联动：
- 知识地图（按知识点域）：
  GET  /v1/chinese-star-map
  GET  /student/chinese-star-map
  POST /student/chinese-star-map/nodes/{key}/quiz
  POST /student/chinese-star-map/nodes/{key}/quiz/submit
- 强应试专项（基础/古诗文/现代文阅读/表达微写作）：
  GET  /v1/chinese-sprints
  GET  /student/chinese-sprints
  POST /student/chinese-sprints/{slug}/start
  POST /student/chinese-sprints/attempts/{attempt_id}/submit
- 静态普通话音频：
  GET  /assets/chinese-audio/{audio_id}.mp3
- 教师 / 家长学情同步：
  GET  /teacher/chinese-arena/overview
  GET  /parent/chinese-arena/children
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, desc, insert, select, update

from changying.services import arena_grade_profiles as agp
from changying.services import arena_review_and_custom as arc
from changying.services import chinese_ai_grader as caig
from changying.services import chinese_arena_points as capts
from changying.services import chinese_builtin_map as cbm
from changying.services import chinese_exam_sprints as ces
from changying.web.arena_wrongbook import record_arena_outcomes
from changying.web.knowledge_map_views import NO_CACHE

AUDIO_DIR = Path(__file__).resolve().parent / "chinese_audio"
AUDIO_ID_RE = re.compile(r"^[a-z0-9_-]{3,40}$")


class ChineseAnswerItem(BaseModel):
    question_id: str = Field(min_length=1, max_length=120)
    selected_index: int | None = None
    text_answer: str = Field(default="", max_length=1500)


class ChineseNodeQuizSubmitBody(BaseModel):
    quiz_id: int
    answers: list[ChineseAnswerItem]


class ChineseSprintSubmitBody(BaseModel):
    answers: list[ChineseAnswerItem] = Field(default_factory=list)
    auto_submitted: bool = False


def register_chinese_arena_tables(implementation: Any) -> dict[str, Table]:
    md = implementation.Base.metadata
    if "chinese_node_mastery" not in md.tables:
        Table(
            "chinese_node_mastery",
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
            UniqueConstraint("school_id", "student_id", "node_key", name="uq_chinese_node_mastery_student"),
        )
    if "chinese_node_quizzes" not in md.tables:
        Table(
            "chinese_node_quizzes",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("node_key", String(24), nullable=False),
            Column("items_json", Text, nullable=False),
            Column("status", String(16), nullable=False),
            Column("correct", Integer, nullable=True),
            Column("total", Integer, nullable=True),
            Column("created_at", DateTime, nullable=False),
            Column("submitted_at", DateTime, nullable=True),
        )
    if "chinese_sprint_attempts" not in md.tables:
        Table(
            "chinese_sprint_attempts",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("slug", String(48), nullable=False, index=True),
            Column("timing_mode", String(24), nullable=False, default="overall"),
            Column("items_json", Text, nullable=False),
            Column("time_limit_sec", Integer, nullable=False),
            Column("status", String(16), nullable=False),
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
        "mastery": md.tables["chinese_node_mastery"],
        "quizzes": md.tables["chinese_node_quizzes"],
        "sprints": md.tables["chinese_sprint_attempts"],
    }


def install_chinese_arena_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "chinese_arena_installed", False):
        return app.state.chinese_arena_router
    tables = register_chinese_arena_tables(implementation)
    t_mastery, t_quizzes, t_sprints = tables["mastery"], tables["quizzes"], tables["sprints"]
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def ensure_tables(db: Any) -> None:
        bind = db.get_bind()
        for tbl in (t_mastery, t_quizzes, t_sprints):
            tbl.create(bind=bind, checkfirst=True)

    def _state_from_row(row: Any | None) -> dict[str, Any]:
        if row is None:
            return cbm.compute_light_state(
                attempts=0, correct=0, hard_correct=0,
                best_quiz_rate_pct=0, sprint_boost_stars=0, needs_repair=False,
            )
        return cbm.compute_light_state(
            attempts=int(row.attempts),
            correct=int(row.correct),
            hard_correct=int(row.hard_correct),
            best_quiz_rate_pct=int(row.best_quiz_rate_pct),
            sprint_boost_stars=int(row.sprint_boost_stars),
            needs_repair=bool(row.needs_repair),
        )

    def _upsert_mastery(
        db: Any,
        *,
        school_id: int,
        student_id: int,
        node_key: str,
        add_attempts: int,
        add_correct: int,
        add_hard_correct: int,
        quiz_rate_pct: int | None = None,
        boost_stars: int | None = None,
        needs_repair: bool | None = None,
    ) -> dict[str, Any]:
        now = datetime.utcnow()
        row = db.execute(
            select(t_mastery).where(
                t_mastery.c.school_id == school_id,
                t_mastery.c.student_id == student_id,
                t_mastery.c.node_key == node_key,
            )
        ).first()
        prev_st = _state_from_row(row)
        prev_repair = bool(row.needs_repair) if row is not None else False

        if row is None:
            attempts = add_attempts
            correct = add_correct
            hard_correct = add_hard_correct
            best_rate = int(quiz_rate_pct or 0)
            sprint_boost = int(boost_stars or 0)
            repair_flag = 1 if needs_repair else 0
            db.execute(
                insert(t_mastery).values(
                    school_id=school_id,
                    student_id=student_id,
                    node_key=node_key,
                    attempts=attempts,
                    correct=correct,
                    hard_correct=hard_correct,
                    best_quiz_rate_pct=best_rate,
                    sprint_boost_stars=sprint_boost,
                    needs_repair=repair_flag,
                    updated_at=now,
                )
            )
        else:
            attempts = int(row.attempts) + add_attempts
            correct = int(row.correct) + add_correct
            hard_correct = int(row.hard_correct) + add_hard_correct
            best_rate = max(int(row.best_quiz_rate_pct), int(quiz_rate_pct or 0))
            sprint_boost = max(int(row.sprint_boost_stars), int(boost_stars or 0))
            repair_flag = int(row.needs_repair) if needs_repair is None else (1 if needs_repair else 0)
            db.execute(
                update(t_mastery)
                .where(t_mastery.c.id == row.id)
                .values(
                    attempts=attempts,
                    correct=correct,
                    hard_correct=hard_correct,
                    best_quiz_rate_pct=best_rate,
                    sprint_boost_stars=sprint_boost,
                    needs_repair=repair_flag,
                    updated_at=now,
                )
            )

        next_st = cbm.compute_light_state(
            attempts=attempts,
            correct=correct,
            hard_correct=hard_correct,
            best_quiz_rate_pct=best_rate,
            sprint_boost_stars=sprint_boost,
            needs_repair=bool(repair_flag),
        )
        return {
            "prev": prev_st,
            "next": next_st,
            "repaired": bool(prev_repair and not bool(repair_flag)),
            "attempts": attempts,
            "correct": correct,
            "bestQuizRate": best_rate,
        }

    # ---------------- 静态普通话音频与页面路由 ----------------
    @router.get("/assets/chinese-audio/{audio_id}.mp3", include_in_schema=False)
    def chinese_audio_file(audio_id: str):
        if not AUDIO_ID_RE.match(audio_id):
            raise HTTPException(404, "音频不存在")
        target = AUDIO_DIR / f"{audio_id}.mp3"
        if not target.is_file():
            raise HTTPException(404, "音频文件未生成")
        return FileResponse(
            path=str(target),
            media_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    @router.get("/v1/chinese-star-map", include_in_schema=False)
    def chinese_star_map_page():
        from changying.web.chinese_arena_pages import chinese_star_map_page_html
        return HTMLResponse(chinese_star_map_page_html(), headers=NO_CACHE)

    @router.get("/v1/chinese-sprints", include_in_schema=False)
    def chinese_sprints_page():
        from changying.web.chinese_arena_pages import chinese_sprints_page_html
        return HTMLResponse(chinese_sprints_page_html(), headers=NO_CACHE)

    # ---------------- 学生端：语文知识地图（4 知识点域） ----------------
    @router.get("/student/chinese-star-map")
    def get_chinese_star_map(grade: int | None = None, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        ensure_tables(db)
        student_grade = agp.detect_user_grade(implementation, db, u)
        active_grade = agp.resolve_arena_grade(grade, student_grade)
        bp = cbm.get_map_blueprint(active_grade)
        rows = db.execute(
            select(t_mastery).where(
                t_mastery.c.school_id == u.school_id,
                t_mastery.c.student_id == u.id,
            )
        ).all()
        by_key = {r.node_key: r for r in rows}
        now = datetime.utcnow()

        nodes_out: list[dict[str, Any]] = []
        lit_nodes = mastered_nodes = repair_nodes = review_due_count = total_stars = 0
        for n in bp["nodes"]:
            r = by_key.get(n["key"])
            st = _state_from_row(r)
            rev = arc.compute_review_meta(
                r,
                now=now,
                stars=int(st["stars"]),
                needs_repair=bool(st["needsRepair"]),
            )
            if st["state"] in ("lit", "mastered"):
                lit_nodes += 1
            if st["state"] == "mastered":
                mastered_nodes += 1
            if st["needsRepair"]:
                repair_nodes += 1
            if rev["reviewDue"]:
                review_due_count += 1
            total_stars += int(st["stars"])
            nodes_out.append({
                **n,
                **st,
                **rev,
                "attempts": int(r.attempts) if r is not None else 0,
                "correct": int(r.correct) if r is not None else 0,
                "bestQuizRate": int(r.best_quiz_rate_pct) if r is not None else 0,
            })

        return {
            "title": bp.get("title", ""),
            "subject": bp["subject"],
            "grade": active_grade,
            "studentGrade": student_grade,
            "availableGrades": agp.build_available_grades(active_grade, student_grade),
            "ageProfile": agp.get_age_interaction_profile(active_grade),
            "domains": bp["domains"],
            "nodes": nodes_out,
            "summary": {
                "totalNodes": len(nodes_out),
                "litNodes": lit_nodes,
                "masteredNodes": mastered_nodes,
                "repairNodes": repair_nodes,
                "reviewDueCount": review_due_count,
                "totalStars": total_stars,
                "maxStars": len(nodes_out) * 3,
            },
            "points": capts.student_arena_points_summary(implementation, db, u),
        }

    @router.post("/student/chinese-star-map/nodes/{node_key}/quiz")
    def start_chinese_node_quiz(node_key: str, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        ensure_tables(db)
        student_grade = agp.detect_user_grade(implementation, db, u)
        target_grade = agp.infer_grade_from_node_key(node_key, student_grade)
        bp = cbm.get_map_blueprint(target_grade)
        node = next((n for n in bp["nodes"] if n["key"] == node_key), None) or cbm.NODE_BY_KEY.get(node_key)
        if not node:
            raise HTTPException(404, "未找到该语文知识节点")
        prev_cnt = db.execute(
            select(t_quizzes.c.id).where(
                t_quizzes.c.school_id == u.school_id,
                t_quizzes.c.student_id == u.id,
                t_quizzes.c.node_key == node_key,
            )
        ).all()
        seed = int(u.id) * 11 + len(prev_cnt) * 5 + 3
        custom_qs = arc.fetch_custom_quiz_questions(
            implementation, db, school_id=int(u.school_id), subject="语文", node_key=node_key, limit=3, seed=seed
        )
        builtin_qs = cbm.generate_node_questions(node_key, count=max(0, 5 - len(custom_qs)), seed=seed, map_friendly=True)
        questions = custom_qs + builtin_qs
        now = datetime.utcnow()
        res = db.execute(
            insert(t_quizzes).values(
                school_id=u.school_id,
                student_id=u.id,
                node_key=node_key,
                items_json=json.dumps(questions, ensure_ascii=False),
                status="open",
                created_at=now,
            )
        )
        quiz_id = int(res.inserted_primary_key[0])
        db.commit()
        public_qs = []
        for q in questions:
            pq = cbm.public_question(q)
            if q.get("isCustom"):
                pq["isCustom"] = True
            public_qs.append(pq)
        return {
            "quizId": quiz_id,
            "node": node,
            "grade": target_grade,
            "ageProfile": agp.get_age_interaction_profile(target_grade),
            "questions": public_qs,
        }

    @router.post("/student/chinese-star-map/nodes/{node_key}/quiz/submit")
    def submit_chinese_node_quiz(
        node_key: str,
        body: ChineseNodeQuizSubmitBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "student")
        ensure_tables(db)
        student_grade = agp.detect_user_grade(implementation, db, u)
        target_grade = agp.infer_grade_from_node_key(node_key, student_grade)
        bp = cbm.get_map_blueprint(target_grade)
        node = next((n for n in bp["nodes"] if n["key"] == node_key), None) or cbm.NODE_BY_KEY.get(node_key)
        if not node:
            raise HTTPException(404, "未找到该语文知识节点")
        row = db.execute(
            select(t_quizzes).where(
                t_quizzes.c.id == body.quiz_id,
                t_quizzes.c.school_id == u.school_id,
                t_quizzes.c.student_id == u.id,
                t_quizzes.c.node_key == node_key,
            )
        ).first()
        if row is None:
            raise HTTPException(404, "未找到本次语文节点微测记录")
        if row.status == "submitted":
            raise HTTPException(409, "本次微测已经提交过")

        questions = json.loads(row.items_json)
        ans_map = {a.question_id: a for a in body.answers}
        subj_pairs = [
            (q, ans_map[q["id"]].text_answer if q["id"] in ans_map else "")
            for q in questions
            if (not arc.is_custom_question_id(q.get("id"))) and q.get("questionType") in cbm.SUBJECTIVE_TYPES
        ]
        subj_grades = caig.grade_subjective_items(
            subj_pairs, implementation=implementation, db=db, school_id=int(u.school_id)
        )

        correct_cnt = 0
        hard_correct = 0
        details: list[dict[str, Any]] = []
        for q in questions:
            a = ans_map.get(q["id"])
            sel = a.selected_index if a else None
            txt = a.text_answer if a else ""
            ai_comment = ""
            grading_mode = "objective"
            if arc.is_custom_question_id(q.get("id")):
                ok, std_ans, std_exp = arc.grade_custom_question(
                    implementation, db, q, selected_index=sel, text_answer=txt
                )
            elif q.get("questionType") in cbm.SUBJECTIVE_TYPES:
                sg = subj_grades.get(q["id"]) or cbm.grade_subjective_rule_fallback(q, txt)
                ok = bool(sg["passed"])
                ai_comment = str(sg.get("comment") or "")
                grading_mode = str(sg.get("gradingMode") or "rule_fallback")
                std_ans = q.get("sampleAnswer") or q["answer"]
                std_exp = q.get("explanation", "")
            else:
                ok = cbm.grade_objective_answer(q, selected_index=sel, text_answer=txt)
                std_ans = q.get("sampleAnswer") or q["answer"]
                std_exp = q.get("explanation", "")
            if ok:
                correct_cnt += 1
                if q.get("level") == "hard":
                    hard_correct += 1
            details.append({
                "id": q["id"],
                "questionType": q["questionType"],
                "typeLabel": q.get("typeLabel", q["questionType"]),
                "text": q["text"],
                "correct": ok,
                "answer": std_ans,
                "explanation": std_exp,
                "aiComment": ai_comment,
                "gradingMode": grading_mode,
                "isCustom": bool(q.get("isCustom")),
            })

        total = len(questions)
        rate_pct = round(correct_cnt * 100 / total) if total else 0
        passed = rate_pct >= 80
        up = _upsert_mastery(
            db,
            school_id=int(u.school_id),
            student_id=int(u.id),
            node_key=node_key,
            add_attempts=total,
            add_correct=correct_cnt,
            add_hard_correct=hard_correct,
            quiz_rate_pct=rate_pct,
            needs_repair=False if passed else None,
        )
        points_awarded = capts.settle_map_node_milestones(
            implementation,
            db,
            u,
            node_key=node_key,
            node_name=node["name"],
            prev_state=up["prev"]["state"],
            next_state=up["next"]["state"],
            repaired=up["repaired"],
            related_id=int(row.id),
        )
        now = datetime.utcnow()
        db.execute(
            update(t_quizzes)
            .where(t_quizzes.c.id == row.id)
            .values(status="submitted", correct=correct_cnt, total=total, submitted_at=now)
        )
        record_arena_outcomes(
            implementation, db, school_id=int(u.school_id), student_id=int(u.id),
            subject="语文", source_kind="map", details=details,
            default_node_key=node_key, default_node_name=node["name"],
        )
        db.commit()
        return {
            "quizId": int(row.id),
            "nodeKey": node_key,
            "nodeName": node["name"],
            "grade": target_grade,
            "correct": correct_cnt,
            "total": total,
            "ratePct": rate_pct,
            "passed": passed,
            "nodeState": up["next"],
            "repaired": up["repaired"],
            "pointsAwarded": points_awarded,
            "points": capts.student_arena_points_summary(implementation, db, u),
            "details": details,
        }

    # ---------------- 学生端：语文应试专项（4 大板块 + 混合计时） ----------------
    @router.get("/student/chinese-sprints")
    def get_chinese_sprints(grade: int | None = None, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        ensure_tables(db)
        student_grade = agp.detect_user_grade(implementation, db, u)
        active_grade = agp.resolve_arena_grade(grade, student_grade)
        rows = db.execute(
            select(t_sprints)
            .where(
                t_sprints.c.school_id == u.school_id,
                t_sprints.c.student_id == u.id,
                t_sprints.c.status == "submitted",
            )
            .order_by(desc(t_sprints.c.id))
        ).all()

        by_slug: dict[str, list[Any]] = {}
        for r in rows:
            by_slug.setdefault(r.slug, []).append(r)

        sprints_out: list[dict[str, Any]] = []
        for s in ces.list_sprints("语文", grade=active_grade):
            hist = by_slug.get(s["slug"], [])
            best_tier = None
            best_rate = 0
            for h in hist:
                t = ces.TIER_BY_CODE.get(h.tier_code or "L0", ces.TIER_BY_CODE["L0"])
                if best_tier is None or t["rank"] > best_tier["rank"]:
                    best_tier = t
                if (h.score_rate or 0) > best_rate:
                    best_rate = int(h.score_rate or 0)
            sprints_out.append({
                **s,
                "attempts": len(hist),
                "bestScoreRate": best_rate,
                "bestTier": best_tier,
                "lastScoreRate": int(hist[0].score_rate or 0) if hist else None,
            })

        return {
            "subject": "语文",
            "grade": active_grade,
            "studentGrade": student_grade,
            "availableGrades": agp.build_available_grades(active_grade, student_grade),
            "ageProfile": agp.get_age_interaction_profile(active_grade),
            "tiers": ces.TIERS,
            "sprints": sprints_out,
            "points": capts.student_arena_points_summary(implementation, db, u),
        }

    @router.post("/student/chinese-sprints/{slug}/start")
    def start_chinese_sprint(slug: str, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        ensure_tables(db)
        sprint = ces.get_sprint(slug)
        if not sprint:
            raise HTTPException(404, "未找到该语文应试专项")
        student_grade = agp.detect_user_grade(implementation, db, u)
        target_grade = int(sprint.get("grade") or agp.infer_grade_from_sprint_slug(slug, student_grade))
        prev_cnt = db.execute(
            select(t_sprints.c.id).where(
                t_sprints.c.school_id == u.school_id,
                t_sprints.c.student_id == u.id,
                t_sprints.c.slug == slug,
            )
        ).all()
        seed = int(u.id) * 17 + len(prev_cnt) * 7 + 5
        questions = ces.compose_sprint_questions(slug, seed=seed)
        now = datetime.utcnow()
        res = db.execute(
            insert(t_sprints).values(
                school_id=u.school_id,
                student_id=u.id,
                slug=slug,
                timing_mode=sprint["timingMode"],
                items_json=json.dumps(questions, ensure_ascii=False),
                time_limit_sec=int(sprint["timeLimitSec"]),
                status="open",
                started_at=now,
            )
        )
        attempt_id = int(res.inserted_primary_key[0])
        db.commit()
        return {
            "attemptId": attempt_id,
            "sprint": sprint,
            "grade": target_grade,
            "ageProfile": agp.get_age_interaction_profile(target_grade),
            "timingMode": sprint["timingMode"],
            "perQuestionSec": int(sprint.get("perQuestionSec", 0)),
            "maxPlays": int(sprint.get("maxPlays", 0)),
            "timeLimitSec": int(sprint["timeLimitSec"]),
            "startedAt": now.isoformat() + "Z",
            "questions": [cbm.public_question(q) for q in questions],
        }

    @router.post("/student/chinese-sprints/attempts/{attempt_id}/submit")
    def submit_chinese_sprint(
        attempt_id: int,
        body: ChineseSprintSubmitBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
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
            raise HTTPException(404, "未找到本次语文专项作答记录")
        if row.status == "submitted":
            raise HTTPException(409, "本次语文专项已经提交过")

        sprint = ces.get_sprint(row.slug) or {"slug": row.slug, "title": row.slug}
        student_grade = agp.detect_user_grade(implementation, db, u)
        target_grade = int(sprint.get("grade") or agp.infer_grade_from_sprint_slug(row.slug, student_grade))
        questions = json.loads(row.items_json)
        now = datetime.utcnow()
        elapsed_sec = max(1, int((now - row.started_at).total_seconds()))
        answers_by_id = {
            a.question_id: {"selected_index": a.selected_index, "text_answer": a.text_answer}
            for a in body.answers
        }
        result = ces.evaluate_sprint_attempt(
            questions=questions,
            answers_by_id=answers_by_id,
            elapsed_sec=elapsed_sec,
            time_limit_sec=int(row.time_limit_sec),
            auto_submitted=body.auto_submitted,
            implementation=implementation,
            db=db,
            school_id=int(u.school_id),
        )

        node_names = {n["key"]: n["name"] for n in cbm.ALL_CHINESE_NODES}
        map_changes: dict[str, list[dict[str, Any]]] = {"lit": [], "repaired": [], "flagged": []}
        all_entries: list[dict[str, Any]] = []
        capped = False

        sprint_pts = capts.settle_sprint_tier_milestones(
            implementation,
            db,
            u,
            slug=row.slug,
            title=sprint["title"],
            tier_code=result["tier"]["code"],
            attempt_id=int(row.id),
            now_utc=now,
        )
        all_entries.extend(sprint_pts["entries"])
        capped = capped or bool(sprint_pts["capped"])

        for mu in result["mapUpdates"]:
            nk = mu["nodeKey"]
            up = _upsert_mastery(
                db,
                school_id=int(u.school_id),
                student_id=int(u.id),
                node_key=nk,
                add_attempts=int(mu["attempts"]),
                add_correct=int(mu["correct"]),
                add_hard_correct=int(mu["hardCorrect"]),
                boost_stars=int(mu["boostStars"]) or None,
                needs_repair=True if mu["needsRepair"] else (False if mu["boostStars"] > 0 else None),
            )
            if mu["needsRepair"]:
                map_changes["flagged"].append({"key": nk, "name": node_names.get(nk, nk)})
            elif up["next"]["state"] in ("lit", "mastered") and up["prev"]["state"] not in ("lit", "mastered"):
                map_changes["lit"].append({"key": nk, "name": node_names.get(nk, nk)})
            if up["repaired"]:
                map_changes["repaired"].append({"key": nk, "name": node_names.get(nk, nk)})

            n_pts = capts.settle_map_node_milestones(
                implementation,
                db,
                u,
                node_key=nk,
                node_name=node_names.get(nk, nk),
                prev_state=up["prev"]["state"],
                next_state=up["next"]["state"],
                repaired=up["repaired"],
                related_id=int(row.id),
                now_utc=now,
            )
            all_entries.extend(n_pts["entries"])
            capped = capped or bool(n_pts["capped"])

        points_awarded = {
            "total": sum(int(e["awarded"]) for e in all_entries),
            "capped": capped,
            "entries": all_entries,
        }

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
            subject="语文", source_kind="sprint", details=result["details"],
        )
        db.commit()
        return {
            "attemptId": int(row.id),
            "slug": row.slug,
            "grade": target_grade,
            "timingMode": row.timing_mode,
            "pointsAwarded": points_awarded,
            "points": capts.student_arena_points_summary(implementation, db, u),
            "mapChanges": map_changes,
            **result,
        }

    # ---------------- 教师 / 家长学情同步概览 ----------------
    def _summarize_student_arena(db: Any, stu: Any) -> dict[str, Any]:
        node_names = {n["key"]: n["name"] for n in cbm.ALL_CHINESE_NODES}
        m_rows = db.execute(
            select(t_mastery).where(t_mastery.c.school_id == stu.school_id, t_mastery.c.student_id == stu.id)
        ).all()
        lit_count = mastered_count = 0
        repair_names: list[str] = []
        for r in m_rows:
            st = _state_from_row(r)
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
            t = ces.TIER_BY_CODE.get(sr.tier_code or "L0", ces.TIER_BY_CODE["L0"])
            if best_tier is None or t["rank"] > best_tier["rank"]:
                best_tier = t
        pts = capts.student_arena_points_summary(implementation, db, stu)
        return {
            "studentId": int(stu.id),
            "name": stu.name or stu.username,
            "grade": getattr(stu, "grade", None),
            "litNodes": lit_count,
            "masteredNodes": mastered_count,
            "totalNodes": len(cbm.CHINESE_G5_NODES),
            "repairCount": len(repair_names),
            "repairNames": repair_names[:4],
            "sprintAttempts": len(s_rows),
            "bestTier": best_tier,
            "pointsBalance": pts["balance"],
            "todayPoints": pts["todayEarned"],
        }

    @router.get("/teacher/chinese-arena/overview")
    def teacher_chinese_overview(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher", "admin")
        ensure_tables(db)
        User = implementation.User
        students = db.scalars(
            select(User).where(User.school_id == u.school_id, User.role == "student").order_by(User.id)
        ).all()
        items = [_summarize_student_arena(db, stu) for stu in students[:100]]
        return {
            "role": u.role,
            "subject": "语文",
            "totalNodes": len(cbm.CHINESE_G5_NODES),
            "totalSprints": len(ces.CHINESE_G5_SPRINTS),
            "items": items,
        }

    @router.get("/parent/chinese-arena/children")
    def parent_chinese_children(u: Any = Depends(current_user), db: Any = Depends(get_db)):
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
            "subject": "语文",
            "totalNodes": len(cbm.CHINESE_G5_NODES),
            "totalSprints": len(ces.CHINESE_G5_SPRINTS),
            "items": items,
        }

    app.include_router(router)
    app.state.chinese_arena_installed = True
    app.state.chinese_arena_router = router
    return router


__all__ = ["AUDIO_DIR", "install_chinese_arena_views", "register_chinese_arena_tables"]
