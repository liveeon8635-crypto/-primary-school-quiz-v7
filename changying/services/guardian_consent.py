"""Student-level guardian AI consent, one-time token verification, and unified AI egress guard.

Implements P0-2 safety controls:
1. Platform compliance gate (``STUDENT_AI_COMPLIANCE_APPROVED``, default off).
2. Teacher/workspace global AI student-data switch (``SchoolAIConfig.allow_student_data``).
3. Student-level guardian consent (``guardian_ai_consents``) with distinct ``valid_until``
   and ``retention_until`` timestamps.
4. Atomic one-time token confirmation (``guardian_consent_tokens``, SHA-256 hashed) bound
   to logged-in parent identity and ``ParentStudent`` link.
5. Unified pre-send and pre-retry authorization check for all external AI HTTP send points,
   with traceable audit logging that never stores API keys, plaintext tokens, or sensitive
   student content.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Table,
    Text,
    and_,
    insert,
    select,
    update,
)

COMPLIANCE_FLAG = "STUDENT_AI_COMPLIANCE_APPROVED"

CONSENT_SCOPES: tuple[str, ...] = (
    "student_ai_all",
    "homework_help",
    "weekend_review",
    "knowledge_map_ai",
    "exam_prep_ai",
)

FEATURE_TO_SCOPE: dict[str, str] = {
    "homework_notice_parse": "homework_help",
    "homework_notice_vision": "homework_help",
    "homework_help_vision": "homework_help",
    "homework_help_guide": "homework_help",
    "homework_help_solve": "homework_help",
    "homework_practice": "homework_help",
    "weekend_report": "weekend_review",
    "weekend_report_suggest": "weekend_review",
    "weekend_written_score": "weekend_review",
    "weekend_written_precheck": "weekend_review",
    "knowledge_map_student_ai": "knowledge_map_ai",
    "exam_prep_student_ai": "exam_prep_ai",
}

DEFAULT_VALID_DAYS = 180
DEFAULT_RETENTION_DAYS = 365 * 3
TOKEN_TTL_HOURS = 72


def compliance_student_ai_enabled() -> bool:
    """Return True only when formal legal/compliance approval flag is explicitly enabled."""
    return os.getenv(COMPLIANCE_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


def hash_consent_token(raw_token: str) -> str:
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


def register_guardian_consent_tables(implementation: Any) -> dict[str, Table]:
    md = implementation.Base.metadata
    if "guardian_ai_consents" not in md.tables:
        Table(
            "guardian_ai_consents",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("guardian_user_id", Integer, nullable=True, index=True),
            Column("status", String(20), nullable=False, default="active", index=True),
            Column("scope", String(64), nullable=False),
            Column("policy_version", String(32), nullable=False),
            Column("verification_method", String(32), nullable=False),
            Column("verifier_user_id", Integer, nullable=True),
            Column("proof_digest", String(128), nullable=True),
            Column("verified_at", DateTime, nullable=False),
            Column("valid_until", DateTime, nullable=False, index=True),
            Column("retention_until", DateTime, nullable=False),
            Column("revoked_at", DateTime, nullable=True),
            Column("revoked_by", Integer, nullable=True),
            Column("revoke_reason", String(200), nullable=False, default=""),
            Column("created_at", DateTime, nullable=False),
            Column("updated_at", DateTime, nullable=False),
            Index("ix_guardian_consent_lookup", "school_id", "student_id", "status"),
        )
    if "guardian_consent_tokens" not in md.tables:
        Table(
            "guardian_consent_tokens",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("created_by", Integer, nullable=False),
            Column("token_hash", String(64), nullable=False, unique=True),
            Column("scope", String(64), nullable=False),
            Column("policy_version", String(32), nullable=False),
            Column("valid_days", Integer, nullable=False, default=DEFAULT_VALID_DAYS),
            Column("expires_at", DateTime, nullable=False, index=True),
            Column("consumed_at", DateTime, nullable=True),
            Column("consumed_by", Integer, nullable=True),
            Column("revoked_at", DateTime, nullable=True),
            Column("created_at", DateTime, nullable=False),
        )
    if "guardian_consent_audit_logs" not in md.tables:
        Table(
            "guardian_consent_audit_logs",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=True, index=True),
            Column("actor_user_id", Integer, nullable=True),
            Column("action", String(48), nullable=False, index=True),
            Column("scope", String(64), nullable=False, default=""),
            Column("detail", Text, nullable=False, default=""),
            Column("created_at", DateTime, nullable=False, index=True),
        )
    return {
        "consents": md.tables["guardian_ai_consents"],
        "tokens": md.tables["guardian_consent_tokens"],
        "audits": md.tables["guardian_consent_audit_logs"],
    }


def _record_audit(
    db: Any,
    audits_table: Table,
    *,
    school_id: int,
    student_id: int | None,
    actor_user_id: int | None,
    action: str,
    scope: str = "",
    detail: str = "",
) -> None:
    db.execute(
        insert(audits_table).values(
            school_id=int(school_id),
            student_id=int(student_id) if student_id is not None else None,
            actor_user_id=int(actor_user_id) if actor_user_id is not None else None,
            action=action[:48],
            scope=(scope or "")[:64],
            detail=(detail or "")[:400],
            created_at=datetime.utcnow(),
        )
    )


def create_consent_token(
    db: Any,
    implementation: Any,
    *,
    teacher: Any,
    student_id: int,
    scope: str = "student_ai_all",
    policy_version: str = "v1.0",
    valid_days: int = DEFAULT_VALID_DAYS,
    ttl_hours: int = TOKEN_TTL_HOURS,
) -> dict[str, Any]:
    if scope not in CONSENT_SCOPES:
        raise HTTPException(400, "授权范围无效")
    if valid_days < 1 or valid_days > 365:
        raise HTTPException(400, "授权有效天数须在 1-365 之间")
    tables = register_guardian_consent_tables(implementation)
    now = datetime.utcnow()
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_consent_token(raw_token)
    expires_at = now + timedelta(hours=max(1, ttl_hours))
    db.execute(
        insert(tables["tokens"]).values(
            school_id=int(teacher.school_id),
            student_id=int(student_id),
            created_by=int(teacher.id),
            token_hash=token_hash,
            scope=scope,
            policy_version=policy_version[:32],
            valid_days=int(valid_days),
            expires_at=expires_at,
            consumed_at=None,
            consumed_by=None,
            revoked_at=None,
            created_at=now,
        )
    )
    _record_audit(
        db,
        tables["audits"],
        school_id=int(teacher.school_id),
        student_id=int(student_id),
        actor_user_id=int(teacher.id),
        action="token.create",
        scope=scope,
        detail=f"policy={policy_version[:32]}:valid_days={int(valid_days)}",
    )
    db.commit()
    return {
        "token": raw_token,
        "studentId": int(student_id),
        "scope": scope,
        "policyVersion": policy_version[:32],
        "expiresAt": expires_at.isoformat(timespec="seconds"),
    }


def confirm_consent_token(
    db: Any,
    implementation: Any,
    *,
    raw_token: str,
    parent_user: Any,
    expected_student_id: int | None = None,
) -> dict[str, Any]:
    """Atomically consume a one-time token for the logged-in linked parent."""
    if getattr(parent_user, "role", "") != "parent":
        raise HTTPException(403, "仅已登录的家长账号可确认监护人授权")
    tables = register_guardian_consent_tables(implementation)
    tokens_t, consents_t, audits_t = tables["tokens"], tables["consents"], tables["audits"]
    token_hash = hash_consent_token(raw_token)
    tok = db.execute(select(tokens_t).where(tokens_t.c.token_hash == token_hash)).first()
    if tok is None:
        raise HTTPException(404, "授权确认链接无效")
    if int(tok.school_id) != int(parent_user.school_id):
        raise HTTPException(403, "无权跨工作室确认该授权链接")
    if expected_student_id is not None and int(tok.student_id) != int(expected_student_id):
        raise HTTPException(403, "授权链接与当前学生不匹配")

    ParentStudent = implementation.ParentStudent
    linked = db.scalar(
        select(ParentStudent.id).where(
            ParentStudent.parent_id == parent_user.id,
            ParentStudent.student_id == tok.student_id,
        )
    )
    if not linked:
        _record_audit(
            db,
            audits_t,
            school_id=int(tok.school_id),
            student_id=int(tok.student_id),
            actor_user_id=int(parent_user.id),
            action="consent.denied",
            scope=str(tok.scope),
            detail="parent_student_link_missing",
        )
        db.commit()
        raise HTTPException(403, "当前家长账号尚未绑定该学生，无法确认授权")

    now = datetime.utcnow()
    res = db.execute(
        update(tokens_t)
        .where(
            and_(
                tokens_t.c.id == tok.id,
                tokens_t.c.consumed_at.is_(None),
                tokens_t.c.revoked_at.is_(None),
                tokens_t.c.expires_at > now,
            )
        )
        .values(consumed_at=now, consumed_by=int(parent_user.id))
    )
    if res.rowcount != 1:
        raise HTTPException(409, "授权确认链接已使用、已撤回或已过期")

    db.execute(
        update(consents_t)
        .where(
            consents_t.c.school_id == tok.school_id,
            consents_t.c.student_id == tok.student_id,
            consents_t.c.scope == tok.scope,
            consents_t.c.status == "active",
        )
        .values(
            status="revoked",
            revoked_at=now,
            revoked_by=int(parent_user.id),
            revoke_reason="superseded_by_new_consent",
            updated_at=now,
        )
    )
    valid_until = now + timedelta(days=int(tok.valid_days or DEFAULT_VALID_DAYS))
    retention_until = now + timedelta(days=DEFAULT_RETENTION_DAYS)
    db.execute(
        insert(consents_t).values(
            school_id=int(tok.school_id),
            student_id=int(tok.student_id),
            guardian_user_id=int(parent_user.id),
            status="active",
            scope=str(tok.scope),
            policy_version=str(tok.policy_version),
            verification_method="parent_link",
            verifier_user_id=int(parent_user.id),
            proof_digest="",
            verified_at=now,
            valid_until=valid_until,
            retention_until=retention_until,
            revoked_at=None,
            revoked_by=None,
            revoke_reason="",
            created_at=now,
            updated_at=now,
        )
    )
    _record_audit(
        db,
        audits_t,
        school_id=int(tok.school_id),
        student_id=int(tok.student_id),
        actor_user_id=int(parent_user.id),
        action="consent.grant",
        scope=str(tok.scope),
        detail=f"method=parent_link:policy={tok.policy_version}",
    )
    db.commit()
    return {
        "ok": True,
        "studentId": int(tok.student_id),
        "scope": str(tok.scope),
        "status": "active",
        "validUntil": valid_until.isoformat(timespec="seconds"),
        "retentionUntil": retention_until.isoformat(timespec="seconds"),
    }


def record_proof_consent(
    db: Any,
    implementation: Any,
    *,
    teacher: Any,
    student_id: int,
    verification_method: str,
    proof_digest: str,
    scope: str = "student_ai_all",
    policy_version: str = "v1.0",
    valid_days: int = DEFAULT_VALID_DAYS,
) -> dict[str, Any]:
    if verification_method not in ("written_proof", "electronic_proof"):
        raise HTTPException(400, "备用凭证类型无效")
    digest = (proof_digest or "").strip()
    if len(digest) < 6:
        raise HTTPException(400, "请填写可核验的凭证摘要或编号")
    if scope not in CONSENT_SCOPES:
        raise HTTPException(400, "授权范围无效")
    tables = register_guardian_consent_tables(implementation)
    consents_t, audits_t = tables["consents"], tables["audits"]
    now = datetime.utcnow()
    db.execute(
        update(consents_t)
        .where(
            consents_t.c.school_id == int(teacher.school_id),
            consents_t.c.student_id == int(student_id),
            consents_t.c.scope == scope,
            consents_t.c.status == "active",
        )
        .values(
            status="revoked",
            revoked_at=now,
            revoked_by=int(teacher.id),
            revoke_reason="superseded_by_new_proof",
            updated_at=now,
        )
    )
    valid_until = now + timedelta(days=max(1, min(int(valid_days), 365)))
    retention_until = now + timedelta(days=DEFAULT_RETENTION_DAYS)
    db.execute(
        insert(consents_t).values(
            school_id=int(teacher.school_id),
            student_id=int(student_id),
            guardian_user_id=None,
            status="active",
            scope=scope,
            policy_version=policy_version[:32],
            verification_method=verification_method,
            verifier_user_id=int(teacher.id),
            proof_digest=digest[:128],
            verified_at=now,
            valid_until=valid_until,
            retention_until=retention_until,
            revoked_at=None,
            revoked_by=None,
            revoke_reason="",
            created_at=now,
            updated_at=now,
        )
    )
    _record_audit(
        db,
        audits_t,
        school_id=int(teacher.school_id),
        student_id=int(student_id),
        actor_user_id=int(teacher.id),
        action="consent.proof",
        scope=scope,
        detail=f"method={verification_method}:policy={policy_version[:32]}",
    )
    db.commit()
    return {
        "ok": True,
        "studentId": int(student_id),
        "scope": scope,
        "status": "active",
        "validUntil": valid_until.isoformat(timespec="seconds"),
        "retentionUntil": retention_until.isoformat(timespec="seconds"),
    }


def revoke_student_consent(
    db: Any,
    implementation: Any,
    *,
    school_id: int,
    student_id: int,
    actor_user_id: int,
    scope: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    tables = register_guardian_consent_tables(implementation)
    consents_t, tokens_t, audits_t = tables["consents"], tables["tokens"], tables["audits"]
    now = datetime.utcnow()
    conds = [
        consents_t.c.school_id == int(school_id),
        consents_t.c.student_id == int(student_id),
        consents_t.c.status == "active",
    ]
    if scope:
        conds.append(consents_t.c.scope == scope)
    res = db.execute(
        update(consents_t)
        .where(*conds)
        .values(
            status="revoked",
            revoked_at=now,
            revoked_by=int(actor_user_id),
            revoke_reason=(reason or "guardian_or_teacher_revoked")[:200],
            updated_at=now,
        )
    )
    tok_conds = [
        tokens_t.c.school_id == int(school_id),
        tokens_t.c.student_id == int(student_id),
        tokens_t.c.consumed_at.is_(None),
        tokens_t.c.revoked_at.is_(None),
    ]
    if scope:
        tok_conds.append(tokens_t.c.scope == scope)
    db.execute(update(tokens_t).where(*tok_conds).values(revoked_at=now))
    _record_audit(
        db,
        audits_t,
        school_id=int(school_id),
        student_id=int(student_id),
        actor_user_id=int(actor_user_id),
        action="consent.revoke",
        scope=scope or "all",
        detail=(reason or "revoked")[:200],
    )
    db.commit()
    return {"ok": True, "revokedCount": int(res.rowcount or 0)}


def _has_active_consent(db: Any, consents_t: Table, school_id: int, student_id: int, scope: str, now: datetime) -> bool:
    row = db.execute(
        select(consents_t.c.id).where(
            consents_t.c.school_id == int(school_id),
            consents_t.c.student_id == int(student_id),
            consents_t.c.status == "active",
            consents_t.c.valid_until > now,
            consents_t.c.scope.in_(("student_ai_all", scope)),
        ).limit(1)
    ).first()
    return row is not None


def require_student_ai_authorized(
    db: Any,
    implementation: Any,
    *,
    school_id: int,
    feature: str,
    student_ids: Iterable[int] = (),
    actor_user_id: int | None = None,
    require_guardian_for_personal: bool = True,
) -> None:
    """Unified authorization check before ANY external AI HTTP call carrying student data."""
    scope = FEATURE_TO_SCOPE.get(feature, "student_ai_all")
    is_personal = bool(implementation.is_individual_school(db, int(school_id)))
    config = implementation.ai_config_for(db, int(school_id), False)
    tables = register_guardian_consent_tables(implementation)
    audits_t = tables["audits"]
    consents_t = tables["consents"]

    def _deny(status_code: int, message: str, reason: str, sid: int | None = None) -> None:
        _record_audit(
            db,
            audits_t,
            school_id=int(school_id),
            student_id=sid,
            actor_user_id=actor_user_id,
            action="egress.blocked",
            scope=scope,
            detail=f"feature={feature}:reason={reason}",
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(status_code, message)

    if is_personal and not compliance_student_ai_enabled():
        _deny(
            403,
            "真实学生数据外部 AI 处理尚未通过合规开放，请先手动处理或使用示例模式",
            "compliance_gate_closed",
        )

    if not config or not config.enabled:
        msg = "AI 教学助手尚未启用，请先在「AI 设置」完成配置并启用" if is_personal else "AI 教学助手尚未启用，请联系学校管理员完成 AI 设置"
        _deny(503, msg, "ai_disabled")

    sids = [int(x) for x in dict.fromkeys(student_ids) if x is not None]
    if not config.allow_student_data and (is_personal or sids or feature == "homework_notice_parse"):
        msg = (
            "尚未开启发送学生内容授权，请先前往「AI 设置」开启并完成监护人授权"
            if is_personal
            else "学校管理员尚未允许把学生内容发送到 AI 服务商，请先手动录入"
        )
        _deny(403, msg, "allow_student_data_false")
    if is_personal and require_guardian_for_personal:
        if not sids:
            _deny(
                403,
                "未指定已获监护人授权的学生对象，禁止向外部 AI 发送真实学生数据",
                "missing_student_consent_target",
            )
        now = datetime.utcnow()
        for sid in sids:
            if not _has_active_consent(db, consents_t, int(school_id), sid, scope, now):
                _deny(
                    403,
                    "该学生尚未完成或已撤回监护人 AI 授权，禁止向外部 AI 发送学生数据",
                    "guardian_consent_missing_or_revoked",
                    sid=sid,
                )
