def test_v1_student_assignments_have_native_quiz_open_and_submit_flow():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()

    assert "openV1StudentAssignment" in html
    assert "bindV1StudentAssignments" in html
    assert "开始测试" in html
    assert "补交测试" in html
    assert "/papers/" in html
    assert "/student/assignments/" in html
    assert "/submit" in html
    assert "请完成全部题目后再提交" in html
    assert "成绩已经写入当前学生的连续学习记录" in html


def test_v1_quiz_flow_does_not_require_teacher_or_recreate_assignment():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()

    assert "if(session.role!=='student')return" in html
    assert "rows.find(x=>Number(x.id)===Number(aid))" in html
    assert "answers:new" not in html
    assert "auto-practice" not in html.split("async function openV1StudentAssignment", 1)[1].split("async function studentPage", 1)[0]
