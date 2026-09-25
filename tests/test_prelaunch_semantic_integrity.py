import inspect

import app_v924 as legacy


def test_semantic_integrity_distinguishes_live_operability_from_history():
    source = inspect.getsource(legacy.production_semantic_integrity)
    assert "StudentClassHistory.left_at.is_(None)" in source
    assert "student.active" in source
    assert '"assignmentRecipientSnapshotSemantics":True' in source
    assert '"mixedPurposeClassGradeSemantics":True' in source


def test_launch_readiness_blocks_stranded_active_students():
    source = inspect.getsource(legacy.production_readiness_payload)
    assert "semantic=production_semantic_integrity(db)" in source
    assert "启用学生仍归属到已停用教师负责的班级" in source
    assert '"semanticIntegrity"' in source
