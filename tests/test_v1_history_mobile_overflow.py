from fastapi.testclient import TestClient

from app import app
from changying.web.v1_history_focus import V1_HISTORY_MOBILE_MARKER


def test_history_page_includes_scoped_mobile_overflow_guard():
    html = TestClient(app).get('/v1/history').text

    assert V1_HISTORY_MOBILE_MARKER in html
    assert '#historyStudents .row-main{flex:1 1 auto;min-width:0;overflow:hidden}' in html
    assert '#historyStudents .row-action{flex:0 0 auto}' in html
    assert '#historySearch{width:100%;max-width:100%}' in html


def test_history_student_rows_do_not_force_horizontal_scroll():
    html = TestClient(app).get('/v1/history').text

    # The row container must be allowed to shrink inside the card.
    assert 'max-width:100%;overflow:hidden' in html
    # Long affiliation text must ellipsize instead of widening the row.
    assert 'text-overflow:ellipsis;white-space:nowrap' in html
