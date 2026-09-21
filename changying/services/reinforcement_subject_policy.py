"""Subject-aware policy for AI reinforcement generation.

The legacy reinforcement endpoint already preserves grade/subject/textbook from
assessment context. This module tightens the generation contract so a Chinese
assessment cannot be biased by the mathematical examples in the shared prompt.
"""

from __future__ import annotations

import json
import re
from functools import wraps
from types import ModuleType
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from changying.services.question_type_fit import (
    question_type_is_acceptable,
    subject_question_type_guidance,
)

from changying.services.language_question_quality import language_semantic_family_fields


def reinforcement_subject_from_prompt(prompt: str) -> str:
    text = str(prompt or "")
    # The serialized assessment context appears before the wrong-question list.
    primary = re.search(
        r'"primary"\s*:\s*\{.*?"subject"\s*:\s*"([^"]+)"',
        text,
        flags=re.DOTALL,
    )
    if primary:
        return primary.group(1).strip()
    source = re.search(r'"subject"\s*:\s*"([^"]+)"', text)
    return source.group(1).strip() if source else ""





SCIENCE_AUTO_TYPES = frozenset({"single_choice", "true_false", "fill_blank"})
AMBIGUOUS_SCIENCE_TEXTBOOKS = frozenset(
    {
        "",
        "人教版",
        "人教版（当前最新版）",
        "人教版（PEP·当前最新版）",
        "PEP·当前最新版",
        "统编版",
        "统编版（人民教育出版社）",
    }
)


def explicit_science_textbook(textbook: str) -> str:
    """Return only a school-explicit science textbook label."""
    value = str(textbook or "").strip()
    return "" if value in AMBIGUOUS_SCIENCE_TEXTBOOKS else value


def require_explicit_science_textbook(textbook: str) -> str:
    """Reject generic defaults that could silently relabel science work."""
    value = explicit_science_textbook(textbook)
    if not value:
        raise ValueError(
            "科学教材必须明确填写学校实际使用的出版社/版本；"
            "针对性练习不能默认使用“人教版”等其他学科通用教材名"
        )
    return value


def normalize_science_reinforcement_items(
    items: list[dict[str, Any]],
    *,
    textbook: str = "",
) -> list[dict[str, Any]]:
    """Keep science reinforcement objective-safe and textbook-faithful.

    The legacy generator defaults non-Chinese reinforcement to "人教版".
    Science must overwrite that value from explicit assessment context only.
    """
    safe_textbook = explicit_science_textbook(textbook)
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        qtype = str(item.get("question_type") or "").strip().lower()
        if qtype == "choice":
            qtype = "single_choice"
        if qtype not in SCIENCE_AUTO_TYPES:
            continue
        row = dict(item)
        row["question_type"] = qtype
        row["textbook"] = safe_textbook
        row["figure"] = {}
        result.append(row)
    return result



_GENERIC_SOURCE_MARKERS = (
    "下列",
    "哪项",
    "哪一项",
    "一项是",
    "选择正确",
    "choose the correct",
)


