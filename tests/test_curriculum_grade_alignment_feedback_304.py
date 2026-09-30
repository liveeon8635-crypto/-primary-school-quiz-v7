import importlib


def _load():
    return importlib.import_module("changying.domain.learning_evidence_growth_profile")


def _latest_names():
    mod = _load()
    return mod, mod.grade5_knowledge_module_names(mod.TEXTBOOK_EDITION_RENMIN_2024)


def test_elementary_equation_legacy_label_not_in_latest_grade5():
    mod, names = _latest_names()
    assert "简易方程" not in names, (
        "legacy 简易方程 label must not be returned for the latest 人教版"
    )
    assert "用字母表示数与方程" in names
    assert mod.TEXTBOOK_EDITION_RENMIN_2024 == "renmin-2024"


def test_position_legacy_label_not_in_latest_grade5():
    _, names = _latest_names()
    assert "位置" not in names, (
        "legacy 位置 label must not be returned for the latest 人教版"
    )
    assert "位置（用数对确定位置）" in names
