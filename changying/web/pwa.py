"""PWA manifest helpers.

Keep web-app metadata outside the production implementation module so it can
be tested and versioned independently of the large legacy application file.
"""

from __future__ import annotations

import json


def build_manifest(asset_version: str = "924") -> str:
    payload = {
        "name": "长缨辅学",
        "short_name": "长缨辅学",
        "id": "/",
        "start_url": "/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "background_color": "#f6f7fb",
        "theme_color": "#5362e8",
        "icons": [
            {
                "src": f"/icon-192.png?v={asset_version}",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": f"/icon-512.png?v={asset_version}",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


__all__ = ["build_manifest"]
