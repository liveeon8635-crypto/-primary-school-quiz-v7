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
2. 语文可用题型为 single_choice、true_false、fill_blank、short_answer；不要使用 calculation。5题以上尽量覆盖至少3种题型，但准确性优先。
3. fill_blank 只用于存在明确、可自动判定答案的字词、关联词、标点或短语；short_answer 只用于答案简短、唯一或可枚举等价答案的内容。开放性阅读感受、习作、长篇表达不得自动判分，遇到这类知识点应改写成客观题或明确评分点的短答。
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
            db = kwargs.get("db")
            if db is None or not wrong_ids:
                return result
            valid = db.scalars(
                select(implementation.WrongQuestionRecord.id).where(
                    implementation.WrongQuestionRecord.id.in_(wrong_ids),
                    implementation.WrongQuestionRecord.subject == subject,
                )
            ).all()
            payload = dict(result)
            payload["wrongIDs"] = [int(x) for x in valid]
            return payload

        route.dependant.call = subject_scoped_route
        route.endpoint = subject_scoped_route
        break

    implementation._reinforcement_subject_policy_installed = True


__all__ = [
    "augment_reinforcement_prompt",
    "install_reinforcement_subject_policy",
    "reinforcement_subject_from_prompt",
    "scope_context_to_primary_subject",
]
