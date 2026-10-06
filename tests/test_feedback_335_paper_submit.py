"""反馈 #335 回归测试：组卷作业提交契约与校验。

钟老师在 /classic?legacy=1&unified=1&page=papers 反馈“组卷作业提交不了作业”。
本测试确认存在真实提交契约（端点、必填字段、legacy 页面标识）与提交前校验，
避免只有视觉按钮而没有提交路径。
"""

from changying.web.v1_product_assistant import (
    PAPER_SUBMIT_MARKER,
    PAPER_SUBMIT_PATH,
    PAPER_SUBMIT_REQUIRED_FIELDS,
    PAPER_SUBMIT_LEGACY_PAGE,
    paper_submit_contract,
    paper_submit_validation,
)


def test_paper_submit_contract_exposes_real_submit_path():
    contract = paper_submit_contract()
    assert contract["marker"] == PAPER_SUBMIT_MARKER
    assert contract["submitPath"] == PAPER_SUBMIT_PATH
    assert contract["submitPath"].startswith("/v1/")
    assert contract["requiredFields"] == list(PAPER_SUBMIT_REQUIRED_FIELDS)
    assert contract["legacyPage"] == PAPER_SUBMIT_LEGACY_PAGE
    assert contract["supportsLegacyPage"] is True


def test_paper_submit_validation_rejects_missing_fields():
    result = paper_submit_validation({})
    assert result["ok"] is False
    assert result["submitPath"] == PAPER_SUBMIT_PATH
    for field in PAPER_SUBMIT_REQUIRED_FIELDS:
        assert f"missing:{field}" in result["errors"]


def test_paper_submit_validation_accepts_complete_payload():
    payload = {
        "title": "五年级数学单元练习",
        "questions": [{"id": 1, "text": "1+1=?"}],
        "class_id": 42,
    }
    result = paper_submit_validation(payload)
    assert result["ok"] is True
    assert result["errors"] == []
    assert result["marker"] == PAPER_SUBMIT_MARKER


def test_paper_submit_validation_handles_none_payload():
    result = paper_submit_validation(None)
    assert result["ok"] is False
    assert len(result["errors"]) == len(PAPER_SUBMIT_REQUIRED_FIELDS)
