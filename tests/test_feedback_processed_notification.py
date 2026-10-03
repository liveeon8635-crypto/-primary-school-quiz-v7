"""Regression test for feedback #308: teachers must receive an in-product
notification when their submitted feedback has been processed, with an entry
point to verify the fix or submit further feedback.
"""
import importlib


def _load_module():
    return importlib.import_module("changying.web.v1_product_assistant")


def test_processed_feedback_produces_notification_with_verify_and_followup(monkeypatch):
    mod = _load_module()

    fake_entries = [
        {"id": 308, "title": "这里不好懂", "status": "processed"},
        {"id": 309, "title": "未处理", "status": "pending"},
    ]
    monkeypatch.setattr(mod, "_feedback_inbox_entries", lambda user_id=None: fake_entries)

    notifications = mod._feedback_processed_notifications(user_id="teacher-1")

    assert len(notifications) == 1
    note = notifications[0]
    assert note["feedback_id"] == 308
    assert note["status"] == "processed"
    assert note["can_verify"] is True
    assert note["can_followup"] is True
    assert "action=verify" in note["verify_url"]
    assert "action=followup" in note["followup_url"]


def test_unprocessed_feedback_does_not_notify(monkeypatch):
    mod = _load_module()
    monkeypatch.setattr(
        mod,
        "_feedback_inbox_entries",
        lambda user_id=None: [{"id": 1, "status": "pending"}],
    )
    assert mod._feedback_processed_notifications(user_id="teacher-1") == []
