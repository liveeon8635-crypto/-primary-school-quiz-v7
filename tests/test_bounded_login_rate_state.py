from changying.security.login_rate import BoundedLoginRateLimiter, LoginRateLimitExceeded


def test_bounded_login_rate_limiter_caps_unique_clients_and_prunes_stale_state():
    now = [1000.0]
    limiter = BoundedLoginRateLimiter(
        window_seconds=60,
        max_attempts=3,
        max_keys=32,
        clock=lambda: now[0],
    )

    for index in range(32):
        key = f"client-{index}"
        limiter.check(key)
        limiter.failure(key)
    assert limiter.size() == 32

    try:
        limiter.check("client-overflow")
    except LoginRateLimitExceeded:
        pass
    else:
        raise AssertionError("new client must fail closed at tracker capacity")

    now[0] += 61
    limiter.check("client-overflow")
    limiter.failure("client-overflow")
    assert limiter.size() == 1


def test_bounded_login_rate_limiter_preserves_attempt_limit_and_success_clear():
    now = [2000.0]
    limiter = BoundedLoginRateLimiter(
        window_seconds=900,
        max_attempts=3,
        max_keys=64,
        clock=lambda: now[0],
    )

    for _ in range(3):
        limiter.check("same-client")
        limiter.failure("same-client")

    try:
        limiter.check("same-client")
    except LoginRateLimitExceeded:
        pass
    else:
        raise AssertionError("client should be limited after max failures")

    limiter.clear("same-client")
    limiter.check("same-client")
    assert limiter.size() == 0


def test_production_compat_installs_bounded_login_tracker():
    import app_v924 as legacy
    from app import app  # noqa: F401

    limiter = getattr(legacy, "_bounded_login_rate_limiter", None)
    assert limiter is not None
    assert limiter.max_keys == 2048
    assert legacy.login_rate_check.__module__ == "changying.compat.legacy"
