from changying.security.login_rate import BoundedLoginRateLimiter, LoginRateLimitExceeded

# ``max_keys`` is floored at 32 on purpose: a tiny cache would let a guesser evict
# competing keys trivially. The tests use that floor as their capacity.
CAPACITY = 32


def test_full_tracker_evicts_an_unlocked_key_instead_of_locking_out_new_clients():
    limiter = BoundedLoginRateLimiter(window_seconds=600, max_attempts=2, max_keys=CAPACITY)
    for index in range(CAPACITY):
        limiter.failure(f"client-{index}")
    assert limiter.size() == CAPACITY

    # A brand-new client is still admitted: the oldest one-failure key is dropped.
    limiter.check("fresh")
    limiter.failure("fresh")

    assert limiter.count("client-0") == 0
    assert limiter.count("fresh") == 1
    assert limiter.size() <= CAPACITY


def test_tracker_only_refuses_when_every_tracked_key_is_locked_out():
    limiter = BoundedLoginRateLimiter(window_seconds=600, max_attempts=2, max_keys=CAPACITY)
    for index in range(CAPACITY):
        key = f"locked-{index}"
        limiter.failure(key)
        limiter.failure(key)

    try:
        limiter.check("fresh")
    except LoginRateLimitExceeded:
        pass
    else:  # pragma: no cover - explicit failure message
        raise AssertionError("a saturated tracker of locked keys must refuse new clients")


def test_clearing_recent_failures_does_not_clear_the_client_budget():
    recent = BoundedLoginRateLimiter(window_seconds=600, max_attempts=3)
    budget = BoundedLoginRateLimiter(window_seconds=600, max_attempts=3)

    for _ in range(3):
        budget.failure("1.2.3.4")
        recent.failure("1.2.3.4")

    recent.clear("1.2.3.4")          # what a successful sign-in does

    assert recent.count("1.2.3.4") == 0
    assert budget.count("1.2.3.4") == 3
    try:
        budget.check("1.2.3.4")
    except LoginRateLimitExceeded:
        pass
    else:  # pragma: no cover - explicit failure message
        raise AssertionError("the never-cleared client budget must still hold the attempts")
