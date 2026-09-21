"""Pure helpers for teacher-controlled live classroom quick checks."""

from __future__ import annotations

from typing import Any


QUICK_CHECK_TYPES = frozenset({"single_choice", "true_false"})


def normalize_quick_check_type(value: Any) -> str:
    qtype = str(value or "single_choice").strip().lower()
    if qtype in {"choice", "single"}:
        qtype = "single_choice"
    if qtype in {"judgement", "judgment", "boolean"}:
        qtype = "true_false"
    if qtype not in QUICK_CHECK_TYPES:
        raise ValueError("随堂检测当前只支持单选题或判断题")
    return qtype


def quick_check_prompt(
    *,
    grade: int,
    subject: str,
    textbook: str,
    knowledge: str,
    qtype: str,
    notes: str = "",
) -> str:
    qtype = normalize_quick_check_type(qtype)
    if qtype == "true_false":
        schema = '{"questions":[{"question_type":"true_false","text":"...","options":["正确","错误"],"correct_index":0,"explanation":"..."}]}'
        rule = "生成1道判断题，只有一个确定答案。"
    else:
        schema = '{"questions":[{"question_type":"single_choice","text":"...","options":["...","...","...","..."],"correct_index":0,"explanation":"..."}]}'
        rule = "生成1道四选一单选题，四个选项都应具有合理迷惑性，但只有一个确定答案。"
    return f"""你是中国小学课堂教师。请为一次知识点讲解后的即时随堂检测生成1道题。
年级：{int(grade or 5)}年级
科目：{str(subject or '').strip()}
教材：{str(textbook or '').strip()}
知识点：{str(knowledge or '').strip()}
教师补充：{str(notes or '').strip() or '无'}

要求：
1. 题目用于讲解后的即时理解检查，不是正式考试，不要复述教师原话。
2. {rule}
3. 内容必须与给定知识点直接相关，不得扩展到未讲内容。
4. 不得包含学生姓名、排名、能力标签或个人学习数据。
5. 解析简短清楚。
6. 只返回JSON，不要Markdown。

结构：
{schema}
"""


def clean_ai_quick_check(data: Any, *, requested_type: str, knowledge: str) -> dict[str, Any] | None:
    qtype = normalize_quick_check_type(requested_type)
    rows = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        return None
    raw = rows[0] if isinstance(rows[0], dict) else None
    if not raw:
        return None

    text = str(raw.get("text") or raw.get("question") or "").strip()
    if not text:
        return None
    try:
        correct_index = int(raw.get("correct_index"))
    except Exception:
        return None

    if qtype == "true_false":
        options = ["正确", "错误"]
        if correct_index not in (0, 1):
            return None
    else:
        options = [str(x).strip()[:1000] for x in (raw.get("options") or [])]
        if len(options) != 4 or any(not x for x in options) or correct_index not in range(4):
            return None

    return {
        "question_type": qtype,
        "question_text": text[:5000],
        "options": options,
        "correct_index": correct_index,
        "explanation": str(raw.get("explanation") or "").strip()[:5000],
        "knowledge": str(knowledge or "").strip()[:180],
    }


def quick_check_summary(rows: list[dict[str, Any]], *, option_count: int) -> dict[str, Any]:
    total = len(rows)
    correct = sum(1 for row in rows if bool(row.get("is_correct")))
    accuracy = int(correct * 100 / total + 0.5) if total else None
    counts = [0 for _ in range(max(0, int(option_count or 0)))]
    for row in rows:
        try:
            idx = int(row.get("selected_index"))
        except Exception:
            continue
        if 0 <= idx < len(counts):
            counts[idx] += 1
    distribution = [
        {
            "selectedIndex": idx,
            "count": count,
            "percentage": int(count * 100 / total + 0.5) if total else 0,
        }
        for idx, count in enumerate(counts)
    ]
    return {
        "responseCount": total,
        "correctCount": correct,
        "accuracy": accuracy,
        "distribution": distribution,
    }


__all__ = [
    "QUICK_CHECK_TYPES",
    "clean_ai_quick_check",
    "normalize_quick_check_type",
    "quick_check_prompt",
    "quick_check_summary",
]
