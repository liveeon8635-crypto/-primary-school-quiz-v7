"""Independent check of a model's maths answer (used by the homework assistant).

The model is asked to return the calculation as ``expression`` next to its ``answer``. We evaluate
the expression ourselves and compare. Model output is never executed: it is normalised, matched
against a strict character allow-list, and then either evaluated by a tiny exact-fraction parser
(plain arithmetic) or handed to sympy as a single-variable linear/quadratic equation built only
from digits, ``x`` and ``+ - * / ^ ( )``.

Result: ``{"status": "ok" | "mismatch" | "skipped", "detail": str}``. ``skipped`` means we could
not check it (figures, word reasoning, several answers, unusual notation) - never "wrong".
"""

from __future__ import annotations

import re
import threading
import unicodedata
from fractions import Fraction
from typing import Any

MAX_EXPRESSION_CHARS = 120
MAX_TOKENS = 80
MAX_BITS = 256
MAX_EXPONENT = 8

OK = "ok"
MISMATCH = "mismatch"
SKIPPED = "skipped"


class _Skip(Exception):
    """The expression is outside what we can check."""


def _result(status: str, detail: str = "") -> dict[str, str]:
    return {"status": status, "detail": detail}


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    for old, new in (("×", "*"), ("·", "*"), ("÷", "/"), ("−", "-"), ("–", "-"), ("—", "-"), ("＝", "="), ("，", ","), ("。", "")):
        value = value.replace(old, new)
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"(\d+)又(\d+/\d+)", r"(\1+\2)", value)
    return value.replace("X", "x")


_NUM = re.compile(r"\d+(?:\.\d+)?")


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isdigit():
            m = _NUM.match(text, i)
            assert m
            tokens.append(m.group())
            i = m.end()
            if i < len(text) and text[i] == "%":
                tokens.extend(["/", "100"])
                i += 1
        elif ch in "+-*/^()":
            tokens.append(ch)
            i += 1
        else:
            raise _Skip(f"含有无法核对的字符“{ch}”")
        if len(tokens) > MAX_TOKENS:
            raise _Skip("算式太长")
    # implicit multiplication: 2(3+4), (1+2)(3+4), (1+2)3
    out: list[str] = []
    for tok in tokens:
        if out and (
            (out[-1] == ")" and (tok == "(" or tok[0].isdigit()))
            or (out[-1][0].isdigit() and tok == "(")
        ):
            out.append("*")
        out.append(tok)
    return out


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens, self.pos = tokens, 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def take(self) -> str:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def parse(self) -> Fraction:
        value = self.expr()
        if self.peek() is not None:
            raise _Skip("算式格式无法识别")
        return value

    def expr(self) -> Fraction:
        value = self.term()
        while self.peek() in ("+", "-"):
            op = self.take()
            right = self.term()
            value = value + right if op == "+" else value - right
            self._guard(value)
        return value

    def term(self) -> Fraction:
        value = self.power()
        while self.peek() in ("*", "/"):
            op = self.take()
            right = self.power()
            if op == "*":
                value = value * right
            else:
                if right == 0:
                    raise _Skip("算式里出现了除以 0")
                value = value / right
            self._guard(value)
        return value

    def power(self) -> Fraction:
        base = self.unary()
        if self.peek() == "^":
            self.take()
            exponent = self.unary()
            if exponent.denominator != 1 or abs(exponent) > MAX_EXPONENT:
                raise _Skip("乘方的指数太大或不是整数")
            if base == 0 and exponent < 0:
                raise _Skip("算式里出现了除以 0")
            base = base ** int(exponent)
            self._guard(base)
        return base

    def unary(self) -> Fraction:
        tok = self.peek()
        if tok in ("+", "-"):
            self.take()
            value = self.unary()
            return -value if tok == "-" else value
        return self.atom()

    def atom(self) -> Fraction:
        tok = self.peek()
        if tok is None:
            raise _Skip("算式不完整")
        if tok == "(":
            self.take()
            value = self.expr()
            if self.peek() != ")":
                raise _Skip("括号不匹配")
            self.take()
            return value
        if tok[0].isdigit():
            self.take()
            return Fraction(tok)
        raise _Skip("算式格式无法识别")

    @staticmethod
    def _guard(value: Fraction) -> None:
        if value.numerator.bit_length() > MAX_BITS or value.denominator.bit_length() > MAX_BITS:
            raise _Skip("数字太大")


def evaluate_arithmetic(text: str) -> Fraction:
    return _Parser(_tokenize(normalize(text))).parse()


_ANSWER_TOKEN = re.compile(r"(?<!\d)-?\d+(?:\.\d+)?(?:/\d+)?%?")
_PI_ANSWER = re.compile(r"[πΠ]|pi", re.IGNORECASE)


def parse_answer(answer: str) -> tuple[Fraction, int]:
    """The single numeric value in an answer like ``7个``, ``x=7``, ``5/6``, ``1又1/2`` -> (value, decimals)."""
    text = normalize(answer)
    if _PI_ANSWER.search(text):
        raise _Skip("答案含π，需人工确认")
    text = re.sub(r"^[a-z]=", "", text)
    mixed = re.fullmatch(r"(\D*?)\((\d+)\+(\d+)/(\d+)\)\D*", text)
    if mixed:
        whole, num, den = (int(x) for x in mixed.groups()[1:])
        if den == 0:
            raise _Skip("答案格式无法识别")
        value = Fraction(whole) + Fraction(num, den)
        return (-value if "-" in mixed.group(1) else value), 0
    found = _ANSWER_TOKEN.findall(text)
    if len(found) != 1:
        raise _Skip("答案里不是单个数字")
    token = found[0]
    percent = token.endswith("%")
    token = token.rstrip("%")
    negative = token.startswith("-")
    token = token.lstrip("-")
    decimals = len(token.split(".")[1]) if "." in token and "/" not in token else 0
    if "/" in token:
        num, den = token.split("/")
        if int(den) == 0:
            raise _Skip("答案格式无法识别")
        value = Fraction(int(num), int(den))
    else:
        value = Fraction(token)
    value = -value if negative else value
    return (value / 100 if percent else value), decimals


