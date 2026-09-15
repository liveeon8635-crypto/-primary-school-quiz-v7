from changying.web.v1 import v1_html
from changying.web.v1_data_quality import patch_v1_html


def test_v1_student_position_uses_neutral_teaching_affiliation_language():
    html = patch_v1_html(v1_html())
    assert "当前教学归属：" in html
    assert "当前教学归属待完善" in html
    assert "当前班级：${className}" not in html


def test_teacher_people_are_aggregated_by_stable_student_id_across_classes():
    html = patch_v1_html(v1_html())
    assert "const byId=new Map()" in html
    assert "teachingAffiliations:[]" in html
    assert "!p.teachingAffiliations.includes(c.name)" in html
    assert "return [...byId.values()]" in html


def test_teacher_people_load_class_memberships_in_parallel_for_mobile_speed():
    html = patch_v1_html(v1_html())
    assert "const classRows=await Promise.all" in html
    assert "classes.slice(0,30).map(async c=>" in html
    assert "students:await api('/teacher/classes/'+c.id+'/students')" in html
    assert "for(const item of classRows)" in html


def test_same_name_different_ids_are_audited_without_auto_merge():
    html = patch_v1_html(v1_html())
    assert "duplicateNameGroups" in html
    assert "同名多档案，暂不自动合并" in html
    assert "档案 #${esc(p.id)}" in html
    assert "系统不会删除或合并真实记录" in html
    assert "duplicateAuditHtml(people)" in html


def test_archived_duplicate_accounts_are_not_shown_as_active_students():
    html = patch_v1_html(v1_html())
    assert "x.role==='student'&&x.active!==false" in html
    assert "if(x.active===false)continue" in html
    assert "(await api('/parent/children')).filter(x=>x.active!==false)" in html
