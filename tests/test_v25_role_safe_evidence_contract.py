from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shared_evidence_endpoint_applies_role_visibility():
    source = (
        ROOT / "changying" / "web" / "v1_learning_evidence_access.py"
    ).read_text(encoding="utf-8")

    assert "learning_evidence_for_role" in source
    assert "learning_evidence_for_role(evidence, user.role)" in source


def test_transition_snapshot_applies_viewer_role_visibility():
    source = (
        ROOT / "changying" / "web" / "v1_transition_snapshot.py"
    ).read_text(encoding="utf-8")

    assert 'viewer_role: str = "teacher"' in source
    assert "learning_evidence_for_role(evidence, viewer_role)" in source
    assert "user.role," in source


def test_shared_visibility_never_exposes_internal_recent_keys():
    source = (
        ROOT / "changying" / "domain" / "learning_evidence_visibility.py"
    ).read_text(encoding="utf-8")

    assert '"occurredAt"' in source
    assert '"evidenceType"' in source
    assert '"knowledgeKey"' in source
    assert '"sourceId"' not in source
    assert '"sourceType"' not in source
    assert '"context"' not in source
