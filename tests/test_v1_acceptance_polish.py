from fastapi.testclient import TestClient

from app import app


def rendered_v1() -> str:
    return TestClient(app).get('/v1').text


def test_internal_product_language_is_not_exposed_in_teacher_ui():
    html = rendered_v1()
    assert 'changying_v1_acceptance_polish_v1' in html
    assert '学生是独立实体' not in html
    assert '沿用同一 student_id' not in html
    assert '在 V1 内打开' not in html
    assert '直接读取现有教师工作台，不生成虚构数据' not in html
    assert '真实历史摘要' not in html
    assert '结构占位' not in html
    assert '当前为 V1 展示规则' not in html
    assert '未来每一步都引用同一个 student_id' not in html
    assert '打开学生的长期连续发展档案。' in html
    assert '查看当前学生的监护人关联与历史教学归属。' in html


def test_read_coalescer_loads_before_v1_body_scripts_and_only_targets_get_reads():
    html = rendered_v1()
    coalescer = html.index('changying_v1_acceptance_polish_v1-read-coalescer')
    base_script = html.index('changying_v1_20260915-script')
    assert coalescer < base_script
    assert "method!=='GET'" in html
    assert "'/teacher/v1-roster'" in html
    assert "'/teacher/v1-profiles'" in html
    assert "'/teacher/v1-bootstrap'" in html
    assert "'/teacher/workbench-summary'" in html
    assert r"/^\/teacher\/students\/\d+\/growth-profile$/" in html
    assert 'r.clone()' in html
    assert 'window.fetch=' in html


def test_acceptance_polish_does_not_add_write_endpoints_or_forms():
    html = rendered_v1()
    polish = html.split('changying_v1_acceptance_polish_v1-read-coalescer', 1)[1].split('</script>', 1)[0]
    assert "method:'POST'" not in polish
    assert "method:'PUT'" not in polish
    assert "method:'PATCH'" not in polish
    assert "method:'DELETE'" not in polish
