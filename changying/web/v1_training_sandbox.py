"""Ephemeral role training sandbox for Changying V1.

The sandbox deliberately does not use the production database session. It
exercises real HTTP routes and workflow state transitions while keeping all
training objects in a bounded in-process store. Training sessions are isolated
by authenticated owner and expire automatically.
"""

from __future__ import annotations

import secrets
import threading
import time
from copy import deepcopy
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


TRAINING_PREFIX = "/v1/training-sandbox"
TRAINING_TTL_SECONDS = 8 * 60 * 60
TRAINING_MAX_SESSIONS = 250

ROLE_FLOW: dict[str, list[dict[str, str]]] = {
    "teacher": [
        {"id": "purpose", "page": "/v1/workspace", "title": "认识产品主线"},
        {"id": "create_class", "page": "/v1/tool?page=classes", "title": "建立班级"},
        {"id": "add_student", "page": "/v1/tool?page=classes", "title": "添加学生账号"},
        {"id": "student_profile", "page": "/v1/student", "title": "学生连续档案"},
        {"id": "paper", "page": "/v1/tool?page=papers", "title": "组卷 / AI 出题"},
        {"id": "review", "page": "/v1/tool?page=papers", "title": "审核题目与积分"},
        {"id": "assign", "page": "/v1/tool?page=assignments", "title": "布置作业"},
        {"id": "student_submission", "page": "/v1/tool?page=assignments", "title": "学生作答"},
        {"id": "evidence", "page": "/v1/student", "title": "结果与学习证据回流"},
        {"id": "targeted", "page": "/v1/tool?page=ai", "title": "针对性练习"},
        {"id": "class_review", "page": "/v1/tool?page=analytics", "title": "课堂复盘"},
        {"id": "interactive", "page": "/v1/tool?page=teaching", "title": "互动课堂与随堂检测"},
        {"id": "points", "page": "/v1/tool?page=classPoints", "title": "积分与课堂评价"},
        {"id": "history", "page": "/v1/history", "title": "往期教学"},
        {"id": "transition", "page": "/v1/transition", "title": "升年级与衔接"},
        {"id": "hub", "page": "/v1/tool", "title": "全部功能与关系"},
    ],
    "student": [
        {"id": "classroom", "page": "/v1/tool?page=syncLearning", "title": "课堂"},
        {"id": "assignments", "page": "/v1/tool?page=assignments", "title": "作业"},
        {"id": "answer", "page": "/v1/tool?page=assignments", "title": "逐题作答"},
        {"id": "result", "page": "/v1/student", "title": "提交结果"},
        {"id": "practice", "page": "/v1/tool?page=practice", "title": "针对性练习"},
        {"id": "progress", "page": "/v1/tool?page=progress", "title": "学情"},
        {"id": "rewards", "page": "/v1/tool?page=rewards", "title": "积分"},
        {"id": "wrongbook", "page": "/v1/tool?page=wrongbook", "title": "错题"},
        {"id": "account", "page": "/v1/tool?page=account", "title": "账号与更多"},
    ],
    "parent": [
        {"id": "learning", "page": "/v1/tool?page=childLearning", "title": "孩子课程"},
        {"id": "assignments", "page": "/v1/tool?page=childAssignments", "title": "孩子作业"},
        {"id": "progress", "page": "/v1/tool?page=childProgress", "title": "孩子学情"},
        {"id": "rewards", "page": "/v1/tool?page=childRewards", "title": "课堂表现与积分"},
        {"id": "history", "page": "/v1/history", "title": "连续档案与历史"},
        {"id": "account", "page": "/v1/tool?page=account", "title": "账号与关联孩子"},
    ],
    "admin": [
        {"id": "overview", "page": "/v1/tool?page=admin", "title": "平台总览"},
        {"id": "users", "page": "/v1/tool?page=users", "title": "账号管理"},
        {"id": "classes", "page": "/v1/tool?page=users", "title": "班级与教学归属"},
        {"id": "points", "page": "/v1/tool?page=pointsAdmin", "title": "积分规则"},
        {"id": "audit", "page": "/v1/tool?page=adminAudit", "title": "审计"},
        {"id": "system", "page": "/v1/tool?page=system", "title": "系统设置"},
        {"id": "history", "page": "/v1/history", "title": "历史连续性"},
    ],
}

