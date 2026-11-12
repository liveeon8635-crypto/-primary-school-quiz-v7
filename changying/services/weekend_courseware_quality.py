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


def _premature_rule(steps: list[str]) -> bool:
    """Flag obvious immediate explanation where the pupil should observe first."""
    if not steps:
        return False
    first = _text(steps[0])
    return bool(re.search(
        r"(?:月历|百数表|同行|同列|同一行|同一列).{0,26}(?:相差|差为|加[+＋]?\d+|减[−-]?\d+)",
        first,
    )) and not bool(re.search(r"(?:想一想|观察|比较|试一试|找一找|你认为|请判断|怎样|多少|什么)", first))


def _figure_exposes_choice(figure: dict[str, Any]) -> bool:
    """The diagram should display question conditions, not a solved A/B/C/D key."""
    if figure.get("type") != "table":
        return False
    rows = figure.get("rows") or []
    return any(
        bool(re.search(r"(?:^|[：:])(?:正确|错误|故选|答案是|答案为)", str(cell)))
        for row in rows if isinstance(row, list)
        for cell in row
    )


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
        approved = item.get("approved") if item and isinstance(item.get("approved"), dict) else None
        draft = item.get("params") if item and isinstance(item.get("params"), dict) else {}
        # The approved snapshot is what the classroom sees; do not mistake a
        # newer, unfinished teacher draft for the quality of the live lesson.
        saved = approved if approved is not None else draft
        figure = saved.get("figure") if isinstance(saved.get("figure"), dict) else {}
        figure_type = str(figure.get("type") or "")
        steps = saved.get("steps") if isinstance(saved.get("steps"), list) else []
        answer = _text(saved.get("answer"))

        if not item:
            problems.append("尚未配置互动课件")
        else:
            if approved is None:
                problems.append("课件尚未审核通过")
            if item.get("pageText") and _text(item["pageText"]) != _text(source):
                problems.append("课件绑定的原题与当前教案不一致")
            if item.get("approvedPageText") and _text(item["approvedPageText"]) != _text(source):
                problems.append("已审核课件对应的原题发生变化")
            if approved is not None and draft != approved:
                warnings.append("存在新草稿：课堂版本与当前编辑版本不同")
            if _figure_exposes_choice(figure):
                problems.append("图示中含直接判断结论，可能提前泄露选择题答案")
            if not figure_type and expected:
                problems.append("此题需要图示，但当前课件没有可核对的教学图示")
            elif not figure_type and re.search(r"如图|下图|图中|图上|看图|观察.{0,12}图|①②③④", source):
                problems.append("原题要求观察图形，但课件无图；请对照原练习补绘后再审核")
            elif figure_type == "uploaded_image":
                warnings.append("当前只有原卷图片，尚需独立教学图示")
            elif expected and figure_type != expected:
                problems.append("图示类型与题型不匹配（期望：" + expected + "）")
            if ("灯笼锦" in source or "正八边形" in source) and figure_type == "table":
                warnings.append("八边形数量题目前只有数表，请核对原题排列图后再决定是否补图")
            if ("计算小程序" in source or ("输入" in source and "输出" in source)) and figure_type == "table":
                warnings.append("计算程序题目前只有数表，如原课件没有程序流向图可酌情补充")
            if figure_type == "table" and ("3×3" in source or "3x3" in source) and not figure.get("nineGrid"):
                warnings.append("九宫格仍使用普通表格，需核对是否缺少分步高亮")
            if figure_type == "table" and any(word in source for word in ("大小正方形", "大正方形", "长方形拼", "拼成长方形")):
                warnings.append("空间拼接题仅有数表，建议核对是否缺少实际拼接图")
            if expected == "parallelogram_methods" and re.search(
                    r"待教师确认|原题未提供|图示缺失|看不到图|无法判断", answer):
                problems.append("四种方法图已补绘，但教师答案仍为待确认；请对照原题逐项核实")
            if item.get("kind") == "steps":
                if expected and len(steps) < 4:
                    warnings.append("此规律/图形题分步不足四步，可核对是否缺少观察、探索或验证")
                if not answer:
                    problems.append("缺少教师参考答案")
                if _first_step_reveals_solution([str(x) for x in steps], answer):
                    problems.append("第一步可能提前暴露答案")
                elif _premature_rule([str(x) for x in steps]):
                    warnings.append("第一步直接讲出规律，建议改为观察性提问")
            else:
                warnings.append("非通用分步课件，应人工核对专用交互是否完整")
            if not expected and figure_type:
                warnings.append("此题未配置专用图示规则；该提示不阻止审核，但请按原题核对")

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
