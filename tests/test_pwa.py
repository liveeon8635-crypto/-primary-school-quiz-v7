import json

from changying.web.pwa import build_manifest


def test_build_manifest_uses_asset_version():
    payload = json.loads(build_manifest("test-version"))
    assert payload["name"] == "长缨辅学"
    assert payload["start_url"] == "/?source=pwa"
    assert payload["icons"][0]["src"].endswith("?v=test-version")
    assert payload["icons"][1]["src"].endswith("?v=test-version")
