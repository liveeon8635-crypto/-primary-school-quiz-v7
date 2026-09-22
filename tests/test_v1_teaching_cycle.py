from types import SimpleNamespace

from changying.domain.teaching_cycle_read_model import _cycle_kind


def test_cycle_kind_maps_existing_terms_without_inference():
    assert _cycle_kind("秋季") == "term"
    assert _cycle_kind("春季") == "term"
    assert _cycle_kind("寒假") == "winter"
    assert _cycle_kind("暑期") == "summer"


def test_route_is_read_only_contract():
    source=(__import__("pathlib").Path(__file__).resolve().parents[1]/"changying/web/v1_teaching_cycle.py").read_text(encoding="utf-8")
    assert '@app.get("/v1/teaching-cycles"' in source
    assert "storageNeutral" in source
    assert "@app.post" not in source
    assert ".commit(" not in source
    assert ".add(" not in source
