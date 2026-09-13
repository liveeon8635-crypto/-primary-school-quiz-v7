"""Stable production entrypoint for the Render service.

The active production implementation currently lives in ``app_v924.py``.
When a newer version is promoted, update only the import below; Render can
continue using the stable ``app:app`` start target.
"""

from app_v924 import app

__all__ = ["app"]
