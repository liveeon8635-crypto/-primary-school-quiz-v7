"""Deterministic knowledge-point / question-type fit policy.

The goal is not to maximize superficial type diversity. It prevents mechanically
re-skinned forms that are awkward for the actual skill being assessed while
keeping multiple natural forms available where they genuinely fit.
"""

from __future__ import annotations

from typing import Any


_ALIASES = {
    "choice": "single_choice",
    "single": "single_choice",
    "judgement": "true_false",
    "judgment": "true_false",
    "boolean": "true_false",
    "blank": "fill_blank",
    "calc": "calculation",
    "application": "short_answer",
}


def normalize_type(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return _ALIASES.get(raw, raw)


def _match(knowledge: str, markers: tuple[str, ...]) -> bool:
    text = str(knowledge or "").strip().lower()
    return any(marker.lower() in text for marker in markers)


def question_type_fit_score(subject: str, knowledge: str, question_type: str) -> int:
    """Return 0=natural, 1=acceptable, 3=reject for automatic practice."""

    subject = str(subject or "").strip()
    knowledge = str(knowledge or "").strip()
    qtype = normalize_type(question_type)

    if subject == "语文":
        if _match(knowledge, ("句子衔接", "语句衔接", "句子排序", "语序", "连贯")):
            return 0 if qtype in {"single_choice", "fill_blank"} else 3
        if _match(knowledge, ("病句", "习作修改", "修改病句")):
            return 0 if qtype == "single_choice" else (1 if qtype == "fill_blank" else 3)
        if _match(knowledge, ("关联词",)):
            return 0 if qtype in {"fill_blank", "single_choice"} else (1 if qtype == "true_false" else 3)
        if _match(knowledge, ("字音", "字形", "标点", "修辞", "说明方法")):
            return 0 if qtype in {"single_choice", "true_false"} else (1 if qtype == "fill_blank" else 3)
        if _match(knowledge, ("词语理解", "成语")):
            return 0 if qtype in {"single_choice", "fill_blank"} else (1 if qtype == "true_false" else 3)
        if _match(knowledge, ("阅读推断", "提取关键信息", "概括主要内容", "体会思想感情", "资料整合")):
            return 0 if qtype == "single_choice" else (1 if qtype == "true_false" else 3)
        return 0 if qtype == "single_choice" else (1 if qtype in {"true_false", "fill_blank"} else 3)

    if subject == "英语":
        if _match(knowledge, ("拼写", "词汇", "单词", "短语")):
            return 0 if qtype in {"fill_blank", "single_choice"} else (1 if qtype == "true_false" else 3)
        if _match(knowledge, ("句型", "语法", "一般现在时", "should", "can", "be动词", "do")):
            return 0 if qtype in {"fill_blank", "single_choice"} else (1 if qtype == "true_false" else 3)
        if _match(knowledge, ("信息理解", "阅读", "情境", "推断")):
            return 0 if qtype == "single_choice" else (1 if qtype == "true_false" else 3)
        return 0 if qtype in {"single_choice", "fill_blank"} else (1 if qtype == "true_false" else 3)

    if subject == "数学":
        if _match(knowledge, ("计算", "口算", "竖式", "小数乘", "小数除", "简便运算")):
            return 0 if qtype in {"calculation", "fill_blank"} else (1 if qtype in {"single_choice", "short_answer"} else 3)
        if _match(knowledge, ("应用", "数量关系", "解决问题")):
            return 0 if qtype in {"short_answer", "calculation"} else (1 if qtype == "single_choice" else 3)
        if _match(knowledge, ("面积", "周长", "图形", "几何", "统计", "可能性")):
            return 0 if qtype in {"single_choice", "calculation", "short_answer"} else (1 if qtype in {"fill_blank", "true_false"} else 3)
        return 0 if qtype in {"single_choice", "fill_blank", "calculation", "short_answer"} else 1

    if subject == "科学":
        return 0 if qtype in {"single_choice", "true_false", "fill_blank"} else 3

    return 0


def question_type_is_acceptable(subject: str, knowledge: str, question_type: str) -> bool:
    return question_type_fit_score(subject, knowledge, question_type) < 3


def subject_question_type_guidance(subject: str) -> str:
    subject = str(subject or "").strip()
    if subject == "语文":
        return (
            "题型必须服从知识点，而不是为了凑题型而机械改写："
            "句子衔接/排序/连贯优先单选或填空，不使用判断题；"
            "病句与习作修改优先单选；关联词优先填空或单选；"
            "字音字形、标点、修辞、说明方法可用单选或判断；"
            "阅读推断、信息提取、概括、思想感情、资料整合优先有材料支撑的单选。"
        )
    if subject == "英语":
        return (
            "题型必须服从知识点：词汇/拼写优先填空或单选；"
            "句型和语法优先填空或单选；阅读与情境理解优先单选，"
            "判断题只用于结论确实可二值判定的内容。"
        )
    if subject == "数学":
        return (
            "题型必须服从知识点：计算类优先计算题/填空；"
            "应用与数量关系优先简短应用题/计算；"
            "图形统计类按任务需要使用选择、计算或简答，"
            "不要为了题型多样把过程性计算机械改成判断题。"
        )
    return ""


__all__ = [
    "normalize_type",
    "question_type_fit_score",
    "question_type_is_acceptable",
    "subject_question_type_guidance",
]
