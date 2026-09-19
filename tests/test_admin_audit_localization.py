import inspect

import app_v924 as legacy


def test_admin_audit_uses_shared_chinese_action_dictionary():
    source = inspect.getsource(legacy.admin_audit_logs)
    assert '"actionName":AUDIT_ACTION_NAMES.get(x.action,x.action)' in source
    assert '"student.transfer":"学生调班"' not in source


def test_new_learning_evidence_actions_are_localized_in_shared_dictionary():
    assert legacy.AUDIT_ACTION_NAMES["learning.evidence.record"] == "记录学习证据"
    assert legacy.AUDIT_ACTION_NAMES["learning.evidence.retract"] == "撤回学习证据"
