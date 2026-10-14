from __future__ import annotations

import time

import pytest

from changying.services.homework_math_check import check_solution, evaluate_arithmetic, normalize


@pytest.mark.parametrize(
    "expression,answer,status",
    [
        ("12-5", "7", "ok"),
        ("12-5", "8", "mismatch"),
        ("12-5=7", "7个", "ok"),
        ("12-5=8", "8", "mismatch"),
        ("(3+4)×2", "14", "ok"),
        ("3×(4+5)÷9", "3", "ok"),
        ("２４÷（３＋５）", "3", "ok"),  # full-width characters
        ("1/2+1/3", "5/6", "ok"),
        ("1又1/2+1/2", "2", "ok"),
        ("20%×50", "10", "ok"),
        ("0.5+0.25", "0.75", "ok"),
        ("2(3+4)", "14", "ok"),
        ("1÷3", "0.33", "ok"),  # rounded decimals are accepted
        ("1÷3", "0.4", "mismatch"),
        ("x+3=10", "x=7", "ok"),
        ("x+3=10", "8", "mismatch"),
        ("3x+2=14", "4", "ok"),
        ("x^2=9", "3", "ok"),
        ("x^2=9", "4", "mismatch"),
        # Not checkable -> skipped, never "wrong".
        ("12-5", "商3余2", "skipped"),
        ("", "7", "skipped"),
        ("12-5", "", "skipped"),
        ("a+b", "1", "skipped"),
        ("x+y=3", "1", "skipped"),
        ("5/0", "1", "skipped"),
        ("x/0=1", "1", "skipped"),
        ("x+1=x+2", "1", "skipped"),
        ("x*x*x*x=16", "2", "skipped"),
        ("2^100", "1", "skipped"),
    ],
)
def test_check_solution(expression, answer, status):
    assert check_solution(expression, answer)["status"] == status


def test_model_output_is_never_executed():
    for hostile in (
        "__import__('os').system('echo hacked')",
        "open('/etc/passwd').read()",
        "().__class__.__bases__",
        "x=__import__('os')",
        "lambda: 1",
        "1;2",
    ):
        assert check_solution(hostile, "1")["status"] == "skipped", hostile


def test_hostile_sizes_are_bounded_and_fast():
    started = time.time()
    for expression in (
        "9" * 500,
        "(" * 400 + "1" + ")" * 400,
        "9^9^9^9",
        "((9^8)^8)^8",
        "x^99999=1",
        "x^(99999999)=1",
        "1+" * 200 + "1",
    ):
        assert check_solution(expression, "1")["status"] == "skipped", expression[:30]
    assert time.time() - started < 5


def test_normalize_and_evaluate_helpers():
    assert normalize(" ２×３ ＝ 6。 ") == "2*3=6"
    assert str(evaluate_arithmetic("7÷2")) == "7/2"


def test_stacked_and_nested_powers_in_equations_are_refused_quickly():
    started = time.time()
    for expression in (
        "x+9^99^9=1",
        "x=9^99^9",
        "((((((((9^8)^8)^8)^8)^8)^8)^8)^8)+x=1",
        "x+9^(9^9)=1",
        "x^-1=2",
        "(x^8)^8=1",
        "x^9=1",
        "x^2+3^3^3=1",
    ):
        assert check_solution(expression, "3")["status"] == "skipped", expression
    assert time.time() - started < 5


def test_a_stuck_equation_check_gives_up_instead_of_hanging(monkeypatch):
    from changying.services import homework_math_check as mc

    monkeypatch.setattr(mc, "SYMPY_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(mc, "_solve_equation", lambda text: time.sleep(3) or [])
    started = time.time()
    result = check_solution("x+3=10", "7")
    assert result["status"] == "skipped" and "超时" in result["detail"]
    assert time.time() - started < 1.5


def test_negative_answers_keep_their_sign():
    from changying.services.homework_math_check import check_solution

    ok = [("3-8", "-5"), ("3-8=-5", "-5"), ("x+8=3", "x=-5"), ("0.5-1", "-0.5"), ("1/2-1", "-1/2"), ("7-9", "−2"), ("(-3)*2", "-6元")]
    for expression, answer in ok:
        assert check_solution(expression, answer)["status"] == "ok", (expression, answer)
    for expression, answer in [("3-8", "5"), ("x+8=3", "5"), ("12-5", "-7")]:
        assert check_solution(expression, answer)["status"] == "mismatch", (expression, answer)
    assert check_solution("12-5", "7个")["status"] == "ok"