def _same(value: Fraction, answer: Fraction, decimals: int) -> bool:
    if value == answer:
        return True
    if decimals:  # a rounded decimal answer, e.g. 1/3 written as 0.33
        return abs(value - answer) <= Fraction(1, 2 * 10**decimals)
    return False


def _fmt(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}（约 {float(value):.4g}）"


def _solve_equation(text: str) -> list[Fraction]:
    try:
        import sympy
        from sympy.parsing.sympy_parser import parse_expr, standard_transformations
    except ImportError:  # the check is a safety net: without sympy equations are simply not checked
        raise _Skip("方程核对暂不可用")

    if not re.fullmatch(r"[0-9.+\-*/^()=x]+", text) or text.count("=") != 1:
        raise _Skip("方程格式无法识别")
    exponents = [int(n) for n in re.findall(r"\^(\d+)", text)]
    if (
        text.count("^") > 2                      # nested/stacked powers can blow up (9^99^9, ((9^8)^8)^8 ...)
        or any(n > MAX_EXPONENT for n in exponents)
        or re.search(r"\^\d+\^|\^\(|\^-|\^x|x\^x", text)
    ):
        raise _Skip("方程里的乘方无法核对")
    text = re.sub(r"(\d|\))x", r"\1*x", text)
    text = re.sub(r"x(\d|\()", r"x*\1", text)
    text = text.replace("^", "**")
    left, right = text.split("=")
    if not left or not right:
        raise _Skip("方程不完整")
    x = sympy.Symbol("x")
    try:
        lhs = parse_expr(left, local_dict={"x": x}, transformations=standard_transformations, evaluate=True)
        rhs = parse_expr(right, local_dict={"x": x}, transformations=standard_transformations, evaluate=True)
        poly = sympy.Poly(sympy.expand(lhs - rhs), x)
    except Exception:
        raise _Skip("方程无法核对")
    if poly.degree() < 1 or poly.degree() > 2:
        raise _Skip("只核对一次或二次方程")
    roots = sympy.solve(sympy.Eq(lhs, rhs), x)
    values: list[Fraction] = []
    for root in roots:
        if not isinstance(root, sympy.Rational):
            raise _Skip("方程的解不是有理数")
        values.append(Fraction(int(root.p), int(root.q)))
    if not values:
        raise _Skip("方程没有可核对的解")
    return values


SYMPY_TIMEOUT_SECONDS = 2.0


def _solve_with_timeout(text: str) -> list[Fraction]:
    """Run the equation check on a helper thread and give up after a couple of seconds.

    The input is already tightly bounded; this is the last line of defence so a pathological
    expression can never keep a request waiting (the helper thread is a daemon).
    """
    try:  # the first import of sympy takes a second or more: do it here, outside the 2-second budget
        import sympy  # noqa: F401
        from sympy.parsing.sympy_parser import parse_expr  # noqa: F401
    except ImportError:
        raise _Skip("方程核对暂不可用")
    box: dict[str, Any] = {}

    def run() -> None:
        try:
            box["value"] = _solve_equation(text)
        except BaseException as exc:  # noqa: BLE001 - re-raised on the caller's thread
            box["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(SYMPY_TIMEOUT_SECONDS)
    if worker.is_alive():
        raise _Skip("方程核对超时")
    if "error" in box:
        raise box["error"]
    return box["value"]


def check_solution(expression: Any, answer: Any) -> dict[str, str]:
    """Compare the model's calculation with its stated answer."""
    expr = normalize(expression)
    if not expr or not str(answer or "").strip():
        return _result(SKIPPED, "没有可核对的算式")
    if len(expr) > MAX_EXPRESSION_CHARS:
        return _result(SKIPPED, "算式太长")
    try:
        target, decimals = parse_answer(str(answer))
        if "x" in expr:
            solutions = _solve_with_timeout(expr)
            if any(_same(v, target, decimals) for v in solutions):
                return _result(OK, "方程的解与答案一致")
            return _result(MISMATCH, "方程的解是 " + "、".join(_fmt(v) for v in solutions) + f"，答案写的是 {_fmt(target)}")
        parts = expr.split(",")[0].split("=")
        values = [evaluate_arithmetic(part) for part in parts if part != ""]
        if not values:
            raise _Skip("没有可核对的算式")
        if any(v != values[0] for v in values[1:]):
            return _result(MISMATCH, "算式等号两边的结果不相等")
        # "12-5=7": the stated result is part of the expression; the answer must agree with it.
        if _same(values[-1], target, decimals):
            return _result(OK, "算式结果与答案一致")
        return _result(MISMATCH, f"算式结果是 {_fmt(values[-1])}，答案写的是 {_fmt(target)}")
    except _Skip as skip:
        return _result(SKIPPED, str(skip))
    except RecursionError:
        return _result(SKIPPED, "算式太复杂")


__all__ = ["MISMATCH", "OK", "SKIPPED", "check_solution", "evaluate_arithmetic", "normalize", "parse_answer"]
