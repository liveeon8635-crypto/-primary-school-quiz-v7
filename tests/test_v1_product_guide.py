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
    assert 'id="walkthroughButton"' in html
    assert '>完整演示</button>' in html
    assert "location.href='/v1/guide'" in html
    assert "location.pathname==='/v1/guide'" in html
    assert 'cy-v1-product-guide-page' in html


def test_first_visit_can_start_full_demo_or_be_skipped_and_reopened():
    html = rendered_guide()

    assert "const KEY='cyV1ProductGuideSeenV2'" in html
    assert "localStorage.getItem(KEY)!=='1'" in html
    assert '首次使用' in html
    assert '开始完整演示' in html
    assert '先进入系统' in html
    assert '暂时跳过' in html
    assert "localStorage.setItem(KEY,'1')" in html
    assert '以后可随时点击顶部“完整演示”或“使用指南”重新查看' in html


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


def test_full_demo_covers_eight_end_to_end_learning_and_classroom_steps():
    html = rendered_guide()

    for label in (
        '教师进入当前教学',
        '打开学生连续档案',
        '教师生成并布置练习',
        '学生完成练习并提交',
        '教师根据结果继续针对教学',
        '课堂复盘并生成讲义',
        '开展互动课堂与随堂检测',
        '长期跟踪：家长、历史与升年级',
    ):
        assert label in html

    assert '你做什么' in html
    assert '系统记录什么' in html
    assert '最终得到什么' in html
    assert "'第 '+(i+1)+' / '+demoSteps.length+' 步'" in html
    assert '从头开始' in html
    assert '继续上次演示' in html
    assert '打开对应功能' in html


def test_full_demo_uses_only_browser_local_progress_and_never_business_writes():
    html = rendered_guide()

    start = html.index('id="changying_v1_product_guide_v2-script"')
    end = html.index('</script>', start)
    segment = html[start:end]

    assert "const DEMO_KEY='cyV1ProductDemoStepV1'" in segment
    assert "localStorage.setItem(DEMO_KEY" in segment
    assert '不会创建真实学生、作业、积分、学习证据或课堂数据' in segment
    assert "method:'POST'" not in segment
    assert "method:'PUT'" not in segment
    assert "method:'DELETE'" not in segment
