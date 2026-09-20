"""Deterministic quality fallback for AI reinforcement figures.

AI is allowed to choose when a structured figure is useful, but obvious visual
math tasks should not degrade to text-only questions when the provider omits
figure metadata.  This module post-processes reinforcement drafts without
changing the underlying question or answer.
"""

from __future__ import annotations

from functools import wraps
import re
from typing import Any

from changying.services.answer_semantics import enrich_generated_item
from changying.services.question_figure_quality import normalize_question_figure


VISUAL_FIGURE_TYPES = {"coordinate_grid", "geometry", "line_segment", "bar_chart", "object_group"}


def _existing_figure(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("figure")
    if isinstance(value, dict) and str(value.get("type") or "").strip().lower() in VISUAL_FIGURE_TYPES:
        return value
    return {}


def _measurement_labels(text: str) -> dict[str, str]:
    """Extract a few dimension phrases for display without solving the problem."""
    patterns = [
        ("上底", r"上底(?:是|为)?\s*([0-9]+(?:\.[0-9]+)?\s*(?:厘米|分米|米|千米)?)"),
        ("下底", r"下底(?:是|为)?\s*([0-9]+(?:\.[0-9]+)?\s*(?:厘米|分米|米|千米)?)"),
        ("底", r"(?<!上)(?<!下)底(?:是|为)?\s*([0-9]+(?:\.[0-9]+)?\s*(?:厘米|分米|米|千米)?)"),
        ("高", r"高(?:是|为)?\s*([0-9]+(?:\.[0-9]+)?\s*(?:厘米|分米|米|千米)?)"),
        ("长", r"长(?:是|为)?\s*([0-9]+(?:\.[0-9]+)?\s*(?:厘米|分米|米|千米)?)"),
        ("宽", r"宽(?:是|为)?\s*([0-9]+(?:\.[0-9]+)?\s*(?:厘米|分米|米|千米)?)"),
    ]
    labels: dict[str, str] = {}
    for label, pattern in patterns:
        match = re.search(pattern, text)
        if match:
            labels[label] = match.group(1).replace(" ", "")
    return labels


def _coordinate_points(text: str) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    # Match optional Latin point labels such as A(3,4), plus bare number pairs.
    for label, x, y in re.findall(
        r"([A-Za-z]?)\s*[（(]\s*(-?\d+(?:\.\d+)?)\s*[,，]\s*(-?\d+(?:\.\d+)?)\s*[)）]",
        text,
    ):
        points.append({"label": label or "", "x": float(x), "y": float(y)})
        if len(points) >= 8:
            break
    return points


def _merge_semantic_figure(item: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    """Enrich a valid AI figure with labels that are explicit in the question text."""
    if not existing:
        return {}
    figure = dict(existing)
    text = str(item.get("text") or "")
    knowledge = str(item.get("knowledge") or "")
    combined = f"{knowledge} {text}"
    kind = str(figure.get("type") or "").strip().lower()

    if kind == "geometry":
        labels = dict(figure.get("labels") or {})
        for key, value in _measurement_labels(text).items():
            labels.setdefault(key, value)
        if labels:
            figure["labels"] = labels
        if not str(figure.get("shape") or "").strip():
            if "平行四边形" in combined:
                figure["shape"] = "parallelogram"
            elif "三角形" in combined:
                figure["shape"] = "triangle"
            elif "梯形" in combined:
                figure["shape"] = "trapezoid"
            elif "组合图形" in combined:
                figure["shape"] = "composite_rect"
            elif "长方形" in combined or "正方形" in combined:
                figure["shape"] = "rectangle"
    elif kind == "coordinate_grid":
        if not figure.get("points"):
            points = _coordinate_points(text)
            if points:
                figure["points"] = points
    elif kind == "line_segment":
        if not figure.get("segments") and ("植树" in combined or "每隔" in text):
            figure["segments"] = [{"label": "间隔", "ratio": 1} for _ in range(6)]
    return figure


def infer_reinforcement_figure(item: dict[str, Any]) -> dict[str, Any]:
    """Return a conservative structured figure for clearly visual math items."""
    if str(item.get("subject") or "").strip() not in {"数学", ""}:
        # Do not preserve accidental mathematical figures on Chinese or other
        # subjects. Subject-specific visual schemas can be introduced later.
        return {}

    existing = _existing_figure(item)
    if existing:
        return normalize_question_figure(item, _merge_semantic_figure(item, existing))

    knowledge = str(item.get("knowledge") or "")
    text = str(item.get("text") or "")
    combined = f"{knowledge} {text}"
    labels = _measurement_labels(text)

    if any(key in combined for key in ("位置", "数对", "坐标")):
        points = _coordinate_points(text)
        xmax = max([8.0] + [float(p["x"]) + 1 for p in points if float(p["x"]) >= 0])
        ymax = max([8.0] + [float(p["y"]) + 1 for p in points if float(p["y"]) >= 0])
        return normalize_question_figure(item, {
            "type": "coordinate_grid",
            "title": "位置示意图",
            "xMax": min(12, xmax),
            "yMax": min(12, ymax),
            "points": points,
        })

    if "植树" in combined or ("每隔" in text and any(unit in text for unit in ("米", "厘米", "分米"))):
        return normalize_question_figure(item, {
            "type": "line_segment",
            "title": "植树间隔示意图（端点是否栽树按题意判断）",
            "segments": [{"label": "间隔", "ratio": 1} for _ in range(6)],
        })

    if "组合图形" in combined or ("长方形" in text and any(key in text for key in ("剪去", "剩余", "挖去", "去掉", "中间"))):
        return normalize_question_figure(item, {
            "type": "geometry",
            "shape": "composite_rect",
            "title": "组合图形示意图",
            "labels": labels,
        })

    shape = ""
    if "平行四边形" in combined:
        shape = "parallelogram"
    elif "三角形" in combined:
        shape = "triangle"
    elif "梯形" in combined:
        shape = "trapezoid"
    elif any(key in combined for key in ("长方形", "正方形", "面积")) and ("如图" in text or labels):
        shape = "rectangle"

    if shape:
        return {
            "type": "geometry",
            "shape": shape,
            "title": "题目图示",
            "labels": labels,
        }

    return {}


def install_reinforcement_figure_fallback(implementation: Any) -> None:
    """Patch the existing FastAPI route result without changing its dependencies."""
    app = implementation.app
    if getattr(app.state, "reinforcement_figure_fallback_installed", False):
        return

    target = "/teacher/students/{sid}/reinforcement/generate"
    for route in app.routes:
        if getattr(route, "path", None) != target or "POST" not in getattr(route, "methods", set()):
            continue
        original = route.dependant.call

        @wraps(original)
        def patched(*args: Any, __original=original, **kwargs: Any):
            result = __original(*args, **kwargs)
            if not isinstance(result, dict):
                return result
            items = result.get("items")
            if not isinstance(items, list):
                return result
            patched_items = []
            for raw in items:
                if not isinstance(raw, dict):
                    patched_items.append(raw)
                    continue
                item = enrich_generated_item(dict(raw))
                item["figure"] = infer_reinforcement_figure(item)
                patched_items.append(item)
            payload = dict(result)
            payload["items"] = patched_items
            payload["figureFallback"] = True
            return payload

        route.dependant.call = patched
        route.endpoint = patched
        app.state.reinforcement_figure_fallback_installed = True
        return

    raise RuntimeError("reinforcement generate route not found for figure fallback")


__all__ = ["infer_reinforcement_figure", "install_reinforcement_figure_fallback"]
