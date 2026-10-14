"""周末课计分口径(纯函数,不连数据库)。

口径见 docs/weekend-course/3-口径文档.md;scripts/weekend_course_simulation.py 用同一份代码跑模拟。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

PROGRESS_ACC_PP = 10      # 正确率进步阈值(百分点)
PROGRESS_ACC_PTS = 2
PROGRESS_HINT_DROP = 0.5  # 提示依赖下降阈值(级)
PROGRESS_HINT_PTS = 2
WEAK_FIX_PTS = 3
WEAK_FIX_MAX = 2
PROGRESS_CAP = 6
TUTOR_PTS = 2
TEAM_BASE = 2
TEAM_STEP_PP = 10
TEAM_CAP = 4
BASELINE_N = 3
COMPLETE_HIGH = (90, 2)  # 完成率奖励:≥90% +2
COMPLETE_MID = (80, 1)   # ≥80% +1


@dataclass
class Answer:
    correct: bool
    hint: int = 0  # 0=未用 1-3 级
    knowledge: str = ""


@dataclass
class History:
    accuracy: float  # 0-100
    hint_dep: float


@dataclass
class Student:
    name: str
    attended: bool = True
    answers: list[Answer] = field(default_factory=list)
    history: list[History] = field(default_factory=list)
    flagged: set[str] = field(default_factory=set)  # 上次被标记的薄弱知识点
    followup_correct: bool | None = None  # 作为被讲学生的巩固题结果


def completion_rate(answers: list[Answer]) -> float:
    return 100.0 * sum(a.correct for a in answers) / len(answers) if answers else 0.0


def hint_dependence(answers: list[Answer]) -> float:
    done = [a.hint for a in answers if a.correct]
    return mean(done) if done else 0.0


def progress_points(s: Student) -> dict:
    if not s.attended or not s.answers:
        return {"points": 0, "reason": "缺课或未作答"}
    base = s.history[-BASELINE_N:]
    if not base:
        return {"points": 0, "reason": "首次课,只记参与"}
    pts = 0
    acc = completion_rate(s.answers)
    if acc - mean(h.accuracy for h in base) >= PROGRESS_ACC_PP:
        pts += PROGRESS_ACC_PTS
    if acc > 0 and mean(h.hint_dep for h in base) - hint_dependence(s.answers) >= PROGRESS_HINT_DROP:
        pts += PROGRESS_HINT_PTS
    fixed = {
        a.knowledge for a in s.answers
        if a.correct and a.hint < 3 and a.knowledge in s.flagged
    }
    pts += WEAK_FIX_PTS * min(len(fixed), WEAK_FIX_MAX)
    return {"points": min(pts, PROGRESS_CAP), "reason": "ok"}


def completion_bonus(s: Student) -> int:
    """完成率奖励:独立于进步分,不占进步封顶;缺课/未作答不得。"""
    if not s.attended or not s.answers:
        return 0
    r = completion_rate(s.answers)
    for line, pts in (COMPLETE_HIGH, COMPLETE_MID):
        if r >= line:
            return pts
    return 0


def tutor_points(tutee: Student) -> int:
    return TUTOR_PTS if tutee.followup_correct else 0


def team_points(prev_post: float | None, post: float) -> int:
    if prev_post is None or post <= prev_post:
        return 0
    return min(TEAM_BASE + int((post - prev_post) // TEAM_STEP_PP), TEAM_CAP)


def class_post_rate(students: list[Student]) -> float:
    """巩固后完成率:被讲学生以巩固题结果替换其错题,其余沿用练习结果。"""
    rates = []
    for s in students:
        if not s.attended or not s.answers:
            continue
        r = completion_rate(s.answers)
        if s.followup_correct:
            r = min(100.0, r + 100.0 / len(s.answers))
        rates.append(r)
    return mean(rates) if rates else 0.0



__all__ = [
    "Answer", "History", "Student", "class_post_rate", "completion_bonus", "completion_rate", "hint_dependence",
    "progress_points", "team_points", "tutor_points",
]
