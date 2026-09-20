from types import SimpleNamespace
import json

from changying.services.builtin_question_bank import built_in_question_specs
from changying.services.language_question_quality import language_question_text


def _q(*, text, subject="英语", question_type="fill_blank", answer=""):
    return SimpleNamespace(
        text=text,
        subject=subject,
        question_type=question_type,
        answer_json=json.dumps({"answer": answer}, ensure_ascii=False),
    )


def test_existing_ambiguous_english_fill_is_repaired_to_real_cloze():
    question = _q(
        text="Complete with the correct answer: Choose the correct sentence.",
        answer="She is kind.",
    )
    rendered = language_question_text(question)
    assert rendered == "Complete the sentence: She ____ kind."
    assert "She is kind" not in rendered


def test_existing_english_judgement_wording_is_repaired_without_changing_claim():
    question = _q(
        text='True or false: For "Eric studies carefully. What is Eric like", the answer is "He is thirsty.".',
        question_type="true_false",
    )
    rendered = language_question_text(question)
    assert rendered == "Is this answer correct? Eric studies carefully. What is Eric like — He is thirsty."
    assert "the answer is" not in rendered


def test_new_english_fill_variants_are_self_contained():
    rows = built_in_question_specs(5, "英语", "人教版（PEP·当前最新版）")
    fills = [row for row in rows if row.get("question_type") == "fill_blank"]
    assert len(fills) == 16
    assert all("Choose the correct sentence" not in row["text"] for row in fills)
    assert all("Choose the correct answer" not in row["text"] for row in fills)
    assert any("____" in row["text"] for row in fills)


def test_new_language_judgement_variants_use_direct_wording():
    english = built_in_question_specs(5, "英语", "人教版（PEP·当前最新版）")
    chinese = built_in_question_specs(5, "语文", "统编版（人民教育出版社）")

    english_tf = [row for row in english if row.get("question_type") == "true_false"]
    chinese_tf = [row for row in chinese if row.get("question_type") == "true_false"]

    assert english_tf and chinese_tf
    assert all(row["text"].startswith("Is this answer correct?") for row in english_tf)
    assert all(row["text"].startswith("判断下面的作答是否正确：") for row in chinese_tf)
