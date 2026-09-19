from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "app_v924.py"


def growth_report_block() -> str:
    source = SOURCE.read_text(encoding="utf-8")
    start = source.index('@app.get("/teacher/students/{sid}/growth-report.xlsx")')
    end = source.index("\n@app.", start + 20)
    return source[start:end]


def test_growth_report_contains_standardized_learning_evidence_sheet():
    block = growth_report_block()

    assert "learning_evidence_export_payload" in block
    assert 'wb.create_sheet("学习证据")' in block
    assert "标准化学习证据" in block
    assert "证据状态" in block
    assert "已记录维度" in block
    assert "学科观测" in block
    assert "知识点观测" in block
    assert "最近证据事实" in block


def test_growth_report_uses_observation_wording_not_mastery_wording():
    block = growth_report_block()

    assert 'section(wa,r,"知识点作答观测")' in block
    assert '"观测正确率"' in block
    assert 'section(wa,r,"知识点掌握")' not in block


def test_general_growth_report_does_not_export_internal_context_or_source_ids():
    block = growth_report_block()

    assert '.get("context")' not in block
    assert '.get("sourceId")' not in block
    assert '"教师内部"' not in block


def test_growth_report_carries_non_diagnostic_export_note():
    block = growth_report_block()

    assert 'evidence_export.get("note","")' in block
    assert "learning_evidence_export_payload(data.get(\"learningEvidence\") or {})" in block
