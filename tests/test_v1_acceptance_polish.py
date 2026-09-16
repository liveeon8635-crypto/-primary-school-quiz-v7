import subprocess
import sys
import textwrap

from changying.web import v1_acceptance_polish


def run_isolated(code: str) -> None:
    result = subprocess.run(
        [sys.executable, '-c', textwrap.dedent(code)],
        text=True,
        capture_output=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_internal_product_language_is_not_exposed_in_teacher_ui():
    run_isolated(
        """
        from fastapi.testclient import TestClient
        from app import app

        html = TestClient(app).get('/v1').text
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
        """
    )


def test_read_coalescer_loads_before_v1_body_scripts_and_only_targets_get_reads():
    run_isolated(
        r"""
        from fastapi.testclient import TestClient
        from app import app

        html = TestClient(app).get('/v1').text
        coalescer = html.index('changying_v1_acceptance_polish_v1-read-coalescer')
        base_script = html.index('changying_v1_20260915-script')
        assert coalescer < base_script
        assert "method!=='GET'" in html
        assert "'/teacher/v1-roster'" in html
        assert "'/teacher/v1-profiles'" in html
        assert "'/teacher/v1-bootstrap'" in html
        assert "'/teacher/workbench-summary'" in html
        assert '/^\\/teacher\\/students\\/\\d+\\/growth-profile$/' in html
        assert 'r.clone()' in html
        assert 'window.fetch=' in html
        """
    )


def test_acceptance_polish_does_not_add_write_paths():
    snippet = v1_acceptance_polish._EARLY_READ_COALESCER
    assert "method:'POST'" not in snippet
    assert "method:'PUT'" not in snippet
    assert "method:'PATCH'" not in snippet
    assert "method:'DELETE'" not in snippet
    assert "method!=='GET'" in snippet
