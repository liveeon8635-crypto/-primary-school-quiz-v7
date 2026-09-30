from changying.web.v1_product_assistant import _GUIDANCE_CARDS, patch_v1_product_assistant

def test_feedback_records_server_card_is_real_route():
    card = next(c for c in _GUIDANCE_CARDS if c["key"] == "feedback_records")
    assert card["path"] == "/v1/workspace?tab=feedback-records"

def test_assistant_client_has_feedback_records_tab_and_history_endpoint():
    html = patch_v1_product_assistant("<html><body></body></html>")
    assert 'data-pa-tab="records"' in html
    assert "FEEDBACK_RECORDS_GUIDE" in html
    assert "/v1/product-feedback/history" in html
    assert "feedback-records" in html


def test_assistant_fab_and_collapse_bindings_survive_feedback_records_ui():
    html = patch_v1_product_assistant("<html><body></body></html>")
    assert "fab.onclick=()=>panel.hidden?openPanel():closePanel()" in html
    assert "document.getElementById('cy-pa-collapse').onclick=closePanel" in html
    assert "const openPanel=()=>{if(!identityReady())return;" in html
    assert "const closePanel=()=>{panel.hidden=true;" in html
