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


def test_v1_contract_matches_classic_boot_storage_rules() -> None:
    from pathlib import Path

    classic = Path("app_v924.py").read_text(encoding="utf-8")
    script = _v1_script()

    classic_rules = (
        'const initialRemember=localStorage.getItem("v717Remember")==="1";',
        'token:(initialRemember?localStorage.getItem("v717Token"):sessionStorage.getItem("v717Token"))||""',
        'user:JSON.parse((initialRemember?localStorage.getItem("v717User"):sessionStorage.getItem("v717User"))||"null")',
        'store.setItem("v717Token",state.token||"");store.setItem("v717User",JSON.stringify(state.user||null));',
        'localStorage.setItem("v717Remember",state.remember?"1":"0");',
    )
    for rule in classic_rules:
        assert rule in classic

    assert "const authRemember=()=>localStorage.getItem(REMEMBER_KEY)==='1'" in script
    assert "const authStore=()=>authRemember()?localStorage:sessionStorage" in script
    assert "store.setItem(TOKEN_KEY" in script
    assert "store.setItem(USER_KEY" in script
    assert "localStorage.setItem(REMEMBER_KEY,remember?'1':'0')" in script
