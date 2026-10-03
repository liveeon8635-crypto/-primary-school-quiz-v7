from pathlib import Path


SOURCE = Path("changying/web/v1_product_assistant.py")


def test_feedback_menu_directly_loads_live_records():
    source = SOURCE.read_text(encoding="utf-8")
    assert 'data-feedback-ui-revision="3"' in source
    assert 'id="cy-pa-feedback-dropdown-records"' in source
    assert "async function loadFeedbackDropdownRecords()" in source
    assert "if(opening)await loadFeedbackDropdownRecords()" in source
    assert "<b>取用状态：</b>" in source
    assert "<b>奖励分：</b>" in source
    assert "<b>回执：</b>" in source


def test_feedback_dropdown_followup_targets_exact_record_and_photo_flow():
    source = SOURCE.read_text(encoding="utf-8")
    assert "data-pa-dropdown-followup" in source
    assert "追加反馈（可传照片）" in source
    assert "u.searchParams.set('tab','feedback-records')" in source
    assert "u.searchParams.set('focus',id)" in source
    assert "u.searchParams.set('followup',id)" in source
    assert 'data-pa-followup-photo="' in source
    assert 'accept="image/jpeg,image/png,image/webp"' in source


def test_feedback_dropdown_contract_exposes_records_and_attachment_support():
    from changying.web.v1_product_assistant import feedback_records_dropdown_payload

    payload = feedback_records_dropdown_payload([
        {
            "id": 320,
            "message": "追加反馈示例",
            "status": "已处理 · 待你确认",
            "receipt": "已处理，请验收",
            "rewardPoints": 1,
            "followUpCount": 2,
        }
    ])
    assert payload["recordsListedInDropdown"] is True
    assert payload["recordsEndpoint"] == "/v1/product-feedback/mine"
    assert payload["followUpImageUpload"] is True
    assert payload["recordsShowStatus"] == ("取用", "回执", "奖励分")
    assert payload["items"][0]["feedbackId"] == 320
    assert payload["items"][0]["followUpAttachmentTypes"] == (
        "image/jpeg",
        "image/png",
        "image/webp",
    )
