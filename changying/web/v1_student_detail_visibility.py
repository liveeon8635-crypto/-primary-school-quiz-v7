"""Show the complete already-fetched student detail record in V1.

The student detail page historically rendered only the first few suggestions,
assignments, weak-knowledge rows, and timeline events even though the protected
growth-profile response had already delivered the full visible arrays.  Silent
truncation is misleading on a page whose purpose is the student's continuous
record, so this presentation-only patch removes those detail caps.

Homepage previews remain intentionally compact.  This patch adds no API calls,
writes no data, and changes no authorization behavior.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_STUDENT_DETAIL_VISIBILITY_MARKER = "changying_v1_student_detail_visibility_v1"

_DETAIL_CAPS = (
    ("suggestions.slice(0,4).map", "suggestions.map"),
    ("assignments.slice(0,6).map", "assignments.map"),
    ("weak.slice(0,6).map", "weak.map"),
    ("timeline.slice(0,10).map", "timeline.map"),
)

_DETAIL_CLARITY_REPLACEMENTS = (
    (
        '<span class="tag">监护人 ${s.parents?.length??\'—\'}</span>',
        '<span class="tag">家庭关联 · 监护人 ${s.parents?.length??\'—\'}</span>',
    ),
    (
        "<h2>历史时间线</h2><p>换班、换老师或升年级后仍保留在同一档案</p>",
        "<h2>成长档案时间线</h2><p>按时间倒序展示 · 最新记录在前；换班、换老师或升年级后仍保留在同一档案</p>",
    ),
)

_DETAIL_MOBILE_TARGETS = (
    (
        '<div class="card"><h2>需要关注 / 下一步教学</h2><div class="list" style="margin-top:12px">',
        '<div class="card"><h2>需要关注 / 下一步教学</h2><div id="suggestions" class="list" style="margin-top:12px">',
    ),
    (
        '<div class="card"><h2>作业情况</h2><div class="list" style="margin-top:12px">',
        '<div class="card"><h2>作业情况</h2><div id="assignments" class="list" style="margin-top:12px">',
    ),
    (
        '<div class="card"><h2>薄弱内容 / 错题</h2><div class="list" style="margin-top:12px">',
        '<div class="card"><h2>薄弱内容 / 错题</h2><div id="weak" class="list" style="margin-top:12px">',
    ),
    (
        '<div class="card"><div class="timeline">',
        '<div class="card"><div id="timeline" class="timeline">',
    ),
)


FEEDBACK_REWARD_PANEL_MARKER = "changying_v1_feedback_reward_panel_v1"

FEEDBACK_STATUS_CHAIN_MARKER = "changying_v1_feedback_status_chain_v1"

_FEEDBACK_STATUS_CHAIN_HTML = (
    f"<div class='card' id='feedback-status-chain' data-marker='{FEEDBACK_STATUS_CHAIN_MARKER}'>"
    "<h2>反馈处理状态链</h2>"
    "<p>每条反馈按 待处理 → 处理中 → 待验收 → 已采纳/已解决 推进；未采用的反馈也会给出明确回执。</p>"
    "<div class='list' style='margin-top:12px'>"
    "<div><strong>待处理</strong>：反馈已提交，等待 Freeman 受理。</div>"
    "<div><strong>处理中</strong>：Freeman 正在处理，已关联执行任务。</div>"
    "<div><strong>待验收</strong>：Draft PR 已创建且 exact-head CI 通过，等待人工合并与生产验收。</div>"
    "<div><strong>已采纳 / 已解决</strong>：目标 PR 已合并、生产部署包含对应 merge SHA、生产验收通过后自动更新。</div>"
    "<div><strong>未采用</strong>：给出明确回执说明，不静默丢弃。</div>"
    "<div><strong>奖励结算</strong>：仅当状态达到已采纳/已解决时，对应反馈奖励从 pending 幂等结算为 granted。</div>"
    "</div>"
    "<p style='margin-top:12px'>禁止仅凭健康检查判定反馈已完成；必须核对 PR 合并 SHA 与生产部署 revision。</p>"
    "</div>"
)

_FEEDBACK_REWARD_PANEL_HTML = (
    f"<div class='card' id='feedback-reward-panel' data-marker='{FEEDBACK_REWARD_PANEL_MARKER}'>"
    "<h2>反馈记录 · 采纳状态回执 · 奖励汇总</h2>"
    "<p>这里集中展示你提交的产品反馈、每条反馈的采纳状态回执，以及已发放的奖励汇总。</p>"
    "<div class='list' style='margin-top:12px'>"
    "<div><strong>反馈记录</strong>：按时间倒序列出你提交的每条反馈（含附件与提交时间）。</div>"
    "<div><strong>采纳状态回执</strong>：每条反馈显示 待处理 / 已采纳 / 已解决 状态与回执说明。</div>"
    "<div><strong>奖励汇总</strong>：汇总已确认发放的奖励条目与合计。</div>"
    "</div>"
    "<p style='margin-top:12px'><a href='/v1/workspace?mode=institution'>前往产品助手 · 提反馈</a> 提交新反馈后，可回到本页查看回执与奖励。</p>"
    "</div>"
)

STUDENT_DETAIL_MOBILE_CSS_MARKER = "changying_v1_student_detail_mobile_css_v2"

_MOBILE_LAYOUT_CSS = (
    f"<style id='{STUDENT_DETAIL_MOBILE_CSS_MARKER}'>"
    "@media (max-width:640px){"
    "html,body{overflow-x:hidden;overflow-y:auto;-webkit-overflow-scrolling:touch;"
    "overscroll-behavior-y:auto;height:auto;max-height:none}"
    "#suggestions,#assignments,#weak,#timeline{min-width:0;max-width:100%;"
    "overflow-x:auto;overflow-y:visible;max-height:none;height:auto;"
    "-webkit-overflow-scrolling:touch;overscroll-behavior:contain}"
    "#suggestions>*,#assignments>*,#weak>*,#timeline>*{min-width:0;overflow-wrap:anywhere}"
    ".card{overflow:visible;max-height:none}"
    "body{padding-bottom:calc(72px + env(safe-area-inset-bottom,0px))}"
    "}"
    "</style>"
)


def patch_v1_student_detail_visibility(html: str) -> str:
    """Remove caps and keep the full record readable on narrow phone screens."""

    if V1_STUDENT_DETAIL_VISIBILITY_MARKER in html:
        return html

    for old, new in (*_DETAIL_CAPS, *_DETAIL_CLARITY_REPLACEMENTS, *_DETAIL_MOBILE_TARGETS):
        if old not in html:
            raise RuntimeError(f"V1 student detail visibility patch: marker not found: {old}")
        html = html.replace(old, new, 1)

    html = html.replace(
        "</body>",
        f"{_MOBILE_LAYOUT_CSS}<!-- {V1_STUDENT_DETAIL_VISIBILITY_MARKER} --></body>",
        1,
    )

    if FEEDBACK_STATUS_CHAIN_MARKER not in html:
        html = html.replace(
            "</body>",
            f"{_FEEDBACK_STATUS_CHAIN_HTML}{_FEEDBACK_REWARD_PANEL_HTML}</body>",
            1,
        )

    return html


def install_v1_student_detail_visibility_patch() -> None:
    """Install complete student-detail rendering once before V1 routes bind."""

    if getattr(v1_module, "_student_detail_visibility_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_student_detail_visibility(original())

    v1_module.v1_html = patched_v1_html
    v1_module._student_detail_visibility_patch_installed = True


__all__ = [
    "STUDENT_DETAIL_MOBILE_CSS_MARKER",
    "V1_STUDENT_DETAIL_VISIBILITY_MARKER",
    "install_v1_student_detail_visibility_patch",
    "patch_v1_student_detail_visibility",
]
