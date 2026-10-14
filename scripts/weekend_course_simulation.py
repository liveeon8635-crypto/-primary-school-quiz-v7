"""周末课口径模拟(不连数据库,不改线上数据)。

口径见 docs/weekend-course/3-口径文档.md,计分函数在 changying/services/weekend_scoring.py。
运行:python scripts/weekend_course_simulation.py
"""
from __future__ import annotations

from changying.services.weekend_scoring import (  # noqa: F401
    Answer, History, Student, class_post_rate, completion_bonus, completion_rate, hint_dependence,
    progress_points, team_points, tutor_points,
)


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
            cb = completion_bonus(s)
            print(f"  {s.name}: 完成率={completion_rate(s.answers):.0f}% 提示依赖={hint_dependence(s.answers):.1f} "
                  f"进步分={p['points']}({p['reason']}) 完成奖励={cb} 小老师分(来自该生巩固)={tp}")
        print(f"  巩固后班级完成率={post:.1f}% 上次={prev} 团队分={team_points(prev, post)}")


if __name__ == "__main__":
    run()
