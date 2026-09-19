import ast
import re
from pathlib import Path


SOURCE_PATH = Path(__file__).resolve().parents[1] / "app_v924.py"


def _source():
    return SOURCE_PATH.read_text(encoding="utf-8")


def _action_names():
    tree = ast.parse(_source())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "AUDIT_ACTION_NAMES":
                    return ast.literal_eval(node.value)
    raise AssertionError("AUDIT_ACTION_NAMES not found")


def test_every_current_teacher_audit_action_has_a_chinese_label():
    source = _source()
    actions = set(re.findall(r'audit\(db,u,"([^"]+)"', source))
    names = _action_names()

    missing = sorted(actions - set(names))
    assert missing == [], f"这些审计动作缺少中文名称: {missing}"

    for action in sorted(actions):
        label = names[action]
        assert label
        assert label != action
        assert re.search(r"[\u4e00-\u9fff]", label), (action, label)


def test_teacher_audit_endpoint_uses_the_single_shared_dictionary():
    source = _source()
    start = source.index('def teacher_audit_logs(')
    end = source.index('@app.post("/teacher/papers")', start)
    block = source[start:end]

    assert "names=AUDIT_ACTION_NAMES" in block
    assert '"actionName":names.get(x.action,x.action)' in block


def test_readable_summary_prefers_chinese_label_over_raw_technical_detail():
    source = _source()
    start = source.index("def audit_readable(db,row):")
    end = source.index("# ---------------- V7.4 customized teaching module", start)
    block = source[start:end]

    assert "names=AUDIT_ACTION_NAMES" in block
    assert "return names.get(action) or detail or action" in block
    assert "return detail or names.get(action,action)" not in block


def test_newer_actions_that_previously_fell_back_to_english_are_localized():
    names = _action_names()
    expected = {
        "ai.grade.assist": "生成 AI 批改建议",
        "ai.reinforcement.generate": "生成个性化巩固",
        "followup.status": "更新跟进状态",
        "class.todo.status": "更新班级待办状态",
        "points.group.members": "更新积分小组成员",
        "teaching.resource.upload": "上传教学资源",
        "wrong_question.status": "更新错题状态",
    }
    for action, label in expected.items():
        assert names[action] == label
