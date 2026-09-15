import inspect

from changying.web.v1 import v1_html
from changying.web.v1_data_quality import patch_v1_html
from changying.web.v1_fast_path import V1_FAST_PATH_MARKER, _teacher_roster
from changying.web.v1_membership_visibility import patch_v1_membership_visibility


def rendered_html() -> str:
    return patch_v1_membership_visibility(patch_v1_html(v1_html()))


def test_v1_student_position_uses_neutral_teaching_affiliation_language():
    html = rendered_html()
    assert "当前教学归属：" in html
    assert "当前教学归属待完善" in html
    assert "当前班级：${className}" not in html


def test_teacher_people_are_aggregated_by_stable_student_id_across_classes():
    html = rendered_html()
    if V1_FAST_PATH_MARKER in html:
        source = inspect.getsource(_teacher_roster)
        assert "key = str(student.id)" in source
        assert '"teachingAffiliations": []' in source
        assert 'teaching_class.name not in item["teachingAffiliations"]' in source
        assert 'return {' in source and '"people": list(people.values())' in source
    else:
        assert "const byId=new Map()" in html
        assert "teachingAffiliations:[]" in html
        assert "!p.teachingAffiliations.includes(c.name)" in html
        assert "return [...byId.values()]" in html


def test_teacher_people_load_all_class_memberships_without_mobile_request_fanout():
    html = rendered_html()
    assert "classes.slice(0,30)" not in html
    if V1_FAST_PATH_MARKER in html:
        assert "/teacher/v1-roster" in html
        assert "api('/teacher/classes/'+c.id+'/students')" not in html
        source = inspect.getsource(_teacher_roster)
        assert "SchoolClass.teacher_id == user.id" in source
        assert "ClassStudent.class_id.in_(class_ids)" in source
    else:
        assert "for(let i=0;i<classes.length;i+=8)" in html
        assert "classes.slice(i,i+8).map(async c=>" in html
        assert "students:await api('/teacher/classes/'+c.id+'/students')" in html
        assert "classRows.push(...batch)" in html


def test_same_name_different_ids_are_audited_without_auto_merge():
    html = rendered_html()
    assert "duplicateNameGroups" in html
    assert "同名多档案，暂不自动合并" in html
    assert "档案 #${esc(p.id)}" in html
    assert "系统不会删除或合并真实记录" in html
    assert "duplicateAuditHtml(people)" in html


def test_archived_duplicate_accounts_are_not_shown_as_active_students():
    html = rendered_html()
    assert "x.role==='student'&&x.active!==false" in html
    assert "(await api('/parent/children')).filter(x=>x.active!==false)" in html
    if V1_FAST_PATH_MARKER in html:
        assert "if student.active is False" in inspect.getsource(_teacher_roster)
    else:
        assert "if(x.active===false)continue" in html
