"""Executable database migration and reverse-order rollback CLI for P0-2 guardian consent tables.

Usage:
    python -m changying.services.guardian_consent_ddl upgrade --database-url sqlite:///...
    python -m changying.services.guardian_consent_ddl verify --database-url sqlite:///...
    python -m changying.services.guardian_consent_ddl downgrade --database-url sqlite:///... --confirm-downgrade
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from sqlalchemy import create_engine, inspect

from changying.services.guardian_consent import CONSENT_METADATA, register_guardian_consent_tables

CONSENT_TABLES: tuple[str, ...] = (
    "guardian_ai_consents",
    "guardian_consent_tokens",
    "guardian_consent_audit_logs",
)

ROLLBACK_ORDER: tuple[str, ...] = ("audits", "tokens", "consents")


def upgrade_consent_schema(engine: Any) -> list[str]:
    """Create the three guardian consent tables idempotently and return created table names."""
    register_guardian_consent_tables()
    CONSENT_METADATA.create_all(bind=engine)
    return list(CONSENT_TABLES)


def downgrade_consent_schema(engine: Any) -> list[str]:
    """Drop only the three guardian consent tables in reverse dependency order."""
    tables = register_guardian_consent_tables()
    dropped: list[str] = []
    for key in ROLLBACK_ORDER:
        tbl = tables[key]
        tbl.drop(bind=engine, checkfirst=True)
        dropped.append(tbl.name)
    return dropped


def verify_consent_schema(engine: Any) -> dict[str, bool]:
    """Return existence status for each of the three guardian consent tables."""
    existing = set(inspect(engine).get_table_names())
    return {name: (name in existing) for name in CONSENT_TABLES}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guardian AI consent schema migration tool")
    parser.add_argument("action", choices=("upgrade", "downgrade", "verify"))
    parser.add_argument("--database-url", required=True, help="Target SQLAlchemy database URL")
    parser.add_argument(
        "--confirm-downgrade",
        action="store_true",
        help="Explicitly confirm dropping guardian consent tables after backup",
    )
    args = parser.parse_args(argv)

    engine = create_engine(args.database_url)
    try:
        if args.action == "upgrade":
            created = upgrade_consent_schema(engine)
            print("UPGRADE_OK:", ",".join(created))
            return 0
        if args.action == "downgrade":
            env_confirmed = os.getenv("GUARDIAN_CONSENT_DOWNGRADE_CONFIRM", "").strip() == "YES"
            if not (args.confirm_downgrade or env_confirmed):
                print("DOWNGRADE_REFUSED: pass --confirm-downgrade or GUARDIAN_CONSENT_DOWNGRADE_CONFIRM=YES after backup")
                return 2
            dropped = downgrade_consent_schema(engine)
            print("DOWNGRADE_OK:", ",".join(dropped))
            return 0
        status = verify_consent_schema(engine)
        if not all(status.values()):
            print("VERIFY_FAIL:", status)
            return 1
        print("VERIFY_OK:", status)
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
