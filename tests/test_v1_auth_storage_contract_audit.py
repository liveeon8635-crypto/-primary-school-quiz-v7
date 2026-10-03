from pathlib import Path


WEB_DIR = Path(__file__).resolve().parents[1] / "changying" / "web"


def test_v1_browser_token_readers_keep_remember_aware_storage_contract():
    """Prevent a return of the repeated localStorage-first V1/Classic login bug."""
    audited = []
    for path in sorted(WEB_DIR.glob("v1*.py")):
        text = path.read_text(encoding="utf-8")
        if "v717Token" not in text or "localStorage.getItem" not in text:
            continue
        audited.append(path.name)
        assert "v717Remember" in text, f"{path.name} reads V1 auth storage without remember mode"
        assert "sessionStorage.getItem" in text, f"{path.name} has no sessionStorage auth fallback"

    assert audited, "expected at least one V1 browser auth reader to be audited"


def test_classic_unified_top_keeps_both_current_and_legacy_fallbacks():
    text = (WEB_DIR / "v1_classic_unified_top.py").read_text(encoding="utf-8")
    for marker in (
        "v717Remember",
        "sessionStorage.getItem('v717Token')",
        "localStorage.getItem('v717Token')",
        "sessionStorage.getItem('v6Token')",
        "localStorage.getItem('v6Token')",
    ):
        assert marker in text


def test_explicit_v1_logout_clears_onboarding_session_marker():
    from pathlib import Path
    source = Path("changying/web/v1.py").read_text(encoding="utf-8")
    assert "sessionStorage.removeItem('cyV1RoleTutorialShownThisLoginV7')" in source
