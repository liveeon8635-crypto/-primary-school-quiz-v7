import json
from types import SimpleNamespace

from changying.services.builtin_question_bank import (
    built_in_question_specs,
    potential_question_catalog,
)


def _q(qid, *, unit, knowledge, text, options=None, textbook=""):
    return SimpleNamespace(
        id=qid,
        unit=unit,
        knowledge=knowledge,
        text=text,
        textbook=textbook,
        options_json=json.dumps(options or ["A", "B", "C", "D"], ensure_ascii=False),
        correct_index=0,
    )


def test_options_preview_combines_existing_and_not_yet_materialized_inventory():
    existing = [
        _q(1, unit="自建单元", knowledge="教师自建模块", text="教师自建题"),
    ]
    modules, total = potential_question_catalog(
        existing,
        grade=5,
        subject="数学",
    )
    counts = {row["knowledge"]: row["count"] for row in modules}

    assert total >= 180
    assert counts["教师自建模块"] == 1
    assert counts["小数乘小数"] >= 10
    assert counts["解方程"] >= 10
    assert counts["植树问题"] >= 10


def test_practice_ui_uses_real_inventory_limits_and_clears_old_result():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert 'max="50" value="20"' in html
    assert "当前年级科目可用约 " in html
    assert "countEl.max=String(max)" in html
    assert "const clearResult=()=>{resultBox.innerHTML=''}" in html
    assert "moduleEl.onchange=syncCount" in html


def test_chinese_options_preview_exposes_real_module_inventory():
    modules, total = potential_question_catalog(
        [],
        grade=5,
        subject="语文",
        textbook="统编版（人民教育出版社）",
    )
    counts = {row["knowledge"]: row["count"] for row in modules}

    assert total == 129
    assert counts["字音辨析"] >= 8
    assert counts["病句辨析"] >= 8
    assert counts["提取关键信息"] >= 8
    assert counts["资料整合"] >= 8



def test_chinese_same_stem_questions_are_distinguished_by_options():
    specs = built_in_question_specs(
        5,
        "语文",
        "统编版（人民教育出版社）",
    )
    glyphs = [x for x in specs if x["knowledge"] == "字形辨析"]
    baseline_glyphs = [x for x in glyphs if not x.get("question_type")]
    assert len(baseline_glyphs) == 8
    assert len({x["text"] for x in baseline_glyphs}) == 1
    assert len({tuple(x["options"]) for x in baseline_glyphs}) == 8

    first = baseline_glyphs[0]
    existing = [
        _q(
            1,
            unit=first["unit"],
            knowledge=first["knowledge"],
            text=first["text"],
            options=first["options"],
            textbook=first["textbook"],
        )
    ]
    modules, total = potential_question_catalog(
        existing,
        grade=5,
        subject="语文",
        textbook="统编版（人民教育出版社）",
    )
    counts = {row["knowledge"]: row["count"] for row in modules}

    # The one materialized item replaces exactly one source family. All eight
    # same-stem baseline questions with different options remain distinct; the
    # genuine 津津有味 fill adds one more unique 字形 family.
    assert total == 129
    assert counts["字形辨析"] == 9
