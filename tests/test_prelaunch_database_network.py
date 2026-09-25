import inspect

import app_v924 as legacy


def test_launch_readiness_requires_restricted_database_network_boundary():
    source = inspect.getsource(legacy.production_readiness_payload)
    assert "PRODUCTION_DB_NETWORK_RESTRICTED_CONFIRMED" in source
    assert "0.0.0.0/0" in source
    assert '"databaseNetworkBoundary"' in source
