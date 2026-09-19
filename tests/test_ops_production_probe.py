from __future__ import annotations

import urllib.request

import pytest


@pytest.mark.parametrize("path", ["/health", "/v1"])
def test_production_endpoint_is_reachable(path: str) -> None:
    url = "https://primary-school-quiz-v7.onrender.com" + path
    with urllib.request.urlopen(url, timeout=12) as response:
        body = response.read(256)
        assert response.status == 200, (url, response.status, body)
