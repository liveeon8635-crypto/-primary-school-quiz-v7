from changying.web.v1 import v1_html
from changying.web.v1_guardian_visibility import (
    V1_GUARDIAN_VISIBILITY_MARKER,
    patch_v1_guardian_visibility,
)


def rendered_html() -> str:
    return patch_v1_guardian_visibility(v1_html())


def test_guardian_visibility_is_scoped_to_student_detail_and_existing_read_api():
    html = rendered_html()

    assert V1_GUARDIAN_VISIBILITY_MARKER in html
    assert "location.pathname!='/v1/student'" in html
    assert "'/teacher/students/'+id+'/growth-profile'" in html
    assert "profile?.student?.parents||profile?.parents||[]" in html
    assert "家庭关联" in html
    assert "不代表新增授权" in html


def test_guardian_visibility_exposes_relationship_metadata_not_credentials():
    html = rendered_html()

    assert "guardian_account_id" in html
    assert "主要联系人" in html
    assert "password" not in html
    assert "access_token" not in html
    assert "refresh_token" not in html
    assert "permissions" not in html


def test_guardian_visibility_normalizes_and_deduplicates_legacy_rows():
    html = rendered_html()

    assert "const seen=new Set()" in html
    assert "seen.has(id)" in html
    assert "id<=0" in html
    assert "祖辈监护人" in html
    assert "其他监护人" in html


def test_guardian_visibility_patch_is_idempotent_and_adds_no_write_method():
    original = v1_html()
    once = patch_v1_guardian_visibility(original)
    twice = patch_v1_guardian_visibility(once)

    assert once == twice
    for verb in ("method:'POST'", 'method:"POST"', "method:'PUT'", "method:'PATCH'", "method:'DELETE'"):
        assert once.count(verb) == original.count(verb)
