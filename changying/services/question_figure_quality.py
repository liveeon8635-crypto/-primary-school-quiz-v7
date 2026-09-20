"""Question-figure quality normalization for stored online practice questions.

This layer repairs incomplete-but-recoverable structured figures at read time.
It does not rewrite historical question rows, so already-assigned work can
benefit immediately after deploy without mutating production data.
"""

from __future__ import annotations

import re
from typing import Any


def _num(text: str) -> float | None:
    try:
        return float(text)
    except Exception:
        return None


def _fmt_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _first_pair(text: str) -> tuple[float, float] | None:
    match = re.search(
        r"[（(]\s*(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)\s*[)）]",
        text,
    )
    if not match:
        return None
    return float(match.group(1)), float(match.group(2))


def _length_spacing(text: str) -> tuple[float, float] | None:
    length = re.search(r"长\s*(\d+(?:\.\d+)?)\s*(?:米|厘米|分米)", text)
    spacing = re.search(r"每隔\s*(\d+(?:\.\d+)?)\s*(?:米|厘米|分米)", text)
    if not length or not spacing:
        return None
    a, b = _num(length.group(1)), _num(spacing.group(1))
    if a is None or b is None or b <= 0:
        return None
    return a, b


def _outer_inner_rectangles(text: str) -> dict[str, str]:
    values = re.findall(
        r"长\s*(\d+(?:\.\d+)?)\s*(?:米|厘米|分米).*?宽\s*(\d+(?:\.\d+)?)\s*(?:米|厘米|分米)",
        text,
    )
    if len(values) < 2:
        return {}
    outer_l, outer_w = values[0]
    inner_l, inner_w = values[1]
    unit_match = re.search(r"长\s*\d+(?:\.\d+)?\s*(米|厘米|分米)", text)
    unit = unit_match.group(1) if unit_match else ""
    return {
        "外长": f"{outer_l}{unit}",
        "外宽": f"{outer_w}{unit}",
        "内长": f"{inner_l}{unit}",
        "内宽": f"{inner_w}{unit}",
    }


def _field(question: Any, key: str) -> Any:
    if isinstance(question, dict):
        return question.get(key)
    return getattr(question, key, "")


def normalize_question_figure(question: Any, figure: Any) -> dict[str, Any]:
    """Repair semantic figure metadata using facts explicitly stated in the stem."""

    if not isinstance(figure, dict):
        return {}
    kind = str(figure.get("type") or "").strip().lower()
    if not kind:
        return {}

    out = dict(figure)
    text = str(_field(question, "text") or "")
    knowledge = str(_field(question, "knowledge") or "")
    combined = f"{knowledge} {text}"

    if kind == "coordinate_grid":
        points = out.get("points")
        needs_point = not isinstance(points, list) or not points or any(
            not isinstance(p, dict)
            or not isinstance(p.get("x"), (int, float))
            or not isinstance(p.get("y"), (int, float))
            for p in points
        )
        pair = _first_pair(text)
        if needs_point and pair is not None:
            x, y = pair
            label_match = re.search(r"点\s*([A-Za-z])", text)
            out["points"] = [{"label": label_match.group(1) if label_match else "A", "x": x, "y": y}]
            out["xMax"] = max(8, min(12, int(max(0, x)) + 2))
            out["yMax"] = max(8, min(12, int(max(0, y)) + 2))
        return out

    if kind == "line_segment" and ("植树" in combined or "每隔" in text):
        values = _length_spacing(text)
        if values is not None:
            length, spacing = values
            intervals = length / spacing
            rounded = int(round(intervals))
            if abs(intervals - rounded) < 1e-9 and 1 <= rounded <= 12:
                out["segments"] = [{"label": "间隔", "ratio": 1} for _ in range(rounded)]
                out["title"] = f"{_fmt_number(length)}÷{_fmt_number(spacing)}={rounded} 个间隔"
        return out

    if kind == "geometry":
        labels = _outer_inner_rectangles(text)
        if labels and any(word in text for word in ("中间", "水池", "挖去", "剪去", "去掉")):
            out["shape"] = "nested_rect"
            out["labels"] = labels
            out["title"] = out.get("title") or "组合图形示意图"
        return out

    return out


__all__ = ["normalize_question_figure"]
