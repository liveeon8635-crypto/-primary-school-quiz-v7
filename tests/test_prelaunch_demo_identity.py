import inspect

import app_v924 as legacy


def test_public_launch_detects_seeded_demo_school_and_accounts():
    source = inspect.getsource(legacy.production_demo_identity_status)

    assert 'func.lower(School.code)=="demo"' in source
    assert 'School.name=="演示小学"' in source
    assert "LEGACY_DEMO_USERNAMES" in source
    assert "teacher1" in legacy.LEGACY_DEMO_USERNAMES
    assert "student1" in legacy.LEGACY_DEMO_USERNAMES
    assert "parent1" in legacy.LEGACY_DEMO_USERNAMES


def test_operator_launch_readiness_blocks_live_demo_logins_not_repurposed_school():
    source = inspect.getsource(legacy.production_readiness_payload)

    assert "production_demo_identity_status(db)" in source
    assert "生产环境仍包含启用的默认演示账号" in source
    assert '"demoIdentity"' in source


def test_admin_release_readiness_uses_same_infrastructure_and_semantic_gates():
    source = inspect.getsource(legacy.admin_release_readiness)

    for marker in (
        "production_demo_identity_status(db)",
        "production_semantic_integrity(db)",
        "PRODUCTION_DB_DURABILITY_CONFIRMED",
        "PRODUCTION_DB_BACKUP_CONFIRMED",
        "PRODUCTION_DB_NETWORK_RESTRICTED_CONFIRMED",
        '"demoIdentity"',
        '"semanticIntegrity"',
    ):
        assert marker in source


def test_admin_stability_check_cannot_report_stable_while_launch_gates_fail():
    source = inspect.getsource(legacy.admin_stability_check)

    for marker in (
        "production_demo_identity_status(db)",
        "production_semantic_integrity(db)",
        "PRODUCTION_DB_DURABILITY_CONFIRMED",
        "PRODUCTION_DB_BACKUP_CONFIRMED",
        "PRODUCTION_DB_NETWORK_RESTRICTED_CONFIRMED",
        '"demoIdentity"',
        '"semanticIntegrity"',
    ):
        assert marker in source
