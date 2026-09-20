from changying.services.reinforcement_subject_policy import (
    augment_reinforcement_prompt,
    normalize_science_reinforcement_items,
    reinforcement_subject_from_prompt,
    scope_context_to_primary_subject,
)
from changying.web.reinforcement_quality import infer_reinforcement_figure


def test_chinese_reinforcement_prompt_adds_subject_specific_contract():
    base = '''最近测试/练习反馈：{"primary":{"grade":5,"subject":"语文","textbook":"统编版（人民教育出版社）"}}
要求：生成针对性练习。'''
    assert reinforcement_subject_from_prompt(base) == "语文"
    prompt = augment_reinforcement_prompt("reinforcement_generate", base)
    assert "当前科目是语文" in prompt
    assert "不要使用 calculation" in prompt
    assert "不要使用 calculation 或 short_answer" in prompt
    assert "开放性阅读感受" in prompt
    assert "不得自动判分" in prompt
    assert "figure 必须返回 {}" in prompt


def test_math_reinforcement_prompt_gets_only_generic_subject_isolation():
    base = '''最近测试/练习反馈：{"primary":{"grade":5,"subject":"数学","textbook":"人教版"}}'''
    assert reinforcement_subject_from_prompt(base) == "数学"
    prompt = augment_reinforcement_prompt("reinforcement_generate", base)
    assert "当前科目是数学" in prompt
    assert "必须忽略" in prompt
    assert "不要使用 calculation" not in prompt
    assert "开放性阅读感受、习作、长篇表达不得自动判分" not in prompt


def test_unrelated_ai_features_are_untouched():
    base = '''{"primary":{"subject":"语文"}}'''
    assert augment_reinforcement_prompt("grading", base) == base


def test_chinese_item_drops_accidental_math_figure():
    item = {
        "subject": "语文",
        "knowledge": "提取关键信息",
        "text": "阅读材料后选择正确答案。",
        "figure": {
            "type": "coordinate_grid",
            "points": [{"label": "A", "x": 2, "y": 3}],
        },
    }
    assert infer_reinforcement_figure(item) == {}


def test_math_item_still_preserves_valid_figure():
    item = {
        "subject": "数学",
        "knowledge": "位置",
        "text": "点A在(2,3)。",
        "figure": {
            "type": "coordinate_grid",
            "points": [{"label": "A", "x": 2, "y": 3}],
        },
    }
    figure = infer_reinforcement_figure(item)
    assert figure["type"] == "coordinate_grid"
    assert figure["points"][0]["x"] == 2


def test_context_is_scoped_to_primary_subject():
    context = {
        "primary": {"assignmentID": 9, "subject": "语文", "textbook": "人教版"},
        "assessmentCount": 3,
        "sourceAssignmentIDs": [9, 8, 7],
        "assessments": [
            {"assignmentID": 9, "subject": "语文", "score": 70},
            {"assignmentID": 8, "subject": "数学", "score": 80},
            {"assignmentID": 7, "subject": "语文", "score": 90},
        ],
        "weakKnowledge": [
            {"subject": "数学", "knowledge": "梯形的面积", "accuracy": 20},
            {"subject": "语文", "knowledge": "病句辨析", "accuracy": 50},
            {"subject": "语文", "knowledge": "提取关键信息", "accuracy": 60},
        ],
    }
    scoped = scope_context_to_primary_subject(context)
    assert scoped["assessmentCount"] == 2
    assert scoped["sourceAssignmentIDs"] == [9, 7]
    assert {x["subject"] for x in scoped["assessments"]} == {"语文"}
    assert {x["subject"] for x in scoped["weakKnowledge"]} == {"语文"}
    assert scoped["primary"]["assignmentID"] == 9


def test_non_chinese_subject_gets_cross_subject_ignore_instruction():
    base = '''最近测试/练习反馈：{"primary":{"grade":5,"subject":"数学","textbook":"人教版"}}'''
    prompt = augment_reinforcement_prompt("reinforcement_generate", base)
    assert "当前科目是数学" in prompt
    assert "必须忽略" in prompt


def test_runtime_context_policy_precedes_subject_scope_and_route_filters_wrong_subject():
    import inspect
    import app  # noqa: F401
    import app_v924 as legacy

    # Reinforcement policy wraps the subject-aware textbook selector; both must be active.
    assert legacy.student_assessment_context.__name__ == "subject_scoped_assessment_context"
    closure_names = {
        getattr(cell.cell_contents, "__name__", "")
        for cell in (legacy.student_assessment_context.__closure__ or ())
        if callable(getattr(cell, "cell_contents", None))
    }
    assert "subject_aware_context" in closure_names

    source = inspect.getsource(legacy.teacher_reinforcement_generate)
    assert "context_subject" in source
    assert 'str(x.subject or "").strip()==context_subject' in source
    assert 'forced_subject!="数学"' in source
    assert 'if forced_subject=="数学" else {}' in source



def test_english_reinforcement_prompt_locks_current_pep_and_objective_types():
    base = '''最近测试/练习反馈：{"primary":{"grade":5,"subject":"英语","textbook":"人教版（PEP·当前最新版）"}}'''
    assert reinforcement_subject_from_prompt(base) == "英语"
    prompt = augment_reinforcement_prompt("reinforcement_generate", base)
    assert "当前科目是英语" in prompt
    assert "PEP·当前最新版" in prompt
    assert "Different friends" in prompt
    assert "Nature and us" in prompt
    assert "不要使用 calculation" in prompt
    assert "figure 必须返回 {}" in prompt
    assert "不得回退到旧版单元标题" in prompt



def test_science_reinforcement_prompt_preserves_context_and_does_not_guess_publisher():
    base = '''最近测试/练习反馈：{"primary":{"grade":5,"subject":"科学","textbook":"教师明确的科学教材","unit":"观察与实验"}}'''
    assert reinforcement_subject_from_prompt(base) == "科学"
    prompt = augment_reinforcement_prompt("reinforcement_generate", base)
    assert "当前科目是科学" in prompt
    assert "不得自行猜测" in prompt
    assert "single_choice、true_false、fill_blank" in prompt
    assert "不要使用 calculation" in prompt
    assert "figure 必须返回 {}" in prompt
    assert "明火、强电、危险化学品" in prompt
    assert "人教/鄂教版" not in prompt
    assert "青岛版" not in prompt


def test_science_reinforcement_normalizer_keeps_only_objective_safe_types():
    rows = normalize_science_reinforcement_items(
        [
            {
                "question_type": "choice",
                "subject": "科学",
                "text": "观察现象后选择正确解释。",
                "figure": {"type": "coordinate_grid"},
            },
            {
                "question_type": "true_false",
                "subject": "科学",
                "text": "根据实验记录判断。",
                "figure": {"type": "geometry"},
            },
            {
                "question_type": "fill_blank",
                "subject": "科学",
                "text": "填写唯一科学术语。",
                "figure": {},
            },
            {
                "question_type": "calculation",
                "subject": "科学",
                "text": "不应进入自动科学练习。",
            },
            {
                "question_type": "short_answer",
                "subject": "科学",
                "text": "解释证据，应由教师审核。",
            },
        ]
    )
    assert [row["question_type"] for row in rows] == [
        "single_choice",
        "true_false",
        "fill_blank",
    ]
    assert all(row["figure"] == {} for row in rows)
