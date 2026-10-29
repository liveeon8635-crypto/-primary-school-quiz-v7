"""周末课 AI 出习题：按题型和难度配额出题，数学答案由系统验算（纯函数，不连数据库、不调模型）.

Teachers found the drafts "too easy, one type only": the old prompt asked for lesson plan and 4–6 questions in one
go, with no type or difficulty targets, and the difficulty was assigned by position. Here questions are their own
request with fixed quotas (type x level), every row says its level and its solution steps, and rules decide what
is kept:
- a maths question above 基础 must make the pupil compute (numbers or operators in the stem), and 提高 needs two
  or more solution steps;
- a maths answer that is a number comes with an arithmetic expression, evaluated exactly here; when the two disagree
  the question is dropped (the model's arithmetic is not trusted). Fill-in and problem-solving questions above 基础
  must have one; others without one are kept and shown as not yet checked;
- near-duplicates of each other or of the lesson's existing questions are dropped.
Whatever the quotas still miss is asked for once more, naming exactly what is missing.
"""
from __future__ import annotations

import ast
import re
from fractions import Fraction
from typing import Any

TYPES = ("choice", "final_answer", "short_answer", "composition")
TYPE_NAMES = {"choice": "选择题", "final_answer": "填空／计算题（只填最终答案）", "short_answer": "解决问题／阅读简答（写过程或理由）",
              "composition": "写作／复述"}
LEVELS = ("基础", "中等", "提高")
LEVEL_CODE = {"基础": "C", "中等": "B", "提高": "A"}
CODE_LEVEL = {v: k for k, v in LEVEL_CODE.items()}
COUNTS = (8, 12, 16)

# Per 12 questions. Maths: every type, a third 提高; 语文: reading-centred with one piece of writing.
BASE_QUOTAS = {
    "数学": {"types": {"choice": 3, "final_answer": 5, "short_answer": 4}, "levels": {"基础": 3, "中等": 5, "提高": 4}},
    "语文": {"types": {"choice": 3, "final_answer": 2, "short_answer": 6, "composition": 1}, "levels": {"基础": 3, "中等": 5, "提高": 4}},
}

LEVEL_RULES = {
    "数学": ("基础：一步计算或直接套用方法；中等：两步计算，或需要先判断用哪种方法；"
             "提高：三步及以上、含易错点（单位换算、近似数、比较大小、逆向思考）或生活情境的解决问题。"
             "中等和提高题题干里必须有具体数字，让学生真正去算，不能只问概念。"),
    "语文": ("基础：字词、句子的理解与积累；中等：概括内容、理解关键句的含义；"
             "提高：联系上下文或生活实际说出理由、比较、评价，或有要求的写作。"),
}


def quotas(subject: str, count: int) -> dict[str, dict[str, int]]:
    """Scale the per-12 quotas to ``count`` questions (largest remainders), every type and level at least 1."""
    base = BASE_QUOTAS[subject]
    out = {}
    for part in ("types", "levels"):
        raw = {k: v * count / 12 for k, v in base[part].items()}
        got = {k: max(1, int(v)) for k, v in raw.items()}
        while sum(got.values()) < count:
            k = max(raw, key=lambda k: raw[k] - got[k])
            got[k] += 1
        while sum(got.values()) > count:
            k = max((k for k in got if got[k] > 1), key=lambda k: got[k] - raw[k])
            got[k] -= 1
        out[part] = got
    return out


