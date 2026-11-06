"""T03 第一步：单位与 π 边界回放与最小修复测试。

覆盖范围：
1. 服务端 parse_answer 与 check_solution 对 4π、π×4、4pi、4PI、4 pi、纯数字、分数、百分数、带单位的解析与判定；
2. 晚托辅导/引导侧（homework_guidance._check、check_steps）对上述输入的判定；
3. 学生页面 hwHasPi 单词边界漏洞（4pi 漏网）只读回放；
4. 正式提交判分（app_v924 的 grade_answers / normalized_answer_stats）只读回放，断言现状。

说明：各测试中基线断言（修复前 main）与修复后断言分别注释记录。
"""
from __future__ import annotations

import json
import re
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app_v924 import (
    Base,
    Question,
    User,
    _text_answer_matches,
    grade_answers,
    normalized_answer_stats,
)
from changying.services.homework_guidance import _check, check_steps
from changying.services.homework_math_check import (
    MISMATCH,
    OK,
    SKIPPED,
    _Skip,
    check_solution,
    parse_answer,
)

PAGE_FILE = Path(__file__).resolve().parents[1] / "changying" / "web" / "homework_assistant_pages.py"


# ==============================================================================
# 1. parse_answer 回放与修复后断言
# ==============================================================================

def test_parse_answer_pi_and_unit_boundary():
    """parse_answer 输入回放与修复断言。

    【基线行为（修复前 main）】：
    - parse_answer 只按正则提取单个数字，对 π / pi 没有任何语义保护。
    - 4π、π×4、4pi、4PI、4 pi 中的 π/pi 被当作无害字符忽略，直接提取出数字 4！
      即：
        assert parse_answer("4π") == (Fraction(4, 1), 0)
        assert parse_answer("π×4") == (Fraction(4, 1), 0)
        assert parse_answer("4pi") == (Fraction(4, 1), 0)
        assert parse_answer("4PI") == (Fraction(4, 1), 0)
        assert parse_answer("4 pi") == (Fraction(4, 1), 0)
    - 纯数字、分数、百分数正常解析。
    - '12.56平方厘米'：单位被忽略，提取出 12.56 (314/25)。
    - '12.56 cm²'：NFKC 规范化将 ² 转为 2，使得字符串变为 '12.56cm2'，存在两个数字而抛出 _Skip("答案里不是单个数字")。

    【修复后行为】：
    - 含 π / pi 的不可核验答案（4π、π×4、4pi、4PI、4 pi）不可直接提取出纯数字 4，
      必须抛出 _Skip("答案含π，需人工确认")，转由人工确认。
    - 纯数字、分数、百分数、可提取数值的中文单位维持原行为不变。
    """
    # --- A. 含 π / pi 的不可核验写法 ---
    # 【基线行为（main 提交 493e366）】：均返回 (Fraction(4, 1), 0)
    # 【修复后断言】：必须抛出 _Skip 异常，明确提示需人工确认，不可提取出 4
    for pi_ans in ("4π", "π×4", "4pi", "4PI", "4 pi"):
        with pytest.raises(_Skip) as exc_info:
            parse_answer(pi_ans)
        assert "答案含π，需人工确认" in str(exc_info.value), f"{pi_ans} 需明确提示人工确认"

    # --- B. 纯数字 ---
    # 【基线与修复后一致】：正常提取
    assert parse_answer("12") == (Fraction(12, 1), 0)
    assert parse_answer("12.56") == (Fraction(314, 25), 2)

    # --- B2. 普通单词里出现 pi 不能被当成圆周率 ---
    # 正则加了字母边界：只有 pi 两侧不是字母才算 π
    for plain in ("6 pizzas", "pink", "3 pieces", "pinyin"):
        try:
            parse_answer(plain)
        except _Skip as exc:  # noqa: PERF203 - 只为确认不是"含π"分支
            assert "答案含π" not in str(exc), f"{plain} 不应被当成含π：{exc}"

    # --- C. 分数与带分数 ---
    # 【基线与修复后一致】：正常提取
    assert parse_answer("3/4") == (Fraction(3, 4), 0)
    assert parse_answer("1又1/2") == (Fraction(3, 2), 0)

    # --- D. 百分数 ---
    # 【基线与修复后一致】：正常提取
    assert parse_answer("25%") == (Fraction(1, 4), 0)

    # --- E. 带单位 ---
    # 【基线与修复后一致】：
    # 12.56平方厘米：用于计算题提取可验算数值，提取 12.56（辅导层有“数值相符≠单位正确”的独立说明）
    assert parse_answer("12.56平方厘米") == (Fraction(314, 25), 2)
    # 12.56 cm²：由于 NFKC 将 ² 转为 2，产生 '12.56' 与 '2' 两个数字，触发多数字 _Skip，无法核对
    with pytest.raises(_Skip) as exc_info:
        parse_answer("12.56 cm²")
    assert "答案里不是单个数字" in str(exc_info.value)


