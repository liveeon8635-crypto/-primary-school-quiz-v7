from changying.web.v1 import v1_html


def rendered_html() -> str:
    return v1_html()


def test_student_detail_page_has_mobile_viewport():
    html = rendered_html()

    assert 'width=device-width' in html
    assert 'viewport-fit=cover' in html


def test_family_association_is_labeled_for_mobile_readability():
    html = rendered_html()

    # 学生详情页在手机端应明确标注家庭关联（监护人）信息层级
    assert '监护人' in html
    assert '家庭关联' in html or '监护人' in html


def test_growth_record_timeline_has_explicit_section_label():
    html = rendered_html()

    # 成长档案的历史时间线在手机端应有明确分区标题
    assert '历史时间线' in html
    assert '同一档案' in html or '同一份' in html


def test_student_detail_mobile_layout_uses_single_column():
    html = rendered_html()

    # 手机端断点下学生详情相关栅格应折叠为单列，保证可读性
    assert '@media(max-width:720px)' in html
    assert 'grid-template-columns:1fr' in html
