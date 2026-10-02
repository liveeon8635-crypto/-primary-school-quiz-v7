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


def test_feedback_revisions_are_not_truncated_before_proof_sync():
    backend = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    # AuditLog.detail is Text. Truncating JSON after appending a follow-up can cut
    # transferToken/followUps mid-document, making /mine lose the record payload
    # and Freeman's proof import return 404.
    assert "json.dumps(detail, ensure_ascii=False)[:1800]" not in backend
    assert "json.dumps(payload, ensure_ascii=False)[:1800]" not in backend
    assert "json.dumps(persisted, ensure_ascii=False)[:1800]" not in backend
    assert 'detail["transferToken"] = proof_token' in backend
    assert 'detail["followUps"] = follow_ups' in backend


def test_feedback_handoff_has_bounded_retry_and_observable_failure():
    backend = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    assert "def _post_feedback_import(" in backend
    assert "for attempt in range(1, 4):" in backend
    assert "freeman_feedback_sync_ok" in backend
    assert "freeman_feedback_sync_failed" in backend
    assert "synced = _post_feedback_import(proof_token, int(row.id))" in backend


def test_feedback_reconciliation_is_admin_gated_and_rotates_proof_token():
    backend = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    assert '"/internal/product-feedback/{feedback_id}/reconcile"' in backend
    assert 'not in ("admin", "school_admin")' in backend
    assert 'detail["transferToken"] = proof_token' in backend
    assert 'detail["transferTokenAt"] = now.isoformat() + "Z"' in backend
    assert '_post_feedback_import(proof_token, int(row.id))' in backend
    assert '"freemanSynced": True' in backend


def test_feedback_314_is_reconciled_on_startup_without_browser_action():
    backend = Path("changying/web/v1_product_assistant.py").read_text(encoding="utf-8")
    assert 'reconcile_known_dropped_feedback_on_startup' in backend
    assert '_reconcile_feedback_handoff(db, 314)' in backend
    assert 'freeman_feedback_startup_reconcile_failed feedback_id=314' in backend
