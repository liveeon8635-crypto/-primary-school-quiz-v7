from fastapi.testclient import TestClient

from app import app


def rendered_v1() -> str:
    return TestClient(app).get('/v1').text


def test_single_real_identity_skips_redundant_picker_but_keeps_account_switch():
    html = rendered_v1()
    assert 'changying_v1_identity_clarity_v1' in html
    assert "if(choices.length===1){identity=choices[0]" in html
    assert "identityButton.hidden=false" in html
    assert "identityButton.textContent=choices.length<=1?'切换账号':'切换身份'" in html
    assert "clearAuthStorage();token='';session=null;identity=null" in html
    assert "localStorage.removeItem(IDENTITY_KEY)" in html
    assert "localStorage.setItem(IDENTITY_KEY,identity.key)" in html


def test_multiple_identity_picker_remains_available_for_demo_or_future_multi_identity_accounts():
    html = rendered_v1()
    assert '选择本次使用身份' in html
    assert "choices.map(x=>`<button class=\"identity\"" in html
    assert "演示流程可切换机构与学校模式" in html
