"""Stable production entrypoint for the Render service.

The active production implementation currently lives in ``app_v924.py``.
When a newer version is promoted, update only the import below; Render can
continue using the stable ``app:app`` start target.
"""

import json

import app_v924 as implementation

# app_v924 exposes /manifest.webmanifest but does not define MANIFEST.
# Provide a valid PWA manifest at the stable entrypoint so the production
# endpoint cannot fail with NameError.
implementation.MANIFEST = json.dumps(
    {
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
                "src": "/icon-192.png?v=924",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": "/icon-512.png?v=924",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
    },
    ensure_ascii=False,
    separators=(",", ":"),
)

app = implementation.app

__all__ = ["app"]
