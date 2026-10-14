"""Header banner: the silk 混天绫 that stays on screen after the title sequence.

This inline SVG is the shimmering silk (waves and sparkles) with the flying
Nezha cut-out sliding along it.
"""
from __future__ import annotations

import json

from changying.web.v1_nezha_icons import NEZHA_SPRITE_SIZE, NEZHA_SPRITE_WEBP_B64

# 志莽行书 (OFL) subset to the four brand characters 长缨辅学 only.
BRAND_FONT_B64 = "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"

def _build() -> str:
    star = "M0 -4 L1 -1 L4 0 L1 1 L0 4 L-1 1 L-4 0 L-1 -1Z"
    sparkles = "".join(
        f'<path d="{star}" transform="translate({x} {y})" fill="#fff6c8" opacity="0">'
        f'<animate attributeName="opacity" dur="30s" repeatCount="indefinite" '
        f'keyTimes="0;{b:g};{b + 0.03:g};{b + 0.06:g};1" values="0;0;1;0;0"/></path>'
        for x, y, b in ((330, 18, 0.32), (520, 50, 0.45), (760, 14, 0.58), (1010, 52, 0.7), (1180, 20, 0.82), (1420, 44, 0.9))
    )
    sw, sh = NEZHA_SPRITE_SIZE
    scale = 52 / sh
    w, h = sw * scale, sh * scale
    shimmer = (
        # the flying Nezha rides the gold silk from left to right, bobbing as he goes
        '<g><animateMotion dur="18s" repeatCount="indefinite" calcMode="linear" '
        'path="M-90 41C260 27 520 49 800 37S1300 27 1700 41"/>'
        '<g><animateTransform attributeName="transform" type="translate" dur=".8s" repeatCount="indefinite" '
        'values="0 0;0 -1.6;0 0"/>'
        f'<image href="data:image/webp;base64,{NEZHA_SPRITE_WEBP_B64}" x="{-w * 0.55:.2f}" y="{-h * 0.65:.2f}" '
        f'width="{w:.2f}" height="{h:.2f}"/></g></g>'
    )
    return (
        '<svg class="cy-ribbon" viewBox="0 0 1600 68" preserveAspectRatio="xMidYMid slice" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">'
        '<defs><linearGradient id="cyRib" x1="0" x2="1" y1="0" y2="0">'
        '<stop offset="0" stop-color="#ffe9a8"/><stop offset=".5" stop-color="#ff9a3c"/><stop offset="1" stop-color="#ffe9a8"/>'
        "</linearGradient></defs>"
        '<path d="M0 46C220 8 400 74 640 40S1020 4 1260 42S1500 64 1600 28L1600 68L0 68Z" fill="rgba(255,255,255,.10)"/>'
        '<path d="M0 41C260 27 520 49 800 37S1300 27 1600 41" fill="none" stroke="url(#cyRib)" stroke-width="3" stroke-linecap="round" stroke-opacity=".95"/>'
        '<path d="M0 52C240 18 420 78 660 50S1040 14 1280 52S1520 68 1600 40" fill="none" stroke="rgba(255,255,255,.3)" stroke-width="1.4"/>'
        '<path d="M0 28C260 -4 440 52 700 24S1080 -8 1320 26S1540 44 1600 12" fill="none" stroke="rgba(120,0,10,.22)" stroke-width="3"/>'
        + shimmer
        + sparkles
        + "</svg>"
    )


RIBBON_SVG = _build()
RIBBON_SVG_JSON = json.dumps(RIBBON_SVG, ensure_ascii=False)

__all__ = ["BRAND_FONT_B64", "RIBBON_SVG", "RIBBON_SVG_JSON"]
