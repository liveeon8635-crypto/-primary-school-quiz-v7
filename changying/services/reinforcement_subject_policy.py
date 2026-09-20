"""Subject-aware policy for AI reinforcement generation.

The legacy reinforcement endpoint already preserves grade/subject/textbook from
assessment context. This module tightens the generation contract so a Chinese
assessment cannot be biased by the mathematical examples in the shared prompt.
"""

from __future__ import annotations

import re
from types import ModuleType
from typing import Any

from sqlalchemy import select


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


def normalize_science_reinforcement_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep science reinforcement auto-gradable and free of math-only figures."""
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
        row["figure"] = {}
        result.append(row)
    return result


def scope_context_to_primary_subject(context: dict[str, Any]) -> dict[str, Any]:
    """Keep one reinforcement generation cycle inside a single school subject."""
    if not isinstance(context, dict):
        return context
    primary = dict(context.get("primary") or {})
    subject = str(primary.get("subject") or "").strip()
    if not subject:
        return context
    assessments = [
        x for x in (context.get("assessments") or [])
        if str((x or {}).get("subject") or "").strip() == subject
    ]
    weak = [
        x for x in (context.get("weakKnowledge") or [])
        if str((x or {}).get("subject") or "").strip() == subject
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
                normalized_items = normalize_science_reinforcement_items(items)
                payload["items"] = normalized_items
                if len(normalized_items) != len(items):
                    payload["notice"] = (
                        str(payload.get("notice") or "")
                        + "；科学针对性练习已移除不适合自动判分的开放题型。"
                    ).strip("；")
            if subject == "英语":
                normalized_items = []
                for item in items:
                    row = dict(item)
                    row["textbook"] = "人教版（PEP·当前最新版）"
                    row["figure"] = {}
                    normalized_items.append(row)
                payload["items"] = normalized_items
                primary = dict((payload.get("assessmentContext") or {}).get("primary") or {})
                if primary and not str(primary.get("textbook") or "").strip():
                    primary["textbook"] = "人教版（PEP·当前最新版）"
                    ctx = dict(payload.get("assessmentContext") or {})
                    ctx["primary"] = primary
                    payload["assessmentContext"] = ctx

            db = kwargs.get("db")
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

    implementation._reinforcement_subject_policy_installed = True


__all__ = [
    "augment_reinforcement_prompt",
    "install_reinforcement_subject_policy",
    "normalize_science_reinforcement_items",
    "reinforcement_subject_from_prompt",
    "scope_context_to_primary_subject",
]