STEP_RELATIONSHIPS: dict[str, dict[str, str]] = {
    "create_class": {"who": "教师", "creates": "当前教学容器", "visible_to": "教师/管理员", "other_role_sees": "学生和家长此时还看不到任何作业", "communication_tip": "先确认班级名称、年级和教学周期，避免后续双方口径不一致", "next": "添加学生账号"},
    "add_student": {"who": "教师", "creates": "学生账号 + 连续档案起点", "visible_to": "教师/学生/授权家长", "other_role_sees": "学生得到自己的入口；家长只有关联后才看到该学生", "communication_tip": "告知学生使用哪个账号、家长能看到什么，避免把教师入口当成学生入口", "next": "组卷和布置"},
    "paper": {"who": "教师", "creates": "试卷草稿", "visible_to": "教师", "other_role_sees": "未发布前学生和家长都看不到", "communication_tip": "草稿不是作业，教师审核通过后才进入布置环节", "next": "审核后布置"},
    "assign": {"who": "教师", "creates": "学生待办", "visible_to": "教师/学生/家长状态页", "other_role_sees": "学生看到待完成作业；家长看到状态和截止信息，不代替学生作答", "communication_tip": "让教师明确告诉学生作业名称、截止时间和入口", "next": "学生作答"},
    "student_submission": {"who": "学生或沙盒模拟器", "creates": "提交结果", "visible_to": "学生/教师/家长摘要", "other_role_sees": "教师看到提交状态与结果；家长看到授权范围内的完成状态/摘要", "communication_tip": "提交与保存草稿要区分，避免教师误以为学生已交", "next": "教师查看证据"},
    "evidence": {"who": "系统汇总", "creates": "分数/逐题/知识点/错题/积分", "visible_to": "按角色授权可见", "other_role_sees": "学生看自己的结果；教师看教学证据；家长看适合家长理解的摘要", "communication_tip": "页面要解释同一结果在不同角色下为什么显示不同", "next": "针对性练习"},
    "targeted": {"who": "AI 草稿 + 教师审核", "creates": "针对性练习", "visible_to": "教师审核后给指定学生", "other_role_sees": "学生只看到教师确认发布后的练习", "communication_tip": "明确说明练习为什么被生成、依据哪次测试/哪些错题", "next": "继续练习并回流"},
    "class_review": {"who": "教师", "creates": "班级复盘讲义草稿", "visible_to": "教师确认后再发布", "other_role_sees": "草稿阶段学生不可见；发布后按课堂流程使用", "communication_tip": "区分“系统建议复盘”和“教师确认发布”", "next": "互动课堂"},
    "interactive": {"who": "教师主导/学生参与", "creates": "课堂事件与随堂反馈", "visible_to": "对应课堂参与者", "other_role_sees": "学生收到邀请/随堂检测；教师看汇总；家长只看适合家长端的结果摘要", "communication_tip": "邀请学生讲解不是系统评价，学生可以拒绝且不形成负面证据", "next": "积分/复盘/下一轮教学"},
    "points": {"who": "规则或教师", "creates": "可追溯积分动态", "visible_to": "教师/学生/家长摘要", "other_role_sees": "不同角色看到同一积分事实的不同解释层级", "communication_tip": "必须显示积分来源，避免用户把总分误解为学习成绩", "next": "长期激励与评价"},
    "history": {"who": "系统归档", "creates": "只读往期教学", "visible_to": "授权角色", "other_role_sees": "当前工作台减少旧内容，但学生连续档案仍保留历史", "communication_tip": "结束班级不等于删除学生或删除成绩", "next": "阶段衔接"},
    "transition": {"who": "教师/管理员", "creates": "同一学生的阶段变化计划", "visible_to": "授权角色", "other_role_sees": "学生/家长看到的是同一学生下一阶段的连续变化，而不是一个新账号", "communication_tip": "强调学生ID连续性，避免升年级重复建档", "next": "下一阶段继续同一档案"},
}

