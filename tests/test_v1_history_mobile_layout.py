from fastapi.testclient import TestClient

from app import app


def test_history_search_and_rows_are_hardened_against_narrow_screen_overflow():
    html = TestClient(app).get('/v1/history').text

    # Search field must be constrained to the viewport.
    assert '#historySearch{width:100%;max-width:100%;box-sizing:border-box}' in html

    # Student list and rows must allow shrinking and wrap long names/affiliations.
    assert '#historyStudents{min-width:0}' in html
    assert '#historyStudents .row{min-width:0;flex-wrap:wrap;gap:6px}' in html
    assert '#historyStudents .row-main{min-width:0;flex:1 1 auto;overflow-wrap:anywhere;word-break:break-word}' in html
    assert '#historyStudents .row-action{flex:0 0 auto;white-space:nowrap}' in html


def test_history_mobile_css_is_scoped_to_history_page_only():
    html = TestClient(app).get('/v1/history').text

    # The hardening must not leak into global selectors.
    assert '<style>#historySearch' in html
    assert 'body{overflow' not in html
    assert '.row{min-width:0;flex-wrap:wrap' not in html


def test_history_page_still_renders_shell_before_roster_network_wait():
    html = TestClient(app).get('/v1/history').text
    start = html.index('async function historyPage()')
    end = html.index('function transitionPage()', start)
    segment = html[start:end]

    assert segment.index("screen.innerHTML=shell(content,'history')") < segment.index('people=await loadPeople()')
    assert 'historySearch' in segment
    assert 'data-student' in segment
