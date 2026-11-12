"""周末课 课前互动课件：每一页讲解／例题可配一个经审核的互动课件.

teacher  GET  /teacher/weekend/lessons/{lid}/courseware            pages of the lesson and their courseware (draft/approved)
         POST /teacher/weekend/lessons/{lid}/courseware/generate   {stageNo, page} AI picks a reviewed template for this page (draft)
         PUT  /teacher/weekend/lessons/{lid}/courseware            {stageNo, page, kind, params, writtenTask} teacher edits (draft)
         POST /teacher/weekend/lessons/{lid}/courseware/approve    {stageNo, page} classrooms show it on that page
         POST /teacher/weekend/lessons/{lid}/courseware/remove     {stageNo, page} remove a page's courseware
         POST /teacher/weekend/sessions/{sid}/courseware/view      {view} live screen state while teaching (no AI)

A lesson keeps one row; its items are keyed by (stage, page), so every slide or worked example can have its own
courseware without a schema change. Rows written by the first pilot (one courseware, kind column) are read as one
item. The approved parameters reach the big screen with the existing session state (weekend_views.state) only
when the screen is on that page. When the teacher ticks it, an approved item also gives pupils a written task
through the existing written questions (text/photo, teacher review, question-by-question release).
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text, delete, insert, select, update

from changying.services import weekend_courseware as cw
from changying.services.weekend_courseware_quality import audit_example_pages
from changying.services.weekend_stages import STAGE_COUNT

AI_FEATURE = "weekend_courseware"


class PageBody(BaseModel):
    stageNo: int = Field(default=3, ge=1, le=STAGE_COUNT)
    page: int | None = Field(default=None, ge=0)


class SaveBody(PageBody):
    kind: str = Field(max_length=20)
    params: dict[str, Any]
    writtenTask: bool = False


class TemplateBody(PageBody):
    name: str = Field(default="", max_length=80)


class ApplyTemplateBody(PageBody):
    templateId: int


class ViewBody(BaseModel):
    view: dict[str, Any]


def register_courseware_table(implementation: Any) -> Table:
    md = implementation.Base.metadata
    if "weekend_courseware" not in md.tables:
        Table("weekend_courseware", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("lesson_id", Integer, nullable=False, unique=True),
              Column("teacher_id", Integer, nullable=False),
              Column("kind", String(20), nullable=False),
              Column("stage_no", Integer, nullable=False),
              Column("status", String(12), nullable=False),            # draft | approved (any item approved)
              Column("params_json", Text, nullable=False),             # {"version": 2, "items": [...]}; pilot rows: one params
              Column("approved_json", Text, nullable=True),            # non-null when some item is approved
              Column("approved_stage", Integer, nullable=True),
              Column("template_id", Integer, nullable=True),
              Column("live_json", Text, nullable=False),               # {"session:stage:page": screen state}
              Column("updated_at", DateTime, nullable=False))
    return md.tables["weekend_courseware"]


def register_courseware_template_table(implementation: Any) -> Table:
    """Courseware templates a school can reuse across lessons; created by the startup create_all.

    Kept apart from ``weekend_courseware`` because that table's ``lesson_id`` is unique and
    non-null (one row per lesson), so a template cannot live there without breaking its shape.
    """
    md = implementation.Base.metadata
    if "weekend_courseware_template" not in md.tables:
        Table("weekend_courseware_template", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("grade", Integer, nullable=False, default=0, index=True),
              Column("subject", String(30), nullable=False, index=True),
              Column("name", String(80), nullable=False),
              Column("kind", String(20), nullable=False),
              Column("stage_no", Integer, nullable=False),
              Column("page", Integer, nullable=True),
              Column("params_json", Text, nullable=False),
              Column("written_task", Boolean, nullable=False, default=False),
              Column("source_lesson_id", Integer, nullable=True),
              Column("created_by", Integer, nullable=True),
              Column("created_at", DateTime, nullable=False, default=datetime.utcnow))
    return md.tables["weekend_courseware_template"]


def stage_pages(lesson: Any, stage_no: int) -> list[str]:
    """The pages the big screen pages through in this stage (slides or worked examples); empty when it has none."""
    from changying.services.weekend_presentation import lesson_deck
    return lesson_deck({"ppt_json": lesson.ppt_json, "examples_json": lesson.examples_json, "reading_plan": lesson.reading_plan}, stage_no)


def _short(text: str, limit: int = 40) -> str:
    line = " ".join(str(text or "").split())
    return line if len(line) <= limit else line[:limit] + "…"


def items_of(row: Any) -> list[dict[str, Any]]:
    """Every page item of a lesson's courseware row; a pilot row (single courseware) becomes one or two items."""
    if row is None:
        return []
    data = json.loads(row.params_json or "{}")
    if isinstance(data, dict) and data.get("version") == 2:
        return list(data.get("items") or [])
    draft = data if isinstance(data, dict) else {}
    approved = json.loads(row.approved_json) if row.approved_json else None
    items = [{"stage": int(row.stage_no), "page": draft.get("page"), "kind": row.kind, "status": row.status, "params": draft,
              "approved": None, "writtenTask": True, "templateId": row.template_id, "pageText": "", "updatedAt": ""}]
    if approved is not None:
        key = (int(row.approved_stage or row.stage_no), approved.get("page"))
        if key == (items[0]["stage"], items[0]["page"]):
            items[0]["approved"] = approved
        else:
            items[0]["templateId"] = None
            items.append({"stage": key[0], "page": key[1], "kind": row.kind, "status": "approved", "params": approved, "approved": approved,
                          "writtenTask": True, "templateId": row.template_id, "pageText": "", "updatedAt": ""})
    return items


def invalidate_courseware_on_reimport(db: Any, table: Table, lesson_id: int) -> int:
    """Keep prepared visuals as drafts but revoke approval after reimport.

    An embedded image can change without changing the extracted problem text.
    The enclosing import transaction owns the commit/rollback.
    """
    row = db.execute(select(table).where(table.c.lesson_id == lesson_id).with_for_update()).first()
    if row is None:
        return 0
    items = items_of(row)
    for item in items:
        item["status"] = "draft"
        item["approved"] = None
        item["reimportReviewRequired"] = True
        item.pop("approvedPageText", None)
    db.execute(update(table).where(table.c.id == row.id).values(
        kind="multi", stage_no=int(items[0]["stage"]) if items else 3,
        status="draft", approved_json=None, approved_stage=None, template_id=None,
        params_json=json.dumps({"version": 2, "items": items}, ensure_ascii=False),
        live_json="{}", updated_at=datetime.utcnow(),
    ))
    return len(items)


def source_page_mismatch(lesson: Any) -> tuple[int, bool]:
    """Independent heading count catches the dangerous 23-to-1 fallback."""
    numbers = {int(n) for n in re.findall(
        r'(?m)^[^\S\n]*第[^\S\n]*(\d{1,2})[^\S\n]*题',
        lesson.reading_plan or "",
    )}
    count = len(numbers) if lesson.subject == "数学" and len(numbers) >= 5 else 0
    return count, bool(count and len(stage_pages(lesson, 3)) < count)


