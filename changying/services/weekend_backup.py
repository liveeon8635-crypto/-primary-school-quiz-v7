"""Self-contained paper pack for an existing classroom; no extra student archive."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile

from fastapi import HTTPException
from sqlalchemy import func, select

from changying.services.weekend_roster import session_class, session_roster


def backup_material(impl, db, session, *, include_files=False):
    from changying.web.weekend_written import register_written_tables
    if session_class(impl, db, session) is None:
        raise HTTPException(409, '请先为原课堂指定班级，再生成备用包')
    lesson = db.get(impl.TeachingLesson, session.lesson_id)
    if lesson is None or lesson.school_id != session.school_id:
        raise HTTPException(404, '没有找到原教案')
    questions = []
    for q in db.scalars(select(impl.TeachingQuestion).where(impl.TeachingQuestion.school_id == session.school_id,
            impl.TeachingQuestion.lesson_id == session.lesson_id, impl.TeachingQuestion.active.is_(True)).order_by(impl.TeachingQuestion.id)):
        options = json.loads(q.options_json or '[]')
        if not isinstance(options, list) or not 0 <= q.correct_index < len(options):
            raise HTTPException(409, '有题目的选项或答案不完整，请先审核')
        questions.append(dict(kind='choice', id=q.id, stem=q.stem, options=options, selected=q.correct_index,
            reference=str(options[q.correct_index]), explanation=q.explanation or '', level=q.level,
            knowledge=q.knowledge or lesson.core_target or ''))
    wq = register_written_tables(impl)['questions']
    for q in db.execute(select(wq).where(wq.c.school_id == session.school_id, wq.c.session_id == session.id,
            wq.c.teacher_id == session.teacher_id).order_by(wq.c.id)):
        questions.append(dict(kind='written', id=q.id, stem=q.stem, reference=q.reference,
            explanation='', level='开放作答', knowledge=lesson.core_target or ''))
    if not questions:
        raise HTTPException(409, '请先审核或添加本节课题目')
    roster = [dict(id=i, name=n) for i, (n, _) in sorted(session_roster(impl, db, session).items())]
    if not roster:
        raise HTTPException(409, '本节课堂没有学生')
    if (len(lesson.reading_plan or '')+sum(len(q['stem'])+sum(len(str(x)) for x in q.get('options',[])) for q in questions))*len(roster)>4_000_000:
        raise HTTPException(413,'本课堂打印内容过大，请减少本次题目或分班准备')
    resource = impl.TeachingResource
    resources = db.execute(select(resource.id,resource.file_name,resource.file_ext,resource.sha256,
        func.length(resource.file_data).label('bytes')).where(resource.school_id == session.school_id,
        resource.lesson_id == session.lesson_id, func.lower(resource.file_ext).in_(['pdf','.pdf','docx','.docx','pptx','.pptx','txt','.txt','md','.md','png','.png','jpg','.jpg','jpeg','.jpeg'])).order_by(resource.id).limit(21)).all()
    resources = [r for r in resources if str(r.file_ext or '').lower().lstrip('.') in
                 ('pdf','docx','pptx','txt','md','png','jpg','jpeg')]
    if len(resources)>20 or sum(int(r.bytes or 0) for r in resources)>30*1024*1024:
        raise HTTPException(413, '关联原文件超过20份或30MB，请先整理本课资源')
    files = []
    for r in resources:
        item = dict(id=r.id,name=r.file_name,extension=str(r.file_ext).lower().lstrip('.'),sha256=r.sha256)
        if include_files:
            item['data'] = bytes(db.get(resource,r.id).file_data or b'')
            if r.sha256 and hashlib.sha256(item['data']).hexdigest()!=r.sha256:
                raise HTTPException(409,'原文件校验不一致，请检查教案附件')
        files.append(item)
    material = dict(sessionId=session.id, lessonId=lesson.id, title=session.title, subject=lesson.subject,
        className=session_class(impl, db, session).class_name, roster=roster, questions=questions,
        lesson={key: getattr(lesson, key) for key in ('core_target', 'duration_min', 'teacher_plan', 'reading_plan',
            'writing_plan', 'examples_json', 'ppt_json', 'closure_training', 'essay_review')},
        resources=[{k: f[k] for k in ('id', 'name', 'sha256')} for f in files])
    digest = hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    material.update(packageHash=digest, version=digest[:16])
    return material, files


def backup_zip(material):
    """Keep the existing ZIP URL, containing exactly the two requested Word files."""
    from changying.services.weekend_handouts import question_document
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
        for role, filename in [('teacher', '教师版.docx'), ('student', '学生版.docx')]:
            archive.writestr(filename, question_document(material, role))
    return out.getvalue()
