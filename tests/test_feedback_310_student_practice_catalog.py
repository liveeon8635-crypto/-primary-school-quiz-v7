"""Regression test for feedback #310.

晚托布置作业时，部分学生（如“淦云凡”“翁舒言”）暂无可用教材，也没有对应的
“知识模块练习”明细。ensure_student_practice_catalog 必须在年级/科目下
回退到标准教材并补齐知识模块明细，且模块名去重。
"""

from __future__ import annotations

from changying.web import v1_student_practice as mod


def test_catalog_falls_back_to_standard_textbook_and_modules(monkeypatch):
    calls: list[tuple[int, str]] = []

    def fake_textbooks(grade, subject):
        # 学生自身年级/科目没有教材，只有标准年级 5 有。
        if int(grade) == 5 and subject == "数学":
            return ["人教版"]
        return []

    def fake_ensure(grade, subject):
        calls.append((int(grade), subject))

    def fake_catalog(grade, subject, textbook):
        if int(grade) == 5 and subject == "数学" and textbook == "人教版":
            return [
                {"knowledge": "小数乘法", "unit": "第一单元", "count": 3},
                {"knowledge": "小数乘法", "unit": "第一单元", "count": 3},
                {"knowledge": "位置", "unit": "第二单元", "count": 2},
            ]
        return []

    monkeypatch.setattr(mod, "built_in_textbooks", fake_textbooks)
    monkeypatch.setattr(mod, "ensure_built_in_questions", fake_ensure)
    monkeypatch.setattr(mod, "potential_question_catalog", fake_catalog)

    textbooks, modules = mod.ensure_student_practice_catalog(3, "数学")

    assert textbooks, "应回退到标准教材，而不是空白"
    assert modules, "应补齐知识模块练习明细，而不是空白"
    names = [m["knowledge"] for m in modules]
    assert len(names) == len(set(names)), "知识模块名应去重"
    assert "用数对确定位置" in names, "旧版模块名应对齐到最新人教版模块名"
    assert calls, "应主动补入标准题"
