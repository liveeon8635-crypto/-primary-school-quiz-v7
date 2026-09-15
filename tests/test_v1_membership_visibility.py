from changying.web.v1 import v1_html
from changying.web.v1_membership_visibility import (
    V1_MEMBERSHIP_VISIBILITY_MARKER,
    patch_v1_membership_visibility,
)


def rendered_html() -> str:
    return patch_v1_membership_visibility(v1_html())


def test_teacher_roster_no_longer_stops_after_first_30_classes():
    html = rendered_html()

    assert V1_MEMBERSHIP_VISIBILITY_MARKER in html
    assert "classes.slice(0,30)" not in html
    assert "for(let i=0;i<classes.length;i+=8)" in html
    assert "classes.slice(i,i+8).map" in html
    assert "classRows.push(...batch)" in html


def test_membership_visibility_preserves_student_continuity_rules():
    html = rendered_html()

    assert "if(x.active===false)continue" in html
    assert "const key=String(x.id)" in html
    assert "teachingAffiliations:[]" in html
    assert "if(c.name&&!p.teachingAffiliations.includes(c.name))" in html
    assert "if(c.id&&!p.classIDs.includes(c.id))" in html


def test_membership_visibility_only_changes_read_fanout():
    original = v1_html()
    patched = rendered_html()

    # The base login POST is intentionally part of V1.  This patch must not add
    # any new write verb beyond what the original shell already contained.
    for verb in ("method:'POST'", 'method:"POST"', "method:'PUT'", "method:'DELETE'"):
        assert patched.count(verb) == original.count(verb)