def required_visual_type(page_text: Any) -> str:
    """Known lesson types whose saved courseware must include a matching visual."""
    text = str(page_text or "")
    compact = _normalize_text(text)
    for quote in ("'", '"', "“", "”", "‘", "’", "「", "」", "『", "』"):
        compact = compact.replace(quote, "")

    # The original grade-five exercise has four DIFFERENT pictured cut/move/
    # rotate options. Without those four panels the question cannot be solved.
    if ("平行四边形" in text and
            ("四种转化方法" in text or
             (all(symbol in text for symbol in "①②③④") and "面积公式" in text))):
        return "parallelogram_methods"

    # Deterministic visuals for the three grade-five questions that were rendering
    # without their required diagrams or with an incomplete unit table.
    if ("平行四边形" in text and "三个图形" in text and "底均为" in text
            and "平行线间距" in text):
        return "equal_base_height"
    if ("平行四边形" in text and "底被平均分成" in text
            and "中间涂色" in text and "高不变" in text):
        return "parallelogram_thirds"
    if "正方形边长" in text and "平方千米" in text and "公顷" in text:
        return "table"

    # More specific patterns must be checked before the general calendar cases.
    if "月历" in text and ("框形辨析" in text or "哪一种错误" in text or "哪种错误" in text):
        return "calendar_compare"
    if ("3×3" in text or "3x3" in text or "3＊3" in text) and ("九数和" in text or "中心数" in text):
        return "table"
    if "a＋b²" in compact or "a+b²" in compact or ("小明算成" in text and "平方" in text):
        return "flow"
    if ("计算小程序" in text or "程序输入" in text) and all(token in text for token in ("4", "9", "15", "11", "26", "44")):
        return "flow"
    if "大正方形" in text and "小正方形" in text and "长方形" in text and "周长" in text:
        return "table"
    if "正方形边长" in text and "长方形长" in text and ("周长" in text or "面积" in text):
        return "table"
    if "月历" in text and "十" in text and "框" in text:
        return "calendar_cross"
    if "方桌" in text and ("可坐" in text or "座位" in text):
        return "seating_pattern"
    if "黑白棋子" in text and "三角形" in text:
        return "alternating_triangle"
    if "地砖" in text and ("排列" in text or "白地砖" in text):
        return "tile_pattern"
    if ("正方形" in text and "小棒" in text and ("摆" in text or "根" in text)
            and re.search(r"4\s*根", text) and re.search(r"7\s*根", text) and re.search(r"10\s*根", text)):
        return "square_sticks_pattern"
    if "田字形" in compact and "百数表" in compact and ("四数和" in compact or "四数之和" in compact or "四个数" in compact):
        return "hundred_chart_square"
    if "跑道" in text and ("追上" in text or "超过" in text or "多跑一圈" in text):
        return "running_track"
    if "三角形数" in compact or re.search(r"1[,，、]3[,，、]6[,，、]10[,，、]15", text):
        return "triangular_numbers"
    return ""


