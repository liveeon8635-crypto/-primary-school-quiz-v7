import importlib


def test_feedback_status_payload_exposes_verify_and_followup():
    mod = importlib.import_module("changying.web.v1_product_assistant")
    payload = mod._feedback_status_payload(308, status="resolved", resolution_note="done")
    assert payload["feedbackId"] == 308
    assert payload["status"] == "resolved"
    assert payload["canVerify"] is True
    assert payload["canFollowUp"] is True


def test_feedback_status_payload_defaults_pending():
    mod = importlib.import_module("changying.web.v1_product_assistant")
    payload = mod._feedback_status_payload(308)
    assert payload["status"] == "pending"
    assert payload["canVerify"] is True
