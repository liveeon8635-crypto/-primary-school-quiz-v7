from changying.web.v1 import v1_html
from changying.web.v1_classic_unified_top import V1_CLASSIC_UNIFIED_SNIPPET


def test_v1_capsule_is_fixed_on_desktop_and_a_bottom_bar_on_mobile():
    # The capsule used to be position:sticky and drifted away on mobile when the page scrolled.
    html = v1_html()
    assert ".cy-seg{position:fixed;left:clamp(8px,1.6vw,20px);top:113px;" in html
    assert ".cy-seg{position:sticky" not in html
    # desktop: the layout reserves the capsule's width so content never sits underneath it
    assert "padding-left:calc(84px + clamp(8px,1.6vw,20px) + 4px)" in html

    mobile = html[html.index("@media(max-width:720px)"):]
    assert ".cy-seg{top:auto;left:8px;right:8px;bottom:max(8px,env(safe-area-inset-bottom));" in mobile
    assert "grid-template-columns:repeat(var(--n),1fr);grid-template-rows:1fr" in mobile
    assert "transform:translateX(calc(var(--i)*100%))" in mobile
    # content keeps clearance above the bottom bar
    assert "padding:16px 14px calc(92px + env(safe-area-inset-bottom))" in mobile


def test_classic_pages_get_the_same_fixed_navigation():
    # Second-level (Classic) pages such as 教材教案 used to have no capsule on desktop.
    snippet = V1_CLASSIC_UNIFIED_SNIPPET
    desktop = snippet[snippet.index("@media(min-width:721px)"):]
    assert "#cy-v1-unified-bottom{box-sizing:border-box;position:fixed;display:grid;" in desktop
    assert "left:clamp(8px,1.6vw,20px);top:113px;width:84px;" in desktop
    assert "html.cy-v1-unified body{padding-left:calc(84px + clamp(8px,1.6vw,20px) + 8px)!important}" in desktop
    # not shown over the login form while the session is still being restored
    assert "html.cy-v1-login-pending #cy-v1-unified-bottom{visibility:hidden}" in desktop
    # mobile: the same capsule look as the V1 pages (track + white active pill, text only) instead of the old white card
    mobile = snippet[snippet.index("@media(max-width:720px)"):]
    assert "#cy-v1-unified-bottom{box-sizing:border-box;position:fixed;display:grid;grid-template-columns:repeat(auto-fit,minmax(0,1fr));grid-auto-flow:column;" in mobile
    assert "background:linear-gradient(180deg,#f6e4dc,#fbefe9)" in mobile
    assert "#cy-v1-unified-bottom a span{display:none}" in mobile
    assert "#cy-v1-unified-bottom a.active{background:linear-gradient(180deg,#fff,#fff4ee);color:#a8101c;" in mobile
    # on any Classic tool page a teacher is inside 全部功能, so that segment shows as active (it used to show nothing)
    assert "(role==='teacher'&&x[0]==='tools'&&!!page&&page!=='__hub__')" in snippet
