"""Supplemental Grade 5 Math question packs for multiple textbook editions.

These packs are deterministic baseline questions for the teacher's automatic
test/practice workflow. They are edition-scoped and mirror the broad unit
structure of each textbook so different editions are never mixed in one paper.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from typing import Any


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
    textbook: str,
    unit: str,
    knowledge: str,
    text: str,
    answer: str,
    distractors: list[str],
    explanation: str,
    seed: int,
) -> dict[str, Any]:
    answer = str(answer)
    unique: list[str] = []
    for item in distractors:
        item = str(item)
        if item != answer and item not in unique:
            unique.append(item)
    for fallback in ("0", "1", "10", "无法确定", "以上都不对"):
        if len(unique) >= 3:
            break
        if fallback != answer and fallback not in unique:
            unique.append(fallback)
    correct_index = seed % 4
    options = unique[:3]
    options.insert(correct_index, answer)
    return {
        "grade": 5,
        "subject": "数学",
        "textbook": textbook,
        "semester": "上册",
        "unit": unit,
        "knowledge": knowledge,
        "text": text,
        "options": options,
        "correct_index": correct_index,
        "explanation": explanation,
    }


def _num_distractors(answer: Decimal) -> list[str]:
    return [
        _fmt(answer + Decimal("1")),
        _fmt(answer - Decimal("1")),
        _fmt(answer * Decimal("10")),
    ]


def _decimal_multiplication(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    integer_pairs = [
        ("2.4", 3), ("1.25", 4), ("0.36", 5), ("3.08", 6),
        ("4.5", 8), ("0.72", 9), ("6.04", 5), ("2.35", 7),
        ("0.48", 12), ("7.5", 4), ("1.06", 15), ("9.2", 3),
    ]
    for i, (a, b) in enumerate(integer_pairs):
        ans = _dec(a) * _dec(b)
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="小数乘整数",
            text=f"{a} × {b} = ?", answer=_fmt(ans),
            distractors=_num_distractors(ans),
            explanation="按整数乘法计算，再根据小数位数确定积的小数点。",
            seed=i,
        ))

    decimal_pairs = [
        ("1.2", "0.4"), ("2.5", "1.6"), ("0.75", "0.8"), ("3.4", "0.25"),
        ("1.25", "0.6"), ("4.08", "0.5"), ("0.36", "1.5"), ("2.4", "0.35"),
        ("5.2", "0.12"), ("0.48", "0.25"), ("6.25", "0.8"), ("1.44", "1.25"),
    ]
    for i, (a, b) in enumerate(decimal_pairs):
        ans = _dec(a) * _dec(b)
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="小数乘小数",
            text=f"{a} × {b} = ?", answer=_fmt(ans),
            distractors=_num_distractors(ans),
            explanation="两个因数的小数位数之和决定积的小数位数。",
            seed=i + 1,
        ))
    return rows


def _decimal_division(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pairs = [
        ("8.4", "4"), ("7.35", "5"), ("12.6", "6"), ("9.45", "9"),
        ("4.32", "8"), ("15.75", "7"), ("6.48", "12"), ("18.9", "9"),
        ("7.2", "0.6"), ("4.5", "0.9"), ("8.4", "1.2"), ("3.6", "0.24"),
        ("6.25", "0.5"), ("1.44", "0.12"), ("9.6", "0.8"), ("5.04", "0.7"),
        ("2.52", "0.18"), ("7.5", "0.25"), ("12.48", "1.6"), ("0.81", "0.09"),
        ("10.5", "0.5"), ("3.24", "0.6"), ("6.6", "1.1"), ("2.88", "0.16"),
    ]
    for i, (a, b) in enumerate(pairs):
        ans = _dec(a) / _dec(b)
        knowledge = "除数是整数的小数除法" if "." not in b else "一个数除以小数"
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge=knowledge,
            text=f"{a} ÷ {b} = ?", answer=_fmt(ans),
            distractors=_num_distractors(ans),
            explanation="除数是小数时，先把除数转化为整数，再按小数除法计算。",
            seed=i,
        ))

    approx = [(10, 3), (7, 6), (2, 7), (5, 9), (13, 6), (8, 3), (11, 7), (19, 8)]
    for i, (a, b) in enumerate(approx):
        exact = _dec(a) / _dec(b)
        ans = exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="商的近似数",
            text=f"{a} ÷ {b} 的商保留两位小数约是多少？",
            answer=f"{ans:.2f}",
            distractors=[
                f"{ans + Decimal('0.01'):.2f}",
                f"{ans - Decimal('0.01'):.2f}",
                f"{exact.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP):.1f}",
            ],
            explanation="除到比保留位数多一位，再四舍五入。",
            seed=i + 2,
        ))
    return rows


def _areas(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    parallelograms = [(6,4),(8,5),(12,7),(9,6),(15,8),(11,9),(20,4),(14,6)]
    for i, (base, height) in enumerate(parallelograms):
        ans = base * height
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="平行四边形的面积",
            text=f"平行四边形底{base}厘米，高{height}厘米，面积是多少平方厘米？",
            answer=str(ans), distractors=[str(ans//2), str(base+height), str(2*(base+height))],
            explanation="平行四边形面积=底×高。",
            seed=i,
        ))
    triangles = [(8,6),(10,7),(12,5),(14,9),(16,8),(9,4),(15,6),(18,7)]
    for i, (base, height) in enumerate(triangles):
        ans = base * height // 2
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="三角形的面积",
            text=f"三角形底{base}厘米，高{height}厘米，面积是多少平方厘米？",
            answer=str(ans), distractors=[str(base*height), str(base+height), str(ans+base)],
            explanation="三角形面积=底×高÷2。",
            seed=i + 1,
        ))
    trapezoids = [(6,10,4),(8,12,5),(7,13,6),(9,15,4),(10,16,7),(5,11,8),(12,18,5),(14,20,6)]
    for i, (a, b, h) in enumerate(trapezoids):
        ans = (a + b) * h // 2
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="梯形的面积",
            text=f"梯形上底{a}厘米，下底{b}厘米，高{h}厘米，面积是多少平方厘米？",
            answer=str(ans), distractors=[str((a+b)*h), str(a*b), str(a+b+h)],
            explanation="梯形面积=(上底+下底)×高÷2。",
            seed=i + 2,
        ))
    composite = [(10,8,4,3),(12,9,5,2),(15,10,6,4),(14,12,4,5),(18,9,7,3),(16,11,5,5),(20,12,8,4),(13,10,3,6)]
    for i, (length, width, cut_l, cut_w) in enumerate(composite):
        ans = length * width - cut_l * cut_w
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="组合图形的面积",
            text=f"长{length}厘米、宽{width}厘米的长方形剪去一个{cut_l}×{cut_w}厘米的小长方形，剩余面积是多少平方厘米？",
            answer=str(ans),
            distractors=[str(length*width), str(cut_l*cut_w), str(length*width+cut_l*cut_w)],
            explanation="组合图形可用整体面积减去挖去部分面积。",
            seed=i + 3,
        ))
    return rows


def _probability(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    data = [(6,2),(3,7),(8,1),(4,5),(9,3),(2,6),(7,4),(5,8),(10,2),(3,9)]
    for i, (red, blue) in enumerate(data):
        ans = "红球" if red > blue else "蓝球"
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="可能性大小",
            text=f"盒中有{red}个红球和{blue}个蓝球，随机摸1个，摸到哪种颜色的可能性更大？",
            answer=ans,
            distractors=["蓝球" if ans=="红球" else "红球", "一样大", "无法确定"],
            explanation="数量较多的颜色被摸到的可能性更大。",
            seed=i,
        ))
    return rows


def _equations(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    eqs = [
        (3,2,20,6),(4,5,33,7),(5,-3,37,8),(6,4,58,9),(7,-5,65,10),
        (8,3,91,11),(9,-4,104,12),(2,7,33,13),(3,-6,36,14),(5,10,85,15),
        (4,-8,56,16),(6,1,103,17),
    ]
    for i, (a,b,c,sol) in enumerate(eqs):
        sign = "+" if b >= 0 else "-"
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="解方程",
            text=f"解方程：{a}x {sign} {abs(b)} = {c}，x = ?",
            answer=str(sol), distractors=[str(sol+1), str(sol-1), str(sol+2)],
            explanation="利用等式的性质先消去常数项，再除以未知数前面的系数。",
            seed=i,
        ))
    letters = [
        ("每本练习册a元，买5本需要多少元？","5a",["a+5","a-5","a÷5"]),
        ("一个数是x，比它大8的数怎样表示？","x+8",["8x","x-8","8-x"]),
        ("长方形长a米、宽b米，周长怎样表示？","2(a+b)",["ab","a+b","2ab"]),
        ("每小时行v千米，3小时行多少千米？","3v",["v+3","v÷3","v-3"]),
        ("正方形边长a厘米，周长是多少？","4a",["a²","2a","a+4"]),
        ("原有x本书，又买12本，共有多少本？","x+12",["12x","x-12","12-x"]),
        ("每箱a瓶饮料，6箱共多少瓶？","6a",["a+6","a÷6","a-6"]),
        ("一个数x的3倍减2怎样表示？","3x-2",["3(x-2)","x-6","2x-3"]),
    ]
    for i, (text,ans,ds) in enumerate(letters):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="用字母表示数",
            text=text, answer=ans, distractors=ds,
            explanation="根据数量关系直接用字母式表示。",
            seed=i+1,
        ))
    return rows


def _factors(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    multiple_cases = [
        (6,24,[25,26,29]),(7,35,[36,37,39]),(8,40,[41,42,43]),(9,54,[52,53,55]),
        (4,28,[26,27,29]),(5,45,[44,46,47]),(3,33,[31,32,34]),(12,60,[58,59,61]),
    ]
    for i, (base,ans,ds) in enumerate(multiple_cases):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="倍数与因数",
            text=f"下面哪个数是{base}的倍数？",
            answer=str(ans), distractors=[str(x) for x in ds],
            explanation=f"能被{base}整除的数是{base}的倍数。",
            seed=i,
        ))
    factor_cases = [
        (24,6,[5,7,11]),(36,9,[5,7,11]),(48,8,[5,7,11]),(30,10,[7,11,13]),
        (42,7,[5,8,11]),(56,14,[9,11,13]),(63,9,[5,8,10]),(72,12,[5,7,11]),
    ]
    for i, (n,ans,ds) in enumerate(factor_cases):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="找因数",
            text=f"下面哪个数是{n}的因数？",
            answer=str(ans), distractors=[str(x) for x in ds],
            explanation=f"如果{n}能被一个数整除，这个数就是{n}的因数。",
            seed=i+1,
        ))
    primes = [(11,[9,12,15]),(13,[10,14,21]),(17,[12,15,18]),(19,[14,16,22]),(23,[18,20,25]),(29,[21,27,33]),(31,[25,27,35]),(37,[32,34,39])]
    for i,(ans,ds) in enumerate(primes):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="质数与合数",
            text="下面哪个数是质数？", answer=str(ans),
            distractors=[str(x) for x in ds],
            explanation="质数只有1和它本身两个因数。",
            seed=i+2,
        ))
    return rows


def _fractions(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    equivalent = [
        ("1/2","2/4",["2/3","3/5","4/5"]),("2/3","4/6",["3/4","4/5","5/6"]),
        ("3/5","6/10",["4/7","5/8","7/10"]),("3/4","6/8",["5/6","7/9","8/10"]),
        ("2/7","4/14",["3/8","5/14","6/14"]),("5/6","10/12",["8/12","9/12","11/12"]),
        ("4/9","8/18",["6/18","7/18","10/18"]),("5/8","10/16",["9/16","11/16","12/16"]),
    ]
    for i,(base,ans,ds) in enumerate(equivalent):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="分数基本性质",
            text=f"下面哪个分数与{base}相等？", answer=ans, distractors=ds,
            explanation="分子和分母同时乘或除以相同的非零数，分数大小不变。",
            seed=i,
        ))
    compare = [
        ("2/3","3/5","2/3"),("3/4","5/8","3/4"),("5/6","7/9","5/6"),("4/7","3/5","3/5"),
        ("7/10","2/3","7/10"),("5/12","3/8","5/12"),("8/9","5/6","8/9"),("7/15","1/2","1/2"),
    ]
    for i,(a,b,ans) in enumerate(compare):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="分数大小比较",
            text=f"{a} 与 {b} 比较，较大的是？", answer=ans,
            distractors=[b if ans==a else a, "一样大", "无法确定"],
            explanation="可以通分或化成小数后比较。",
            seed=i+1,
        ))
    gcd_lcm = [(12,18,6,36),(8,12,4,24),(15,20,5,60),(9,12,3,36)]
    for i,(a,b,g,l) in enumerate(gcd_lcm):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="最大公因数和最小公倍数",
            text=f"{a}和{b}的最大公因数是多少？", answer=str(g),
            distractors=[str(l),str(g+1),str(max(1,g-1))],
            explanation="列出两个数的公因数，最大的一个就是最大公因数。",
            seed=i+2,
        ))
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="最大公因数和最小公倍数",
            text=f"{a}和{b}的最小公倍数是多少？", answer=str(l),
            distractors=[str(g),str(l+a),str(l-b)],
            explanation="列出两个数的公倍数，最小的正公倍数就是最小公倍数。",
            seed=i+3,
        ))
    return rows


def _transformations(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    shifts = [
        ((2,3),(3,0)),((4,5),(-2,0)),((3,2),(0,4)),((6,4),(0,-3)),
        ((1,5),(2,-1)),((5,2),(-3,2)),((7,3),(-2,1)),((2,6),(4,-2)),
    ]
    for i,((x,y),(dx,dy)) in enumerate(shifts):
        nx,ny=x+dx,y+dy
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="平移",
            text=f"点A({x},{y})平移到({nx},{ny})，横向和纵向分别改变多少？",
            answer=f"({dx},{dy})",
            distractors=[f"({dy},{dx})",f"({-dx},{-dy})",f"({dx+1},{dy})"],
            explanation="比较平移前后横坐标和纵坐标的变化量。",
            seed=i,
        ))
    symmetry = [
        ("等腰三角形",1,["0","2","3"]),("正方形",4,["1","2","3"]),
        ("长方形",2,["1","3","4"]),("等边三角形",3,["1","2","4"]),
        ("圆",0,["1","2","4"]),("一般平行四边形",0,["1","2","4"]),
        ("菱形",2,["1","3","4"]),("正五边形",5,["1","2","4"]),
    ]
    for i,(shape,ans,ds) in enumerate(symmetry):
        answer = "无数" if shape=="圆" else str(ans)
        distractors = ds if shape!="圆" else ["1","2","4"]
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="轴对称",
            text=f"{shape}有多少条对称轴？", answer=answer, distractors=distractors,
            explanation="对称轴能使图形沿该直线折叠后两侧完全重合。",
            seed=i+1,
        ))
    return rows


def _negative_numbers(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cases = [
        ("零上5℃记作+5℃，零下3℃记作什么？","-3℃",["+3℃","0℃","-5℃"]),
        ("海拔高于海平面20米记作+20米，低于海平面8米记作什么？","-8米",["+8米","0米","-20米"]),
        ("收入50元记作+50元，支出30元记作什么？","-30元",["+30元","0元","-50元"]),
        ("向东走6米记作+6米，向西走4米记作什么？","-4米",["+4米","0米","-6米"]),
    ]
    for i in range(3):
        for j,(text,ans,ds) in enumerate(cases):
            suffix="" if i==0 else f"（情境{i+1}）"
            rows.append(_spec(
                textbook=textbook, unit=unit, knowledge="负数的初步认识",
                text=text+suffix, answer=ans, distractors=ds,
                explanation="相反意义的量可以分别用正数和负数表示。",
                seed=i*4+j,
            ))
    return rows


def _decimal_concepts(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    place = [
        ("3.47中，4在什么数位？","十分位",["个位","百分位","千分位"]),
        ("5.206中，2在什么数位？","十分位",["个位","百分位","千分位"]),
        ("0.684中，8在什么数位？","百分位",["十分位","个位","千分位"]),
        ("12.305中，5在什么数位？","千分位",["个位","十分位","百分位"]),
        ("7.09中，9在什么数位？","百分位",["十分位","个位","千分位"]),
        ("0.125中，1在什么数位？","十分位",["个位","百分位","千分位"]),
    ]
    for i,(text,ans,ds) in enumerate(place):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="小数的意义和数位",
            text=text, answer=ans, distractors=ds,
            explanation="小数点右边依次是十分位、百分位、千分位……",
            seed=i,
        ))
    equivalent = [
        ("0.5","0.50",["0.05","5.0","0.005"]),("1.20","1.2",["1.02","12.0","0.12"]),
        ("3.400","3.4",["34","0.34","3.04"]),("0.080","0.08",["0.8","0.008","8.0"]),
        ("6.70","6.7",["67","0.67","6.07"]),("2.300","2.3",["23","0.23","2.03"]),
    ]
    for i,(base,ans,ds) in enumerate(equivalent):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="小数的性质",
            text=f"下面哪个数与{base}大小相等？", answer=ans, distractors=ds,
            explanation="小数末尾添上0或去掉0，小数大小不变。",
            seed=i+1,
        ))
    compare = [
        ("3.45","3.405","3.45"),("0.86","0.806","0.86"),("5.07","5.7","5.7"),("2.099","2.1","2.1"),
        ("7.50","7.5","一样大"),("0.39","0.4","0.4"),("12.08","12.8","12.8"),("6.006","6.06","6.06"),
    ]
    for i,(a,b,ans) in enumerate(compare):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="小数大小比较",
            text=f"{a} 与 {b} 比较，较大的是？", answer=ans,
            distractors=[a,b,"无法确定"],
            explanation="先比较整数部分，再从十分位开始逐位比较。",
            seed=i+2,
        ))
    return rows


def _decimal_add_sub(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cases = [
        ("3.45","+","2.7"),("6.8","-","2.35"),("1.25","+","4.08"),("9.6","-","3.47"),
        ("0.75","+","2.36"),("8.04","-","1.9"),("5.5","+","3.28"),("7.32","-","4.16"),
        ("12.6","+","0.85"),("10","-","3.75"),("4.09","+","5.91"),("6.2","-","0.68"),
        ("2.375","+","1.625"),("9.08","-","2.995"),("0.84","+","0.76"),("15.5","-","8.25"),
    ]
    for i,(a,op,b) in enumerate(cases):
        ans = _dec(a)+_dec(b) if op=="+" else _dec(a)-_dec(b)
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="小数加法和减法",
            text=f"{a} {op} {b} = ?", answer=_fmt(ans),
            distractors=_num_distractors(ans),
            explanation="小数加减法要把小数点对齐，再按整数加减法计算。",
            seed=i,
        ))
    return rows


def _statistics(textbook: str, unit: str, knowledge: str = "统计图表") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cases = [
        ([12,15,18,20],"第四项",20),([8,11,14,17],"增长最多",3),
        ([25,22,28,30],"最大值",30),([16,19,21,24],"第二项",19),
        ([30,27,25,20],"第一项",30),([5,9,12,16],"第四项",16),
        ([18,21,19,23],"最大值",23),([10,14,13,17],"第二项",14),
        ([7,8,11,15],"第四项",15),([40,35,32,28],"第一项",40),
    ]
    for i,(vals,label,ans) in enumerate(cases):
        if label=="增长最多":
            text=f"某组四次测量数据为{vals}，从第几次到下一次增长最多？"
            answer="第3次" if vals[3]-vals[2] >= max(vals[1]-vals[0], vals[2]-vals[1]) else "第1次"
            ds=["第1次","第2次","第4次"]
        else:
            text=f"统计图对应四个时点的数据为{vals}，{label}的数据是多少？"
            answer=str(ans); ds=[str(vals[0]),str(vals[1]),str(vals[2])]
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge=knowledge,
            text=text, answer=answer, distractors=ds,
            explanation="根据统计图表中的数据直接读取或比较。",
            seed=i,
        ))
    return rows


def _direction(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cases = [
        ("正东","0°"),("正北","90°"),("正西","180°"),("正南","270°"),
        ("东北方向","45°"),("西北方向","135°"),("西南方向","225°"),("东南方向","315°"),
    ]
    for i,(direction,ans) in enumerate(cases):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="方向与路线",
            text=f"以正东方向为0°，逆时针计角，{direction}大约对应多少度？",
            answer=ans, distractors=["45°","90°","180°"],
            explanation="方向可以用角度表示，并结合路线图描述运动路线。",
            seed=i,
        ))
    route_cases = [
        ("先向东3格再向北2格","东北"),("先向西4格再向北1格","西北"),
        ("先向南2格再向东5格","东南"),("先向南3格再向西2格","西南"),
    ]
    for i,(route,ans) in enumerate(route_cases):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="认识路线图",
            text=f"从起点{route}，终点大致位于起点的哪个方向？",
            answer=ans, distractors=["东北","西北","东南","西南"],
            explanation="根据东西方向和南北方向的合成判断终点方位。",
            seed=i+1,
        ))
    return rows


def _mixed_operations(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    expressions = [
        ("12.5 + 7.5 × 2", Decimal("27.5")),
        ("(8.4 + 3.6) ÷ 4", Decimal("3")),
        ("20 - 3.5 × 4", Decimal("6")),
        ("6.4 ÷ 0.8 + 5", Decimal("13")),
        ("18 ÷ (3 + 3)", Decimal("3")),
        ("5.5 + 2.5 × 3", Decimal("13")),
        ("(15 - 7.5) ÷ 2.5", Decimal("3")),
        ("4.8 × 2 + 6.4", Decimal("16")),
        ("30 ÷ 5 - 1.2", Decimal("4.8")),
        ("9.6 ÷ 1.2 × 0.5", Decimal("4")),
        ("(2.5 + 7.5) × 1.2", Decimal("12")),
        ("24 - 4 × 3.5", Decimal("10")),
    ]
    for i,(expr,ans) in enumerate(expressions):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="四则混合运算",
            text=f"计算：{expr} = ?", answer=_fmt(ans),
            distractors=_num_distractors(ans),
            explanation="先算括号，再乘除，最后加减；同级运算从左到右。",
            seed=i,
        ))
    return rows


def _land_area(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cases = [
        ("1公顷等于多少平方米？","10000",["100","1000","100000"]),
        ("3公顷等于多少平方米？","30000",["3000","300000","300"]),
        ("1平方千米等于多少公顷？","100",["10","1000","10000"]),
        ("2平方千米等于多少公顷？","200",["20","2000","20000"]),
        ("50000平方米等于多少公顷？","5",["50","0.5","500"]),
        ("800公顷等于多少平方千米？","8",["80","0.8","8000"]),
        ("250000平方米等于多少公顷？","25",["2.5","250","2500"]),
        ("6平方千米等于多少平方米？","6000000",["60000","600000","60000000"]),
        ("12公顷等于多少平方米？","120000",["1200","12000","1200000"]),
        ("900000平方米等于多少公顷？","90",["9","900","9000"]),
    ]
    for i,(text,ans,ds) in enumerate(cases):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="土地面积单位",
            text=text, answer=ans, distractors=ds,
            explanation="1公顷=10000平方米，1平方千米=100公顷=1000000平方米。",
            seed=i,
        ))
    return rows


def _strategy(textbook: str, unit: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cases = [
        ("用1元和2元硬币组成5元，共有几种不同搭配？","3",["2","4","5"]),
        ("长方形周长12厘米，长和宽取整厘米且长≥宽，有几种不同长方形？","3",["2","4","5"]),
        ("从A、B、C三件上衣中选1件，从甲、乙两条裤子中选1条，共有几种搭配？","6",["3","5","8"]),
        ("把10分成两个正整数之和，不计顺序，共有几种分法？","5",["4","6","9"]),
        ("3种饮料和4种点心各选1种，共有几种搭配？","12",["7","10","16"]),
        ("从1、2、3、4中选两个不同数字组成两位数，共有几个？","12",["6","8","16"]),
        ("有红、黄、蓝3面旗，选2面不同颜色排列，共有几种？","6",["3","4","9"]),
        ("四个人两两握手一次，共握手多少次？","6",["4","8","12"]),
        ("从5本不同书中选2本，共有几种选法？","10",["5","8","20"]),
        ("用2、5、10元纸币各一张，任选若干张，可组成多少种不同非零金额？","7",["3","6","8"]),
    ]
    for i,(text,ans,ds) in enumerate(cases):
        rows.append(_spec(
            textbook=textbook, unit=unit, knowledge="解决问题的策略",
            text=text, answer=ans, distractors=ds,
            explanation="按一定顺序一一列举，可以做到不重复、不遗漏。",
            seed=i,
        ))
    return rows


def _line_chart(textbook: str, unit: str) -> list[dict[str, Any]]:
    return _statistics(textbook, unit, knowledge="折线统计图")


def beishida_grade5_math_specs() -> list[dict[str, Any]]:
    textbook = "北师大版"
    rows: list[dict[str, Any]] = []
    rows += _decimal_division(textbook, "第一单元 · 小数除法")
    rows += _transformations(textbook, "第二单元 · 轴对称和平移")
    rows += _factors(textbook, "第三单元 · 倍数与因数")
    rows += _areas(textbook, "第四单元 · 多边形的面积")
    rows += _fractions(textbook, "第五单元 · 分数的意义")
    rows += _areas(textbook, "第六单元 · 组合图形的面积")[-8:]
    rows += _probability(textbook, "第七单元 · 可能性")
    return rows


def sujiao_grade5_math_specs() -> list[dict[str, Any]]:
    textbook = "苏教版"
    rows: list[dict[str, Any]] = []
    rows += _negative_numbers(textbook, "第一单元 · 负数的初步认识")
    rows += _areas(textbook, "第二单元 · 多边形的面积")
    rows += _decimal_concepts(textbook, "第三单元 · 小数的意义和性质")
    rows += _decimal_add_sub(textbook, "第四单元 · 小数加法和减法")
    rows += _decimal_multiplication(textbook, "第五单元 · 小数乘法和除法")
    rows += _decimal_division(textbook, "第五单元 · 小数乘法和除法")
    rows += _statistics(textbook, "第六单元 · 统计表和条形统计图（二）")
    rows += _strategy(textbook, "第七单元 · 解决问题的策略")
    rows += _equations(textbook, "第八单元 · 用字母表示数")[12:]
    return rows


def jijiao_grade5_math_specs() -> list[dict[str, Any]]:
    textbook = "冀教版"
    rows: list[dict[str, Any]] = []
    rows += _direction(textbook, "第一单元 · 方向与路线")
    rows += _decimal_multiplication(textbook, "第二单元 · 小数乘法")
    rows += _decimal_division(textbook, "第三单元 · 小数除法")
    rows += _probability(textbook, "第四单元 · 可能性")
    rows += _mixed_operations(textbook, "第五单元 · 四则混合运算（二）")
    rows += _areas(textbook, "第六单元 · 多边形的面积")
    rows += _land_area(textbook, "第七单元 · 土地的面积")
    rows += _equations(textbook, "第八单元 · 方程")
    return rows


def qingdao_grade5_math_specs() -> list[dict[str, Any]]:
    textbook = "青岛版"
    rows: list[dict[str, Any]] = []
    rows += _decimal_multiplication(textbook, "第一单元 · 今天我当家——小数乘法")
    rows += _transformations(textbook, "第二单元 · 图案美——对称、平移与旋转")
    rows += _decimal_division(textbook, "第三单元 · 游三峡——小数除法")
    rows += _equations(textbook, "第四单元 · 走进动物园——简易方程")
    rows += _areas(textbook, "第五单元 · 生活中的多边形——多边形的面积")
    rows += _factors(textbook, "第六单元 · 团体操表演——因数与倍数")
    rows += _line_chart(textbook, "第七单元 · 绿色家园——折线统计图")
    return rows


def supplemental_grade5_math_specs(textbook: str) -> list[dict[str, Any]]:
    key = (textbook or "").strip()
    if key == "北师大版":
        return beishida_grade5_math_specs()
    if key == "苏教版":
        return sujiao_grade5_math_specs()
    if key == "冀教版":
        return jijiao_grade5_math_specs()
    if key == "青岛版":
        return qingdao_grade5_math_specs()
    return []


SUPPORTED_GRADE5_MATH_TEXTBOOKS = [
    "人教版",
    "北师大版",
    "苏教版",
    "冀教版",
    "青岛版",
]


__all__ = [
    "SUPPORTED_GRADE5_MATH_TEXTBOOKS",
    "beishida_grade5_math_specs",
    "sujiao_grade5_math_specs",
    "jijiao_grade5_math_specs",
    "qingdao_grade5_math_specs",
    "supplemental_grade5_math_specs",
]
