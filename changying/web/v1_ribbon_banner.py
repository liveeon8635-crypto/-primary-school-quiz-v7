"""Header banner animation: 哪吒用混天绫束缚苍龙, ending on a shimmering ribbon.

The scene is one inline SVG driven by SMIL animations that all share a 30 s
timeline, so the whole story replays every 30 seconds without any script.
Everything outside the ``cy-scene`` group (the silk waves, their shimmer and
the sparkles) is the "final" state and stays on screen the entire time.
"""
from __future__ import annotations

import json
import math

# 志莽行书 (OFL) subset to the four brand characters 长缨辅学 only.
BRAND_FONT_B64 = "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"

DUR = "30s"

# Dragon body, tail -> head, as three cubic segments in the 1600x68 viewBox.
_SEGS = [
    ((640, 38), (690, 56), (730, 18), (790, 34)),
    ((790, 34), (850, 50), (880, 54), (930, 30)),
    ((930, 30), (980, 6), (1010, 14), (1060, 26)),
]
_DRAGON_D = "M640 38 C690 56 730 18 790 34 S880 54 930 30 S1010 14 1060 26"


def _bez(seg, t):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = seg
    u = 1 - t
    x = u**3 * x0 + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * x3
    y = u**3 * y0 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * y3
    dx = 3 * u * u * (x1 - x0) + 6 * u * t * (x2 - x1) + 3 * t * t * (x3 - x2)
    dy = 3 * u * u * (y1 - y0) + 6 * u * t * (y2 - y1) + 3 * t * t * (y3 - y2)
    return x, y, math.degrees(math.atan2(dy, dx))


def _kt(values):
    return ";".join(f"{v:g}" for v in values)


def _anim(attr, key_times, values, extra=""):
    return (
        f'<animate attributeName="{attr}" dur="{DUR}" repeatCount="indefinite" '
        f'keyTimes="{_kt(key_times)}" values="{";".join(str(v) for v in values)}" {extra}/>'
    )


def _coil_rings() -> str:
    rings = []
    for i in range(6):
        seg = _SEGS[1]
        x, y, ang = _bez(seg, 0.08 + i * 0.16)
        start = 0.14 + i * 0.012
        end = start + 0.02
        rings.append(
            f'<g transform="translate({x:.1f} {y:.1f}) rotate({ang + 90:.1f})">'
            f'<ellipse rx="9" ry="3.4" fill="none" stroke="#e11d2a" stroke-width="2.6" opacity="0">'
            + _anim("opacity", [0, start, end, 1], [0, 0, 1, 1])
            + _anim("rx", [0, start, end, 1], [9, 9, 4.6, 4.6])
            + "</ellipse></g>"
        )
    return "".join(rings)


def _jitter() -> str:
    steps = 14
    times = [0, 0.14] + [0.14 + 0.10 * (i + 1) / steps for i in range(steps)] + [1]
    values = ["0 0", "0 0"] + [("0 -1.6" if i % 2 == 0 else "0 1.6") for i in range(steps - 1)] + ["0 0", "0 0"]
    return (
        f'<animateTransform attributeName="transform" type="translate" dur="{DUR}" repeatCount="indefinite" '
        f'keyTimes="{_kt(times)}" values="{";".join(values)}"/>'
    )


