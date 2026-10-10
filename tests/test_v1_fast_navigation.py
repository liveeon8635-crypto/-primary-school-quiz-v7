from changying.web.v1 import v1_html
from changying.web.v1_classic_gzip_embed import _ALLOWED_TOOL_PAGES


def test_v1_opens_classic_directly_without_307_hop():
    html = v1_html()
    assert "const classicTarget=" in html
    assert "/classic?legacy=1&unified=1&from=v1&page=" in html
    assert "location.href=classicTarget(path)" in html
    assert "classes" in _ALLOWED_TOOL_PAGES and "__hub__" not in html.split("CLASSIC_PAGES=new Set(")[1].split(")")[0]


def test_v1_shows_immediate_opening_feedback_before_handoff():
    html = v1_html()
    body = html.split("const openClassic=async path=>")[1].split("};")[0]
    assert body.index("showOpening()") < body.index("stageClassicHandoff()")
    assert "正在打开…" in html
    assert "e.persisted" in html
