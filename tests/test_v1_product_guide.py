from fastapi.testclient import TestClient

from app import app
from changying.web.v1_product_guide import GUIDE_PATH, V1_PRODUCT_GUIDE_MARKER


def rendered_guide() -> str:
    response = TestClient(app).get(GUIDE_PATH)
    assert response.status_code == 200
    return response.text


def test_v1_product_guide_is_routable_and_permanently_reachable():
    html = rendered_guide()

    assert V1_PRODUCT_GUIDE_MARKER in html
    assert 'id="guideButton"' in html
    assert '>使用指南</button>' in html
    assert "guideButton.onclick=()=>navigate('/v1/guide')" in html
    assert "if(path.includes('/guide'))productGuidePage()" in html


def test_first_visit_uses_same_product_guide_and_can_be_skipped_or_reopened():
    html = rendered_guide()

    assert "const GUIDE_KEY='cyV1ProductGuideSeenV1'" in html
    assert "localStorage.getItem(GUIDE_KEY)!=='1'" in html
    assert "history.replaceState({},'', '/v1/guide?first=1&return='" in html
    assert '首次使用' in html
    assert '暂时跳过' in html
    assert "localStorage.setItem(GUIDE_KEY,'1')" in html


def test_product_guide_covers_the_continuous_student_workflow():
    html = rendered_guide()

    for label in (
        '学生主档案',
        '教学归属',
        '课堂与学习动态',
        '家长关联',
        '升年级衔接',
        '历史查询',
    ):
        assert label in html

    assert '同一个学生 ID' in html
    assert '/v1/student' in html
    assert '/v1/workspace' in html
    assert '/v1/transition' in html
    assert '/v1/history' in html


def test_product_guide_is_browser_local_and_does_not_add_data_writes():
    html = rendered_guide()

    segment = html[html.index('function productGuidePage()'):html.index('async function render()', html.index('function productGuidePage()'))]
    assert 'localStorage.setItem(GUIDE_KEY' in segment
    assert "method:'POST'" not in segment
    assert "method:'PUT'" not in segment
    assert "method:'DELETE'" not in segment