SCENARIO_PRESETS: dict[str, dict[str, Any]] = {
    "empty": {"title": "从零开始", "description": "从建立班级开始完整练习。"},
    "assigned": {"title": "从已布置作业开始", "description": "自动准备班级、学生、试卷和已布置作业，直接练学生端/关联角色体验。"},
    "submitted": {"title": "从已提交结果开始", "description": "自动准备一次学生提交，直接练证据回流、针对性练习和学情沟通。"},
    "classroom": {"title": "从课堂复盘开始", "description": "自动准备班级结果与复盘草稿，直接练互动课堂、随堂检测和积分评价。"},
}


@dataclass
class SandboxSession:
    session_id: str
    owner_user_id: int
    primary_role: str
    current_role: str
    linked_mode: str = "choose"
    created_at: float = field(default_factory=time.time)
    touched_at: float = field(default_factory=time.time)
    next_id: int = 1
    progress: dict[str, str] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=lambda: {
        "classes": [],
        "students": [],
        "papers": [],
        "assignments": [],
        "submissions": [],
        "targeted_practices": [],
        "class_reviews": [],
        "classroom_events": [],
        "points": [],
        "history": [],
        "transitions": [],
    })
    events: list[dict[str, Any]] = field(default_factory=list)

    def new_id(self) -> int:
        value = self.next_id
        self.next_id += 1
        return value

    def touch(self) -> None:
        self.touched_at = time.time()


class TrainingSandboxStore:
    def __init__(self, ttl_seconds: int = TRAINING_TTL_SECONDS, max_sessions: int = TRAINING_MAX_SESSIONS):
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._items: dict[str, SandboxSession] = {}
        self._lock = threading.RLock()

    def _prune(self) -> None:
        now = time.time()
        expired = [sid for sid, item in self._items.items() if now - item.touched_at > self.ttl_seconds]
        for sid in expired:
            self._items.pop(sid, None)
        if len(self._items) <= self.max_sessions:
            return
        oldest = sorted(self._items.values(), key=lambda item: item.touched_at)
        for item in oldest[: len(self._items) - self.max_sessions]:
            self._items.pop(item.session_id, None)

    def create(self, owner_user_id: int, role: str, linked_mode: str = "choose") -> SandboxSession:
        with self._lock:
            self._prune()
            sid = secrets.token_urlsafe(18)
            item = SandboxSession(
                session_id=sid,
                owner_user_id=owner_user_id,
                primary_role=role,
                current_role=role,
                linked_mode=linked_mode,
            )
            self._items[sid] = item
            return item

    def get(self, session_id: str, owner_user_id: int) -> SandboxSession:
        with self._lock:
            self._prune()
            item = self._items.get(session_id)
            if not item or item.owner_user_id != owner_user_id:
                raise KeyError(session_id)
            item.touch()
            return item

    def reset(self, session_id: str, owner_user_id: int) -> SandboxSession:
        with self._lock:
            old = self.get(session_id, owner_user_id)
            fresh = SandboxSession(
                session_id=old.session_id,
                owner_user_id=old.owner_user_id,
                primary_role=old.primary_role,
                current_role=old.primary_role,
                linked_mode=old.linked_mode,
            )
            self._items[session_id] = fresh
            return fresh


STORE = TrainingSandboxStore()


class StartTrainingBody(BaseModel):
    linked_mode: str = Field(default="choose", pattern="^(choose|switch|simulate)$")


