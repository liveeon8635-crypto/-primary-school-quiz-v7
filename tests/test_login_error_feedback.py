def test_classic_login_failure_is_persistent_and_actionable():
    from app import app  # noqa: F401
    import app_v924 as legacy

    html = legacy.INDEX_HTML

    assert 'id="loginError"' in html
    assert 'role="alert"' in html
    assert 'aria-live="polite"' in html
    assert '用户名或密码错误，请检查后重试' in html
    assert 'errorBox.textContent=msg' in html
    assert 'errorBox.classList.remove("hidden")' in html
    assert 'btn.disabled=false' in html
    assert 'btn.textContent=oldText' in html


def test_classic_login_clears_previous_error_before_retry():
    from app import app  # noqa: F401
    import app_v924 as legacy

    html = legacy.INDEX_HTML

    assert 'const errorBox=$("#loginError")' in html
    assert 'errorBox.textContent=""' in html
    assert 'errorBox.classList.add("hidden")' in html
