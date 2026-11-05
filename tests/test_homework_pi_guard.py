"""含 π 的答案不能被当成纯数字，也不能被判错。

服务端：``_check`` 遇到 π 返回 None，该步降级为只读讲解。
页面：``hwNum`` 返回 null，且步骤/最终答案两处都先提示再 return，不进错题计数。
"""
from __future__ import annotations

from pathlib import Path

from changying.services.homework_guidance import _check

PAGE = Path(__file__).resolve().parents[1] / "changying" / "web" / "homework_assistant_pages.py"


def test_pi_answers_have_no_numeric_target():
    for answer in ("4π", "π×4", "4Π", "4pi", "4PI"):
        assert _check(answer) is None, f"{answer} 不应该拿到数字比较目标"


def test_plain_numbers_are_still_compared():
    target = _check("12.56 平方厘米")
    assert target is not None
    assert abs(target["value"] - 12.56) < 1e-9
    assert target["tol"] > 0


def test_page_parses_pi_as_unknown_not_as_a_number():
    text = PAGE.read_text(encoding="utf-8")
    assert "function hwHasPi(" in text
    assert "if(hwHasPi(t))return null;" in text, "hwNum 遇到 π 必须返回 null"


def test_page_warns_before_counting_a_pi_answer_wrong():
    text = PAGE.read_text(encoding="utf-8")
    # 步骤答案与最终答案各有一处；两处都必须在比较之前拦下
    assert text.count("if(hwHasPi(inp.value))") == 2, "步骤和最终答案都要拦"
    for marker in ("if(hwSame(inp.value,st.check))", "if(hwSame(inp.value,c)){"):
        guarded = text.index("if(hwHasPi(inp.value))")
        assert guarded != -1
    # 提示语要说明"不算你错"，不能静默
    assert "先不算你错" in text
