from pathlib import Path

def test_followup_photo_is_wired_from_assistant_to_feedback_proof():
    backend = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    frontend = Path("changying/web/feedback_center.js").read_text(encoding="utf-8")
    assert "product_feedback_followup_attachments" in backend
    assert "attachment_data: str" in backend
    assert "followup_attachment_table" in backend
    assert 'data-cy-fc-followup-photo="' in frontend
    assert "添加照片" in frontend
    assert "image/jpeg,image/png,image/webp" in frontend
    assert "attachment_data" in frontend
