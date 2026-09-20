from types import SimpleNamespace
import json

from changying.services.builtin_question_bank import built_in_question_specs
from changying.services.language_question_quality import chinese_choice_repair, language_choice_repair, language_question_text


def _q(*, text, subject="英语", question_type="fill_blank", answer="", knowledge=""):
    return SimpleNamespace(
        text=text,
        subject=subject,
        question_type=question_type,
        knowledge=knowledge,
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



def test_existing_option_dependent_chinese_fill_restores_candidates():
    question = _q(
        subject="语文",
        knowledge="病句辨析",
        text="请直接填写答案：下列句子没有语病的一项是？",
        answer="同学们认真讨论并记录了观察结果。",
    )
    rendered = language_question_text(question)
    assert rendered.startswith("请从备选答案中选择，并输入完整答案：")
    assert "A. 通过这次活动，使我学会了合作。" in rendered
    assert "B. 同学们认真讨论并记录了观察结果。" in rendered
    assert "备选答案：" in rendered


def test_existing_direct_chinese_fill_stays_direct():
    question = _q(
        subject="语文",
        knowledge="词语理解",
        text="请直接填写答案：“这条小路十分僻静。”句中“僻静”的意思是？",
        answer="偏僻而安静",
    )
    assert language_question_text(question) == question.text


def test_new_option_dependent_chinese_fills_embed_candidates():
    rows = built_in_question_specs(5, "语文", "统编版（人民教育出版社）")
    fills = [row for row in rows if row.get("question_type") == "fill_blank"]
    risky = [
        row for row in fills
        if any(marker in row["text"] for marker in ("下列", "哪项", "哪一项", "一项是", "最恰当的一项", "最符合", "选择最"))
    ]
    assert risky
    assert all("备选答案：" in row["text"] for row in risky)



def test_choice_like_chinese_fill_restores_single_choice_shape():
    question = _q(
        subject="语文",
        knowledge="病句辨析",
        text="请直接填写答案：下列句子没有语病的一项是？",
        answer="经过努力，小组终于完成了实验记录。",
    )
    repaired = chinese_choice_repair(question)
    assert repaired is not None
    assert repaired["text"] == "下列句子没有语病的一项是？"
    assert repaired["options"][repaired["correct_index"]] == "经过努力，小组终于完成了实验记录。"
    assert len(repaired["options"]) == 4


def test_baseline_derived_semantic_chinese_fill_restores_choice_shape():
    question = _q(
        subject="语文",
        knowledge="词语理解",
        text="请直接填写答案：“这条小路十分僻静。”句中“僻静”的意思是？",
        answer="偏僻而安静",
    )
    repaired = chinese_choice_repair(question)
    assert repaired is not None
    assert repaired["text"] == "“这条小路十分僻静。”句中“僻静”的意思是？"
    assert repaired["options"][repaired["correct_index"]] == "偏僻而安静"


def test_genuine_chinese_free_text_fill_stays_text_input():
    question = _q(
        subject="语文",
        knowledge="关联词运用",
        text="填写关联词：_____天气很冷，_____同学们仍按计划观察。",
        answer="虽然……但是……",
    )
    assert chinese_choice_repair(question) is None


def test_baseline_derived_english_semantic_fill_restores_choice_shape():
    question = _q(
        subject="英语",
        knowledge="人物信息理解",
        text="Write the answer: Eric studies carefully and finishes every task on time. What is Eric like?",
        answer="He is hard-working.",
    )
    repaired = language_choice_repair(question)
    assert repaired is not None
    assert repaired["text"] == "Eric studies carefully and finishes every task on time. What is Eric like?"
    assert repaired["options"][repaired["correct_index"]] == "He is hard-working."


def test_baseline_derived_english_dialogue_blank_restores_choice_shape():
    question = _q(
        subject="英语",
        knowledge="人物描述句型",
        text="—What is your new friend like? —____",
        answer="He is quiet and polite.",
    )
    repaired = language_choice_repair(question)
    assert repaired is not None
    assert repaired["options"][repaired["correct_index"]] == "He is quiet and polite."


def test_objective_one_token_english_cloze_keeps_text_input_shape():
    question = _q(
        subject="英语",
        knowledge="人物描述句型",
        text="Tom and I ____ good friends.",
        answer="are",
    )
    assert language_choice_repair(question) is None
