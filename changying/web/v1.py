"""长缨辅学 V1 页面渲染（最小实现，满足移动端布局冒烟测试）。"""

_STYLE = """
@media(max-width:720px){
  .cols-4{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
  .kpi{padding:14px}
  .page{padding:20px 14px calc(132px + env(safe-area-inset-bottom))}
}
"""


def studentPosition(p):
    """返回学生档案年级与当前教学归属的展示文本。"""
    grade = getattr(p, "grade", None) or (p.get("grade") if isinstance(p, dict) else None) or ""
    affiliation = getattr(p, "affiliation", None) or (p.get("affiliation") if isinstance(p, dict) else None) or ""
    return f"档案年级：{grade} 当前教学归属：{affiliation}"


def v1_html():
    return (
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>长缨辅学 V1</title><style>" + _STYLE + "</style></head>"
        "<body><main class=\"page\">"
        "<section class=\"cols-4\">"
        "<div class=\"kpi\">学生总数</div>"
        "<div class=\"kpi\">在读</div>"
        "<div class=\"kpi\">本周新增</div>"
        "<div class=\"kpi\">待跟进</div>"
        "</section>"
        "<section class=\"students\">"
        "<input class=\"search\" type=\"search\" placeholder=\"搜索学生\">"
        "<ul class=\"student-list\"></ul>"
        "</section>"
        "</main></body></html>"
    )
