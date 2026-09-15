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
    assert "教学工作台验收清单" in text


def test_acceptance_doc_references_existing_contracts():
    text = _doc_text()
    for token in (
        "changying/web/product_shell.py",
        "changying/compat/legacy.py",
        "tests/test_product_shell.py",
        "tests/test_product_visibility.py",
        "changying_product_shell_v1_3",
        "PRODUCT_SHELL_MARKER",
        "NO_CACHE_HEADERS",
        "X-Changying-Product-UI",
    ):
        assert token in text, f"missing contract reference: {token}"


def test_acceptance_doc_covers_required_routes_and_entries():
    text = _doc_text()
    for route in ("/", "/classic", "/workbench", "/new", "/health", "/manifest.webmanifest"):
        assert route in text, f"missing route: {route}"
    for entry in ("v717Token", "v717Remember", "v6Token", "/session", "/admin/overview", "/teacher/classes"):
        assert entry in text, f"missing entry: {entry}"


def test_acceptance_doc_preserves_production_constraints():
    text = _doc_text()
    assert "uvicorn app:app --host 0.0.0.0 --port $PORT" in text
    assert "PYTHONPATH=. pytest -q" in text
    assert "生产 PostgreSQL" in text
    assert "未合并 `main`" in text


def test_acceptance_doc_does_not_claim_production_changes():
    text = _doc_text()
    lowered = text.lower()
    for forbidden in ("修改生产代码", "部署生产", "合并 main"):
        assert forbidden not in lowered, f"doc must not claim: {forbidden}"