def required_visual_figure(page_text: Any) -> dict[str, Any]:
    """Return stable, data-only visual parameters for known questions."""
    text = str(page_text or "")
    kind = required_visual_type(text)
    if kind == "equal_base_height":
        height = re.search(r"平行线间距(?:离)?(?:为|是)?\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)", text, re.I)
        base = re.search(r"底(?:均)?\s*(?:为|是)?\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)", text, re.I)
        return {"type": kind, "base": float(base.group(1)) if base else 3,
                "height": float(height.group(1)) if height else 7}
    if kind == "parallelogram_thirds":
        total = re.search(r"(?:原图面积|面积)\s*(?:为|是)?\s*(\d+(?:\.\d+)?)\s*(?:平方厘米|cm²|cm2)", text, re.I)
        return {"type": kind, "parts": 3, "totalArea": float(total.group(1)) if total else 36}
    if kind == "parallelogram_methods":
        return {"type": "parallelogram_methods"}
    if kind == "calendar_compare":
        return {"type": "calendar_compare"}
    if kind == "table":
        compact = _normalize_text(text)
        if "正方形边长" in text and "平方千米" in text and "公顷" in text:
            return {"type": "table", "rows": [
                ["正方形边长", "对应面积"],
                ["1厘米", "（　　　）"],
                ["（　　　）", "1平方分米"],
                ["1米", "（　　　）"],
                ["（　　　）米", "1公顷"],
                ["（　　　）米", "1平方千米"],
            ]}
        if ("3×3" in text or "3x3" in text or "3＊3" in text) and ("九数和" in text or "中心数" in text):
            # 九宫格本身是题目条件：九个数一次看全，并按讲解步骤高亮对称数对/中心数。
            total = re.search(r"九数和\s*(?:为|是)?\s*(\d+)(?!\s*[A-Za-z])", text)
            total = int(total.group(1)) if total else None
            return {"type": "table", "reveal": False, "nineGrid": True, "targetSum": total,
                    "center": total // 9 if total and total % 9 == 0 else None,
                    "rows": [["a−11", "a−10", "a−9"], ["a−1", "a", "a+1"], ["a+9", "a+10", "a+11"]]}
        if "大正方形" in text and "小正方形" in text and "长方形" in text:
            return {"type": "table", "rows": [["拼接排", "正方形数", "总宽"], ["上排", "2个大正方形", "2m"], ["下排", "3个小正方形", "3n"], ["同一长方形", "两排等宽", "2m=3n"]]}
        if "正方形边长" in text and "长方形长" in text:
            return {"type": "table", "rows": [["图形", "周长", "面积"], ["正方形a", "4a", "a²"], ["长方形a,b", "2(a+b)", "ab"]]}
    if kind == "flow" and ("a＋b²" in text or "a+b²" in text or "小明算成" in text):
        return {"type": "flow", "boxes": ["原式 a+b²", "代入 a=5、b=3", "先求平方", "再做加法"], "branches": []}
    if kind == "flow" and ("计算小程序" in text or "程序输入" in text):
        return {"type": "flow", "boxes": ["输入 a", "×3", "−1", "输出 b"], "branches": []}
    if kind == "calendar_cross":
        total_match = re.search(r"五数和\s*(?:是|为)\s*(\d+)", text)
        total = int(total_match.group(1)) if total_match else 90
        return {"type": kind, "center": total // 5, "daysInMonth": 31, "firstWeekday": 0, "total": total}
    if kind == "hundred_chart_square":
        return {"type": kind, "topLeftNumber": 45}
    if kind == "running_track":
        speeds = [int(x) for x in re.findall(r"每分钟\s*跑\s*(\d+)\s*米", text)]
        distance = re.search(r"(?:跑道)?(?:周长|长)\s*(?:为|是)?\s*([A-Za-z])\s*米", text)
        if len(speeds) >= 2:
            symbol = distance.group(1) if distance else "s"
            return {"type": kind, "fastSpeed": max(speeds[:2]), "slowSpeed": min(speeds[:2]), "distanceSymbol": symbol}
    if kind == "triangular_numbers":
        target = re.search(r"第\s*(\d+)\s*个(?:三角形数)?", text)
        return {"type": kind, "terms": [1, 3, 6, 10, 15], "targetTerm": int(target.group(1)) if target else 10}
    if kind == "square_sticks_pattern":
        targets = [int(x) for x in re.findall(r"m\s*[=＝]\s*(\d+)", text)]
        target_sticks = re.search(r"n\s*[=＝]\s*(\d+)", text)
        return {"type": kind, "sampleCounts": [4, 7, 10], "targetSquares": targets[:2] if len(targets) >= 2 else [8, 60],
                "targetSticks": int(target_sticks.group(1)) if target_sticks else 100}
    if kind == "tile_pattern":
        white = [int(x) for x in re.findall(r"(\d+)\s*块白地砖", text)]
        blue = [int(x) for x in re.findall(r"(\d+)\s*块蓝地砖", text)]
        term = re.search(r"当\s*n\s*[=＝]\s*(\d+)", text)
        target = re.search(r"(?:用了|用)\s*(\d+)\s*块蓝(?:色)?砖", text)
        return {"type": kind, "whiteCounts": white[:2] if len(white) >= 2 else [5, 8],
                "blueCounts": blue[:2] if len(blue) >= 2 else [4, 7], "targetTerm": int(term.group(1)) if term else 10,
                "targetBlue": int(target.group(1)) if target else 100}
    if kind == "alternating_triangle":
        symbol = re.search(r"黑(?:棋子)?比白(?:棋子)?多\s*([A-Za-z])", text)
        return {"type": kind, "rows": 6, "differenceSymbol": symbol.group(1) if symbol else "m"}
    if kind == "seating_pattern":
        return {"type": kind, "sampleCounts": [8, 12, 16]}
    return {}


def _courseware_visual_text(item: dict[str, Any], params: dict[str, Any] | None = None, page_text: str = "") -> str:
    """Use both the source page and saved question fields when repairing legacy diagrams."""
    parts = [page_text, item.get("approvedPageText"), item.get("pageText")]
    for source in (params, item.get("params"), item.get("approved")):
        if isinstance(source, dict):
            parts.extend(source.get(key) for key in ("problem", "sourceProblem", "question", "title"))
    return " ".join(str(part or "") for part in parts)


def _repair_courseware_visual(params: dict[str, Any], visual_text: str) -> dict[str, Any]:
    """Repair known lesson diagrams at display time while preserving the scanned source separately."""
    result = dict(params or {})
    figure = required_visual_figure(visual_text)
    if not figure:
        return result
    # Saved courseware is the authority: never silently replace a teacher's valid
    # diagram or their hand-tuned steps with a deterministic fallback.
    original_figure = result.get("figure") if isinstance(result.get("figure"), dict) else {}
    original_steps = result.get("steps") if isinstance(result.get("steps"), list) else []
    legacy_calendar_answer_table = (
        figure.get("type") == "calendar_compare"
        and original_figure.get("type") == "table"
        and any(
            isinstance(row, list) and any("月历关系" in str(cell) or "竖列差10" in str(cell) for cell in row)
            for row in (original_figure.get("rows") or [])
        )
    )
    # Targeted display-time repair of the already-reviewed example 15.
    # Older saved 3×3 tables can show a dot instead of a+1/a+11 and lack
    # the progressive-grid metadata. Do not touch other examples or DB rows.
    lesson15_grid = (
        figure.get("nineGrid") is True
        and figure.get("targetSum") == 2016
        and figure.get("center") == 224
        and ("第15题" in visual_text or "第 15 题" in visual_text)
        and original_figure.get("type") in ("table", None, "")
    )
    if lesson15_grid:
        rows15 = original_figure.get("rows") or []
        grid15 = (
            isinstance(rows15, list) and len(rows15) == 3
            and all(isinstance(row, list) and len(row) == 3 for row in rows15)
            and str(rows15[1][1]).strip() == "a"
        )
        outdated_six_steps = (
            len(original_steps) == 6
            and ("在3×3方框中定位中心数" in str(original_steps[0])
                 or "第1步：在3×3" in str(original_steps[0]))
        )
        missing_right_cells = grid15 and (
            str(rows15[1][2]).strip() in ("", ".", "·", "?", "？")
            or str(rows15[2][2]).strip() in ("", ".", "·", "?", "？")
        )
        # Fully completed teacher-authored grids and other custom explanations
        # remain unchanged; only the photographed legacy state is repaired.
        if missing_right_cells or (grid15 and outdated_six_steps) or not original_figure.get("type"):
            result["figure"] = figure
            if outdated_six_steps or not original_steps:
                result["steps"] = [
                    "第1步：观察每行10个数的数表，先把3×3方框中间的数设为a。",
                    "第2步：同一行左右相邻数差1，所以左右分别是a−1、a+1。",
                    "第3步：同一列上下相邻数差10，所以上下分别是a−10、a+10。",
                    "第4步：再结合横向差1、纵向差10，补齐四角a−11、a−9、a+9、a+11。",
                    "第5步：把九个数相加，对称的加减抵消，九数和为9a。",
                    "第6步：若九数和为2016，则9a=2016，求得中心数a=224。",
                ]
            return result
    targeted_equal_area_figure = figure.get("type") in ("equal_base_height", "parallelogram_thirds")
    targeted_unit_table = (
        figure.get("type") == "table" and "正方形边长" in visual_text
        and "平方千米" in visual_text and "公顷" in visual_text
    )
    if targeted_equal_area_figure:
        if original_figure.get("type") != figure.get("type"):
            result["figure"] = figure
        return result
    if targeted_unit_table:
        rows = original_figure.get("rows") if original_figure.get("type") == "table" else None
        if rows != figure.get("rows"):
            result["figure"] = figure
        return result
    if original_figure.get("type") and not legacy_calendar_answer_table:
        return result
    if result.get("figure") != figure:
        result["figure"] = figure
    # Even if an old slide lacks a figure, retain its existing explanation.
    # Only replace clearly empty or scaffold text.
    placeholder_steps = len(original_steps) < 2 or all(
        not str(step).strip() or "点下一步显示" in str(step) or "第1步" in str(step)
        for step in original_steps
    ) or (
        figure.get("type") in (
            "calendar_compare", "calendar_cross", "seating_pattern",
            "alternating_triangle", "running_track", "triangular_numbers",
            "tile_pattern", "square_sticks_pattern", "hundred_chart_square",
        ) and len(original_steps) < 4
    )
    if not placeholder_steps and not (
        legacy_calendar_answer_table and
        any("选项C写成" in str(step) or "因此C错误" in str(step) for step in original_steps)
    ):
        return result
    text = str(visual_text or "")
    compact = _normalize_text(text)
    steps: list[str] | None = None
    if ("3×3" in text or "3x3" in text or "3＊3" in text) and ("九数和" in text or "中心数" in text):
        steps = [
            "先观察九宫格：同一行和同一列相邻数如何变化？试着找出中心格。",
            "设中心数为a，中心周围两两对称：a−11与a+11、a−10与a+10、a−9与a+9、a−1与a+1。",
            "四组对称数各相加都是2a，再加中心a，九数和为9a。",
            (f"九数和为{figure['targetSum']}时，中心数={figure['targetSum']}÷9={figure['center']}。"
             if figure.get("targetSum") is not None and figure.get("center") is not None
             else "如果题目给出九数和，请自己用总和÷9求中心数，并检验是否为整数。"),
        ]
    elif "月历" in text and ("框形辨析" in text or "哪一种错误" in text or "哪种错误" in text):
        steps = [
            "观察月历：同一行相邻两格的日期有什么变化？同一列呢？先说出你的发现。",
            "选择A和B，对照蓝色日期格：题目中的横向、纵向关系能成立吗？说说理由。",
            "重点检查C：从下往上数三格，若最下格是x，另外两格该怎样表示？先自己写。",
            "比较D的中心对称日期，再回看四个选项：你认为哪项有误？说明依据。",
        ]
    elif "正方形边长" in text and "长方形长" in text:
        steps = [
            "观察正方形和长方形：哪些边相等？周长与面积分别要求什么？",
            "长方形长a、宽b，对边相等，所以周长2(a+b)、面积ab。",
            "根据原题给出的边长或字母关系，代入相应的周长、面积公式。",
            "自己检查结果的单位，并说明周长与面积的区别。",
        ]
    elif "a＋b²" in text or "a+b²" in text or "小明算成" in text:
        steps = [
            "观察a+b²：平方究竟作用于哪个数？你准备先算哪一步？",
            "先算乘方：b²=3²=9，不是3×2。",
            "再加a：5+9=14；不能把a+b改成(a+b)²。",
            "所以正确结果是14。",
        ]
    elif "大正方形" in text and "小正方形" in text and "长方形" in text:
        steps = [
            "观察大小正方形拼成的长方形：上下两排的宽度有什么关系？",
            "上排2个大正方形的总宽为2m，下排3个小正方形的总宽为3n；所以2m=3n。",
            "长方形的长是2m，宽是m+n，周长C=2[2m+(m+n)]=6m+2n。",
            "由2m=3n得6m=9n，所以C=9n+2n=11n。",
            "如果题目提供m的数值，再代入2m=3n计算n，并检查拼接宽度相等。",
        ]
    elif figure["type"] == "hundred_chart_square":
        steps = [
            "观察百数表田字格：向右和向下移动一格，数字分别怎么变化？",
            "设田字格左上角为n，则右上是n+1，左下是n+10，右下是n+11。",
            "四数相加：n+(n+1)+(n+10)+(n+11)=4n+22。",
            "若右下角为m，则左上m−11，右上m−10，左下m−1。",
            "四数和：(m−11)+(m−10)+(m−1)+m=4m−22。",
        ]
    elif figure["type"] == "square_sticks_pattern":
        steps = [
            "观察连续正方形：从1个摆到2个、3个，共用边在哪里？小棒数如何变化？",
            "发现：每增加1个正方形，都会和前一个共用一条边，所以只增加3根小棒。",
            "列式：摆m个，先用4根，后面m−1个各增加3根，n=4+3(m−1)=3m+1。",
            "代入：m=8时n=25；m=60时n=181。",
            "反求：n=100时，3m+1=100，所以m=33。",
        ]
    if steps is not None:
        result["steps"] = steps
    elif figure["type"] == "calendar_cross":
        if re.search(r"五数和\s*(?:是|为)\s*\d+", text):
            total, center = int(figure["total"]), int(figure["center"])
            result["steps"] = ["观察月历十字框：左右、上下移动一格，日期怎样变化？",
                               "若中心数为a，四周依次是a−7、a−1、a+1、a+7。",
                               "五数相加：(a−7)+(a−1)+a+(a+1)+(a+7)=5a。",
                               f"五数和为{total}，所以a={total}÷5={center}，最小{center-7}，最大{center+7}。"]
        else:
            result["steps"] = ["先观察十字框：如果用a表示中心数，四周日期如何表示？", "最上面和最下面分别是a−7、a+7，两数相加等于2a。",
                               "最左面和最右面分别是a−1、a+1，两数相加也等于2a。",
                               "所以两组相对数的和相等，都是中心数的2倍。"]
    elif figure["type"] == "tile_pattern":
        white, blue = figure["whiteCounts"], figure["blueCounts"]
        white_step, blue_step = white[1] - white[0], blue[1] - blue[0]
        target_n, target_blue = figure["targetTerm"], figure["targetBlue"]
        white_n = white[0] + (target_n - 1) * white_step
        blue_n = blue[0] + (target_n - 1) * blue_step
        reverse_n = (target_blue - blue[0] + blue_step - 1) // blue_step + 1
        result["steps"] = ["先观察前两幅地砖：白砖与蓝砖的数量分别怎样变化？",
                           f"两种颜色每增加一幅分别增加{white_step}块和{blue_step}块。",
                           f"第n幅白砖为{white[0]}+{white_step}(n−1)，蓝砖为{blue[0]}+{blue_step}(n−1)。",
                           f"第{target_n}幅白砖{white_n}块；蓝砖为{target_blue}块时对应第{reverse_n}幅。"]
    elif figure["type"] == "running_track":
        fast, slow, symbol = figure["fastSpeed"], figure["slowSpeed"], figure["distanceSymbol"]
        result["steps"] = ["观察同向跑步：快者追上一整圈时，两人累计路程相差多少？",
                           f"快者每分钟跑{fast}米，慢者每分钟跑{slow}米。",
                           f"每分钟路程差为{fast}−{slow}={fast-slow}米。",
                           f"追上一整圈所需时间={symbol}÷{fast-slow}分钟。"]
    elif figure["type"] == "triangular_numbers":
        target = figure["targetTerm"]
        result["steps"] = ["观察三角形点阵：每增加一层，新增点数遵循什么规律？",
                           "第n个三角形数是1+2+…+n。",
                           "两份同样的点阵可拼成n行、每行n+1个点的长方形，共n(n+1)个点。",
                           f"原点阵为一半，所以第n个是n(n+1)÷2；第{target}个为{target*(target+1)//2}。"]
    elif figure["type"] == "alternating_triangle":
        result["steps"] = ["观察三角形棋子图：黑白棋子是怎样分层排列的？", "每两层一组，黑层比白层多1颗棋子。", "黑棋子比白棋子多m颗，说明有m组这样的两层。", "总层数为2m层。"]
    elif figure["type"] == "seating_pattern":
        result["steps"] = ["1张方桌外周有8个座位；方桌是正方形，座位沿外周排列。", "每增加1张方桌，与前一张共用一条边，内部共用边不坐人，所以外周座位增加4人。", "m张方桌可坐8+4(m−1)人。", "化简得到4m+4人。"]
    return result


def courseware_for_session(implementation: Any, db: Any, row: Any, page_index: int | None) -> tuple[dict[str, Any] | None, str]:
    """The approved courseware of the page on screen, without answers; else a note for the teacher."""
    t = register_courseware_table(implementation)
    c = db.execute(select(t).where(t.c.school_id == row.school_id, t.c.lesson_id == row.lesson_id,
                                   t.c.approved_json.isnot(None))).first()
    stage = int(row.current_stage or 0)
    if stage == 3 and source_page_mismatch(db.get(implementation.TeachingLesson, row.lesson_id))[1]:
        return None, "原文题号与例题页数不符，互动课件已暂停显示，请返回备课页检查。"
    approved = [i for i in items_of(c) if i.get("approved") is not None and int(i["stage"]) == stage]
    if not approved:
        return None, ""
    pages = stage_pages(db.get(implementation.TeachingLesson, row.lesson_id), stage)
    if pages:
        # Each courseware belongs to one slide or worked example; other pages keep their own content.
        bound = [i for i in approved if i.get("page") is not None and 0 <= int(i["page"]) < len(pages)]
        item = next((i for i in bound if int(i["page"]) == page_index), None)
        if item is None:
            if bound:
                return None, "本环节第 " + "、".join(str(int(i["page"]) + 1) for i in sorted(bound, key=lambda i: i["page"])) + " 页有互动课件。"
            return None, "本环节有互动课件，但没有对应到具体的页（例题）。请到备课页“互动课件”选择对应页并重新审核。"
        approved_text = item.get('approvedPageText', item.get('pageText', ''))
        if approved_text and approved_text != pages[int(item['page'])]:
            return None, '教案页面已变化，原课件暂不显示，请老师核对对应题目后重新审核。'
    else:
        item = approved[0]
    params = item["approved"]
    page_text = ""
    if pages and item.get("page") is not None and 0 <= int(item["page"]) < len(pages):
        page_text = pages[int(item["page"])]
    visual_text = _courseware_visual_text(item, params, page_text)
    params = _repair_courseware_visual(params, visual_text)
    key = f"{row.id}:{stage}:{item.get('page')}"
    view = json.loads(c.live_json or "{}").get(key) or cw.clean_view(item["kind"], params, {})
    return {"id": c.id, "kind": item["kind"], "kindLabel": cw.KIND_LABEL[item["kind"]], "stageNo": stage, "page": item.get("page"),
            "params": cw.public_params(item["kind"], params), "view": view}, ""


def _normalize_text(text: Any) -> str:
    return "".join(str(text or "").split())


_FIGURE_URL = re.compile(r"data:image/jpeg;base64,[A-Za-z0-9+/]+={0,2}")


_QUESTION_NO = re.compile(r"第\s*(\d{1,2})\s*题")


def lesson_figures(implementation: Any, db: Any, lesson: Any, written_table: Any = None) -> list[dict[str, Any]]:
    """The pictures imported with this lesson's questions, with their question number when known."""
    TQ = implementation.TeachingQuestion
    rows = db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != "weekend_removed").order_by(TQ.id)).all()
    out = []
    for q in rows:
        try:
            fig = json.loads(getattr(q, "figure_json", "") or "{}")
        except (TypeError, ValueError):
            continue
        if not isinstance(fig, dict) or fig.get("type") != "uploaded_image":
            continue
        url = str(fig.get("data_url") or "")
        if len(url) > 700000 or not _FIGURE_URL.fullmatch(url):
            continue
        stem = str(q.stem or "")
        number = _QUESTION_NO.search(stem)
        verified_no = fig.get("question_no")
        try:
            verified_no = int(verified_no) if verified_no is not None else None
        except (TypeError, ValueError):
            verified_no = None
        out.append({"number": verified_no or (int(number.group(1)) if number else None), "key": _normalize_text(stem)[:60],
                    "figure": {"type": "uploaded_image", "data_url": url, "alt": "原卷插图"}})
    if written_table is not None:
        # Imported written/fill-in questions keep their source picture in hints_json.figure.
        written_rows = db.execute(select(written_table).where(written_table.c.lesson_id == lesson.id,
            written_table.c.session_id == 0).order_by(written_table.c.id)).all()
        for q in written_rows:
            try:
                meta = json.loads(q.hints_json or "{}")
                fig = meta.get("figure") if isinstance(meta, dict) else None
            except (TypeError, ValueError):
                continue
            if not isinstance(fig, dict) or fig.get("type") != "uploaded_image":
                continue
            url = str(fig.get("data_url") or "")
            if len(url) > 700000 or not _FIGURE_URL.fullmatch(url):
                continue
            stem = str(q.stem or "")
            number = _QUESTION_NO.search(stem)
            verified_no = fig.get("question_no")
            try:
                verified_no = int(verified_no) if verified_no is not None else None
            except (TypeError, ValueError):
                verified_no = None
            out.append({"number": verified_no or (int(number.group(1)) if number else None), "key": _normalize_text(stem)[:60],
                        "figure": {"type": "uploaded_image", "data_url": url, "alt": "原卷插图"}})
    return out