# ==============================================================================
# 2. check_solution 回放与修复后断言
# ==============================================================================

def test_check_solution_pi_and_unit_boundary():
    """check_solution 回放与修复断言。

    【基线行为（修复前 main）】：
    - 当算式为 "4"、答案为 "4π" 时，check_solution 判定为 OK ("算式结果与答案一致")！
      即：assert check_solution("4", "4π")["status"] == OK
    - 当算式为 "4*3.14"、答案为 "4π" 时，check_solution 判定为 MISMATCH，且提示
      "算式结果是 314/25（约 12.56），答案写的是 4"，把 4π 吞成了 4，误判 AI 算式错误！
      即：assert check_solution("4*3.14", "4π")["status"] == MISMATCH
    - 4pi、4PI、4 pi 同理。

    【修复后行为】：
    - 当答案含 π / pi 时，parse_answer 抛出 _Skip，check_solution 捕获后返回 status="skipped"，
      detail="答案含π，需人工确认"，不再发生 false ok 也不会将正解误报为 mismatch。
    """
    # 【基线行为】：
    # check_solution("4", "4π")["status"] == OK （误判一致）
    # check_solution("4*3.14", "4π")["status"] == MISMATCH （误判不一致）
    # 【修复后断言】：无论算式写 4 还是 4*3.14，含 π 答案一律 status="skipped"，转人工确认
    for pi_ans in ("4π", "π×4", "4pi", "4PI", "4 pi"):
        res_four = check_solution("4", pi_ans)
        assert res_four["status"] == SKIPPED
        assert "答案含π，需人工确认" in res_four["detail"]

        res_calc = check_solution("4*3.14", pi_ans)
        assert res_calc["status"] == SKIPPED
        assert "答案含π，需人工确认" in res_calc["detail"]

    # 算式自身含 π（非合法符号）跳过核验
    assert check_solution("4*pi", "4π")["status"] == SKIPPED

    # 纯数字、分数、百分数正常核对
    assert check_solution("12", "12")["status"] == OK
    assert check_solution("12.56", "12.56")["status"] == OK
    assert check_solution("3/4", "3/4")["status"] == OK
    assert check_solution("1+1/2", "1又1/2")["status"] == OK
    assert check_solution("25/100", "25%")["status"] == OK

    # 单位：
    # "12.56平方厘米" 提取 12.56，数值一致判定为 OK
    assert check_solution("12.56", "12.56平方厘米")["status"] == OK
    # "12.56 cm²" 无法提取单一数字，返回 skipped
    assert check_solution("12.56", "12.56 cm²")["status"] == SKIPPED


# ==============================================================================
# 3. 辅导与引导链路回放（homework_guidance）
# ==============================================================================

