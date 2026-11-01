"""三年级上册 U2–U4 题目草稿（可程序验算）。

每个知识点 6 题：基础 2、中等 2、提高 2。题目里带 verify 参数，测试会重算答案，
保证「能算的必须验算」。U1（观察物体）与 UC（曹冲称象）需要配图或情境，留给老师人工出题。
"""
from __future__ import annotations

from typing import Any

# 长度/质量单位换算因子（相对基准单位：毫米、克）
_LEN = {"毫米": 1, "厘米": 10, "分米": 100, "米": 1000, "千米": 1000000}
_MASS = {"克": 1, "千克": 1000, "吨": 1000000}


def _mul(a: int, b: int, level: str) -> dict[str, Any]:
    return {"text": f"{a} × {b} = ____", "answer": str(a * b), "level": level,
            "verify": {"op": "mul", "a": a, "b": b}}


def _expr(text: str, level: str) -> dict[str, Any]:
    """纯数字与 + - × ÷ 括号的算式，先按普通运算优先级求值再核对。"""
    value = eval(text.replace("×", "*").replace("÷", "/"), {"__builtins__": {}}, {})
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return {"text": f"{text} = ____", "answer": str(value), "level": level,
            "verify": {"op": "expr", "text": text}}


def _conv(value: int, src: str, dst: str, level: str, table: dict[str, int] = None) -> dict[str, Any]:
    table = table or _LEN
    answer = value * table[src] // table[dst]
    return {"text": f"{value} {src} = （　）{dst}", "answer": str(answer), "level": level,
            "verify": {"op": "conv", "value": value, "src": src, "dst": dst, "table": table}}


def _word(question: str, answer: int, level: str, check: dict[str, Any]) -> dict[str, Any]:
    return {"text": question, "answer": str(answer), "level": level, "verify": check}


