from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "TEACHING_WORKBENCH_ACCEPTANCE.md"


def _doc_text() -> str:
    assert DOC.is_file(), "docs/TEACHING_WORKBENCH_ACCEPTANCE.md must exist"
    return DOC.read_text(encoding="utf-8")


def test_acceptance_doc_exists_and_is_non_empty():
    text = _doc_text()
    assert text.strip()
    assert "教学工作台验收清单" in text


def test_acceptance_doc_references_existing_contracts():
    text = _doc_text()
    for reference in (
        "changying/web/product_shell.py",
        "changying/compat/legacy.py",
        "tests/test_product_shell.py",
        "tests/test_product_visibility.py",
        "tests/test_smoke.py",
        "tests/test_deployment_contract.py",
    ):
        assert reference in text, f"missing reference: {reference}"


def test_acceptance_doc_keeps_production_constraints():
    text = _doc_text()
    assert "uvicorn app:app --host 0.0.0.0 --port $PORT" in text
    assert "healthCheckPath: /health" in text
    assert "changying_product_shell_v1_3" in text
    assert "不得连接生产 PostgreSQL" in text


def test_acceptance_doc_covers_workbench_routes_and_headers():
    text = _doc_text()
    for token in (
        "/workbench",
        "/new",
        "/classic",
        "X-Changying-Product-UI",
        "NO_CACHE_HEADERS",
        "v717Token",
        "v717Remember",
        "v6Token",
        "/session",
        "/admin/overview",
        "/teacher/classes",
        "kpi-students",
        "classList",
    ):
        assert token in text, f"missing token: {token}"


def test_acceptance_doc_states_scope_limits():
    text = _doc_text()
    assert "不修改生产代码" in text
    assert "不合并 `main`" in text
    assert "不部署生产" in text
