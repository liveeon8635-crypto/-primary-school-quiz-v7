from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "TEACHING_WORKBENCH_ACCEPTANCE.md"


def _doc_text() -> str:
    assert DOC.is_file(), "docs/TEACHING_WORKBENCH_ACCEPTANCE.md must exist"
    return DOC.read_text(encoding="utf-8")


def test_acceptance_doc_exists_and_is_utf8():
    text = _doc_text()
    assert text.strip(), "acceptance doc must not be empty"
    assert "长缨辅学" in text


def test_acceptance_doc_covers_required_endpoints():
    text = _doc_text()
    for endpoint in (
        "GET /health",
        "GET /",
        "GET /manifest.webmanifest",
        "GET /workbench",
        "GET /new",
        "GET /classic",
    ):
        assert endpoint in text, f"missing endpoint reference: {endpoint}"


def test_acceptance_doc_references_existing_contracts():
    text = _doc_text()
    assert "changying_product_shell_v1_3" in text
    assert "install_product_shell" in text
    assert "install_product_visibility_routes" in text
    assert "X-Changying-Product-UI" in text
    assert "NO_CACHE_HEADERS" in text


def test_acceptance_doc_keeps_scope_limits():
    text = _doc_text()
    assert "不得连接生产 PostgreSQL" in text
    assert "不在本清单范围" in text
    assert "高风险" in text


def test_acceptance_doc_does_not_claim_production_changes():
    text = _doc_text()
    assert "不修改任何生产代码" in text
