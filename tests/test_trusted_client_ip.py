from types import SimpleNamespace

from changying.security.client_ip import trusted_client_ip


def test_render_canonical_client_ip_overrides_forwarded_chain():
    headers = {
        "cf-connecting-ip": "198.51.100.44",
        "x-forwarded-for": "1.2.3.4, 203.0.113.9",
    }
    assert trusted_client_ip(headers, "10.0.0.2") == "198.51.100.44"


def test_forwarded_fallback_ignores_spoofable_leftmost_value():
    headers = {"x-forwarded-for": "1.2.3.4, 198.51.100.20, 203.0.113.9"}
    assert trusted_client_ip(headers, "10.0.0.2") == "203.0.113.9"


def test_invalid_forwarded_values_fall_back_to_peer_and_normalize_ipv4_mapped():
    assert (
        trusted_client_ip(
            {"cf-connecting-ip": "invalid", "x-forwarded-for": "bad"},
            "::ffff:192.0.2.9",
        )
        == "192.0.2.9"
    )


def test_production_login_and_commercial_auth_share_trusted_client_identity(monkeypatch):
    import app_v924 as legacy

    request = SimpleNamespace(
        headers={
            "cf-connecting-ip": "198.51.100.77",
            "x-forwarded-for": "1.2.3.4, 203.0.113.10",
        },
        client=SimpleNamespace(host="10.0.0.3"),
    )
    assert legacy._client_ip(request) == "198.51.100.77"

    monkeypatch.setattr(legacy, "COMMERCIAL_ADMIN_KEY", "k" * 32)

    class Recorder:
        def __init__(self):
            self.checked = []
            self.failed = []
            self.cleared = []

        def check(self, key):
            self.checked.append(key)

        def failure(self, key):
            self.failed.append(key)

        def clear(self, key):
            self.cleared.append(key)

    limiter = Recorder()
    monkeypatch.setattr(legacy, "_commercial_auth_limiter", limiter)
    assert legacy.commercial_operator(request, "k" * 32) is True
    assert limiter.checked == ["198.51.100.77"]
    assert limiter.cleared == ["198.51.100.77"]


def test_source_no_longer_uses_first_forwarded_for_for_auth_identity():
    import inspect
    import app_v924 as legacy

    source = inspect.getsource(legacy._client_ip)
    assert "trusted_client_ip" in source
    commercial = inspect.getsource(legacy.commercial_operator)
    assert "client=_client_ip(request)" in commercial
