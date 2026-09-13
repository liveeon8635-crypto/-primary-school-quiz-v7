"""Stable production entrypoint for the Render service.

The active production implementation currently lives in ``app_v924.py``.
When a newer version is promoted, update only the import below; Render can
continue using the stable ``app:app`` start target.
"""

import app_v924 as implementation

from changying.web.pwa import build_manifest

# app_v924 exposes /manifest.webmanifest but does not define MANIFEST.
# Keep that compatibility shim at the stable entrypoint while the legacy
# implementation is gradually split into maintainable modules.
implementation.MANIFEST = build_manifest(asset_version="924")

app = implementation.app

__all__ = ["app"]
