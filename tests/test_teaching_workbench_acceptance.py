"""教学工作台验收文档与现有测试契约的一致性检查。

本测试只校验文档存在且覆盖关键验收锚点，不引入新的生产行为。
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "TEACHING_WORKBENCH_ACCEPTANCE.md"


def test_acceptance_doc_exists():
    assert DOC.is_file(), "缺少教学工作台验收文档"


def test_acceptance_doc_covers_brand_and_entry():
    text = DOC.read_text(encoding="utf-8")
    for anchor in ("长缨辅学", "实践工作台", "V1.3", "/classic", "完整系统"):
        assert anchor in text, f"验收文档缺少品牌/入口锚点: {anchor}"


def test_acceptance_doc_covers_auth_and_data_sources():
    text = DOC.read_text(encoding="utf-8")
    for anchor in (
        "v717Token",
        "v717Remember",
        "v6Token",
        "/session",
        "/admin/overview",
        "/teacher/classes",
        "kpi-students",
        "classList",
    ):
        assert anchor in text, f"验收文档缺少认证/数据源锚点: {anchor}"


def test_acceptance_doc_covers_guidance_and_scope():
    text = DOC.read_text(encoding="utf-8")
    for anchor in (
        "今日上课路径",
        "运营体检",
        "首次使用建议",
        "STEP 01",
        "移动端快捷入口",
        "小学阶段晚托、周末课、寒暑假班",
        "年级/升学衔接",
    ):
        assert anchor in text, f"验收文档缺少引导/范围锚点: {anchor}"


def test_acceptance_doc_covers_routes_and_headers():
    text = DOC.read_text(encoding="utf-8")
    for anchor in (
        "/workbench",
        "/new",
        "X-Changying-Product-UI",
        "changying_product_shell_v1_3",
        "NO_CACHE_HEADERS",
        "/health",
        "/manifest.webmanifest",
    ):
        assert anchor in text, f"验收文档缺少路由/响应头锚点: {anchor}"


def test_acceptance_doc_references_existing_tests():
    text = DOC.read_text(encoding="utf-8")
    for test_file in (
        "tests/test_product_shell.py",
        "tests/test_product_visibility.py",
        "tests/test_smoke.py",
        "tests/test_deployment_contract.py",
    ):
        assert test_file in text, f"验收文档未引用现有测试: {test_file}"
        assert (ROOT / test_file).is_file(), f"引用的测试文件不存在: {test_file}"
