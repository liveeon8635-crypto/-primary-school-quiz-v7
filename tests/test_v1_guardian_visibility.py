from changying.web.v1 import v1_html
from changying.web.v1_guardian_visibility import (
    V1_GUARDIAN_VISIBILITY_MARKER,
    patch_v1_guardian_visibility,
)


def rendered_html() -> str:
    return patch_v1_guardian_visibility(v1_html())


def guardian_patch_fragment() -> str:
    html = rendered_html()
    marker = f'<style id="{V1_GUARDIAN_VISIBILITY_MARKER}-style">'
    return html[html.index(marker) : html.index("</body>", html.index(marker))]


def test_guardian_visibility_is_scoped_to_student_detail_and_existing_read_api():
    html = rendered_html()

    assert V1_GUARDIAN_VISIBILITY_MARKER in html
    assert "location.pathname!='/v1/student'" in html
    assert "'/teacher/students/'+id+'/growth-profile'" in html
    assert "profile?.student?.parents||profile?.parents||[]" in html
    assert "家庭关联" in html
    assert "不代表新增授权" in html


def test_guardian_visibility_exposes_relationship_metadata_not_credentials():
    fragment = guardian_patch_fragment()

    assert "guardian_account_id" in fragment
    assert "主要联系人" in fragment
    assert "password" not in fragment
    assert "access_token" not in fragment
    assert "refresh_token" not in fragment
    assert "permissions" not in fragment


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


def test_guardian_visibility_uses_shared_session_storage_contract():
    fragment = guardian_patch_fragment()

    assert "v717Remember" in fragment
    assert "sessionStorage.getItem('v717Token')" in fragment
    assert "localStorage.getItem('v717Token')" in fragment


def test_guardian_visibility_renders_parent_history_without_inventing_times():
    fragment = guardian_patch_fragment()

    assert "profile?.parentHistory||[]" in fragment
    assert "家长关联历史" in fragment
    assert "起始时间未知" in fragment
    assert "结束时间未知" in fragment
    assert "当前关联" in fragment
    assert "已换绑" in fragment
