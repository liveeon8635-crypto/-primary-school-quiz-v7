"""Consolidation practice from the questions a pupil asked the after-school AI assistant (晚托作业助手).

Questions are grouped by knowledge point. A group whose knowledge point matched the school's own names keeps
that exact name on every new question, so a later submission can clear the "AI 辅助过·待巩固" flag under the
existing rule (see homework_knowledge_flags). Variants are checked with the same rules as the weekend targeted
practice (services/weekend_reports.clean_question): no copies, no number-only changes, gradable answers.
"""
from __future__ import annotations

import json
from typing import Any

from changying.services.homework_knowledge_flags import thresholds
from changying.services.weekend_reports import _norm, clean_question

SUBJECTS = ("数学", "语文", "英语")


def group_key(row: Any) -> str:
    if row["matched"] and row["knowledge_key"]:
        return f"k:{row['subject']}:{row['knowledge_key']}"
    return f"r:{row['raw_knowledge'] or ''}:{row['help_id'] if not row['raw_knowledge'] else ''}"


def text_key(text: str) -> str:
    return _norm(text)


def default_count(matched: bool) -> int:
    # Enough questions on the knowledge point for one submission to be able to clear the flag.
    return max(2, thresholds()["minQuestions"]) if matched else 2


def build_groups(rows: list[Any], counts: dict[str, int] | None = None, subjects: dict[str, str] | None = None) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = group_key(row)
        matched = bool(row["matched"] and row["knowledge_key"])
        g = groups.setdefault(key, {
            "key": key, "matched": matched, "knowledge": (row["knowledge_key"] if matched else row["raw_knowledge"]) or "",
            "subject": row["subject"] if matched else "", "grade": row["grade"], "items": []})
        g["items"].append({"key": f"h:{row['help_id']}", "helpId": int(row["help_id"]), "question": row["question_text"],
                           "answer": row["answer"], "steps": row["steps"], "verify": row["verify_status"]})
    out = []
    for g in groups.values():
        subject = (subjects or {}).get(g["key"]) or g["subject"] or "数学"
        g["subject"] = subject if subject in SUBJECTS else "数学"
        g["topic"] = g["knowledge"] or "「" + str(g["items"][0]["question"])[:30] + "」"
        n = (counts or {}).get(g["key"])
        g["count"] = max(1, min(5, int(n))) if n else default_count(g["matched"])
        out.append(g)
    # Matched knowledge points first: they need their full count to be able to clear the flag.
    return sorted(out, key=lambda g: not g["matched"])


def sources(groups: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Originals keyed the way clean_question looks them up (``item key`` after the first colon)."""
    return {str(i["helpId"]): {"full": i["question"], "material": ""} for g in groups for i in g["items"]}


def prompt(groups: list[dict[str, Any]]) -> str:
    """Anonymised: the questions the pupil asked and the explained answer; no name or class."""
    rows = [{"key": g["key"], "科目": g["subject"], "年级": g["grade"], "知识点": g["knowledge"] or "（未归类，请按原题判断具体知识点）",
             "题数": g["count"], "学生问过的题": [{"原题": str(i["question"])[:1500], "AI讲解的答案": str(i["answer"])[:200],
                                              "讲解步骤": [str(s.get("text") if isinstance(s, dict) else s)[:120] for s in (i["steps"] or [])][:6],
                                              "答案核对": "未通过，原讲解可能有误，请重新判断" if i["verify"] == "mismatch" else "正常"}
                                             for i in g["items"]]} for g in groups]
    return ("你是小学老师。学生在晚托时请 AI 讲解过下面这些题，请为每个知识点出巩固新题，要求：\n"
            "1. 考查同一知识点和方法，但不得照抄原题，也不能只把数字换掉：至少改变情境、问法或条件之一；难度由易到难（level 1、2、3）。\n"
            "2. 针对原题里容易出错的步骤（如单位换算、来回路程、平均分段数）设计，题目条件要完整，答案唯一。\n"
            "3. question_type 只允许 single_choice（4个选项，correct_index 0-3）、true_false（[\"正确\",\"错误\"]）、fill_blank、calculation、short_answer"
            "（语文不用 calculation/short_answer）；非选择题必须给简洁可判分的 answer，可在 accepted_answers 列出等价写法（如“2400米”“2.4千米”）。\n"
            "4. 不要写“如图”；需要的数据全部写进题目。每题写 explanation（给老师看的解析）。不要出现学生姓名。\n"
            "题目：" + json.dumps(rows, ensure_ascii=False) +
            '\n只输出 JSON：{"groups":[{"key":"","questions":[{"question_type":"fill_blank","level":1,"text":"","options":[],'
            '"correct_index":-1,"answer":"","accepted_answers":[],"explanation":""}]}]}')


def clean(raw: Any, group: dict[str, Any], src: dict[str, dict[str, Any]], sanitize_figure: Any) -> dict[str, Any]:
    q = clean_question(raw, group, src, sanitize_figure)
    if group["matched"]:
        q["knowledge"] = group["knowledge"]      # exact school name: the flag can only clear on this name
    return q