def test_guidance_check_and_steps_boundary():
    """homework_guidance 的 _check 与 check_steps 回放与表现。

    【行为判定】：
    - homework_guidance 内部维护了 PI_MARKS = ("π", "Π", "pi", "PI")，
      同时 parse_answer 在修复后对所有 π/pi 均抛出 _Skip。
    - _check("4π")、_check("4pi") 等直接返回 None，无法比对。
    - check_steps 在遇到 check_solution 为 skipped / _check 为 None 时，将步骤类型从 'number' 降级为 'read'，
      不生成 numeric check 目标，页面不向学生提问该数值，转为只读呈现。
    - 绝不计入学生答错，绝不让学生输入该数值记为“自己算出”。
    """
    # A. _check 对 π 写法的防护
    for pi_ans in ("4π", "π×4", "4pi", "4PI", "4 pi"):
        assert _check(pi_ans) is None, f"{pi_ans} 应返回 None，不提供数值比对目标"

    # A2. 普通单词里的 pi 不能把整步降级（与 parse_answer 用同一个 contains_pi）
    for plain in ("6 pizzas", "3 pieces"):
        assert _check(plain) is not None, f"{plain} 不应被当成含 π"

    # B. _check 对纯数字与单位
    c_pure = _check("12.56")
    assert c_pure is not None
    assert abs(c_pure["value"] - 12.56) < 1e-9

    c_unit = _check("12.56平方厘米")
    assert c_unit is not None
    assert abs(c_unit["value"] - 12.56) < 1e-9

    # cm² 因 parse_answer 抛 _Skip 返回 None
    assert _check("12.56 cm²") is None

    # C. check_steps 降级逻辑：含 π 步骤绝不设 check 目标，降级为 read
    solution_pi = {
        "steps": [
            {"n": 1, "kind": "number", "ask": "算一下面积", "expression": "4*3.14", "answer": "4π", "text": "4π"},
        ],
        "answer": "4π",
    }
    processed = check_steps(solution_pi, final_ok=True)
    # 步骤降级为 read，不计入学生答题检查，不让学生输入该数值
    assert processed["steps"][0]["kind"] == "read"
    assert "check" not in processed["steps"][0]
    # finalCheck 也是 None，页面不让学生最终核对该数，不会产生 selfSolved 记录
    assert "finalCheck" not in processed


# ==============================================================================
# 4. 学生页面 hwHasPi 单词边界漏洞只读回放
# ==============================================================================

def test_student_page_hw_has_pi_gap_baseline():
    """学生页面 homework_assistant_pages.py 中 hwHasPi 的 4pi 单词边界缺口只读回放。

    【基线事实】：
    - 页面源码中定义为：function hwHasPi(t){return /[πΠ]|\bpi\b/i.test(String(t||''))}
    - 正则使用了 ASCII 单词边界 \\b。在 "4pi" 中，'4' 与 'p' 均为单词字符（\\w），两者之间不存在单词边界！
    - 因此：
      - "4π" -> True (匹配到 π)
      - "π×4" -> True (匹配到 π)
      - "4 pi" -> True (匹配到 \\bpi\\b)
      - "4pi" -> False (未匹配！漏网！)
      - "4PI" -> False (未匹配！漏网！)
    - 按照任务约束 C，本次不改动 homework_assistant_pages.py，仅在测试中回放确认此缺口。
    """
    content = PAGE_FILE.read_text(encoding="utf-8")
    match = re.search(r"function\s+hwHasPi\s*\([^\)]*\)\s*\{([^}]+)\}", content)
    assert match is not None, "hwHasPi 必须存在于页面脚本中"
    fn_body = match.group(1)
    assert r"/[πΠ]|\bpi\b/i" in fn_body, "hwHasPi 必须使用 /[πΠ]|\\bpi\\b/i 正则"

    # 在 Python 中模拟该 JS 正则
    js_regex = re.compile(r"[πΠ]|\bpi\b", re.IGNORECASE)
    assert bool(js_regex.search("4π")) is True
    assert bool(js_regex.search("π×4")) is True
    assert bool(js_regex.search("4 pi")) is True

    # 确认 4pi 和 4PI 漏网缺口
    assert bool(js_regex.search("4pi")) is False, "缺口确认：4pi 因缺少单词边界导致 hwHasPi 判定为 False"
    assert bool(js_regex.search("4PI")) is False, "缺口确认：4PI 因缺少单词边界导致 hwHasPi 判定为 False"


# ==============================================================================
# 5. 正式提交判分只读回放（app_v924: grade_answers / normalized_answer_stats）
# ==============================================================================

