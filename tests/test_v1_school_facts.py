from changying.web.v1 import v1_html
from changying.web.v1_operational import _OPERATIONAL_SNIPPET
from changying.web.v1_school_facts import (
    V1_SCHOOL_FACTS_MARKER,
    patch_v1_school_facts,
)


def current_operational_html() -> str:
    return v1_html().replace("</body>", _OPERATIONAL_SNIPPET + "\n</body>", 1)


def test_school_mode_does_not_claim_a_data_domain_that_is_not_persisted():
    html = patch_v1_school_facts(current_operational_html())

    assert V1_SCHOOL_FACTS_MARKER in html
    assert "学校数据域内的教学入口" not in html
    assert "复用当前账号已有教学数据，不虚构独立学校数据域" in html
    assert "学校独立数据域尚未标准化落表" in html


def test_today_timetable_opens_a_fact_only_overview_until_schedule_exists():
    html = patch_v1_school_facts(current_operational_html())

    assert "async function showSchoolToday()" in html
    assert "if(f==='今日课表'){await showSchoolToday();return}" in html
    assert "当前没有标准化课表时段数据" in html
    assert "不会生成虚构的上课时间、教室或学科安排" in html
    assert "待后续真正建立学校、学年、学期、课节与时间段数据模型" in html


def test_school_facts_patch_is_idempotent_and_read_only():
    once = patch_v1_school_facts(current_operational_html())
    twice = patch_v1_school_facts(once)

    assert once == twice
    assert "fetch('/" not in once or "method:'POST'" not in once
    assert "method:'PUT'" not in once
    assert "method:'DELETE'" not in once