def requires_original_geometry_image(page_text: Any) -> bool:
    """Measurement diagrams require a source scan; reviewed transformation-method diagrams use their own verified four-panel figure."""
    text = str(page_text or "")
    if required_visual_type(text) == "parallelogram_methods":
        return False  # teacher must still verify all four panels and supply a real answer
    return (
        any(term in text for term in ("平行四边形", "三角形", "梯形", "多边形"))
        and any(term in text for term in ("图上", "下图", "右图", "下面各个", "画高", "量出", "测量", "涂色", "①②③", "三个图形", "相邻点"))
    )


def attach_original_figure(params: dict[str, Any], figures: list[dict[str, Any]], page_text: Any) -> dict[str, Any]:
    """Recover a source scan on edit/review, without replacing any teacher-authored figure."""
    if (params.get("sourceFigure") or {}).get("type") == "uploaded_image":
        return params
    original = match_figure(figures, page_text)
    if not original:
        return params
    return {**params, "sourceFigure": original}


def match_figure(figures: list[dict[str, Any]], page_text: Any) -> dict[str, Any]:
    """Return an unambiguous original figure or leave the page without a picture."""
    text = _normalize_text(page_text)
    number = _QUESTION_NO.search(text)
    if number:
        wanted = int(number.group(1))
        numbered = [item for item in figures if item.get("number") == wanted]
        if len(numbered) == 1:
            # The original PDF layout established this association. AI may reword the slide.
            return numbered[0]["figure"]
        return {}
    matched = [item for item in figures if len(str(item.get('key') or '')) >= 12 and str(item['key']) in text]
    if len(matched) == 1:
        return matched[0]['figure']
    return {}