def _item_value(item: Any, key: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _normalized_reinforcement_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text.rstrip("。.!！?？").strip().lower()


def reinforcement_source_stem(item: Any) -> str:
    subject = str(_item_value(item, "subject", "") or "").strip()
    qtype = str(_item_value(item, "question_type", "") or "").strip().lower()
    text = str(_item_value(item, "text", "") or "").strip()

    if subject == "语文":
        if text.startswith("请从备选答案中选择，并输入完整答案："):
            text = text.split("：", 1)[1].strip()
            text = re.split(r"\s*备选答案：", text, maxsplit=1)[0].strip()
        elif text.startswith("请直接填写答案："):
            text = text.split("：", 1)[1].strip()
        elif qtype == "true_false" and text.startswith("判断下面的作答是否正确：") and "——" in text:
            text = text.split("：", 1)[1].rsplit("——", 1)[0].strip()
    elif subject == "英语":
        lowered = text.lower()
        for prefix in ("write the answer:", "complete with the correct answer:"):
            if lowered.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        if qtype == "true_false":
            if text.startswith("Is this answer correct?") and "—" in text:
                text = text[len("Is this answer correct?"):].rsplit("—", 1)[0].strip()
            else:
                match = re.fullmatch(
                    r'True or false:\s*For\s+"(.+)",\s*the answer is\s*".+"\.',
                    text,
                    flags=re.IGNORECASE,
                )
                if match:
                    text = match.group(1).strip()
    return _normalized_reinforcement_text(text)


def reinforcement_source_key(item: Any) -> str:
    subject = str(_item_value(item, "subject", "") or "").strip()
    knowledge = str(_item_value(item, "knowledge", "") or "").strip()
    stem = reinforcement_source_stem(item)
    if not stem:
        return ""
    # Generic option-dependent stems can represent many genuinely different
    # questions. Never use the stem alone to block those against source rows.
    lowered = stem.lower()
    if any(marker in lowered for marker in _GENERIC_SOURCE_MARKERS):
        return ""
    return "|".join((subject, knowledge, stem))



def _reinforcement_claimed_answer(item: Any) -> str:
    subject = str(_item_value(item, "subject", "") or "").strip()
    qtype = str(_item_value(item, "question_type", "") or "").strip().lower()
    if qtype != "true_false":
        return ""
    text = str(_item_value(item, "text", "") or "").strip()
    if subject == "语文":
        prefix = "判断下面的作答是否正确："
        if text.startswith(prefix) and "——" in text[len(prefix):]:
            return text[len(prefix):].rsplit("——", 1)[1].strip().rstrip("。")
        match = re.fullmatch(r"判断正误：题目“.+”的答案是“(.+)”。", text)
        return match.group(1).strip() if match else ""
    if subject == "英语":
        prefix = "Is this answer correct?"
        if text.startswith(prefix) and "—" in text[len(prefix):]:
            return text[len(prefix):].rsplit("—", 1)[1].strip().rstrip(".")
        match = re.fullmatch(
            r'True or false:\s*For\s+".+",\s*the answer is\s*"(.+)"\.',
            text,
            flags=re.IGNORECASE,
        )
        return match.group(1).strip() if match else ""
    return ""


def reinforcement_content_aliases(item: Any) -> set[str]:
    """Return deterministic cross-type aliases for language content.

    The aliases do not use fuzzy similarity. A reviewed single-choice source
    can therefore match a fill/true-false re-skin even when its stem is generic,
    while another option set with the same generic stem remains distinct.
    """
    subject = str(_item_value(item, "subject", "") or "").strip()
    if subject not in {"语文", "英语"}:
        return set()
    knowledge = str(_item_value(item, "knowledge", "") or "").strip()
    stem = reinforcement_source_stem(item)
    if not stem:
        return set()
    qtype = str(_item_value(item, "question_type", "") or "").strip().lower()
    if qtype == "choice":
        qtype = "single_choice"
    options = [str(x).strip() for x in (_item_value(item, "options", []) or [])]
    try:
        correct_index = int(_item_value(item, "correct_index", -1))
    except Exception:
        correct_index = -1
    answer = str(
        _item_value(item, "answer", "")
        or _item_value(item, "reference_answer", "")
        or ""
    ).strip()

    prefix = "|".join((subject, knowledge, stem))
    aliases: set[str] = set()

    if qtype == "single_choice" and 0 <= correct_index < len(options):
        correct = _normalized_reinforcement_text(options[correct_index])
        aliases.add(prefix + "|answer|" + correct)
        for index, option in enumerate(options):
            value = _normalized_reinforcement_text(option)
            aliases.add(
                prefix
                + "|claim|"
                + value
                + "|"
                + ("true" if index == correct_index else "false")
            )
    elif qtype == "fill_blank" and answer:
        aliases.add(prefix + "|answer|" + _normalized_reinforcement_text(answer))
    elif qtype == "true_false":
        claimed = _reinforcement_claimed_answer(item)
        if claimed and correct_index in (0, 1):
            aliases.add(
                prefix
                + "|claim|"
                + _normalized_reinforcement_text(claimed)
                + "|"
                + ("true" if correct_index == 0 else "false")
            )
    return aliases


def reinforcement_content_family(item: Any) -> str:
    subject = str(_item_value(item, "subject", "") or "").strip()
    knowledge = str(_item_value(item, "knowledge", "") or "").strip()
    text = str(_item_value(item, "text", "") or "").strip()
    qtype = str(_item_value(item, "question_type", "") or "").strip().lower()
    if qtype == "choice":
        qtype = "single_choice"
    options = [str(x) for x in (_item_value(item, "options", []) or [])]
    try:
        correct_index = int(_item_value(item, "correct_index", -1))
    except Exception:
        correct_index = -1
    answer = str(
        _item_value(item, "answer", "")
        or _item_value(item, "reference_answer", "")
        or ""
    ).strip()

    if subject in {"语文", "英语"}:
        return language_semantic_family_fields(
            subject=subject,
            knowledge=knowledge,
            text=text,
            options=options,
            correct_index=correct_index,
            question_type=qtype,
            answer=answer,
        )

    # Non-language subjects use an exact, conservative family. This blocks
    # literal duplicates without guessing that two merely similar questions
    # are equivalent.
    stem = reinforcement_source_stem(item)
    answer_or_options = options or ([f"answer:{answer}"] if answer else [])
    return "|".join(
        (
            subject,
            knowledge,
            stem,
            json.dumps(answer_or_options, ensure_ascii=False),
        )
    )


def dedupe_reinforcement_items(
    items: list[Any],
    *,
    source_keys: set[str] | None = None,
    source_families: set[str] | None = None,
    source_aliases: set[str] | None = None,
) -> tuple[list[Any], int]:
    seen: set[str] = set(source_families or set())
    seen_aliases: set[str] = set(source_aliases or set())
    blocked = set(source_keys or set())
    kept: list[Any] = []
    dropped = 0
    for item in items:
        family = reinforcement_content_family(item)
        aliases = reinforcement_content_aliases(item)
        source_key = reinforcement_source_key(item)
        if (
            family in seen
            or bool(aliases & seen_aliases)
            or (source_key and source_key in blocked)
        ):
            dropped += 1
            continue
        seen.add(family)
        seen_aliases.update(aliases)
        kept.append(item)
    return kept, dropped


def scope_context_to_primary_subject(context: dict[str, Any]) -> dict[str, Any]:
    """Keep one reinforcement cycle inside the primary subject and textbook line."""
    if not isinstance(context, dict):
        return context
    primary = dict(context.get("primary") or {})
    subject = str(primary.get("subject") or "").strip()
    textbook = str(primary.get("textbook") or "").strip()
    if not subject:
        return context
    assessments = [
        x for x in (context.get("assessments") or [])
        if str((x or {}).get("subject") or "").strip() == subject
        and (
            not textbook
            or str((x or {}).get("textbook") or "").strip() == textbook
        )
    ]
    weak = [
        x for x in (context.get("weakKnowledge") or [])
        if str((x or {}).get("subject") or "").strip() == subject
        and (
            not textbook
            or str((x or {}).get("textbook") or "").strip() == textbook
        )
    ]
    out = dict(context)
    out["assessments"] = assessments
    out["weakKnowledge"] = weak[:10]
    out["assessmentCount"] = len(assessments)
    out["sourceAssignmentIDs"] = [
        int(x.get("assignmentID"))
        for x in assessments
        if int(x.get("assignmentID") or 0) > 0
    ]
    out["primary"] = primary
    return out


def augment_reinforcement_prompt(feature: str, prompt: str) -> str:
    if str(feature or "") != "reinforcement_generate":
        return prompt
    subject = reinforcement_subject_from_prompt(prompt)
    fit_guidance = subject_question_type_guidance(subject)
    if subject == "科学":
        return (
            str(prompt)
            + """

【科学学科附加约束】
1. 当前科目是科学。所有题目必须围绕当前学生已有科学学习证据，不得生成纯数学计算题、语文阅读题或英语语言题。
2. 教材名称、年级、册次和单元必须原样沿用 assessmentContext 中已有信息；如果上下文没有明确教材版本，不得自行猜测、替换或声称来自某一出版社教材。
3. 本轮自动判分只使用 single_choice、true_false、fill_blank；不要使用 calculation 或开放式 short_answer。fill_blank 只用于存在唯一或明确等价答案的科学术语、现象或结论。
4. 题干必须给足观察对象、实验条件、数据或现象，考查“观察—证据—解释”、结构与功能、变化与因果、系统与模型等真实科学理解，不能把教学目标直接改成题目。
5. 涉及实验时必须明确变量和条件；不得要求学生自行实施明火、强电、危险化学品等有风险操作。
6. figure 必须返回 {}。当前渲染器的坐标图、几何图、线段图等属于数学图示，在专门的科学结构化图示规范上线前不得冒充科学实验图。
7. answer / accepted_answers 只能放可自动判分的标准答案或明确等价表达；需要解释证据、设计实验或开放推理的内容应留给教师审核型主观题，而不是伪装成自动判分。
"""
        )
    if subject == "英语":
        return (
            str(prompt)
            + """

【英语学科附加约束】
1. 当前科目是英语。所有题目必须是小学英语内容，不得生成数学计算题、数学数量关系题或数学图示。
0. {fit_guidance}
2. 教材必须保持“人教版（PEP·当前最新版）”五年级上册语境；当前六个单元为 Different friends、My feelings、Work and play、Healthy habits、Food we eat、Nature and us。不得回退到旧版单元标题。
3. 自动判分题只使用 single_choice、true_false、fill_blank；不要使用 calculation 或开放式 short_answer。5题以上尽量覆盖至少3种题型。
4. fill_blank 仅用于答案明确的单词、短语、be/do/can/should 等语法形式；若存在多种合理表达，改成 single_choice/true_false，或完整列入 accepted_answers。
5. 阅读或情境题所需材料必须在题干内完整给出，材料简短、原创、信息充分；不得假定学生能看到教材原文，也不要复制教材对话。
6. figure 必须返回 {}。英语题不得使用 coordinate_grid、geometry、line_segment 等数学图示。
7. 题目优先围绕当前测试反馈中的词汇、句型、语法、情境理解、短文信息提取与健康/自然主题语言运用，不得跨科。
"""
        )
    if subject and subject != "语文":
        return (
            str(prompt)
            + f"""

【学科隔离约束】
当前科目是{subject}。待巩固错题中如意外混入其他学科记录，必须忽略；所有生成题必须保持当前科目，不得跨科。
"""
        )
    if subject != "语文":
        return prompt
    return (
        str(prompt)
        + """

【语文学科附加约束】
1. 当前科目是语文。所有题目必须是小学语文学科内容，不得生成数学计算题、数学数量关系题或数学图示。
0. {fit_guidance}
2. 语文自动判分题只使用 single_choice、true_false、fill_blank；不要使用 calculation 或 short_answer。5题以上尽量覆盖这3种题型，但准确性优先。
3. fill_blank 只用于存在明确、可自动判定答案的字词、关联词、标点或短语。开放性阅读感受、习作、概括性长答和长篇表达不得自动判分，遇到这类知识点必须改写成选择/判断等客观题；主观题以后走评分点 + 教师确认，不与本轮自动判分混用。
4. 阅读题所需材料必须在题干内完整给出，材料简短、原创、信息充分；不得假定学生看得到教材原文，也不要大段复现教材或受版权保护的文章。
5. 字音、字形、词语、成语、关联词、病句、标点、修辞、句子衔接、信息提取、概括、推断、说明方法、资料整合等题目要紧扣反馈中的具体知识点。
6. 语文题 figure 必须返回 {}，除非未来有专门的语文学科结构化图表规范；不得使用 coordinate_grid、geometry、line_segment 等数学图示。
7. answer / accepted_answers 必须只包含可以自动判分的标准答案或明确等价表达，不能把主观性很强的多种自由回答伪装成自动判分。
"""
    )


def install_reinforcement_subject_policy(implementation: ModuleType) -> None:
    if getattr(implementation, "_reinforcement_subject_policy_installed", False):
        return

    original_ai_call = implementation._ai_call
    original_context = implementation.student_assessment_context

    def subject_aware_ai_call(
        db: Any,
        u: Any,
        feature: str,
        prompt: str,
        images=None,
        timeout: int = 90,
    ):
        return original_ai_call(
            db,
            u,
            feature,
            augment_reinforcement_prompt(feature, prompt),
            images=images,
            timeout=timeout,
        )

    def subject_scoped_assessment_context(*args: Any, **kwargs: Any):
        return scope_context_to_primary_subject(original_context(*args, **kwargs))

    implementation._ai_call = subject_aware_ai_call
    implementation.student_assessment_context = subject_scoped_assessment_context

    # The route returns wrongIDs which are later stored in ReinforcementLink.
    # Keep those IDs in the same subject as the generated practice, including
    # teacher-authored historical wrong records that are not assessment-scoped.
    target = "/teacher/students/{sid}/reinforcement/generate"
    for route in implementation.app.routes:
        if getattr(route, "path", None) != target or "POST" not in getattr(route, "methods", set()):
            continue
        original_route = route.dependant.call

        def subject_scoped_route(*args: Any, __original=original_route, **kwargs: Any):
            result = __original(*args, **kwargs)
            if not isinstance(result, dict):
                return result
            items = [x for x in (result.get("items") or []) if isinstance(x, dict)]
            subjects = {
                str(x.get("subject") or "").strip()
                for x in items
                if str(x.get("subject") or "").strip()
            }
            if len(subjects) != 1:
                return result
            subject = next(iter(subjects))
            wrong_ids = [
                int(x) for x in (result.get("wrongIDs") or [])
                if int(x or 0) > 0
            ]
            payload = dict(result)
            if subject == "科学":
                primary = dict((payload.get("assessmentContext") or {}).get("primary") or {})
                science_textbook = explicit_science_textbook(
                    str(primary.get("textbook") or "")
                )
                normalized_items = normalize_science_reinforcement_items(
                    items,
                    textbook=science_textbook,
                )
                payload["items"] = normalized_items
                notices: list[str] = []
                if len(normalized_items) != len(items):
                    notices.append("科学针对性练习已移除不适合自动判分的开放题型。")
                if not science_textbook:
                    notices.append(
                        "科学学习证据未明确教材出版社/版本；本次练习不会默认标记为“人教版”，补全学校实际教材后才能布置。"
                    )
                if notices:
                    payload["notice"] = (
                        str(payload.get("notice") or "").strip("；")
                        + "；"
                        + "；".join(notices)
                    ).strip("；")
            if subject == "英语":
                normalized_items = []
                for item in items:
                    row = dict(item)
                    row["textbook"] = "人教版（PEP·当前最新版）"
                    row["figure"] = {}
                    normalized_items.append(row)
                payload["items"] = normalized_items
                items = normalized_items
                primary = dict((payload.get("assessmentContext") or {}).get("primary") or {})
                if primary and not str(primary.get("textbook") or "").strip():
                    primary["textbook"] = "人教版（PEP·当前最新版）"
                    ctx = dict(payload.get("assessmentContext") or {})
                    ctx["primary"] = primary
                    payload["assessmentContext"] = ctx
            elif subject == "科学":
                items = list(payload.get("items") or items)

            fit_items = [
                item for item in items
                if question_type_is_acceptable(
                    subject,
                    str(item.get("knowledge") or "").strip(),
                    str(item.get("question_type") or "").strip(),
                )
            ]
            if len(fit_items) != len(items):
                payload["notice"] = (
                    str(payload.get("notice") or "").strip("；")
                    + f"；已移除 {len(items)-len(fit_items)} 道题型与知识点不匹配的机械变体。"
                ).strip("；")
            items = fit_items
            payload["items"] = items
            if not items:
                raise HTTPException(
                    502,
                    "AI 生成题型与当前知识点不匹配，请重新生成。",
                )

            db = kwargs.get("db")
            source_keys: set[str] = set()
            source_families: set[str] = set()
            source_aliases: set[str] = set()
            if db is not None and wrong_ids:
                wrong_rows = db.scalars(
                    select(implementation.WrongQuestionRecord).where(
                        implementation.WrongQuestionRecord.id.in_(wrong_ids)
                    )
                ).all()
                for wrong in wrong_rows:
                    source_key = reinforcement_source_key(
                        {
                            "subject": getattr(wrong, "subject", ""),
                            "knowledge": getattr(wrong, "knowledge", ""),
                            "text": getattr(wrong, "problem_text", ""),
                            "question_type": "",
                        }
                    )
                    if source_key:
                        source_keys.add(source_key)

                    question_id = int(getattr(wrong, "question_id", 0) or 0)
                    if not question_id:
                        continue
                    source_question = db.scalar(
                        select(implementation.Question).where(
                            implementation.Question.id == question_id,
                            implementation.Question.school_id == getattr(wrong, "school_id", None),
                        )
                    )
                    if source_question is None:
                        continue
                    try:
                        source_options = json.loads(
                            getattr(source_question, "options_json", "[]") or "[]"
                        )
                    except Exception:
                        source_options = []
                    if not isinstance(source_options, list):
                        source_options = []
                    try:
                        source_meta = implementation.question_answer_meta(source_question)
                    except Exception:
                        source_meta = {}
                    source_item = {
                        "subject": getattr(source_question, "subject", ""),
                        "knowledge": getattr(source_question, "knowledge", ""),
                        "text": getattr(source_question, "text", ""),
                        "question_type": implementation.question_type_of(source_question),
                        "options": source_options,
                        "correct_index": getattr(source_question, "correct_index", -1),
                        "answer": (source_meta or {}).get("answer", ""),
                    }
                    source_families.add(reinforcement_content_family(source_item))
                    source_aliases.update(reinforcement_content_aliases(source_item))

            items, duplicate_count = dedupe_reinforcement_items(
                list(items),
                source_keys=source_keys,
                source_families=source_families,
                source_aliases=source_aliases,
            )
            if not items:
                raise HTTPException(
                    502,
                    "AI 生成题与原题或同批题目内容重复，请重新生成。",
                )
            payload["items"] = items
            if duplicate_count:
                payload["notice"] = (
                    str(payload.get("notice") or "").strip("；")
                    + f"；已自动移除 {duplicate_count} 道与原题或同批题目内容重复的题。"
                ).strip("；")

            if db is not None and wrong_ids:
                valid = db.scalars(
                    select(implementation.WrongQuestionRecord.id).where(
                        implementation.WrongQuestionRecord.id.in_(wrong_ids),
                        implementation.WrongQuestionRecord.subject == subject,
                    )
                ).all()
                payload["wrongIDs"] = [int(x) for x in valid]
            return payload

        route.dependant.call = subject_scoped_route
        route.endpoint = subject_scoped_route
        break

    assign_target = "/teacher/students/{sid}/reinforcement/assign"
    for route in implementation.app.routes:
        if getattr(route, "path", None) != assign_target or "POST" not in getattr(route, "methods", set()):
            continue
        original_assign = route.dependant.call

        @wraps(original_assign)
        def science_textbook_safe_assign(*args: Any, __original=original_assign, **kwargs: Any):
            body = kwargs.get("b")
            if body is None:
                for value in reversed(args):
                    if hasattr(value, "questions"):
                        body = value
                        break

            questions = list(getattr(body, "questions", []) or [])
            mismatched = [
                q for q in questions
                if not question_type_is_acceptable(
                    str(_item_value(q, "subject", "") or "").strip(),
                    str(_item_value(q, "knowledge", "") or "").strip(),
                    str(_item_value(q, "question_type", "") or "").strip(),
                )
            ]
            if mismatched:
                raise HTTPException(
                    400,
                    "针对性练习包含题型与知识点不匹配的机械变体，请重新生成或调整后再布置。",
                )
            unique_questions, duplicate_count = dedupe_reinforcement_items(questions)
            if duplicate_count:
                raise HTTPException(
                    400,
                    "针对性练习包含内容重复的跨题型题目，请删除重复题后再布置。",
                )

            science_textbooks: set[str] = set()
            for question in questions:
                subject = str(getattr(question, "subject", "") or "").strip()
                if subject != "科学":
                    continue
                try:
                    textbook = require_explicit_science_textbook(
                        str(getattr(question, "textbook", "") or "")
                    )
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
                science_textbooks.add(textbook)

            if len(science_textbooks) > 1:
                raise HTTPException(
                    400,
                    "同一次科学针对性练习必须使用同一教材出版社/版本，不能混用。",
                )
            return __original(*args, **kwargs)

        science_textbook_safe_assign._science_textbook_integrity_guard = True
        science_textbook_safe_assign._reinforcement_duplicate_guard = True
        route.dependant.call = science_textbook_safe_assign
        route.endpoint = science_textbook_safe_assign
        break

    implementation._reinforcement_subject_policy_installed = True


__all__ = [
    "AMBIGUOUS_SCIENCE_TEXTBOOKS",
    "augment_reinforcement_prompt",
    "dedupe_reinforcement_items",
    "explicit_science_textbook",
    "install_reinforcement_subject_policy",
    "normalize_science_reinforcement_items",
    "require_explicit_science_textbook",
    "reinforcement_content_aliases",
    "reinforcement_content_family",
    "reinforcement_source_key",
    "reinforcement_source_stem",
    "reinforcement_subject_from_prompt",
    "scope_context_to_primary_subject",
]