def test_official_submission_grading_read_only_baseline():
    """正式提交判分逻辑只读回放（不修改 app_v924）。

    【基线事实】：
    - 正式判分（grade_answers / normalized_answer_stats）使用的是 _text_answer_matches。
    - _text_answer_matches 逻辑：规范化去空格去标点后，首先进行精确字符串比对；若失败且两端均为合法浮点数，再进行 float 比对。
    - 它不使用 parse_answer，也不使用 sympy。
    - 现状表现：
      - 标准答案 "4π"：
        - 学生写 "4π" -> 正确 (100分)
        - 学生写 "4pi" -> 错误 (0分)
        - 学生写 "π×4" -> 错误 (0分)
        - 学生写 "4" -> 错误 (0分)
      - 标准答案 "12.56"：
        - 学生写 "12.56" -> 正确
        - 学生写 "12.56平方厘米" -> 错误 (非 float，字符串不等)
        - 学生写 "12.56 cm²" -> 错误
      - 标准答案 "12.56平方厘米"：
        - 学生写 "12.56平方厘米" -> 正确
        - 学生写 "12.56" -> 错误
    """
    # A. _text_answer_matches 底层判定回放
    # 标准答案 4π
    assert _text_answer_matches("4π", "4π") is True
    assert _text_answer_matches("4pi", "4π") is False
    assert _text_answer_matches("π×4", "4π") is False
    assert _text_answer_matches("4", "4π") is False

    # 标准答案 12.56
    assert _text_answer_matches("12.56", "12.56") is True
    assert _text_answer_matches("12.56平方厘米", "12.56") is False
    assert _text_answer_matches("12.56 cm²", "12.56") is False

    # 标准答案 12.56平方厘米
    assert _text_answer_matches("12.56平方厘米", "12.56平方厘米") is True
    assert _text_answer_matches("12.56", "12.56平方厘米") is False

    # B. grade_answers 与 normalized_answer_stats 内存数据库行为回放
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id=1, username="test_u", password_hash="dummy_hash", name="测试学生", role="student", school_id=1)
        q1 = Question(
            id=101,
            school_id=1,
            grade=6,
            subject="数学",
            question_type="fill_blank",
            text="求面积",
            correct_index=-1,
            options_json="[]",
            answer_json=json.dumps({"answer": "4π", "accepted": []}),
            knowledge="圆的面积",
        )
        q2 = Question(
            id=102,
            school_id=1,
            grade=6,
            subject="数学",
            question_type="fill_blank",
            text="求面积数值",
            correct_index=-1,
            options_json="[]",
            answer_json=json.dumps({"answer": "12.56", "accepted": []}),
            knowledge="圆的面积",
        )
        db.add_all([user, q1, q2])
        db.commit()

        # 学生提交 q1=4π (对), q2=12.56平方厘米 (错)
        answers = [
            SimpleNamespace(question_id=101, text_answer="4π", selected_index=None),
            SimpleNamespace(question_id=102, text_answer="12.56平方厘米", selected_index=None),
        ]
        norm, correct, total, score = grade_answers(db, user, answers)
        assert total == 2
        assert correct == 1
        assert score == 50
        assert norm[0]["correct"] is True
        assert norm[1]["correct"] is False  # 带单位未在 accepted_answers 时判错

        # 学生提交 q1=4pi (错)
        answers_pi_ascii = [
            SimpleNamespace(question_id=101, text_answer="4pi", selected_index=None),
        ]
        norm_ascii, correct_ascii, total_ascii, score_ascii = grade_answers(db, user, answers_pi_ascii)
        assert correct_ascii == 0
        assert score_ascii == 0
        assert norm_ascii[0]["correct"] is False

        # normalized_answer_stats 回放
        stat_answers = [
            {"question_id": 101, "text_answer": "4π"},
            {"question_id": 102, "text_answer": "12.56平方厘米"},
        ]
        know, valid = normalized_answer_stats(db, stat_answers, school_id=1)
        assert valid == 2
        # "圆的面积" 2题中对1题
        assert know["圆的面积"] == (1, 2)
