import importlib
import pytest


def _load():
    return importlib.import_module("changying.domain.learning_evidence_growth_profile")


def test_elementary_equation_not_in_grade5():
    mod = _load()
    text = "\n".join(
        str(getattr(mod, name))
        for name in dir(mod)
        if not name.startswith("__")
    )
    assert "简易方程" not in text or "六年级" in text, (
        "简易方程 must not be presented as a 五年级 module under the latest 人教版"
    )


def test_position_not_in_grade5():
    mod = _load()
    text = "\n".join(
        str(getattr(mod, name))
        for name in dir(mod)
        if not name.startswith("__")
    )
    assert "位置" not in text or "四年级" in text, (
        "位置 must not be presented as a 五年级 module under the latest 人教版"
    )
