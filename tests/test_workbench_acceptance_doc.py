from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "WORKBENCH_ACCEPTANCE.md"


def test_workbench_acceptance_doc_exists_and_is_utf8():
    assert DOC.is_file()
    text = DOC.read_text(encoding="utf-8")
    assert text.strip()


def test_workbench_acceptance_doc_references_real_contracts():
    text = DOC.read_text(encoding="utf-8")
    for needle in (
        "changying_product_shell_v1_3",
        "PRODUCT_SHELL_MARKER",
        "X-Changying-Product-UI",
        "NO_CACHE_HEADERS",
        "/workbench",
        "/new",
        "/classic",
        "/health",
        "/manifest.webmanifest",
        "uvicorn app:app --host 0.0.0.0 --port $PORT",
        "ASSET_VERSION",
        "PRODUCTION_MODULE",
    ):
        assert needle in text, f"missing reference: {needle}"


def test_workbench_acceptance_doc_links_existing_test_files():
    text = DOC.read_text(encoding="utf-8")
    for name in (
        "tests/test_product_shell.py",
        "tests/test_product_visibility.py",
        "tests/test_smoke.py",
        "tests/test_deployment_contract.py",
    ):
        assert name in text, f"missing test reference: {name}"
        assert (ROOT / name).is_file(), f"referenced test file missing: {name}"


def test_workbench_acceptance_doc_declares_non_goals():
    text = DOC.read_text(encoding="utf-8")
    assert "非目标" in text
    assert "不连接生产 PostgreSQL" in text
    assert "不合并 `main`" in text
