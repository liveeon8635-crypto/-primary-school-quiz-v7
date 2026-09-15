from changying.web.product_shell import teacher_workbench_html


# 长缨辅学 V1 产品边界：主工作台聚焦小学教学与学生连续发展记录。
# 这些断言用于阻止已经撤销的 AI、市场化、训练、经营叙事重新进入辅学主界面。
FORBIDDEN_MAIN_SHELL_TERMS = (
    "AI 对接与市场化价值",
    "能力发展实践系统",
    "公众号获客",
    "会员服务",
)


def test_teacher_workbench_keeps_tutoring_product_boundary():
    html = teacher_workbench_html()

    assert "长缨辅学" in html
    for term in FORBIDDEN_MAIN_SHELL_TERMS:
        assert term not in html
