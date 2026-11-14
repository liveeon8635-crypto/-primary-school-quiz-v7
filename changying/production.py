"""Production application loader.

Render imports ``app:app`` and never needs to know which legacy implementation
is currently promoted. Change ``PRODUCTION_MODULE`` and ``ASSET_VERSION`` only
when a newer implementation has passed CI and is ready for production.
"""

from __future__ import annotations

import importlib

from fastapi import FastAPI

from changying.compat.legacy import apply_legacy_compatibility
from changying.ops.one_time_migrations import maybe_apply_one_time_migration
from changying.web.entry_policy import install_entry_policy
from changying.web.runtime_probe import install_runtime_health

PRODUCTION_MODULE = "app_v924"
ASSET_VERSION = "924"


def load_production_app() -> FastAPI:
    implementation = importlib.import_module(PRODUCTION_MODULE)
    apply_legacy_compatibility(implementation, asset_version=ASSET_VERSION)
    install_entry_policy(implementation.app)
    install_runtime_health(implementation.app)
    maybe_apply_one_time_migration(implementation)
    return implementation.app


app = load_production_app()

__all__ = ["ASSET_VERSION", "PRODUCTION_MODULE", "app", "load_production_app"]
