"""语数英知识地图与应试专项「教—学—家」三端打通服务.

核心能力：
- 教师端：按班级筛选、全班考点薄弱热力榜与专项达标率、一键派发（全班 / 仅薄弱生）+ 达标目标 + 任务追踪；
- 学生端：置顶老师布置的闯关/专项任务、达标后自动验收完成、接收长缨助手转达的家长点赞鼓励；
- 家长端：全自动同步关联孩子的老师任务进度与三科学情汇总、每日一键点赞鼓励。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, desc, insert, select, update

from changying.services import arena_points_core as pcore
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
    "L2": "达到 L2 达标·银章",
    "L3": "达到 L3 熟练·金章",
}

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
    goal_code: str = Field(default="lit", pattern="^(lit|mastered|attempt|L2|L3)$")
    audience: str = Field(default="all", pattern="^(all|weak)$")
    due_date: str = Field(default="", max_length=24)


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
    return {
        "tasks": md.tables["arena_tasks"],
        "targets": md.tables["arena_task_targets"],
        "cheers": md.tables["arena_parent_cheers"],
    }


def _subject_meta(implementation: Any, subject: str) -> dict[str, Any]:
    if subject == "数学":
        tbls = register_math_arena_tables(implementation)
        return {
            "nodes": list(mbm.MATH_G5_CORE_MAP["nodes"]),
            "sprints": list(mes.MATH_G5_SPRINTS),
            "mastery_tbl": tbls["mastery"],
            "sprints_tbl": tbls["sprints"],
            "points_mod": mapts,
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
        return {
            "nodes": list(ebm.ENGLISH_G5_NODES),
            "sprints": list(ees.ENGLISH_G5_SPRINTS),
            "mastery_tbl": tbls["mastery"],
            "sprints_tbl": tbls["sprints"],
            "points_mod": eapts,
            "state_fn": lambda r: ebm.compute_light_state(
                attempts=int(r.attempts), correct=int(r.correct),
                hard_correct=int(r.hard_correct),
                best_quiz_rate_pct=int(r.best_quiz_rate_pct),
                sprint_boost_stars=int(r.sprint_boost_stars),
                needs_repair=bool(r.needs_repair),
            ),
        }
    tbls = register_chinese_arena_tables(implementation)
    return {
        "nodes": list(cbm.CHINESE_G5_NODES),
        "sprints": list(ces.CHINESE_G5_SPRINTS),
        "mastery_tbl": tbls["mastery"],
        "sprints_tbl": tbls["sprints"],
        "points_mod": capts,
        "state_fn": lambda r: cbm.compute_light_state(
            attempts=int(r.attempts), correct=int(r.correct),
            hard_correct=int(r.hard_correct),
            best_quiz_rate_pct=int(r.best_quiz_rate_pct),
            sprint_boost_stars=int(r.sprint_boost_stars),
            needs_repair=bool(r.needs_repair),
        ),
    }


def _action_url(subject: str, task_kind: str, target_key: str) -> str:
    map_url, sp_url = SUBJECT_URLS.get(subject, ("/v1/math-star-map", "/v1/math-sprints"))
    if task_kind == "map_node":
        return f"{map_url}#node={target_key}"
    return sp_url


def install_arena_tasks_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "arena_tasks_installed", False):
        return app.state.arena_tasks_router
    tables = register_arena_task_tables(implementation)
    t_tasks, t_targets, t_cheers = tables["tasks"], tables["targets"], tables["cheers"]
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def ensure_all_tables(db: Any) -> None:
        bind = db.get_bind()
        for tbl in (t_tasks, t_targets, t_cheers):
            tbl.create(bind=bind, checkfirst=True)
        for subj in ("数学", "英语", "语文"):
            m = _subject_meta(implementation, subj)
            m["mastery_tbl"].create(bind=bind, checkfirst=True)
            m["sprints_tbl"].create(bind=bind, checkfirst=True)

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
        m_rows = db.execute(
            select(mt).where(mt.c.school_id == school_id, mt.c.student_id.in_(student_ids))
        ).all()
        mastery_map: dict[tuple[int, str], dict[str, Any]] = {}
        for r in m_rows:
            mastery_map[(int(r.student_id), str(r.node_key))] = meta["state_fn"](r)

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

    def _is_goal_met(
        task: Any,
        student_id: int,
        mastery_by_subj: dict[str, dict[tuple[int, str], dict[str, Any]]],
        sprint_by_subj: dict[str, dict[tuple[int, str], int]],
    ) -> bool:
        subj = str(task.subject)
        key = str(task.target_key)
        goal = str(task.goal_code)
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
        if goal == "L2":
            return rank >= 2
        return True  # attempt

    def _sync_targets(db: Any, school_id: int, task_rows: list[Any], target_rows: list[Any]) -> dict[int, list[Any]]:
        """对所有 pending 目标实时对账自动验收，并按 task_id 分组返回最新目标行."""
        by_task: dict[int, list[Any]] = {}
        task_by_id = {int(t.id): t for t in task_rows}
        subjects_needed: set[str] = set()
        student_ids: set[int] = set()
        for tr in target_rows:
            by_task.setdefault(int(tr.task_id), []).append(tr)
            if tr.status == "pending" and int(tr.task_id) in task_by_id:
                subjects_needed.add(str(task_by_id[int(tr.task_id)].subject))
                student_ids.add(int(tr.student_id))

        if not subjects_needed or not student_ids:
            return by_task

        mastery_by_subj: dict[str, dict[tuple[int, str], dict[str, Any]]] = {}
        sprint_by_subj: dict[str, dict[tuple[int, str], int]] = {}
        sids = list(student_ids)
        for subj in subjects_needed:
            m_map, s_map = _load_subject_maps(db, school_id, subj, sids)
            mastery_by_subj[subj] = m_map
            sprint_by_subj[subj] = s_map

        now = datetime.utcnow()
        changed = False
        for tr in target_rows:
            if tr.status != "pending":
                continue
            task = task_by_id.get(int(tr.task_id))
            if task is None:
                continue
            if _is_goal_met(task, int(tr.student_id), mastery_by_subj, sprint_by_subj):
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
        students = _students_for_scope(db, int(u.school_id), use_class_id)
        sids = [int(s.id) for s in students]
        meta = _subject_meta(implementation, subject)
        mastery_map, sprint_rank = _load_subject_maps(db, int(u.school_id), subject, sids)
        total_stu = len(students)

        # 1. 全班考点薄弱热力榜
        node_heat: list[dict[str, Any]] = []
        for n in meta["nodes"]:
            nk = n["key"]
            lit_cnt = mastered_cnt = repair_cnt = weak_cnt = 0
            for sid in sids:
                st = mastery_map.get((sid, nk))
                if not st or st["state"] not in ("lit", "mastered") or st.get("needsRepair"):
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
                "litCount": lit_cnt,
                "masteredCount": mastered_cnt,
                "repairCount": repair_cnt,
                "weakCount": weak_cnt,
                "litRate": round(lit_cnt * 100 / total_stu) if total_stu else 0,
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
            })

        # 3. 班级学生个人明细
        node_names = {n["key"]: n["name"] for n in meta["nodes"]}
        stu_items: list[dict[str, Any]] = []
        for stu in students:
            sid = int(stu.id)
            lit_n = mastered_n = 0
            rep_names: list[str] = []
            for n in meta["nodes"]:
                st = mastery_map.get((sid, n["key"]))
                if st and st["state"] in ("lit", "mastered"):
                    lit_n += 1
                if st and st["state"] == "mastered":
                    mastered_n += 1
                if st and st.get("needsRepair"):
                    rep_names.append(f"{n['key']} {node_names.get(n['key'], n['key'])}")
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
                "bestTier": best_tier,
                "pointsBalance": pts["balance"],
                "todayPoints": pts["todayEarned"],
            })

        return {
            "subject": subject,
            "classId": use_class_id,
            "classes": class_list,
            "studentCount": total_stu,
            "totalNodes": len(meta["nodes"]),
            "totalSprints": len(meta["sprints"]),
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
            goal_code = body.goal_code if body.goal_code in ("lit", "mastered") else "lit"
        else:
            sp = next((s for s in meta["sprints"] if s["slug"] == body.target_key), None)
            if not sp:
                raise HTTPException(404, "未找到该应试专项")
            target_title = sp["title"]
            goal_code = body.goal_code if body.goal_code in ("attempt", "L2", "L3") else "L2"

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
                    if not st or st["state"] not in ("lit", "mastered") or st.get("needsRepair"):
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
        due = body.due_date.strip() or (now + timedelta(hours=8, days=2)).strftime("%Y-%m-%d")
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
        return {
            "taskId": task_id,
            "subject": body.subject,
            "targetTitle": target_title,
            "goalCode": goal_code,
            "goalLabel": GOAL_LABELS.get(goal_code, goal_code),
            "audience": body.audience,
            "assignedCount": len(target_sids),
            "dueDate": due,
        }

    @router.get("/teacher/arena/tasks")
    def list_teacher_arena_tasks(
        subject: str = "",
        class_id: int = 0,
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

        items: list[dict[str, Any]] = []
        for tr in task_rows:
            trs = by_task.get(int(tr.id), [])
            done_cnt = sum(1 for x in trs if x.status == "done")
            pending_names = [stu_name_map.get(int(x.student_id), f"学生#{x.student_id}") for x in trs if x.status != "done"]
            items.append({
                "id": int(tr.id),
                "subject": tr.subject,
                "classId": int(tr.class_id),
                "taskKind": tr.task_kind,
                "targetKey": tr.target_key,
                "targetTitle": tr.target_title,
                "goalCode": tr.goal_code,
                "goalLabel": GOAL_LABELS.get(tr.goal_code, tr.goal_code),
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
                tasks_out.append({
                    "taskId": int(t.id),
                    "subject": t.subject,
                    "taskKind": t.task_kind,
                    "targetKey": t.target_key,
                    "targetTitle": t.target_title,
                    "goalCode": t.goal_code,
                    "goalLabel": GOAL_LABELS.get(t.goal_code, t.goal_code),
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
    def parent_arena_summary(
        subject: str = "",
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
                        child_tasks.append({
                            "taskId": int(t.id),
                            "subject": t.subject,
                            "targetTitle": t.target_title,
                            "goalLabel": GOAL_LABELS.get(t.goal_code, t.goal_code),
                            "dueDate": t.due_date,
                            "status": mine.status,
                        })

            subj_stats: list[dict[str, Any]] = []
            points_balance = 0
            for sname in subjs:
                meta = _subject_meta(implementation, sname)
                m_map, s_rank = _load_subject_maps(db, int(u.school_id), sname, [sid])
                lit_n = mastered_n = 0
                rep_names: list[str] = []
                for n in meta["nodes"]:
                    st = m_map.get((sid, n["key"]))
                    if st and st["state"] in ("lit", "mastered"):
                        lit_n += 1
                    if st and st["state"] == "mastered":
                        mastered_n += 1
                    if st and st.get("needsRepair"):
                        rep_names.append(f"{n['key']} {n['name']}")
                best_rk = max((s_rank.get((sid, sp["slug"]), -1) for sp in meta["sprints"]), default=-1)
                best_tier = next((t for t in mes.TIERS if t["rank"] == best_rk), None) if best_rk >= 0 else None
                pts = meta["points_mod"].student_arena_points_summary(implementation, db, c)
                points_balance = pts["balance"]
                subj_stats.append({
                    "subject": sname,
                    "litNodes": lit_n,
                    "masteredNodes": mastered_n,
                    "totalNodes": len(meta["nodes"]),
                    "repairNames": rep_names[:4],
                    "bestTier": best_tier,
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
                "grade": getattr(c, "grade", None),
                "pointsBalance": points_balance,
                "cheeredToday": cheered_today,
                "tasks": child_tasks,
                "subjects": subj_stats,
            })

        return {"items": out_children}

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