def install_weekend_courseware(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "weekend_courseware_installed", False):
        return app.state.weekend_courseware_router
    from changying.services.lesson_written import template_meta, written_templates
    from changying.web.weekend_views import register_weekend_tables
    from changying.web.weekend_written import register_written_tables

    t = register_courseware_table(implementation)
    register_courseware_template_table(implementation)   # must exist in metadata before the startup create_all
    tables = register_weekend_tables(implementation)
    sessions, slide = tables["sessions"], tables["slide"]
    written = register_written_tables(implementation)["questions"]
    Lesson = implementation.TeachingLesson
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def my_lesson(db: Any, u: Any, lid: int) -> Any:
        need(u, "teacher")
        lesson = db.get(Lesson, lid)
        if lesson is None or int(lesson.school_id) != int(u.school_id) or lesson.subject not in cw.TEMPLATES:
            raise HTTPException(404, "没有找到这节课")
        return lesson

    def row_for(db: Any, lesson: Any, lock: bool = False) -> Any:
        q = select(t).where(t.c.school_id == lesson.school_id, t.c.lesson_id == lesson.id)
        return db.execute(q.with_for_update() if lock else q).first()

    def find(items: list[dict[str, Any]], stage: int, page: int | None) -> dict[str, Any] | None:
        return next((i for i in items if int(i["stage"]) == stage and i.get("page") == page), None)

    def checked_page(lesson: Any, stage_no: int, page: int | None) -> int | None:
        pages = stage_pages(lesson, stage_no)
        if not pages:
            return None
        if page is None or not 0 <= page < len(pages):
            raise HTTPException(400, "这个环节有分页，请选择课件对应的页（例题）")
        return page

    def required_visual_type(page_text: Any) -> str:
        return globals()["required_visual_type"](page_text)

    def lesson_grade(db: Any, lesson: Any) -> int:
        """The school's current grade, kept on the template so a listing can be filtered later."""
        Program = getattr(implementation, "TeachingProgram", None)
        if Program is None:
            return 0
        p = db.scalar(select(Program).where(Program.school_id == lesson.school_id)
                      .order_by(Program.active.desc(), Program.id.desc()).limit(1))
        return int(getattr(p, "grade", 0) or 0) if p is not None else 0

    def write(db: Any, u: Any, lesson: Any, items: list[dict[str, Any]]) -> None:
        c = row_for(db, lesson, lock=True)
        items = sorted(items, key=lambda i: (int(i["stage"]), -1 if i.get("page") is None else int(i["page"])))
        approved = [[int(i["stage"]), i.get("page")] for i in items if i.get("approved") is not None]
        values = dict(kind="multi", stage_no=int(items[0]["stage"]) if items else 3, status="approved" if approved else "draft",
                      params_json=json.dumps({"version": 2, "items": items}, ensure_ascii=False),
                      approved_json=json.dumps(approved) if approved else None, approved_stage=None, template_id=None,
                      updated_at=datetime.utcnow())
        if c is None:
            db.execute(insert(t).values(school_id=u.school_id, lesson_id=lesson.id, teacher_id=u.id, live_json="{}", **values))
        else:
            db.execute(update(t).where(t.c.id == c.id).values(**values))
        db.commit()

    def task(item: dict[str, Any], params: dict[str, Any]) -> dict[str, str]:
        try:
            return dict(zip(("stem", "reference"), cw.written_question(item["kind"], params, item.get("pageText") or "")))
        except ValueError as e:
            return {"stem": str(e), "reference": ""}

    def payload(db: Any, lesson: Any) -> dict[str, Any]:
        items = []
        for i in items_of(row_for(db, lesson)):
            pages = stage_pages(lesson, int(i.get("stage") or 0))
            page_index = i.get("page")
            page_text = pages[int(page_index)] if page_index is not None and 0 <= int(page_index) < len(pages) else ""
            visual_text = _courseware_visual_text(i, i.get("params"), page_text)
            for key in ("params", "approved"):
                current = i.get(key)
                if isinstance(current, dict):
                    i[key] = _repair_courseware_visual(current, visual_text)
            needs_sync = bool(i.get("reimportReviewRequired"))
            if page_index is not None:
                needs_sync = needs_sync or not 0 <= int(page_index) < len(pages) or i.get("pageText", "") != page_text
            items.append({**i, "needsSync": needs_sync,
                          "kindLabel": cw.KIND_LABEL.get(i["kind"], i["kind"]),
                          "writtenTaskPreview": task(i, i["params"])})
        quality_audit = audit_example_pages(
            stage_pages(lesson, 3), items,
            globals()["required_visual_type"], stage=3,
        )
        source_count, mismatch = source_page_mismatch(lesson)
        return {"lessonId": lesson.id, "subject": lesson.subject, "templates": list(cw.TEMPLATES[lesson.subject]), "kindLabels": cw.KIND_LABEL,
                "sourceQuestionCount": source_count, "sourcePageMismatch": mismatch,
                "qualityAudit": quality_audit,
                "hasSource": bool((lesson.reading_plan or "").strip()), "items": items,
                "pages": {str(n): [_short(x, 80) for x in stage_pages(lesson, n)] for n in (2, 3)}}

    def upsert(db: Any, u: Any, lesson: Any, stage: int, page: int | None, kind: str, params: dict[str, Any],
               written_task: bool | None, page_text: str) -> None:
        items = items_of(row_for(db, lesson, lock=True))
        old = find(items, stage, page)
        if old is None:
            items.append({"stage": stage, "page": page, "kind": kind, "status": "draft", "params": params, "approved": None,
                          "writtenTask": bool(written_task), "templateId": None, "pageText": page_text})
        else:
            # The approved version stays in classrooms until this draft is approved.
            if old.get('approved') is not None and old.get('kind') != kind:
                raise HTTPException(409, '已审核的课件不能直接更换模板类型，请先核对后处理原课件')
            old['previousDraft'] = {k: old.get(k) for k in ('kind', 'params', 'writtenTask', 'pageText')}
            old.update(kind=kind, status="draft", params=params, pageText=page_text or old.get("pageText", ""))
            old.pop("reimportReviewRequired", None)
            if written_task is not None:
                old["writtenTask"] = bool(written_task)
        target = find(items, stage, page)
        target["updatedAt"] = datetime.now(implementation.SCHOOL_TZ).strftime("%Y-%m-%d %H:%M")
        write(db, u, lesson, items)

    @router.get("/teacher/weekend/lessons/{lid}/courseware")
    def get_courseware(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        return payload(db, my_lesson(db, u, lid))

    @router.post("/teacher/weekend/lessons/{lid}/courseware/restore-previous")
    def restore_previous(lid: int, b: PageBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        lesson = my_lesson(db, u, lid)
        page = checked_page(lesson, b.stageNo, b.page)
        items = items_of(row_for(db, lesson, lock=True))
        item = find(items, b.stageNo, page)
        previous = item.get('previousDraft') if item else None
        if not isinstance(previous, dict):
            raise HTTPException(404, '这页没有可恢复的上一版')
        if item.get('approved') is not None and previous.get('kind') != item.get('kind'):
            raise HTTPException(409, '上一版模板与已审核课件不同，不能自动恢复')
        pages = stage_pages(lesson, b.stageNo)
        current_text = pages[page] if page is not None else ''
        if previous.get('pageText') != current_text:
            raise HTTPException(409, '教案分页已变化，不能自动恢复到这一页，请先核对原教案')
        item['previousDraft'] = {k: item.get(k) for k in ('kind', 'params', 'writtenTask', 'pageText')}
        item.update({k: previous.get(k) for k in ('kind', 'params', 'writtenTask', 'pageText')})
        item['status'] = 'draft'
        write(db, u, lesson, items)
        return payload(db, lesson)

    @router.post("/teacher/weekend/lessons/{lid}/courseware/generate")
    def generate(lid: int, b: PageBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Preparation only: for one page, AI picks a reviewed template and fills it; validated, saved as a draft."""
        lesson = my_lesson(db, u, lid)
        if b.stageNo == 3 and source_page_mismatch(lesson)[1]:
            raise HTTPException(409, "导入原题数量与例题课件页数不符，已暂停生成；请检查教案题号识别。")
        page = checked_page(lesson, b.stageNo, b.page)
        pages = stage_pages(lesson, b.stageNo)
        page_text = pages[page] if page is not None else ""
        info = {"title": lesson.title, "coreTarget": lesson.core_target or "", "sourceText": lesson.reading_plan or "",
                "pageText": page_text or (lesson.teacher_plan or "")[:1500]}
        try:
            from changying.services.weekend_presentation import literal_numbered_questions
            literal_page = bool(page_text and any(page_text in q for q in literal_numbered_questions(lesson.reading_plan or '')))
            prompt = cw.generation_prompt(lesson.subject, info)
            if lesson.subject == '数学':
                prompt += '\n\u8bf7\u4f7f\u7528 steps \u6a21\u677f\u3002\u539f\u5377\u56fe\u7247\u53ea\u4f5c\u5bf9\u7167\uff1b\u5fc5\u987b\u6309\u9898\u610f\u63d0\u4f9b\u53d7\u652f\u6301\u7684\u6570\u636e\u56fe\u793a\uff0c\u4e0d\u80fd\u7528\u539f\u56fe\u4ee3\u66ff\u8bb2\u89e3\u56fe\u3002\u4e0d\u786e\u5b9a\u65f6\u7559\u7a7a。'
            if literal_page:
                prompt += '\n\u672c\u9875\u5fc5\u987b\u9009\u62e9 steps\uff0c\u9898\u76ee\u539f\u6587\u7531\u7cfb\u7edf\u63d0\u4f9b\uff0c\u4e0d\u8981\u53e6\u7f16\u9898\u76ee\uff1b\u6839\u636e\u9898\u610f\u751f\u6210\u53d7\u652f\u6301\u7684\u6570\u636e\u56fe\u793a\uff0c\u4e0d\u80fd\u6539\u53d8\u539f\u9898\u6761\u4ef6。'
            data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, prompt, timeout=60))
            kind = str(data.get("template") or "") if isinstance(data, dict) else ""
            if kind not in cw.TEMPLATES[lesson.subject] or (kind == "reading" and not (lesson.reading_plan or "").strip()):
                raise ValueError("没有选择可用的模板")
            required_figure = required_visual_type(page_text)
            if required_figure and isinstance(data, dict) and (data.get("figure") or {}).get("type") != required_figure:
                # Known classroom visuals are generated from the question's literal givens, also repairing older model outputs.
                data["figure"] = required_visual_figure(page_text)
            if lesson.subject == '数学' and kind != 'steps':
                raise ValueError('自动生成未能保留可核对的题图，请重试或手动填写')
            if literal_page:
                if kind != 'steps':
                    raise ValueError('该页需要保留原题，请重试或手动填写')
                data['sourceProblem'] = page_text
                data['problem'] = page_text
            figures = lesson_figures(implementation, db, lesson, written)
            original = match_figure(figures, page_text)
            notice = ""
            try:
                params = cw.clean(kind, data, lesson.reading_plan or "")
            except ValueError as e:
                if kind != "steps" or not data.get("figure"):
                    raise
                # The worked example is usable; only its figure is not: keep the page, say so, let the teacher draw it.
                params = cw.clean(kind, {**data, "figure": {}}, lesson.reading_plan or "")
                notice = f"AI 画的图示没有通过校验（{e}），已去掉，可在预览里手动补上"
            if original and kind == "steps":
                # The scan is always a comparison image, never a substitute for a teaching diagram.
                if params.get("figure") and params["figure"].get("type") != "uploaded_image":
                    params["sourceFigure"] = original
                    notice = "已生成课件图示；原题图片保留为对照，可在预览中展开"
                else:
                    params["figure"] = {}
                    params["sourceFigure"] = original
                    if notice:
                        notice += "；原题图片保留为对照，可在预览中展开"
                    else:
                        notice = "只匹配到原题图片，尚无课件演示图；请在预览/修改中补充图示"
            elif kind == "steps" and requires_original_geometry_image(page_text) and not original:
                notice = "本题需要原题图进行测量核对，但没有找到可唯一匹配的原图；已保留草稿，禁止直接审核"
            elif kind == "steps" and not params.get("figure") and not notice:
                notice = "未生成可视化图示；课件保留为草稿，请在预览/修改中补图后再审核"
        except ValueError as e:
            raise HTTPException(502, f"第 {(page or 0) + 1} 页：AI 生成的课件未通过校验（{e}），已有课件未改动，可重试或手动填写")
        except HTTPException as e:
            raise HTTPException(502, f"第 {(page or 0) + 1} 页：生成失败（{e.detail}），已有课件未改动，可重试或手动填写")
        upsert(db, u, lesson, b.stageNo, page, kind, params, None, page_text)
        implementation.audit(db, u, "weekend.courseware.generate", f"lesson={lid}:stage={b.stageNo}:page={page}:kind={kind}")
        db.commit()
        return {**payload(db, lesson), "notice": notice}

    @router.put("/teacher/weekend/lessons/{lid}/courseware")
    def save(lid: int, b: SaveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        lesson = my_lesson(db, u, lid)
        if b.kind not in cw.TEMPLATES[lesson.subject]:
            raise HTTPException(400, "这门课不能使用这种课件模板")
        try:
            params = cw.clean(b.kind, b.params, lesson.reading_plan or "")
        except ValueError as e:
            raise HTTPException(400, str(e))
        page = checked_page(lesson, b.stageNo, b.page)
        pages = stage_pages(lesson, b.stageNo)
        page_text = pages[page] if page is not None else ""
        fallback_figure = required_visual_figure(page_text)
        if fallback_figure and not (params.get("figure") or {}).get("type"):
            params = cw.clean(b.kind, {**params, "figure": fallback_figure}, lesson.reading_plan or "")
        elif fallback_figure and (params.get("figure") or {}).get("type") != fallback_figure.get("type"):
            # These question types have fixed, source-derived diagrams; repair stale legacy figure kinds.
            if fallback_figure.get("type") in ("equal_base_height", "parallelogram_thirds", "table"):
                params = cw.clean(b.kind, {**params, "figure": fallback_figure}, lesson.reading_plan or "")
        if b.kind == "steps":
            params = attach_original_figure(params, lesson_figures(implementation, db, lesson, written), page_text)
        upsert(db, u, lesson, b.stageNo, page, b.kind, params, b.writtenTask, page_text)
        return payload(db, lesson)

    def drop_template(db: Any, u: Any, lesson: Any, template_id: int | None) -> None:
        # Only the lesson's preparation template (session_id 0); classroom snapshots are never touched.
        if template_id:
            db.execute(delete(written).where(written.c.id == template_id, written.c.session_id == 0,
                                             written.c.lesson_id == lesson.id, written.c.school_id == u.school_id))

    @router.post("/teacher/weekend/lessons/{lid}/courseware/approve")
    def approve(lid: int, b: PageBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Teacher review done for one page: classrooms show it on that page; optional written task for pupils."""
        lesson = my_lesson(db, u, lid)
        if b.stageNo == 3 and source_page_mismatch(lesson)[1]:
            raise HTTPException(409, "原文题号与例题页数不符，已禁止审核或展示错误页。")
        page = checked_page(lesson, b.stageNo, b.page)
        items = items_of(row_for(db, lesson))
        item = find(items, b.stageNo, page)
        if item is None:
            raise HTTPException(404, "这一页还没有课件，请先生成或填写")
        if item.get("reimportReviewRequired"):
            raise HTTPException(409, "教案已重新导入，图片可能变化；请重新生成或保存课件草稿，再逐页审核。")
        pages = stage_pages(lesson, b.stageNo)
        current_text = pages[page] if page is not None else ""
        if item.get("pageText", "") != current_text:
            raise HTTPException(409, "教案原题已变化，旧课件不可直接审核；请重新生成或保存与本页一致的讲解。")
        try:
            params = cw.clean(item["kind"], item["params"], lesson.reading_plan or "")
        except ValueError as e:
            raise HTTPException(400, str(e))
        if item["kind"] == "steps":
            params = attach_original_figure(
                params, lesson_figures(implementation, db, lesson, written), item.get("pageText") or ""
            )
            if requires_original_geometry_image(item.get("pageText") or "") and (
                (params.get("sourceFigure") or {}).get("type") != "uploaded_image"
            ):
                raise HTTPException(400, "本题需要对照原题图片测量，但尚未找到匹配的原图；请重新导入原卷图并核对后审核")
        if requires_original_geometry_image(item.get("pageText") or "") and (
            (params.get("figure") or {}).get("type") in (None, "", "table")
        ):
            raise HTTPException(400, "本题依赖原图中的几何关系，文字表格不能代替①②③题图；请补充与原图一致的教学图后再审核")
        required_figure = required_visual_type(item.get("pageText") or "")
        saved_figure = params.get("figure") or {}
        if required_figure in ("equal_base_height", "parallelogram_thirds", "table") and saved_figure.get("type") != required_figure:
            fallback_figure = required_visual_figure(item.get("pageText") or "")
            if fallback_figure:
                params = cw.clean(item["kind"], {**params, "figure": fallback_figure}, lesson.reading_plan or "")
                saved_figure = params.get("figure") or {}
        # A reviewed custom diagram may be better than our generic fallback.
        # Prevent approval of the known old solved-answer calendar table, but
        # never silently overwrite any teacher-authored drawing.
        if required_figure == "calendar_compare" and saved_figure.get("type") == "table":
            if any(
                isinstance(row, list) and any(str(cell).strip() in ("正确", "错误") for cell in row)
                for row in saved_figure.get("rows", [])
            ):
                raise HTTPException(400, "月历判断表直接显示了正确/错误，请先改为不泄露答案的图示")
        if required_figure and not saved_figure.get("type"):
            raise HTTPException(400, "请先补充本题的教学图示，再审核")
        if required_figure == "parallelogram_methods" and re.search(
                r"待教师确认|原题未提供|图示缺失|看不到图|无法判断", str(params.get("answer") or "")):
            raise HTTPException(400, "原题四种转化图已补齐，请先对照①②③④核实并填写答案，再审核通过")
        template_id = item.get("templateId")
        if item.get("writtenTask"):
            try:
                stem, reference = cw.written_question(item["kind"], params, item.get("pageText") or "")
            except ValueError as e:
                raise HTTPException(400, str(e))
            meta = {"approved": True, "type": "short_answer", "hints": [], "courseware": f"{b.stageNo}:{page}"}
            template = next((q for q in written_templates(db, written, u.school_id, u.id, lesson.id) if q.id == template_id), None)
            if template is not None and template_meta(template).get("courseware"):
                db.execute(update(written).where(written.c.id == template.id).values(stem=stem, reference=reference,
                                                                                      hints_json=json.dumps(meta, ensure_ascii=False)))
            else:
                template_id = db.execute(insert(written).values(school_id=u.school_id, teacher_id=u.id, lesson_id=lesson.id, session_id=0, stem=stem,
                                                                reference=reference, hints_json=json.dumps(meta, ensure_ascii=False))).inserted_primary_key[0]
        else:
            drop_template(db, u, lesson, template_id)
            template_id = None
        item.update(status="approved", params=params, approved=params, approvedPageText=current_text, templateId=template_id)
        item.pop("reimportReviewRequired", None)
        write(db, u, lesson, items)
        implementation.audit(db, u, "weekend.courseware.approve", f"lesson={lid}:stage={b.stageNo}:page={page}:template={template_id}")
        db.commit()
        return payload(db, lesson)

    @router.post("/teacher/weekend/lessons/{lid}/courseware/remove")
    def remove(lid: int, b: PageBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        lesson = my_lesson(db, u, lid)
        items = items_of(row_for(db, lesson))
        item = find(items, b.stageNo, b.page)
        if item is None:
            raise HTTPException(404, "这一页没有课件")
        drop_template(db, u, lesson, item.get("templateId"))
        items.remove(item)
        write(db, u, lesson, items)
        return payload(db, lesson)

    @router.get("/teacher/weekend/courseware/templates")
    def list_templates(subject: str = "", u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """This school's saved courseware templates, newest first."""
        need(u, "teacher")
        qt = register_courseware_template_table(implementation)
        q = select(qt).where(qt.c.school_id == u.school_id)
        if subject in cw.TEMPLATES:
            q = q.where(qt.c.subject == subject)
        rows = db.execute(q.order_by(qt.c.id.desc()).limit(200)).all()
        return {"items": [{"id": r.id, "name": r.name, "kind": r.kind, "kindLabel": cw.KIND_LABEL.get(r.kind, r.kind),
                           "grade": r.grade, "subject": r.subject, "stageNo": r.stage_no, "page": r.page,
                           "writtenTask": bool(r.written_task)} for r in rows]}

    @router.post("/teacher/weekend/lessons/{lid}/courseware/save-as-template")
    def save_as_template(lid: int, b: TemplateBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Save one page's current courseware as a template this school can reuse in other lessons."""
        lesson = my_lesson(db, u, lid)
        page = checked_page(lesson, b.stageNo, b.page)
        item = find(items_of(row_for(db, lesson)), b.stageNo, page)
        if item is None:
            raise HTTPException(404, "这一页还没有课件，请先生成或填写")
        try:
            params = cw.clean(item["kind"], item["params"], lesson.reading_plan or "")
        except ValueError as e:
            raise HTTPException(400, f"这一页的课件参数还不完整，不能存为模板（{e}）")
        name = (b.name or "").strip()[:80] or f"{lesson.subject}第{lesson.lesson_no}课 第{b.stageNo}环节"
        qt = register_courseware_template_table(implementation)
        tid = db.execute(insert(qt).values(school_id=u.school_id, grade=lesson_grade(db, lesson), subject=lesson.subject,
                                           name=name, kind=item["kind"], stage_no=b.stageNo, page=page,
                                           params_json=json.dumps(params, ensure_ascii=False),
                                           written_task=bool(item.get("writtenTask")), source_lesson_id=lesson.id,
                                           created_by=u.id, created_at=datetime.utcnow())).inserted_primary_key[0]
        implementation.audit(db, u, "weekend.courseware.save_template", f"lesson={lid}:stage={b.stageNo}:page={page}:template={tid}")
        db.commit()
        return {"templateId": tid, "name": name, "kind": item["kind"]}

    @router.post("/teacher/weekend/lessons/{lid}/courseware/from-template")
    def from_template(lid: int, b: ApplyTemplateBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Copy a saved template onto one page of this lesson; re-validated and stored as a draft."""
        lesson = my_lesson(db, u, lid)
        page = checked_page(lesson, b.stageNo, b.page)
        qt = register_courseware_template_table(implementation)
        row = db.execute(select(qt).where(qt.c.id == b.templateId, qt.c.school_id == u.school_id)).first()
        if row is None:
            raise HTTPException(404, "没有找到这个模板")
        if row.subject != lesson.subject:
            raise HTTPException(400, "这个模板属于另一门学科，不能用在当前课程")
        try:
            params = cw.clean(row.kind, json.loads(row.params_json or "{}"), lesson.reading_plan or "")
        except ValueError as e:
            raise HTTPException(400, f"这个模板套用到本节课不合适（{e}），可以改用生成或手动填写")
        pages = stage_pages(lesson, b.stageNo)
        page_text = pages[page] if page is not None else ""
        upsert(db, u, lesson, b.stageNo, page, row.kind, params, bool(row.written_task), page_text)
        implementation.audit(db, u, "weekend.courseware.from_template", f"lesson={lid}:stage={b.stageNo}:page={page}:template={row.id}")
        db.commit()
        return payload(db, lesson)

    @router.post("/teacher/weekend/sessions/{sid}/courseware/view")
    def set_view(sid: int, b: ViewBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Teacher drags, turns or reveals during class: stores the screen state only (no AI)."""
        need(u, "teacher")
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id,
                                                sessions.c.teacher_id == u.id).with_for_update()).first()
        if row is None:
            raise HTTPException(404, "没有找到这节课堂")
        if row.status != "running":
            raise HTTPException(409, "这节课还没开始或已结束")
        c = db.execute(select(t).where(t.c.school_id == row.school_id, t.c.lesson_id == row.lesson_id).with_for_update()).first()
        cursor = db.execute(select(slide).where(slide.c.session_id == row.id)).first()
        index = int(cursor.idx) if cursor is not None and int(cursor.stage_no) == int(row.current_stage) else 0
        pages = stage_pages(db.get(Lesson, row.lesson_id), int(row.current_stage))
        index = max(0, min(index, len(pages) - 1)) if pages else index      # same clamp as the screen state
        shown, note = courseware_for_session(implementation, db, row, index)
        if shown is None or c is None:
            raise HTTPException(409, note or "当前页没有互动课件")
        item = next(i for i in items_of(c) if i.get("approved") is not None and int(i["stage"]) == int(row.current_stage)
                    and i.get("page") == shown["page"])
        view = cw.clean_view(item["kind"], item["approved"], b.view)
        live = json.loads(c.live_json or "{}")
        live[f"{sid}:{int(row.current_stage)}:{shown['page']}"] = view
        db.execute(update(t).where(t.c.id == c.id).values(live_json=json.dumps(live, ensure_ascii=False)))
        db.commit()
        return {"view": view}

    app.include_router(router)
    app.state.weekend_courseware_installed = True
    app.state.weekend_courseware_router = router
    return router


__all__ = ["courseware_for_session", "install_weekend_courseware", "items_of", "register_courseware_table",
           "register_courseware_template_table", "stage_pages"]




