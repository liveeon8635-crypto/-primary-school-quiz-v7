"""Three student submissions, independent of grading revisions, using the audit log."""
import json
from fastapi import HTTPException
from sqlalchemy import select


def submission_attempts(impl, db, user, session_id, kind, question_id, exists=False):
    action = f'weekend.submit.{kind}.{session_id}.{question_id}'
    log = impl.AuditLog
    detail = db.scalar(select(log.detail).where(log.school_id == user.school_id,
        log.user_id == user.id, log.action == action).order_by(log.id.desc()).limit(1))
    return int(json.loads(detail)['attempt']) if detail else int(bool(exists))


def record_submission(impl, db, user, session_id, kind, question_id, attempt):
    impl.audit(db, user, f'weekend.submit.{kind}.{session_id}.{question_id}', json.dumps({'attempt': attempt}))


def require_unsettled(impl, db, session_id):
    awards = impl.Base.metadata.tables['weekend_awards']
    if db.execute(select(awards.c.id).where(awards.c.session_id == session_id).limit(1)).first():
        raise HTTPException(409, '本课堂已结算，答案和批改已锁定')