def prompt(subject: str, grade: int, textbook: str, lesson: dict[str, Any], want: dict[str, dict[str, int]],
           examples: list[str], weak: list[str], avoid: list[str]) -> str:
    """The question-only request. ``want`` is the quota still to fill (types and levels)."""
    n = sum(want["types"].values())
    types = "、".join(f"{TYPE_NAMES[t]} {c} 道" for t, c in want["types"].items() if c)
    levels = "、".join(f"{lv} {c} 道" for lv, c in want["levels"].items() if c)
    parts = [
        f"你是小学{grade}年级{subject}老师（{textbook}），要给周末补习班出随堂习题。学生基础参差不齐，题目要拉开层次，不能都是简单题。",
        f"本节课题：《{lesson.get('title') or ''}》；本节目标：{lesson.get('core_target') or ''}。",
    ]
    if lesson.get("content"):
        parts.append("本节讲解与例题（出题要紧扣这些内容，不超纲）：\n" + str(lesson["content"])[:2500])
    if lesson.get("material"):
        parts.append("本节阅读材料（阅读题必须基于这篇材料出题，参考答案要引用原文句子）：\n" + str(lesson["material"])[:4000])
    if weak:
        parts.append("班里近期错得多的知识点，可以多出几道：" + "、".join(weak))
    if examples:
        parts.append("本校老师审核通过的同类题，只作难度和风格参照，不要照抄：\n" + "\n".join(examples))
    if avoid:
        parts.append("下面这些题已经有了，不要重复：\n" + "\n".join("- " + a[:80] for a in avoid[:20]))
    parts += [
        f"一共出 {n} 道：{types}。难度分布：{levels}。",
        "难度标准：" + LEVEL_RULES[subject],
        "每道题都要写 level（基础/中等/提高）和 steps（解题步骤，每步一句；提高题至少 2 步）。",
        ("数学题的答案如果是数，必须给 expression：只用数字和 + - × ÷ ( ) 写出算出答案的算式，系统会用它验算；"
         "近似数要在题干写明保留几位小数。") if subject == "数学" else "阅读简答的参考答案要写出依据原文的要点。",
        "选择题 4 个选项、只有一个正确，干扰项要是学生常见的错误答案。",
        '只输出 JSON：{"items":[{"type":"choice|final_answer|short_answer|composition","level":"基础|中等|提高",'
        '"knowledge":"知识点","stem":"题干","options":["只有选择题有，4个"],"correctIndex":0,"answer":"最终答案（选择题写正确选项内容）",'
        '"expression":"数学算式，可空","steps":["第一步","第二步"],"explanation":"解析","hints":["方向提示","第一步提示","完整思路"]}]}',
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------- checks
_DIGIT = re.compile(r"[0-9０-９]")
_OPERATOR = re.compile(r"[×÷+\-=＝<>]")
_ROUND = re.compile(r"保留|近似|约|精确到|四舍五入")
_NUMBER = re.compile(r"^-?\d+(?:\.\d+)?$")


def _number_text(text: Any) -> str:
    s = str(text or "").strip().replace("，", "").replace(",", "")
    return re.sub(r"[^\d.\-]+$", "", re.sub(r"^[^\d\-]+", "", s))        # 约 3.5 米 -> 3.5


def _num(text: Any) -> Fraction | None:
    s = _number_text(text)
    return Fraction(s) if _NUMBER.match(s) else None


def evaluate(expression: Any) -> Fraction | None:
    """Exact value of an arithmetic expression (+ - × ÷ and brackets only), or None."""
    s = str(expression or "").strip().replace("×", "*").replace("÷", "/").replace("（", "(").replace("）", ")")
    s = s.split("=")[0].strip()
    if not s or not re.fullmatch(r"[\d.+\-*/() ]+", s):
        return None
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError:
        return None

    def walk(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return Fraction(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = walk(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if b == 0:
                raise ZeroDivisionError
            return a / b
        raise ValueError("not arithmetic")

    try:
        return walk(tree)
    except (ValueError, ZeroDivisionError, RecursionError):
        return None


def agrees(value: Fraction, answer: Fraction, stem: str, answer_text: str) -> bool:
    """The answer equals the computed value, or is it rounded as the stem asks."""
    if value == answer:
        return True
    if not _ROUND.search(stem + answer_text):
        return False
    s = _number_text(answer_text)
    digits = len(s.split(".")[1]) if "." in s else 0
    return round(value, digits) == answer


def _norm(text: str) -> str:
    """Same question apart from spacing and punctuation. Numbers count: a calculation with other numbers is new practice."""
    return re.sub(r"[\s，。,、：:；;！!？?（）()“”\"'　]+", "", str(text or ""))


def check(row: Any, subject: str) -> tuple[dict[str, Any] | None, str]:
    """A cleaned question, or None and the reason it was dropped."""
    if not isinstance(row, dict):
        return None, "格式不对"
    t, level = str(row.get("type") or ""), str(row.get("level") or "")
    stem = str(row.get("stem") or "").strip()
    if t not in TYPES or (t == "composition" and subject == "数学"):
        return None, "题型不对"
    if level not in LEVELS:
        return None, "没写难度"
    if len(stem) < 6 or len(stem) > 4000:
        return None, "题干太短或太长"
    steps = [str(s).strip() for s in row.get("steps") or [] if str(s).strip()] if isinstance(row.get("steps"), list) else []
    if level == "提高" and len(steps) < 2:
        return None, "提高题少于两步"
    if subject == "数学" and level != "基础" and not (_DIGIT.search(stem) or _OPERATOR.search(stem)):
        return None, "中等以上没有让学生计算"
    hints = [str(h).strip()[:300] for h in row.get("hints") or []] if isinstance(row.get("hints"), list) else []
    hints = hints if len(hints) == 3 and all(hints) else []
    out: dict[str, Any] = {"type": t, "level": level, "stem": stem, "knowledge": str(row.get("knowledge") or "")[:160],
                           "explanation": str(row.get("explanation") or "").strip()[:600], "steps": steps[:6], "hints": hints,
                           "verified": False}
    answer = str(row.get("answer") or "").strip()
    if t == "choice":
        try:
            opts = [str(o).strip() for o in row.get("options") or []][:4]
            ci = int(row.get("correctIndex"))
        except (TypeError, ValueError):
            return None, "选项不对"
        if len(opts) != 4 or not all(opts) or len(set(opts)) != 4 or not 0 <= ci < 4:
            return None, "选择题要 4 个不同的选项"
        out.update(options=opts, correctIndex=ci)
        answer = opts[ci]
    elif not answer and t != "composition":
        return None, "没有答案"
    out["answer"] = answer[:400]
    if subject == "数学" and t != "composition":
        target = _num(answer)
        if target is not None:
            value = evaluate(row.get("expression"))
            if value is None:
                if t != "choice" and level != "基础":
                    return None, "数学答案没有可验算的算式"      # computing questions must be checkable
            elif not agrees(value, target, stem, answer):
                return None, "验算不对"
            else:
                out["verified"] = True
                out["expression"] = str(row.get("expression")).strip()[:200]
    return out, ""


def select(rows: list[dict[str, Any]], want: dict[str, dict[str, int]], existing: list[str]) -> list[dict[str, Any]]:
    """Keep rows that fill the quotas, without near-duplicates (of each other or of ``existing``)."""
    seen = {_norm(s) for s in existing}
    left_t, left_l = dict(want["types"]), dict(want["levels"])
    out = []
    for r in sorted(rows, key=lambda r: (not r["verified"], LEVELS.index(r["level"]) * -1)):
        key = _norm(r["stem"])
        if key in seen or left_t.get(r["type"], 0) <= 0 or left_l.get(r["level"], 0) <= 0:
            continue
        seen.add(key)
        left_t[r["type"]] -= 1
        left_l[r["level"]] -= 1
        out.append(r)
    return out


def missing(want: dict[str, dict[str, int]], got: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out = {"types": dict(want["types"]), "levels": dict(want["levels"])}
    for r in got:
        out["types"][r["type"]] -= 1
        out["levels"][r["level"]] -= 1
    return {k: {x: max(0, c) for x, c in v.items()} for k, v in out.items()}


def reference_text(q: dict[str, Any]) -> str:
    """What the teacher sees as the answer key of a written question."""
    lines = [f"答案：{q['answer']}"] if q.get("answer") else []
    if q.get("expression"):
        lines.append(f"列式：{q['expression']}（系统已验算）")
    if q.get("steps"):
        lines.append("步骤：" + "；".join(q["steps"]))
    if q.get("explanation"):
        lines.append("解析：" + q["explanation"])
    return "\n".join(lines)[:4000]


__all__ = ["CODE_LEVEL", "COUNTS", "LEVELS", "LEVEL_CODE", "TYPES", "TYPE_NAMES", "agrees", "check", "evaluate", "missing",
           "prompt", "quotas", "reference_text", "select"]
