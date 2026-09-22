import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from changying.web.pwa import (
    ICON_180_PNG,
    ICON_192_PNG,
    ICON_512_PNG,
    ICON_SVG,
    build_manifest,
    install_favicon_route,
)


def _png_dimensions(payload: bytes) -> tuple[int, int]:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    return (
        int.from_bytes(payload[16:20], "big"),
        int.from_bytes(payload[20:24], "big"),
    )


def test_build_manifest_uses_asset_version():
    payload = json.loads(build_manifest("test-version"))
    assert payload["name"] == "长缨辅学"
    assert payload["start_url"] == "/?source=pwa"
    assert payload["icons"][0]["src"].endswith("?v=test-version")
    assert payload["icons"][1]["src"].endswith("?v=test-version")


def test_branded_pwa_assets_have_declared_dimensions():
    assert _png_dimensions(ICON_180_PNG) == (180, 180)
    assert _png_dimensions(ICON_192_PNG) == (192, 192)
    assert _png_dimensions(ICON_512_PNG) == (512, 512)
    assert "<svg" in ICON_SVG
    assert 'viewBox="0 0 512 512"' in ICON_SVG


def test_favicon_route_returns_png_and_is_idempotent():
    app = FastAPI()
    install_favicon_route(app)
    install_favicon_route(app)
    client = TestClient(app)

    response = client.get("/favicon.ico")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert _png_dimensions(response.content) == (180, 180)
    matching = [
        child
        for route in app.routes
        for child in getattr(getattr(route, "original_router", route), "routes", [route])
        if getattr(child, "path", None) == "/favicon.ico"
    ]
    assert len(matching) == 1


def test_production_pwa_asset_routes_do_not_raise_name_error():
    from changying.production import app as production_app

    client = TestClient(production_app)
    cases = (
        ("/icon.svg?v=acceptance", "image/svg+xml", None),
        ("/icon-180.png?v=acceptance", "image/png", (180, 180)),
        ("/icon-192.png?v=acceptance", "image/png", (192, 192)),
        ("/icon-512.png?v=acceptance", "image/png", (512, 512)),
        ("/favicon.ico", "image/png", (180, 180)),
    )
    for path, media_type, dimensions in cases:
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
        assert response.headers["content-type"].startswith(media_type)
        if dimensions is not None:
            assert _png_dimensions(response.content) == dimensions
