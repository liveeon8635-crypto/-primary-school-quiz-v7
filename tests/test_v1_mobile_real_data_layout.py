from changying.web.v1 import v1_html


def test_v1_mobile_kpis_stay_compact_and_leave_nav_clearance():
    html = v1_html()
    assert "@media(max-width:720px)" in html
    assert ".cols-4{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}" in html
    assert "padding:20px 14px calc(132px + env(safe-area-inset-bottom))" in html
    assert ".kpi{padding:14px}" in html


def test_v1_student_position_labels_do_not_merge_grade_and_teaching_affiliation_meanings():
    html = v1_html()
    assert "档案年级：" in html
    assert "当前教学归属：" in html
    assert "studentPosition(p)" in html
    assert "studentPosition(s)" in html
