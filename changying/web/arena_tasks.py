"""语数英知识地图与应试专项「教—学—家」三端打通服务.

核心能力：
- 教师端：按班级筛选、全班考点薄弱热力榜与专项达标率、一键派发（全班 / 仅薄弱生）+ 达标目标 + 任务追踪；
- 学生端：置顶老师布置的闯关/专项任务、达标后自动验收完成、接收长缨助手转达的家长点赞鼓励；
- 家长端：全自动同步关联孩子的老师任务进度与三科学情汇总、每日一键点赞鼓励。
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, desc, insert, select, update

from changying.services import arena_grade_profiles as agp
from changying.services import arena_points_core as pcore
from changying.services import arena_review_and_custom as arc
from changying.services import chinese_arena_points as capts
from changying.services import chinese_builtin_map as cbm
from changying.services import chinese_exam_sprints as ces
from changying.services import english_arena_points as eapts
from changying.services import english_builtin_map as ebm
from changying.services import english_exam_sprints as ees
from changying.services import exam_sprints as mes
from changying.services import math_arena_points as mapts
from changying.services import math_builtin_map as mbm
from changying.web.chinese_arena_views import register_chinese_arena_tables
from changying.web.english_arena_views import register_english_arena_tables
from changying.web.math_arena_views import register_math_arena_tables

GOAL_LABELS = {
    "lit": "点亮考点（≥80%）",
    "mastered": "三星精通",
    "attempt": "完成作答",
    "complete": "完成1次专项",
    "L2": "达到 L2 达标·银章",
    "tier_b": "达到 B 级以上（L2+）",
    "L3": "达到 L3 熟练·金章",
    "fresh_lit": "重刷：派发后新点亮（≥80%）",
    "fresh_mastered": "重刷：派发后新达三星（满分）",
    "fresh_complete": "重刷：派发后新完成1次专项",
    "fresh_attempt": "重刷：派发后新完成1次专项",
    "fresh_tier_b": "重刷：派发后新达 B 级以上",
    "fresh_L2": "重刷：派发后新达 L2 银章",
    "fresh_L3": "重刷：派发后新达 L3 金章",
}

MAP_GOAL_CODES = ("lit", "mastered", "fresh_lit", "fresh_mastered")
SPRINT_GOAL_CODES = ("attempt", "complete", "L2", "tier_b", "L3", "fresh_attempt", "fresh_complete", "fresh_L2", "fresh_tier_b", "fresh_L3")

SUBJECT_URLS = {
    "数学": ("/v1/math-star-map", "/v1/math-sprints"),
    "英语": ("/v1/english-star-map", "/v1/english-sprints"),
    "语文": ("/v1/chinese-star-map", "/v1/chinese-sprints"),
}


class CreateArenaTaskBody(BaseModel):
    subject: str = Field(pattern="^(数学|英语|语文)$")
    class_id: int = 0
    task_kind: str = Field(pattern="^(map_node|sprint)$")
    target_key: str = Field(min_length=1, max_length=64)
    goal_code: str = Field(
        default="lit",
        pattern="^(lit|mastered|attempt|complete|L2|tier_b|L3|fresh_lit|fresh_mastered|fresh_attempt|fresh_complete|fresh_L2|fresh_tier_b|fresh_L3)$",
    )
    audience: str = Field(default="all", pattern="^(all|weak)$")
    due_date: Optional[str] = Field(default=None, max_length=24)


class CreateCustomQuestionBody(BaseModel):
    subject: str = Field(pattern="^(数学|英语|语文)$")
    node_key: str = Field(min_length=1, max_length=32)
    question_type: str = Field(pattern="^(single_choice|fill_blank|true_false)$")
    stem: str = Field(min_length=1, max_length=2000)
    options: list[str] = Field(default_factory=list)
    answer: str = Field(min_length=1, max_length=500)
    explanation: str = Field(default="", max_length=2000)


class ParentCheerBody(BaseModel):
    student_id: int
    subject: str = Field(default="综合", max_length=16)
    message: str = Field(default="坚持自主练习真棒，继续加油！", min_length=1, max_length=120)


def register_arena_task_tables(implementation: Any) -> dict[str, Table]:
    md = implementation.Base.metadata
    if "arena_tasks" not in md.tables:
        Table(
            "arena_tasks",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("class_id", Integer, nullable=False, default=0, index=True),
            Column("teacher_id", Integer, nullable=False, index=True),
            Column("subject", String(16), nullable=False, index=True),
            Column("task_kind", String(16), nullable=False),  # map_node | sprint
            Column("target_key", String(64), nullable=False),
            Column("target_title", String(160), nullable=False),
            Column("goal_code", String(16), nullable=False),  # lit | mastered | attempt | L2 | L3
            Column("audience", String(16), nullable=False, default="all"),  # all | weak
            Column("due_date", String(24), nullable=False, default=""),
            Column("status", String(16), nullable=False, default="active"),  # active | closed
            Column("created_at", DateTime, nullable=False),
        )
    if "arena_task_targets" not in md.tables:
        Table(
            "arena_task_targets",
            md,
            Column("id", Integer, primary_key=True),
            Column("task_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("status", String(16), nullable=False, default="pending"),  # pending | done
            Column("completed_at", DateTime, nullable=True),
            UniqueConstraint("task_id", "student_id", name="uq_arena_task_target"),
        )
    if "arena_parent_cheers" not in md.tables:
        Table(
            "arena_parent_cheers",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("parent_id", Integer, nullable=False, index=True),
            Column("parent_name", String(80), nullable=False),
            Column("student_id", Integer, nullable=False, index=True),
            Column("subject", String(16), nullable=False, default="综合"),
            Column("message", Text, nullable=False),
            Column("day_key", String(16), nullable=False),
            Column("created_at", DateTime, nullable=False),
            Column("seen_at", DateTime, nullable=True),
            UniqueConstraint("parent_id", "student_id", "day_key", name="uq_arena_parent_cheer_day"),
        )
    t_custom = arc.register_arena_custom_questions_table(implementation)
    return {
        "tasks": md.tables["arena_tasks"],
        "targets": md.tables["arena_task_targets"],
        "cheers": md.tables["arena_parent_cheers"],
        "custom_questions": t_custom,
    }


def _parse_due_date(raw: str | None, now: datetime) -> str:
    default_due = (now + timedelta(hours=8, days=2)).strftime("%Y-%m-%d")
    s = (raw or "").strip()
    if not s:
        return default_due
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return default_due


def _subject_meta(implementation: Any, subject: str, grade: int | None = None) -> dict[str, Any]:
    if subject == "数学":
        tbls = register_math_arena_tables(implementation)
        if grade is not None:
            g = agp.clamp_arena_grade(grade, agp.DEFAULT_ARENA_GRADE, subject=subject)
            m = mbm.get_builtin_math_map(g)
            unit_map = {u["key"]: u["name"] for u in m["units"]}
            nodes = list(m["nodes"])
            sprints = list(mes.list_sprints("数学", grade=g))
        else:
            unit_map = {}
            nodes = []
            for g in agp.supported_grades_for_subject("数学"):
                gm = mbm.get_builtin_math_map(g)
                for u in gm["units"]:
                    unit_map[u["key"]] = u["name"]
                for n in gm["nodes"]:
                    nodes.append({**n, "grade": g})
            sprints = list(mes.list_all_sprints("数学"))
        return {
            "nodes": nodes,
            "sprints": sprints,
            "mastery_tbl": tbls["mastery"],
            "quizzes_tbl": tbls["quizzes"],
            "sprints_tbl": tbls["sprints"],
            "points_mod": mapts,
            "domain_name_fn": lambda n: unit_map.get(str(n.get("unit", "")), ""),
            "state_fn": lambda r: mbm.compute_node_light_state(
                attempts=int(r.attempts), correct=int(r.correct),
                best_quiz_rate=int(r.best_quiz_rate_pct) / 100.0,
                hard_correct=int(r.hard_correct),
                sprint_boost_stars=int(r.sprint_boost_stars),
                needs_repair=bool(r.needs_repair),
            ),
        }
    if subject == "英语":
        tbls = register_english_arena_tables(implementation)
        if grade is not None:
            g = agp.clamp_arena_grade(grade, agp.DEFAULT_ARENA_GRADE, subject=subject)
            bp = ebm.get_map_blueprint(g)
            nodes = list(bp["nodes"])
            sprints = list(ees.list_sprints("英语", grade=g))
        else:
            nodes = list(ebm.ALL_ENGLISH_NODES)
            sprints = list(ees.list_all_sprints("英语"))
        return {
            "nodes": nodes,
            "sprints": sprints,
            "mastery_tbl": tbls["mastery"],
            "quizzes_tbl": tbls["quizzes"],
            "sprints_tbl": tbls["sprints"],
            "points_mod": eapts,
            "domain_name_fn": lambda n: str(ebm.DOMAIN_BY_ID.get(str(n.get("domain", "")), {}).get("name", "")),
            "state_fn": lambda r: ebm.compute_light_state(
                attempts=int(r.attempts), correct=int(r.correct),
                hard_correct=int(r.hard_correct),
                best_quiz_rate_pct=int(r.best_quiz_rate_pct),
                sprint_boost_stars=int(r.sprint_boost_stars),
                needs_repair=bool(r.needs_repair),
            ),
        }
    tbls = register_chinese_arena_tables(implementation)
    if grade is not None:
        g = agp.clamp_arena_grade(grade, agp.DEFAULT_ARENA_GRADE, subject=subject)
        bp = cbm.get_map_blueprint(g)
        nodes = list(bp["nodes"])
        sprints = list(ces.list_sprints("语文", grade=g))
    else:
        nodes = list(cbm.ALL_CHINESE_NODES)
        sprints = list(ces.list_all_sprints("语文"))
    return {
        "nodes": nodes,
        "sprints": sprints,
        "mastery_tbl": tbls["mastery"],
        "quizzes_tbl": tbls["quizzes"],
        "sprints_tbl": tbls["sprints"],
        "points_mod": capts,
        "domain_name_fn": lambda n: str(cbm.DOMAIN_BY_ID.get(str(n.get("domain", "")), {}).get("name", "")),
        "state_fn": lambda r: cbm.compute_light_state(
            attempts=int(r.attempts), correct=int(r.correct),
            hard_correct=int(r.hard_correct),
            best_quiz_rate_pct=int(r.best_quiz_rate_pct),
            sprint_boost_stars=int(r.sprint_boost_stars),
            needs_repair=bool(r.needs_repair),
        ),
    }


def _subject_spec(implementation: Any, subject: str, grade: int | None = None) -> dict[str, Any]:
    return _subject_meta(implementation, subject, grade=grade)


def _action_url(subject: str, task_kind: str, target_key: str) -> str:
    map_url, sp_url = SUBJECT_URLS.get(subject, ("/v1/math-star-map", "/v1/math-sprints"))
    if task_kind == "map_node":
        g = agp.infer_grade_from_node_key(target_key)
        return f"{map_url}?grade={g}#node={target_key}"
    g = agp.infer_grade_from_sprint_slug(target_key)
    return f"{sp_url}?grade={g}#sprint={target_key}"


def install_arena_tasks_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "arena_tasks_installed", False):
        return app.state.arena_tasks_router
    tables = register_arena_task_tables(implementation)
    t_tasks, t_targets, t_cheers, t_custom = (
        tables["tasks"],
        tables["targets"],
        tables["cheers"],
        tables["custom_questions"],
    )
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    subj_tables: list[Table] = []
    for _reg in (register_math_arena_tables, register_english_arena_tables, register_chinese_arena_tables):
        _tmap = _reg(implementation)
        subj_tables.extend([_tmap["mastery"], _tmap["quizzes"], _tmap["sprints"]])
    all_arena_tables = (t_tasks, t_targets, t_cheers, t_custom, *subj_tables)

    def ensure_all_tables(db: Any) -> None:
        arc.ensure_tables_on_session(db, *all_arena_tables)

    def _teacher_classes(db: Any, u: Any) -> list[Any]:
        SchoolClass = getattr(implementation, "SchoolClass", None)
        if SchoolClass is None:
            return []
        q = select(SchoolClass).where(SchoolClass.school_id == u.school_id)
        if u.role == "teacher":
            q = q.where(SchoolClass.teacher_id == u.id)
        return list(db.scalars(q.order_by(SchoolClass.id)).all())

    def _students_for_scope(db: Any, school_id: int, class_id: int) -> list[Any]:
        User = implementation.User
        ClassStudent = getattr(implementation, "ClassStudent", None)
        if class_id and ClassStudent is not None:
            sids = list(db.scalars(select(ClassStudent.student_id).where(ClassStudent.class_id == class_id)).all())
            if not sids:
                return []
            return list(
                db.scalars(
                    select(User).where(User.school_id == school_id, User.role == "student", User.id.in_(sids)).order_by(User.id)
                ).all()
            )
        return list(
            db.scalars(
                select(User).where(User.school_id == school_id, User.role == "student").order_by(User.id)
            ).all()
        )[:120]

    def _load_subject_maps(db: Any, school_id: int, subject: str, student_ids: list[int]) -> tuple[dict[tuple[int, str], dict[str, Any]], dict[tuple[int, str], int]]:
        """返回 (mastery_by_(sid,node_key), best_tier_rank_by_(sid,slug))"""
        if not student_ids:
            return {}, {}
        meta = _subject_meta(implementation, subject)
        mt, st = meta["mastery_tbl"], meta["sprints_tbl"]
        now = datetime.utcnow()
        m_rows = db.execute(
            select(mt).where(mt.c.school_id == school_id, mt.c.student_id.in_(student_ids))
        ).all()
        mastery_map: dict[tuple[int, str], dict[str, Any]] = {}
        for r in m_rows:
            st_dict = meta["state_fn"](r)
            rev = arc.compute_review_meta(
                r,
                now=now,
                stars=int(st_dict.get("stars", 0)),
                needs_repair=bool(st_dict.get("needsRepair", False)),
            )
            mastery_map[(int(r.student_id), str(r.node_key))] = {**st_dict, **rev}

        s_rows = db.execute(
            select(st).where(
                st.c.school_id == school_id,
                st.c.student_id.in_(student_ids),
                st.c.status == "submitted",
            )
        ).all()
        sprint_rank: dict[tuple[int, str], int] = {}
        for r in s_rows:
            t = mes.TIER_BY_CODE.get(r.tier_code or "L0", mes.TIER_BY_CODE["L0"])
            k = (int(r.student_id), str(r.slug))
            sprint_rank[k] = max(sprint_rank.get(k, -1), int(t["rank"]))
        return mastery_map, sprint_rank

    def _load_fresh_records(
        db: Any,
        school_id: int,
        subject: str,
        student_ids: list[int],
    ) -> tuple[dict[tuple[int, str], list[Any]], dict[tuple[int, str], list[Any]]]:
        """加载已提交的微测记录与专项记录，供 fresh_* 强制重刷模式按 task.created_at 核验."""
        if not student_ids:
            return {}, {}
        meta = _subject_meta(implementation, subject)
        qt, st = meta["quizzes_tbl"], meta["sprints_tbl"]
        q_rows = db.execute(
            select(qt).where(
                qt.c.school_id == school_id,
                qt.c.student_id.in_(student_ids),
                qt.c.status == "submitted",
            )
        ).all()
        quiz_by_key: dict[tuple[int, str], list[Any]] = {}
        for r in q_rows:
            quiz_by_key.setdefault((int(r.student_id), str(r.node_key)), []).append(r)

        s_rows = db.execute(
            select(st).where(
                st.c.school_id == school_id,
                st.c.student_id.in_(student_ids),
                st.c.status == "submitted",
            )
        ).all()
        sprint_by_key: dict[tuple[int, str], list[Any]] = {}
        for r in s_rows:
            sprint_by_key.setdefault((int(r.student_id), str(r.slug)), []).append(r)
        return quiz_by_key, sprint_by_key

    def _is_goal_met(
        task: Any,
        student_id: int,
        mastery_by_subj: dict[str, dict[tuple[int, str], dict[str, Any]]],
        sprint_by_subj: dict[str, dict[tuple[int, str], int]],
        fresh_quizzes_by_subj: dict[str, dict[tuple[int, str], list[Any]]] | None = None,
        fresh_sprints_by_subj: dict[str, dict[tuple[int, str], list[Any]]] | None = None,
    ) -> bool:
        subj = str(task.subject)
        key = str(task.target_key)
        goal = str(task.goal_code)
        task_created = getattr(task, "created_at", None)

        if goal.startswith("fresh_"):
            if task.task_kind == "map_node":
                q_list = (fresh_quizzes_by_subj or {}).get(subj, {}).get((student_id, key), [])
                for qr in q_list:
                    ts = getattr(qr, "submitted_at", None) or getattr(qr, "created_at", None)
                    if task_created is not None and (ts is None or ts < task_created):
                        continue
                    total = int(getattr(qr, "total", 0) or 0)
                    correct = int(getattr(qr, "correct", 0) or 0)
                    if total <= 0:
                        continue
                    rate_pct = round(correct * 100 / total)
                    if goal == "fresh_mastered":
                        if correct >= total:
                            return True
                    else:  # fresh_lit
                        if rate_pct >= 80 or (correct / total) >= 0.8:
                            return True
                return False

            # sprint fresh_*
            s_list = (fresh_sprints_by_subj or {}).get(subj, {}).get((student_id, key), [])
            for sr in s_list:
                ts = getattr(sr, "submitted_at", None) or getattr(sr, "started_at", None)
                if task_created is not None and (ts is None or ts < task_created):
                    continue
                t = mes.TIER_BY_CODE.get(sr.tier_code or "L0", mes.TIER_BY_CODE["L0"])
                rk = int(t["rank"])
                if goal == "fresh_L3":
                    if rk >= 3:
                        return True
                elif goal in ("fresh_tier_b", "fresh_L2"):
                    if rk >= 2:
                        return True
                else:  # fresh_complete | fresh_attempt
                    return True
            return False

        if task.task_kind == "map_node":
            st = mastery_by_subj.get(subj, {}).get((student_id, key))
            if not st:
                return False
            if goal == "mastered":
                return st["state"] == "mastered" and not st.get("needsRepair")
            return st["state"] in ("lit", "mastered") and not st.get("needsRepair")
        rank = sprint_by_subj.get(subj, {}).get((student_id, key), -1)
        if rank < 0:
            return False
        if goal == "L3":
            return rank >= 3
        if goal in ("L2", "tier_b"):
            return rank >= 2
        return True  # attempt | complete

    def _sync_targets(db: Any, school_id: int, task_rows: list[Any], target_rows: list[Any]) -> dict[int, list[Any]]:
        """对所有 pending 目标实时对账自动验收，并按 task_id 分组返回最新目标行."""
        by_task: dict[int, list[Any]] = {}
        task_by_id = {int(t.id): t for t in task_rows}
        subjects_needed: set[str] = set()
        fresh_subjects_needed: set[str] = set()
        student_ids: set[int] = set()
        for tr in target_rows:
            by_task.setdefault(int(tr.task_id), []).append(tr)
            if tr.status == "pending" and int(tr.task_id) in task_by_id:
                t_obj = task_by_id[int(tr.task_id)]
                subj = str(t_obj.subject)
                subjects_needed.add(subj)
                if str(t_obj.goal_code).startswith("fresh_"):
                    fresh_subjects_needed.add(subj)
                student_ids.add(int(tr.student_id))

        if not subjects_needed or not student_ids:
            return by_task

        mastery_by_subj: dict[str, dict[tuple[int, str], dict[str, Any]]] = {}
        sprint_by_subj: dict[str, dict[tuple[int, str], int]] = {}
        fresh_quizzes_by_subj: dict[str, dict[tuple[int, str], list[Any]]] = {}
        fresh_sprints_by_subj: dict[str, dict[tuple[int, str], list[Any]]] = {}
        sids = list(student_ids)
        for subj in subjects_needed:
            m_map, s_map = _load_subject_maps(db, school_id, subj, sids)
            mastery_by_subj[subj] = m_map
            sprint_by_subj[subj] = s_map
        for subj in fresh_subjects_needed:
            q_map, sp_map = _load_fresh_records(db, school_id, subj, sids)
            fresh_quizzes_by_subj[subj] = q_map
            fresh_sprints_by_subj[subj] = sp_map

        now = datetime.utcnow()
        changed = False
        for tr in target_rows:
            if tr.status != "pending":
                continue
            task = task_by_id.get(int(tr.task_id))
            if task is None:
                continue
            if _is_goal_met(
                task,
                int(tr.student_id),
                mastery_by_subj,
                sprint_by_subj,
                fresh_quizzes_by_subj,
                fresh_sprints_by_subj,
            ):
                db.execute(
                    update(t_targets)
                    .where(t_targets.c.id == tr.id)
                    .values(status="done", completed_at=now)
                )
                changed = True
        if changed:
            db.commit()
            refreshed = db.execute(
                select(t_targets).where(t_targets.c.task_id.in_(list(task_by_id.keys())))
            ).all()
            by_task = {}
            for tr in refreshed:
                by_task.setdefault(int(tr.task_id), []).append(tr)
        return by_task

    # ---------------- 教师端：班级热力诊断 + 一键派发 + 任务追踪 ----------------
    @router.get("/teacher/arena/diagnostics")
    def teacher_arena_diagnostics(
        subject: str = "数学",
        class_id: int = 0,
        grade: int | None = None,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        if subject not in ("数学", "英语", "语文"):
            raise HTTPException(400, "不支持的学科")
        ensure_all_tables(db)
        classes = _teacher_classes(db, u)
        class_list = [{"id": int(c.id), "name": c.name, "grade": int(c.grade)} for c in classes]
        use_class_id = int(class_id)
        if use_class_id and not any(c["id"] == use_class_id for c in class_list) and u.role == "teacher":
            raise HTTPException(403, "无权查看该班级")
        if grade is not None:
            active_grade = agp.clamp_arena_grade(grade, agp.DEFAULT_ARENA_GRADE, subject=subject)
        elif use_class_id:
            sel_cls = next((c for c in classes if int(c.id) == use_class_id), None)
            if sel_cls is None:
                SchoolClass = getattr(implementation, "SchoolClass", None)
                if SchoolClass is not None:
                    sel_cls = db.scalar(select(SchoolClass).where(SchoolClass.id == use_class_id))
            cls_grade = getattr(sel_cls, "grade", None) if sel_cls is not None else None
            active_grade = (
                agp.clamp_arena_grade(cls_grade, agp.DEFAULT_ARENA_GRADE, subject=subject)
                if cls_grade
                else agp.DEFAULT_ARENA_GRADE
            )
        else:
            active_grade = agp.DEFAULT_ARENA_GRADE

        students = _students_for_scope(db, int(u.school_id), use_class_id)
        sids = [int(s.id) for s in students]
        meta = _subject_meta(implementation, subject, grade=active_grade)
        mastery_map, sprint_rank = _load_subject_maps(db, int(u.school_id), subject, sids)
        total_stu = len(students)

        # 查询当前范围仍在 active 状态的任务 -> dispatched 集合 & 学生未完成任务计数
        aq = select(t_tasks).where(
            t_tasks.c.school_id == u.school_id,
            t_tasks.c.subject == subject,
            t_tasks.c.status == "active",
        )
        if use_class_id:
            aq = aq.where(t_tasks.c.class_id.in_([0, use_class_id]))
        active_tasks = db.execute(aq).all()
        dispatched_node_set: set[str] = set()
        dispatched_sprint_set: set[str] = set()
        for t in active_tasks:
            if t.task_kind == "map_node":
                dispatched_node_set.add(str(t.target_key))
            elif t.task_kind == "sprint":
                dispatched_sprint_set.add(str(t.target_key))

        pending_tasks_by_sid: dict[int, int] = {}
        if active_tasks and sids:
            atids = [int(t.id) for t in active_tasks]
            atr_rows = db.execute(
                select(t_targets).where(
                    t_targets.c.task_id.in_(atids),
                    t_targets.c.student_id.in_(sids),
                )
            ).all()
            synced = _sync_targets(db, int(u.school_id), active_tasks, atr_rows)
            for trs in synced.values():
                for tr in trs:
                    if tr.status != "done":
                        sid_int = int(tr.student_id)
                        pending_tasks_by_sid[sid_int] = pending_tasks_by_sid.get(sid_int, 0) + 1

        # 1. 全班考点薄弱热力榜（返回全部考点，纳入待温习人数）
        node_heat: list[dict[str, Any]] = []
        for n in meta["nodes"]:
            nk = n["key"]
            domain_name = meta["domain_name_fn"](n)
            lit_cnt = mastered_cnt = repair_cnt = review_due_cnt = weak_cnt = 0
            for sid in sids:
                st = mastery_map.get((sid, nk))
                is_review_due = bool(st and st.get("reviewDue"))
                if is_review_due:
                    review_due_cnt += 1
                if not st or st["state"] not in ("lit", "mastered") or st.get("needsRepair") or is_review_due:
                    weak_cnt += 1
                if st and st["state"] in ("lit", "mastered"):
                    lit_cnt += 1
                if st and st["state"] == "mastered":
                    mastered_cnt += 1
                if st and st.get("needsRepair"):
                    repair_cnt += 1
            node_heat.append({
                "key": nk,
                "name": n["name"],
                "domain": domain_name,
                "module": domain_name,
                "litCount": lit_cnt,
                "masteredCount": mastered_cnt,
                "repairCount": repair_cnt,
                "reviewDueCount": review_due_cnt,
                "weakCount": weak_cnt,
                "litRate": round(lit_cnt * 100 / total_stu) if total_stu else 0,
                "dispatched": nk in dispatched_node_set,
            })
        node_heat.sort(key=lambda x: (-x["repairCount"], -x["weakCount"], x["key"]))

        # 2. 应试专项达标榜
        sprint_heat: list[dict[str, Any]] = []
        for sp in meta["sprints"]:
            slug = sp["slug"]
            attempted = passed_l2 = weak_cnt = 0
            for sid in sids:
                rk = sprint_rank.get((sid, slug), -1)
                if rk >= 0:
                    attempted += 1
                if rk >= 2:
                    passed_l2 += 1
                else:
                    weak_cnt += 1
            sprint_heat.append({
                "slug": slug,
                "title": sp["title"],
                "attemptedCount": attempted,
                "passedCount": passed_l2,
                "weakCount": weak_cnt,
                "passRate": round(passed_l2 * 100 / total_stu) if total_stu else 0,
                "dispatched": slug in dispatched_sprint_set,
            })

        # 3. 班级学生个人明细
        node_names = {n["key"]: n["name"] for n in meta["nodes"]}
        stu_items: list[dict[str, Any]] = []
        for stu in students:
            sid = int(stu.id)
            lit_n = mastered_n = review_due_n = 0
            rep_names: list[str] = []
            for n in meta["nodes"]:
                st = mastery_map.get((sid, n["key"]))
                if st and st["state"] in ("lit", "mastered"):
                    lit_n += 1
                if st and st["state"] == "mastered":
                    mastered_n += 1
                if st and st.get("needsRepair"):
                    rep_names.append(f"{n['key']} {node_names.get(n['key'], n['key'])}")
                if st and st.get("reviewDue"):
                    review_due_n += 1
            best_rk = max((sprint_rank.get((sid, sp["slug"]), -1) for sp in meta["sprints"]), default=-1)
            best_tier = next((t for t in mes.TIERS if t["rank"] == best_rk), None) if best_rk >= 0 else None
            pts = meta["points_mod"].student_arena_points_summary(implementation, db, stu)
            stu_items.append({
                "studentId": sid,
                "name": stu.name or stu.username,
                "grade": getattr(stu, "grade", None),
                "litNodes": lit_n,
                "masteredNodes": mastered_n,
                "totalNodes": len(meta["nodes"]),
                "repairCount": len(rep_names),
                "repairNames": rep_names[:4],
                "reviewDueCount": review_due_n,
                "pendingTasksCount": pending_tasks_by_sid.get(sid, 0),
                "bestTier": best_tier,
                "pointsBalance": pts["balance"],
                "todayPoints": pts["todayEarned"],
            })

        return {
            "subject": subject,
            "grade": active_grade,
            "availableGrades": agp.build_available_grades(active_grade, active_grade, subject=subject),
            "ageProfile": agp.get_age_interaction_profile(active_grade),
            "classId": use_class_id,
            "classes": class_list,
            "studentCount": total_stu,
            "totalNodes": len(meta["nodes"]),
            "totalSprints": len(meta["sprints"]),
            "dispatchedNodeKeys": sorted(dispatched_node_set),
            "dispatchedSprintSlugs": sorted(dispatched_sprint_set),
            "nodeHeat": node_heat,
            "sprintHeat": sprint_heat,
            "students": stu_items,
        }

    @router.post("/teacher/arena/tasks")
    def create_arena_task(
        body: CreateArenaTaskBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        ensure_all_tables(db)
        meta = _subject_meta(implementation, body.subject)
        if body.task_kind == "map_node":
            node = next((n for n in meta["nodes"] if n["key"] == body.target_key), None)
            if not node:
                raise HTTPException(404, "未找到该知识节点")
            target_title = f"{node['key']} {node['name']}"
            goal_code = body.goal_code if body.goal_code in MAP_GOAL_CODES else "lit"
        else:
            sp = next((s for s in meta["sprints"] if s["slug"] == body.target_key), None)
            if not sp:
                raise HTTPException(404, "未找到该应试专项")
            target_title = sp["title"]
            goal_code = body.goal_code if body.goal_code in SPRINT_GOAL_CODES else "L2"

        students = _students_for_scope(db, int(u.school_id), int(body.class_id))
        if not students:
            raise HTTPException(400, "当前范围内没有可派发的学生")
        sids = [int(s.id) for s in students]
        mastery_map, sprint_rank = _load_subject_maps(db, int(u.school_id), body.subject, sids)

        if body.audience == "weak":
            picked: list[int] = []
            for sid in sids:
                if body.task_kind == "map_node":
                    st = mastery_map.get((sid, body.target_key))
                    if not st or st["state"] not in ("lit", "mastered") or st.get("needsRepair") or st.get("reviewDue"):
                        picked.append(sid)
                else:
                    if sprint_rank.get((sid, body.target_key), -1) < 2:
                        picked.append(sid)
            if not picked:
                raise HTTPException(400, "当前范围内所有学生均已掌握该考点/专项，无需定向补弱")
            target_sids = picked
        else:
            target_sids = sids

        now = datetime.utcnow()
        due = _parse_due_date(body.due_date, now)
        res = db.execute(
            insert(t_tasks).values(
                school_id=int(u.school_id),
                class_id=int(body.class_id),
                teacher_id=int(u.id),
                subject=body.subject,
                task_kind=body.task_kind,
                target_key=body.target_key,
                target_title=target_title,
                goal_code=goal_code,
                audience=body.audience,
                due_date=due,
                status="active",
                created_at=now,
            )
        )
        task_id = int(res.inserted_primary_key[0])
        for sid in target_sids:
            db.execute(
                insert(t_targets).values(task_id=task_id, student_id=sid, status="pending")
            )
        db.commit()
        target_grade = (
            agp.infer_grade_from_node_key(body.target_key)
            if body.task_kind == "map_node"
            else agp.infer_grade_from_sprint_slug(body.target_key)
        )
        return {
            "taskId": task_id,
            "subject": body.subject,
            "grade": target_grade,
            "targetTitle": target_title,
            "goalCode": goal_code,
            "goalLabel": GOAL_LABELS.get(goal_code, goal_code),
            "isFresh": goal_code.startswith("fresh_"),
            "audience": body.audience,
            "assignedCount": len(target_sids),
            "dueDate": due,
        }

    @router.get("/teacher/arena/tasks")
    def list_teacher_arena_tasks(
        subject: str = "",
        class_id: int = 0,
        grade: int | None = None,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        ensure_all_tables(db)
        q = select(t_tasks).where(t_tasks.c.school_id == u.school_id)
        if subject in ("数学", "英语", "语文"):
            q = q.where(t_tasks.c.subject == subject)
        if class_id:
            q = q.where(t_tasks.c.class_id == class_id)
        task_rows = db.execute(q.order_by(desc(t_tasks.c.id)).limit(40)).all()
        if not task_rows:
            return {"items": []}

        tids = [int(r.id) for r in task_rows]
        target_rows = db.execute(select(t_targets).where(t_targets.c.task_id.in_(tids))).all()
        by_task = _sync_targets(db, int(u.school_id), task_rows, target_rows)

        User = implementation.User
        all_sids = list({int(tr.student_id) for trs in by_task.values() for tr in trs})
        stu_name_map: dict[int, str] = {}
        if all_sids:
            for usr in db.scalars(select(User).where(User.id.in_(all_sids))).all():
                stu_name_map[int(usr.id)] = usr.name or usr.username

        filter_grade = agp.clamp_arena_grade(grade) if grade is not None else None
        items: list[dict[str, Any]] = []
        for tr in task_rows:
            t_grade = (
                agp.infer_grade_from_node_key(tr.target_key)
                if tr.task_kind == "map_node"
                else agp.infer_grade_from_sprint_slug(tr.target_key)
            )
            if filter_grade is not None and t_grade != filter_grade:
                continue
            trs = by_task.get(int(tr.id), [])
            done_cnt = sum(1 for x in trs if x.status == "done")
            pending_names = [stu_name_map.get(int(x.student_id), f"学生#{x.student_id}") for x in trs if x.status != "done"]
            items.append({
                "id": int(tr.id),
                "subject": tr.subject,
                "grade": t_grade,
                "classId": int(tr.class_id),
                "taskKind": tr.task_kind,
                "targetKey": tr.target_key,
                "targetTitle": tr.target_title,
                "goalCode": tr.goal_code,
                "goalLabel": GOAL_LABELS.get(tr.goal_code, tr.goal_code),
                "isFresh": str(tr.goal_code).startswith("fresh_"),
                "audience": tr.audience,
                "audienceLabel": "定向薄弱生" if tr.audience == "weak" else "全班",
                "dueDate": tr.due_date,
                "status": tr.status,
                "doneCount": done_cnt,
                "totalCount": len(trs),
                "pendingNames": pending_names[:20],
            })
        return {"items": items}

    @router.post("/teacher/arena/tasks/{task_id}/close")
    def close_teacher_arena_task(
        task_id: int,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        ensure_all_tables(db)
        row = db.execute(
            select(t_tasks).where(t_tasks.c.id == task_id, t_tasks.c.school_id == u.school_id)
        ).first()
        if row is None:
            raise HTTPException(404, "未找到该任务")
        db.execute(update(t_tasks).where(t_tasks.c.id == row.id).values(status="closed"))
        db.commit()
        return {"id": int(row.id), "status": "closed"}

    # ---------------- 教师端：题目预览 + 考点私房题 CRUD ----------------
    @router.get("/teacher/arena/target-preview")
    @router.get("/teacher/arena/preview-questions")
    def preview_arena_questions(
        subject: str = "数学",
        kind: str = "map_node",
        task_kind: str = "",
        target_key: str = "",
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        if subject not in ("数学", "英语", "语文"):
            raise HTTPException(400, "不支持的学科")
        use_kind = (task_kind or kind or "map_node").strip()
        if use_kind not in ("map_node", "sprint"):
            raise HTTPException(400, "kind 必须为 map_node 或 sprint")
        tk = target_key.strip()
        if not tk:
            raise HTTPException(400, "target_key 不能为空")
        ensure_all_tables(db)
        meta = _subject_meta(implementation, subject)

        builtin_raw: list[dict[str, Any]] = []
        target_title = tk
        custom_node_keys: list[str] = []

        if use_kind == "map_node":
            node = next((n for n in meta["nodes"] if n["key"] == tk), None)
            if not node:
                raise HTTPException(404, "未找到该知识节点")
            target_grade = agp.infer_grade_from_node_key(tk)
            target_title = f"{node['key']} {node['name']}"
            custom_node_keys = [tk]
            if subject == "数学":
                builtin_raw = mbm.generate_node_questions(tk, count=10, seed=1)
            elif subject == "英语":
                builtin_raw = list(ebm.QUESTION_BANK.get(tk, []))[:10]
            else:
                builtin_raw = list(cbm.QUESTION_BANK.get(tk, []))[:10]
        else:
            sp = next((s for s in meta["sprints"] if s["slug"] == tk), None)
            if not sp:
                raise HTTPException(404, "未找到该应试专项")
            target_grade = int(sp.get("grade") or agp.infer_grade_from_sprint_slug(tk))
            target_title = sp["title"]
            custom_node_keys = list(sp.get("nodeKeys") or [])
            if subject == "数学":
                builtin_raw = mes.compose_sprint_questions(tk, seed=1)[:10]
            elif subject == "英语":
                builtin_raw = ees.compose_sprint_questions(tk, seed=1)[:10]
            else:
                builtin_raw = ces.compose_sprint_questions(tk, seed=1)[:10]

        type_labels = mbm.TYPE_LABELS if subject == "数学" else (ebm.TYPE_LABELS if subject == "英语" else cbm.TYPE_LABELS)
        builtin_items = [
            {
                "id": str(q.get("id", "")),
                "questionType": str(q.get("questionType", "")),
                "typeLabel": str(q.get("typeLabel") or type_labels.get(str(q.get("questionType", "")), "")),
                "stem": str(q.get("text", "")),
                "text": str(q.get("text", "")),
                "options": list(q.get("options") or []),
                "answer": str(q.get("sampleAnswer") or q.get("answer") or ""),
                "explanation": str(q.get("explanation") or ""),
                "isCustom": False,
            }
            for q in builtin_raw[:10]
        ]

        custom_items: list[dict[str, Any]] = []
        if custom_node_keys:
            c_rows = db.execute(
                select(t_custom)
                .where(
                    t_custom.c.school_id == u.school_id,
                    t_custom.c.subject == subject,
                    t_custom.c.node_key.in_(custom_node_keys),
                    t_custom.c.active == 1,
                )
                .order_by(desc(t_custom.c.id))
            ).all()
            custom_items = [arc.serialize_custom_question_row(r) for r in c_rows]

        return {
            "subject": subject,
            "grade": target_grade,
            "kind": use_kind,
            "targetKey": tk,
            "targetTitle": target_title,
            "builtinCount": len(builtin_items),
            "customCount": len(custom_items),
            "items": custom_items + builtin_items,
            "questions": custom_items + builtin_items,
            "customQuestions": custom_items,
            "builtinQuestions": builtin_items,
        }

    @router.get("/teacher/arena/custom-questions")
    def list_custom_questions(
        subject: str = "",
        node_key: str = "",
        grade: int | None = None,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        ensure_all_tables(db)
        q = select(t_custom).where(t_custom.c.school_id == u.school_id, t_custom.c.active == 1)
        if subject in ("数学", "英语", "语文"):
            q = q.where(t_custom.c.subject == subject)
        if node_key.strip():
            q = q.where(t_custom.c.node_key == node_key.strip())
        rows = db.execute(q.order_by(desc(t_custom.c.id)).limit(200)).all()
        filter_grade = agp.clamp_arena_grade(grade) if grade is not None else None
        out_items: list[dict[str, Any]] = []
        for r in rows:
            item = arc.serialize_custom_question_row(r)
            item_grade = agp.infer_grade_from_node_key(str(item.get("nodeKey") or r.node_key))
            item["grade"] = item_grade
            if filter_grade is not None and item_grade != filter_grade:
                continue
            out_items.append(item)
        return {"items": out_items}

    @router.post("/teacher/arena/custom-questions")
    def create_custom_question(
        body: CreateCustomQuestionBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        ensure_all_tables(db)
        meta = _subject_meta(implementation, body.subject)
        if not any(n["key"] == body.node_key for n in meta["nodes"]):
            raise HTTPException(404, "未找到该学科下的知识节点")
        stem = body.stem.strip()
        answer = body.answer.strip()
        if not stem:
            raise HTTPException(400, "题干不能为空")
        if not answer:
            raise HTTPException(400, "标准答案不能为空")

        opts = [str(x).strip() for x in body.options if str(x).strip()]
        if body.question_type == "single_choice":
            if len(opts) < 2:
                raise HTTPException(400, "单选题至少需要 2 个非空选项")
        elif body.question_type == "true_false":
            if not opts:
                opts = ["正确", "错误"]
        else:
            opts = []

        now = datetime.utcnow()
        res = db.execute(
            insert(t_custom).values(
                school_id=int(u.school_id),
                subject=body.subject,
                node_key=body.node_key,
                question_type=body.question_type,
                stem=stem,
                options_json=json.dumps(opts, ensure_ascii=False),
                answer=answer,
                explanation=body.explanation.strip(),
                created_by=int(u.id),
                active=1,
                created_at=now,
            )
        )
        qid = int(res.inserted_primary_key[0])
        db.commit()
        row = db.execute(select(t_custom).where(t_custom.c.id == qid)).first()
        serialized = arc.serialize_custom_question_row(row)
        serialized["grade"] = agp.infer_grade_from_node_key(body.node_key)
        return serialized

    @router.delete("/teacher/arena/custom-questions/{qid}")
    def delete_custom_question(
        qid: int,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        ensure_all_tables(db)
        row = db.execute(
            select(t_custom).where(
                t_custom.c.id == qid,
                t_custom.c.school_id == u.school_id,
                t_custom.c.active == 1,
            )
        ).first()
        if row is None:
            raise HTTPException(404, "未找到该私房题")
        db.execute(update(t_custom).where(t_custom.c.id == row.id).values(active=0))
        db.commit()
        return {"ok": True, "id": int(row.id)}

    # ---------------- 学生端：置顶任务 + 家长鼓励 ----------------
    @router.get("/student/arena-tasks")
    def list_student_arena_tasks(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        ensure_all_tables(db)
        tr_rows = db.execute(
            select(t_targets).where(t_targets.c.student_id == u.id).order_by(desc(t_targets.c.id)).limit(40)
        ).all()
        task_ids = [int(r.task_id) for r in tr_rows]
        tasks_out: list[dict[str, Any]] = []
        if task_ids:
            t_rows = db.execute(
                select(t_tasks).where(
                    t_tasks.c.id.in_(task_ids),
                    t_tasks.c.school_id == u.school_id,
                    t_tasks.c.status == "active",
                )
            ).all()
            by_task = _sync_targets(db, int(u.school_id), t_rows, tr_rows)
            for t in sorted(t_rows, key=lambda x: -int(x.id)):
                mine = next((x for x in by_task.get(int(t.id), []) if int(x.student_id) == int(u.id)), None)
                if not mine:
                    continue
                t_grade = (
                    agp.infer_grade_from_node_key(t.target_key)
                    if t.task_kind == "map_node"
                    else agp.infer_grade_from_sprint_slug(t.target_key)
                )
                tasks_out.append({
                    "taskId": int(t.id),
                    "subject": t.subject,
                    "grade": t_grade,
                    "taskKind": t.task_kind,
                    "targetKey": t.target_key,
                    "targetTitle": t.target_title,
                    "goalCode": t.goal_code,
                    "goalLabel": GOAL_LABELS.get(t.goal_code, t.goal_code),
                    "isFresh": str(t.goal_code).startswith("fresh_"),
                    "dueDate": t.due_date,
                    "status": mine.status,
                    "actionUrl": _action_url(t.subject, t.task_kind, t.target_key),
                })

        cheers_rows = db.execute(
            select(t_cheers)
            .where(
                t_cheers.c.school_id == u.school_id,
                t_cheers.c.student_id == u.id,
                t_cheers.c.seen_at.is_(None),
            )
            .order_by(desc(t_cheers.c.id))
            .limit(3)
        ).all()
        cheers = [
            {
                "id": int(c.id),
                "parentName": c.parent_name,
                "subject": c.subject,
                "message": c.message,
                "dayKey": c.day_key,
            }
            for c in cheers_rows
        ]
        pending_cnt = sum(1 for x in tasks_out if x["status"] != "done")
        return {"pendingCount": pending_cnt, "items": tasks_out, "cheers": cheers}

    @router.post("/student/arena-cheers/seen")
    def mark_student_cheers_seen(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        ensure_all_tables(db)
        db.execute(
            update(t_cheers)
            .where(
                t_cheers.c.school_id == u.school_id,
                t_cheers.c.student_id == u.id,
                t_cheers.c.seen_at.is_(None),
            )
            .values(seen_at=datetime.utcnow())
        )
        db.commit()
        return {"ok": True}

    # ---------------- 家长端：三科汇总与任务进度 + 一键点赞鼓励 ----------------
    def _parent_children(db: Any, u: Any) -> list[Any]:
        User = implementation.User
        ParentStudent = getattr(implementation, "ParentStudent", None)
        if ParentStudent is None:
            return []
        sids = list(
            db.scalars(
                select(ParentStudent.student_id).where(
                    ParentStudent.parent_id == u.id,
                )
            ).all()
        )
        if not sids:
            return []
        return list(db.scalars(select(User).where(User.school_id == u.school_id, User.id.in_(sids))).all())

    @router.get("/parent/arena-summary")
    @router.get("/parent/arena/summary")
    @router.get("/parent/arena-overview")
    def parent_arena_summary(
        subject: str = "",
        grade: int | None = None,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "parent")
        ensure_all_tables(db)
        children = _parent_children(db, u)
        _, _, day_key = pcore.school_day_bounds_utc()
        subjs = [subject] if subject in ("数学", "英语", "语文") else ["数学", "英语", "语文"]

        out_children: list[dict[str, Any]] = []
        for c in children:
            sid = int(c.id)
            child_grade = agp.detect_user_grade(implementation, db, c)
            active_grade = agp.resolve_arena_grade(grade, child_grade, subject=subject or None)
            tr_rows = db.execute(select(t_targets).where(t_targets.c.student_id == sid)).all()
            tids = [int(r.task_id) for r in tr_rows]
            child_tasks: list[dict[str, Any]] = []
            if tids:
                tq = select(t_tasks).where(
                    t_tasks.c.id.in_(tids),
                    t_tasks.c.school_id == u.school_id,
                    t_tasks.c.status == "active",
                )
                if subject in ("数学", "英语", "语文"):
                    tq = tq.where(t_tasks.c.subject == subject)
                t_rows = db.execute(tq.order_by(desc(t_tasks.c.id))).all()
                by_task = _sync_targets(db, int(u.school_id), t_rows, tr_rows)
                for t in t_rows:
                    mine = next((x for x in by_task.get(int(t.id), []) if int(x.student_id) == sid), None)
                    if mine:
                        t_grade = (
                            agp.infer_grade_from_node_key(t.target_key)
                            if t.task_kind == "map_node"
                            else agp.infer_grade_from_sprint_slug(t.target_key)
                        )
                        child_tasks.append({
                            "taskId": int(t.id),
                            "subject": t.subject,
                            "grade": t_grade,
                            "targetKey": t.target_key,
                            "targetTitle": t.target_title,
                            "goalCode": t.goal_code,
                            "goalLabel": GOAL_LABELS.get(t.goal_code, t.goal_code),
                            "isFresh": str(t.goal_code).startswith("fresh_"),
                            "dueDate": t.due_date,
                            "status": mine.status,
                        })

            subj_stats: list[dict[str, Any]] = []
            points_balance = 0
            total_review_due = 0
            all_node_details: list[dict[str, Any]] = []
            for sname in subjs:
                subj_grade = agp.resolve_arena_grade(grade, child_grade, subject=sname)
                grade_meta = _subject_meta(implementation, sname, grade=subj_grade)
                all_meta = _subject_meta(implementation, sname)
                m_map, s_rank = _load_subject_maps(db, int(u.school_id), sname, [sid])
                lit_n = mastered_n = review_due_n = 0
                rep_names: list[str] = []
                node_details: list[dict[str, Any]] = []
                shown_keys: set[str] = set()
                for n in grade_meta["nodes"]:
                    nk = n["key"]
                    shown_keys.add(nk)
                    st = m_map.get((sid, nk))
                    state = st["state"] if st else "unexplored"
                    state_label = st.get("stateLabel", "未探索") if st else "未探索"
                    stars = int(st.get("stars", 0)) if st else 0
                    needs_rep = bool(st.get("needsRepair", False)) if st else False
                    rev_due = bool(st.get("reviewDue", False)) if st else False
                    days_since = int(st.get("daysSincePractice", 0)) if st else 0
                    if state in ("lit", "mastered"):
                        lit_n += 1
                    if state == "mastered":
                        mastered_n += 1
                    if needs_rep:
                        rep_names.append(f"{nk} {n['name']}")
                    if rev_due:
                        review_due_n += 1
                    node_details.append({
                        "subject": sname,
                        "grade": subj_grade,
                        "key": nk,
                        "name": n["name"],
                        "domain": grade_meta["domain_name_fn"](n),
                        "state": state,
                        "stateLabel": state_label,
                        "stars": stars,
                        "needsRepair": needs_rep,
                        "reviewDue": rev_due,
                        "daysSincePractice": days_since,
                    })
                if grade is None:
                    for n in all_meta["nodes"]:
                        nk = n["key"]
                        if nk in shown_keys:
                            continue
                        st = m_map.get((sid, nk))
                        if not st:
                            continue
                        n_grade = agp.infer_grade_from_node_key(nk, child_grade)
                        state = st["state"]
                        state_label = st.get("stateLabel", "未探索")
                        stars = int(st.get("stars", 0))
                        needs_rep = bool(st.get("needsRepair", False))
                        rev_due = bool(st.get("reviewDue", False))
                        days_since = int(st.get("daysSincePractice", 0))
                        if needs_rep:
                            rep_names.append(f"{nk} {n['name']}")
                        if rev_due:
                            review_due_n += 1
                        node_details.append({
                            "subject": sname,
                            "grade": n_grade,
                            "key": nk,
                            "name": n["name"],
                            "domain": all_meta["domain_name_fn"](n),
                            "state": state,
                            "stateLabel": state_label,
                            "stars": stars,
                            "needsRepair": needs_rep,
                            "reviewDue": rev_due,
                            "daysSincePractice": days_since,
                        })
                total_review_due += review_due_n
                all_node_details.extend(node_details)
                best_rk = max((s_rank.get((sid, sp["slug"]), -1) for sp in all_meta["sprints"]), default=-1)
                best_tier = next((t for t in mes.TIERS if t["rank"] == best_rk), None) if best_rk >= 0 else None
                pts = grade_meta["points_mod"].student_arena_points_summary(implementation, db, c)
                points_balance = pts["balance"]
                subj_stats.append({
                    "subject": sname,
                    "grade": subj_grade,
                    "litNodes": lit_n,
                    "masteredNodes": mastered_n,
                    "totalNodes": len(grade_meta["nodes"]),
                    "reviewDueCount": review_due_n,
                    "repairNames": rep_names[:4],
                    "bestTier": best_tier,
                    "nodeDetails": node_details,
                })

            cheered_today = db.execute(
                select(t_cheers.c.id).where(
                    t_cheers.c.parent_id == u.id,
                    t_cheers.c.student_id == sid,
                    t_cheers.c.day_key == day_key,
                )
            ).first() is not None

            out_children.append({
                "studentId": sid,
                "name": c.name or c.username,
                "grade": active_grade,
                "studentGrade": child_grade,
                "availableGrades": agp.build_available_grades(active_grade, child_grade, subject=subject or None),
                "pointsBalance": points_balance,
                "cheeredToday": cheered_today,
                "reviewDueCount": total_review_due,
                "nodeDetails": subj_stats[0]["nodeDetails"] if len(subj_stats) == 1 else all_node_details,
                "tasks": child_tasks,
                "subjects": subj_stats,
            })

        return {"items": out_children, "children": out_children}

    @router.post("/parent/arena-cheers")
    def send_parent_cheer(
        body: ParentCheerBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "parent")
        ensure_all_tables(db)
        children = _parent_children(db, u)
        if not any(int(c.id) == int(body.student_id) for c in children):
            raise HTTPException(403, "只能给已关联的孩子发送鼓励")
        _, _, day_key = pcore.school_day_bounds_utc()
        existing = db.execute(
            select(t_cheers.c.id).where(
                t_cheers.c.parent_id == u.id,
                t_cheers.c.student_id == body.student_id,
                t_cheers.c.day_key == day_key,
            )
        ).first()
        if existing is not None:
            return {"ok": True, "alreadyCheered": True, "dayKey": day_key}

        db.execute(
            insert(t_cheers).values(
                school_id=int(u.school_id),
                parent_id=int(u.id),
                parent_name=(u.name or "家长")[:80],
                student_id=int(body.student_id),
                subject=body.subject[:16],
                message=body.message.strip()[:120],
                day_key=day_key,
                created_at=datetime.utcnow(),
                seen_at=None,
            )
        )
        db.commit()
        return {"ok": True, "alreadyCheered": False, "dayKey": day_key}

    app.include_router(router)
    app.state.arena_tasks_installed = True
    app.state.arena_tasks_router = router
    return router


__all__ = ["install_arena_tasks_views", "register_arena_task_tables"]
