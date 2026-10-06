"""反馈 #348：手机端验收条被底部导航遮住，导致无法点击“验收完成 · 返回”退回反馈记录。

修复：验收条在运行时找到占据屏幕底边的固定元素（如统一底部导航），
停在它上方；助手按钮、待验收提示与面板随之上移，不再叠在一起。
（浏览器实测：412×915 手机视口下，修复前两个按钮都被底部导航遮挡、不可点击；
修复后验收条位于导航之上，两个按钮均可点击。）
"""
from pathlib import Path

SOURCE = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")


def test_review_bar_sits_above_fixed_bottom_navigation():
    assert "const bottomObstacleTop=()=>" in SOURCE
    assert "document.elementsFromPoint(window.innerWidth*x,window.innerHeight-dy)" in SOURCE
    assert "getComputedStyle(node).position==='fixed'" in SOURCE
    assert "bar.style.bottom=lift?String(lift)+'px'" in SOURCE


def test_review_bar_actions_are_full_width_touch_targets():
    for label in ("未通过 · 追加反馈", "验收完成 · 返回"):
        assert label in SOURCE
    assert SOURCE.count("flex:1 1 0;min-height:40px") == 2


def test_assistant_controls_are_lifted_above_the_review_bar():
    assert "--cy-feedback-review-lift" in SOURCE
    assert "#cy-product-assistant-fab{position:fixed;right:14px;bottom:max(calc(84px + env(safe-area-inset-bottom)),var(--cy-feedback-review-lift,0px))" in SOURCE
    assert "#cy-product-assistant-fab{right:12px;bottom:max(calc(78px + env(safe-area-inset-bottom)),var(--cy-feedback-review-lift,0px))" in SOURCE
    assert "#cy-pa-processed-notice{position:fixed;right:70px;bottom:max(calc(88px + env(safe-area-inset-bottom)),calc(var(--cy-feedback-review-lift,0px) + 4px))" in SOURCE


def test_previous_clearance_contract_kept():
    assert "--cy-feedback-review-clearance" in SOURCE
    assert "getBoundingClientRect().height" in SOURCE
    assert "requestAnimationFrame(syncReviewClearance)" in SOURCE
