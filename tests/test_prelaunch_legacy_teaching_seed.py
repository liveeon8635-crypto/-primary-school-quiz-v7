import inspect

import app_v924 as legacy
from changying.web.v1_unified_tools import unified_tool_html


def test_production_startup_does_not_implicitly_provision_legacy_grade5_template():
    source = inspect.getsource(legacy.startup)

    assert 'ENABLE_LEGACY_TEACHING_SEED' in source
    assert 'raw_url.startswith("sqlite")' in source
    assert 'v740_seed_teaching(db,create_missing=allow_legacy_teaching_seed)' in source


def test_v740_seed_can_preserve_existing_template_without_creating_new_one():
    source = inspect.getsource(legacy.v740_seed_teaching)

    assert "create_missing=True" in source
    assert "if not create_missing:" in source
    assert "continue" in source
    assert "2026年秋五年级上册语数定制教学" in source


def test_unified_tools_name_the_legacy_teaching_scope_truthfully():
    html = unified_tool_html()

    assert "五年级定制教学" in html
    assert "['teaching','定制教学']" not in html
