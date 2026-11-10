"""Interactive weekend courseware: reviewed templates filled with validated parameters.

AI (or the teacher) only supplies structured parameters; the page code is fixed and reviewed. Nothing
here produces HTML or script from AI output, and playing a courseware in class never calls AI.

rotation  数学·图形旋转：grid, shape points, centre, direction, angle -> original and rotated figure
reading   语文·文本依据：an excerpt of the lesson's own reading text split into sentences, the question,
          supplementary material and a written-explanation prompt; evidence sentences and the reference
          answer stay teacher-only.
clock     数学·钟面指针旋转：start number, direction, angle (multiple of 30°) -> the number the hand points to
steps     通用·分步讲解：the page's own worked example revealed step by step, then the answer; fits any example.
          It may carry one figure drawn by the page (never an image from AI): points on a segment, a program
          flowchart (with up to two branches), a labelled shape, or a small table.

A lesson may have one courseware per slide/example page; the AI picks the best fitting template per page.
"""
from __future__ import annotations

import json
import re
from typing import Any

TEMPLATES = {"数学": ("rotation", "clock", "steps"), "语文": ("reading", "steps")}
KIND_LABEL = {"rotation": "数学·图形旋转", "reading": "语文·阅读与文本依据", "clock": "数学·钟面指针旋转", "steps": "分步讲解"}
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


