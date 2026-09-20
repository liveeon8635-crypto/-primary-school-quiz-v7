from changying.services.builtin_question_bank import (
    built_in_question_specs,
    built_in_textbooks,
)


def test_grade5_math_exposes_current_pep_textbook_only():
    assert built_in_textbooks(5, "数学") == ["人教版"]


def test_current_pep_pack_has_substantial_valid_inventory():
    specs = built_in_question_specs(5, "数学", "人教版")
    assert len(specs) >= 180
    keys = set()
    for row in specs:
        assert row["grade"] == 5
        assert row["subject"] == "数学"
        assert row["semester"] == "上册"
        assert row["textbook"] == "人教版"
        assert row["unit"]
        assert row["knowledge"]
        assert row["text"]
        question_type = row.get("question_type") or "single_choice"
        if question_type in {"single_choice", "true_false"}:
            assert len(row["options"]) >= 2
            assert len(set(row["options"])) == len(row["options"])
            assert 0 <= row["correct_index"] < len(row["options"])
        else:
            assert question_type in {"fill_blank", "calculation", "short_answer"}
            assert row["options"] == []
            assert row["correct_index"] == -1
            assert row["answer_json"]["answer"]
        key = (row["unit"], row["knowledge"], row["text"])
        assert key not in keys
        keys.add(key)


def test_other_publishers_are_not_treated_as_pep_versions():
    for publisher in ("北师大版", "苏教版", "冀教版", "青岛版", "西师大版"):
        assert built_in_question_specs(5, "数学", publisher) == []
