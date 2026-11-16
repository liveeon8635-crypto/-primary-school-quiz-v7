"""Per-teacher, shared-database limit for exact parent-account lookups."""
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select


def limit_parent_lookup(db, user, user_model, audit_model, *, now=None):
    """Record attempts without storing the searched account; serialize per user on PostgreSQL."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(minutes=10)
    # Unlike a process-local tracker, this row lock and audit history are shared
    # by all application workers that use the same PostgreSQL database.
    db.execute(select(user_model.id).where(user_model.id == user.id,
               user_model.school_id == user.school_id).with_for_update()).first()
    base = (audit_model.school_id == user.school_id, audit_model.user_id == user.id,
            audit_model.created_at >= cutoff)
    count = db.scalar(select(func.count()).select_from(audit_model).where(
        *base, audit_model.action == "parent.lookup.attempt")) or 0
    if count >= 10:
        denied = db.scalar(select(audit_model.id).where(*base,
            audit_model.action == "parent.lookup.limited").limit(1))
        if denied is None:
            db.add(audit_model(school_id=user.school_id, user_id=user.id,
                               action="parent.lookup.limited", detail="rate limit", created_at=now))
        db.commit()
        raise HTTPException(429, "查询次数过多，请稍后再试")
    db.add(audit_model(school_id=user.school_id, user_id=user.id,
                       action="parent.lookup.attempt", detail="exact account", created_at=now))
    db.commit()
