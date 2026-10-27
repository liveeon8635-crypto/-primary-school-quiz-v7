from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("offline_page_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_offline_page_is_served_instead_of_raising_name_error(tmp_path):
    """The /offline route once referenced an undefined OFFLINE_HTML and returned 500."""
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
with TestClient(app) as client:
    r = client.get("/offline")
    assert r.status_code == 200, r.status_code
    assert "离线模式" in r.text
print('OK')
''')