def _build() -> str:
    scene_op = _anim("opacity", [0, 0.02, 0.26, 0.30, 1], [0, 1, 1, 0, 0])
    draw = _anim("stroke-dashoffset", [0, 0.02, 0.10, 1], [1000, 1000, 0, 0])
    lasso = _anim("stroke-dashoffset", [0, 0.10, 0.14, 1], [1000, 1000, 0, 0])
    head_motion = (
        f'<animateMotion dur="{DUR}" repeatCount="indefinite" rotate="auto" calcMode="linear" '
        f'keyPoints="0;0;1;1" keyTimes="0;0.02;0.10;1"><mpath href="#cyDragonPath"/></animateMotion>'
    )
    nezha_in = (
        f'<animateTransform attributeName="transform" type="translate" additive="sum" dur="{DUR}" '
        f'repeatCount="indefinite" keyTimes="0;0.03;0.10;1" values="-120 0;-120 0;0 0;0 0"/>'
    )
    bob = (
        f'<animateTransform attributeName="transform" type="translate" dur="{DUR}" repeatCount="indefinite" '
        f'keyTimes="0;0.10;0.14;0.18;0.22;0.26;1" values="0 0;0 0;0 -2;0 1;0 -2;0 0;0 0"/>'
    )
    flame = (
        '<animateTransform attributeName="transform" type="scale" dur="0.35s" repeatCount="indefinite" '
        'values="1 1;1.35 0.8;1 1"/>'
    )
    star = "M0 -4 L1 -1 L4 0 L1 1 L0 4 L-1 1 L-4 0 L-1 -1Z"
    sparkles = "".join(
        f'<path d="{star}" transform="translate({x} {y})" fill="#fff6c8" opacity="0">'
        + _anim("opacity", [0, b, b + 0.03, b + 0.06, 1], [0, 0, 1, 0, 0])
        + "</path>"
        for x, y, b in ((330, 18, 0.32), (520, 50, 0.45), (760, 14, 0.58), (1010, 52, 0.7), (1180, 20, 0.82), (1420, 44, 0.9))
    )
    shimmer = (
        '<path d="M0 46C220 8 400 74 640 40S1020 4 1260 42S1500 64 1600 28" pathLength="1000" fill="none" '
        'stroke="#fff" stroke-opacity=".85" stroke-width="3" stroke-linecap="round" stroke-dasharray="40 960">'
        '<animate attributeName="stroke-dashoffset" dur="6s" repeatCount="indefinite" values="1000;0"/></path>'
    )
    return (
        '<svg class="cy-ribbon" viewBox="0 0 1600 68" preserveAspectRatio="xMidYMid slice" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">'
        '<defs><linearGradient id="cyRib" x1="0" x2="1" y1="0" y2="0">'
        '<stop offset="0" stop-color="#ffe9a8"/><stop offset=".5" stop-color="#ff9a3c"/><stop offset="1" stop-color="#ffe9a8"/>'
        "</linearGradient>"
        f'<path id="cyDragonPath" d="{_DRAGON_D}"/></defs>'
        '<path d="M0 46C220 8 400 74 640 40S1020 4 1260 42S1500 64 1600 28L1600 68L0 68Z" fill="rgba(255,255,255,.10)"/>'
        '<path d="M0 40C200 6 380 66 620 34S1000 2 1240 36S1500 58 1600 22" fill="none" stroke="url(#cyRib)" stroke-width="2.4" stroke-opacity=".8"/>'
        '<path d="M0 52C240 18 420 78 660 50S1040 14 1280 52S1520 68 1600 40" fill="none" stroke="rgba(255,255,255,.3)" stroke-width="1.4"/>'
        '<path d="M0 28C260 -4 440 52 700 24S1080 -8 1320 26S1540 44 1600 12" fill="none" stroke="rgba(120,0,10,.22)" stroke-width="3"/>'
        + shimmer
        + sparkles
        + f'<g class="cy-scene" opacity="0">{scene_op}<g transform="translate(110 0)">'
        # dragon
        f'<g>{_jitter()}'
        f'<path d="{_DRAGON_D}" pathLength="1000" fill="none" stroke="#0e6f6a" stroke-width="7.4" stroke-linecap="round" stroke-dasharray="1000" stroke-dashoffset="1000">{draw}</path>'
        f'<path d="{_DRAGON_D}" pathLength="1000" fill="none" stroke="#2fc4b2" stroke-width="5" stroke-linecap="round" stroke-dasharray="1000" stroke-dashoffset="1000">{draw}</path>'
        f'<path d="{_DRAGON_D}" pathLength="1000" fill="none" stroke="#c8fff0" stroke-width="1.2" stroke-linecap="round" stroke-dasharray="2 5" stroke-dashoffset="0" opacity=".8"/>'
        '<g><path d="M-2 -5 L11 -3 L15 0 L11 3.4 L-2 5 Z" fill="#2fc4b2" stroke="#0e6f6a" stroke-width="1"/>'
        '<path d="M2 -5 L-3 -10 M6 -4 L3 -10" stroke="#e8d28a" stroke-width="1.5" stroke-linecap="round"/>'
        '<path d="M12 1 L22 6 M12 -1 L22 -6" stroke="#e8d28a" stroke-width="1" fill="none"/>'
        '<circle cx="8" cy="-1.4" r="1.2" fill="#fff"/><circle cx="8.3" cy="-1.4" r=".55" fill="#7a0010"/>'
        f"{head_motion}</g></g>"
        # lasso + coils
        f'<path d="M603 28C690 -6 800 6 872 40" pathLength="1000" fill="none" stroke="#e11d2a" stroke-width="3.2" stroke-linecap="round" stroke-dasharray="1000" stroke-dashoffset="1000">{lasso}</path>'
        + _coil_rings()
        # nezha
        + f'<g transform="translate(590 34)">{nezha_in}<g>{bob}'
        '<g transform="translate(-6 14)"><circle r="4.6" fill="#ff5a1f" stroke="#ffb02e" stroke-width="1.6"/>'
        f'<path d="M-5 0 q-9 -3 -15 0 q9 3 15 0Z" fill="#ffd34d">{flame}</path></g>'
        '<g transform="translate(6 14)"><circle r="4.6" fill="#ff5a1f" stroke="#ffb02e" stroke-width="1.6"/>'
        f'<path d="M-5 0 q-9 -3 -15 0 q9 3 15 0Z" fill="#ffd34d">{flame}</path></g>'
        '<path d="M-5 2 L5 2 L4.2 11 L-4.2 11 Z" fill="#e0242c"/><path d="M-4.4 7 H4.4" stroke="#f4c542" stroke-width="1.4"/>'
        '<path d="M4 3 L13 -5" stroke="#ffdcb8" stroke-width="2.4" stroke-linecap="round"/>'
        '<ellipse cx="9" cy="-1.4" rx="2" ry="3" fill="none" stroke="#f4c542" stroke-width="1.2" transform="rotate(40 9 -1.4)"/>'
        '<circle cx="0" cy="-4" r="5.2" fill="#ffdcb8"/><circle cx="-5.6" cy="-8.4" r="2.8" fill="#1b1b1b"/><circle cx="5.6" cy="-8.4" r="2.8" fill="#1b1b1b"/>'
        '<path d="M-5 -6.4 Q0 -10.4 5 -6.4" fill="#1b1b1b"/><circle cx="-1.8" cy="-3.6" r=".7" fill="#1b1b1b"/><circle cx="1.8" cy="-3.6" r=".7" fill="#1b1b1b"/>'
        '<circle cx="0" cy="-6.4" r=".8" fill="#e11d2a"/>'
        "</g></g></g></g></svg>"
    )


RIBBON_SVG = _build()
RIBBON_SVG_JSON = json.dumps(RIBBON_SVG, ensure_ascii=False)

__all__ = ["BRAND_FONT_B64", "RIBBON_SVG", "RIBBON_SVG_JSON"]
