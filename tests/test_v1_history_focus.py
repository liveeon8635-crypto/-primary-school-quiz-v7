from fastapi.testclient import TestClient

from app import app
from changying.web.v1_history_focus import V1_HISTORY_FOCUS_MARKER


def test_history_page_is_task_oriented_and_drops_conceptual_read_only_shell():
    html = TestClient(app).get('/v1/history').text

    assert V1_HISTORY_FOCUS_MARKER in html
    assert '按学生找往期记录' in html
    assert '为什么保留往期记录' in html
    assert '<span class="tag">往期记录</span>' in html
    assert '不需要另外建立“历史档案”' in html
    assert '查询层级' not in html
    assert '2025—2026（演示）' not in html
    assert '<span class="tag">只读查询</span>' not in html
    assert '<span class="tag">历史档案</span>' not in html


def test_history_shell_renders_before_roster_network_wait():
    html = TestClient(app).get('/v1/history').text
    start = html.index('async function historyPage()')
    end = html.index('function transitionPage()', start)
    segment = html[start:end]

    assert segment.index("screen.innerHTML=shell(content,'history')") < segment.index('people=await loadPeople()')
    assert 'historySearch' in segment
    assert 'data-student' in segment


def test_history_no_longer_eagerly_loads_every_student_profile():
    html = TestClient(app).get('/v1/history').text
    start = html.index('async function enhanceHistory()')
    end = html.index('function transitionName', start)
    segment = html[start:end]

    assert 'async function enhanceHistory(){return}' in segment
    assert '/teacher/v1-profiles' not in segment
    assert '/growth-profile' not in segment