class TrainingActionBody(BaseModel):
    action: str = Field(min_length=1, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


def _role(user: Any) -> str:
    role = str(getattr(user, "role", "") or "").strip().lower()
    if role not in ROLE_FLOW:
        raise HTTPException(403, "当前身份暂不支持实操沙盒")
    return role


def _payload(session: SandboxSession) -> dict[str, Any]:
    return {
        "ok": True,
        "training": True,
        "persistent": False,
        "sessionID": session.session_id,
        "primaryRole": session.primary_role,
        "currentRole": session.current_role,
        "linkedMode": session.linked_mode,
        "flow": ROLE_FLOW.get(session.primary_role, []),
        "relationships": STEP_RELATIONSHIPS,
        "scenarioPresets": SCENARIO_PRESETS,
        "progress": deepcopy(session.progress),
        "data": deepcopy(session.data),
        "events": deepcopy(session.events[-80:]),
        "notice": "这是临时实操沙盒；不会写入真实班级、学生、作业、积分或学习证据。",
    }


def _need(items: list[dict[str, Any]], label: str) -> dict[str, Any]:
    if not items:
        raise HTTPException(409, f"请先完成：{label}")
    return items[-1]


def _event(session: SandboxSession, action: str, detail: str) -> None:
    session.events.append({
        "id": session.new_id(),
        "action": action,
        "detail": detail,
        "role": session.current_role,
        "at": int(time.time()),
    })


def apply_training_action(session: SandboxSession, action: str, payload: dict[str, Any]) -> None:
    p = payload or {}
    session.touch()

    if action == "load_scenario":
        preset = str(p.get("preset", "empty")).strip()
        if preset not in SCENARIO_PRESETS:
            raise HTTPException(400, "未知练习场景")
        if preset == "empty":
            session.data = SandboxSession(
                session_id=session.session_id,
                owner_user_id=session.owner_user_id,
                primary_role=session.primary_role,
                current_role=session.primary_role,
                linked_mode=session.linked_mode,
            ).data
            session.progress = {}
            session.events = []
            session.next_id = 1
            _event(session, action, "preset=empty")
            return
        if session.primary_role != "teacher":
            raise HTTPException(400, "当前预置场景仅支持教师主线")
        # Presets are built through the same sandbox actions so page relationships
        # and downstream behavior stay identical to a user-driven training run.
        if not session.data["classes"]:
            apply_training_action(session, "create_class", {"name": "五年级实操班", "grade": 5})
        if not session.data["students"]:
            apply_training_action(session, "add_student", {"name": "小禾", "username": "xiaohe01"})
        if not session.data["papers"]:
            apply_training_action(session, "create_paper", {"subject": "数学", "textbook": "人教版", "knowledge": "小数乘法", "questionCount": 8})
            apply_training_action(session, "review_paper", {})
        if not session.data["assignments"]:
            apply_training_action(session, "assign", {"title": "小数乘法练习", "due": "本周五"})
        if preset in {"submitted", "classroom"} and not session.data["submissions"]:
            apply_training_action(session, "simulate_student_submission", {"correct": 6})
        if preset == "classroom" and not session.data["class_reviews"]:
            apply_training_action(session, "create_class_review", {})
        _event(session, action, f"preset={preset}")
        return

    if action == "set_linked_mode":
        mode = str(p.get("mode", "")).strip()
        if mode not in {"choose", "switch", "simulate"}:
            raise HTTPException(400, "关联角色体验方式无效")
        session.linked_mode = mode
        _event(session, action, f"linked_mode={mode}")
        return

    if action == "visit_step":
        step = str(p.get("step", "")).strip()
        valid = {x["id"] for x in ROLE_FLOW.get(session.primary_role, [])}
        if step not in valid:
            raise HTTPException(400, "未知教学步骤")
        session.progress[step] = str(p.get("status", "done"))
        _event(session, action, step)
        return

    if session.primary_role != "teacher":
        raise HTTPException(400, "当前版本仅教师主线支持业务实操；其他身份可先浏览完整页面关系")

    if action == "create_class":
        name = str(p.get("name", "")).strip() or "五年级一班"
        grade = int(p.get("grade", 5))
        if not 1 <= grade <= 12:
            raise HTTPException(400, "年级无效")
        obj = {"id": session.new_id(), "name": name[:120], "grade": grade, "teacher": "当前沙盒教师"}
        session.data["classes"].append(obj)
        session.progress["create_class"] = "done"
        _event(session, action, f"class={obj['id']}:{obj['name']}")
        return

    if action == "add_student":
        cls = _need(session.data["classes"], "建立班级")
        name = str(p.get("name", "")).strip() or "小禾"
        username = str(p.get("username", "")).strip() or f"sandbox{session.new_id()}"
        obj = {
            "id": session.new_id(),
            "name": name[:100],
            "username": username[:100],
            "classID": cls["id"],
            "className": cls["name"],
            "grade": cls["grade"],
        }
        session.data["students"].append(obj)
        session.progress["add_student"] = "done"
        _event(session, action, f"student={obj['id']}:{obj['name']}")
        return

    if action == "create_paper":
        cls = _need(session.data["classes"], "建立班级")
        count = max(1, min(int(p.get("questionCount", 8)), 30))
        subject = str(p.get("subject", "数学"))[:30]
        knowledge = str(p.get("knowledge", "小数乘法"))[:120]
        textbook = str(p.get("textbook", "人教版"))[:80]
        questions = [
            {
                "id": session.new_id(),
                "index": i + 1,
                "type": ["单选", "填空", "计算", "应用"][i % 4],
                "knowledge": knowledge,
                "prompt": f"{knowledge} · 沙盒练习题 {i + 1}",
            }
            for i in range(count)
        ]
        obj = {
            "id": session.new_id(),
            "title": str(p.get("title", f"{subject}练习"))[:160],
            "grade": cls["grade"],
            "subject": subject,
            "textbook": textbook,
            "knowledge": knowledge,
            "questions": questions,
            "reviewed": False,
        }
        session.data["papers"].append(obj)
        session.progress["paper"] = "done"
        _event(session, action, f"paper={obj['id']}:questions={count}")
        return

    if action == "review_paper":
        paper = _need(session.data["papers"], "组卷")
        paper["reviewed"] = True
        paper["reviewNote"] = str(p.get("note", "题型、答案方式、难度和积分已检查"))[:300]
        session.progress["review"] = "done"
        _event(session, action, f"paper={paper['id']}:reviewed")
        return

    if action == "assign":
        cls = _need(session.data["classes"], "建立班级")
        paper = _need(session.data["papers"], "组卷")
        if not paper.get("reviewed"):
            raise HTTPException(409, "请先审核试卷")
        students = [x for x in session.data["students"] if x["classID"] == cls["id"]]
        if not students:
            raise HTTPException(409, "请先添加学生")
        obj = {
            "id": session.new_id(),
            "title": str(p.get("title", paper["title"]))[:160],
            "classID": cls["id"],
            "paperID": paper["id"],
            "studentIDs": [x["id"] for x in students],
            "due": str(p.get("due", "本周五"))[:40],
            "status": "open",
        }
        session.data["assignments"].append(obj)
        session.progress["assign"] = "done"
        _event(session, action, f"assignment={obj['id']}:students={len(students)}")
        return

    if action in {"switch_to_student", "simulate_student_submission", "student_submit"}:
        assignment = _need(session.data["assignments"], "布置作业")
        student = _need(session.data["students"], "添加学生")
        paper = _need(session.data["papers"], "组卷")
        if action == "switch_to_student":
            session.current_role = "student"
            session.linked_mode = "switch"
            _event(session, action, f"student={student['id']}")
            return
        if action == "student_submit" and session.current_role != "student":
            raise HTTPException(409, "请先切换到虚拟学生视角，或选择自动模拟")
        total = len(paper["questions"])
        correct = max(0, min(total, int(p.get("correct", max(1, round(total * 0.75))))))
        score = round(correct * 100 / max(1, total))
        existing = [x for x in session.data["submissions"] if x["assignmentID"] == assignment["id"] and x["studentID"] == student["id"]]
        if existing:
            raise HTTPException(409, "这份沙盒作业已经提交，可重置沙盒后重新练习")
        obj = {
            "id": session.new_id(),
            "assignmentID": assignment["id"],
            "studentID": student["id"],
            "studentName": student["name"],
            "score": score,
            "correct": correct,
            "total": total,
            "knowledge": paper["knowledge"],
            "accuracy": score,
            "wrongCount": total - correct,
            "source": "manual_virtual_student" if action == "student_submit" else "simulated_linked_role",
        }
        session.data["submissions"].append(obj)
        session.data["points"].append({
            "id": session.new_id(),
            "studentID": student["id"],
            "points": correct,
            "source": "练习完成",
        })
        session.progress["student_submission"] = "done"
        session.progress["evidence"] = "done"
        _event(session, action, f"submission={obj['id']}:score={score}")
        return

    if action == "return_primary_role":
        session.current_role = session.primary_role
        _event(session, action, "return_primary")
        return

    if action == "create_targeted_practice":
        submission = _need(session.data["submissions"], "学生提交或自动模拟提交")
        obj = {
            "id": session.new_id(),
            "studentID": submission["studentID"],
            "knowledge": submission["knowledge"],
            "basedOnSubmissionID": submission["id"],
            "questionCount": max(3, min(int(p.get("questionCount", 6)), 15)),
            "status": "draft",
        }
        session.data["targeted_practices"].append(obj)
        session.progress["targeted"] = "done"
        _event(session, action, f"targeted={obj['id']}")
        return

    if action == "create_class_review":
        submission = _need(session.data["submissions"], "至少一次学生提交")
        cls = _need(session.data["classes"], "建立班级")
        obj = {
            "id": session.new_id(),
            "classID": cls["id"],
            "knowledge": submission["knowledge"],
            "summary": f"围绕{submission['knowledge']}生成课堂复盘草稿",
            "status": "draft",
        }
        session.data["class_reviews"].append(obj)
        session.progress["class_review"] = "done"
        _event(session, action, f"class_review={obj['id']}")
        return

    if action == "run_interactive_classroom":
        review = _need(session.data["class_reviews"], "生成课堂复盘")
        obj = {
            "id": session.new_id(),
            "reviewID": review["id"],
            "mode": str(p.get("mode", "师生共讲"))[:30],
            "quickCheck": True,
            "studentResponse": str(p.get("studentResponse", "已完成"))[:30],
        }
        session.data["classroom_events"].append(obj)
        session.progress["interactive"] = "done"
        _event(session, action, f"classroom={obj['id']}")
        return

    if action == "archive_history":
        cls = _need(session.data["classes"], "建立班级")
        obj = {"id": session.new_id(), "classID": cls["id"], "className": cls["name"], "status": "read_only"}
        session.data["history"].append(obj)
        session.progress["history"] = "done"
        _event(session, action, f"history={obj['id']}")
        return

    if action == "create_transition":
        student = _need(session.data["students"], "添加学生")
        obj = {
            "id": session.new_id(),
            "studentID": student["id"],
            "from": str(p.get("from", f"{student['grade']}年级")),
            "to": str(p.get("to", f"{student['grade'] + 1}年级")),
            "status": "practice_plan",
        }
        session.data["transitions"].append(obj)
        session.progress["transition"] = "done"
        _event(session, action, f"transition={obj['id']}")
        return

    if action == "review_points":
        _need(session.data["points"], "学生提交")
        session.progress["points"] = "done"
        _event(session, action, "points_reviewed")
        return

    raise HTTPException(400, "未知沙盒操作")


def install_v1_training_sandbox_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v1_training_sandbox_routes_installed", False):
        return

    router = APIRouter()

    @router.post(TRAINING_PREFIX + "/start", include_in_schema=False)
    def start_training(body: StartTrainingBody, user=Depends(implementation.current_user)):
        role = _role(user)
        item = STORE.create(int(user.id), role, body.linked_mode)
        return _payload(item)

    @router.get(TRAINING_PREFIX + "/{session_id}", include_in_schema=False)
    def read_training(session_id: str, user=Depends(implementation.current_user)):
        try:
            item = STORE.get(session_id, int(user.id))
        except KeyError:
            raise HTTPException(404, "实操沙盒不存在或已过期") from None
        return _payload(item)

    @router.post(TRAINING_PREFIX + "/{session_id}/action", include_in_schema=False)
    def training_action(session_id: str, body: TrainingActionBody, user=Depends(implementation.current_user)):
        try:
            item = STORE.get(session_id, int(user.id))
        except KeyError:
            raise HTTPException(404, "实操沙盒不存在或已过期") from None
        apply_training_action(item, body.action, body.payload)
        return _payload(item)

    @router.post(TRAINING_PREFIX + "/{session_id}/reset", include_in_schema=False)
    def reset_training(session_id: str, user=Depends(implementation.current_user)):
        try:
            item = STORE.reset(session_id, int(user.id))
        except KeyError:
            raise HTTPException(404, "实操沙盒不存在或已过期") from None
        return _payload(item)

    app.include_router(router)
    app.state.v1_training_sandbox_routes_installed = True


__all__ = [
    "ROLE_FLOW",
    "SCENARIO_PRESETS",
    "STEP_RELATIONSHIPS",
    "STORE",
    "TRAINING_PREFIX",
    "TrainingSandboxStore",
    "apply_training_action",
    "install_v1_training_sandbox_routes",
]
