"""周末课口径模拟(纯函数,不连数据库,不改线上数据)。

口径见 docs/weekend-course/3-口径文档.md。运行:python scripts/weekend_course_simulation.py
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


def _answers(n_ok: int, n_total: int, hint: int = 0, kp: str = "分数") -> list[Answer]:
    return [Answer(i < n_ok, hint if i < n_ok else 0, kp) for i in range(n_total)]


def scenarios() -> dict[str, tuple[list[Student], float | None]]:
    hist = lambda a, h: [History(a, h)] * 3
    strong = lambda **kw: Student("强", history=hist(80, 0.3), **kw)
    mid = lambda **kw: Student("中", history=hist(60, 1.0), **kw)
    weak = lambda **kw: Student("弱", history=hist(40, 2.0), **kw)
    return {
        "常规课(弱生进步,强带弱成功)": (
            [strong(answers=_answers(9, 10)), mid(answers=_answers(7, 10, 1)),
             weak(answers=_answers(5, 10, 1), flagged={"分数"}, followup_correct=True)], 55.0),
        "全对": ([strong(answers=_answers(10, 10)), mid(answers=_answers(10, 10)),
                  weak(answers=_answers(10, 10))], 90.0),
        "全错": ([strong(answers=_answers(0, 10)), mid(answers=_answers(0, 10)),
                  weak(answers=_answers(0, 10))], 50.0),
        "一人缺课": ([strong(answers=_answers(9, 10)), mid(attended=False),
                      weak(answers=_answers(6, 10, 1), followup_correct=False)], 55.0),
        "首次课无基线": ([Student("强", answers=_answers(8, 10)), Student("中", answers=_answers(6, 10)),
                          Student("弱", answers=_answers(4, 10), followup_correct=True)], None),
    }


def run() -> None:
    for name, (students, prev) in scenarios().items():
        print(f"== {name}")
        post = class_post_rate(students)
        for s in students:
            p = progress_points(s)
            tp = tutor_points(s)
            print(f"  {s.name}: 完成率={completion_rate(s.answers):.0f}% 提示依赖={hint_dependence(s.answers):.1f} "
                  f"进步分={p['points']}({p['reason']}) 小老师分(来自该生巩固)={tp}")
        print(f"  巩固后班级完成率={post:.1f}% 上次={prev} 团队分={team_points(prev, post)}")


if __name__ == "__main__":
    run()
