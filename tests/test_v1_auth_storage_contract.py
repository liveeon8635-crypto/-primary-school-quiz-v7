import re
import subprocess

from changying.web.v1 import v1_html


def _v1_script() -> str:
    html = v1_html()
    match = re.search(
        r'<script id="changying_v1_20260915-script">(?P<script>.*?)</script>',
        html,
        re.S,
    )
    assert match, "V1 runtime script not found"
    return match.group("script")


def test_v1_auth_storage_matches_classic_contract() -> None:
    script = _v1_script()

    assert "USER_KEY='v717User'" in script
    assert "REMEMBER_KEY='v717Remember'" in script
    assert "const authStore=()=>authRemember()?localStorage:sessionStorage" in script
    assert "store.setItem(TOKEN_KEY" in script
    assert "store.setItem(USER_KEY" in script
    assert "other.removeItem(TOKEN_KEY)" in script
    assert "other.removeItem(USER_KEY)" in script
    assert "localStorage.setItem(REMEMBER_KEY,remember?'1':'0')" in script


def test_v1_login_persists_token_user_and_remember_together() -> None:
    script = _v1_script()

    assert "remember=data.remember==='on'" in script
    assert "remember})" in script
    assert "persistAuth(result,remember)" in script


def test_v1_session_refresh_migrates_legacy_token_into_shared_contract() -> None:
    script = _v1_script()

    assert "sessionStorage.getItem(TOKEN_KEY)" in script
    assert "localStorage.getItem(TOKEN_KEY)" in script
    assert "persistAuth({...session,token},authRemember())" in script
    assert "clearAuthStorage()" in script


def test_v1_runtime_script_is_valid_javascript() -> None:
    result = subprocess.run(
        ["node", "--check", "-"],
        input=_v1_script(),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
