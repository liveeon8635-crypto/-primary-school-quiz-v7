"""Semantic answer matching for auto-graded elementary-school questions.

The legacy matcher compared normalized strings (and bare numeric values).  This
module keeps that behaviour for ordinary answers while adding two safeguards:

* mathematically equivalent numeric forms such as 1/2, 0.5 and 50% can match;
* units are enforced when the question asks for a dimensional answer without
  already supplying the unit next to the blank / in the prompt.

No schema migration is required.  AI-generated answers are enriched before they
are saved so the teacher preview and stored reference answer stay aligned with
the grading rule.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from fractions import Fraction
import re
from typing import Any


# Longer / more specific aliases must win before shorter ones.
_UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "立方厘米": ("立方厘米", "cm³", "cm3", "cm^3"),
    "立方分米": ("立方分米", "dm³", "dm3", "dm^3"),
    "立方米": ("立方米", "m³", "m3", "m^3"),
    "平方厘米": ("平方厘米", "cm²", "cm2", "cm^2", "平方公分"),
    "平方分米": ("平方分米", "dm²", "dm2", "dm^2"),
    "平方米": ("平方米", "m²", "m2", "m^2"),
    "平方千米": ("平方千米", "km²", "km2", "km^2"),
    "毫米": ("毫米", "mm"),
    "厘米": ("厘米", "cm", "公分"),
    "分米": ("分米", "dm"),
    "千米": ("千米", "km", "公里"),
    "米": ("米", "m"),
    "毫升": ("毫升", "ml", "mL"),
    "升": ("升", "l", "L"),
    "千克": ("千克", "kg", "公斤"),
    "克": ("克", "g"),
    "吨": ("吨", "t"),
    "平方度": ("平方度",),
    "元": ("元", "人民币元"),
    "角": ("角",),
    "分": ("分",),
    "棵": ("棵",),
    "人": ("人",),
    "个": ("个",),
    "本": ("本",),
    "支": ("支",),
    "张": ("张",),
    "只": ("只",),
    "辆": ("辆",),
    "盒": ("盒",),
    "袋": ("袋",),
    "分钟": ("分钟", "min"),
    "小时": ("小时", "h"),
    "秒": ("秒", "s"),
    "天": ("天",),
}

_ALIAS_TO_UNIT: dict[str, str] = {}
for _canonical, _aliases in _UNIT_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_TO_UNIT[_alias.lower()] = _canonical

_SORTED_ALIASES = sorted(_ALIAS_TO_UNIT, key=len, reverse=True)

_LENGTH_TO_AREA = {
    "毫米": "平方毫米",
    "厘米": "平方厘米",
    "分米": "平方分米",
    "米": "平方米",
    "千米": "平方千米",
}
_LENGTH_TO_VOLUME = {
    "厘米": "立方厘米",
    "分米": "立方分米",
    "米": "立方米",
}
_LENGTH_UNITS = {"毫米", "厘米", "分米", "米", "千米"}
_MASS_UNITS = {"克", "千克", "吨"}
_CAPACITY_UNITS = {"毫升", "升"}
_TIME_UNITS = {"秒", "分钟", "小时", "天"}


def normalize_text(value: Any) -> str:
    s = str(value or "").strip().lower()
    table = str.maketrans(
        {
            "，": ",",
            "。": ".",
            "（": "(",
            "）": ")",
            "：": ":",
            "－": "-",
            "—": "-",
            "＋": "+",
            "×": "*",
            "÷": "/",
            "％": "%",
            "　": " ",
        }
    )
    return "".join(s.translate(table).split())


def _canonical_unit_from_suffix(value: str) -> tuple[str, str]:
    raw = normalize_text(value)
    for alias in _SORTED_ALIASES:
        if raw.endswith(alias):
            return raw[: -len(alias)], _ALIAS_TO_UNIT[alias]
    return raw, ""


def _numeric_value(value: str) -> Decimal | None:
    raw = normalize_text(value)
    if not raw:
        return None
    try:
        if raw.endswith("%"):
            return Decimal(raw[:-1]) / Decimal(100)
        if "/" in raw and raw.count("/") == 1:
            left, right = raw.split("/", 1)
            if re.fullmatch(r"[+-]?\d+", left) and re.fullmatch(r"[+-]?\d+", right):
                denominator = int(right)
                if denominator == 0:
                    return None
                frac = Fraction(int(left), denominator)
                return Decimal(frac.numerator) / Decimal(frac.denominator)
        return Decimal(raw)
    except (InvalidOperation, ValueError, ZeroDivisionError):
        return None


def _numeric_equal(left: str, right: str) -> bool:
    a, b = _numeric_value(left), _numeric_value(right)
    return a is not None and b is not None and abs(a - b) <= Decimal("1e-12")


def _units_in_text(text: str) -> list[str]:
    raw = str(text or "")
    # Find longest aliases first and discard overlapping shorter matches, e.g.
    # “平方厘米” must not also be read as “厘米” + “米”.
    candidates: list[tuple[int, int, str]] = []
    for alias in sorted(_ALIAS_TO_UNIT, key=len, reverse=True):
        for match in re.finditer(re.escape(alias), raw, flags=re.IGNORECASE):
            candidates.append(
                (match.start(), match.end(), _ALIAS_TO_UNIT[alias.lower()])
            )
    candidates.sort(key=lambda x: (-(x[1] - x[0]), x[0]))
    accepted: list[tuple[int, int, str]] = []
    for start, end, unit in candidates:
        if any(not (end <= a_start or start >= a_end) for a_start, a_end, _ in accepted):
            continue
        accepted.append((start, end, unit))
    accepted.sort(key=lambda x: x[0])
    result: list[str] = []
    for _, _, unit in accepted:
        if unit not in result:
            result.append(unit)
    return result


def _provided_unit(question_text: str) -> str:
    """Unit already supplied by the stem, so the input may be numeric only."""
    text = str(question_text or "")
    alias_group = "|".join(re.escape(x) for x in sorted(_ALIAS_TO_UNIT, key=len, reverse=True))
    patterns = (
        rf"(?:_{{2,}}|＿+|\(\s*\)|（\s*）)\s*({alias_group})",
        rf"(?:多少|几)\s*({alias_group})(?:[？?。,.，]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _ALIAS_TO_UNIT.get(match.group(1).lower(), "")
    return ""


def infer_unit_semantics(
    *,
    question_text: str,
    answer: str = "",
    subject: str = "数学",
    question_type: str = "",
) -> dict[str, str]:
    """Infer whether a unit is required, already provided, or irrelevant."""
    if str(subject or "").strip() not in {"数学", ""}:
        return {"policy": "none", "unit": ""}

    provided = _provided_unit(question_text)
    answer_value, answer_unit = _canonical_unit_from_suffix(answer)
    if provided:
        return {"policy": "provided_in_stem", "unit": provided}

    # If the authored reference answer already has a unit, respect it.
    if answer_unit:
        return {"policy": "required", "unit": answer_unit}

    text = str(question_text or "")
    units = _units_in_text(text)

    # Area / volume need dimensional conversion from the measurements in stem.
    if "面积" in text:
        area_units = [u for u in units if u.startswith("平方")]
        if len(set(area_units)) == 1:
            return {"policy": "required", "unit": area_units[0]}
        lengths = [u for u in units if u in _LENGTH_UNITS and u in _LENGTH_TO_AREA]
        if len(set(lengths)) == 1:
            return {"policy": "required", "unit": _LENGTH_TO_AREA[lengths[0]]}

    if "体积" in text:
        volume_units = [u for u in units if u.startswith("立方")]
        if len(set(volume_units)) == 1:
            return {"policy": "required", "unit": volume_units[0]}
        lengths = [u for u in units if u in _LENGTH_TO_VOLUME]
        if len(set(lengths)) == 1:
            return {"policy": "required", "unit": _LENGTH_TO_VOLUME[lengths[0]]}

    # Common single-dimension quantities.
    if any(key in text for key in ("周长", "长度", "距离", "路程", "高是多少", "底是多少")):
        lengths = [u for u in units if u in _LENGTH_UNITS]
        if len(set(lengths)) == 1:
            return {"policy": "required", "unit": lengths[0]}

    if any(key in text for key in ("多少钱", "总价", "价钱", "价格")):
        return {"policy": "required", "unit": "元"}

    if any(key in text for key in ("质量", "重量", "重多少")):
        masses = [u for u in units if u in _MASS_UNITS]
        if len(set(masses)) == 1:
            return {"policy": "required", "unit": masses[0]}

    if any(key in text for key in ("容量", "容积")):
        caps = [u for u in units if u in _CAPACITY_UNITS]
        if len(set(caps)) == 1:
            return {"policy": "required", "unit": caps[0]}

    if any(key in text for key in ("用时", "时间", "需要多久")):
        times = [u for u in units if u in _TIME_UNITS]
        if len(set(times)) == 1:
            return {"policy": "required", "unit": times[0]}

    return {"policy": "none", "unit": ""}


def answer_matches(
    question: Any,
    value: Any,
    answer: Any,
    accepted: list[Any] | tuple[Any, ...] | None = None,
) -> bool:
    """Compare one response using numeric equivalence plus unit semantics."""
    got_raw = str(value or "")
    got_value, got_unit = _canonical_unit_from_suffix(got_raw)
    candidates = [str(answer or "")] + [str(x) for x in (accepted or [])]
    semantics = infer_unit_semantics(
        question_text=str(getattr(question, "text", "") or ""),
        answer=str(answer or ""),
        subject=str(getattr(question, "subject", "") or ""),
        question_type=str(getattr(question, "question_type", "") or ""),
    )
    policy, inferred_unit = semantics["policy"], semantics["unit"]

    for candidate in candidates:
        want_value, want_unit = _canonical_unit_from_suffix(candidate)
        same_value = (
            _numeric_equal(got_value, want_value)
            if _numeric_value(got_value) is not None and _numeric_value(want_value) is not None
            else normalize_text(got_value) == normalize_text(want_value) and bool(normalize_text(want_value))
        )
        if not same_value:
            continue

        expected_unit = want_unit or inferred_unit
        if policy == "required":
            if expected_unit and got_unit == expected_unit:
                return True
            continue
        if policy == "provided_in_stem":
            # Typing the already-provided correct unit is harmless; a different
            # unit is not.
            if not got_unit or got_unit == expected_unit:
                return True
            continue
        if want_unit:
            if got_unit == want_unit:
                return True
            continue
        if not got_unit:
            return True
    return False


def enrich_generated_item(item: dict[str, Any]) -> dict[str, Any]:
    """Make the generated reference answer explicit when a unit is required."""
    out = dict(item)
    qt = str(out.get("question_type") or "").strip().lower()
    if qt not in {"fill_blank", "calculation", "short_answer"}:
        return out
    answer = str(out.get("answer") or "").strip()
    if not answer:
        return out
    semantics = infer_unit_semantics(
        question_text=str(out.get("text") or ""),
        answer=answer,
        subject=str(out.get("subject") or ""),
        question_type=qt,
    )
    unit, policy = semantics["unit"], semantics["policy"]
    base, existing_unit = _canonical_unit_from_suffix(answer)
    if policy == "required" and unit and not existing_unit and _numeric_value(base) is not None:
        out["answer"] = f"{answer}{unit}"
        # Numeric-only accepted answers must not bypass a required unit.
        accepted = []
        for candidate in out.get("accepted_answers") or []:
            _, candidate_unit = _canonical_unit_from_suffix(str(candidate))
            if candidate_unit == unit:
                accepted.append(str(candidate))
        out["accepted_answers"] = accepted
    out["answer_unit"] = unit
    out["answer_unit_policy"] = policy
    return out


__all__ = [
    "answer_matches",
    "enrich_generated_item",
    "infer_unit_semantics",
    "normalize_text",
]
