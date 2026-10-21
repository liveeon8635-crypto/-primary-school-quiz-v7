"""Authenticated paper backup and idempotent teacher transcription into original rows."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from changying.services.weekend_backup import backup_material, backup_zip


class PaperAnswer(BaseModel):
    version: str = Field(pattern=r'^[0-9a-f]{16}$')
    studentId: int = Field(gt=0)
    kind: str
    questionId: int = Field(gt=0)
    selected: int | None = None
    text: str = Field(default='', max_length=4000)
    photoBase64: str | None = Field(default=None, max_length=4 * 1024 * 1024 + 100)
    result: str = 'correct'
    hintLevel: int = Field(default=0, ge=0, le=3)
    stage: int = Field(default=4, ge=1, le=7)
    note: str = Field(min_length=1, max_length=500)
    occurredAt: datetime


def install_weekend_backup(impl):
    app = impl.app
    if getattr(app.state, 'weekend_backup_installed', False): return
    from changying.web.weekend_views import register_weekend_tables
    from changying.web.weekend_practice import register_practice_tables
    from changying.web.weekend_written import register_written_tables
    from changying.web.weekend_scoring_views import register_scoring_tables
    sessions = register_weekend_tables(impl)['sessions']
    pt, wt = register_practice_tables(impl), register_written_tables(impl)
    awards = register_scoring_tables(impl)['awards']
    router = APIRouter()

    def owned(db, u, sid, lock=False):
        impl.need(u, 'teacher')
        query = select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id, sessions.c.teacher_id == u.id)
        row = db.execute(query.with_for_update() if lock else query).first()
        if row is None: raise HTTPException(404, '没有找到你的原课堂')
        return row

    @router.get('/teacher/weekend/sessions/{sid}/backup.zip')
    def download(sid: int, u=Depends(impl.current_user), db=Depends(impl.get_db)):
        row = owned(db, u, sid)
        material, files = backup_material(impl, db, row, include_files=True)
        slide = impl.Base.metadata.tables['weekend_slide_state']
        cursor = db.execute(select(slide).where(slide.c.session_id == sid)).first()
        page = str(cursor.idx + 1) if cursor is not None and cursor.stage_no in (2,3) else '见原控制页题号'
        checkpoint = '环节 '+str(row.current_stage)+'，页码 '+page
        return Response(backup_zip(material, files, checkpoint), media_type='application/zip',
            headers={'Content-Disposition':f'attachment; filename=weekend-{sid}-paper-backup.zip','Cache-Control':'no-store','X-Changying-Paper-Version':material['version']})

    @router.get('/teacher/weekend/sessions/{sid}/backup')
    def status(sid: int, u=Depends(impl.current_user), db=Depends(impl.get_db)):
        row = owned(db, u, sid)
        material, _ = backup_material(impl, db, row)
        saved = []
        for kind, table in [('choice',pt['answers']),('written',wt['submissions'])]:
            saved.extend({'studentId':a.student_id,'kind':kind,'questionId':a.question_id} for a in
                db.execute(select(table).where(table.c.session_id == sid, table.c.school_id == u.school_id)))
        return {'version':material['version'],'status':row.status,'stage':row.current_stage,
            'students':material['roster'],'questions':material['questions'],'recorded':saved,
            'settled':bool(db.scalar(select(func.count()).select_from(awards).where(awards.c.session_id == sid)))}

    @router.post('/teacher/weekend/sessions/{sid}/backup-record')
    def record(sid: int, b: PaperAnswer, u=Depends(impl.current_user), db=Depends(impl.get_db)):
        row = owned(db, u, sid, True)
        if row.status != 'finished':
            raise HTTPException(409, '请先结束原课堂，再进行课后纸质补录；避免课堂中提前泄露答案')
        material, _ = backup_material(impl, db, row)
        if b.version != material['version']:
            raise HTTPException(409, '纸质包版本与原课堂不一致，请核对教案、班级和题目；本次未写入')
        if b.studentId not in {p['id'] for p in material['roster']}:
            raise HTTPException(404, '这位学生不在原课堂班级中')
        question = next((q for q in material['questions'] if q['kind'] == b.kind and q['id'] == b.questionId),None)
        if question is None: raise HTTPException(404, '不是原课堂的题目')
        if not b.note.strip(): raise HTTPException(400, '请填写纸质补录原因或答卷编号')
        if b.occurredAt.tzinfo is None: raise HTTPException(400, '请提供带时区的实际作答时间')
        when = b.occurredAt.astimezone(timezone.utc).replace(tzinfo=None)
        if when > datetime.utcnow()+timedelta(minutes=5): raise HTTPException(400, '实际作答时间不能在未来')
        photo = None
        if b.photoBase64:
            if b.kind != 'written': raise HTTPException(400, '选择题请填写所选选项')
            try: photo = base64.b64decode(b.photoBase64, validate=True)
            except (ValueError, TypeError): raise HTTPException(400, '照片编码无效')
            if len(photo)>3*1024*1024: raise HTTPException(413, '照片不能超过3MB')
            if photo.startswith(b'\xff\xd8\xff') and photo.endswith(b'\xff\xd9'): mime='image/jpeg'
            elif photo.startswith(b'\x89PNG\r\n\x1a\n') and photo.endswith(b'IEND\xaeB`\x82'): mime='image/png'
            else: raise HTTPException(400, '请上传有效的JPEG或PNG照片')
        else: mime=''
        if b.kind == 'choice':
            if b.selected is None or not 0 <= b.selected < len(question['options']): raise HTTPException(400, '请选择原题选项')
            correct = b.selected == question['selected']
            answer_text = str(question['options'][b.selected])
            table, hlog = pt['answers'], pt['log']
        else:
            if b.result not in ('correct','partial','revise') or not (b.text.strip() or photo):
                raise HTTPException(400, '请填写原答案或上传答卷照片，并选择批改结果')
            correct, answer_text = b.result == 'correct', b.text.strip()
            table, hlog = wt['submissions'], wt['hint_log']
        old = db.execute(select(table).where(table.c.session_id==sid, table.c.student_id==b.studentId, table.c.question_id==b.questionId)).first()
        if old is not None:
            same = old.selected == b.selected if b.kind == 'choice' else old.answer_text == answer_text and old.photo == photo and old.result == b.result
            if same: return {'recorded':False,'alreadyRecorded':True,'message':'已有相同作答，已保留，不重复记录或发分'}
            raise HTTPException(409, '已有线上或纸质作答，本次未覆盖；请到原批改页面核对')
        if db.scalar(select(func.count()).select_from(awards).where(awards.c.session_id==sid)):
            raise HTTPException(409, '原课堂已结算，请先核对结算记录，不能再补入改变积分依据')
        used = db.scalar(select(func.max(hlog.c.level)).where(hlog.c.session_id==sid,hlog.c.student_id==b.studentId,hlog.c.question_id==b.questionId)) or 0
        level = max(int(used),b.hintLevel)
        now = datetime.utcnow()
        try:
            values = dict(school_id=u.school_id,session_id=sid,student_id=b.studentId,question_id=b.questionId)
            if b.kind=='choice': values.update(selected=b.selected,correct=correct,max_hint=level,created_at=when)
            else: values.update(answer_text=answer_text,photo=photo,photo_type=mime,revision=1,result=b.result,
                                comment='纸质补录：'+b.note.strip(),submitted_at=when,reviewed_at=now)
            db.execute(insert(table).values(**values))
            for hint in range(int(used)+1,level+1):
                db.execute(insert(hlog).values(school_id=u.school_id,session_id=sid,student_id=b.studentId,question_id=b.questionId,level=hint,created_at=when))
            context = {'sessionId':sid,'lessonId':row.lesson_id,'studentId':b.studentId,'questionId':b.questionId,
                'kind':b.kind,'stage':b.stage,'packageHash':material['packageHash'],'hintLevel':level,'reason':b.note.strip(),'source':'paper_backup'}
            impl.audit(db,u,'weekend.backup.record',json.dumps(context,ensure_ascii=False))
            db.add(impl.LearningEvidenceEvent(school_id=u.school_id,student_id=b.studentId,actor_id=u.id,event_kind='record',
                evidence_type='performance',subject=material['subject'],knowledge_key=question['knowledge'][:160],
                success=correct if b.kind=='choice' or b.result!='partial' else None,note='周末课纸质作答补录（教师核对）',
                context=json.dumps(context,ensure_ascii=False),source_type='classroom',occurred_at=when))
            if not correct:
                db.add(impl.WrongQuestionRecord(school_id=u.school_id,student_id=b.studentId,source='weekend_backup',
                    subject=material['subject'],knowledge=question['knowledge'][:120],problem_text=question['stem'],
                    wrong_answer=answer_text or '见原课堂答卷照片',correct_answer=question.get('reference',''),
                    analysis=question.get('explanation',''),teacher_feedback=f'原课堂 {sid} · {b.kind}:{b.questionId} · 纸质补录',status='active'))
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409,'这道题已被另一请求记录，请刷新核对；未重复写入')
        return {'recorded':True,'alreadyRecorded':False,'message':'已补入原课堂，学习记录已保存；请核对后使用原积分结算'}

    app.include_router(router)
    app.state.weekend_backup_installed = True
