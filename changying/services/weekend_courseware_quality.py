"""Conservative, read-only quality audit for every weekend worked-example page.

The checks flag detectable gaps; they do not certify semantic correctness or
replace a teacher's comparison with the original question and image.
No database reads or mutations occur in this module.
"""
from __future__ import annotations

import re
from typing import Any, Callable


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _first_step_reveals_solution(steps: list[str], answer: str) -> bool:
    """High-precision heuristic. Avoid inferring knowledge from arbitrary digits."""
    if not steps or not answer:
        return False
    first = _text(steps[0])
    cleaned_answer = _text(answer)
    if len(cleaned_answer) >= 3 and cleaned_answer in first:
        return True
    return bool(re.search(r"(?:正确答案|最终答案|故选|因此选|所以选|答案[是为：:])\s*[A-D](?:\b|[。！；])", first))


def audit_example_pages(
    pages: list[str],
    items: list[dict[str, Any]],
    required_visual_type: Callable[[str], str],
    *,
    stage: int = 3,
) -> dict[str, Any]:
    """Audit *all* pages in a stage; never turn skipped/unmatched pages into success."""
    by_page = {
        int(item["page"]): item
        for item in items
        if isinstance(item, dict)
        and item.get("page") is not None
        and item.get("stage") is not None
        and int(item["stage"]) == stage
        and 0 <= int(item["page"]) < len(pages)
    }
    reports: list[dict[str, Any]] = []
    for index, source in enumerate(pages):
        item = by_page.get(index)
        problems: list[str] = []
        warnings: list[str] = []
        expected = required_visual_type(source)
        saved = item.get("params") if item and isinstance(item.get("params"), dict) else {}
        figure = saved.get("figure") if isinstance(saved.get("figure"), dict) else {}
        figure_type = str(figure.get("type") or "")
        steps = saved.get("steps") if isinstance(saved.get("steps"), list) else []
        answer = _text(saved.get("answer"))
        approved = item.get("approved") if item else None

        if not item:
            problems.append("尚未配置互动课件")
        else:
            if approved is None:
                problems.append("课件尚未审核通过")
            if item.get("pageText") and _text(item["pageText"]) != _text(source):
                problems.append("课件绑定的原题与当前教案不一致")
            if item.get("approvedPageText") and _text(item["approvedPageText"]) != _text(source):
                problems.append("已审核课件对应的原题发生变化")
            if not figure_type:
                problems.append("没有可核对的教学图示")
            elif figure_type == "uploaded_image":
                warnings.append("当前只有原卷图片，尚需独立教学图示")
            elif expected and figure_type != expected:
                problems.append("图示类型与题型不匹配（期望：" + expected + "）")
            if item.get("kind") == "steps":
                if len(steps) < 4:
                    warnings.append("分步引导不足四步，请核对观察、探索、表达和验证过程")
                if not answer:
                    problems.append("缺少教师参考答案")
                if _first_step_reveals_solution([str(x) for x in steps], answer):
                    problems.append("第一步可能提前暴露答案")
            else:
                warnings.append("非通用分步课件，应人工核对专用交互是否完整")
            if not expected:
                warnings.append("未命中已知图示规则，必须对照原题人工确认图示")

        # A check with zero machine-detectable issues still needs content review.
        reports.append({
            "page": index,
            "label": "例题" + str(index + 1),
            "title": _text(source)[:80],
            "status": "missing" if not item else ("needs_fix" if problems else "needs_teacher_review"),
            "figureType": figure_type,
            "expectedFigureType": expected,
            "approved": approved is not None,
            "issues": problems,
            "warnings": warnings,
            "manualReviewRequired": True,
        })
    return {
        "stage": stage,
        "totalPages": len(pages),
        "configured": sum(1 for report in reports if report["status"] != "missing"),
        "flagged": sum(1 for report in reports if report["issues"]),
        "manualReviewRequired": len(pages),
        "pages": reports,
        "note": "机器检查只发现可识别问题；数学正确性、原题忠实性、教学效果须逐题审核，不等于自动验收通过。",
    }
