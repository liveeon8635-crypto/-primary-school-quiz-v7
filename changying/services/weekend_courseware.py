"""Interactive weekend courseware: two reviewed templates filled with validated parameters.

AI (or the teacher) only supplies structured parameters; the page code is fixed and reviewed. Nothing
here produces HTML or script from AI output, and playing a courseware in class never calls AI.

rotation  数学·图形旋转：grid, shape points, centre, direction, angle -> original and rotated figure
reading   语文·文本依据：an excerpt of the lesson's own reading text split into sentences, the question,
          supplementary material and a written-explanation prompt; evidence sentences and the reference
          answer stay teacher-only.
"""
from __future__ import annotations

import json
import re
from typing import Any

KINDS = {"数学": "rotation", "语文": "reading"}
KIND_LABEL = {"rotation": "数学·图形旋转", "reading": "语文·阅读与文本依据"}
ANGLES = (90, 180, 270)
LETTERS = "ABCDEF"


def _text(value: Any, limit: int) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")).strip()[:limit]


def _int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("坐标必须是整数")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("坐标必须是整数")
    if number != int(number):
        raise ValueError("坐标必须是整数")
    return int(number)


def rotate_point(point: list[int], center: list[int], direction: str, angle: int) -> list[int]:
    """Exact rotation on the grid (y axis pointing up); angle is a multiple of 90."""
    x, y = point[0] - center[0], point[1] - center[1]
    turns = (angle // 90) % 4
    if direction == "ccw":
        turns = (4 - turns) % 4
    for _ in range(turns):          # one clockwise quarter turn: (x, y) -> (y, -x)
        x, y = y, -x
    return [center[0] + x, center[1] + y]


def clean_rotation(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("课件参数格式不正确")
    try:
        width, height = _int(raw.get("width", 10)), _int(raw.get("height", 10))
    except ValueError:
        raise ValueError("网格大小必须是整数")
    if not (6 <= width <= 12 and 6 <= height <= 12):
        raise ValueError("网格大小需在 6—12 格之间")
    points = raw.get("shape")
    if not isinstance(points, list) or not 3 <= len(points) <= 6:
        raise ValueError("原图需要 3—6 个顶点")
    shape = []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError("每个顶点需要两个坐标")
        x, y = _int(p[0]), _int(p[1])
        if not (0 <= x <= width and 0 <= y <= height):
            raise ValueError("顶点超出网格")
        shape.append([x, y])
    if len({tuple(p) for p in shape}) != len(shape):
        raise ValueError("顶点不能重复")
    c = raw.get("center")
    if not isinstance(c, (list, tuple)) or len(c) != 2:
        raise ValueError("请给出旋转中心")
    center = [_int(c[0]), _int(c[1])]
    if not (0 <= center[0] <= width and 0 <= center[1] <= height):
        raise ValueError("旋转中心超出网格")
    direction = str(raw.get("direction") or "")
    if direction not in ("cw", "ccw"):
        raise ValueError("旋转方向只能是顺时针或逆时针")
    try:
        angle = _int(raw.get("angle"))
    except ValueError:
        raise ValueError("旋转角度只能是 90°、180° 或 270°")
    if angle not in ANGLES:
        raise ValueError("旋转角度只能是 90°、180° 或 270°")
    rotated = [rotate_point(p, center, direction, angle) for p in shape]
    if any(not (0 <= x <= width and 0 <= y <= height) for x, y in rotated):
        raise ValueError("旋转后的图形超出网格，请调整中心或图形位置")
    steps = [_text(s, 80) for s in (raw.get("steps") or []) if _text(s, 80)][:5]
    return {"title": _text(raw.get("title"), 40) or "图形的旋转", "width": width, "height": height, "shape": shape,
            "center": center, "direction": direction, "angle": angle, "rotated": rotated,
            "steps": steps or ["找准旋转中心", "看清旋转方向", "确定旋转角度", "逐个顶点旋转后连线"],
            "question": _text(raw.get("question"), 200) or "写出旋转后各顶点的坐标，并说明你是怎样确定的。",
            "reference": _text(raw.get("reference"), 1000)}


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def sentences(passage: str) -> list[str]:
    parts = re.findall(r"[^。！？；!?;\n]+[。！？；!?;]?[”」』]?", passage)
    return [p.strip() for p in parts if p.strip()][:60]


def clean_reading(raw: Any, source_text: str) -> dict[str, Any]:
    """The passage must be the lesson's own reading text, word for word (whitespace aside)."""
    if not isinstance(raw, dict):
        raise ValueError("课件参数格式不正确")
    passage = _text(raw.get("passage"), 3000)
    if len(_squash(passage)) < 40:
        raise ValueError("请从原文中摘取不少于40字的阅读材料")
    if not source_text.strip() or _squash(passage) not in _squash(source_text):
        raise ValueError("阅读材料必须是本课教案原文中的连续段落，不能改写或编造")
    parts = sentences(passage)
    if len(parts) < 2:
        raise ValueError("阅读材料至少需要两句")
    evidence = sorted({_int(i) for i in (raw.get("evidence") or [])})
    if not evidence or any(not 0 <= i < len(parts) for i in evidence):
        raise ValueError("请在原文中选出至少一句文本依据")
    question = _text(raw.get("question"), 200)
    if not question:
        raise ValueError("请填写阅读问题")
    return {"title": _text(raw.get("title"), 40) or "找文本依据", "passage": passage, "sentences": parts, "question": question,
            "evidence": evidence, "material": _text(raw.get("material"), 600),
            "writingPrompt": _text(raw.get("writingPrompt"), 200) or "摘录你找到的原文依据，再用自己的话写出解释。",
            "reference": _text(raw.get("reference"), 1000)}


def clean(kind: str, raw: Any, source_text: str = "") -> dict[str, Any]:
    if kind == "rotation":
        return clean_rotation(raw)
    if kind == "reading":
        return clean_reading(raw, source_text)
    raise ValueError("暂只支持数学图形旋转和语文文本依据两种课件")


def public_params(kind: str, params: dict[str, Any]) -> dict[str, Any]:
    """What the classroom screen receives: no reference answer, no evidence key."""
    hidden = {"reference", "evidence"} if kind == "reading" else {"reference"}
    return {k: v for k, v in params.items() if k not in hidden}


def clean_view(kind: str, params: dict[str, Any], raw: Any) -> dict[str, Any]:
    """The teacher's live screen state; small, validated, no AI."""
    raw = raw if isinstance(raw, dict) else {}
    if kind == "rotation":
        try:
            angle, step = _int(raw.get("angle", 0)), _int(raw.get("step", 0))
        except ValueError:
            angle, step = 0, 0
        return {"angle": max(0, min(int(params["angle"]), angle)), "showOriginal": bool(raw.get("showOriginal", True)),
                "showResult": bool(raw.get("showResult")), "showCenter": bool(raw.get("showCenter", True)),
                "step": max(0, min(len(params["steps"]), step))}
    count = len(params["sentences"])
    marks = []
    for i in raw.get("highlight") or []:
        try:
            i = _int(i)
        except ValueError:
            continue
        if 0 <= i < count and i not in marks:
            marks.append(i)
    return {"highlight": marks[:20], "showMaterial": bool(raw.get("showMaterial")), "showPrompt": bool(raw.get("showPrompt"))}


def written_question(kind: str, params: dict[str, Any]) -> tuple[str, str]:
    """The pupils' task for the existing written answer flow (text/photo, teacher-reviewed)."""
    if kind == "rotation":
        names = LETTERS[: len(params["shape"])]
        points = "、".join(f"{n}({x},{y})" for n, (x, y) in zip(names, params["shape"]))
        cx, cy = params["center"]
        way = "顺时针" if params["direction"] == "cw" else "逆时针"
        stem = (f"在 {params['width']}×{params['height']} 的方格纸上，图形顶点为 {points}。"
                f"把图形绕点 O({cx},{cy}) {way}旋转 {params['angle']}°。\n\n{params['question']}")
        result = "、".join(f"{n}′({x},{y})" for n, (x, y) in zip(names, params["rotated"]))
        reference = f"旋转后顶点：{result}。" + (f"\n{params['reference']}" if params["reference"] else "")
        return stem, reference
    material = f"\n\n补充资料：{params['material']}" if params["material"] else ""
    stem = f"{params['passage']}{material}\n\n{params['question']}{params['writingPrompt']}"
    evidence = "；".join(params["sentences"][i] for i in params["evidence"])
    reference = f"文本依据：{evidence}" + (f"\n{params['reference']}" if params["reference"] else "")
    return stem, reference


def generation_prompt(kind: str, lesson: dict[str, Any]) -> str:
    """Structured parameters only; the model never writes markup or code."""
    base = f"课题：{lesson['title']}\n教学目标：{lesson['coreTarget']}\n教学流程：{lesson['teacherPlan'][:3000]}\n"
    if kind == "rotation":
        return ("你是小学数学教师，为“图形的旋转”设计一个课堂演示。只输出 JSON，不要 HTML、代码或 Markdown。\n" + base +
                "要求：网格 width、height 为 6—12 的整数；shape 为 3—6 个整数顶点坐标（y 轴向上）；center 为整数旋转中心；"
                "direction 为 cw（顺时针）或 ccw（逆时针）；angle 为 90、180 或 270；旋转后图形必须仍在网格内；"
                "steps 为 3—5 条讲解步骤（每条不超过40字）；question 为学生书面作答的问题；reference 为给老师的评分要点。\n"
                '格式：{"title":"","width":10,"height":10,"shape":[[2,2],[5,2],[2,4]],"center":[2,2],"direction":"cw","angle":90,'
                '"steps":[""],"question":"","reference":""}')
    return ("你是小学语文教师，为本课设计一个“找文本依据”的课堂活动。只输出 JSON，不要 HTML、代码或 Markdown。\n" + base +
            "本课原文：\n" + lesson["sourceText"][:6000] +
            "\n要求：passage 必须从上面原文中原样摘取一段连续文字（40—600字），不得改写；question 是需要用原文依据回答的问题；"
            "evidence 是 passage 按句号、问号、感叹号、分号或换行切分后，作为依据的句子序号（从0开始）；material 是帮助理解的补充资料"
            "（不超过150字，只写确定的常识，没有就留空）；writingPrompt 是书面解释要求；reference 是给老师的评分要点。\n"
            '格式：{"title":"","passage":"","question":"","evidence":[0],"material":"","writingPrompt":"","reference":""}')
