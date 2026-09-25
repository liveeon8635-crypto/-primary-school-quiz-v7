import inspect

import app_v924 as legacy


def test_legal_pages_publish_configured_operator_contact_and_effective_date(monkeypatch):
    monkeypatch.setattr(legacy, "LEGAL_OPERATOR_NAME", "测试运营主体")
    monkeypatch.setattr(legacy, "LEGAL_PRIVACY_CONTACT", "privacy@example.test")
    monkeypatch.setattr(legacy, "LEGAL_EFFECTIVE_DATE", "2026-09-26")

    body = legacy.legal_page("隐私政策", "<p>测试正文</p>").body.decode("utf-8")
    assert "测试运营主体" in body
    assert "privacy@example.test" in body
    assert "2026-09-26" in body
    assert "测试正文" in body


def test_legal_metadata_is_html_escaped(monkeypatch):
    monkeypatch.setattr(legacy, "LEGAL_OPERATOR_NAME", "<script>bad</script>")
    monkeypatch.setattr(legacy, "LEGAL_PRIVACY_CONTACT", "<b>contact</b>")
    monkeypatch.setattr(legacy, "LEGAL_EFFECTIVE_DATE", "2026-09-26")

    body = legacy.legal_page("隐私政策", "<p>正文</p>").body.decode("utf-8")
    assert "<script>bad</script>" not in body
    assert "&lt;script&gt;bad&lt;/script&gt;" in body
    assert "<b>contact</b>" not in body
    assert "&lt;b&gt;contact&lt;/b&gt;" in body


def test_release_readiness_requires_public_legal_identity():
    production = inspect.getsource(legacy.production_readiness_payload)
    release = inspect.getsource(legacy.admin_release_readiness)
    stability = inspect.getsource(legacy.admin_stability_check)

    for source in (production, release):
        assert "LEGAL_OPERATOR_NAME" in source
        assert "LEGAL_PRIVACY_CONTACT" in source
        assert "LEGAL_EFFECTIVE_DATE" in source

    assert "公开推广法律标识尚未完整配置" in stability


def test_legal_contact_can_fall_back_to_commercial_contact():
    source = inspect.getsource(legacy)
    assert 'LEGAL_PRIVACY_CONTACT=(os.getenv("LEGAL_PRIVACY_CONTACT") or COMMERCIAL_CONTACT).strip()' in source
