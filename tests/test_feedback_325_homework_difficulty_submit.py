"""Regression coverage for feedback #325 against the real Classic assignment UI."""

from fastapi.testclient import TestClient

from app import app as production_app
from changying.web.classic_ui import patch_classic_paper_assignment_flow


def assignment_fragment():
    return (
        '<div><label>单元</label><input id="au" placeholder="留空=综合"></div>'
        'unit=$("#au").value,mode=$("#am").value,instructions=$("#ai").value.trim();'
        'const qs=(await api("/questions?"+params.toString())).filter('
        'q=>(q.options||[]).length>=2&&q.questionType!=="non_choice");'
        'if(!ids.length)throw new Error("没有符合条件的题目");'
    )


def test_difficulty_requirement_is_visible_and_saved_in_assignment_instructions():
    patched = patch_classic_paper_assignment_flow(assignment_fragment())

    assert 'id="homeworkDifficulty"' in patched
    assert '<option value="简单">简单</option>' in patched
    assert '<option value="中等" selected>中等</option>' in patched
    assert '<option value="偏难">偏难</option>' in patched
    assert '"题目难度要求："+difficulty' in patched
    assert "题库暂不按难度自动筛题" in patched
    assert patch_classic_paper_assignment_flow(patched) == patched


def test_empty_unit_question_set_offers_same_textbook_fallback_and_actionable_error():
    patched = patch_classic_paper_assignment_flow(assignment_fragment())

    assert 'broaderParams.delete("unit")' in patched
    assert '是否改用同教材其他单元的题目继续？' in patched
    assert '请调整教材/单元或先录入题目' in patched


def test_production_classic_papers_page_contains_recoverable_assignment_flow():
    response = TestClient(production_app).get(
        "/classic?legacy=1&unified=1&page=papers",
        headers={"Accept-Encoding": "identity"},
    )

    assert response.status_code == 200
    assert 'id="homeworkDifficulty"' in response.text
    assert 'broaderParams.delete("unit")' in response.text
    assert "请调整教材/单元或先录入题目" in response.text