def build_drafts() -> dict[str, list[dict[str, Any]]]:
    """返回 {知识点名称: [6 道题]}，名称与地图节点的 name 一致。"""
    return {
        "无括号的同级混合运算": [
            _expr("36 + 24 - 18", "basic"),
            _expr("72 - 35 + 20", "basic"),
            _expr("8 × 6 ÷ 4", "medium"),
            _expr("96 ÷ 8 × 5", "medium"),
            _word("一盒有 24 支笔，先卖出 9 支，又放进 7 支，现在有多少支？", 24 - 9 + 7, "hard",
                  {"op": "int", "value": 24 - 9 + 7}),
            _word("每排 8 人，共 6 排，平均分成 4 队，每队多少人？", 8 * 6 // 4, "hard",
                  {"op": "int", "value": 8 * 6 // 4}),
        ],
        "无括号的两级混合运算": [
            _expr("24 + 6 × 3", "basic"),
            _expr("50 - 4 × 5", "basic"),
            _expr("36 ÷ 6 + 27", "medium"),
            _expr("81 - 45 ÷ 9", "medium"),
            _word("一支笔 3 元，一个本子 5 元，买 4 支笔和 2 个本子共多少钱？", 3 * 4 + 5 * 2, "hard",
                  {"op": "int", "value": 3 * 4 + 5 * 2}),
            _word("有 60 个苹果，每 5 个装一袋，已经装好 7 袋，还剩多少个没装？", 60 - 5 * 7, "hard",
                  {"op": "int", "value": 60 - 5 * 7}),
        ],
        "有括号的混合运算": [
            _expr("(24 + 16) ÷ 8", "basic"),
            _expr("(45 - 25) × 3", "basic"),
            _expr("72 ÷ (3 + 6)", "medium"),
            _expr("5 × (40 - 32)", "medium"),
            _word("每盒 6 个鸡蛋，买了 4 盒，吃掉 5 个，还剩多少个？（列综合算式）", 6 * 4 - 5, "hard",
                  {"op": "int", "value": 6 * 4 - 5}),
            _word("全班 45 人，平均分成 5 组，每组再分成 3 小队，每小队多少人？", 45 // 5 // 3, "hard",
                  {"op": "int", "value": 45 // 5 // 3}),
        ],
        "解决实际问题（1）": [
            _word("小明有 28 元，买一本 12 元的书，还剩多少元？", 28 - 12, "basic", {"op": "int", "value": 28 - 12}),
            _word("一棵树上 35 个果子，摘了 18 个，树上还有多少个？", 35 - 18, "basic", {"op": "int", "value": 35 - 18}),
            _word("每盒 8 块糖，买了 3 盒，一共多少块？", 8 * 3, "medium", {"op": "int", "value": 8 * 3}),
            _word("一本书 42 页，每天看 6 页，几天看完？", 42 // 6, "medium", {"op": "int", "value": 42 // 6}),
            _word("买 3 支笔每支 5 元，付了 20 元，应找回多少元？", 20 - 3 * 5, "hard",
                  {"op": "int", "value": 20 - 3 * 5}),
            _word("有 24 人，每 4 人一组，分成几组？如果每组再加 1 人，还能分几组？", 24 // 4, "hard",
                  {"op": "int", "value": 24 // 4}),
        ],
        "解决实际问题（2）": [
            _word("每张桌子坐 4 人，5 张桌子坐多少人？", 4 * 5, "basic", {"op": "int", "value": 4 * 5}),
            _word("一箱 12 瓶，3 箱共多少瓶？", 12 * 3, "basic", {"op": "int", "value": 12 * 3}),
            _word("买 4 本 8 元的书，付 50 元，找回多少？（列综合算式）", 50 - 4 * 8, "medium",
                  {"op": "int", "value": 50 - 4 * 8}),
            _word("3 盒铅笔每盒 10 支，平均分给 5 人，每人几支？", 3 * 10 // 5, "medium",
                  {"op": "int", "value": 3 * 10 // 5}),
            _word("做 6 朵花用 30 分钟，照这样 9 朵要多久？", 30 // 6 * 9, "hard",
                  {"op": "int", "value": 30 // 6 * 9}),
            _word("有 5 排座位，每排 8 个，已经坐了 27 人，还空几个？", 5 * 8 - 27, "hard",
                  {"op": "int", "value": 5 * 8 - 27}),
        ],
        "整理和复习（混合运算）": [
            _expr("18 + 30 ÷ 6", "basic"),
            _expr("(20 - 8) × 4", "basic"),
            _expr("64 ÷ (2 × 4)", "medium"),
            _expr("7 × 8 - 30", "medium"),
            _word("每盒 9 个球，买 5 盒，借给同学 12 个，还剩多少个？", 9 * 5 - 12, "hard",
                  {"op": "int", "value": 9 * 5 - 12}),
            _word("36 元买 4 支笔，用 27 元能买几支？", 27 // (36 // 4), "hard",
                  {"op": "int", "value": 27 // (36 // 4)}),
        ],
        "毫米、分米的认识（1）": [
            _conv(3, "厘米", "毫米", "basic"),
            _conv(7, "厘米", "毫米", "basic"),
            _conv(40, "毫米", "厘米", "medium"),
            _conv(85, "毫米", "厘米", "medium"),
            _word("一支铅笔长 16 厘米，也就是多少毫米？", 160, "hard", {"op": "int", "value": 160}),
            _word("一根小棒长 52 毫米，比 6 厘米短多少毫米？", 8, "hard",
                  {"op": "int", "value": 8}),
        ],
        "毫米、分米的认识（2）": [
            _conv(2, "分米", "厘米", "basic"),
            _conv(5, "分米", "厘米", "basic"),
            _conv(30, "厘米", "分米", "medium"),
            _conv(300, "毫米", "分米", "medium"),
            _word("一张桌子高 7 分米，合多少厘米？多少毫米？", 70, "hard", {"op": "int", "value": 70}),
            _word("一条绳子长 1 米，剪去 3 分米，还剩多少分米？", 10 - 3, "hard",
                  {"op": "int", "value": 10 - 3}),
        ],
        "千米的认识与估测": [
            _conv(2, "千米", "米", "basic"),
            _conv(5, "千米", "米", "basic"),
            _conv(3000, "米", "千米", "medium"),
            _conv(8000, "米", "千米", "medium"),
            _word("从家到学校 1 千米 200 米，合多少米？", 1200, "hard", {"op": "int", "value": 1200}),
            _word("小明走了 500 米，再走多少米正好 1 千米？", 500, "hard", {"op": "int", "value": 500}),
        ],
        "整理和复习（毫米、分米和千米）": [
            _conv(6, "分米", "毫米", "basic", _LEN),
            _conv(5000, "米", "千米", "basic", _LEN),
            _conv(9, "厘米", "毫米", "medium", _LEN),
            _conv(70, "毫米", "厘米", "medium", _LEN),
            _word("一根铁丝长 2 米，用去 8 分米，还剩多少分米？", 12, "hard", {"op": "int", "value": 12}),
            _word("跑 400 米的跑道，跑 2 圈半是多少米？合多少千米？", 1000, "hard",
                  {"op": "int", "value": 1000}),
        ],
        "口算乘法": [
            _mul(30, 4, "basic"),
            _mul(20, 5, "basic"),
            _mul(300, 3, "medium"),
            _mul(40, 6, "medium"),
            _word("每箱 500 瓶，8 箱一共多少瓶？", 4000, "hard", {"op": "int", "value": 4000}),
            _word("1 分钟走 60 米，7 分钟走多少米？", 420, "hard", {"op": "int", "value": 420}),
        ],
        "多位数乘一位数（不进位）": [
            _mul(213, 3, "basic"),
            _mul(412, 2, "basic"),
            _mul(121, 4, "medium"),
            _mul(332, 3, "medium"),
            _word("每盒 123 个，3 盒一共多少个？", 369, "hard", {"op": "int", "value": 369}),
            _word("每张票 214 元，2 张多少钱？", 428, "hard", {"op": "int", "value": 428}),
        ],
        "多位数乘一位数（一次进位）": [
            _mul(27, 3, "basic"),
            _mul(46, 2, "basic"),
            _mul(38, 3, "medium"),
            _mul(29, 4, "medium"),
            _word("每箱 35 千克，4 箱多少千克？", 140, "hard", {"op": "int", "value": 140}),
            _word("每本 48 元，3 本多少钱？", 144, "hard", {"op": "int", "value": 144}),
        ],
        "多位数乘一位数（连续进位）": [
            _mul(278, 3, "basic"),
            _mul(156, 4, "basic"),
            _mul(384, 2, "medium"),
            _mul(267, 3, "medium"),
            _word("每箱 365 个，4 箱一共多少个？", 1460, "hard", {"op": "int", "value": 365 * 4}),
            _word("每人 189 元，5 人一共多少元？", 945, "hard", {"op": "int", "value": 189 * 5}),
        ],
        "乘数中间或末尾有 0 的乘法": [
            _mul(306, 3, "basic"),
            _mul(450, 2, "basic"),
            _mul(208, 4, "medium"),
            _mul(600, 5, "medium"),
            _word("每台 406 元，3 台一共多少元？", 1218, "hard", {"op": "int", "value": 406 * 3}),
            _word("每箱 250 瓶，4 箱一共多少瓶？", 1000, "hard", {"op": "int", "value": 250 * 4}),
        ],
        "认识曹冲称象与质量单位": [
            _conv(2, "吨", "千克", "basic", _MASS),
            _conv(5000, "千克", "吨", "basic", _MASS),
            _conv(3, "千克", "克", "medium", _MASS),
            _conv(8000, "克", "千克", "medium", _MASS),
            _word("一头大象重 4 吨，合多少千克？", 4000, "hard", {"op": "int", "value": 4000}),
            _word("一袋大米重 25 千克，40 袋共重多少吨？", 1, "hard", {"op": "int", "value": 25 * 40 // 1000}),
        ],
        "数字编码": [
            _word("邮政编码由几位数字组成？", 6, "basic", {"op": "int", "value": 6}),
            _word("我国居民身份证号码有几位数字？", 18, "basic", {"op": "int", "value": 18}),
            _word("身份证号第 17 位是单数表示性别为？", 1, "medium", {"op": "gender", "digit": 3, "expect": 1}),
            _word("身份证号第 17 位是双数表示性别为？", 0, "medium", {"op": "gender", "digit": 8, "expect": 0}),
            _word("某班学号规则是「年级(1 位)+班级(2 位)+序号(2 位)」，三年级 2 班 7 号应编成？", 30207,
                  "hard", {"op": "int", "value": 30207}),
            _word("上面的学号编码一共用了几位数字？", 5, "hard", {"op": "int", "value": 5}),
        ],        "整理和复习（多位数乘一位数）": [
            _mul(213, 3, "basic"),
            _mul(45, 2, "basic"),
            _mul(306, 4, "medium"),
            _mul(278, 3, "medium"),
            _word("每台 207 元，4 台一共多少元？", 828, "hard", {"op": "int", "value": 207 * 4}),
            _word("每箱 250 瓶，6 箱一共多少瓶？", 1500, "hard", {"op": "int", "value": 250 * 6}),
        ],
        "用乘法估算解决实际问题": [
            _word("每本 19 元，买 5 本，大约要多少元？", 100, "basic", {"op": "int", "value": 20 * 5}),
            _word("每箱 29 瓶，4 箱大约多少瓶？", 120, "basic", {"op": "int", "value": 30 * 4}),
            _word("每袋 52 个，6 袋大约多少个？（把 52 看作 50）", 300, "medium",
                  {"op": "int", "value": 50 * 6}),
            _word("每袋 52 个，5 袋大约多少个？", 250, "medium", {"op": "int", "value": 50 * 5}),
            _word("每分钟打字 61 个，8 分钟大约打多少个？", 480, "hard", {"op": "int", "value": 60 * 8}),
            _word("每箱 39 瓶，7 箱大约多少瓶？（把 39 看作 40）", 280, "hard",
                  {"op": "int", "value": 40 * 7}),
        ],
    }
