import inspect

import app_v924 as legacy


def test_public_launch_requires_durable_database_and_backup_confirmation():
    source = inspect.getsource(legacy.production_readiness_payload)
    assert "PRODUCTION_DB_DURABILITY_CONFIRMED" in source
    assert "PRODUCTION_DB_BACKUP_CONFIRMED" in source
    assert "PRODUCTION_DB_RESTORE_DRILL_CONFIRMED" in source
    assert "生产数据库持久性尚未确认" in source
    assert "生产数据库备份能力尚未确认" in source
    assert "PITR 隔离恢复演练尚未完成" in source


def test_database_launch_checks_are_visible_to_operator():
    source = inspect.getsource(legacy.production_readiness_payload)
    assert '"databaseDurability"' in source
    assert '"databaseBackup"' in source
    assert '"databaseRestoreDrill"' in source
    assert "已确认并完成逻辑导出" in source
    assert "待执行（不覆盖生产库）" in source


def test_backup_guide_keeps_snapshot_restore_as_authoritative_recovery_path():
    source = inspect.getsource(legacy.operator_backup_guide)
    assert "数据库快照" in source
    assert "恢复演练" in source
    assert "platform_database_snapshot" in source