def clock_end(start: int, direction: str, angle: int) -> int:
    turns = (angle // 30) * (1 if direction == "cw" else -1)
    return (start - 1 + turns) % 12 + 1


def clean_clock(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("课件参数格式不正确")
    try:
        start, angle = _int(raw.get("start")), _int(raw.get("angle"))
    except ValueError:
        raise ValueError("起始数字和角度必须是整数")
    if not 1 <= start <= 12:
        raise ValueError("起始数字需在 1—12 之间")
    if angle % 30 or not 30 <= angle <= 360:
        raise ValueError("钟面旋转角度需是 30° 的整数倍（30°—360°）")
    direction = str(raw.get("direction") or "")
    if direction not in ("cw", "ccw"):
        raise ValueError("旋转方向只能是顺时针或逆时针")
    steps = [_text(s, 80) for s in (raw.get("steps") or []) if _text(s, 80)][:5]
    return {"title": _text(raw.get("title"), 40) or "钟面上的旋转", "start": start, "direction": direction, "angle": angle,
            "end": clock_end(start, direction, angle),
            "steps": steps or ["钟面一圈 360°，每两个数字之间 30°", "看清旋转方向", "算出转过几个大格"],
            "question": _text(raw.get("question"), 200) or "指针旋转后指向数字几？写出你的想法。", "reference": _text(raw.get("reference"), 1000)}


FIGURE_SHAPES = {"rectangle": "长方形", "square": "正方形", "triangle": "三角形", "parallelogram": "平行四边形", "trapezoid": "梯形"}
SHAPE_SIDES = ("top", "bottom", "left", "right", "height")


def _boxes(raw: Any, least: int) -> list[str]:
    boxes = [_text(b, 14) for b in (raw if isinstance(raw, list) else []) if _text(b, 14)]
    if not least <= len(boxes) <= 7:
        raise ValueError(f"程序图每一行需要 {least}—7 个框")
    return boxes


def clean_figure(raw: Any) -> dict[str, Any]:
    """One figure for a worked example, as data only; {} when there is none."""
    if raw in (None, {}, ""):
        return {}
    if not isinstance(raw, dict):
        raise ValueError("图示格式不正确")
    kind = str(raw.get("type") or "")
    if kind == "uploaded_image":
        url = str(raw.get("data_url") or "")
        if len(url) > 700000 or not re.fullmatch(r"data:image/jpeg;base64,[A-Za-z0-9+/]+={0,2}", url):
            raise ValueError("原卷图片格式不正确")
        return {"type": "uploaded_image", "data_url": url, "alt": _text(raw.get("alt"), 80) or "原卷插图"}
    if kind == "segment":
        points, seen = [], set()
        for p in raw.get("points") if isinstance(raw.get("points"), list) else []:
            if not isinstance(p, dict):
                raise ValueError("线段上的点需要名称和位置")
            name = _text(p.get("name"), 3)
            try:
                at = float(p.get("at"))
            except (TypeError, ValueError):
                raise ValueError(f"点 {name or '?'} 的位置必须是数")
            if not name or name in seen or not 0 <= at <= 1000:
                raise ValueError("线段上的点名称不能为空或重复，位置在 0—1000 之间")
            seen.add(name)
            points.append({"name": name, "at": at})
        if not 2 <= len(points) <= 8:
            raise ValueError("线段图需要 2—8 个点")
        points.sort(key=lambda p: p["at"])
        if points[0]["at"] == points[-1]["at"]:
            raise ValueError("线段图的点不能都在同一位置")
        marks = []
        for m in (raw.get("marks") if isinstance(raw.get("marks"), list) else [])[:6]:
            if not isinstance(m, dict):
                continue
            a, b, label = _text(m.get("from"), 3), _text(m.get("to"), 3), _text(m.get("label"), 12)
            if a not in seen or b not in seen or a == b or not label:
                raise ValueError("线段标注需要两个已有的点和文字")
            marks.append({"from": a, "to": b, "label": label})
        return {"type": "segment", "points": points, "marks": marks}
    if kind == "flow":
        branches = []
        for br in (raw.get("branches") if isinstance(raw.get("branches"), list) else [])[:2]:
            if not isinstance(br, dict) or not _text(br.get("when"), 16):
                raise ValueError("程序图的分支需要写条件")
            branches.append({"when": _text(br.get("when"), 16), "boxes": _boxes(br.get("boxes"), 1)})
        if len(branches) == 1:
            raise ValueError("分支程序需要两种情况")
        return {"type": "flow", "boxes": _boxes(raw.get("boxes"), 1 if branches else 2), "branches": branches}
    if kind == "shape":
        shape = str(raw.get("shape") or "")
        if shape not in FIGURE_SHAPES:
            raise ValueError("图形只能是长方形、正方形、三角形、平行四边形或梯形")
        labels = raw.get("labels") if isinstance(raw.get("labels"), dict) else {}
        return {"type": "shape", "shape": shape, "labels": {k: _text(labels.get(k), 12) for k in SHAPE_SIDES if _text(labels.get(k), 12)}}
    if kind == "table":
        rows = [[_text(c, 10) for c in r[:8]] for r in (raw.get("rows") if isinstance(raw.get("rows"), list) else [])[:5]
                if isinstance(r, list) and any(_text(c, 10) for c in r)]
        if len(rows) < 2 or len({len(r) for r in rows}) != 1 or len(rows[0]) < 2:
            raise ValueError("表格需要至少 2 行、2 列，并且每行格数相同")
        return {"type": "table", "rows": rows}
    if kind == "seating_pattern":
        try:
            sample_counts = [_int(v) for v in raw.get("sampleCounts", [])]
        except (TypeError, ValueError):
            raise ValueError("方桌人数样例必须是整数")
        if not 2 <= len(sample_counts) <= 4 or sample_counts[0] != 8 or any(
                sample_counts[i] - sample_counts[i - 1] != 4 for i in range(1, len(sample_counts))):
            raise ValueError("方桌图需从 1 张桌 8 人开始，每增加 1 张桌增加 4 人")
        return {"type": "seating_pattern", "sampleCounts": sample_counts}
    if kind == "alternating_triangle":
        try:
            rows = _int(raw.get("rows", 6))
        except ValueError:
            raise ValueError("棋子三角形层数必须是整数")
        symbol = _text(raw.get("differenceSymbol", "m"), 1) or "m"
        if rows < 4 or rows > 8 or rows % 2:
            raise ValueError("棋子三角形示意层数需为 4、6 或 8 层")
        if not re.fullmatch(r"[A-Za-z]", symbol):
            raise ValueError("黑白棋子差值只能使用一个英文字母")
        return {"type": "alternating_triangle", "rows": rows, "differenceSymbol": symbol}
    if kind == "running_track":
        try:
            fast = _int(raw.get("fastSpeed"))
            slow = _int(raw.get("slowSpeed"))
        except ValueError:
            raise ValueError("跑步速度必须是整数")
        if not 1 <= slow < fast <= 1000:
            raise ValueError("跑道题需满足 1—1000 的整数速度，且快者速度大于慢者")
        distance_symbol = _text(raw.get("distanceSymbol", "s"), 1) or "s"
        if not re.fullmatch(r"[A-Za-z]", distance_symbol):
            raise ValueError("跑道长度只能使用一个英文字母表示")
        return {"type": "running_track", "fastSpeed": fast, "slowSpeed": slow,
                "distanceSymbol": distance_symbol}
    if kind == "triangular_numbers":
        try:
            terms = [_int(v) for v in raw.get("terms", [1, 3, 6, 10, 15])]
            target_term = _int(raw.get("targetTerm", 10))
        except (TypeError, ValueError):
            raise ValueError("三角形数样例必须是整数")
        if not 3 <= len(terms) <= 6 or any(value != i * (i + 1) // 2 for i, value in enumerate(terms, 1)):
            raise ValueError("三角形数样例必须从 1、3、6、10、15…按规律递增")
        if not 2 <= target_term <= 100:
            raise ValueError("要计算的项数需在 2—100 之间")
        return {"type": "triangular_numbers", "terms": terms, "targetTerm": target_term}
    if kind == "tile_pattern":
        try:
            white = [_int(v) for v in raw.get("whiteCounts", [5, 8])]
            blue = [_int(v) for v in raw.get("blueCounts", [4, 7])]
            target_term = _int(raw.get("targetTerm", 10))
            target_blue = _int(raw.get("targetBlue", 100))
        except (TypeError, ValueError):
            raise ValueError("地砖样例数量必须是整数")
        if len(white) != 2 or len(blue) != 2 or any(not 1 <= n <= 100 for n in white + blue):
            raise ValueError("地砖样例需填写前两幅的白砖、蓝砖数量")
        if white[1] <= white[0] or blue[1] <= blue[0]:
            raise ValueError("两种地砖数量都应逐幅增加")
        if not 1 <= target_term <= 100 or not 1 <= target_blue <= 10000:
            raise ValueError("地砖规律题的目标幅数或砖数超出范围")
        return {"type": "tile_pattern", "whiteCounts": white, "blueCounts": blue,
                "targetTerm": target_term, "targetBlue": target_blue}
    if kind == "calendar_cross":
        try:
            center = _int(raw.get("center"))
            days = _int(raw.get("daysInMonth", 31))
            first_weekday = _int(raw.get("firstWeekday", 0))
            total = _int(raw.get("total"))
        except ValueError:
            raise ValueError("月历十字框参数必须是整数")
        if not 28 <= days <= 31 or not 0 <= first_weekday <= 6:
            raise ValueError("月历天数需为 28—31，首日星期需为 0—6")
        if total <= 0 or total % 5:
            raise ValueError("五数和必须是大于零且能被 5 整除的数")
        if center != total // 5:
            raise ValueError("五数和必须是中心数的 5 倍，请核对题目数据")
        if not 8 <= center <= days - 7:
            raise ValueError("十字框中心日期必须有完整的上一周、下一周和相邻日期")
        if (first_weekday + center - 1) % 7 in (0, 6):
            raise ValueError("十字框中心不能位于星期日或星期六")
        return {"type": "calendar_cross", "center": center, "daysInMonth": days,
                "firstWeekday": first_weekday, "total": total}
    raise ValueError("图示类型无效，请选择线段图、程序图、图形、表格、方桌规律图或黑白棋子三角形")


def clean_steps(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("课件参数格式不正确")
    steps = [_text(s, 120) for s in (raw.get("steps") or []) if _text(s, 120)]
    if not 2 <= len(steps) <= 6:
        raise ValueError("分步讲解需要 2—6 步")
    answer = _text(raw.get("answer"), 200)
    if not answer:
        raise ValueError("请填写例题答案")
    figure = clean_figure(raw.get("figure"))
    if figure.get("type") in ("calendar_cross", "seating_pattern", "alternating_triangle", "running_track", "triangular_numbers", "tile_pattern") and len(steps) < 4:
        raise ValueError("这类规律题的互动图示需要至少 4 步，才能逐步展示规律和结论")
    return {"title": _text(raw.get("title"), 40) or "分步讲解", "steps": steps, "answer": answer,
            "problem": _text(raw.get("problem"), 600),        # the example's own question, without its answer (pupils' task)
            "figure": figure, "sourceFigure": clean_figure(raw.get("sourceFigure")),
            "question": _text(raw.get("question"), 200) or "写出解题过程和答案。", "reference": _text(raw.get("reference"), 1000)}


def clean(kind: str, raw: Any, source_text: str = "") -> dict[str, Any]:
    if kind == "rotation":
        return clean_rotation(raw)
    if kind == "reading":
        return clean_reading(raw, source_text)
    if kind == "clock":
        return clean_clock(raw)
    if kind == "steps":
        result = clean_steps(raw)
        source_problem = str(raw.get('sourceProblem') or '') if isinstance(raw, dict) else ''
        if source_problem:
            from changying.services.weekend_presentation import literal_numbered_questions
            if len(source_problem) > 2000 or not any(source_problem in q for q in literal_numbered_questions(source_text)):
                raise ValueError('原题与教案原文不一致，请重新核对')
            result['sourceProblem'] = source_problem
        return result
    raise ValueError("没有这种课件模板")


def public_params(kind: str, params: dict[str, Any]) -> dict[str, Any]:
    """What the classroom screen receives: no reference answer, no evidence key."""
    hidden = {"reference", "evidence"} if kind == "reading" else {"reference"}
    return {k: v for k, v in params.items() if k not in hidden}


def clean_view(kind: str, params: dict[str, Any], raw: Any) -> dict[str, Any]:
    """The teacher's live screen state; small, validated, no AI."""
    raw = raw if isinstance(raw, dict) else {}
    try:
        angle, step = _int(raw.get("angle", 0)), _int(raw.get("step", 0))
    except ValueError:
        angle, step = 0, 0
    if kind == "rotation":
        return {"angle": max(0, min(int(params["angle"]), angle)), "showOriginal": bool(raw.get("showOriginal", True)),
                "showResult": bool(raw.get("showResult")), "showCenter": bool(raw.get("showCenter", True)),
                "step": max(0, min(len(params["steps"]), step))}
    if kind == "clock":
        return {"angle": max(0, min(int(params["angle"]), angle)), "showResult": bool(raw.get("showResult")),
                "step": max(0, min(len(params["steps"]), step))}
    if kind == "steps":
        return {"step": max(0, min(len(params["steps"]), step)), "showAnswer": bool(raw.get("showAnswer"))}
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


def written_question(kind: str, params: dict[str, Any], page_text: str = "") -> tuple[str, str]:
    """The pupils' task for the existing written answer flow (text/photo, teacher-reviewed)."""
    if kind == "clock":
        way = "顺时针" if params["direction"] == "cw" else "逆时针"
        stem = f"钟面上的指针从数字 {params['start']} 出发，{way}旋转 {params['angle']}°。\n\n{params['question']}"
        return stem, f"指向数字 {params['end']}。" + (f"\n{params['reference']}" if params["reference"] else "")
    if kind == "steps":
        # Never the board page itself: worked-example pages often carry their answer.
        if not params.get("problem"):
            raise ValueError("要生成学生作答题，请先填写这道例题的题目原文（不含答案）")
        stem = params["problem"] + "\n\n" + params["question"]
        reference = "；".join(params["steps"]) + f"\n答案：{params['answer']}" + (f"\n{params['reference']}" if params["reference"] else "")
        return stem, reference
    if kind == "rotation":
        names = LETTERS[: len(params["shape"])]
        points = "、".join(f"{n}({x},{y})" for n, (x, y) in zip(names, params["shape"]))
        cx, cy = params["center"]
        way = "顺时针" if params["direction"] == "cw" else "逆时针"
        on = next((n for n, p in zip(names, params["shape"]) if p == params["center"]), "")
        center = f"点 {on}" if on else f"点 O({cx},{cy})"
        stem = (f"在 {params['width']}×{params['height']} 的方格纸上，图形顶点为 {points}。"
                f"把图形绕{center} {way}旋转 {params['angle']}°。\n\n{params['question']}")
        result = "、".join(f"{n}′({x},{y})" for n, (x, y) in zip(names, params["rotated"]))
        reference = f"旋转后顶点：{result}。" + (f"\n{params['reference']}" if params["reference"] else "")
        return stem, reference
    material = f"\n\n补充资料：{params['material']}" if params["material"] else ""
    stem = f"{params['passage']}{material}\n\n{params['question']}{params['writingPrompt']}"
    evidence = "；".join(params["sentences"][i] for i in params["evidence"])
    reference = f"文本依据：{evidence}" + (f"\n{params['reference']}" if params["reference"] else "")
    return stem, reference


def generation_prompt(subject: str, lesson: dict[str, Any]) -> str:
    """The model picks one reviewed template for this page and returns its parameters as JSON, never markup or code."""
    kinds = [k for k in TEMPLATES[subject] if k != "reading" or lesson.get("sourceText", "").strip()]
    spec = {
        "rotation": '方格中的图形旋转（顶点、旋转中心、方向、90/180/270°）：{"template":"rotation","title":"","width":10,"height":10,'
                    '"shape":[[2,2],[5,2],[2,4]],"center":[2,2],"direction":"cw或ccw","angle":90,"steps":["讲解步骤"],"question":"","reference":""}'
                    '；width/height 6—12，坐标为整数且 y 轴向上，旋转后必须仍在网格内。',
        "clock": '钟面指针旋转（从某个数字出发，顺/逆时针转 30° 的整数倍）：{"template":"clock","title":"","start":2,"direction":"cw或ccw",'
                 '"angle":120,"steps":["讲解步骤"],"question":"","reference":""}；一道例题有多个小问时，选第一个小问的数据。',
        "reading": '阅读找文本依据：{"template":"reading","title":"","passage":"从本课原文原样摘取的连续段落（40—600字）","question":"",'
                   '"evidence":[作为依据的句子序号，从0开始],"material":"不超过150字的确定常识，可留空","writingPrompt":"","reference":""}',
        "steps": '分步讲解（任何例题都可用）：{"template":"steps","title":"","problem":"这一页例题的题目原文，不含答案","steps":["第1步……","第2步……"],'
                 '"answer":"本题答案","figure":{},"question":"学生书面作答的要求","reference":""}；2—6 步，每步不超过60字，严格按这一页的题目和数据讲解。'
                 '题目里有线段和点、计算程序、图形或数表时，必须用 figure 画出题目给出的条件（只画已知条件，不画答案）：'
                 '线段图 {"type":"segment","points":[{"name":"A","at":0},{"name":"C","at":3},{"name":"B","at":6}],"marks":[{"from":"A","to":"B","label":"x"}]}'
                 '（at 是点在线段上的位置，按题意取大致比例）；'
                 '程序图 {"type":"flow","boxes":["输入 a","÷ 0.5","+ b","输出"]}，分两种情况的程序写 {"type":"flow","boxes":["输入 n"],'
                 '"branches":[{"when":"n 是单数","boxes":["2n + 4"]},{"when":"n 是双数","boxes":["n² + 2"]}]}；'
                 '图形 {"type":"shape","shape":"rectangle|square|triangle|parallelogram|trapezoid","labels":{"top":"a cm","left":"b cm","height":""}}；'
                 '数表 {"type":"table","rows":[["n","1","2","3"],["结果","6","8","10"]]}。没有这类条件时 figure 写 {}。',
    }
    spec["steps"] += ('月历十字框 {"type":"calendar_cross","center":18,"daysInMonth":31,"firstWeekday":0,"total":90}。'
                      'firstWeekday：0=周日，6=周六；中心不能在周末。按题意确定中心和总和；此图为关系示意，不代表真实年月。'
                      '必须讲4步以上：定位中心、看左右差1、看上下差7、列五数和/代入。'
                      '方桌拼接人数规律题必须用 {"type":"seating_pattern","sampleCounts":[8,12,16]}，方桌每排相连，1张8人、每加1张增加4人；图中展示对应桌数的俯视图和外圈座位点，不要只给数表。'
                      '黑白棋子按层交替排成三角形、黑比白多 m 颗时必须用 {"type":"alternating_triangle","rows":6,"differenceSymbol":"m"}；首层白色，偶数层黑色，画 4/6/8 个示意层，逐层显现，最后突出每两层黑比白多1颗、总层数为2m；不能用静态颜色表代替。'
                      '同向环形跑道追及题必须用 {"type":"running_track","fastSpeed":180,"slowSpeed":140,"distanceSymbol":"s"}；画环形跑道、两个不同颜色的跑者和方向箭头，逐步展示每分钟相差的路程，最后说明追一圈需要 s/(快者速度-慢者速度) 分钟；原题图只能折叠作对照，不能代替互动示意图。'
                      '三角形数规律（1、3、6、10、15…）必须用 {"type":"triangular_numbers","terms":[1,3,6,10,15],"targetTerm":10}；逐步加出点阵三角形，并在最后一步把两份相同的三角形拼成 n 行、每行 n+1 个点的长方形，推导 n(n+1)/2；若题目问第10个，明确计算为55。'
                      '地砖颜色/数量规律必须用 {"type":"tile_pattern","whiteCounts":[5,8],"blueCounts":[4,7],"targetTerm":10,"targetBlue":100}；将前两幅按白砖和蓝砖分别画成方块阵列，逐步展示每幅增加的数量、通项和代入/反推结果，不能只显示表格或原题图片。'
                      '所有步骤预览打开后默认显示第1步及对应图示状态；不得把每一步都留作“点下一步显示”的空占位。对长方形周长/面积题用标注边长的图形，并逐步突出对应边、周长路径或面积区域。')
    text = (f"你是小学{subject}教师，为大屏上的一页例题选择一个互动课件模板并填写参数。只输出 JSON，不要 HTML、代码或 Markdown。\n"
            f"课题：{lesson['title']}\n教学目标：{lesson['coreTarget']}\n"
            "这一页的内容（课件必须演示这一页本身，图形、数据、问题与之一致，不能另换一道题）：\n" + lesson.get("pageText", "")[:1500] + "\n"
            "可选模板（优先选最贴合的专用模板；都不贴合时选 steps）：\n" + "\n".join(f"- {spec[k]}" for k in kinds))
    if "reading" in kinds:
        text += "\n本课原文：\n" + lesson["sourceText"][:6000]
    text += "\n图示必须表达题目本身的数量关系；原卷图片只作对照，不要用它代替课件图示。\n"
    return text



