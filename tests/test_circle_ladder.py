"""圆面积退阶阶梯：状态机行为。答案是内容，不是判分规则。"""
from __future__ import annotations

from changying.services import circle_ladder as ladder


def test_five_ordered_levels_each_adds_one_condition():
    ranks = [x["rank"] for x in ladder.LEVELS]
    assert ranks == [1, 2, 3, 4, 5]
    # 前四级同一套数字（r=4），最后一级换回原题
    assert ladder.LEVELS[0]["answer"] == 2
    assert ladder.LEVELS[1]["answer_value"] == 16
    assert ladder.LEVELS[2]["answer_value"] == 50.24
    assert ladder.LEVELS[3]["answer_value"] == 50.24
    assert ladder.LEVELS[4]["answer_value"] is None


def test_correct_answer_climbs_one_rank():
    step = ladder.advance(1, True, 0)
    assert step["action"] == "up" and step["rank"] == 2 and step["misses"] == 0
    assert ladder.advance(4, True, 0)["rank"] == 5


def test_top_rank_correct_finishes():
    assert ladder.advance(5, True, 0)["action"] == "finished"


def test_wrong_answer_steps_down_one_rank():
    step = ladder.advance(3, False, 0)
    assert step["action"] == "down" and step["rank"] == 2 and step["misses"] == 0


def test_lowest_rank_cannot_go_lower():
    step = ladder.advance(1, False, 0)
    assert step["action"] == "remains" and step["rank"] == 1


def test_two_misses_on_same_rank_fall_back_instead_of_drilling():
    """连续错两次就进兜底，不继续往下罚站。"""
    first = ladder.advance(2, False, 0)
    assert first["action"] == "down"
    second = ladder.advance(2, False, 1)
    assert second["action"] == "fallback" and second["rank"] == 2


def test_correct_answer_resets_misses():
    assert ladder.advance(3, True, 1)["misses"] == 0


def test_fallback_offers_a_real_alternative_not_just_teacher():
    actions = ladder.fallback_actions()
    keys = {a["key"] for a in actions}
    assert keys == {"micro_lesson", "see_answer"}
    seen = next(a for a in actions if a["key"] == "see_answer")
    # 看答案必须明说"不算掌握"
    assert "不算你已经掌握" in seen["note"]
    micro = next(a for a in actions if a["key"] == "micro_lesson")
    assert "近似" in micro["text"] or "接近长方形" in micro["note"]


def test_out_of_range_rank_is_clamped():
    assert ladder.advance(0, True, 0)["rank"] == 2      # 先夹到 1，再升一级
    assert ladder.advance(99, True, 0)["action"] == "finished"

def test_too_many_mistakes_prompts_the_teacher():
    """跨级累计错误也要提醒老师，不能只在原地打转。"""
    step = ladder.advance(2, False, 0, total_misses=3)
    assert step["totalMisses"] == 4
    assert step["notifyTeacher"] is True
    # 还没到阈值时不打扰
    early = ladder.advance(2, False, 0, total_misses=1)
    assert early["totalMisses"] == 2 and early["notifyTeacher"] is False


def test_correct_answer_keeps_the_teacher_flag_once_raised():
    step = ladder.advance(3, True, 0, total_misses=4)
    assert step["action"] == "up" and step["notifyTeacher"] is True


def test_teacher_note_names_the_rank_and_count():
    note = ladder.teacher_note(2, 5)
    assert "第 2 级" in note and "累计错 5 次" in note and "尚未独立通过" in note
def test_ping_pong_between_two_ranks_is_stopped():
    """降阶答对、升阶又错，不能无限上下弹：同一级第 3 次就换讲法。"""
    visits: dict[str, int] = {}
    # L2 答对（第 1 次进入）
    step = ladder.advance(2, True, 0, 0, visits)
    visits = step["visits"]
    assert step["action"] == "up" and step["rank"] == 3
    # L3 答错（第 1 次进入）→ 退到 L2
    step = ladder.advance(3, False, 0, 0, visits)
    visits = step["visits"]
    assert step["action"] == "down" and step["rank"] == 2
    # L2 答对（第 2 次）→ 又到 L3
    step = ladder.advance(2, True, 0, 0, visits)
    visits = step["visits"]
    assert step["action"] == "up"
    # L3 又错（第 2 次）→ 仍先退一级
    step = ladder.advance(3, False, 0, 1, visits)
    visits = step["visits"]
    assert step["action"] == "down"
    # L2 第 3 次答对 → 再上 L3（第 3 次进入）
    step = ladder.advance(2, True, 0, 1, visits)
    visits = step["visits"]
    # L3 第 3 次进入后再错 → 不再退回，直接换讲法
    step = ladder.advance(3, False, 0, 2, visits)
    assert step["action"] == "fallback" and step["rank"] == 3


def test_visits_are_reported_so_the_caller_can_carry_them():
    step = ladder.advance(1, True, 0, 0)
    assert step["visits"] == {"1": 1}