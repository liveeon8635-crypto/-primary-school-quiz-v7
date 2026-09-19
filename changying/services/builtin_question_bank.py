"""Built-in baseline question packs used to top up sparse teacher question banks.

The pack is deterministic and only materialized when a teacher explicitly creates
an activity. Read-only option endpoints may preview the available generated
inventory without writing to the database.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import json
from typing import Any

from sqlalchemy import select

from changying.services.grade5_chinese_question_bank import (
    CHINESE_G5_TEXTBOOK,
    grade5_chinese_specs,
)

PEP_CURRENT_TEXTBOOK = "人教版"
PEP_CURRENT_TEXTBOOK_LABEL = "人教版（当前最新版）"


def _dec(value: Any) -> Decimal:
    return Decimal(str(value))


def _fmt(value: Decimal | int | float | str) -> str:
    number = _dec(value)
    text = format(number.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _spec(
    *,
    unit: str,
    knowledge: str,
    text: str,
    answer: str,
    distractors: list[str],
    explanation: str,
    seed: int,
    semester: str = "上册",
) -> dict[str, Any]:
    answer = str(answer)
    unique: list[str] = []
    for value in distractors:
        value = str(value)
        if value != answer and value not in unique:
            unique.append(value)
    for fallback in ("0", "1", "10", "无法确定", "以上都不对"):
        if len(unique) >= 3:
            break
        if fallback != answer and fallback not in unique:
            unique.append(fallback)
    unique = unique[:3]
    correct_index = seed % 4
    options = list(unique)
    options.insert(correct_index, answer)
    return {
        "grade": 5,
        "subject": "数学",
        "textbook": "人教版",
        "semester": semester,
        "unit": unit,
        "knowledge": knowledge,
        "text": text,
        "options": options,
        "correct_index": correct_index,
        "explanation": explanation,
    }


def _numeric_distractors(answer: Decimal) -> list[str]:
    candidates = [
        answer * Decimal("10"),
        answer / Decimal("10"),
        answer + Decimal("1"),
        answer - Decimal("1"),
    ]
    return [_fmt(x) for x in candidates]


def _grade5_math_specs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    multiplication_integer = [
        ("2.4", 3), ("1.25", 4), ("0.36", 5), ("3.08", 6),
        ("4.5", 8), ("0.72", 9), ("6.04", 5), ("2.35", 7),
        ("0.48", 12), ("7.5", 4), ("1.06", 15), ("9.2", 3),
    ]
    for i, (a, b) in enumerate(multiplication_integer):
        answer = _dec(a) * _dec(b)
        rows.append(_spec(
            unit="第一单元 · 小数乘法",
            knowledge="小数乘整数",
            text=f"{a} × {b} = ?",
            answer=_fmt(answer),
            distractors=_numeric_distractors(answer),
            explanation=f"按整数乘法计算，再根据 {a} 的小数位数确定积的小数点，结果是 {_fmt(answer)}。",
            seed=i,
        ))

    multiplication_decimal = [
        ("1.2", "0.4"), ("2.5", "1.6"), ("0.75", "0.8"), ("3.4", "0.25"),
        ("1.25", "0.6"), ("4.08", "0.5"), ("0.36", "1.5"), ("2.4", "0.35"),
        ("5.2", "0.12"), ("0.48", "0.25"), ("6.25", "0.8"), ("1.44", "1.25"),
    ]
    for i, (a, b) in enumerate(multiplication_decimal):
        answer = _dec(a) * _dec(b)
        rows.append(_spec(
            unit="第一单元 · 小数乘法",
            knowledge="小数乘小数",
            text=f"{a} × {b} = ?",
            answer=_fmt(answer),
            distractors=_numeric_distractors(answer),
            explanation=f"两个因数共有的小数位数决定积的小数位数，结果是 {_fmt(answer)}。",
            seed=i + 1,
        ))

    approximate_pairs = [
        ("3.26", "1.7"), ("2.48", "3.6"), ("5.13", "0.9"), ("7.25", "1.4"),
        ("0.86", "4.7"), ("6.04", "2.3"), ("1.75", "3.8"), ("9.12", "0.6"),
        ("4.35", "2.2"), ("8.06", "1.5"),
    ]
    for i, (a, b) in enumerate(approximate_pairs):
        exact = _dec(a) * _dec(b)
        answer = exact.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        rows.append(_spec(
            unit="第一单元 · 小数乘法",
            knowledge="积的近似数",
            text=f"{a} × {b} 的积保留一位小数约是多少？",
            answer=_fmt(answer),
            distractors=[_fmt(answer + Decimal("0.1")), _fmt(answer - Decimal("0.1")), _fmt(exact)],
            explanation=f"先算得积 {_fmt(exact)}，再按四舍五入保留一位小数，约为 {_fmt(answer)}。",
            seed=i + 2,
        ))

    easy_multiply = [
        ("2.5", "4", "3.2"), ("1.25", "8", "0.6"), ("0.5", "2.4", "10"),
        ("4", "0.25", "7.5"), ("12.5", "0.8", "2"), ("2", "3.6", "0.5"),
        ("0.2", "5", "6.4"), ("1.5", "4", "2.5"), ("0.125", "8", "9"),
        ("2.5", "0.4", "11"),
    ]
    for i, (a, b, c) in enumerate(easy_multiply):
        answer = _dec(a) * _dec(b) * _dec(c)
        rows.append(_spec(
            unit="第一单元 · 小数乘法",
            knowledge="小数乘法简便运算",
            text=f"计算 {a} × {b} × {c}，结果是？",
            answer=_fmt(answer),
            distractors=_numeric_distractors(answer),
            explanation="可以利用乘法交换律、结合律，把容易凑整的因数先相乘。",
            seed=i + 3,
        ))

    movements = [
        ((2, 3), (2, 0)), ((4, 5), (-1, 0)), ((3, 2), (0, 3)), ((6, 4), (0, -2)),
        ((1, 5), (3, -1)), ((5, 2), (-2, 2)), ((7, 3), (-3, 1)), ((2, 6), (4, -2)),
        ((4, 4), (1, 2)), ((6, 6), (-2, -3)), ((3, 7), (2, -4)), ((8, 2), (-5, 3)),
    ]
    for i, ((x, y), (dx, dy)) in enumerate(movements):
        nx, ny = x + dx, y + dy
        horizontal = f"向{'右' if dx > 0 else '左'}{abs(dx)}格" if dx else ""
        vertical = f"向{'上' if dy > 0 else '下'}{abs(dy)}格" if dy else ""
        move = "，再".join(x for x in (horizontal, vertical) if x)
        answer = f"({nx},{ny})"
        rows.append(_spec(
            unit="第二单元 · 位置",
            knowledge="用数对确定位置",
            text=f"点A的位置是 ({x},{y})，{move} 后，新位置用数对表示为？",
            answer=answer,
            distractors=[f"({ny},{nx})", f"({x + dy},{y + dx})", f"({x - dx},{y - dy})"],
            explanation="数对的第一个数表示列，第二个数表示行；按移动方向分别改变对应坐标。",
            seed=i,
        ))

    division_integer = [
        ("8.4", 4), ("7.35", 5), ("12.6", 6), ("9.45", 9),
        ("4.32", 8), ("15.75", 7), ("6.48", 12), ("18.9", 9),
        ("5.04", 7), ("21.6", 8), ("3.96", 11), ("14.4", 16),
    ]
    for i, (a, b) in enumerate(division_integer):
        answer = _dec(a) / _dec(b)
        rows.append(_spec(
            unit="第三单元 · 小数除法",
            knowledge="除数是整数的小数除法",
            text=f"{a} ÷ {b} = ?",
            answer=_fmt(answer),
            distractors=_numeric_distractors(answer),
            explanation=f"按整数除法的方法计算，商的小数点与被除数的小数点对齐，结果是 {_fmt(answer)}。",
            seed=i + 1,
        ))

    division_decimal = [
        ("7.2", "0.6"), ("4.5", "0.9"), ("8.4", "1.2"), ("3.6", "0.24"),
        ("6.25", "0.5"), ("1.44", "0.12"), ("9.6", "0.8"), ("5.04", "0.7"),
        ("2.52", "0.18"), ("7.5", "0.25"), ("12.48", "1.6"), ("0.81", "0.09"),
    ]
    for i, (a, b) in enumerate(division_decimal):
        answer = _dec(a) / _dec(b)
        rows.append(_spec(
            unit="第三单元 · 小数除法",
            knowledge="一个数除以小数",
            text=f"{a} ÷ {b} = ?",
            answer=_fmt(answer),
            distractors=_numeric_distractors(answer),
            explanation="先把除数转化为整数，被除数的小数点同时向右移动相同位数，再计算。",
            seed=i + 2,
        ))

    quotient_approx = [
        (10, 3), (7, 6), (2, 7), (5, 9), (13, 6),
        (8, 3), (11, 7), (19, 8), (17, 6), (29, 12),
    ]
    for i, (a, b) in enumerate(quotient_approx):
        exact = _dec(a) / _dec(b)
        answer = exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        rows.append(_spec(
            unit="第三单元 · 小数除法",
            knowledge="商的近似数",
            text=f"{a} ÷ {b} 的商保留两位小数约是多少？",
            answer=f"{answer:.2f}",
            distractors=[f"{answer + Decimal('0.01'):.2f}", f"{answer - Decimal('0.01'):.2f}", f"{exact.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP):.1f}"],
            explanation="除到比需要保留的位数多一位，再按四舍五入取近似值。",
            seed=i + 3,
        ))

    repeating_sets = [
        ("1/3", ["1/2", "3/4", "1/5"]),
        ("2/3", ["1/4", "3/5", "7/10"]),
        ("1/6", ["1/8", "3/4", "9/20"]),
        ("5/6", ["3/8", "7/20", "9/10"]),
        ("2/11", ["1/2", "3/8", "7/25"]),
        ("4/9", ["1/5", "3/4", "7/20"]),
        ("5/12", ["1/4", "3/5", "7/8"]),
        ("7/15", ["1/2", "3/10", "9/20"]),
        ("8/27", ["1/8", "3/20", "7/10"]),
        ("11/30", ["1/4", "3/8", "9/20"]),
    ]
    for i, (answer, distractors) in enumerate(repeating_sets):
        rows.append(_spec(
            unit="第三单元 · 小数除法",
            knowledge="循环小数",
            text=f"在 {answer}、{distractors[0]}、{distractors[1]}、{distractors[2]} 中，哪个分数化成小数后是循环小数？",
            answer=answer,
            distractors=distractors,
            explanation="分数化成最简分数后，分母含有除2、5以外的质因数时，小数通常是循环小数。",
            seed=i,
        ))

    probability_sets = [
        (6, 2, "红球"), (3, 7, "蓝球"), (8, 1, "红球"), (4, 5, "蓝球"),
        (9, 3, "红球"), (2, 6, "蓝球"), (7, 4, "红球"), (5, 8, "蓝球"),
        (10, 2, "红球"), (3, 9, "蓝球"), (11, 5, "红球"), (4, 12, "蓝球"),
    ]
    for i, (red, blue, answer) in enumerate(probability_sets):
        rows.append(_spec(
            unit="第四单元 · 可能性",
            knowledge="可能性大小",
            text=f"盒子里有{red}个红球和{blue}个蓝球，任意摸出1个球，摸到哪种颜色的可能性更大？",
            answer=answer,
            distractors=["红球" if answer == "蓝球" else "蓝球", "一样大", "无法确定"],
            explanation="数量越多的颜色，被随机摸到的可能性越大。",
            seed=i + 1,
        ))

    algebra_prompts = [
        ("一个数是a，比它大8的数表示为？", "a+8", ["8a", "a-8", "8-a"]),
        ("每支笔x元，买5支需要多少元？", "5x", ["x+5", "x-5", "x÷5"]),
        ("长方形长a米、宽b米，周长表示为？", "2(a+b)", ["ab", "a+b", "2ab"]),
        ("小明今年a岁，爸爸比他大28岁，爸爸今年多少岁？", "a+28", ["28a", "a-28", "28-a"]),
        ("一辆车每小时行v千米，3小时行多少千米？", "3v", ["v+3", "v÷3", "v-3"]),
        ("一个正方形边长为a，周长表示为？", "4a", ["a²", "2a", "a+4"]),
        ("原有x本书，又买来12本，现在共有多少本？", "x+12", ["12x", "x-12", "12-x"]),
        ("每箱有a瓶饮料，6箱共有多少瓶？", "6a", ["a+6", "a÷6", "a-6"]),
        ("一个数x的3倍减2，表示为？", "3x-2", ["3(x-2)", "x-6", "2x-3"]),
        ("甲数是a，乙数比甲数少5，乙数表示为？", "a-5", ["5-a", "5a", "a+5"]),
    ]
    for i, (text, answer, distractors) in enumerate(algebra_prompts):
        rows.append(_spec(
            unit="第五单元 · 简易方程",
            knowledge="用字母表示数",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="把数量关系直接用字母和运算符号表示。",
            seed=i + 2,
        ))

    equation_sets = [
        (3, 2, 20, 6), (4, 5, 33, 7), (5, -3, 37, 8), (6, 4, 58, 9),
        (7, -5, 65, 10), (8, 3, 91, 11), (9, -4, 104, 12), (2, 7, 33, 13),
        (3, -6, 36, 14), (5, 10, 85, 15), (4, -8, 56, 16), (6, 1, 103, 17),
    ]
    for i, (a, b, c, solution) in enumerate(equation_sets):
        sign = "+" if b >= 0 else "-"
        text = f"解方程：{a}x {sign} {abs(b)} = {c}，x = ?"
        rows.append(_spec(
            unit="第五单元 · 简易方程",
            knowledge="解方程",
            text=text,
            answer=str(solution),
            distractors=[str(solution + 1), str(solution - 1), str(solution + 2)],
            explanation="先利用等式的性质消去常数项，再除以x前面的系数。",
            seed=i + 3,
        ))

    word_problems = [
        ("每本练习册8元，买了x本共花56元，x等于多少？", "7", ["6", "8", "9"]),
        ("一根绳子剪去12米后还剩28米，原长x米，x等于多少？", "40", ["16", "38", "42"]),
        ("5盒彩笔共有60支，每盒x支，x等于多少？", "12", ["10", "11", "15"]),
        ("一个数的4倍加3等于35，这个数是多少？", "8", ["7", "9", "10"]),
        ("小华有x张邮票，送出9张后还剩21张，x是多少？", "30", ["12", "28", "32"]),
        ("3个相同足球共花225元，每个x元，x是多少？", "75", ["72", "80", "225"]),
        ("某数的6倍减5等于49，这个数是多少？", "9", ["8", "10", "11"]),
        ("一辆车3小时行驶210千米，平均每小时x千米，x是多少？", "70", ["60", "65", "75"]),
        ("妈妈买4千克苹果共花36元，每千克x元，x是多少？", "9", ["8", "10", "12"]),
        ("一个长方形长x米、宽5米，周长30米，x是多少？", "10", ["5", "15", "20"]),
    ]
    for i, (text, answer, distractors) in enumerate(word_problems):
        rows.append(_spec(
            unit="第五单元 · 简易方程",
            knowledge="实际问题与方程",
            text=text,
            answer=answer,
            distractors=distractors,
            explanation="先根据题意列出等量关系和方程，再利用等式的性质求解。",
            seed=i,
        ))

    parallelograms = [(6,4),(8,5),(12,7),(9,6),(15,8),(11,9),(20,4),(14,6),(18,5),(13,10)]
    for i, (base, height) in enumerate(parallelograms):
        answer = base * height
        rows.append(_spec(
            unit="第六单元 · 多边形的面积",
            knowledge="平行四边形的面积",
            text=f"一个平行四边形的底是{base}厘米，高是{height}厘米，面积是多少平方厘米？",
            answer=str(answer),
            distractors=[str(base + height), str(answer // 2), str(2 * (base + height))],
            explanation=f"平行四边形面积=底×高={base}×{height}={answer}平方厘米。",
            seed=i + 1,
        ))

    triangles = [(8,6),(10,7),(12,5),(14,9),(16,8),(9,4),(15,6),(18,7),(20,9),(11,10)]
    for i, (base, height) in enumerate(triangles):
        answer = base * height // 2
        rows.append(_spec(
            unit="第六单元 · 多边形的面积",
            knowledge="三角形的面积",
            text=f"一个三角形的底是{base}厘米，高是{height}厘米，面积是多少平方厘米？",
            answer=str(answer),
            distractors=[str(base * height), str(base + height), str(2 * (base + height))],
            explanation=f"三角形面积=底×高÷2={base}×{height}÷2={answer}平方厘米。",
            seed=i + 2,
        ))

    trapezoids = [(6,10,4),(8,12,5),(7,13,6),(9,15,4),(10,16,7),(5,11,8),(12,18,5),(14,20,6),(8,18,9),(11,17,7)]
    for i, (a, b, height) in enumerate(trapezoids):
        answer = (a + b) * height // 2
        rows.append(_spec(
            unit="第六单元 · 多边形的面积",
            knowledge="梯形的面积",
            text=f"一个梯形的上底是{a}厘米，下底是{b}厘米，高是{height}厘米，面积是多少平方厘米？",
            answer=str(answer),
            distractors=[str((a + b) * height), str(a * b), str((a + b) * 2)],
            explanation=f"梯形面积=(上底+下底)×高÷2=({a}+{b})×{height}÷2={answer}平方厘米。",
            seed=i + 3,
        ))

    composite = [(10,8,4,3),(12,9,5,2),(15,10,6,4),(14,12,4,5),(18,9,7,3),(16,11,5,5),(20,12,8,4),(13,10,3,6),(17,14,6,5),(22,10,7,4)]
    for i, (length, width, cut_l, cut_w) in enumerate(composite):
        answer = length * width - cut_l * cut_w
        rows.append(_spec(
            unit="第六单元 · 多边形的面积",
            knowledge="组合图形的面积",
            text=f"一个长{length}厘米、宽{width}厘米的长方形，剪去一个长{cut_l}厘米、宽{cut_w}厘米的小长方形，剩余面积是多少平方厘米？",
            answer=str(answer),
            distractors=[str(length * width), str(cut_l * cut_w), str(length * width + cut_l * cut_w)],
            explanation="组合图形可用大图形面积减去被剪去的小图形面积。",
            seed=i,
        ))

    tree_sets = [
        (100,10,"两端都栽",11), (120,10,"两端都栽",13), (90,9,"两端都栽",11),
        (80,8,"只栽一端",10), (100,5,"只栽一端",20), (72,6,"只栽一端",12),
        (60,5,"两端都不栽",11), (84,7,"两端都不栽",11), (100,10,"两端都不栽",9),
        (90,9,"围成一圈",10), (120,12,"围成一圈",10), (150,15,"围成一圈",10),
    ]
    for i, (length, spacing, kind, answer) in enumerate(tree_sets):
        if kind == "围成一圈":
            text = f"在周长{length}米的圆形场地四周每隔{spacing}米栽一棵树，一共栽多少棵？"
        else:
            text = f"在一条长{length}米的小路一侧每隔{spacing}米栽一棵树，{kind}，一共栽多少棵？"
        rows.append(_spec(
            unit="第七单元 · 数学广角——植树问题",
            knowledge="植树问题",
            text=text,
            answer=str(answer),
            distractors=[str(answer + 1), str(max(1, answer - 1)), str(answer + 2)],
            explanation="先求间隔数，再根据两端都栽、只栽一端、两端不栽或封闭图形的情况确定棵数。",
            seed=i + 1,
        ))

    return rows


def built_in_subjects(grade: int) -> list[str]:
    return ["数学", "语文"] if int(grade) == 5 else []


def built_in_textbooks(grade: int, subject: str) -> list[str]:
    """Return the currently supported PEP textbook line for each subject."""

    if int(grade) != 5:
        return []
    selected_subject = (subject or "").strip()
    if selected_subject == "数学":
        return [PEP_CURRENT_TEXTBOOK]
    if selected_subject == "语文":
        return [CHINESE_G5_TEXTBOOK]
    return []


def built_in_question_specs(
    grade: int,
    subject: str,
    textbook: str = "",
) -> list[dict[str, Any]]:
    requested_textbook = (textbook or "").strip()
    selected_subject = (subject or "").strip()
    if int(grade) != 5:
        return []
    if selected_subject == "数学":
        if not requested_textbook or requested_textbook == PEP_CURRENT_TEXTBOOK:
            return _grade5_math_specs()
        return []
    if selected_subject == "语文":
        if not requested_textbook or requested_textbook == CHINESE_G5_TEXTBOOK:
            return grade5_chinese_specs()
        return []
    return []


def potential_question_catalog(
    existing_rows: list[Any],
    *,
    grade: int,
    subject: str,
    textbook: str = "",
) -> tuple[list[dict[str, Any]], int]:
    """Return version-matched existing + built-in inventory without writing."""
    selected_textbook = (textbook or "").strip()
    counts: dict[tuple[str, str], int] = defaultdict(int)
    existing_keys: set[tuple[str, str]] = set()
    total = 0
    for row in existing_rows:
        if selected_textbook and str(row.textbook or "").strip() != selected_textbook:
            continue
        try:
            options = json.loads(row.options_json or "[]")
            valid = (
                isinstance(options, list)
                and len(options) >= 2
                and 0 <= int(row.correct_index) < len(options)
            )
        except Exception:
            valid = False
        if not valid:
            continue
        unit = str(row.unit or "").strip()
        knowledge = str(row.knowledge or "").strip()
        if knowledge:
            counts[(unit, knowledge)] += 1
        existing_keys.add((str(row.text or "").strip(), knowledge))
        total += 1

    for spec in built_in_question_specs(grade, subject, selected_textbook):
        key = (str(spec["text"]).strip(), str(spec["knowledge"]).strip())
        if key in existing_keys:
            continue
        counts[(str(spec["unit"]), str(spec["knowledge"]))] += 1
        total += 1

    modules = [
        {"unit": unit, "knowledge": knowledge, "count": count}
        for (unit, knowledge), count in sorted(counts.items())
    ]
    return modules, total


def ensure_built_in_questions(
    db: Any,
    Question: Any,
    *,
    school_id: int,
    creator_id: int,
    grade: int,
    subject: str,
    textbook: str = "",
) -> int:
    """Materialize only missing built-in questions for the selected textbook."""
    selected_textbook = (textbook or "").strip()
    specs = built_in_question_specs(grade, subject, selected_textbook)
    if not specs:
        return 0

    existing_statement = select(Question).where(
        Question.school_id == school_id,
        Question.grade == int(grade),
        Question.subject == (subject or "").strip(),
    )
    if selected_textbook:
        existing_statement = existing_statement.where(
            Question.textbook == selected_textbook
        )
    existing = list(db.scalars(existing_statement).all())
    keys = {
        (str(row.text or "").strip(), str(row.knowledge or "").strip())
        for row in existing
    }
    added = 0
    for spec in specs:
        key = (str(spec["text"]).strip(), str(spec["knowledge"]).strip())
        if key in keys:
            continue
        db.add(
            Question(
                school_id=school_id,
                grade=int(spec["grade"]),
                subject=str(spec["subject"]),
                textbook=str(spec["textbook"]),
                semester=str(spec["semester"]),
                unit=str(spec["unit"]),
                knowledge=str(spec["knowledge"]),
                text=str(spec["text"]),
                options_json=json.dumps(spec["options"], ensure_ascii=False),
                correct_index=int(spec["correct_index"]),
                explanation=str(spec["explanation"]),
                creator_id=creator_id,
            )
        )
        keys.add(key)
        added += 1
    if added:
        db.flush()
    return added


__all__ = [
    "built_in_question_specs",
    "built_in_subjects",
    "built_in_textbooks",
    "ensure_built_in_questions",
    "potential_question_catalog",
]
