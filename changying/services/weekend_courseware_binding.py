"""Conservative re-import binding for reviewed weekend courseware.

Only reuse a slide when its *entire student-visible source page* is identical.
Unknown, edited, or ambiguous pages must be regenerated and reviewed. No AI
calls, session mutations, or changes to published student answers are made here.
"""
from __future__ import annotations

from collections import Counter
from typing import Any


def rebind_unchanged_pages(
    items: list[dict[str, Any]],
    old_pages: dict[int, list[str]],
    new_pages: dict[int, list[str]],
) -> list[dict[str, Any]]:
    """Return only unambiguously unchanged items, with safe current page indexes.

    Matching the full source instead of the printed question number prevents an
    old diagram/answer from silently appearing on a modified problem. Duplicates
    fail closed. Session-specific live state is intentionally not touched.
    """
    result: list[dict[str, Any]] = []
    occupied: set[tuple[int, int | None]] = set()
    for item in items:
        stage = int(item.get("stage") or 0)
        before, after = old_pages.get(stage, []), new_pages.get(stage, [])
        old_index = item.get("page")
        if old_index is None:
            # Pages absent on both sides: retain only if source actually remains
            # unchanged. A one-item unpaged legacy lesson has no page to compare.
            if before or after:
                continue
            continue
        if not isinstance(old_index, int) or old_index < 0 or old_index >= len(before):
            continue
        source = before[old_index].strip()
        if not source or str(item.get("pageText") or "").strip() != source:
            continue
        # Approved source is a separate teacher authorization; never rebind an
        # approval when its last reviewed text differs.
        if item.get("approved") is not None and str(item.get("approvedPageText") or "").strip() != source:
            continue
        if Counter(p.strip() for p in before)[source] != 1:
            continue
        matches = [n for n, page in enumerate(after) if page.strip() == source]
        if len(matches) != 1:
            continue
        new_index = matches[0]
        # Written task templates use stage:page identifiers. Do not silently
        # move them without remapping their references in the written bank.
        if item.get("writtenTask") and new_index != old_index:
            continue
        key = (stage, new_index)
        if key in occupied:
            continue
        occupied.add(key)
        copied = dict(item)
        copied["page"] = new_index
        copied["pageText"] = after[new_index]
        if copied.get("approved") is not None:
            copied["approvedPageText"] = after[new_index]
        result.append(copied)
    return sorted(result, key=lambda it: (int(it["stage"]), int(it["page"])))
